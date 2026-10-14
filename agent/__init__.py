"""写作 Agent 的公开接口。

界面层通常只需导入 create_writing_agent；路由评测额外使用 ModelClient、
SkillRegistry 和 WritingAgent。模型响应等实现类型从其所属模块导入。
"""

from .engine import AgentResult, RouteResult, WritingAgent, create_writing_agent
from .model import ModelClient
from .skills import SkillRegistry

__all__ = [
    "AgentResult",
    "ModelClient",
    "RouteResult",
    "SkillRegistry",
    "WritingAgent",
    "create_writing_agent",
]
