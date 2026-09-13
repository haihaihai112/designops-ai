"""Optional multimodal evaluation of generated interior-design images."""

from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path

from openai import OpenAI

from config import VISION_CONFIG


def _configured() -> bool:
    key = VISION_CONFIG["api_key"].strip().lower()
    return bool(VISION_CONFIG["model"].strip()) and key not in {
        "", "your-api-key", "your_api_key", "replace-me", "changeme",
    }


def _parse_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("视觉模型未返回 JSON 对象")
    payload = json.loads(match.group(0))
    scores = {}
    for key in ("requirement_match", "spatial_coherence", "material_fidelity", "lighting_quality"):
        scores[key] = min(100, max(0, int(payload.get(key, 0))))
    overall = round(sum(scores.values()) / len(scores))
    return {
        "status": "completed",
        "overall": overall,
        **scores,
        "issues": [str(item) for item in payload.get("issues", [])][:8],
        "evidence": [str(item) for item in payload.get("evidence", [])][:8],
    }


def evaluate_generated_image(image_path: str | Path | None, requirement: str) -> dict:
    """Evaluate the final image; degrade without blocking generation."""
    path = Path(image_path) if image_path else None
    if path is None or not path.is_file():
        return {"status": "not_run", "overall": None, "reason": "没有可评测的生成图片"}
    if not _configured():
        return {
            "status": "not_configured",
            "overall": None,
            "reason": "设置 VISION_MODEL 后启用图片结果评测",
        }

    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    prompt = (
        "Evaluate this generated interior-design image against the Chinese requirement below. "
        "Do not infer invisible dimensions or construction accuracy. Return only one JSON object "
        "with integer scores from 0 to 100 for requirement_match, spatial_coherence, "
        "material_fidelity, lighting_quality, plus string arrays issues and evidence.\n\n"
        f"Requirement: {requirement}"
    )
    try:
        client = OpenAI(
            api_key=VISION_CONFIG["api_key"],
            base_url=VISION_CONFIG["api_base"],
        )
        response = client.responses.create(
            model=VISION_CONFIG["model"],
            input=[{
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {
                        "type": "input_image",
                        "image_url": f"data:{mime_type};base64,{encoded}",
                        "detail": VISION_CONFIG["detail"],
                    },
                ],
            }],
        )
        return _parse_json(response.output_text)
    except Exception as exc:
        return {
            "status": "failed",
            "overall": None,
            "reason": f"图片评测失败：{exc}",
        }
