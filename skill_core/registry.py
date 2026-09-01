from pathlib import Path
from typing import Dict, Optional

import yaml

from .models import Skill, SkillMetadata


class SkillRegistry:
    """Scan skill folders and expose Level 1/2/3 skill data."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._load_all_skills()

    def _load_all_skills(self) -> None:
        if not self.skills_dir.exists():
            return

        for skill_dir in sorted(self.skills_dir.iterdir()):
            if skill_dir.is_dir():
                skill_md = self._find_skill_file(skill_dir)
                if skill_md:
                    self._load_skill(skill_dir, skill_md)

    def _find_skill_file(self, skill_dir: Path) -> Optional[Path]:
        for candidate in ("SKILL.md", "skill.md"):
            skill_md = skill_dir / candidate
            if skill_md.exists():
                return skill_md
        return None

    def _load_skill(self, skill_dir: Path, skill_md: Path) -> None:
        content = skill_md.read_text(encoding="utf-8")
        if not content.startswith("---"):
            return

        parts = content.split("---", 2)
        if len(parts) < 3:
            return

        try:
            meta = yaml.safe_load(parts[1]) or {}
        except Exception as exc:
            print(f"加载技能失败 {skill_dir.name}: {exc}")
            return

        metadata = SkillMetadata(
            name=meta.get("name", skill_dir.name),
            description=meta.get("description", ""),
            author=meta.get("author"),
            version=meta.get("version"),
        )
        self._skills[metadata.name] = Skill(
            metadata=metadata,
            content=parts[2].strip(),
            base_path=skill_dir,
        )

    def get_registry_prompt(self) -> str:
        lines = [
            "# 技能注册表（Skills Registry）\n",
            "以下是你可用的技能列表。每个技能包含名称和描述。**当用户需求匹配某个技能的描述时，调用 `Skill` 工具加载完整指令**：\n",
        ]

        for name, skill in self._skills.items():
            lines.append(f"1. **{name}**: {skill.metadata.description}")

        lines.extend(
            [
                "\n如何使用技能：",
                "- 使用技能描述判断用户意图，而非仅匹配关键词",
                "- 只要意图相符，立即调用对应 Skill 工具，不要直接回应",
                "- 你不需要知道 Skill 的文件路径，只需传递技能名称给 Skill 工具",
            ]
        )
        return "\n".join(lines)

    def load_full_skill(self, name: str) -> Optional[Skill]:
        return self._skills.get(name)

    def load_reference(self, skill_name: str, ref_path: str) -> Optional[str]:
        skill = self._skills.get(skill_name)
        if not skill:
            return None

        full_path = skill.base_path / ref_path
        if full_path.exists():
            return full_path.read_text(encoding="utf-8")
        return None
