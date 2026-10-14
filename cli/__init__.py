"""对外导出命令行入口，使调用者可以通过 cli.run_agent 启动对话。"""

from .agent import main as run_agent

__all__ = ["run_agent"]
