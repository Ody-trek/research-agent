"""
VLA 综述生成器
===============

使用 Claude Opus 4.6 + adaptive thinking + 流式输出
将论文分析结果整合为一篇结构完整的 Markdown 综述。

综述结构：
  0. 封面 & 目录
  1. 引言（研究背景、动机、综述范围）
  2. 各主题章节（每个主题一章，含代表论文分析）
  3. 技术趋势对比表格
  4. 开放问题与未来方向
  5. 参考文献列表

使用 streaming 输出，实时显示生成进度（综述很长，防止超时）。
"""

import json
import time
import anthropic
from pathlib import Path
from collections import defaultdict

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from vla_pipeline.vla_queries import SURVEY_THEMES, SURVEY_TITLE, SURVEY_SUBTITLE

SURVEYS_DIR = Path(__file__).parent.parent / "outputs" / "surveys"
SURVEYS_DIR.mkdir(parents=True, exist_ok=True)


def _group_papers_by_theme(analyses: dict[str, dict]) -> dict[str, list[dict]]:
    """按综述主题对论文分组"""
    groups: dict[str, list[dict]] = defaultdict(list)
    for paper in analyses.values():
        theme = paper.get("survey_theme", "其他")
        # 标准化主题名（有时 Claude 输出会有细微差别）
        matched_theme = theme
        for t in SURVEY_THEMES.keys():
            if t in theme or theme in t:
                matched_theme = t
                break
        groups[matched_theme].append(paper)

    # 按重要程度排序每组内的论文
    for theme in groups:
        groups[theme].sort(
            key=lambda x: x.get("importance_score", 3),
            reverse=True
        )
    return groups


def _format_paper_summary_for_prompt(paper: dict) -> str:
    """将单篇论文分析格式化为 prompt 内可用的摘要"""
    return f"""### {paper.get('title_zh', '（标题待翻译）')}
- **ArXiv ID**: {paper['arxiv_id']}
- **一句话概括**: {paper.get('one_sentence_summary', '')}
- **核心贡献**: {'; '.join(paper.get('key_contributions', [])[:3])}
- **技术方法**: {paper.get('technical_approach', '')[:200]}
- **重要程度**: {paper.get('importance_score', 3)}/5"""


def _build_survey_prompt(
    theme: str,
    papers_in_theme: list[dict],
    all_analyses: dict[str, dict],
    chapter_index: int,
    total_chapters: int,
) -> str:
    """为单个主题章节构建生成 prompt"""
    papers_text = "\n\n".join(
        _format_paper_summary_for_prompt(p)
        for p in papers_in_theme[:15]  # 每章最多15篇
    )

    theme_en = SURVEY_THEMES.get(theme, theme)

    return f"""你正在撰写《{SURVEY_TITLE}》的第 {chapter_index}/{total_chapters} 章。

## 本章主题：{theme}（{theme_en}）

本章包含以下 {len(papers_in_theme)} 篇代表论文的分析：

{papers_text}

---

请为本章撰写完整的综述内容，要求：

1. **章节标题**：使用 `## {chapter_index}. {theme}` 格式
2. **概述段落**（约200字）：介绍本主题的研究背景、发展脉络、核心问题
3. **代表工作分析**：重点介绍重要程度 ≥ 4 的论文，包括：
   - 工作背景与动机
   - 核心技术贡献（用 `**粗体**` 标注关键创新）
   - 与前序工作的对比
4. **技术进化脉络**：从早期方法到最新进展的演进路线
5. **本章小结**（约100字）：总结主题现状，指出仍存在的挑战

写作要求：
- 学术写作风格，逻辑清晰
- 中文写作，专业术语保留英文
- 多引用论文（用 `[@arxiv_id]` 格式标注引用）
- 不要重复输出论文原始摘要，要有自己的分析和综合
- 总字数 800-1500 字"""


def generate_introduction(
    all_analyses: dict[str, dict],
    groups: dict[str, list[dict]],
    client: anthropic.Anthropic,
) -> str:
    """生成综述引言部分"""
    stats_text = "\n".join(
        f"- {theme}：{len(papers)} 篇"
        for theme, papers in sorted(groups.items(), key=lambda x: -len(x[1]))
    )

    prompt = f"""请为以下综述撰写引言章节：

# 综述：{SURVEY_TITLE}
# {SURVEY_SUBTITLE}

## 收录论文统计
- 总论文数：{len(all_analyses)} 篇
- 时间范围：2022-2024
- 分类分布：
{stats_text}

## 撰写要求
请撰写完整的引言（约 600-800 字），包含：

1. `## 1. 引言` 标题
2. **研究背景**：为什么 VLA 和具身智能重要？大模型时代的机器人学习面临哪些机遇？
3. **问题定义**：什么是 Vision-Language-Action 模型？与传统机器人学习方法有什么区别？
4. **综述范围**：本文覆盖哪些方向，采用什么分类框架
5. **综述贡献**：与现有综述相比，本文的重点是什么
6. **章节组织**：一段简短介绍各章节内容

写作风格：专业、简洁，适合作为综述论文的引言"""

    print("\n✍  生成引言...", end="", flush=True)
    result = ""
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            result += chunk
            print(".", end="", flush=True)
    print(" ✓")
    return result


def generate_chapter(
    theme: str,
    papers_in_theme: list[dict],
    all_analyses: dict[str, dict],
    chapter_index: int,
    total_chapters: int,
    client: anthropic.Anthropic,
) -> str:
    """生成单个主题章节"""
    if not papers_in_theme:
        return f"\n## {chapter_index}. {theme}\n\n（本主题暂无论文收录）\n"

    prompt = _build_survey_prompt(
        theme, papers_in_theme, all_analyses, chapter_index, total_chapters
    )

    print(f"\n✍  生成第 {chapter_index} 章「{theme}」（{len(papers_in_theme)} 篇）...", end="", flush=True)
    result = ""
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            result += chunk
            print(".", end="", flush=True)
    print(" ✓")
    return result


def generate_future_directions(
    all_analyses: dict[str, dict],
    client: anthropic.Anthropic,
    chapter_index: int,
) -> str:
    """生成未来方向章节"""
    # 汇总所有论文提到的局限性
    limitations = [
        p.get("limitations", "")
        for p in all_analyses.values()
        if p.get("limitations")
    ][:20]

    limitations_text = "\n".join(f"- {l}" for l in limitations)

    prompt = f"""基于对 {len(all_analyses)} 篇 VLA / 具身智能论文的分析，各论文指出的局限性如下：

{limitations_text}

请撰写综述的未来方向与开放问题章节（约 800 字），格式如下：

## {chapter_index}. 未来方向与开放问题

请围绕以下几个维度展开分析：

1. **数据效率与泛化**：如何减少对大规模演示数据的依赖？
2. **多任务统一表示**：如何构建跨机器人、跨任务的通用策略？
3. **安全性与可靠性**：如何确保 VLA 在真实场景的部署安全？
4. **长时序规划**：如何处理复杂的多步骤操作任务？
5. **物理世界理解**：如何增强模型对物理交互的理解？
6. **实时性**：如何在保持性能的同时降低推理延迟？

每个维度 100-150 字，指出具体的技术挑战和可能的解决思路。"""

    print(f"\n✍  生成未来方向章节...", end="", flush=True)
    result = ""
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=2500,
        thinking={"type": "adaptive"},
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            result += chunk
            print(".", end="", flush=True)
    print(" ✓")
    return result


def generate_comparison_table(
    all_analyses: dict[str, dict],
    client: anthropic.Anthropic,
    chapter_index: int,
) -> str:
    """生成重要论文对比表"""
    # 选取重要程度 ≥ 4 的论文
    important = [
        p for p in all_analyses.values()
        if p.get("importance_score", 3) >= 4
    ]
    important.sort(key=lambda x: x.get("published", ""), reverse=True)

    papers_info = "\n".join(
        f"- {p['arxiv_id']} | {p.get('title_zh','')[:30]} | {p.get('one_sentence_summary','')[:50]} | {p.get('survey_theme','')}"
        for p in important[:25]
    )

    prompt = f"""基于以下重要论文列表，请生成一个 Markdown 对比表格：

{papers_info}

请创建章节：

## {chapter_index}. 重要工作对比

先写 2-3 句介绍，然后生成一个 Markdown 表格，列包含：
| 论文 | 发表年 | 核心方法 | 主要贡献 | 主题分类 |

只包含以上论文，每行对应一篇，内容简洁（每格不超过30字）。"""

    print(f"\n✍  生成对比表格...", end="", flush=True)
    result = ""
    with client.messages.stream(
        model=CLAUDE_MODEL,
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for chunk in stream.text_stream:
            result += chunk
            print(".", end="", flush=True)
    print(" ✓")
    return result


def generate_references(all_analyses: dict[str, dict]) -> str:
    """生成参考文献列表"""
    refs = []
    sorted_papers = sorted(
        all_analyses.values(),
        key=lambda x: x.get("published", ""),
        reverse=True,
    )
    for i, p in enumerate(sorted_papers, 1):
        arxiv_id = p.get("arxiv_id", "")
        title_zh = p.get("title_zh", "")
        refs.append(
            f"[{i}] {arxiv_id} — {title_zh} — "
            f"https://arxiv.org/abs/{arxiv_id}"
        )
    return "\n## 参考文献\n\n" + "\n\n".join(refs)


def generate_survey(
    all_analyses: dict[str, dict],
    output_filename: Optional[str] = None,
) -> Path:
    """
    完整综述生成流程

    参数:
        all_analyses:    所有论文的分析结果字典（arxiv_id → analysis）
        output_filename: 输出文件名（默认按时间戳命名）

    返回:
        生成的 Markdown 文件路径
    """
    from typing import Optional  # 避免循环导入

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    if not output_filename:
        timestamp = time.strftime("%Y%m%d_%H%M")
        output_filename = f"vla_survey_{timestamp}.md"

    output_path = SURVEYS_DIR / output_filename

    print(f"\n{'='*60}")
    print(f"📝 开始生成综述：{SURVEY_TITLE}")
    print(f"   论文总数：{len(all_analyses)} 篇")
    print(f"{'='*60}")

    # 按主题分组
    groups = _group_papers_by_theme(all_analyses)
    themes = list(SURVEY_THEMES.keys())  # 按预定义顺序排列主题
    # 添加不在预定义主题中的额外主题
    for t in groups:
        if t not in themes:
            themes.append(t)

    total_chapters = len(themes) + 3  # 引言 + 各主题 + 对比表 + 未来方向

    # 构建综述内容
    sections = []

    # ── 0. 封面 & 目录 ─────────────────────────────────────────
    toc_items = [
        f"  - [1. 引言](#1-引言)",
    ]
    for i, theme in enumerate(themes, 2):
        toc_items.append(f"  - [{i}. {theme}](#{i}-{theme})")
    toc_items.append(f"  - [{len(themes)+2}. 重要工作对比](#{len(themes)+2}-重要工作对比)")
    toc_items.append(f"  - [{len(themes)+3}. 未来方向与开放问题](#{len(themes)+3}-未来方向与开放问题)")

    cover = f"""# {SURVEY_TITLE}

## {SURVEY_SUBTITLE}

> **自动生成综述** · 由 Claude Opus 4.6 撰写 · 覆盖 {len(all_analyses)} 篇论文 · 生成时间：{time.strftime('%Y-%m-%d')}

---

## 目录

{chr(10).join(toc_items)}

- [参考文献](#参考文献)

---
"""
    sections.append(cover)
    print("✓ 封面与目录已生成")

    # ── 1. 引言 ────────────────────────────────────────────────
    intro = generate_introduction(all_analyses, groups, client)
    sections.append(intro)

    # ── 2. 各主题章节 ─────────────────────────────────────────
    for i, theme in enumerate(themes, 2):
        papers_in_theme = groups.get(theme, [])
        chapter = generate_chapter(
            theme=theme,
            papers_in_theme=papers_in_theme,
            all_analyses=all_analyses,
            chapter_index=i,
            total_chapters=total_chapters,
            client=client,
        )
        sections.append("\n" + chapter)

    # ── 最后章节序号 ───────────────────────────────────────────
    last_chapter = len(themes) + 2

    # ── 对比表 ─────────────────────────────────────────────────
    comparison = generate_comparison_table(all_analyses, client, last_chapter)
    sections.append("\n" + comparison)

    # ── 未来方向 ───────────────────────────────────────────────
    future = generate_future_directions(all_analyses, client, last_chapter + 1)
    sections.append("\n" + future)

    # ── 参考文献 ───────────────────────────────────────────────
    refs = generate_references(all_analyses)
    sections.append("\n" + refs)

    # ── 保存到文件 ─────────────────────────────────────────────
    full_survey = "\n\n".join(sections)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(full_survey)

    word_count = len(full_survey.replace(" ", ""))
    print(f"\n{'='*60}")
    print(f"✅ 综述生成完成！")
    print(f"   文件：{output_path}")
    print(f"   字数：约 {word_count:,} 字")
    print(f"{'='*60}")

    return output_path
