"""
科研助手 Agent — 命令行入口
==============================

运行方式：
  python main.py                  # 交互模式
  python main.py "搜索ViT相关论文"  # 单次查询模式

环境变量：
  ANTHROPIC_API_KEY  （必须）
  SEMANTIC_SCHOLAR_API_KEY  （可选，提高 S2 请求频率）
"""

import sys
import os
from agent import ResearchAgent

WELCOME = """
╔══════════════════════════════════════════════════════╗
║           🔬  科研助手 Agent  (Research Agent)        ║
║                                                      ║
║  由 Claude Opus 4.6 驱动 · 数据来自 ArXiv + S2       ║
╚══════════════════════════════════════════════════════╝

可以问我：
  • "帮我搜索 Diffusion Model 最新论文"
  • "精读这篇论文：1706.03762"
  • "分析 Transformer 和 BERT 的引用关系图谱"
  • "生成一篇关于视觉大模型的文献综述"
  • "把刚才找到的论文保存到本地库"
  • "查看我的本地论文库"

输入 'new'   → 开始新对话
输入 'hist'  → 查看对话历史
输入 'quit'  → 退出
"""


def check_api_key():
    """检查 API Key 是否已配置"""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        print("❌ 错误：请先设置 ANTHROPIC_API_KEY 环境变量")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)
    print(f"✓ API Key 已配置（{key[:8]}...）")


def interactive_mode(agent: ResearchAgent):
    """交互式命令行界面"""
    print(WELCOME)

    while True:
        try:
            user_input = input("\n📝 你: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n再见！")
            break

        if not user_input:
            continue

        # 特殊命令
        if user_input.lower() in ("quit", "exit", "q", "退出"):
            print("再见！")
            break
        elif user_input.lower() in ("new", "reset", "新对话"):
            agent.reset()
            continue
        elif user_input.lower() in ("hist", "history", "历史"):
            agent.show_history()
            continue
        elif user_input.lower() in ("help", "?", "帮助"):
            print(WELCOME)
            continue

        # 发送给 Agent
        print("\n🤖 助手: ", end="", flush=True)
        try:
            agent.chat(user_input)
        except KeyboardInterrupt:
            print("\n[已中断]")
        except Exception as e:
            print(f"\n❌ 出错了：{e}")
            import traceback
            traceback.print_exc()


def main():
    check_api_key()
    agent = ResearchAgent(verbose=True)

    if len(sys.argv) > 1:
        # 单次查询模式：python main.py "搜索ViT论文"
        query = " ".join(sys.argv[1:])
        print(f"🤖 助手: ", end="", flush=True)
        agent.chat(query)
        print()
    else:
        # 交互模式
        interactive_mode(agent)


if __name__ == "__main__":
    main()
