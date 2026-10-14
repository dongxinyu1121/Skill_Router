"""用预设模型响应验证工具调用的消息顺序，不连接真实模型或执行真实工具。"""

import builtins
import unittest

from runtime.agent_loop import AgentLoop


class TestToolMessageFlow(unittest.TestCase):
    """检查运行循环是否先记录助手的工具调用，再记录对应工具结果。"""

    def test_tool_result_follows_assistant_tool_call(self):
        """模拟一次工具调用与最终回复，检查第二次模型请求所收到的消息。

        正确顺序为：用户消息 → 助手工具调用 → 工具结果。
        工具结果的调用 ID 必须与助手提出的调用一致。
        """
        captured_messages = []
        # 两次模型请求分别返回工具调用和最终文本，隔离外部接口的不确定性。
        responses = iter(
            [
                {
                    "status": "succeed",
                    "content": "",
                    "stop_reason": "tool_calls",
                    "tools": [
                        {
                            "function_name": "Skill",
                            "arguments": {"command": "outline-expander"},
                            "tool_call_id": "call_1",
                        }
                    ],
                    "assistant_tool_calls": [
                        {
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "Skill",
                                "arguments": '{"command":"outline-expander"}',
                            },
                        }
                    ],
                },
                {
                    "status": "succeed",
                    "content": "最终答案",
                    "stop_reason": "stop",
                },
            ]
        )

        # 跳过构造函数，避免初始化真实模型客户端和读取模型配置。
        agent = object.__new__(AgentLoop)
        agent.agent_context = {}
        agent.tools = {}
        agent._build_system_prompt = lambda: "system"
        agent._reset_agent_context = lambda: None
        # 保存消息快照，再返回下一条预设响应；复制列表以避免后续追加影响断言。
        agent._model_inference = lambda messages: (
            captured_messages.append([dict(message) for message in messages])
            or next(responses)
        )
        agent._execute_tools = lambda tool_calls: [
            {"role": "tool", "tool_call_id": "call_1", "content": "工具结果"}
        ]

        # 用预设输入驱动交互循环：先提交任务，再退出。
        original_input = builtins.input
        inputs = iter(["测试输入", "quit"])
        builtins.input = lambda prompt="": next(inputs)
        try:
            agent.run()
        finally:
            # 无论测试成功还是异常，都恢复全局输入函数，避免影响其他测试。
            builtins.input = original_input

        # 第二次请求应包含前一次的助手调用记录及其对应工具结果。
        self.assertEqual(len(captured_messages), 2)
        second_request = captured_messages[1]
        self.assertEqual(second_request[1]["role"], "assistant")
        self.assertIn("tool_calls", second_request[1])
        self.assertEqual(second_request[2]["role"], "tool")
        self.assertEqual(second_request[2]["tool_call_id"], "call_1")


if __name__ == "__main__":
    unittest.main()
