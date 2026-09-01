from pathlib import Path

from runtime import AgentLoop
from skill_core import SkillRegistry


def main() -> None:
    skills_dir = Path.cwd() / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    agent = AgentLoop(registry)
    agent.run()


if __name__ == "__main__":
    main()
