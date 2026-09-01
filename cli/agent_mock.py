from pathlib import Path

from runtime import MockAgent
from skill_core import SkillRegistry


def main() -> None:
    skills_dir = Path.cwd() / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    agent = MockAgent(registry)
    agent.run("帮我审查一下刚才提交的代码")


if __name__ == "__main__":
    main()
