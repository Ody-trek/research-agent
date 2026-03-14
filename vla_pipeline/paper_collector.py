"""
论文收集器
===========

从 ArXiv 批量收集 VLA / 具身智能论文，去重后返回统一格式的列表。
支持：
  - 关键词搜索（多条查询并发）
  - 直接按 ID 获取经典论文
  - 按年份过滤（可选）
  - 本地缓存，避免重复请求
"""

import json
import time
import arxiv
from pathlib import Path
from typing import Optional

from vla_pipeline.vla_queries import SEARCH_QUERIES, SEED_PAPER_IDS

CACHE_FILE = Path(__file__).parent.parent / "outputs" / "batch_jobs" / "collected_papers.json"


def _fetch_by_query(query: str, category: Optional[str], max_results: int) -> list[dict]:
    """用关键词在 ArXiv 搜索论文"""
    full_query = f"cat:{category} AND ({query})" if category else query

    client = arxiv.Client(page_size=min(max_results, 50), delay_seconds=1.5, num_retries=3)
    search = arxiv.Search(
        query=full_query,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate,  # 按时间排序，优先新论文
    )

    papers = []
    for p in client.results(search):
        papers.append(_arxiv_to_dict(p))
    return papers


def _fetch_by_ids(arxiv_ids: list[str]) -> list[dict]:
    """按 ID 列表获取指定论文"""
    clean_ids = [i.split("v")[0].strip() for i in arxiv_ids]
    client = arxiv.Client(delay_seconds=1.0, num_retries=3)
    search = arxiv.Search(id_list=clean_ids)

    papers = []
    for p in client.results(search):
        papers.append(_arxiv_to_dict(p))
    return papers


def _arxiv_to_dict(p: arxiv.Result) -> dict:
    """将 arxiv.Result 对象转换为统一字典格式"""
    return {
        "id":          p.get_short_id(),
        "title":       p.title.strip(),
        "authors":     [a.name for a in p.authors[:8]],
        "abstract":    p.summary.strip(),
        "published":   p.published.strftime("%Y-%m-%d") if p.published else "unknown",
        "updated":     p.updated.strftime("%Y-%m-%d")   if p.updated   else "unknown",
        "url":         p.entry_id,
        "pdf_url":     p.pdf_url,
        "categories":  p.categories,
        "comment":     p.comment  or "",
        "journal_ref": p.journal_ref or "",
    }


def collect_papers(
    use_cache:    bool = True,
    min_year:     int  = 2022,
    max_papers:   int  = 120,
) -> list[dict]:
    """
    完整收集流程：搜索 + 按ID获取 + 去重 + 过滤

    参数:
        use_cache:  是否使用本地缓存（避免重复请求 ArXiv）
        min_year:   只保留该年份及之后的论文
        max_papers: 最多保留多少篇（按发布时间倒序裁剪）

    返回:
        去重后的论文列表
    """
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if use_cache and CACHE_FILE.exists():
        print(f"📚 加载缓存论文列表：{CACHE_FILE}")
        with open(CACHE_FILE, encoding="utf-8") as f:
            papers = json.load(f)
        print(f"   共 {len(papers)} 篇")
        return papers

    all_papers: dict[str, dict] = {}  # id → paper，用于去重

    # ── 1. 先获取经典 seed 论文，保证不漏 ────────────────────
    print(f"\n📌 获取 {len(SEED_PAPER_IDS)} 篇经典 VLA 论文...")
    try:
        seed_papers = _fetch_by_ids(SEED_PAPER_IDS)
        for p in seed_papers:
            all_papers[p["id"]] = p
        print(f"   ✓ 获取到 {len(seed_papers)} 篇")
    except Exception as e:
        print(f"   ⚠ 获取 seed 论文失败：{e}")

    time.sleep(2)

    # ── 2. 按搜索词搜索 ──────────────────────────────────────
    for i, (query, category, n) in enumerate(SEARCH_QUERIES):
        print(f"\n🔍 [{i+1}/{len(SEARCH_QUERIES)}] 搜索：{query[:50]}...")
        try:
            papers = _fetch_by_query(query, category, n)
            before = len(all_papers)
            for p in papers:
                if p["id"] not in all_papers:
                    all_papers[p["id"]] = p
            added = len(all_papers) - before
            print(f"   ✓ 搜到 {len(papers)} 篇，新增 {added} 篇（去重后共 {len(all_papers)} 篇）")
        except Exception as e:
            print(f"   ⚠ 搜索失败：{e}")

        time.sleep(1.5)

    # ── 3. 过滤年份 ─────────────────────────────────────────
    filtered = [
        p for p in all_papers.values()
        if p["published"] != "unknown" and int(p["published"][:4]) >= min_year
    ]
    print(f"\n📅 过滤 {min_year} 年以后：{len(all_papers)} → {len(filtered)} 篇")

    # ── 4. 按发布时间倒序，限制数量 ─────────────────────────
    filtered.sort(key=lambda x: x["published"], reverse=True)
    result = filtered[:max_papers]
    print(f"📊 最终保留：{len(result)} 篇（最多 {max_papers} 篇）")

    # ── 5. 保存缓存 ─────────────────────────────────────────
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"💾 已缓存到：{CACHE_FILE}")

    return result
