"""Generate an interior concept render from an uploaded floor plan."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from PIL import Image
from openai import OpenAI

from config import IMAGE_CONFIG, PROJECT_ROOT
from module3_agent.openai_image_client import _save_response_image
from module2_rag.query_knowledge import build_citations, format_results, query_design_knowledge


VIEW_PROMPTS = {
    "客厅主视角": "a living room main perspective from eye level",
    "全屋广角": "a wide-angle view showing the overall apartment layout",
    "餐客厅视角": "an open-plan dining and living room perspective",
    "卧室视角": "a bedroom perspective with the surrounding circulation visible",
}

LAYOUT_LOCK = (
    "HARD CONSTRAINTS: Treat the uploaded floor plan as an architectural blueprint. "
    "Do not move, remove, add, merge, resize, rotate, or mirror rooms. Do not change the outer boundary, "
    "wall positions, structural openings, doors, windows, stairs, wet areas, or circulation paths. "
    "Do not invent balconies, rooms, corridors, or windows that are absent from the plan. "
    "Only add furniture, finishes, lighting, and decor inside the existing spaces. "
    "Keep the same room adjacency and relative proportions."
)


def _retrieve_design_constraints(style_prompt: str, view: str) -> tuple[str, list[dict], str]:
    """Retrieve style and room guidance without allowing RAG to override the plan."""
    query = f"{style_prompt.strip()} {view} 户型 室内设计 材质 灯光 家具 动线"
    try:
        results = query_design_knowledge(query, top_k=4)
    except Exception as exc:
        return "", [], f"RAG 检索不可用：{exc}"
    if not results:
        return "", [], "知识库未返回相关设计约束"
    context = format_results(query, results)
    # Keep the image prompt bounded. RAG supplies styling guidance, never layout edits.
    return context[:3500], build_citations(results), ""


def _prepare_image(image_path: str | Path) -> Path:
    """Convert an uploaded floor plan to a PNG accepted by image edit APIs."""
    source = Path(image_path)
    if not source.exists():
        raise FileNotFoundError(f"找不到户型图：{source}")

    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((2048, 2048))
        temporary = Path(tempfile.gettempdir()) / f"interiorforge_floorplan_{time.time_ns()}.png"
        image.save(temporary, format="PNG")
    return temporary


def is_floorplan_generation_configured() -> bool:
    """Return whether the configured OpenAI-compatible image endpoint has a key."""
    return bool(IMAGE_CONFIG.get("api_key", "").strip())


def generate_floorplan_render(
    image_path: str | Path,
    style_prompt: str,
    view: str = "客厅主视角",
    size: str | None = None,
    quality: str | None = None,
) -> dict:
    """Edit a floor plan into a photorealistic interior concept render.

    The floor plan is used as a spatial reference. The result is a concept image,
    not a construction drawing or a guarantee of exact dimensional accuracy.
    """
    if not is_floorplan_generation_configured():
        return {
            "success": False,
            "provider": "openai",
            "image_path": None,
            "error": "未配置 OPENAI_API_KEY，无法使用户型图生图功能",
        }
    if not style_prompt or not style_prompt.strip():
        return {
            "success": False,
            "provider": "openai",
            "image_path": None,
            "error": "请填写风格、材质或空间要求",
        }

    rag_context, rag_citations, rag_warning = _retrieve_design_constraints(style_prompt, view)
    prompt = (
        "Use the uploaded floor plan as the primary and authoritative spatial reference. "
        f"{LAYOUT_LOCK} Generate one coherent, photorealistic interior design concept in "
        f"{VIEW_PROMPTS.get(view, view)}. User requirements: {style_prompt.strip()} "
        "Use the following retrieved design guidance only for finishes, furniture, lighting, colors, and mood. "
        "Never use it to change the floor plan or architectural geometry:\n"
        "<DESIGN_GUIDANCE>\n"
        f"{rag_context or 'No retrieved guidance. Follow the user requirements only.'}\n"
        "</DESIGN_GUIDANCE>\n"
        "Do not show the floor plan, labels, dimensions, text, watermark, or a split-screen comparison. "
        "Keep furniture scale, camera perspective, and architectural proportions consistent with the plan."
    )

    try:
        temporary = _prepare_image(image_path)
        client = OpenAI(
            api_key=IMAGE_CONFIG["api_key"],
            base_url=IMAGE_CONFIG["api_base"],
            timeout=IMAGE_CONFIG["timeout"],
        )
        with temporary.open("rb") as image_file:
            response = client.images.edit(
                model=IMAGE_CONFIG["model"],
                image=image_file,
                prompt=prompt,
                input_fidelity="high",
                size=size or IMAGE_CONFIG["size"],
                quality=quality or IMAGE_CONFIG["quality"],
            )

        first_image = response.data[0] if response.data else None
        if first_image is None:
            data = {}
        elif hasattr(first_image, "model_dump"):
            data = first_image.model_dump()
        else:
            data = dict(first_image)

        output_dir = PROJECT_ROOT / "outputs" / "floorplan"
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = output_dir / f"floorplan_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000:06d}.png"
        path = _save_response_image(data, destination)
        if path is None:
            return {
                "success": False,
                "provider": "openai",
                "image_path": None,
                "error": "API 返回中没有可保存的图片数据",
            }
        return {
            "success": True,
            "provider": "openai",
            "image_path": str(path),
            "model": IMAGE_CONFIG["model"],
            "prompt": prompt,
            "rag_citations": rag_citations,
            "rag_warning": rag_warning,
            "layout_policy": "strict",
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "provider": "openai",
            "image_path": None,
            "error": f"户型图生图失败：{exc}",
        }
    finally:
        if temporary and temporary.exists():
            temporary.unlink(missing_ok=True)
