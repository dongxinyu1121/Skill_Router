from pathlib import Path

from runtime import MockAgent
from skill_core import SkillRegistry


def main() -> None:
    """启动 mock Agent，用固定输入演示三级渐进披露流程。"""
    skills_dir = Path.cwd() / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    agent = MockAgent(registry)
    agent.run("帮我审查一下刚才提交的代码")


if __name__ == "__main__":
    main()
