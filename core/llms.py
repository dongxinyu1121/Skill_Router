import json

from openai import OpenAI

from .config import load_llm_settings


class LLMClient(object):

    def __init__(self):
        settings = load_llm_settings()
        self.client = OpenAI(
            api_key=settings["api_key"],
            base_url=settings["base_url"],
        )
        self.model_name = settings["model_name"]

    def inference(self, messages, system_prompt, tool_schema):
        try:
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
            error_msg = str(exc)
            response = None

        parsed_response = {}
        if response:
            content = response.choices[0].message.content
            stop_reason = response.choices[0].finish_reason
            parsed_response["status"] = "succeed"
            parsed_response["content"] = content
            parsed_response["stop_reason"] = stop_reason
            if stop_reason == "tool_calls":
                tool_list = []
                tool_calls = response.choices[0].message.tool_calls
                for tool_call in tool_calls:
                    tool_list.append({
                        "function_name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments),
                        "tool_call_id": tool_call.id,
                    })
                parsed_response["tools"] = tool_list
        else:
            parsed_response["status"] = "failed"
            parsed_response["error_message"] = error_msg

        return parsed_response
