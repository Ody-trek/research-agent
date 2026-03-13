"""
配置文件
========
统一管理 API keys、模型参数、路径等配置。
敏感信息从环境变量读取，绝不硬编码到代码里。
"""

import os
from pathlib import Path

# ── 路径 ────────────────────────────────────────────────────
ROOT_DIR    = Path(__file__).parent
STORAGE_DIR = ROOT_DIR / "paper_library"  # 本地论文库
STORAGE_DIR.mkdir(exist_ok=True)

# ── Anthropic ────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
# 使用 Opus 4.6，最强推理能力，适合科研分析
CLAUDE_MODEL = "claude-opus-4-6"

# ── Agent 行为 ───────────────────────────────────────────────
MAX_TOOL_ROUNDS = 20        # 最多调用工具多少轮，防止死循环
MAX_SEARCH_RESULTS = 10     # 单次 ArXiv 搜索返回最多条数
MAX_PAPERS_IN_REVIEW = 8    # 综述时最多引用几篇论文

# ── Semantic Scholar ─────────────────────────────────────────
# 免费，无需 key（可选：填入 key 提高请求频率上限）
S2_API_KEY  = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"
