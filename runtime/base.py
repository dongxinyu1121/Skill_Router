"""维护智能体共享状态，并连接技能注册表、提示词和工具。

本模块不请求模型，也不读取终端输入；这些工作由 AgentLoop 完成。
评测脚本也复用此类，以获得与交互入口一致的初始提示词和工具描述。
"""

from pathlib import Path
from typing import Any, Dict, List

from core.prompts import base_system_prompt
from skill_core import SkillRegistry
from toolkit import BashTool, ReadFileTool, SkillTool, Tool


class AgentBase:
    """保存技能、工具和临时上下文，为运行循环提供公共操作。"""

    def __init__(self, skill_registry: SkillRegistry):
        """接收技能注册表，初始化工具映射与状态，并注册初始工具。

        初始只有 Skill 和 Bash；成功加载技能后才注册 ReadFile。
        conversation_history 预留为历史字段，当前 AgentLoop 实际使用
        run 方法里的局部 messages 列表维护对话。
        """
        self.skill_registry = skill_registry
        self.tools: Dict[str, Tool] = {}
        self.conversation_history: List[Dict[str, Any]] = []
        self.agent_context: Dict[str, Any] = {"working_directory": Path.cwd()}

        self._register_tool(SkillTool(skill_registry))
        self._register_tool(BashTool())

    def _register_tool(self, tool: Tool) -> None:
        """将工具对象存入名称映射，供生成工具描述和实际执行时查找。

        注册同名工具会替换此前对象，例如再次加载技能时更新 ReadFile。
        """
        self.tools[tool.name] = tool

    def _build_system_prompt(self) -> str:
        """将第一级技能目录填入写作提示词模板，返回可直接发送的系统指令。

        模板中的场景规则来自 core.prompts；技能名称和描述来自注册表。
        """
        return base_system_prompt.format(skills_registry=self.skill_registry.get_registry_prompt())

    def _get_tool_schema(self):
        """返回当前所有已注册工具的参数结构，告知模型有哪些可用能力。

        每次请求都重新生成，因此新注册的 ReadFile 能在下一次请求中出现。
        """
        return [tool.to_schema() for tool in self.tools.values()]

    def _reset_agent_context(self) -> None:
        """开始新的用户回合时清除临时技能状态，只保留工作目录。

        此操作不清空对话历史，也不删除已经注册的工具；ReadFile 一旦
        注册，会在后续回合继续出现在工具列表中。
        """
        self.agent_context = {"working_directory": Path.cwd()}

    def _in_skill_context(self) -> bool:
        """通过 skill_context 键是否存在，判断本回合是否成功加载过技能。"""
        return "skill_context" in self.agent_context

    def _set_skill_context(self, skill_context: Dict[str, Any]) -> None:
        """保存当前技能的名称、路径和正文，供后续工具执行与日志使用。

        路径保存在 agent_context['skill_context']['base_path'] 中。
        再次调用会覆盖上一个技能的状态，不保存多个技能的独立上下文。
        """
        self.agent_context["skill_context"] = skill_context

    def _attach_read_file_tool(self) -> None:
        """成功加载技能后创建 ReadFile，将当前上下文传入并注册工具。

        此处传入完整 agent_context 字典。具体路径如何解析由 ReadFile
        实现决定；其当前读取的顶层 base_path 与此处的嵌套状态存在差异。
        """
        read_file_tool = ReadFileTool()
        read_file_tool.set_context(self.agent_context)
        self._register_tool(read_file_tool)
