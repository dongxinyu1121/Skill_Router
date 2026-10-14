"""技能数据结构与注册表。

本模块负责从磁盘发现技能，并提供三个层次的数据：用于路由的名称和描述、
选中后的完整技能指令，以及技能目录中的引用文件。它不负责调用模型。
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Set

import yaml


@dataclass(frozen=True)
class SkillMetadata:
    """第一级披露使用的名称和描述，以及可选的维护信息。"""

    name: str
    description: str
    author: Optional[str] = None
    version: Optional[str] = None


@dataclass(frozen=True)
class Skill:
    """一个可执行技能的元数据、完整文字指令和资源根目录。"""

    metadata: SkillMetadata
    content: str
    base_path: Path

    @property
    def name(self) -> str:
        """返回工具调用时使用的技能名称。"""
        return self.metadata.name


class SkillRegistry:
    """扫描技能目录，并以名称为接口提供技能内容。"""

    def __init__(self, skills_dir: Path):
        """保存技能根目录，并立即扫描其中的一级子目录。"""
        self.skills_dir = skills_dir
        self._skills: Dict[str, Skill] = {}
        self._scan()

    @property
    def names(self) -> Set[str]:
        """返回所有已注册技能名称的副本，避免调用者访问内部字典。"""
        return set(self._skills)

    def get(self, name: str) -> Optional[Skill]:
        """按名称返回完整技能；名称不存在时返回 None。"""
        return self._skills.get(name)

    def build_catalog_prompt(self) -> str:
        """生成只包含技能名称、描述和选择说明的第一级提示词。"""
        lines = [
            "# 技能注册表（Skills Registry）\n",
            "以下是你可用的技能列表。每个技能包含名称和描述。"
            "**当用户需求匹配某个技能的描述时，调用 `Skill` 工具加载完整指令**：\n",
        ]
        for name, skill in self._skills.items():
            lines.append("1. **%s**: %s" % (name, skill.metadata.description))
        lines.extend(
            [
                "\n如何使用技能：",
                "- 使用技能描述判断用户意图，而非仅匹配关键词",
                "- 只要意图相符，立即调用对应 Skill 工具，不要直接回应",
                "- 你不需要知道 Skill 的文件路径，只需传递技能名称给 Skill 工具",
            ]
        )
        return "\n".join(lines)

    def _scan(self) -> None:
        """按目录名排序扫描技能，忽略根目录文件和格式无效的目录。"""
        if not self.skills_dir.exists():
            return
        for skill_dir in sorted(self.skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = self._find_skill_file(skill_dir)
            if skill_file:
                self._load_skill(skill_dir, skill_file)

    @staticmethod
    def _find_skill_file(skill_dir: Path) -> Optional[Path]:
        """优先查找 SKILL.md，未找到时兼容 skill.md。"""
        for filename in ("SKILL.md", "skill.md"):
            candidate = skill_dir / filename
            if candidate.is_file():
                return candidate
        return None

    def _load_skill(self, skill_dir: Path, skill_file: Path) -> None:
        """解析 YAML 文件头和 Markdown 正文，成功后加入名称索引。"""
        source = skill_file.read_text(encoding="utf-8")
        if not source.startswith("---"):
            return
        parts = source.split("---", 2)
        if len(parts) < 3:
            return
        try:
            metadata = yaml.safe_load(parts[1]) or {}
        except Exception as exc:
            print("加载技能失败 %s: %s" % (skill_dir.name, exc))
            return

        skill_metadata = SkillMetadata(
            name=metadata.get("name", skill_dir.name),
            description=metadata.get("description", ""),
            author=metadata.get("author"),
            version=metadata.get("version"),
        )
        self._skills[skill_metadata.name] = Skill(
            metadata=skill_metadata,
            content=parts[2].strip(),
            base_path=skill_dir,
        )
