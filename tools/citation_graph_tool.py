"""
引用关系图谱工具
================

用 networkx 构建论文之间的引用关系图，
并用 matplotlib 可视化，帮助研究者：
- 找到领域内最核心的论文（被引最多）
- 发现论文之间的继承关系
- 理解某个研究方向的演化脉络

图的节点 = 论文
图的有向边 = "A 引用了 B"（A → B）
"""

import json
from pathlib import Path
from typing import Optional

try:
    import networkx as nx
    import matplotlib
    matplotlib.use("Agg")          # 无显示器时使用非交互后端
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    HAS_GRAPH_LIBS = True
except ImportError:
    HAS_GRAPH_LIBS = False

from config import STORAGE_DIR
from tools.semantic_scholar_tool import get_paper_references, get_paper_citations


def build_citation_graph(
    seed_arxiv_ids: list[str],
    depth: int = 1,
    max_refs_per_paper: int = 15,
) -> dict:
    """
    以给定论文为种子，向外扩展构建引用关系图谱

    参数:
        seed_arxiv_ids:     起始论文 ID 列表（"种子"节点）
        depth:              扩展深度（1=只看直接引用，2=再看引用的引用）
        max_refs_per_paper: 每篇论文最多展开多少条参考文献

    返回:
        {
          "nodes": [{"id": ..., "title": ..., "year": ..., "is_seed": ...}],
          "edges": [{"source": ..., "target": ..., "type": "cites"}],
          "stats": {"total_nodes": ..., "total_edges": ...}
        }

    注意：depth>=2 时 API 调用次数会大幅增加，建议先用 depth=1
    """
    nodes = {}   # arxiv_id → node_info
    edges = []   # list of (source, target)
    visited = set()

    def expand(arxiv_id: str, current_depth: int, is_seed: bool):
        """递归扩展节点"""
        if arxiv_id in visited or current_depth > depth:
            return
        visited.add(arxiv_id)

        # 确保节点存在于 nodes 字典
        if arxiv_id not in nodes:
            nodes[arxiv_id] = {
                "id":      arxiv_id,
                "title":   arxiv_id,    # 暂用 ID，后续可补充标题
                "year":    None,
                "is_seed": is_seed,
            }

        if current_depth >= depth:
            return

        # 获取参考文献（这篇论文引用了哪些）
        refs_data = get_paper_references(arxiv_id, limit=max_refs_per_paper)
        for ref in refs_data.get("references", []):
            ref_arxiv = ref.get("arxiv_id", "")
            if not ref_arxiv:
                continue

            if ref_arxiv not in nodes:
                nodes[ref_arxiv] = {
                    "id":      ref_arxiv,
                    "title":   ref.get("title", ref_arxiv),
                    "year":    ref.get("year"),
                    "is_seed": False,
                }

            edge = (arxiv_id, ref_arxiv)
            if edge not in edges:
                edges.append(edge)

            # 递归扩展（深度+1）
            expand(ref_arxiv, current_depth + 1, is_seed=False)

    # 从种子节点开始扩展
    for seed_id in seed_arxiv_ids:
        expand(seed_id, current_depth=0, is_seed=True)

    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": s, "target": t, "type": "cites"} for s, t in edges],
        "stats": {
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "seed_count":  len(seed_arxiv_ids),
        },
    }


def visualize_citation_graph(
    graph_data: dict,
    output_path: Optional[str] = None,
    title: str = "论文引用关系图谱",
) -> str:
    """
    将引用图谱数据可视化为 PNG 图片

    参数:
        graph_data:  build_citation_graph() 的返回值
        output_path: 保存路径，默认保存到 paper_library/citation_graph.png
        title:       图片标题

    返回:
        保存的文件路径（字符串）
    """
    if not HAS_GRAPH_LIBS:
        return "错误：请安装 networkx 和 matplotlib（pip install networkx matplotlib）"

    if not output_path:
        output_path = str(STORAGE_DIR / "citation_graph.png")

    # 构建 networkx 有向图
    G = nx.DiGraph()
    node_colors = []
    node_sizes  = []
    labels      = {}

    for node in graph_data["nodes"]:
        nid   = node["id"]
        title = node.get("title", nid)
        # 截断过长标题
        short_title = title[:35] + "..." if len(title) > 35 else title
        G.add_node(nid)
        labels[nid] = f"{nid}\n{short_title}"
        # 种子节点用橙色，引用节点用蓝色
        node_colors.append("#FF8C00" if node.get("is_seed") else "#4A90D9")
        node_sizes.append(1200 if node.get("is_seed") else 600)

    for edge in graph_data["edges"]:
        G.add_edge(edge["source"], edge["target"])

    # 如果节点太少，布局选择弹簧布局；否则用分层布局
    n = len(G.nodes)
    if n == 0:
        return "图谱为空，无法可视化"

    try:
        if n <= 15:
            pos = nx.spring_layout(G, k=2.5, seed=42)
        else:
            pos = nx.kamada_kawai_layout(G)
    except Exception:
        pos = nx.random_layout(G, seed=42)

    # 使用系统英文字体，避免中文字形缺失警告
    plt.rcParams["font.family"] = "DejaVu Sans"

    fig, ax = plt.subplots(figsize=(16, 12))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color=node_colors,
        node_size=node_sizes,
        alpha=0.9,
    )
    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edge_color="#aaaaaa",
        arrows=True,
        arrowsize=15,
        arrowstyle="-|>",
        alpha=0.6,
        connectionstyle="arc3,rad=0.05",
    )
    nx.draw_networkx_labels(
        G, pos, labels=labels, ax=ax,
        font_size=6,
        font_color="white",
    )

    # 图例
    legend = [
        mpatches.Patch(color="#FF8C00", label="Seed Papers"),
        mpatches.Patch(color="#4A90D9", label="Referenced Papers"),
    ]
    ax.legend(handles=legend, loc="upper left", facecolor="#1a1a2e",
              labelcolor="white", fontsize=10)

    stats = graph_data.get("stats", {})
    ax.set_title(
        f"{title}\nNodes: {stats.get('total_nodes',0)} | Edges: {stats.get('total_edges',0)}",
        color="white", fontsize=13, pad=15,
    )
    ax.axis("off")
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()

    return output_path


def analyze_graph_centrality(graph_data: dict) -> dict:
    """
    分析图谱中各节点的重要性（中心性指标）

    指标说明：
    - in_degree (入度中心性)：被多少论文引用→越高越经典
    - pagerank：综合衡量影响力，考虑"被谁引用"
    - betweenness：处于多少条最短路径上→越高越是"桥梁论文"

    参数:
        graph_data: build_citation_graph() 的返回值

    返回:
        按 PageRank 排序的论文重要性列表
    """
    if not HAS_GRAPH_LIBS:
        return {"error": "需要 networkx：pip install networkx"}

    G = nx.DiGraph()
    node_titles = {n["id"]: n.get("title", n["id"]) for n in graph_data["nodes"]}

    for edge in graph_data["edges"]:
        G.add_edge(edge["source"], edge["target"])

    if len(G.nodes) == 0:
        return {"ranked_papers": []}

    # 计算各中心性指标
    in_degree   = nx.in_degree_centrality(G)
    try:
        pagerank = nx.pagerank(G, alpha=0.85, max_iter=100)
    except Exception:
        pagerank = {n: 0 for n in G.nodes}
    try:
        betweenness = nx.betweenness_centrality(G)
    except Exception:
        betweenness = {n: 0 for n in G.nodes}

    ranked = []
    for node_id in G.nodes:
        ranked.append({
            "id":         node_id,
            "title":      node_titles.get(node_id, node_id),
            "in_degree":  round(in_degree.get(node_id, 0), 4),
            "pagerank":   round(pagerank.get(node_id, 0), 4),
            "betweenness":round(betweenness.get(node_id, 0), 4),
        })

    # 按 PageRank 降序排列
    ranked.sort(key=lambda x: x["pagerank"], reverse=True)
    return {"ranked_papers": ranked[:20]}  # 只返回 top20
