"""
批量论文分析器（使用 Batches API，5折优惠）
============================================

核心流程：
  1. 为每篇论文构造分析请求（prompt）
  2. 批量提交到 Batches API（异步处理，成本减半）
  3. 轮询直到 batch 完成
  4. 解析结果，保存每篇论文的结构化分析

每篇论文分析内容：
  - 一句话摘要
  - 核心贡献（3-5条）
  - 技术方法
  - 实验/数据集
  - 局限性
  - 与其他工作的关系
  - 综述主题分类
  - 重要程度评分（1-5）

使用 Batches API 好处：
  - 成本降低 50%（相比同步 API）
  - 无需担心速率限制
  - 支持大规模并发处理
"""

import json
import time
import anthropic
from pathlib import Path
from typing import Optional

from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from vla_pipeline.vla_queries import SURVEY_THEMES

ANALYSES_DIR  = Path(__file__).parent.parent / "outputs" / "paper_analyses"
BATCH_JOB_DIR = Path(__file__).parent.parent / "outputs" / "batch_jobs"

ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
BATCH_JOB_DIR.mkdir(parents=True, exist_ok=True)

# ── 每篇论文的分析 Prompt ────────────────────────────────────────
ANALYSIS_SYSTEM = """你是一位具身智能与机器人学习领域的专家研究员，正在撰写关于
Vision-Language-Action（VLA）模型与具身智能的系统综述。

请对给定论文进行深度分析，严格按照指定 JSON 格式输出，不要输出任何额外文字。
所有字段使用中文填写（技术术语可保留英文）。"""

def _make_analysis_prompt(paper: dict) -> str:
    """为单篇论文生成分析请求的 user prompt"""
    themes_list = "\n".join(f"- {k}：{v}" for k, v in SURVEY_THEMES.items())
    return f"""请深度分析以下论文，并严格按照 JSON 格式输出：

## 论文信息
- **标题**：{paper['title']}
- **作者**：{', '.join(paper['authors'][:5])}
- **发表时间**：{paper['published']}
- **arXiv ID**：{paper['id']}
- **类别**：{', '.join(paper.get('categories', []))}
- **会议/期刊**：{paper.get('comment', '') or paper.get('journal_ref', '') or '待确认'}

## 摘要
{paper['abstract']}

---

请按以下 JSON 结构输出分析结果（所有字段必填，使用中文）：

```json
{{
  "arxiv_id": "{paper['id']}",
  "title_zh": "论文标题的中文翻译",
  "one_sentence_summary": "一句话概括这篇论文做了什么（30字以内）",
  "key_contributions": [
    "贡献1：...",
    "贡献2：...",
    "贡献3：..."
  ],
  "technical_approach": "技术方法描述（100-200字）：模型架构、训练策略、创新点",
  "datasets_and_benchmarks": ["数据集/基准1", "数据集/基准2"],
  "key_results": "主要实验结果和性能指标（50-100字）",
  "limitations": "局限性与不足（50字以内）",
  "connections_to_vla": "与VLA/具身智能领域其他工作的关系（50-100字）",
  "survey_theme": "从以下主题中选一个最匹配的：{list(SURVEY_THEMES.keys())}",
  "importance_score": 4,
  "keywords": ["关键词1", "关键词2", "关键词3"]
}}
```

主题选项说明：
{themes_list}

重要程度评分标准（1-5）：
- 5：领域奠基性工作，高引用，直接推动了VLA发展
- 4：重要贡献，在某个技术方向有突破
- 3：有价值的工作，提供了新数据/方法/分析
- 2：普通工作，贡献有限
- 1：边缘相关，仅供参考"""


def build_batch_requests(papers: list[dict]) -> list[Request]:
    """为所有论文构建 Batch API 请求列表"""
    requests = []
    for paper in papers:
        custom_id = f"paper_{paper['id'].replace('.', '_')}"
        requests.append(Request(
            custom_id=custom_id,
            params=MessageCreateParamsNonStreaming(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=ANALYSIS_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": _make_analysis_prompt(paper)
                }],
            )
        ))
    return requests


def submit_batch(papers: list[dict], client: anthropic.Anthropic) -> str:
    """
    提交 batch 任务，返回 batch_id

    如果本地已有未完成的 batch，可以选择继续等待（不重复提交）。
    """
    job_record_file = BATCH_JOB_DIR / "current_batch.json"

    # 检查是否已有进行中的 batch
    if job_record_file.exists():
        with open(job_record_file, encoding="utf-8") as f:
            record = json.load(f)
        existing_batch_id = record.get("batch_id")
        if existing_batch_id:
            try:
                batch = client.messages.batches.retrieve(existing_batch_id)
                if batch.processing_status != "ended":
                    print(f"⚡ 发现进行中的 batch：{existing_batch_id}（状态：{batch.processing_status}）")
                    print(f"   将继续等待此 batch 完成，而非重新提交。")
                    return existing_batch_id
                else:
                    print(f"✓ 已找到已完成的 batch：{existing_batch_id}")
                    return existing_batch_id
            except Exception:
                pass  # batch 可能已过期，重新提交

    # 构建请求并提交
    print(f"\n📤 提交 {len(papers)} 篇论文到 Batches API...")
    requests = build_batch_requests(papers)

    # Batches API 单次最多 100,000 条，我们分批处理
    BATCH_SIZE = 100  # 安全起见每批 100 条
    all_batch_ids = []

    for chunk_start in range(0, len(requests), BATCH_SIZE):
        chunk = requests[chunk_start:chunk_start + BATCH_SIZE]
        batch = client.messages.batches.create(requests=chunk)
        all_batch_ids.append(batch.id)
        print(f"   ✓ Batch {len(all_batch_ids)} 已提交：{batch.id}（{len(chunk)} 篇）")

    # 只记录第一个 batch（通常论文数 < 100，只有一个）
    primary_batch_id = all_batch_ids[0]
    record = {
        "batch_id": primary_batch_id,
        "all_batch_ids": all_batch_ids,
        "paper_count": len(papers),
        "submitted_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    with open(job_record_file, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)

    print(f"💾 batch 记录已保存：{job_record_file}")
    return primary_batch_id


def wait_for_batch(batch_id: str, client: anthropic.Anthropic, poll_interval: int = 60) -> None:
    """轮询等待 batch 完成（每 60 秒查询一次）"""
    print(f"\n⏳ 等待 Batch {batch_id} 完成（每 {poll_interval} 秒轮询一次）...")

    start_time = time.time()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        elapsed = (time.time() - start_time) / 60

        status_line = (
            f"   [{elapsed:.1f}min] 状态：{batch.processing_status} | "
            f"处理中：{counts.processing} | "
            f"成功：{counts.succeeded} | "
            f"错误：{counts.errored}"
        )
        print(status_line)

        if batch.processing_status == "ended":
            print(f"\n✅ Batch 完成！")
            print(f"   成功：{counts.succeeded} 篇")
            print(f"   错误：{counts.errored} 篇")
            print(f"   耗时：{elapsed:.1f} 分钟")
            break

        time.sleep(poll_interval)


def collect_batch_results(
    batch_id: str,
    client: anthropic.Anthropic,
) -> dict[str, dict]:
    """
    收集 batch 结果，解析 JSON，保存每篇论文的分析到文件

    返回：
        arxiv_id → 分析结果字典
    """
    print(f"\n📥 收集 Batch {batch_id} 结果...")
    analyses: dict[str, dict] = {}

    for result in client.messages.batches.results(batch_id):
        if result.result.type != "succeeded":
            print(f"   ⚠ {result.custom_id} 失败：{result.result.type}")
            continue

        msg = result.result.message
        # 提取文本内容
        text = next((b.text for b in msg.content if b.type == "text"), "")

        # 从 markdown code block 中提取 JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        try:
            analysis = json.loads(text)
        except json.JSONDecodeError:
            # 尝试找到第一个 { 到最后一个 } 之间的内容
            try:
                start = text.index("{")
                end   = text.rindex("}") + 1
                analysis = json.loads(text[start:end])
            except Exception:
                print(f"   ⚠ {result.custom_id} JSON 解析失败，跳过")
                continue

        arxiv_id = analysis.get("arxiv_id", result.custom_id.replace("paper_", "").replace("_", "."))
        analyses[arxiv_id] = analysis

        # 保存单篇分析到文件
        safe_id = arxiv_id.replace(".", "_")
        out_file = ANALYSES_DIR / f"{safe_id}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)

    print(f"✓ 成功解析 {len(analyses)} 篇论文分析")
    # 保存汇总
    summary_file = BATCH_JOB_DIR / "all_analyses.json"
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(analyses, f, ensure_ascii=False, indent=2)
    print(f"💾 汇总已保存：{summary_file}")

    return analyses


def load_existing_analyses() -> dict[str, dict]:
    """加载已有的分析结果（用于断点续传）"""
    analyses = {}
    if ANALYSES_DIR.exists():
        for f in ANALYSES_DIR.glob("*.json"):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                arxiv_id = data.get("arxiv_id", f.stem.replace("_", "."))
                analyses[arxiv_id] = data
            except Exception:
                pass
    return analyses


def run_batch_analysis(
    papers: list[dict],
    skip_existing: bool = True,
    poll_interval: int = 60,
) -> dict[str, dict]:
    """
    完整的批量分析流程入口

    参数:
        papers:         论文列表
        skip_existing:  是否跳过已分析的论文（断点续传）
        poll_interval:  轮询间隔（秒）

    返回:
        arxiv_id → 分析结果
    """
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    # 断点续传：加载已有分析
    existing = load_existing_analyses() if skip_existing else {}
    if existing:
        print(f"📂 已有 {len(existing)} 篇分析，将跳过这些论文")

    # 过滤已分析的论文
    to_analyze = [p for p in papers if p["id"] not in existing]
    print(f"📋 需要分析：{len(to_analyze)} 篇（跳过 {len(existing)} 篇已有结果）")

    if not to_analyze:
        print("✅ 所有论文已分析完毕！")
        return existing

    # 提交 batch
    batch_id = submit_batch(to_analyze, client)

    # 等待完成
    wait_for_batch(batch_id, client, poll_interval)

    # 收集结果
    new_analyses = collect_batch_results(batch_id, client)

    # 合并
    all_analyses = {**existing, **new_analyses}
    print(f"\n📊 分析汇总：共 {len(all_analyses)} 篇")
    return all_analyses
