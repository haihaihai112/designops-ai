"""Export persisted design projects as portable Markdown reports."""

from __future__ import annotations

from pathlib import Path

from config import PROJECT_ROOT
from module5_ops.store import DEFAULT_DB_PATH, get_project


VARIANT_LABELS = {"balanced": "均衡方案", "creative": "创意方案", "practical": "落地方案"}


def _safe_name(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in "-_" else "_" for char in value.strip())
    return safe[:48] or "design_project"


def export_project_report(
    project_id: int,
    db_path: str | Path = DEFAULT_DB_PATH,
    output_dir: str | Path | None = None,
) -> Path:
    project = get_project(project_id, db_path)
    if not project:
        raise ValueError(f"项目不存在: {project_id}")

    target_dir = Path(output_dir) if output_dir else PROJECT_ROOT / "outputs" / "reports"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{project_id:04d}_{_safe_name(project['name'])}.md"

    structured = project["structured_requirement"]
    lines = [
        f"# {project['name']}",
        "",
        "## 原始需求",
        "",
        project["requirement"],
        "",
        "## 结构化 Brief",
        "",
        f"- 风格：{structured.get('style_name', '未指定')}",
        f"- 空间：{structured.get('room', '未指定')}",
        f"- 面积：{structured.get('area_sqm') or '未指定'} ㎡",
        f"- 需求完整度：{structured.get('completeness', 0)}%",
        "",
        "## 候选方案",
        "",
    ]

    for candidate in project["candidates"]:
        result = candidate["result"]
        quality = result.get("quality", {})
        lines.extend([
            f"### V{candidate['version']} · {VARIANT_LABELS.get(candidate['variant'], candidate['variant'])}",
            "",
            f"- 自动质量分：{candidate.get('auto_score') or '-'} / 100",
            f"- 生成模式：{candidate.get('generation_mode')}",
            f"- 总耗时：{candidate.get('duration_seconds')} 秒",
            f"- 采用状态：{'已采用' if candidate.get('selected') else '未采用'}",
            f"- 图片：{candidate.get('image_path') or '未生成'}",
            "",
            "**正向提示词**",
            "",
            "```text",
            result.get("positive_prompt", ""),
            "```",
            "",
            "**设计分析**",
            "",
            result.get("analysis", "") or "无",
            "",
            "**质量诊断**",
            "",
            f"- 需求覆盖：{quality.get('requirement_coverage', 0)}",
            f"- 意图一致：{quality.get('intent_alignment', 0)}",
            f"- 交付完整：{quality.get('deliverable_completeness', 0)}",
            "",
            "**知识引用**",
            "",
        ])
        citations = result.get("rag_citations", [])
        if citations:
            for citation in citations:
                lines.append(f"- `{citation['source']}`（距离 {citation.get('distance')}）：{citation['excerpt']}")
        else:
            lines.append("- 本次运行未记录引用")
        lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")
    return target
