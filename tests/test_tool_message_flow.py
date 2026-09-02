import builtins
import unittest

from runtime.agent_loop import AgentLoop


class TestToolMessageFlow(unittest.TestCase):
    def test_tool_result_follows_assistant_tool_call(self):
        captured_messages = []
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

        agent = object.__new__(AgentLoop)
        agent.agent_context = {}
        agent.tools = {}
        agent._build_system_prompt = lambda: "system"
        agent._reset_agent_context = lambda: None
        agent._model_inference = lambda messages: (
            captured_messages.append([dict(message) for message in messages])
            or next(responses)
        )
        agent._execute_tools = lambda tool_calls: [
            {"role": "tool", "tool_call_id": "call_1", "content": "工具结果"}
        ]

        original_input = builtins.input
        inputs = iter(["测试输入", "quit"])
        builtins.input = lambda prompt="": next(inputs)
        try:
            agent.run()
        finally:
            builtins.input = original_input

        self.assertEqual(len(captured_messages), 2)
        second_request = captured_messages[1]
        self.assertEqual(second_request[1]["role"], "assistant")
        self.assertIn("tool_calls", second_request[1])
        self.assertEqual(second_request[2]["role"], "tool")
        self.assertEqual(second_request[2]["tool_call_id"], "call_1")


if __name__ == "__main__":
    unittest.main()
