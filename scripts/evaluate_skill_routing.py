import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.llms import LLMClient
from runtime.base import AgentBase
from skill_core import SkillRegistry


DEFAULT_INPUT = ROOT / "data" / "skill_routing_eval.json"
DEFAULT_OUTPUT = ROOT / "data" / "skill_routing_eval_results.json"
SKILL_TOOL_NAME = "skill"


def load_cases(input_path: Path) -> List[Dict[str, Any]]:
    """读取人工标注的路由评测数据。"""
    return json.loads(input_path.read_text(encoding="utf-8"))


def validate_cases(cases: List[Dict[str, Any]], registered_skills: Set[str]) -> None:
    """校验评测样本字段、ID 和 Skill 名称。"""
    required_fields = {
        "id",
        "query",
        "expected_skills",
        "acceptable_skills",
        "bad_skills",
    }
    seen_ids: Set[str] = set()
    unknown_skills: Set[str] = set()

    for index, case in enumerate(cases, start=1):
        missing = required_fields - set(case)
        if missing:
            raise ValueError("case #%s missing fields: %s" % (index, sorted(missing)))

        case_id = case["id"]
        if case_id in seen_ids:
            raise ValueError("duplicate case id: %s" % case_id)
        seen_ids.add(case_id)

        for key in ("expected_skills", "acceptable_skills", "bad_skills"):
            value = case[key]
            if not isinstance(value, list):
                raise ValueError("%s.%s must be a list" % (case_id, key))
            unknown_skills.update(set(value) - registered_skills)

    if unknown_skills:
        raise ValueError("unknown skills in eval data: %s" % sorted(unknown_skills))


def extract_skill_commands(llm_response: Dict[str, Any]) -> List[str]:
    """从第一轮模型响应中提取 Skill 工具选择结果。"""
    commands: List[str] = []
    for tool_call in llm_response.get("tools", []):
        function_name = tool_call.get("function_name", "")
        if function_name.lower() != SKILL_TOOL_NAME:
            continue
        arguments = tool_call.get("arguments", {})
        command = arguments.get("command")
        if command:
            commands.append(command)
    return commands


def score_case(case: Dict[str, Any], actual_skills: List[str]) -> Dict[str, Any]:
    """计算单条样本的路由命中情况。"""
    expected = set(case["expected_skills"])
    acceptable = set(case["acceptable_skills"])
    bad = set(case["bad_skills"])
    top3 = actual_skills[:3]

    strict_top1 = bool(actual_skills) and actual_skills[0] in expected
    strict_top3 = bool(expected.intersection(top3))
    acceptable_hit = bool((expected | acceptable).intersection(actual_skills))
    bad_skill_called = bool(bad.intersection(actual_skills))

    return {
        "strict_top1": strict_top1,
        "strict_top3": strict_top3,
        "acceptable_hit": acceptable_hit,
        "bad_skill_called": bad_skill_called,
    }


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """汇总整体评测指标。"""
    total = len(results)
    if total == 0:
        return {
            "total": 0,
            "success": 0,
            "failed": 0,
            "strict_top1_accuracy": 0.0,
            "strict_top3_accuracy": 0.0,
            "acceptable_hit_rate": 0.0,
            "bad_skill_call_rate": 0.0,
            "avg_skill_calls": 0.0,
        }

    def ratio(count: int) -> float:
        return round(count / total, 4)

    success = sum(1 for item in results if item["status"] == "succeed")
    failed = total - success
    strict_top1 = sum(1 for item in results if item["metrics"]["strict_top1"])
    strict_top3 = sum(1 for item in results if item["metrics"]["strict_top3"])
    acceptable_hit = sum(1 for item in results if item["metrics"]["acceptable_hit"])
    bad_skill_called = sum(1 for item in results if item["metrics"]["bad_skill_called"])
    skill_call_count = sum(len(item["actual_skills"]) for item in results)

    return {
        "total": total,
        "success": success,
        "failed": failed,
        "strict_top1_accuracy": ratio(strict_top1),
        "strict_top3_accuracy": ratio(strict_top3),
        "acceptable_hit_rate": ratio(acceptable_hit),
        "bad_skill_call_rate": ratio(bad_skill_called),
        "avg_skill_calls": round(skill_call_count / total, 2),
    }


def evaluate_case(
    case: Dict[str, Any],
    llm_client: LLMClient,
    system_prompt: str,
    tool_schema: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """对单条样本执行第一轮 Skill 路由评测。"""
    started_at = time.time()
    llm_response = llm_client.inference(
        messages=[{"role": "user", "content": case["query"]}],
        system_prompt=system_prompt,
        tool_schema=tool_schema,
    )
    latency_ms = int((time.time() - started_at) * 1000)

    actual_skills = extract_skill_commands(llm_response)
    metrics = score_case(case, actual_skills)
    result = {
        "id": case["id"],
        "domain": case.get("domain", ""),
        "query": case["query"],
        "expected_skills": case["expected_skills"],
        "acceptable_skills": case["acceptable_skills"],
        "bad_skills": case["bad_skills"],
        "actual_skills": actual_skills,
        "status": llm_response["status"],
        "stop_reason": llm_response.get("stop_reason"),
        "latency_ms": latency_ms,
        "metrics": metrics,
    }
    if llm_response["status"] == "failed":
        result["error_message"] = llm_response.get("error_message", "")
    return result


def print_summary(summary: Dict[str, Any]) -> None:
    """打印便于粘贴到简历素材里的指标摘要。"""
    print("\nSkill routing evaluation summary")
    print("total=%s success=%s failed=%s" % (summary["total"], summary["success"], summary["failed"]))
    print("strict_top1_accuracy=%.2f%%" % (summary["strict_top1_accuracy"] * 100))
    print("strict_top3_accuracy=%.2f%%" % (summary["strict_top3_accuracy"] * 100))
    print("acceptable_hit_rate=%.2f%%" % (summary["acceptable_hit_rate"] * 100))
    print("bad_skill_call_rate=%.2f%%" % (summary["bad_skill_call_rate"] * 100))
    print("avg_skill_calls=%.2f" % summary["avg_skill_calls"])


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="Evaluate Skill Router tool-call accuracy.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="评测数据 JSON 路径")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="评测结果 JSON 路径")
    parser.add_argument("--limit", type=int, default=None, help="只评测前 N 条样本，便于小规模试跑")
    parser.add_argument("--start", type=int, default=0, help="从第 N 条样本开始评测，0 表示第一条")
    parser.add_argument("--sleep", type=float, default=0.0, help="每条样本之间暂停秒数，避免触发限流")
    parser.add_argument("--save-every", type=int, default=10, help="每 N 条保存一次中间结果")
    parser.add_argument("--validate-only", action="store_true", help="只校验数据集，不调用大模型")
    return parser.parse_args()


def main() -> None:
    """运行 Skill 路由评测并保存结果。"""
    args = parse_args()
    registry = SkillRegistry(ROOT / ".claude" / "skills")
    registered_skills = set(registry._skills)
    cases = load_cases(args.input)
    validate_cases(cases, registered_skills)

    selected_cases = cases[args.start :]
    if args.limit is not None:
        selected_cases = selected_cases[: args.limit]

    print("eval_cases=%s registered_skills=%s" % (len(selected_cases), len(registered_skills)))
    if args.validate_only:
        print("validate_only=passed")
        return

    agent_base = AgentBase(registry)
    llm_client = LLMClient()
    system_prompt = agent_base._build_system_prompt()
    tool_schema = agent_base._get_tool_schema()
    results: List[Dict[str, Any]] = []

    for index, case in enumerate(selected_cases, start=1):
        print("[%s/%s] %s" % (index, len(selected_cases), case["id"]))
        result = evaluate_case(case, llm_client, system_prompt, tool_schema)
        results.append(result)
        print(
            "  expected=%s actual=%s top1=%s acceptable=%s bad=%s"
            % (
                result["expected_skills"],
                result["actual_skills"],
                result["metrics"]["strict_top1"],
                result["metrics"]["acceptable_hit"],
                result["metrics"]["bad_skill_called"],
            )
        )

        if args.save_every and index % args.save_every == 0:
            write_output(args.output, results)
        if args.sleep:
            time.sleep(args.sleep)

    write_output(args.output, results)
    print_summary(summarize(results))
    print("output=%s" % args.output)


def write_output(output_path: Path, results: List[Dict[str, Any]]) -> None:
    """写入评测明细和汇总指标。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "summary": summarize(results),
        "results": results,
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
