"""DesignOps AI model operations workbench."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import gradio as gr

from config import APP_CONFIG, COMFYUI_CONFIG, PROJECT_ROOT
from module3_agent.agent_pipeline import run_agent
from module3_agent.comfyui_client import check_comfyui_available
from module3_agent.floorplan_image import generate_floorplan_render
from module3_agent.requirement_parser import parse_design_requirement
from module5_ops.report import VARIANT_LABELS, export_project_report
from module5_ops.store import (
    add_candidate,
    create_project,
    dashboard_metrics,
    get_candidate,
    get_project,
    init_db,
    list_projects,
    save_feedback,
    seed_legacy_batch,
)


init_db()
seed_legacy_batch()

VARIANTS = ["balanced", "creative", "practical"]
CATEGORY_LABELS = {
    "materials": "材质", "lighting": "灯光", "furniture": "家具",
    "layout": "布局", "mood": "氛围", "colors": "配色",
}


def _structured_markdown(parsed: dict) -> str:
    area = f"{parsed['area_sqm']:g} ㎡" if parsed.get("area_sqm") is not None else "未指定"
    lines = [
        "### 结构化 Brief",
        f"**{parsed.get('style_name', '未指定')} · {parsed.get('room', '未指定')} · {area}**",
        f"需求完整度：`{parsed.get('completeness', 0)}%`",
    ]
    for category, values in parsed.get("constraints", {}).items():
        if values:
            lines.append(f"**{CATEGORY_LABELS.get(category, category)}**：{'、'.join(values)}")
    return "\n\n".join(lines)


def _citation_markdown(result: dict) -> str:
    citations = result.get("rag_citations", [])
    warning = result.get("rag_warning", "")
    lines = ["### 知识依据"]
    if warning:
        lines.append(f"> {warning}")
    if not citations:
        lines.append("本次方案未记录知识库引用。")
    for citation in citations:
        distance = citation.get("distance")
        score = f"距离 {distance:.4f}" if isinstance(distance, (int, float)) else "距离未知"
        lines.append(
            f"**[{citation['index']}] {citation['source']}** · {score}\n\n"
            f"{citation['excerpt']}"
        )
    return "\n\n".join(lines)


def _candidate_markdown(candidate: dict) -> str:
    result = candidate["result"]
    quality = result.get("quality", {})
    timings = result.get("timings", {})
    notes = "；".join(quality.get("notes", [])) or "暂无诊断"
    params = result.get("params", {})
    selected = " · **已采用**" if candidate.get("selected") else ""
    return f"""### V{candidate['version']} · {VARIANT_LABELS.get(candidate['variant'], candidate['variant'])}{selected}

**自动质量分 `{quality.get('overall', 0)}`** / 100<br>
需求覆盖 {quality.get('requirement_coverage', 0)} · 意图一致 {quality.get('intent_alignment', 0)} · 交付完整 {quality.get('deliverable_completeness', 0)} · Prompt 质量 {quality.get('prompt_quality', 0)}

生成模式：`{candidate.get('generation_mode', 'unknown')}` · 总耗时：`{timings.get('total', candidate.get('duration_seconds', 0))}s` · CFG `{params.get('cfg_scale', '-')}` · Steps `{params.get('steps', '-')}`

**质量诊断**：{notes}

#### 正向提示词
```text
{result.get('positive_prompt', '')}
```

#### 设计分析
{result.get('analysis', '') or '无'}

#### Coohom Brief
```text
{result.get('coohom_brief', '') or '无'}
```

#### 素材标签与发布包
```text
{result.get('asset_tags', '') or '无'}

{result.get('social_copy', '') or '无'}
```
"""


def _candidate_rows(project: dict) -> list[list]:
    return [
        [
            candidate["id"],
            f"V{candidate['version']}",
            VARIANT_LABELS.get(candidate["variant"], candidate["variant"]),
            candidate.get("auto_score") or 0,
            candidate.get("human_score") or "-",
            candidate.get("generation_mode", "unknown"),
            round(candidate.get("duration_seconds") or 0, 2),
            "已采用" if candidate.get("selected") else "待评估",
        ]
        for candidate in project.get("candidates", [])
    ]


def _candidate_choices(project: dict) -> list[tuple[str, str]]:
    return [
        (
            f"V{candidate['version']} · {VARIANT_LABELS.get(candidate['variant'], candidate['variant'])} · {candidate.get('auto_score') or 0}分",
            str(candidate["id"]),
        )
        for candidate in project.get("candidates", [])
    ]


def _project_choices() -> list[tuple[str, str]]:
    return [
        (f"#{item['id']} · {item['name']} · {item['candidate_count']} 个候选", str(item["id"]))
        for item in list_projects()
    ]


def _project_table() -> list[list]:
    return [
        [
            item["id"], item["name"], item["status"], item["candidate_count"],
            item.get("best_score") or 0, "是" if item.get("selected_count") else "否",
            item["updated_at"].replace("T", " ")[:19],
        ]
        for item in list_projects()
    ]


def _dashboard_outputs():
    metrics = dashboard_metrics()
    metric_html = f"""
    <div class="metric-grid">
      <div class="metric"><span>项目</span><strong>{metrics.get('projects') or 0}</strong><small>累计设计任务</small></div>
      <div class="metric"><span>候选</span><strong>{metrics.get('candidates') or 0}</strong><small>已记录版本</small></div>
      <div class="metric"><span>自动质量</span><strong>{metrics.get('auto_score') or 0}</strong><small>平均 / 100</small></div>
      <div class="metric"><span>人工评分</span><strong>{metrics.get('human_score') or '-'}</strong><small>{metrics.get('feedback_count') or 0} 条反馈</small></div>
      <div class="metric"><span>采用率</span><strong>{metrics.get('adoption_rate') or 0}%</strong><small>候选采用占比</small></div>
      <div class="metric warning"><span>兜底率</span><strong>{metrics.get('fallback_rate') or 0}%</strong><small>离线模板占比</small></div>
    </div>
    """
    recent = [
        [
            item["id"], item["name"], f"V{item['version']}",
            VARIANT_LABELS.get(item["variant"], item["variant"]),
            item.get("auto_score") or 0, item["generation_mode"],
            round(item.get("duration_seconds") or 0, 2),
            "已采用" if item.get("selected") else "-",
        ]
        for item in metrics["recent"]
    ]
    styles = [[style, count] for style, count in sorted(metrics["styles"].items(), key=lambda item: -item[1])]
    decisions = [[item["decision"], item["count"]] for item in metrics["decisions"]]
    return metric_html, recent, styles, decisions


def generate_candidates(project_name: str, user_input: str, candidate_count: int, enable_image: bool, image_provider: str):
    if not user_input or not user_input.strip():
        raise gr.Error("请输入完整的空间设计需求")

    parsed = parse_design_requirement(user_input)
    name = project_name.strip() or f"{parsed['style_name']} · {parsed['room']}"
    variants = VARIANTS if int(candidate_count) == 3 else ["balanced"]
    errors = []
    generated_results = []

    for variant in variants:
        try:
            result = run_agent(
                user_input.strip(), generate=enable_image, variant=variant,
                image_provider=image_provider,
            )
            generated_results.append(result)
        except Exception as exc:
            errors.append(f"{VARIANT_LABELS[variant]}：{exc}")

    if not generated_results:
        raise gr.Error("本轮没有生成可保存的候选方案：" + "；".join(errors))

    project_id = create_project(name, user_input.strip(), parsed)
    for result in generated_results:
        add_candidate(project_id, result)
    project = get_project(project_id)

    first = project["candidates"][0]
    first_result = first["result"]
    image = first.get("image_path") if first.get("image_path") and Path(first["image_path"]).exists() else None
    status = f"已创建项目 `#{project_id}`，生成 {len(project['candidates'])} 个候选。"
    if errors:
        status += "\n\n> 部分候选失败：" + "；".join(errors)
    choices = _candidate_choices(project)
    return (
        status,
        _structured_markdown(parsed),
        _candidate_rows(project),
        gr.Dropdown(choices=choices, value=str(first["id"])),
        _candidate_markdown(first),
        _citation_markdown(first_result),
        image,
        str(first["id"]),
        gr.Dropdown(choices=_project_choices(), value=str(project_id)),
        _candidate_rows(project),
        *_dashboard_outputs(),
    )


def show_candidate(candidate_id: str):
    if not candidate_id:
        return "请选择候选方案", "", None, ""
    candidate = get_candidate(int(candidate_id))
    if not candidate:
        return "候选方案不存在", "", None, ""
    image = candidate.get("image_path")
    if image and not Path(image).exists():
        image = None
    return _candidate_markdown(candidate), _citation_markdown(candidate["result"]), image, str(candidate["id"])


def submit_feedback(candidate_id: str, requirement_score: int, visual_score: int, feasibility_score: int, decision: str, notes: str):
    if not candidate_id:
        raise gr.Error("请先选择一个候选方案")
    save_feedback(
        int(candidate_id), int(requirement_score), int(visual_score),
        int(feasibility_score), decision, notes,
    )
    candidate = get_candidate(int(candidate_id))
    project = get_project(candidate["project_id"])
    return (
        f"反馈已保存：**{decision}** · 综合人工评分 `{(requirement_score + visual_score + feasibility_score) / 3:.1f}` / 5",
        _candidate_rows(project),
        _candidate_rows(project),
        *_dashboard_outputs(),
    )


def refresh_projects():
    choices = _project_choices()
    value = choices[0][1] if choices else None
    project = get_project(int(value)) if value else None
    return gr.Dropdown(choices=choices, value=value), _candidate_rows(project) if project else []


def load_project(project_id: str):
    if not project_id:
        return "请选择项目", [], [], gr.Dropdown(choices=[], value=None)
    project = get_project(int(project_id))
    if not project:
        return "项目不存在", [], [], gr.Dropdown(choices=[], value=None)
    gallery = []
    for candidate in project["candidates"]:
        path = candidate.get("image_path")
        if path and Path(path).exists():
            gallery.append((path, f"V{candidate['version']} · {VARIANT_LABELS.get(candidate['variant'], candidate['variant'])}"))
    adopted = next((item for item in project["candidates"] if item.get("selected")), None)
    summary = f"""### #{project['id']} · {project['name']}

{project['requirement']}

状态：`{project['status']}` · 候选：`{len(project['candidates'])}` · 已采用：`{'V' + str(adopted['version']) if adopted else '无'}` · 更新：`{project['updated_at'].replace('T', ' ')[:19]}`
"""
    choices = _candidate_choices(project)
    value = choices[0][1] if choices else None
    return summary, _candidate_rows(project), gallery, gr.Dropdown(choices=choices, value=value)


def export_report(project_id: str):
    if not project_id:
        raise gr.Error("请先选择项目")
    path = export_project_report(int(project_id))
    return str(path), f"报告已导出：`{path.name}`"


def refresh_dashboard():
    return _dashboard_outputs()


def generate_floorplan_effect(floorplan_path: str, style_prompt: str, view: str, image_provider: str):
    """Generate an interior concept image from an uploaded floor plan."""
    if not floorplan_path:
        raise gr.Error("请先上传户型图")
    if (image_provider or "openai").lower() != "openai":
        return None, "户型图生图当前使用 OpenAI Images 图像编辑接口。当前 ComfyUI 工作流未接入 ControlNet。"

    result = generate_floorplan_render(floorplan_path, style_prompt, view=view)
    if not result.get("success"):
        return None, result.get("error", "户型图生图失败")
    citations = result.get("rag_citations", [])
    sources = "、".join(item["source"] for item in citations[:3]) or "无"
    return result["image_path"], (
        f"已生成户型图效果图，使用模型：`{result.get('model', '-')}`。RAG 参考：{sources}。"
        "结果用于方案概念展示，不能替代施工图或精确尺寸校核。"
    )


CUSTOM_CSS = """
:root { --ink:#202624; --muted:#68716d; --line:#dfe4e1; --paper:#ffffff; --canvas:#f3f5f3; --green:#246b52; --amber:#9a651c; }
.gradio-container { max-width: 1480px !important; margin:0 auto !important; background:var(--canvas) !important; color:var(--ink) !important; }
.app-header { background:#202624; color:white; padding:22px 26px; border-radius:6px; margin:14px 0 12px; display:flex; justify-content:space-between; align-items:flex-end; gap:20px; }
.app-header h1 { font-size:24px; margin:0 0 4px; letter-spacing:0; color:#ffffff !important; }
.app-header p { margin:0; color:#bac3bf; font-size:14px; }
.system-state { color:#d7e9df; font-size:13px; white-space:nowrap; }
.workspace-panel { background:var(--paper); border:1px solid var(--line); border-radius:6px; padding:16px; }
.section-title { font-size:13px; font-weight:700; color:var(--muted); text-transform:uppercase; margin:0 0 10px; }
.metric-grid { display:grid; grid-template-columns:repeat(6,minmax(120px,1fr)); gap:10px; margin-bottom:14px; }
.metric { background:white; border:1px solid var(--line); border-top:3px solid var(--green); border-radius:6px; padding:14px; min-height:104px; }
.metric.warning { border-top-color:var(--amber); }
.metric span,.metric small { display:block; color:var(--muted); font-size:12px; }
.metric strong { display:block; font-size:26px; margin:8px 0 3px; letter-spacing:0; }
.primary-btn { background:var(--green) !important; color:white !important; border-color:var(--green) !important; }
.subtle-note { font-size:12px; color:var(--muted); }
.markdown-body pre { max-height:260px; overflow:auto; border-radius:4px !important; }
.gallery-shell { min-height:300px; }
.candidate-grid { overflow-x:auto !important; }
.candidate-grid table { min-width:680px !important; }
.candidate-grid th,.candidate-grid td { white-space:nowrap !important; font-size:12px !important; }
.tab-nav { border-bottom:1px solid var(--line) !important; }
footer { display:none !important; }
@media (max-width:1000px) { .metric-grid { grid-template-columns:repeat(3,1fr); } .app-header { align-items:flex-start; flex-direction:column; } }
@media (max-width:640px) { .metric-grid { grid-template-columns:repeat(2,1fr); } .app-header { padding:18px; } }
"""


with gr.Blocks(title="DesignOps AI · 模型运营工作台") as demo:
    comfy_state = "ComfyUI 已连接" if check_comfyui_available() else "ComfyUI 离线 · 文本链路可用"
    gr.HTML(f"""
    <header class="app-header">
      <div><h1 style="color:#ffffff">DesignOps AI</h1><p>室内设计模型运营工作台 · 生成、评估、反馈与版本追踪</p></div>
      <div class="system-state">{comfy_state}</div>
    </header>
    """)

    current_candidate = gr.State("")

    with gr.Tabs():
        with gr.Tab("设计台"):
            with gr.Row(equal_height=False):
                with gr.Column(scale=4, min_width=320, elem_classes="workspace-panel"):
                    gr.HTML('<div class="section-title">任务配置</div>')
                    project_name = gr.Textbox(label="项目名称", placeholder="例如：杭州住宅客厅改造")
                    user_input = gr.Textbox(
                        label="空间需求",
                        placeholder="描述空间、面积、风格、材质、灯光、家具和目标氛围",
                        lines=7,
                    )
                    with gr.Row():
                        candidate_count = gr.Radio([1, 3], value=3, label="候选数量")
                        enable_image = gr.Checkbox(value=False, label="启用图像生成")
                    image_provider = gr.Radio(
                        ["auto", "comfyui", "openai"], value="auto", label="图像生成通路",
                    )
                    generate_btn = gr.Button("生成并记录候选", variant="primary", elem_classes="primary-btn")
                    generation_status = gr.Markdown("等待创建任务。", elem_classes="subtle-note")
                    structured_output = gr.Markdown("", elem_classes="markdown-body")

                with gr.Column(scale=7, min_width=520):
                    candidate_table = gr.Dataframe(
                        headers=["ID", "版本", "策略", "自动分", "人工分", "模式", "耗时(s)", "状态"],
                        datatype=["number", "str", "str", "number", "str", "str", "number", "str"],
                        value=[], interactive=False, wrap=False, label="候选对比", elem_classes="candidate-grid",
                    )
                    candidate_select = gr.Dropdown(label="查看候选", choices=[])
                    with gr.Row(equal_height=False):
                        with gr.Column(scale=5):
                            candidate_image = gr.Image(label="渲染结果", type="filepath", height=360)
                        with gr.Column(scale=6):
                            candidate_detail = gr.Markdown("选择候选后查看详情。", elem_classes="markdown-body")
                    citation_output = gr.Markdown("", elem_classes="markdown-body")

            with gr.Row(equal_height=False):
                with gr.Column(scale=8, elem_classes="workspace-panel"):
                    gr.HTML('<div class="section-title">人工评估</div>')
                    with gr.Row():
                        requirement_score = gr.Slider(1, 5, value=4, step=1, label="需求符合度")
                        visual_score = gr.Slider(1, 5, value=4, step=1, label="视觉质量")
                        feasibility_score = gr.Slider(1, 5, value=4, step=1, label="落地可行性")
                    with gr.Row():
                        decision = gr.Radio(["采用", "保留", "淘汰"], value="保留", label="决策")
                        feedback_notes = gr.Textbox(label="评语", placeholder="记录采用原因或失败模式")
                    feedback_btn = gr.Button("保存评估")
                    feedback_status = gr.Markdown("")

        with gr.Tab("户型图生图"):
            gr.Markdown(
                "上传户型图，填写风格和空间要求，系统会根据平面布局生成一张室内概念效果图。"
                "当前使用 OpenAI Images 图像编辑接口，结果不用于替代施工图。"
            )
            with gr.Row(equal_height=False):
                with gr.Column(scale=4, elem_classes="workspace-panel"):
                    floorplan_input = gr.Image(
                        label="户型图",
                        type="filepath",
                        sources=["upload", "clipboard"],
                        height=360,
                    )
                    floorplan_prompt = gr.Textbox(
                        label="设计要求",
                        placeholder="例如：原木侘寂风，米色微水泥，客厅带亚麻沙发和暖色灯光",
                        lines=5,
                    )
                    floorplan_view = gr.Radio(
                        ["客厅主视角", "全屋广角", "餐客厅视角", "卧室视角"],
                        value="客厅主视角",
                        label="效果图视角",
                    )
                    floorplan_provider = gr.Radio(
                        ["openai", "comfyui"],
                        value="openai",
                        label="图像编辑通路",
                    )
                    floorplan_generate_btn = gr.Button("根据户型图生成效果图", variant="primary", elem_classes="primary-btn")
                with gr.Column(scale=7):
                    floorplan_output = gr.Image(label="室内概念效果图", type="filepath", height=520)
                    floorplan_status = gr.Markdown(
                        "等待上传户型图。",
                        elem_classes="subtle-note",
                    )

        with gr.Tab("项目库"):
            with gr.Row():
                project_select = gr.Dropdown(label="项目", choices=_project_choices(), scale=5)
                refresh_projects_btn = gr.Button("刷新", scale=1)
                export_btn = gr.Button("导出报告", scale=1)
            project_summary = gr.Markdown("选择项目查看历史版本。")
            history_table = gr.Dataframe(
                headers=["ID", "版本", "策略", "自动分", "人工分", "模式", "耗时(s)", "状态"],
                datatype=["number", "str", "str", "number", "str", "str", "number", "str"],
                value=[], interactive=False, wrap=False, label="项目版本", elem_classes="candidate-grid",
            )
            history_gallery = gr.Gallery(label="方案画廊", columns=3, height=420, object_fit="contain", elem_classes="gallery-shell")
            report_file = gr.File(label="项目报告", interactive=False)
            report_status = gr.Markdown("")

        with gr.Tab("运营看板"):
            metric_html, recent_rows, style_rows, decision_rows = _dashboard_outputs()
            dashboard_metrics_html = gr.HTML(metric_html)
            refresh_dashboard_btn = gr.Button("刷新指标")
            recent_table = gr.Dataframe(
                headers=["候选ID", "项目", "版本", "策略", "自动分", "模式", "耗时(s)", "采用"],
                value=recent_rows, interactive=False, wrap=False, label="最近运行", elem_classes="candidate-grid",
            )
            with gr.Row():
                style_table = gr.Dataframe(headers=["风格", "项目数"], value=style_rows, interactive=False, label="风格分布")
                decision_table = gr.Dataframe(headers=["评估决策", "次数"], value=decision_rows, interactive=False, label="反馈决策")

    generation_outputs = [
        generation_status, structured_output, candidate_table, candidate_select,
        candidate_detail, citation_output, candidate_image, current_candidate,
        project_select, history_table, dashboard_metrics_html, recent_table,
        style_table, decision_table,
    ]
    generate_btn.click(
        generate_candidates,
        [project_name, user_input, candidate_count, enable_image, image_provider],
        generation_outputs,
    )
    candidate_select.change(
        show_candidate,
        candidate_select,
        [candidate_detail, citation_output, candidate_image, current_candidate],
    )
    feedback_btn.click(
        submit_feedback,
        [current_candidate, requirement_score, visual_score, feasibility_score, decision, feedback_notes],
        [feedback_status, candidate_table, history_table, dashboard_metrics_html, recent_table, style_table, decision_table],
    )
    refresh_projects_btn.click(refresh_projects, outputs=[project_select, history_table])
    project_select.change(load_project, project_select, [project_summary, history_table, history_gallery, candidate_select])
    export_btn.click(export_report, project_select, [report_file, report_status])
    refresh_dashboard_btn.click(
        refresh_dashboard,
        outputs=[dashboard_metrics_html, recent_table, style_table, decision_table],
    )
    floorplan_generate_btn.click(
        generate_floorplan_effect,
        [floorplan_input, floorplan_prompt, floorplan_view, floorplan_provider],
        [floorplan_output, floorplan_status],
    )


if __name__ == "__main__":
    auth = None
    if APP_CONFIG["auth_user"] and APP_CONFIG["auth_password"]:
        auth = (APP_CONFIG["auth_user"], APP_CONFIG["auth_password"])

    demo.queue(default_concurrency_limit=2).launch(
        server_name=APP_CONFIG["server_name"],
        server_port=APP_CONFIG["server_port"],
        share=False,
        auth=auth,
        allowed_paths=[COMFYUI_CONFIG["output_dir"], str(PROJECT_ROOT / "outputs" / "reports")],
        footer_links=[],
        css=CUSTOM_CSS,
        theme=gr.themes.Base(),
    )
