"""Deterministic offline evaluation for the design generation pipeline."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

from config import PROJECT_ROOT
from module3_agent.agent_pipeline import run_agent


DEFAULT_CASES = PROJECT_ROOT / "evals" / "interior_cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "evaluations"


def load_cases(path: str | Path = DEFAULT_CASES) -> list[dict]:
    cases = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(cases, list) or not cases:
        raise ValueError("评测集必须是非空 JSON 数组")
    return cases


def _case_metrics(case: dict, result: dict, elapsed: float) -> dict:
    expected = case.get("expected", {})
    parsed = result.get("structured_requirement", {})
    expected_keywords = expected.get("keywords", [])
    extracted_keywords = parsed.get("keywords", [])
    prompt = result.get("positive_prompt", "").lower()
    prompt_covered = [item for item in expected_keywords if str(item).lower() in prompt]
    extracted_covered = [
        item
        for item in expected_keywords
        if any(
            str(item).lower() in str(extracted).lower()
            or str(extracted).lower() in str(item).lower()
            for extracted in extracted_keywords
        )
    ]
    checks = {
        "style": parsed.get("style_code") == expected.get("style_code"),
        "room": parsed.get("room") == expected.get("room"),
        "area": parsed.get("area_sqm") == expected.get("area_sqm"),
    }
    return {
        "id": case.get("id"),
        "checks": checks,
        "parse_accuracy": round(sum(checks.values()) / len(checks) * 100, 1),
        "constraint_coverage": (
            round(len(extracted_covered) / len(expected_keywords) * 100, 1)
            if expected_keywords
            else 100.0
        ),
        "prompt_constraint_coverage": (
            round(len(prompt_covered) / len(expected_keywords) * 100, 1)
            if expected_keywords
            else 100.0
        ),
        "covered_keywords": extracted_covered,
        "missing_keywords": [item for item in expected_keywords if item not in extracted_covered],
        "quality_score": result.get("quality", {}).get("overall", 0),
        "generation_mode": result.get("generation_mode", "unknown"),
        "latency_seconds": round(elapsed, 4),
    }


def run_evaluation(cases: list[dict]) -> dict:
    rows = []
    for case in cases:
        started = time.perf_counter()
        result = run_agent(case["requirement"], generate=False, variant="balanced")
        rows.append(_case_metrics(case, result, time.perf_counter() - started))
    return {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "case_count": len(rows),
        "summary": {
            "parse_accuracy": round(statistics.mean(row["parse_accuracy"] for row in rows), 1),
            "constraint_coverage": round(statistics.mean(row["constraint_coverage"] for row in rows), 1),
            "prompt_constraint_coverage": round(
                statistics.mean(row["prompt_constraint_coverage"] for row in rows), 1
            ),
            "quality_score": round(statistics.mean(row["quality_score"] for row in rows), 1),
            "avg_latency_seconds": round(statistics.mean(row["latency_seconds"] for row in rows), 4),
            "fallback_rate": round(
                sum(row["generation_mode"] == "fallback" for row in rows) / len(rows) * 100, 1
            ),
        },
        "cases": rows,
    }


def write_report(report: dict, output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> tuple[Path, Path]:
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = target_dir / f"evaluation_{timestamp}.json"
    md_path = target_dir / f"evaluation_{timestamp}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = report["summary"]
    lines = [
        "# InteriorForge 离线评测报告",
        "",
        f"- 用例数：{report['case_count']}",
        f"- 解析准确率：{summary['parse_accuracy']}%",
        f"- 约束覆盖率：{summary['constraint_coverage']}%",
        f"- Prompt 约束覆盖率：{summary['prompt_constraint_coverage']}%",
        f"- 平均质量分：{summary['quality_score']}",
        f"- 平均延迟：{summary['avg_latency_seconds']} 秒",
        f"- 本地兜底率：{summary['fallback_rate']}%",
        "",
        "| 用例 | 解析准确率 | 抽取覆盖率 | Prompt 覆盖率 | 质量分 | 耗时 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in report["cases"]:
        lines.append(
            f"| {row['id']} | {row['parse_accuracy']}% | {row['constraint_coverage']}% | "
            f"{row['prompt_constraint_coverage']}% | {row['quality_score']} | {row['latency_seconds']}s |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


def main() -> None:
    parser = argparse.ArgumentParser(description="运行不产生 API 图片费用的固定评测集")
    parser.add_argument("--cases", default=str(DEFAULT_CASES))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--min-parse-accuracy", type=float, default=0)
    parser.add_argument("--min-constraint-coverage", type=float, default=0)
    args = parser.parse_args()
    report = run_evaluation(load_cases(args.cases))
    paths = write_report(report, args.output_dir)
    print(f"JSON: {paths[0]}")
    print(f"Markdown: {paths[1]}")
    if report["summary"]["parse_accuracy"] < args.min_parse_accuracy:
        raise SystemExit("解析准确率低于评测门禁")
    if report["summary"]["constraint_coverage"] < args.min_constraint_coverage:
        raise SystemExit("结构化约束覆盖率低于评测门禁")


if __name__ == "__main__":
    main()
