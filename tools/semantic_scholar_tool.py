"""
Semantic Scholar 工具
======================

Semantic Scholar 是 AI2（Allen Institute for AI）提供的学术搜索引擎，
比 ArXiv 多了引用关系数据，可以用来：
- 获取一篇论文被哪些论文引用（被引列表）
- 获取一篇论文引用了哪些论文（参考文献列表）
- 构建引用关系图谱

API 免费使用，无需注册（有频率限制：100次/5分钟）
可申请 API Key 提升至 1次/秒：https://www.semanticscholar.org/product/api

ArXiv ID → Semantic Scholar 的对应格式：
  ArXiv: "2312.04567"
  S2:    "arXiv:2312.04567"
"""

import time
import requests
from typing import Optional
from config import S2_API_KEY, S2_BASE_URL


def _make_headers() -> dict:
    """构造请求头（如果有 API Key 则加入）"""
    headers = {"Accept": "application/json"}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY
    return headers


def _s2_request(url: str, params: dict = None) -> Optional[dict]:
    """
    发送 Semantic Scholar API 请求（含重试和限流处理）

    参数:
        url:    完整 API URL
        params: 查询参数字典

    返回:
        JSON 响应字典，失败时返回 None
    """
    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, headers=_make_headers(), timeout=15)

            if resp.status_code == 200:
                return resp.json()
            elif resp.status_code == 429:
                # 被限流：等待后重试
                wait = int(resp.headers.get("Retry-After", "10"))
                print(f"  [S2] 请求频率超限，等待 {wait}s 后重试...")
                time.sleep(wait)
            elif resp.status_code == 404:
                return None  # 论文不在 S2 数据库中（正常情况）
            else:
                print(f"  [S2] HTTP {resp.status_code}: {resp.text[:100]}")
                return None

        except requests.exceptions.RequestException as e:
            print(f"  [S2] 网络错误（第{attempt+1}次）: {e}")
            time.sleep(2 ** attempt)

    return None


def get_paper_citations(arxiv_id: str, limit: int = 20) -> dict:
    """
    获取一篇论文的被引信息（谁引用了这篇论文）

    参数:
        arxiv_id: ArXiv ID，如 "1706.03762"
        limit:    最多返回多少条引用，默认20

    返回:
        包含 total_count 和 citations 列表的字典
        每条引用含：title, authors, year, arxiv_id（如有）
    """
    s2_id = f"arXiv:{arxiv_id}"
    url = f"{S2_BASE_URL}/paper/{s2_id}/citations"
    params = {
        "fields": "title,authors,year,externalIds",
        "limit":  min(limit, 100),
    }

    data = _s2_request(url, params)
    if not data:
        return {"total_count": 0, "citations": [],
                "note": "Semantic Scholar 中未找到该论文的引用数据"}

    citations = []
    for item in data.get("data", []):
        citing = item.get("citingPaper", {})
        ext_ids = citing.get("externalIds", {})
        citations.append({
            "title":    citing.get("title", ""),
            "authors":  [a["name"] for a in citing.get("authors", [])[:3]],
            "year":     citing.get("year"),
            "arxiv_id": ext_ids.get("ArXiv", ""),
        })

    return {
        "total_count": data.get("total", len(citations)),
        "returned":    len(citations),
        "citations":   citations,
    }


def get_paper_references(arxiv_id: str, limit: int = 30) -> dict:
    """
    获取一篇论文的参考文献（这篇论文引用了哪些论文）

    参数:
        arxiv_id: ArXiv ID，如 "1706.03762"
        limit:    最多返回多少条，默认30

    返回:
        包含 total_count 和 references 列表的字典
    """
    s2_id = f"arXiv:{arxiv_id}"
    url = f"{S2_BASE_URL}/paper/{s2_id}/references"
    params = {
        "fields": "title,authors,year,externalIds",
        "limit":  min(limit, 100),
    }

    data = _s2_request(url, params)
    if not data:
        return {"total_count": 0, "references": [],
                "note": "Semantic Scholar 中未找到该论文的参考文献数据"}

    references = []
    for item in data.get("data", []):
        cited = item.get("citedPaper", {})
        ext_ids = cited.get("externalIds", {})
        references.append({
            "title":    cited.get("title", ""),
            "authors":  [a["name"] for a in cited.get("authors", [])[:3]],
            "year":     cited.get("year"),
            "arxiv_id": ext_ids.get("ArXiv", ""),
        })

    return {
        "total_count": data.get("total", len(references)),
        "returned":    len(references),
        "references":  references,
    }


def get_paper_s2_details(arxiv_id: str) -> dict:
    """
    获取 Semantic Scholar 上的论文补充信息
    （ArXiv 没有的字段：引用次数、影响力分数、研究领域）

    参数:
        arxiv_id: ArXiv ID

    返回:
        包含引用次数、高影响力引用次数等信息的字典
    """
    s2_id = f"arXiv:{arxiv_id}"
    url = f"{S2_BASE_URL}/paper/{s2_id}"
    params = {
        "fields": "citationCount,influentialCitationCount,fieldsOfStudy,s2FieldsOfStudy,publicationVenue"
    }

    data = _s2_request(url, params)
    if not data:
        return {"note": "Semantic Scholar 中未找到该论文"}

    return {
        "citation_count":             data.get("citationCount", 0),
        "influential_citation_count": data.get("influentialCitationCount", 0),
        "fields_of_study":            data.get("fieldsOfStudy", []),
        "publication_venue":          data.get("publicationVenue", {}).get("name", ""),
    }
