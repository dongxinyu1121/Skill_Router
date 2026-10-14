"""Agent 工具包。

三个具体工具分别定义在 skill.py、read_file.py 和 bash.py 中。本文件只负责
声明所有工具共用的接口与执行上下文，并通过 ToolRegistry 统一注册和调用工具。
外部模块仍然可以直接使用 ``from agent.tools import ToolRegistry``，不需要了解
工具包内部的文件划分。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..skills import Skill, SkillRegistry


@dataclass
class ToolContext:
    """工具执行期间共享的会话状态。

    active_skill 记录本轮已经加载的技能。ReadFile 工具会用该技能所在目录
    作为相对路径的起点，因此调用方不需要反复传递技能目录。
    """

    active_skill: Optional[Skill] = None


class Tool(ABC):
    """所有工具必须遵守的统一接口。"""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        required: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.parameters = parameters
        self.required = required or []

    def schema(self) -> Dict[str, Any]:
        """把工具信息转换为 OpenAI 兼容的函数工具描述。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "required": self.required,
                },
            },
        }

    @abstractmethod
    def execute(self, context: ToolContext, **arguments: Any) -> Dict[str, Any]:
        """执行工具，并返回能够写入模型消息的字典。"""


# Tool 和 ToolContext 定义完成后再导入具体工具。三个子模块会复用上面的公共接口。
from .bash import BashTool
from .read_file import ReadFileTool
from .skill import SkillTool


class ToolRegistry:
    """保存可用工具，生成模型所需描述，并按工具名称分发调用。"""

    def __init__(self, skill_registry: SkillRegistry):
        self._tools: Dict[str, Tool] = {}
        self.register(SkillTool(skill_registry))
        self.register(BashTool())

    def register(self, tool: Tool) -> None:
        """注册工具；如果名称已经存在，则使用新工具替换旧工具。"""
        self._tools[tool.name] = tool

    def enable_read_file(self) -> None:
        """技能成功加载后，开放第三级文件读取能力。"""
        if "ReadFile" not in self._tools:
            self.register(ReadFileTool())

    def schemas(self) -> List[Dict[str, Any]]:
        """返回当前所有工具的模型参数结构。"""
        return [tool.schema() for tool in self._tools.values()]

    def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: ToolContext,
    ) -> Dict[str, Any]:
        """按名称执行工具；未知名称返回失败结果，而不是抛出 KeyError。"""
        tool = self._tools.get(name)
        if not tool:
            return {"status": "failed", "message": "未知工具: %s" % name}

        result = tool.execute(context, **arguments)
        if name.lower() == "skill" and result.get("status") == "succeed":
            self.enable_read_file()
        return result


__all__ = [
    "BashTool",
    "ReadFileTool",
    "SkillTool",
    "Tool",
    "ToolContext",
    "ToolRegistry",
]
