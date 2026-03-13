"""
工具定义（Tool Schema）
========================

Claude 的 Tool Use 需要为每个工具提供 JSON Schema：
- name: 工具名称（Claude 调用时用这个名字）
- description: 工具功能描述（Claude 根据这个决定何时调用）
- input_schema: 参数的 JSON Schema（Claude 据此构造参数）

注意：description 写得越清晰，Claude 调用工具越准确。
"""

TOOL_DEFINITIONS = [
    # ── ArXiv 搜索 ──────────────────────────────────────────
    {
        "name": "search_arxiv",
        "description": (
            "在 ArXiv 学术预印本平台上搜索论文。"
            "适用于：寻找某个研究方向的相关论文、查找特定作者的论文、"
            "了解某领域最新进展。返回论文列表（ID、标题、摘要前400字、作者、日期）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "搜索关键词或表达式。支持自然语言，也支持高级语法："
                        "ti:标题关键词, au:作者名, abs:摘要关键词。"
                        "例：'vision transformer image classification' 或 "
                        "'ti:diffusion model AND au:ho'"
                    ),
                },
                "max_results": {
                    "type": "integer",
                    "description": "返回论文数量，默认8，最大20",
                    "default": 8,
                },
                "category": {
                    "type": "string",
                    "description": (
                        "ArXiv 类别过滤（可选）。常用：cs.AI, cs.LG, cs.CL, cs.CV, "
                        "cs.RO, stat.ML, eess.IV。不填则搜索所有类别。"
                    ),
                },
                "sort_by": {
                    "type": "string",
                    "enum": ["relevance", "lastUpdatedDate", "submittedDate"],
                    "description": "排序方式：relevance(相关性), lastUpdatedDate(最近更新), submittedDate(提交日期)",
                    "default": "relevance",
                },
            },
            "required": ["query"],
        },
    },

    # ── 论文详情（ArXiv）──────────────────────────────────
    {
        "name": "get_paper_detail",
        "description": (
            "获取单篇论文的完整信息（完整摘要、全部作者、类别、DOI 等）。"
            "在 search_arxiv 找到感兴趣的论文 ID 后，用此工具获取更多细节。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "ArXiv 论文 ID，如 '1706.03762' 或 '2312.04567'",
                },
            },
            "required": ["arxiv_id"],
        },
    },

    # ── 被引列表（S2）────────────────────────────────────
    {
        "name": "get_paper_citations",
        "description": (
            "查询一篇论文被哪些论文引用（来自 Semantic Scholar）。"
            "用于了解论文的影响力，找到该论文之后的跟进工作。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "ArXiv 论文 ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回引用数量上限，默认15",
                    "default": 15,
                },
            },
            "required": ["arxiv_id"],
        },
    },

    # ── 参考文献（S2）────────────────────────────────────
    {
        "name": "get_paper_references",
        "description": (
            "获取一篇论文的参考文献列表（这篇论文引用了哪些论文）。"
            "用于了解该工作的技术基础和相关先验工作。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "ArXiv 论文 ID",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回参考文献数量，默认20",
                    "default": 20,
                },
            },
            "required": ["arxiv_id"],
        },
    },

    # ── S2 补充详情 ───────────────────────────────────────
    {
        "name": "get_paper_s2_details",
        "description": (
            "从 Semantic Scholar 获取论文的引用次数、高影响力引用数、研究领域。"
            "用于快速评估一篇论文的学术影响力。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "arxiv_id": {
                    "type": "string",
                    "description": "ArXiv 论文 ID",
                },
            },
            "required": ["arxiv_id"],
        },
    },

    # ── 构建引用图谱 ──────────────────────────────────────
    {
        "name": "build_citation_graph",
        "description": (
            "以给定论文为种子，构建引用关系图谱（图的节点是论文，边是引用关系）。"
            "深度=1：只展开直接参考文献；深度=2：再展开一层（论文较多时可能较慢）。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "seed_arxiv_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "种子论文 ID 列表，建议2-5篇",
                },
                "depth": {
                    "type": "integer",
                    "description": "扩展深度，1或2（建议先用1）",
                    "default": 1,
                },
                "max_refs_per_paper": {
                    "type": "integer",
                    "description": "每篇论文最多展开多少条参考文献，默认10",
                    "default": 10,
                },
            },
            "required": ["seed_arxiv_ids"],
        },
    },

    # ── 可视化图谱 ────────────────────────────────────────
    {
        "name": "visualize_citation_graph",
        "description": (
            "将 build_citation_graph 返回的图谱数据渲染为 PNG 图片并保存。"
            "必须先调用 build_citation_graph，再将结果传入此工具。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "graph_data": {
                    "type": "object",
                    "description": "build_citation_graph 的返回值（包含 nodes 和 edges）",
                },
                "title": {
                    "type": "string",
                    "description": "图片标题，默认'论文引用关系图谱'",
                    "default": "论文引用关系图谱",
                },
            },
            "required": ["graph_data"],
        },
    },

    # ── 图谱中心性分析 ────────────────────────────────────
    {
        "name": "analyze_graph_centrality",
        "description": (
            "分析引用图谱中哪些论文最重要（用 PageRank、入度中心性等指标）。"
            "必须先调用 build_citation_graph，再将结果传入此工具。"
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "graph_data": {
                    "type": "object",
                    "description": "build_citation_graph 的返回值",
                },
            },
            "required": ["graph_data"],
        },
    },

    # ── 保存论文 ──────────────────────────────────────────
    {
        "name": "save_paper",
        "description": "将一篇论文的信息保存到本地论文库，方便后续查阅。",
        "input_schema": {
            "type": "object",
            "properties": {
                "paper_data": {
                    "type": "object",
                    "description": "论文信息字典（get_paper_detail 的返回值）",
                },
            },
            "required": ["paper_data"],
        },
    },

    # ── 查看本地库 ────────────────────────────────────────
    {
        "name": "list_saved_papers",
        "description": "查看本地论文库中已保存的所有论文（可按关键词过滤）。",
        "input_schema": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "可选过滤词（匹配标题或摘要），不填则列出全部",
                    "default": "",
                },
            },
            "required": [],
        },
    },

    # ── 库统计 ────────────────────────────────────────────
    {
        "name": "get_library_stats",
        "description": "查看本地论文库的统计信息（论文总数、年份分布、类别分布）。",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]
