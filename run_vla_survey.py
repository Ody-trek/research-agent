"""
VLA 具身智能论文综述 · 主入口
==============================

完整流程（一键运行）：
  Step 1  收集 ArXiv 论文（搜索 + 经典 seed 论文）
  Step 2  Batches API 批量分析（5折优惠，并行处理）
  Step 3  Claude Opus 4.6 生成综述 Markdown
  Step 4  推送到 GitHub

用法示例：
  # 完整运行
  python run_vla_survey.py

  # 仅收集论文（跳过后续步骤）
  python run_vla_survey.py --step collect

  # 从已有分析生成综述（跳过收集和分析）
  python run_vla_survey.py --step survey

  # 仅发布（使用已有综述）
  python run_vla_survey.py --step publish

  # 不推送 GitHub，只本地生成
  python run_vla_survey.py --no-publish

环境变量：
  ANTHROPIC_API_KEY   （必须）
  GITHUB_REPO_URL     （可选，推送目标仓库）
  GITHUB_TOKEN        （可选，HTTPS 认证）
"""

import sys
import os
import json
import argparse
import time
from pathlib import Path

# ── 添加项目根目录到 Python 路径 ────────────────────────────────
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def check_environment():
    """检查必要环境变量"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("❌ 错误：请设置 ANTHROPIC_API_KEY 环境变量")
        print("   export ANTHROPIC_API_KEY='sk-ant-...'")
        sys.exit(1)
    print(f"✓ ANTHROPIC_API_KEY 已配置（{key[:12]}...）")

    github_url = os.environ.get("GITHUB_REPO_URL", "")
    if github_url:
        print(f"✓ GITHUB_REPO_URL: {github_url}")
    else:
        print("⚠ GITHUB_REPO_URL 未设置（将只保存到本地）")


def step_collect(args) -> list[dict]:
    """Step 1：收集论文"""
    from vla_pipeline.paper_collector import collect_papers

    print(f"\n{'='*60}")
    print("Step 1 / 4  📚 收集 VLA 论文")
    print(f"{'='*60}")

    papers = collect_papers(
        use_cache=not args.no_cache,
        min_year=args.min_year,
        max_papers=args.max_papers,
    )

    print(f"\n✅ 共收集到 {len(papers)} 篇论文")
    # 打印年份分布
    from collections import Counter
    year_dist = Counter(p["published"][:4] for p in papers)
    for year in sorted(year_dist, reverse=True):
        print(f"   {year}: {year_dist[year]} 篇")

    return papers


def step_analyze(papers: list[dict], args) -> dict[str, dict]:
    """Step 2：批量分析"""
    from vla_pipeline.batch_analyzer import run_batch_analysis

    print(f"\n{'='*60}")
    print("Step 2 / 4  🔬 批量分析论文（Batches API 5折）")
    print(f"{'='*60}")

    analyses = run_batch_analysis(
        papers=papers,
        skip_existing=not args.no_cache,
        poll_interval=args.poll_interval,
    )

    # 打印主题分布
    from collections import Counter
    themes = Counter(a.get("survey_theme", "未分类") for a in analyses.values())
    print("\n📊 主题分布：")
    for theme, count in themes.most_common():
        print(f"   {theme}: {count} 篇")

    return analyses


def step_survey(analyses: dict[str, dict], args) -> Path:
    """Step 3：生成综述"""
    from vla_pipeline.survey_generator import generate_survey

    print(f"\n{'='*60}")
    print("Step 3 / 4  📝 生成综述 Markdown")
    print(f"{'='*60}")

    survey_path = generate_survey(
        all_analyses=analyses,
        output_filename=args.output_name,
    )
    return survey_path


def step_publish(survey_path: Path, args) -> None:
    """Step 4：推送到 GitHub"""
    from vla_pipeline.github_publisher import publish

    print(f"\n{'='*60}")
    print("Step 4 / 4  🚀 发布到 GitHub")
    print(f"{'='*60}")

    success = publish(
        survey_path=survey_path,
        repo_url=args.repo_url,
    )
    if success:
        print("\n🎉 全部完成！")
        github_url = os.environ.get("GITHUB_REPO_URL", "")
        if github_url and "github.com" in github_url:
            # 提取可读 URL
            clean_url = github_url.replace(".git", "").split("@github.com/")[-1]
            print(f"   仓库：https://github.com/{clean_url}")
    else:
        print("\n⚠ 发布失败，请检查 GITHUB 配置")


def load_cached_analyses() -> dict[str, dict]:
    """从本地缓存加载已有分析"""
    summary_file = ROOT / "outputs" / "batch_jobs" / "all_analyses.json"
    if summary_file.exists():
        with open(summary_file, encoding="utf-8") as f:
            return json.load(f)

    # 逐文件加载
    analyses = {}
    analyses_dir = ROOT / "outputs" / "paper_analyses"
    if analyses_dir.exists():
        for f in analyses_dir.glob("*.json"):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                arxiv_id = data.get("arxiv_id", f.stem.replace("_", "."))
                analyses[arxiv_id] = data
            except Exception:
                pass
    return analyses


def main():
    parser = argparse.ArgumentParser(
        description="VLA 具身智能论文综述自动生成系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--step",
        choices=["all", "collect", "analyze", "survey", "publish"],
        default="all",
        help="执行哪个步骤（默认 all：执行全部）",
    )
    parser.add_argument(
        "--no-publish",
        action="store_true",
        help="跳过 GitHub 发布步骤",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="忽略本地缓存，重新执行所有步骤",
    )
    parser.add_argument(
        "--min-year",
        type=int,
        default=2022,
        help="只收集该年份及之后的论文（默认 2022）",
    )
    parser.add_argument(
        "--max-papers",
        type=int,
        default=100,
        help="最多收集多少篇论文（默认 100）",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=60,
        help="Batch API 轮询间隔（秒，默认 60）",
    )
    parser.add_argument(
        "--output-name",
        type=str,
        default=None,
        help="综述文件名（默认按时间戳命名）",
    )
    parser.add_argument(
        "--repo-url",
        type=str,
        default=None,
        help="GitHub 仓库 URL（覆盖环境变量 GITHUB_REPO_URL）",
    )
    args = parser.parse_args()

    # 环境检查
    check_environment()

    start_time = time.time()
    survey_path = None

    try:
        if args.step in ("all", "collect", "analyze"):
            # ── Step 1：收集 ───────────────────────────────────
            papers = step_collect(args)

            if args.step == "collect":
                print(f"\n已保存到 outputs/batch_jobs/collected_papers.json")
                return

        if args.step in ("all", "analyze"):
            # ── Step 2：分析 ───────────────────────────────────
            if args.step == "analyze":
                # 只做分析：从缓存加载论文
                cache_file = ROOT / "outputs" / "batch_jobs" / "collected_papers.json"
                if not cache_file.exists():
                    print("❌ 未找到缓存论文，请先运行 --step collect")
                    sys.exit(1)
                with open(cache_file, encoding="utf-8") as f:
                    papers = json.load(f)

            analyses = step_analyze(papers, args)

            if args.step == "analyze":
                print(f"\n分析完成，共 {len(analyses)} 篇")
                return

        if args.step in ("all", "survey"):
            # ── Step 3：综述 ───────────────────────────────────
            if args.step == "survey":
                analyses = load_cached_analyses()
                if not analyses:
                    print("❌ 未找到分析结果，请先运行 --step analyze")
                    sys.exit(1)
                print(f"📂 加载已有分析：{len(analyses)} 篇")

            survey_path = step_survey(analyses, args)

            if args.step == "survey":
                return

        if args.step == "publish":
            # 仅发布，找最新综述
            surveys_dir = ROOT / "outputs" / "surveys"
            if surveys_dir.exists():
                survey_files = sorted(surveys_dir.glob("*.md"), reverse=True)
                survey_path = survey_files[0] if survey_files else None

        # ── Step 4：发布 ───────────────────────────────────────
        if not args.no_publish:
            step_publish(survey_path, args)
        else:
            elapsed = (time.time() - start_time) / 60
            print(f"\n✅ 完成！（跳过 GitHub 发布）耗时：{elapsed:.1f} 分钟")
            if survey_path:
                print(f"   综述文件：{survey_path}")

    except KeyboardInterrupt:
        elapsed = (time.time() - start_time) / 60
        print(f"\n\n⚠ 已中断（已运行 {elapsed:.1f} 分钟）")
        print("  提示：重新运行时会自动续传已完成部分（使用缓存）")
        sys.exit(0)

    elapsed = (time.time() - start_time) / 60
    print(f"\n⏱  总耗时：{elapsed:.1f} 分钟")


if __name__ == "__main__":
    main()
