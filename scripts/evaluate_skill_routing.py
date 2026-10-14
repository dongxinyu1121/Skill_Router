"""评测模型第一次响应中的技能选择，保存逐条结果及汇总指标。

数据来自 data/skill_routing_eval.json。此脚本不实际执行技能或评测续写质量，
只比较模型提出的 Skill 调用与人工标注是否匹配。可用 --validate-only
仅校验数据集，无需模型配置，也不会发起模型请求。
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Set

# 以脚本所在位置定位项目根目录，使默认数据路径不依赖终端工作目录。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    # 直接运行脚本时补齐导入路径，才能导入项目根目录的 agent 包。
    sys.path.insert(0, str(ROOT))

from agent import ModelClient, SkillRegistry, WritingAgent


# 默认输入为人工标注，默认输出为本轮结果。
DEFAULT_INPUT = ROOT / "data" / "skill_routing_eval.json"
DEFAULT_OUTPUT = ROOT / "data" / "skill_routing_eval_results.json"


def load_cases(input_path: Path) -> List[Dict[str, Any]]:
    """读取 UTF-8 编码的 JSON 评测文件，返回样本列表。

    本方法只解码数据；字段完整性、重复 ID 和技能名称由 validate_cases 检查。
    """
    return json.loads(input_path.read_text(encoding="utf-8"))


def validate_cases(cases: List[Dict[str, Any]], registered_skills: Set[str]) -> None:
    """校验必填字段、样本 ID 唯一性及三组技能标注是否有效。

    expected_skills 是严格命中目标，acceptable_skills 是可接受的替代技能，
    bad_skills 是不应调用的技能。三者必须是列表，且名称都已在注册表中。
    发现问题时抛出 ValueError；通过时不返回结果。
    """
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
            # 集合差找出未注册名称，累积后统一报告。
            unknown_skills.update(set(value) - registered_skills)

    if unknown_skills:
        raise ValueError("unknown skills in eval data: %s" % sorted(unknown_skills))


def score_case(case: Dict[str, Any], actual_skills: List[str]) -> Dict[str, Any]:
    """将实际技能列表与人工标注比较，返回四个布尔指标。

    strict_top1：第一个选择是否属于严格目标集合。
    strict_top3：前三个选择中是否至少有一个属于严格目标集合。
    acceptable_hit：所有选择中是否至少命中严格目标或可接受替代。
    bad_skill_called：所有选择中是否至少出现一个不应调用的技能。
    """
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
    """汇总请求成功数、命中比例、错误技能比例及平均技能调用数量。

    所有比例的分母都是总样本数，包含模型请求失败的样本；不是只统计
    成功请求。空列表返回全零指标，避免除零。比例保留四位小数，
    平均调用数量保留两位小数，重复技能也计入调用数量。
    """
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
        """计算某类结果占全部样本的比例，返回小数而非百分数。"""
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
    writing_agent: WritingAgent,
) -> Dict[str, Any]:
    """向模型提交单条样本，提取技能选择并返回标注、预测、耗时和指标。

    每个样本只发送一条用户消息，互不共享历史。模型提出工具调用后不执行，
    也不请求第二轮回答。latency_ms 测量的是本次 route 调用的耗时，
    不包含评分和文件保存；请求失败时额外保留错误消息。
    """
    started_at = time.time()
    route_result = writing_agent.route(case["query"])
    latency_ms = int((time.time() - started_at) * 1000)

    actual_skills = route_result.selected_skills
    metrics = score_case(case, actual_skills)
    result = {
        "id": case["id"],
        "domain": case.get("domain", ""),
        "query": case["query"],
        "expected_skills": case["expected_skills"],
        "acceptable_skills": case["acceptable_skills"],
        "bad_skills": case["bad_skills"],
        "actual_skills": actual_skills,
        "status": route_result.status,
        "stop_reason": route_result.stop_reason,
        "latency_ms": latency_ms,
        "metrics": metrics,
    }
    if route_result.status == "failed":
        result["error_message"] = route_result.error or ""
    return result


def print_summary(summary: Dict[str, Any]) -> None:
    """将汇总结果打印到终端，比例转成百分数，平均调用数量保持原单位。"""
    print("\nSkill routing evaluation summary")
    print("total=%s success=%s failed=%s" % (summary["total"], summary["success"], summary["failed"]))
    print("strict_top1_accuracy=%.2f%%" % (summary["strict_top1_accuracy"] * 100))
    print("strict_top3_accuracy=%.2f%%" % (summary["strict_top3_accuracy"] * 100))
    print("acceptable_hit_rate=%.2f%%" % (summary["acceptable_hit_rate"] * 100))
    print("bad_skill_call_rate=%.2f%%" % (summary["bad_skill_call_rate"] * 100))
    print("avg_skill_calls=%.2f" % summary["avg_skill_calls"])


def parse_args() -> argparse.Namespace:
    """读取评测路径、样本范围、限流间隔及保存频率等命令行选项。

    start 是从零开始的偏移量；limit 限制从该位置开始的样本数量。
    validate-only 让主函数在数据校验后退出，不创建模型客户端。
    """
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
    """组织完整评测流程：注册技能、校验样本、筛选范围、请求模型和保存。

    评测通过 WritingAgent.route 复用与交互入口相同的提示词和工具描述。
    results 只保存当前执行选中的样本；输出文件会被当前结果覆盖，
    不自动合并先前执行的记录。
    """
    args = parse_args()
    registry = SkillRegistry(ROOT / ".claude" / "skills")
    registered_skills = registry.names
    cases = load_cases(args.input)
    validate_cases(cases, registered_skills)

    # 先校验整个数据集，再按 start 和 limit 选择本轮实际请求的范围。
    selected_cases = cases[args.start :]
    if args.limit is not None:
        selected_cases = selected_cases[: args.limit]

    print("eval_cases=%s registered_skills=%s" % (len(selected_cases), len(registered_skills)))
    if args.validate_only:
        print("validate_only=passed")
        return

    # 评测只调用公开的 route 接口，不依赖 Agent 的私有提示词或工具方法。
    writing_agent = WritingAgent(registry=registry, model=ModelClient())
    results: List[Dict[str, Any]] = []

    for index, case in enumerate(selected_cases, start=1):
        print("[%s/%s] %s" % (index, len(selected_cases), case["id"]))
        result = evaluate_case(case, writing_agent)
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

        # 定期覆盖写入本轮已完成的全部结果，降低中途退出时的数据损失。
        if args.save_every and index % args.save_every == 0:
            write_output(args.output, results)
        if args.sleep:
            time.sleep(args.sleep)

    # 正常结束时再保存一次，包含不足一个保存周期的最后一批样本。
    write_output(args.output, results)
    print_summary(summarize(results))
    print("output=%s" % args.output)


def write_output(output_path: Path, results: List[Dict[str, Any]]) -> None:
    """创建输出目录，将本轮结果和重新计算的汇总指标写入 JSON 文件。

    created_at 使用运行机器的本地时间；ensure_ascii=False 保留中文，
    indent=2 便于人工阅读。写入方式为覆盖，不是向文件末尾追加。
    """
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
