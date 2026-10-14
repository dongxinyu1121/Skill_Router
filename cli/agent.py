"""命令行启动入口：连接技能注册表与交互式智能体。

在项目根目录执行 ``python -m cli.agent``。技能路径以当前工作目录为准，
因此从其他目录启动时，扫描到的技能也会不同。
"""

from pathlib import Path

from runtime import AgentLoop
from skill_core import SkillRegistry


def main() -> None:
    """扫描本地技能，创建使用真实模型的智能体，然后进入终端对话。

    注册表负责提供技能，智能体负责运行对话；入口只负责把两者连接起来。
    模型配置由智能体创建模型客户端时读取，不在此处直接处理。
    """
    # 初始化注册表会读取各技能文件；此时尚未向模型发送完整技能正文。
    skills_dir = Path.cwd() / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    agent = AgentLoop(registry)
    agent.run()


if __name__ == "__main__":
    # 被作为入口执行时启动对话；被其他模块导入时不启动。
    main()
