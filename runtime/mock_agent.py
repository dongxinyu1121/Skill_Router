import json
import re
from pathlib import Path
from typing import Any, Dict, Optional

from skill_core import SkillRegistry
from toolkit import ReadFileTool

from .base import AgentBase


class MockAgent(AgentBase):
    """Deterministic demo agent for the progressive disclosure flow."""

    def __init__(self, registry: SkillRegistry):
        super().__init__(registry)
        self.context: Dict[str, Any] = {}

    def _parse_model_output(self, output: str) -> Optional[Dict]:
        json_match = re.search(r"```json\s*(\{.*?\})\s*```", output, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        if "Skill" in output and "code-reviewer" in output:
            return {"tool": "Skill", "params": {"command": "code-reviewer"}}
        if "git diff" in output:
            return {"tool": "Bash", "params": {"command": "git diff", "description": "获取代码变更"}}
        if "ReadFile" in output and "style-guide" in output:
            return {"tool": "ReadFile", "params": {"file_path": "references/style-guide.md"}}
        if "lint.sh" in output:
            return {"tool": "Bash", "params": {"command": "bash scripts/lint.sh", "description": "运行代码检查"}}
        return None

    def _model_inference(self, user_input: str, available_info: str = "") -> str:
        triggers = ["review", "审查", "检查代码", "看看这段代码"]
        if any(t in user_input.lower() for t in triggers):
            return f"""
[模型思考过程]
用户输入: "{user_input}"
检查 Skills Registry:
- 匹配到 **code-reviewer**: "在代码提交前进行审查，检查潜在bug...当用户提到'review'、'审查代码'...时触发"
→ 意图匹配！需要调用 Skill 工具加载完整指令。

[工具调用]
```json
{{
  "tool": "Skill",
  "params": {{"command": "code-reviewer"}}
}}
```
"""
        return f"[模型思考] 未匹配到特定 Skill，直接回应用户: {user_input}"

    def run(self, user_input: str) -> None:
        print("=" * 80)
        print(f"用户输入: {user_input}")
        print("=" * 80)

        print("\n" + "=" * 80)
        print("Step 1: 启动加载 SKILL.md中的元数据【Level 1】")
        print("=" * 80)
        system_prompt = self._build_system_prompt()
        print(self.skill_registry.get_registry_prompt())
        print(f"\n[Token 消耗: 约 {len(system_prompt)} 字符（仅元数据）]")

        print("\n" + "=" * 80)
        print("Step 2: （模拟）模型基于 SKILL.md 元数据判断意图 【Level 2】")
        print("=" * 80)
        reasoning = self._model_inference(user_input)
        print(reasoning)
        tool_call = self._parse_model_output(reasoning)
        if not tool_call or tool_call["tool"] != "Skill":
            print("\n" + "=" * 80)
            print("任务完成")
            print("=" * 80)
            return

        print("\n" + "=" * 80)
        print("Step 3: 如果匹配到技能（Skill），使用Skill工具加载对应技能的Skills.md")
        print("=" * 80)
        skill_tool = self.tools["Skill"]
        result = skill_tool.execute(**tool_call["params"])

        self.context = {
            "skill_name": result["command_name"],
            "base_path": result["base_path"],
            "skill_content": result["content"],
        }

        print(f"技能名称: {result['command_name']}")
        print(f"Base Path: {result['base_path']}")
        print(f"内容长度: {len(result['content'])} 字符")
        print("\n【SKILL.md 内容（已注入上下文）】")
        print(result["content"][:500] + "..." if len(result["content"]) > 500 else result["content"])

        readfile_tool = ReadFileTool()
        readfile_tool.set_context(self.context)
        self._register_tool(readfile_tool)

        print("\n" + "=" * 80)
        print("Step 4: 按 Skill 指令执行【Level 3】")
        print("=" * 80)

        execution_steps = [
            ("Bash", {"command": "git diff", "description": "获取代码变更"}),
            ("ReadFile", {"file_path": "references/style-guide.md"}),
            ("Bash", {"command": "scripts/lint.sh"}),
        ]

        for i, (tool_name, params) in enumerate(execution_steps, 1):
            print(f"\n执行步骤 {i}: {tool_name}({params})")
            if tool_name == "ReadFile":
                full_path = Path(self.context["base_path"]) / params["file_path"]
                print(f"  相对路径 '{params['file_path']}' 解析为: {full_path}")

            tool = self.tools.get(tool_name)
            if not tool:
                continue
            result = tool.execute(**params)
            if result["status"] == "succeed":
                content = result.get("content", result.get("stdout", ""))
                preview = content[:200] + "..." if len(content) > 200 else content
                print(f"  结果: {preview}")
            else:
                print(f"  错误: {result.get('message', '')}")

        print("\n" + "=" * 80)
        print("任务完成")
        print("=" * 80)
        print("\n【披露层级总结】")
        print("Level 1: 始终保留 - Skills Registry (仅元数据)")
        print("Level 2: 触发加载 - SKILL.md 完整内容（一次性)")
        print("Level 3: 按需加载 - references/, scripts/ 等资源（执行时动态）")
