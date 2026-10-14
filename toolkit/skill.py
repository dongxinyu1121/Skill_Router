"""把技能注册表包装成模型可以调用的 Skill 工具，实现第二级披露。"""

from typing import Dict

from skill_core import SkillRegistry

from .base import Tool


class SkillTool(Tool):
    """按技能名称获取完整指令，供模型在后续推理中遵循。

    加载技能不等于运行某个 Python 函数：工具返回的是文字指令，
    模型读完后才决定如何完成写作或继续调用资源工具。
    """

    def __init__(self, registry: SkillRegistry):
        """接收已初始化的注册表，声明唯一必填参数 command。

        command 是技能的公开名称，不是文件路径或终端命令。
        本工具复用传入的注册表，不重新扫描技能目录。
        """
        super().__init__(
            name="Skill",
            description="加载技能（skills）完整指令。参数: {'command': '技能名称'}",
            params={"command": {"type": "string", "description": "技能名称，如 'code-reviewer'"}},
            required=["command"],
        )
        self.registry = registry

    def execute(self, command: str) -> Dict[str, str]:
        """从注册表取出技能，返回状态、技能名称、所在目录和完整正文。

        名称不存在时返回失败信息；成功时由 AgentLoop 将结果追加到对话。
        本方法不修改智能体上下文，也不执行正文中提到的脚本。
        """
        skill = self.registry.load_full_skill(command)
        if not skill:
            return {"status": "failed", "message": f"Skill '{command}' 不存在"}

        # 运行层用 command_name 和 base_path 设置当前技能，用 content 向模型披露正文。
        return {
            "status": "succeed",
            "message": f"启动技能: {command}",
            "command_name": command,
            "base_path": str(skill.base_path),
            "content": skill.content,
            "note": "请按照上述技能指令执行。如需查阅引用文件（如 references/xxx.md），使用 ReadFile 工具并基于 Base Path 构造路径",
        }
