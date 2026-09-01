from typing import Dict

from skill_core import SkillRegistry

from .base import Tool


class SkillTool(Tool):
    """Load a full SKILL.md file by skill name."""

    def __init__(self, registry: SkillRegistry):
        """绑定 skill 注册表，并声明 Skill 工具 schema。"""
        super().__init__(
            name="Skill",
            description="加载技能（skills）完整指令。参数: {'command': '技能名称'}",
            params={"command": {"type": "string", "description": "技能名称，如 'code-reviewer'"}},
            required=["command"],
        )
        self.registry = registry

    def execute(self, command: str) -> Dict[str, str]:
        """按技能名称加载完整 SKILL.md 正文。"""
        skill = self.registry.load_full_skill(command)
        if not skill:
            return {"status": "failed", "message": f"Skill '{command}' 不存在"}

        return {
            "status": "succeed",
            "message": f"启动技能: {command}",
            "command_name": command,
            "base_path": str(skill.base_path),
            "content": skill.content,
            "note": "请按照上述技能指令执行。如需查阅引用文件（如 references/xxx.md），使用 ReadFile 工具并基于 Base Path 构造路径",
        }
