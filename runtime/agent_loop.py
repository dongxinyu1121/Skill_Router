"""交互式智能体主流程：用户输入 → 模型请求 → 工具执行 → 模型继续回复。

外层循环管理多次用户输入，内层循环完成一次用户任务中的多轮工具调用。
模型请求由 core.llms 完成，实际工具能力来自 toolkit。
"""

import json
from typing import Dict, List

from core.llms import LLMClient
from skill_core import SkillRegistry

from .base import AgentBase

# 终端颜色转义序列只影响显示，不参与模型推理或工具参数解析。
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


def colored_prompt() -> str:
    """生成用户输入前显示的彩色提示符，供 input 函数使用。"""
    return f"{CYAN}{BOLD}You > {RESET}"


def print_assistant(text: str) -> None:
    """在终端显示模型最终文本，使用颜色将其与调试日志区分开。"""
    print(f"\n{GREEN}{BOLD}Assistant:{RESET} {text}\n")


def print_info(text: str) -> None:
    """打印用于观察提示词、工具参数和响应的调试日志，不追加到对话历史。"""
    print(f"{DIM}{text}{RESET}")


class AgentLoop(AgentBase):
    """使用真实模型的终端交互循环，协调消息、工具和当前技能状态。"""

    def __init__(self, skill_registry: SkillRegistry):
        """先初始化公共工具与状态，再创建读取本地配置的模型客户端。"""
        super().__init__(skill_registry)
        self.llm_client = LLMClient()

    def _model_inference(self, messages: List[Dict]) -> dict:
        """提交现有对话、系统提示词及当前工具描述，返回一次模型响应。

        messages 包含前面回合的历史和本回合的工具结果。
        每次都获取最新工具描述，以便模型看到加载技能后新增的 ReadFile。
        """
        return self.llm_client.inference(
            messages=messages,
            system_prompt=self._build_system_prompt(),
            tool_schema=self._get_tool_schema(),
        )

    def _execute_tools(self, tool_calls: List[Dict]) -> List[Dict]:
        """按返回顺序执行工具，将每个结果包装成可追加到对话的工具消息。

        输入工具记录包含名称、参数字典和调用 ID；每条结果必须携带对应
        tool_call_id，模型才能知道它回答的是哪一次调用。
        Skill 需要额外更新上下文并注册读文件工具，因此在这里单独处理。
        """
        tool_messages: List[Dict] = []
        for tool_call in tool_calls:
            func_name = tool_call["function_name"]
            arguments = tool_call["arguments"]
            tool_call_id = tool_call["tool_call_id"]

            # 第二级披露：模型选中技能后，才把完整指令放进工具结果。
            if func_name.upper() == "SKILL":
                print_info("\n" + "=" * 80)
                print_info("Step 2: 模型基于用户输入加载匹配到的技能（Skill）【Level 2】")
                print_info("=" * 80)

                # **arguments 将参数字典展开，例如 {"command": "outline-expander"}。
                tool_result = self.tools["Skill"].execute(**arguments)
                tool_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(tool_result)})

                if tool_result["status"] == "succeed":
                    # 当前只记录最后一个成功加载的技能；后续调用会覆盖此状态。
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
                    # 这里只截断终端预览，前面的工具消息已经包含完整正文。
                    print_info(content[:500] + "..." if len(content) > 500 else content)
                    self._attach_read_file_tool()
                continue

            # 普通工具统一分发。处于技能上下文时打印第三级资源执行的提示，
            # 但工具是否真的使用某个技能资源，取决于它的参数和具体实现。
            if self._in_skill_context():
                print_info("\n" + "=" * 80)
                print_info(f"Step 3: 执行{self.agent_context['skill_context']['skill_name']}工具的资源或者脚本【Level 3】")
                print_info("=" * 80)

            print_info(f"调用工具: {func_name}")
            print_info(f"参数: {arguments}")
            print_info(f"调用ID: {tool_call_id}")
            tool = self.tools[func_name]
            # 执行前传入本回合最新状态，避免工具只持有之前回合的字典引用。
            tool.set_context(self.agent_context)
            tool_result = tool.execute(**arguments)
            print_info(f"工具结果: {tool_result}")
            tool_messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": str(tool_result)})
        return tool_messages

    def run(self) -> None:
        """持续接收用户输入，并完成每次任务所需的模型与工具往返。

        外层循环：接收用户消息、处理空输入与退出、重置临时技能状态。
        内层循环：请求模型；若要求工具调用，则追加调用和结果后再次请求；
        若返回最终文本，则结束本回合，继续等待下一条用户消息。
        messages 在外层循环之前创建，因此历史会跨用户回合保留。
        """
        print_info("\n" + "=" * 80)
        print_info("Step 1: 启动加载SKILL元数据【Level 1】")
        print_info("=" * 80)
        system_prompt = self._build_system_prompt()
        print_info(f"system_prompt:\n{system_prompt}")
        # 日志实际统计的是字符数，不是模型分词后的真实令牌数。
        print_info(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        messages: List[Dict] = []
        while True:
            # 外层循环负责终端交互；Ctrl+C 或输入流结束时正常退出。
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

            # 保留历史对话，只清除本回合之前激活的技能状态。
            self._reset_agent_context()
            print_info("=" * 80)
            print_info(f"用户输入: {user_input}")
            print_info("=" * 80)
            messages.append({"role": "user", "content": user_input})

            while True:
                # 内层每次请求都带上最新消息，使模型能够继续处理工具结果。
                llm_response = self._model_inference(messages)
                print("=" * 80 + ">")
                try:
                    print_info(f"LLM result:\n{json.dumps(llm_response, ensure_ascii=False, indent=4)}")
                except Exception:
                    print_info(f"LLM result: {llm_response}")
                print("<" + "=" * 80)

                if llm_response["status"] == "failed":
                    print_info(f"\n{YELLOW}API Error: {llm_response['error_message']}{RESET}\n")
                    # 撤回本次用户消息及其后追加的调用和结果，保留此前成功历史。
                    # 这里只处理客户端以 failed 状态返回的请求错误。
                    while messages and messages[-1]["role"] != "user":
                        messages.pop()
                    if messages:
                        messages.pop()
                    break

                content = llm_response["content"]

                if llm_response["stop_reason"] == "tool_calls":
                    # 必须先记录助手提出的调用，再追加对应工具结果。
                    # 只有工具消息而没有前面的调用记录，会破坏接口要求的消息顺序。
                    messages.append(
                        {
                            "role": "assistant",
                            "content": content,
                            "tool_calls": llm_response["assistant_tool_calls"],
                        }
                    )
                    messages.extend(self._execute_tools(llm_response["tools"]))
                    # 工具调用并不是最终回答；继续请求模型，让它读取结果再作决定。
                    continue

                messages.append({"role": "assistant", "content": content})

                if llm_response["stop_reason"] == "stop":
                    # 模型正常结束，本回合完成，但外层交互循环仍继续运行。
                    if content:
                        print_assistant(content)
                    break

                # 对长度限制等其他结束原因，也显示已返回文本并结束本回合。
                print_info(f"[stop_reason={llm_response['stop_reason']}]")
                if content:
                    print_assistant(content)
                break
