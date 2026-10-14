"""封装模型请求，将第三方 SDK 响应转换为 Agent 使用的数据结构。

本模块只请求模型并解析响应，不执行模型提出的工具调用。
"""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from .settings import load_model_settings


@dataclass
class ToolCall:
    """模型提出的一次工具调用。

    name 和 arguments 供程序执行工具，call_id 用来把工具结果与本次调用
    对应起来，raw 保存写回对话历史所需的 OpenAI 兼容结构。
    """

    name: str
    arguments: Dict[str, Any]
    call_id: str
    raw: Dict[str, Any]


@dataclass
class ModelResponse:
    """一次模型请求的标准化结果，屏蔽第三方 SDK 对象的具体结构。"""

    status: str
    content: Optional[str] = None
    stop_reason: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    error: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        """请求成功时返回 True。"""
        return self.status == "succeed"

    @property
    def requests_tools(self) -> bool:
        """模型要求执行工具时返回 True。"""
        return self.stop_reason == "tool_calls"


class Model(Protocol):
    """Agent 对模型的唯一要求：接收消息、规则和工具描述，返回标准响应。

    真实的 ModelClient 和测试中的 FakeModel 都遵守这个接口；Agent 不需要
    知道请求来自网络还是预设数据。Protocol 只描述约定，不增加运行层级。
    """

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tool_schema: List[Dict[str, Any]],
    ) -> ModelResponse:
        """完成一次模型推理，或返回带错误说明的失败响应。"""
        ...


class ModelClient:
    """通过 OpenAI 兼容接口完成单次推理，并保留工具调用的关联信息。"""

    def __init__(self):
        """读取连接配置，创建 SDK 客户端并保存后续请求使用的模型名。"""
        # 延迟导入第三方 SDK：路由数据校验和假模型测试无需安装或初始化它。
        from openai import OpenAI

        settings = load_model_settings()
        self.client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )
        self.model_name = settings["model_name"]

    def generate(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str,
        tool_schema: List[Dict[str, Any]],
    ) -> ModelResponse:
        """发送一次模型请求，返回文本、结束原因及可能存在的工具调用。

        参数：
            messages：已有对话，包含用户、助手和工具消息。
            system_prompt：当前系统提示词，由运行层注入技能目录信息。
            tool_schema：可用工具的名称、描述和参数结构。

        请求失败时返回带错误说明的 ModelResponse；若模型要求调用工具，
        每个 ToolCall 会同时保留可执行参数与可写回消息历史的原始结构。
        """
        try:
            # 系统提示词放在对话最前面；auto 允许模型自行决定是否调用工具。
            response = self.client.chat.completions.create(
                model=self.model_name,
                temperature=0.8,
                tools=tool_schema,
                messages=[
                    {"role": "system", "content": system_prompt},
                    *messages
                ],
                tool_choice="auto"
            )
            return self._parse_response(response)
        except Exception as exc:
            # 请求异常和不合法的工具参数都转成失败结果，交给 Agent 撤回本轮历史。
            return ModelResponse(status="failed", error=str(exc))

    @staticmethod
    def _parse_response(response: Any) -> ModelResponse:
        """解析第一条候选回复，并同时保留工具的执行参数与原始调用记录。"""
        if not getattr(response, "choices", None):
            raise ValueError("模型响应缺少候选回复 choices")

        # 当前只处理第一条候选回复；content 在工具调用时可能为空。
        choice = response.choices[0]
        parsed = ModelResponse(
            status="succeed",
            content=choice.message.content,
            stop_reason=choice.finish_reason,
        )

        if choice.finish_reason == "tool_calls":
            if not choice.message.tool_calls:
                raise ValueError("模型要求执行工具，但没有提供工具调用记录")
            for tool_call in choice.message.tool_calls:
                # 工具参数由模型以 JSON 字符串返回，执行前转换为字典。
                arguments = json.loads(tool_call.function.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("工具参数必须是 JSON 对象")
                raw = {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                parsed.tool_calls.append(
                    ToolCall(
                        name=tool_call.function.name,
                        arguments=arguments,
                        call_id=tool_call.id,
                        raw=raw,
                    )
                )

        return parsed
