"""封装模型请求，将模型 SDK 的响应转换为运行层使用的字典。

本模块只请求模型并解析响应，不执行模型提出的工具调用。
"""

import json

from openai import OpenAI

from .config import load_llm_settings


class LLMClient(object):
    """通过 OpenAI 兼容接口完成单次推理，并保留工具调用的关联信息。"""

    def __init__(self):
        """读取连接配置，创建 SDK 客户端并保存后续请求使用的模型名。"""
        settings = load_llm_settings()
        self.client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )
        self.model_name = settings["model_name"]

    def inference(self, messages, system_prompt, tool_schema):
        """发送一次模型请求，返回文本、结束原因及可能存在的工具调用。

        参数：
            messages：已有对话，包含用户、助手和工具消息。
            system_prompt：当前系统提示词，由运行层注入技能目录信息。
            tool_schema：可用工具的名称、描述和参数结构。

        请求失败时返回 status='failed' 和 error_message；成功时返回
        content 与 stop_reason。若模型要求调用工具，还会返回两份记录：
        tools 的参数是字典，供程序执行；assistant_tool_calls 保留参数
        JSON 字符串，供运行层按接口要求写回对话历史。
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
            error_msg = None
        except Exception as exc:
            # 将模型请求异常交给上层处理，不在这里直接退出交互循环。
            error_msg = str(exc)
            response = None

        parsed_response = {}
        if response:
            if not hasattr(response, "choices"):
                return {
                    "status": "failed",
                    "error_message": "Unexpected LLM response type: %s. Raw response: %s"
                    % (type(response).__name__, response),
                }
            # 当前只处理第一条候选回复；content 在工具调用时可能为空。
            content = response.choices[0].message.content
            stop_reason = response.choices[0].finish_reason
            parsed_response["status"] = "succeed"
            parsed_response["content"] = content
            parsed_response["stop_reason"] = stop_reason
            if stop_reason == "tool_calls":
                tool_list = []
                assistant_tool_calls = []
                tool_calls = response.choices[0].message.tool_calls
                for tool_call in tool_calls:
                    # 工具参数由模型以 JSON 字符串返回，执行前转换为字典。
                    # 此处的 JSON 解析在上面的请求异常捕获范围之外。
                    tool_list.append({
                        "function_name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                        "tool_call_id": tool_call.id,
                    })
                    # 原始调用结构也要保存，才能让后续工具结果与调用 ID 对应。
                    assistant_tool_calls.append({
                        "id": tool_call.id,
                        "type": "function",
                        "function": {
                            "name": tool_call.function.name,
                            "arguments": tool_call.function.arguments,
                        },
                    })
                parsed_response["tools"] = tool_list
                parsed_response["assistant_tool_calls"] = assistant_tool_calls
        else:
            parsed_response["status"] = "failed"
            parsed_response["error_message"] = error_msg

        return parsed_response
