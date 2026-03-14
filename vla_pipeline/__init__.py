"""
VLA 具身智能论文批量综述流水线
================================

流程：
  1. 从 ArXiv 收集 VLA / 具身智能相关论文
  2. 用 Batches API（5折优惠）批量分析每篇论文
  3. 用 Streaming 生成完整综述 Markdown
  4. 自动提交到 GitHub
"""
