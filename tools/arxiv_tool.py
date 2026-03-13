"""
ArXiv 工具
===========

封装所有与 ArXiv 相关的操作：
- 关键词/作者/类别搜索论文
- 获取论文详情（标题、摘要、作者、PDF链接）
- 批量获取多篇论文

使用 `arxiv` 官方 Python 库（底层调用 ArXiv API）。

ArXiv 论文 ID 格式：YYMM.NNNNN，例如 "2312.04567"
ArXiv 类别示例：
  cs.AI   — 人工智能
  cs.LG   — 机器学习
  cs.CL   — 计算语言学/NLP
  cs.CV   — 计算机视觉
  stat.ML — 统计机器学习
"""

import arxiv
import time
from typing import Optional
from config import MAX_SEARCH_RESULTS


def search_papers(
    query: str,
    max_results: int = MAX_SEARCH_RESULTS,
    category: Optional[str] = None,
    sort_by: str = "relevance",
) -> list[dict]:
    """
    在 ArXiv 上搜索论文

    参数:
        query:       搜索关键词，支持自然语言或布尔表达式
                     例如："transformer attention mechanism"
                          "ti:BERT AND au:devlin"（ti=标题, au=作者）
        max_results: 返回最多多少篇，默认10篇
        category:    限定 ArXiv 类别，如 "cs.LG"，None 表示全类别搜索
        sort_by:     排序方式："relevance"(相关性) | "lastUpdatedDate" | "submittedDate"

    返回:
        论文列表，每篇包含：id, title, authors, abstract(前300字), published, url
    """
    # 如果指定类别，将其加入查询词
    if category:
        query = f"cat:{category} AND ({query})"

    # 排序枚举映射
    sort_map = {
        "relevance":        arxiv.SortCriterion.Relevance,
        "lastUpdatedDate":  arxiv.SortCriterion.LastUpdatedDate,
        "submittedDate":    arxiv.SortCriterion.SubmittedDate,
    }
    criterion = sort_map.get(sort_by, arxiv.SortCriterion.Relevance)

    client = arxiv.Client(
        page_size=min(max_results, 50),  # ArXiv 单次最多50条
        delay_seconds=1,                 # 礼貌性延迟，避免被限流
        num_retries=3,
    )

    search = arxiv.Search(
        query=query,
        max_results=max_results,
        sort_by=criterion,
    )

    results = []
    for paper in client.results(search):
        results.append({
            "id":        paper.get_short_id(),          # 例如 "2312.04567"
            "title":     paper.title,
            "authors":   [a.name for a in paper.authors[:5]],  # 只取前5位作者
            "abstract":  paper.summary[:400] + "..." if len(paper.summary) > 400 else paper.summary,
            "published": paper.published.strftime("%Y-%m-%d") if paper.published else "unknown",
            "updated":   paper.updated.strftime("%Y-%m-%d")   if paper.updated   else "unknown",
            "url":       paper.entry_id,
            "pdf_url":   paper.pdf_url,
            "categories": paper.categories,
        })

    return results


def get_paper_detail(arxiv_id: str) -> dict:
    """
    获取单篇论文的完整详情

    参数:
        arxiv_id: ArXiv 论文 ID，例如 "1706.03762" 或 "2312.04567v2"

    返回:
        包含完整摘要、完整作者列表等信息的字典
        如果找不到论文，返回包含 error 字段的字典
    """
    # 去掉版本号后缀（如 v2），使用最新版
    clean_id = arxiv_id.split("v")[0].strip()

    try:
        client = arxiv.Client(delay_seconds=1, num_retries=3)
        search = arxiv.Search(id_list=[clean_id])
        results = list(client.results(search))

        if not results:
            return {"error": f"找不到论文 {arxiv_id}"}

        paper = results[0]
        return {
            "id":          paper.get_short_id(),
            "title":       paper.title,
            "authors":     [a.name for a in paper.authors],
            "abstract":    paper.summary,                    # 完整摘要
            "published":   paper.published.strftime("%Y-%m-%d") if paper.published else "unknown",
            "updated":     paper.updated.strftime("%Y-%m-%d")   if paper.updated   else "unknown",
            "url":         paper.entry_id,
            "pdf_url":     paper.pdf_url,
            "categories":  paper.categories,
            "primary_category": paper.primary_category,
            "comment":     paper.comment or "",              # 作者备注（如"NeurIPS 2023"）
            "journal_ref": paper.journal_ref or "",          # 期刊引用信息
            "doi":         paper.doi or "",
        }

    except Exception as e:
        return {"error": f"获取论文 {arxiv_id} 时出错：{str(e)}"}


def get_papers_batch(arxiv_ids: list[str]) -> list[dict]:
    """
    批量获取多篇论文的详情（带礼貌延迟）

    参数:
        arxiv_ids: 论文 ID 列表

    返回:
        论文详情列表（顺序对应输入 ID）
    """
    results = []
    for i, arxiv_id in enumerate(arxiv_ids):
        result = get_paper_detail(arxiv_id)
        results.append(result)
        # 每获取一篇后稍作等待，避免请求过于频繁
        if i < len(arxiv_ids) - 1:
            time.sleep(0.5)
    return results
