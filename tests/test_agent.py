"""通过固定响应的假模型解释并验证 Agent 的完整执行流程。

测试不访问网络，也不依赖真实模型的随机输出。每条预设响应代表模型在某一步
作出的决定，captures 则记录 Agent 实际发送给模型的消息和工具列表。
"""

import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import List

from agent import SkillRegistry, WritingAgent
from agent.model import ModelResponse, ToolCall


def tool_response(name: str, arguments: dict, call_id: str) -> ModelResponse:
    """构造一次确定的工具调用响应，代替真实模型生成的不稳定结果。"""
    argument_json = json.dumps(arguments, ensure_ascii=False)
    raw = {
        "id": call_id,
        "type": "function",
        "function": {"name": name, "arguments": argument_json},
    }
    return ModelResponse(
        status="succeed",
        content="",
        stop_reason="tool_calls",
        tool_calls=[
            ToolCall(
                name=name,
                arguments=arguments,
                call_id=call_id,
                raw=raw,
            )
        ],
    )


class FakeModel:
    """按顺序返回预设响应，同时保存每次收到的消息和工具描述。"""

    def __init__(self, responses: List[ModelResponse]):
        self.responses = iter(responses)
        self.calls = []

    def generate(self, messages, system_prompt, tool_schema):
        """记录请求快照，避免后续历史追加改变已经保存的测试证据。"""
        self.calls.append(
            {
                "messages": deepcopy(messages),
                "system_prompt": system_prompt,
                "tool_schema": deepcopy(tool_schema),
            }
        )
        return next(self.responses)


class WritingAgentTest(unittest.TestCase):
    """验证公开接口可观察到的行为，不依赖 Agent 内部私有方法。"""

    def setUp(self):
        """为每个测试创建一个包含引用文件的最小临时技能。"""
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        skill_dir = root / "skills" / "outline-expander"
        reference_dir = skill_dir / "references"
        reference_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(
            "---\n"
            "name: outline-expander\n"
            "description: 帮助作者确定下一段的写作方向。\n"
            "---\n\n"
            "先读取 references/guide.md，再给出下一段建议。\n",
            encoding="utf-8",
        )
        (reference_dir / "guide.md").write_text(
            "先总结当前段落，再补充一个具体例子。",
            encoding="utf-8",
        )
        self.registry = SkillRegistry(root / "skills")

    def tearDown(self):
        """删除测试创建的临时技能目录。"""
        self.temp_dir.cleanup()

    def test_skill_and_reference_flow(self):
        """解释主流程：选择技能、读取引用文件、最后生成回答。

        第二次模型请求必须看到 Skill 工具结果和新增的 ReadFile；第三次请求
        必须再看到 ReadFile 结果。这正是渐进式披露的二、三级加载过程。
        """
        model = FakeModel(
            [
                tool_response("Skill", {"command": "outline-expander"}, "call_skill"),
                tool_response(
                    "ReadFile",
                    {"file_path": "references/guide.md"},
                    "call_file",
                ),
                ModelResponse(
                    status="succeed",
                    content="下一段可以先总结观点，再加入具体例子。",
                    stop_reason="stop",
                ),
            ]
        )
        agent = WritingAgent(self.registry, model)

        result = agent.run("我不知道下一段怎么写")

        self.assertEqual(result.error, None)
        self.assertIn("下一段", result.answer)
        self.assertEqual(len(model.calls), 3)

        first_call = model.calls[0]
        first_tools = [item["function"]["name"] for item in first_call["tool_schema"]]
        self.assertEqual(first_tools, ["Skill", "Bash"])
        self.assertIn("outline-expander", first_call["system_prompt"])
        self.assertNotIn("先读取 references/guide.md", first_call["system_prompt"])

        second_call = model.calls[1]
        self.assertEqual(
            [message["role"] for message in second_call["messages"]],
            ["user", "assistant", "tool"],
        )
        second_tools = [item["function"]["name"] for item in second_call["tool_schema"]]
        self.assertIn("ReadFile", second_tools)

        third_messages = model.calls[2]["messages"]
        self.assertEqual(third_messages[-1]["role"], "tool")
        self.assertIn("先总结当前段落", third_messages[-1]["content"])
        self.assertEqual(third_messages[-1]["tool_call_id"], "call_file")

    def test_history_is_preserved_across_user_turns(self):
        """两次 run 共用历史，使第二次模型请求能看到第一次问答。"""
        model = FakeModel(
            [
                ModelResponse(status="succeed", content="第一轮回答", stop_reason="stop"),
                ModelResponse(status="succeed", content="第二轮回答", stop_reason="stop"),
            ]
        )
        agent = WritingAgent(self.registry, model)

        agent.run("第一轮问题")
        agent.run("第二轮问题")

        roles = [message["role"] for message in model.calls[1]["messages"]]
        self.assertEqual(roles, ["user", "assistant", "user"])
        self.assertEqual(model.calls[1]["messages"][1]["content"], "第一轮回答")

    def test_route_always_uses_initial_tools(self):
        """即使完整任务已开放 ReadFile，独立路由评测仍只使用初始工具。"""
        model = FakeModel(
            [
                tool_response("Skill", {"command": "outline-expander"}, "call_skill"),
                ModelResponse(status="succeed", content="完成", stop_reason="stop"),
                tool_response("Skill", {"command": "outline-expander"}, "call_route"),
            ]
        )
        agent = WritingAgent(self.registry, model)

        agent.run("先完成一个正式任务")
        agent.route("再做一次独立路由评测")

        run_tools = [item["function"]["name"] for item in model.calls[1]["tool_schema"]]
        route_tools = [item["function"]["name"] for item in model.calls[2]["tool_schema"]]
        self.assertIn("ReadFile", run_tools)
        self.assertEqual(route_tools, ["Skill", "Bash"])

    def test_route_is_public_and_does_not_change_history(self):
        """路由评测只取第一轮技能选择，不执行工具或污染正式历史。"""
        model = FakeModel(
            [
                tool_response("Skill", {"command": "outline-expander"}, "call_route"),
                ModelResponse(status="succeed", content="正式回答", stop_reason="stop"),
            ]
        )
        agent = WritingAgent(self.registry, model)

        route = agent.route("后面不知道怎么展开")
        result = agent.run("正式问题")

        self.assertEqual(route.selected_skills, ["outline-expander"])
        self.assertEqual(result.answer, "正式回答")
        self.assertEqual(model.calls[1]["messages"], [{"role": "user", "content": "正式问题"}])

    def test_failed_request_rolls_back_current_turn(self):
        """模型失败时撤回当前用户消息，避免错误回合残留在历史中。"""
        model = FakeModel(
            [
                ModelResponse(status="failed", error="测试错误"),
                ModelResponse(status="succeed", content="恢复成功", stop_reason="stop"),
            ]
        )
        agent = WritingAgent(self.registry, model)

        result = agent.run("这条消息会失败")
        recovery = agent.run("下一条消息")

        self.assertEqual(result.error, "测试错误")
        self.assertEqual(recovery.answer, "恢复成功")
        self.assertEqual(
            model.calls[1]["messages"],
            [{"role": "user", "content": "下一条消息"}],
        )


if __name__ == "__main__":
    unittest.main()
