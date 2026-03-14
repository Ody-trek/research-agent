"""
VLA / 具身智能领域搜索配置
============================

定义搜索词、经典论文 ID 列表、领域主题分类。
添加新方向只需在此文件中修改。
"""

# ── ArXiv 搜索词（每条会单独搜索 N 篇，结果去重合并）──────────────
SEARCH_QUERIES = [
    # 核心 VLA
    ("vision language action model robot",          "cs.RO", 12),
    ("vision language action embodied",             "cs.AI", 10),
    # 具身智能基础模型
    ("embodied agent large language model manipulation", "cs.RO", 10),
    ("robot foundation model language conditioned", "cs.RO", 10),
    # 操作学习
    ("robot manipulation policy transformer",       "cs.RO", 8),
    ("diffusion policy robot learning",             "cs.LG", 8),
    # 感知与表示
    ("visual representation robot pre-training",    "cs.CV", 8),
    ("multimodal robot perception grounding",       "cs.CV", 8),
    # 规划与推理
    ("llm robot task planning",                     "cs.AI", 8),
    ("world model robot planning embodied",         "cs.AI", 8),
]

# ── 必收经典论文（直接按 arXiv ID 获取，保证不漏掉）─────────────────
SEED_PAPER_IDS = [
    # ─ VLA 核心 ─
    "2307.15818",   # RT-2: Vision-Language-Action Models Transfer Web Knowledge
    "2212.06817",   # RT-1: Robotics Transformer
    "2406.09246",   # OpenVLA: An Open-Source Vision-Language-Action Model
    "2410.24164",   # π0: A Vision-Language-Action Flow Model for General Robot Control
    "2406.11833",   # Octo: An Open-Source Generalist Robot Policy
    "2312.14457",   # RoboVLMs Survey
    # ─ 基础模型用于机器人 ─
    "2204.01691",   # SayCan: Do As I Can, Not As I Say
    "2303.03378",   # PaLM-E: An Embodied Multimodal Language Model
    "2405.00776",   # ManipLLM
    # ─ 操作策略 ─
    "2304.13705",   # ACT: Learning Fine-Grained Bimanual Manipulation
    "2303.04137",   # Diffusion Policy: Visuomotor Policy Learning
    "2401.12945",   # Mobile ALOHA
    "2406.25260",   # Robotic View Planning via MLLM
    # ─ 视觉表示预训练 ─
    "2203.12601",   # R3M: Reusable Representations for Robot Manipulation
    "2206.06828",   # MVP: Masked Visual Pre-Training for Motor Control
    # ─ 规划 ─
    "2307.05973",   # VoxPoser: Composable 3D Value Maps for Robot Manipulation
    "2209.07753",   # Inner Monologue: Embodied Reasoning through Planning
    # ─ 数据集 ─
    "2310.08864",   # Open X-Embodiment Dataset
    "2406.20382",   # GROOT: Learning to Follow Instructions by Watching Video
    # ─ 综述 ─
    "2312.07843",   # A Survey on Language-Conditioned Robot Manipulation
]

# ── 主题分类（用于综述章节组织）────────────────────────────────────
SURVEY_THEMES = {
    "VLA核心架构":     "Vision-Language-Action Models",
    "基础模型迁移":    "Foundation Models for Robotics",
    "操作策略学习":    "Robot Manipulation Policies",
    "视觉表示学习":    "Visual Representation Learning",
    "任务规划推理":    "LLM-based Task Planning",
    "数据与基准":      "Datasets and Benchmarks",
}

# ── 综述生成提示词配置 ────────────────────────────────────────────
SURVEY_TITLE = "VLA与具身智能研究综述：从视觉-语言-动作模型到通用机器人"
SURVEY_SUBTITLE = "Vision-Language-Action Models and Embodied Intelligence: A Survey"
