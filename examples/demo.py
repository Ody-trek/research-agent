"""
演示脚本：展示 Agent 的各种能力
================================

运行前请确保设置了 ANTHROPIC_API_KEY 环境变量。
运行方式：python examples/demo.py

每个 demo_* 函数演示一种使用场景。
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── 不需要 API Key 的工具单独测试 ──────────────────────────
def demo_arxiv_search():
    """直接测试 ArXiv 搜索工具（无需 API Key）"""
    from tools.arxiv_tool import search_papers, get_paper_detail

    print("=" * 55)
    print("1. ArXiv 搜索测试")
    print("=" * 55)

    # 搜索 Vision Transformer 相关论文
    results = search_papers("vision transformer image recognition", max_results=3)
    print(f"找到 {len(results)} 篇论文：\n")
    for i, p in enumerate(results, 1):
        print(f"  [{i}] {p['title']}")
        print(f"       ID: {p['id']}  发表: {p['published']}")
        print(f"       {p['abstract'][:150]}...\n")

    # 获取 "Attention Is All You Need" 的完整详情
    print("\n获取 Transformer 原论文详情（1706.03762）：")
    detail = get_paper_detail("1706.03762")
    if "error" not in detail:
        print(f"  标题：{detail['title']}")
        print(f"  作者：{', '.join(detail['authors'][:3])}...")
        print(f"  类别：{detail['categories']}")
        print(f"  备注：{detail.get('comment', '无')}")
    else:
        print(f"  错误：{detail['error']}")


def demo_semantic_scholar():
    """测试 Semantic Scholar 引用数据（无需 API Key）"""
    from tools.semantic_scholar_tool import get_paper_s2_details, get_paper_references

    print("\n" + "=" * 55)
    print("2. Semantic Scholar 数据测试")
    print("=" * 55)

    # 查询 BERT 论文的影响力（BERT: 1810.04805）
    print("BERT 论文（1810.04805）的影响力数据：")
    details = get_paper_s2_details("1810.04805")
    if "note" not in details:
        print(f"  总引用次数：{details.get('citation_count', 'N/A')}")
        print(f"  高影响力引用：{details.get('influential_citation_count', 'N/A')}")
        print(f"  研究领域：{details.get('fields_of_study', [])}")
    else:
        print(f"  {details['note']}")

    # 查询参考文献
    print("\nBERT 论文的部分参考文献：")
    refs = get_paper_references("1810.04805", limit=5)
    for r in refs.get("references", []):
        if r.get("title"):
            print(f"  - {r['title'][:60]}  ({r.get('year', '?')})")


def demo_paper_store():
    """测试本地论文库功能（无需 API Key）"""
    from tools.arxiv_tool import get_paper_detail
    from storage.paper_store import save_paper, list_saved_papers, get_library_stats, delete_paper

    print("\n" + "=" * 55)
    print("3. 本地论文库测试")
    print("=" * 55)

    # 获取并保存一篇论文
    print("获取并保存 ResNet 论文（1512.03385）...")
    paper = get_paper_detail("1512.03385")
    if "error" not in paper:
        result = save_paper(paper)
        print(f"  {result['message']}")

    # 查看库中内容
    library = list_saved_papers()
    print(f"\n本地库共 {library['count']} 篇论文：")
    for p in library["papers"]:
        print(f"  - [{p['id']}] {p['title'][:50]}")

    # 统计
    stats = get_library_stats()
    print(f"\n库统计：{stats}")

    # 清理（删除刚才保存的）
    delete_paper("1512.03385")
    print("  已清理测试数据")


def demo_citation_graph():
    """测试引用图谱构建与可视化（无需 API Key）"""
    from tools.citation_graph_tool import (
        build_citation_graph, visualize_citation_graph, analyze_graph_centrality
    )

    print("\n" + "=" * 55)
    print("4. 引用图谱测试")
    print("=" * 55)

    # 以 ResNet 和 VGG 为种子构建图谱
    seed_ids = ["1512.03385", "1409.1556"]  # ResNet, VGGNet
    print(f"构建图谱（种子：{seed_ids}，深度=1）...")

    graph = build_citation_graph(seed_ids, depth=1, max_refs_per_paper=8)
    stats = graph["stats"]
    print(f"  节点数：{stats['total_nodes']}  边数：{stats['total_edges']}")

    if stats["total_nodes"] > 0:
        # 中心性分析
        centrality = analyze_graph_centrality(graph)
        top3 = centrality.get("ranked_papers", [])[:3]
        if top3:
            print("\n  最重要的3篇论文（按PageRank）：")
            for p in top3:
                print(f"    [{p['id']}] PageRank={p['pagerank']:.4f}")

        # 可视化
        print("\n  保存图谱可视化...")
        path = visualize_citation_graph(graph, title="ResNet & VGGNet 引用图谱")
        if path and not path.startswith("错误"):
            print(f"  已保存至：{path}")
        else:
            print(f"  {path}")


def demo_agent_chat():
    """演示完整 Agent 对话（需要 ANTHROPIC_API_KEY）"""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        print("\n" + "=" * 55)
        print("5. Agent 对话演示（跳过：未设置 ANTHROPIC_API_KEY）")
        print("=" * 55)
        print("请设置环境变量后运行：")
        print("  export ANTHROPIC_API_KEY='your-key'")
        print("  python main.py")
        return

    from agent import ResearchAgent

    print("\n" + "=" * 55)
    print("5. Agent 完整对话演示")
    print("=" * 55)

    agent = ResearchAgent(verbose=True)

    # 演示多轮对话
    queries = [
        "搜索3篇关于 Retrieval-Augmented Generation (RAG) 的论文，简要介绍它们的主要贡献",
        "帮我查一下第一篇论文的引用次数，并把它保存到本地库",
    ]

    for q in queries:
        print(f"\n\n📝 用户: {q}")
        print("🤖 助手: ", end="", flush=True)
        agent.chat(q)
        print()

    print("\n✓ 多轮对话演示完成！上下文在整个对话中保留。")


if __name__ == "__main__":
    print("科研助手 Agent — 功能演示\n")

    demo_arxiv_search()
    demo_semantic_scholar()
    demo_paper_store()
    demo_citation_graph()
    demo_agent_chat()

    print("\n" + "=" * 55)
    print("演示完成！运行 python main.py 启动交互模式")
    print("=" * 55)
