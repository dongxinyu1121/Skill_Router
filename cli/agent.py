"""命令行界面：读取用户输入、调用 Agent 并显示结果。

在项目根目录执行 ``python -m cli.agent``。技能路径以当前工作目录为准，
因此从其他目录启动时，扫描到的技能也会不同。
"""

import argparse
from pathlib import Path
from typing import List, Optional

from agent import create_writing_agent


CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RESET = "\033[0m"
BOLD = "\033[1m"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """解析 --verbose；默认只显示简洁的技能、工具和最终回答。"""
    parser = argparse.ArgumentParser(description="启动渐进式技能写作 Agent")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示模型请求、工具参数和工具结果等详细调试信息",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """创建写作 Agent，持续接收终端输入，直到用户主动退出。

    CLI 只关心输入与显示；模型、技能、工具和历史消息全部由 agent 包管理。
    """
    args = parse_args(argv)
    skills_dir = Path.cwd() / ".claude" / "skills"
    writing_agent = create_writing_agent(skills_dir)

    print("已加载 %s 个技能。输入 quit 或 exit 退出。" % len(writing_agent.skill_names))
    while True:
        try:
            user_input = input("%s%sYou > %s" % (CYAN, BOLD, RESET)).strip()
        except (KeyboardInterrupt, EOFError):
            print("\n再见。")
            return

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit", "buy"}:
            print("再见。")
            return

        result = writing_agent.run(user_input)
        for line in result.logs:
            print(line)
        if args.verbose:
            for line in result.debug_logs:
                print(line)
        if result.error:
            print("%s请求失败：%s%s" % (YELLOW, result.error, RESET))
        elif result.answer:
            print("\n%s%sAssistant >%s %s\n" % (GREEN, BOLD, RESET, result.answer))


if __name__ == "__main__":
    # 被作为入口执行时启动对话；被其他模块导入时不启动。
    main()
