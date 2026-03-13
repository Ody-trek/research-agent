"""
科研助手 Agent 核心
====================

实现 ReAct (Reasoning + Acting) 循环：

┌─────────────────────────────────────────────────────────┐
│                    Agent 主循环                           │
│                                                          │
│  用户输入                                                 │
│     ↓                                                    │
│  Claude (claude-opus-4-6 + adaptive thinking)            │
│     ↓                                                    │
│  ┌─ stop_reason == "tool_use" ─────────────────────┐    │
│  │  解析 tool_use 块                                 │    │
│  │  调用对应 Python 函数（工具路由）                  │    │
│  │  将结果作为 tool_result 消息发回给 Claude          │    │
│  └─────────────────────────────────────────────────┘    │
│     ↓                                                    │
│  stop_reason == "end_turn" → 输出最终回答                 │
└─────────────────────────────────────────────────────────┘

使用 adaptive thinking（让 Claude 自主决定思考深度），
对于复杂的科研分析任务效果最佳。

流式输出让用户实时看到 Claude 的回复，改善体验。
"""

import json
import anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL, MAX_TOOL_ROUNDS
from agent.prompts import SYSTEM_PROMPT
from agent.tool_definitions import TOOL_DEFINITIONS
from tools.arxiv_tool import search_papers, get_paper_detail
from tools.semantic_scholar_tool import (
    get_paper_citations, get_paper_references, get_paper_s2_details
)
from tools.citation_graph_tool import (
    build_citation_graph, visualize_citation_graph, analyze_graph_centrality
)
from storage.paper_store import (
    save_paper, list_saved_papers, get_library_stats
)


# ── 工具路由表：工具名 → Python 函数 ────────────────────────
# 当 Claude 决定调用某个工具时，在这里找到对应的 Python 函数执行
TOOL_ROUTER = {
    "search_arxiv":            lambda args: search_papers(
                                    query=args["query"],
                                    max_results=args.get("max_results", 8),
                                    category=args.get("category"),
                                    sort_by=args.get("sort_by", "relevance"),
                               ),
    "get_paper_detail":        lambda args: get_paper_detail(args["arxiv_id"]),
    "get_paper_citations":     lambda args: get_paper_citations(
                                    args["arxiv_id"],
                                    limit=args.get("limit", 15),
                               ),
    "get_paper_references":    lambda args: get_paper_references(
                                    args["arxiv_id"],
                                    limit=args.get("limit", 20),
                               ),
    "get_paper_s2_details":    lambda args: get_paper_s2_details(args["arxiv_id"]),
    "build_citation_graph":    lambda args: build_citation_graph(
                                    seed_arxiv_ids=args["seed_arxiv_ids"],
                                    depth=args.get("depth", 1),
                                    max_refs_per_paper=args.get("max_refs_per_paper", 10),
                               ),
    "visualize_citation_graph":lambda args: {
                                    "saved_path": visualize_citation_graph(
                                        graph_data=args["graph_data"],
                                        title=args.get("title", "论文引用关系图谱"),
                                    )
                               },
    "analyze_graph_centrality":lambda args: analyze_graph_centrality(args["graph_data"]),
    "save_paper":              lambda args: save_paper(args["paper_data"]),
    "list_saved_papers":       lambda args: list_saved_papers(args.get("keyword", "")),
    "get_library_stats":       lambda args: get_library_stats(),
}


def execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    执行一次工具调用，返回 JSON 字符串结果

    参数:
        tool_name:  工具名称（必须在 TOOL_ROUTER 中）
        tool_input: Claude 传入的参数字典

    返回:
        JSON 字符串（发送给 Claude 的 tool_result 内容）
    """
    handler = TOOL_ROUTER.get(tool_name)

    if handler is None:
        result = {"error": f"未知工具：{tool_name}"}
    else:
        try:
            result = handler(tool_input)
        except Exception as e:
            result = {"error": f"工具 {tool_name} 执行出错：{str(e)}"}

    # 工具结果以 JSON 字符串形式返回给 Claude
    return json.dumps(result, ensure_ascii=False, indent=2)


class ResearchAgent:
    """
    科研助手 Agent

    对话记录保存在 self.messages 列表中，
    支持多轮对话（上下文在整个会话内保留）。

    使用示例：
        agent = ResearchAgent()
        agent.chat("帮我找一些关于 ViT 的论文")
        agent.chat("把第一篇保存到本地库")
    """

    def __init__(self, verbose: bool = True):
        """
        参数:
            verbose: 是否打印工具调用过程（调试用）
        """
        if not ANTHROPIC_API_KEY:
            raise ValueError("请设置环境变量 ANTHROPIC_API_KEY")

        self.client   = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        self.messages = []   # 完整对话历史（多轮共享）
        self.verbose  = verbose

    def chat(self, user_input: str) -> str:
        """
        向 Agent 发送一条消息，获取完整回复

        支持多轮对话：每次调用都会在同一对话上下文中继续。

        参数:
            user_input: 用户输入的问题或指令

        返回:
            Agent 的最终文字回复
        """
        # 将用户消息加入对话历史
        self.messages.append({"role": "user", "content": user_input})

        round_count = 0
        final_text  = ""

        # ── ReAct 主循环 ──────────────────────────────────
        while round_count < MAX_TOOL_ROUNDS:
            round_count += 1

            # 使用流式调用，用户可以实时看到输出
            # adaptive thinking：让 Claude 自主决定是否以及如何思考
            with self.client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=8000,
                thinking={"type": "adaptive"},   # Opus 4.6 推荐用法
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=self.messages,
            ) as stream:
                # 实时打印文字内容（流式体验）
                for text_chunk in stream.text_stream:
                    print(text_chunk, end="", flush=True)

                # 等待完整响应（含工具调用块）
                response = stream.get_final_message()

            # 将 assistant 回复加入对话历史
            # 注意：必须保存完整的 response.content（含 thinking 块、tool_use 块）
            self.messages.append({
                "role":    "assistant",
                "content": response.content,
            })

            # ── 判断停止原因 ──────────────────────────────
            if response.stop_reason == "end_turn":
                # Claude 已完成，提取最终文字
                final_text = self._extract_text(response.content)
                break

            elif response.stop_reason == "tool_use":
                # Claude 想要调用工具
                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name  = block.name
                    tool_input = block.input

                    if self.verbose:
                        print(f"\n\n🔧 [工具调用] {tool_name}")
                        # 显示关键参数（截断避免过长）
                        preview = json.dumps(tool_input, ensure_ascii=False)[:120]
                        print(f"   参数: {preview}")

                    # 执行工具
                    result_str = execute_tool(tool_name, tool_input)

                    if self.verbose:
                        result_preview = result_str[:200].replace("\n", " ")
                        print(f"   结果: {result_preview}...\n")

                    tool_results.append({
                        "type":        "tool_result",
                        "tool_use_id": block.id,    # 必须与 tool_use 的 id 匹配
                        "content":     result_str,
                    })

                # 将所有工具结果作为一条 user 消息发回
                self.messages.append({
                    "role":    "user",
                    "content": tool_results,
                })
                # 继续循环，Claude 会处理工具结果后继续回复

            else:
                # 其他停止原因（max_tokens 等）
                final_text = self._extract_text(response.content)
                if response.stop_reason == "max_tokens":
                    final_text += "\n\n[注意：回复因超出长度限制被截断]"
                break

        if round_count >= MAX_TOOL_ROUNDS:
            final_text = "已达到最大工具调用轮次，请尝试更简单的问题。"

        # 在流式输出后加换行
        print()
        return final_text

    def _extract_text(self, content: list) -> str:
        """从 response.content 列表中提取所有文字块"""
        texts = []
        for block in content:
            if hasattr(block, "type") and block.type == "text":
                texts.append(block.text)
        return "\n".join(texts)

    def reset(self):
        """清空对话历史，开始新会话"""
        self.messages = []
        print("✓ 已开始新的对话")

    def show_history(self):
        """打印对话历史摘要（调试用）"""
        print(f"\n对话历史：共 {len(self.messages)} 条消息")
        for i, msg in enumerate(self.messages):
            role = msg["role"]
            content = msg["content"]
            if isinstance(content, str):
                preview = content[:80]
            elif isinstance(content, list):
                preview = f"[{len(content)}个块]"
            else:
                preview = str(content)[:80]
            print(f"  [{i}] {role}: {preview}")
