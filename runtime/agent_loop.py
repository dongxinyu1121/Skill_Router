import json
from typing import Dict, List

from core.llms import LLMClient
from skill_core import SkillRegistry

from .base import AgentBase

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


def colored_prompt() -> str:
    """返回带颜色的命令行用户输入提示符。"""
    return f"{CYAN}{BOLD}You > {RESET}"


def print_assistant(text: str) -> None:
    """用统一格式打印模型最终回复。"""
    print(f"\n{GREEN}{BOLD}Assistant:{RESET} {text}\n")


def print_info(text: str) -> None:
    """用弱化颜色打印调试和流程信息。"""
    print(f"{DIM}{text}{RESET}")


class AgentLoop(AgentBase):
    """Interactive LLM-backed agent loop."""

    def __init__(self, skill_registry: SkillRegistry):
        """创建真实交互 Agent，并绑定 LLM 客户端。"""
        super().__init__(skill_registry)
        self.llm_client = LLMClient()

    def _model_inference(self, messages: List[Dict]) -> dict:
        """把当前对话、系统提示词和工具 schema 发送给模型。"""
        return self.llm_client.inference(
            messages=messages,
            system_prompt=self._build_system_prompt(),
            tool_schema=self._get_tool_schema(),
        )

    def _execute_tools(self, tool_calls: list[dict]) -> list[dict]:
        """执行模型请求的工具调用，并把工具结果转成 messages。"""
        tool_messages: list[dict] = []
        for tool_call in tool_calls:
            func_name = tool_call["function_name"]
            arguments = tool_call["arguments"]
            tool_call_id = tool_call["tool_call_id"]

            if func_name.upper() == "SKILL":
                print_info("\n" + "=" * 80)
                print_info("Step 2: 模型基于用户输入加载匹配到的技能（Skill）【Level 2】")
                print_info("=" * 80)

                tool_result = self.tools["Skill"].execute(**arguments)
                tool_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(tool_result)})

                if tool_result["status"] == "succeed":
                    self._set_skill_context(
                        {
                            "skill_name": tool_result["command_name"],
                            "base_path": tool_result["base_path"],
                            "skill_content": tool_result["content"],
                        }
                    )
                    print_info("调用SKILL:")
                    print_info(f"技能名称: {tool_result['command_name']}")
                    print_info(f"Base Path: {tool_result['base_path']}")
                    print_info(f"内容长度: {len(tool_result['content'])} 字符")
                    print_info("\n【SKILL.md 内容（已注入上下文）】")
                    content = tool_result["content"]
                    print_info(content[:500] + "..." if len(content) > 500 else content)
                    self._attach_read_file_tool()
                continue

            if self._in_skill_context():
                print_info("\n" + "=" * 80)
                print_info(f"Step 3: 执行{self.agent_context['skill_context']['skill_name']}工具的资源或者脚本【Level 3】")
                print_info("=" * 80)

            print_info(f"调用工具: {func_name}")
            print_info(f"参数: {arguments}")
            print_info(f"调用ID: {tool_call_id}")
            tool = self.tools[func_name]
            tool.set_context(self.agent_context)
            tool_result = tool.execute(**arguments)
            print_info(f"工具结果: {tool_result}")
            tool_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(tool_result)})
        return tool_messages

    def run(self) -> None:
        """启动命令行交互循环，直到用户输入退出命令。"""
        print_info("\n" + "=" * 80)
        print_info("Step 1: 启动加载SKILL元数据【Level 1】")
        print_info("=" * 80)
        system_prompt = self._build_system_prompt()
        print_info(f"system_prompt:\n{system_prompt}")
        print_info(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        messages: list[dict] = []
        while True:
            try:
                user_input = input(colored_prompt()).strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{DIM}再见.{RESET}")
                break

            if not user_input:
                continue
            if user_input.lower() in ("quit", "exit", "buy"):
                print(f"{DIM}再见.{RESET}")
                break

            self._reset_agent_context()
            print_info("=" * 80)
            print_info(f"用户输入: {user_input}")
            print_info("=" * 80)
            messages.append({"role": "user", "content": user_input})

            while True:
                llm_response = self._model_inference(messages)
                print("=" * 80 + ">")
                try:
                    print_info(f"LLM result:\n{json.dumps(llm_response, ensure_ascii=False, indent=4)}")
                except Exception:
                    print_info(f"LLM result: {llm_response}")
                print("<" + "=" * 80)

                if llm_response["status"] == "failed":
                    print_info(f"\n{YELLOW}API Error: {llm_response['error_message']}{RESET}\n")
                    while messages and messages[-1]["role"] != "user":
                        messages.pop()
                    if messages:
                        messages.pop()
                    break

                content = llm_response["content"]
                messages.append({"role": "assistant", "content": content})

                if llm_response["stop_reason"] == "tool_calls":
                    messages.extend(self._execute_tools(llm_response["tools"]))
                    continue

                if llm_response["stop_reason"] == "stop":
                    if content:
                        print_assistant(content)
                    break

                print_info(f"[stop_reason={llm_response['stop_reason']}]")
                if content:
                    print_assistant(content)
                break
