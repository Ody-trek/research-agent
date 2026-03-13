# 🔬 科研助手 Agent

> 由 **Claude Opus 4.6**（adaptive thinking）驱动，整合 ArXiv + Semantic Scholar，
> 帮助研究者快速搜索、精读、综述学术论文，并可视化论文引用关系图谱。

---

## ✨ 功能一览

| 功能 | 说明 |
|------|------|
| 🔍 **论文搜索** | 关键词/作者/类别搜索 ArXiv，支持高级语法 |
| 📖 **论文精读** | 获取完整摘要，结合 Claude 深度分析核心贡献 |
| 📊 **影响力分析** | 从 Semantic Scholar 获取引用次数、高影响力引用 |
| 🕸️ **引用图谱** | 构建并可视化论文之间的引用关系网络 |
| 🏆 **重要性排序** | 用 PageRank 找出领域内最核心的论文 |
| 📝 **文献综述** | 多轮对话生成结构化的研究方向综述 |
| 💾 **本地论文库** | 保存感兴趣的论文，跨对话保留研究成果 |

---

## 🚀 快速开始

```bash
git clone https://github.com/Ody-trek/research-agent
cd research-agent

# 安装依赖
pip install -r requirements.txt

# 设置 API Key
export ANTHROPIC_API_KEY="your-key-here"

# 启动交互模式
python main.py

# 或单次查询
python main.py "帮我找5篇关于大语言模型幻觉问题的论文"
```

---

## 💬 使用示例

```
📝 你: 帮我搜索关于 Chain-of-Thought prompting 的论文

🤖 助手: 正在搜索...

🔧 [工具调用] search_arxiv
   参数: {"query": "chain-of-thought prompting reasoning", "max_results": 8}

找到了以下几篇重要论文：

### 1. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models
- **ArXiv**: `2201.11903`  发表: 2022-01-28
- **作者**: Jason Wei, Xuezhi Wang, Dale Schuurmans 等（Google Brain）
- **核心贡献**: 首次系统提出 CoT 提示方法，展示通过"展示推理步骤"
  可以显著提升大模型在数学、推理等任务上的表现...
```

---

## 🏗️ 项目架构

```
research-agent/
│
├── main.py                   # 命令行入口（交互 + 单次查询模式）
├── config.py                 # 配置（API key、模型参数、路径）
│
├── agent/
│   ├── core.py               # ReAct 主循环（Claude + Tool Use）
│   ├── prompts.py            # 系统提示词（角色定义 + 行为规范）
│   └── tool_definitions.py   # 工具 JSON Schema（Claude 调用时参考）
│
├── tools/
│   ├── arxiv_tool.py         # ArXiv 搜索 & 详情获取
│   ├── semantic_scholar_tool.py  # S2 引用数据
│   └── citation_graph_tool.py    # 图谱构建 & 可视化 & 中心性分析
│
├── storage/
│   └── paper_store.py        # 本地论文库（JSON 文件）
│
├── examples/
│   └── demo.py               # 各模块独立演示
│
└── paper_library/            # 自动创建，存储本地论文数据
    ├── papers.json
    └── citation_graph.png
```

---

## 🧠 技术架构详解

### Agent 主循环（ReAct 模式）

```
用户输入
  ↓
Claude (adaptive thinking)
  ↓
┌─ stop_reason == "tool_use" ──────────────────────────┐
│  解析 tool_use 块 → 执行 Python 函数 → tool_result    │
│  发回 Claude → Claude 继续思考...                      │
└──────────────────────────────────────────────────────┘
  ↓
stop_reason == "end_turn" → 输出最终回答
```

### 为什么用 Adaptive Thinking？

`thinking: {type: "adaptive"}` 让 Claude 自主决定：
- 简单搜索任务：快速直接回答
- 复杂综述任务：深度推理后给出结构化分析

比固定 `budget_tokens` 更灵活，成本与质量自动平衡。

### 工具调用流程

```python
# Claude 返回 tool_use 块
{"type": "tool_use", "name": "search_arxiv", "input": {"query": "ViT"}}

# Agent 路由到对应函数
result = TOOL_ROUTER["search_arxiv"]({"query": "ViT"})

# 结果发回 Claude
{"type": "tool_result", "tool_use_id": "...", "content": "...JSON..."}
```

---

## 🔧 支持的工具

| 工具名 | 数据源 | 用途 |
|--------|--------|------|
| `search_arxiv` | ArXiv API | 关键词搜索论文 |
| `get_paper_detail` | ArXiv API | 获取单篇论文完整信息 |
| `get_paper_citations` | Semantic Scholar | 谁引用了这篇论文 |
| `get_paper_references` | Semantic Scholar | 这篇论文引用了谁 |
| `get_paper_s2_details` | Semantic Scholar | 引用次数、影响力分数 |
| `build_citation_graph` | S2 + 本地计算 | 构建引用关系图 |
| `visualize_citation_graph` | networkx + matplotlib | 生成图谱 PNG |
| `analyze_graph_centrality` | networkx | PageRank 重要性排序 |
| `save_paper` | 本地文件 | 保存到论文库 |
| `list_saved_papers` | 本地文件 | 查看论文库 |
| `get_library_stats` | 本地文件 | 库统计信息 |

---

## 📁 可选配置

```bash
# Semantic Scholar API Key（可选，提高请求频率限制）
# 申请：https://www.semanticscholar.org/product/api
export SEMANTIC_SCHOLAR_API_KEY="your-s2-key"
```

---

## 📚 参考

- [Anthropic Claude API 文档](https://platform.claude.com/docs)
- [ArXiv API 文档](https://info.arxiv.org/help/api/)
- [Semantic Scholar API](https://api.semanticscholar.org/api-docs/)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)

---

MIT License — 欢迎 Star ⭐
