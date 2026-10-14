"""写作 Agent 的主流程。

阅读本项目时建议先看 WritingAgent.run：它完整呈现一次用户请求如何经过模型、
工具和技能，最后形成回答。模型通信、技能解析和工具实现分别下沉到其他模块。
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .model import Model, ModelClient, ModelResponse, ToolCall
from .prompts import base_system_prompt
from .skills import SkillRegistry
from .tools import ToolContext, ToolRegistry


@dataclass
class AgentResult:
    """执行一次用户请求后返回给界面层的结果。

    answer 是最终回答；logs 是默认显示的简洁进度，debug_logs 是按执行顺序
    保存的详细记录。error 不为空表示本轮模型请求失败。日志在任务结束后显示，
    本项目没有引入实时事件或流式输出系统。
    """

    answer: str = ""
    logs: List[str] = field(default_factory=list)
    debug_logs: List[str] = field(default_factory=list)
    error: Optional[str] = None


@dataclass
class RouteResult:
    """只执行第一轮模型判断时得到的技能路由结果。"""

    selected_skills: List[str]
    status: str
    stop_reason: Optional[str]
    error: Optional[str] = None


class WritingAgent:
    """维护对话历史，并协调模型与工具完成写作任务。

    对外只有 run 和 route 两个主要接口：run 完成一次完整任务，route 只做
    第一轮技能选择，供评测脚本使用。终端输入和显示不属于本类职责。
    """

    def __init__(self, registry: SkillRegistry, model: Model):
        """注入技能注册表和模型客户端，并建立独立的对话历史。"""
        self._registry = registry
        self._model = model
        self._tools = ToolRegistry(registry)
        self._history: List[Dict[str, Any]] = []

    @property
    def skill_names(self) -> Set[str]:
        """返回技能名称副本，供界面展示数量，无需了解注册表内部结构。"""
        return self._registry.names

    def run(self, user_input: str) -> AgentResult:
        """处理一条用户输入，必要时反复执行工具，最终返回回答和日志。

        每次 run 都重置当前技能，但保留之前的多轮对话。
        模型请求失败时撤回本次任务添加的所有消息，避免错误历史污染后续对话。
        """
        result = AgentResult()
        context = ToolContext()
        history_start = len(self._history)
        self._history.append({"role": "user", "content": user_input})

        while True:
            response = self._request_model(result)
            if not response.succeeded:
                del self._history[history_start:]
                result.error = response.error or "模型请求失败"
                return result

            if response.requests_tools:
                self._record_tool_request(response)
                self._execute_tools(response.tool_calls, context, result)
                continue

            answer = response.content or ""
            self._history.append({"role": "assistant", "content": answer})
            result.answer = answer
            return result

    def route(self, user_input: str) -> RouteResult:
        """只请求模型一次并返回它选择的 Skill，不修改正式对话历史。

        该公开接口使评测脚本不需要调用 Agent 的私有提示词或工具方法。
        它不会执行 Skill，也不会请求模型生成第二轮最终回答。
        """
        # 每条评测使用初始工具集，避免先前 run 开放的 ReadFile 影响路由口径。
        initial_tools = ToolRegistry(self._registry)
        response = self._model.generate(
            messages=[{"role": "user", "content": user_input}],
            system_prompt=self._build_system_prompt(),
            tool_schema=initial_tools.schemas(),
        )
        selected = [
            call.arguments["command"]
            for call in response.tool_calls
            if call.name.lower() == "skill" and call.arguments.get("command")
        ]
        return RouteResult(
            selected_skills=selected,
            status=response.status,
            stop_reason=response.stop_reason,
            error=response.error,
        )

    def _build_system_prompt(self) -> str:
        """把第一级技能目录填入固定的写作场景提示词。"""
        return base_system_prompt.format(
            skills_registry=self._registry.build_catalog_prompt()
        )

    def _request_model(self, result: AgentResult) -> ModelResponse:
        """使用最新消息和工具列表请求模型，并记录详细调试信息。"""
        schemas = self._tools.schemas()
        result.debug_logs.append(
            "[模型请求] messages=%s tools=%s"
            % (len(self._history), [item["function"]["name"] for item in schemas])
        )
        response = self._model.generate(
            messages=self._history,
            system_prompt=self._build_system_prompt(),
            tool_schema=schemas,
        )
        result.debug_logs.append(
            "[模型响应] status=%s stop_reason=%s content=%r tool_calls=%s"
            % (
                response.status,
                response.stop_reason,
                response.content,
                [call.name for call in response.tool_calls],
            )
        )
        return response

    def _record_tool_request(self, response: ModelResponse) -> None:
        """先记录助手提出的工具调用，保证后续工具消息顺序符合接口协议。"""
        self._history.append(
            {
                "role": "assistant",
                "content": response.content,
                "tool_calls": [call.raw for call in response.tool_calls],
            }
        )

    def _execute_tools(
        self,
        calls: List[ToolCall],
        context: ToolContext,
        result: AgentResult,
    ) -> None:
        """顺序执行模型提出的工具，并把每个结果追加到对话历史。"""
        for call in calls:
            tool_result = self._tools.execute(call.name, call.arguments, context)
            if tool_result.get("status") != "succeed":
                result.logs.append(
                    "[工具] %s 失败：%s" % (call.name, tool_result.get("message", "未知错误"))
                )
            elif call.name.lower() == "skill":
                result.logs.append("[技能] 已加载 %s" % tool_result["command_name"])
            elif call.name.lower() != "skill":
                result.logs.append("[工具] 已执行 %s" % call.name)

            result.debug_logs.append(
                "[工具调用] name=%s id=%s arguments=%r result=%r"
                % (call.name, call.call_id, call.arguments, tool_result)
            )
            self._history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.call_id,
                    "content": str(tool_result),
                }
            )


def create_writing_agent(
    skills_dir: Optional[Path] = None,
    model: Optional[Model] = None,
) -> WritingAgent:
    """创建默认写作 Agent；测试可以传入假模型避免网络请求。

    未传技能目录时，使用当前工作目录下的 .claude/skills。
    默认读取 .env 创建真实模型；传入 model 时不初始化真实 SDK。
    """
    if skills_dir is None:
        skills_dir = Path.cwd() / ".claude" / "skills"
    registry = SkillRegistry(skills_dir)
    selected_model = model if model is not None else ModelClient()
    return WritingAgent(registry=registry, model=selected_model)
