"""
本地论文库
==========

将感兴趣的论文保存到本地 JSON 文件，方便：
- 离线查看已保存的论文
- 跨对话记住已研究的论文
- 快速搜索本地库

存储结构：
  paper_library/
  └── papers.json    ← 所有论文的元数据（列表）
"""

import json
from datetime import datetime
from pathlib import Path
from config import STORAGE_DIR

LIBRARY_FILE = STORAGE_DIR / "papers.json"


def _load_library() -> list[dict]:
    """加载本地论文库"""
    if not LIBRARY_FILE.exists():
        return []
    try:
        return json.loads(LIBRARY_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return []


def _save_library(papers: list[dict]):
    """保存论文库到磁盘"""
    LIBRARY_FILE.write_text(
        json.dumps(papers, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def save_paper(paper_data: dict) -> dict:
    """
    保存一篇论文到本地库

    参数:
        paper_data: 包含 id、title、abstract 等字段的字典

    返回:
        {"status": "saved"|"already_exists", "id": arxiv_id}
    """
    papers = _load_library()
    arxiv_id = paper_data.get("id", "")

    # 检查是否已存在
    for p in papers:
        if p.get("id") == arxiv_id:
            return {"status": "already_exists", "id": arxiv_id,
                    "message": f"论文 {arxiv_id} 已在本地库中"}

    # 添加保存时间戳
    paper_data["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    papers.append(paper_data)
    _save_library(papers)

    return {"status": "saved", "id": arxiv_id,
            "message": f"已保存：{paper_data.get('title', arxiv_id)}"}


def list_saved_papers(keyword: str = "") -> dict:
    """
    列出本地库中的所有论文（可按关键词过滤）

    参数:
        keyword: 可选过滤词（匹配标题或摘要，忽略大小写）

    返回:
        {"count": N, "papers": [...]}
    """
    papers = _load_library()

    if keyword:
        kw = keyword.lower()
        papers = [
            p for p in papers
            if kw in p.get("title", "").lower()
            or kw in p.get("abstract", "").lower()
        ]

    # 只返回摘要的前200字，避免信息过多
    display = []
    for p in papers:
        display.append({
            "id":        p.get("id"),
            "title":     p.get("title"),
            "authors":   p.get("authors", [])[:3],
            "published": p.get("published"),
            "abstract":  (p.get("abstract", "")[:200] + "...") if p.get("abstract") else "",
            "saved_at":  p.get("saved_at"),
        })

    return {"count": len(display), "papers": display}


def get_saved_paper(arxiv_id: str) -> dict:
    """
    从本地库获取一篇论文的完整信息

    参数:
        arxiv_id: 论文 ID

    返回:
        论文完整信息字典，若不存在返回 {"error": ...}
    """
    papers = _load_library()
    for p in papers:
        if p.get("id") == arxiv_id:
            return p
    return {"error": f"本地库中找不到 {arxiv_id}，请先保存该论文"}


def delete_paper(arxiv_id: str) -> dict:
    """从本地库删除一篇论文"""
    papers = _load_library()
    new_papers = [p for p in papers if p.get("id") != arxiv_id]

    if len(new_papers) == len(papers):
        return {"status": "not_found", "message": f"本地库中没有 {arxiv_id}"}

    _save_library(new_papers)
    return {"status": "deleted", "message": f"已删除 {arxiv_id}"}


def get_library_stats() -> dict:
    """获取本地库统计信息"""
    papers = _load_library()
    if not papers:
        return {"total": 0, "message": "本地库为空"}

    # 按年份统计
    year_counts = {}
    for p in papers:
        year = (p.get("published") or "unknown")[:4]
        year_counts[year] = year_counts.get(year, 0) + 1

    # 按类别统计
    cat_counts = {}
    for p in papers:
        for cat in p.get("categories", []):
            cat_counts[cat] = cat_counts.get(cat, 0) + 1

    top_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "total":       len(papers),
        "by_year":     dict(sorted(year_counts.items())),
        "top_categories": dict(top_cats),
        "oldest_save": min(p.get("saved_at", "9999") for p in papers),
        "latest_save": max(p.get("saved_at", "0000") for p in papers),
    }
