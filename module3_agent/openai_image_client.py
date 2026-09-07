"""OpenAI Images API client used as a cloud alternative to ComfyUI."""

from __future__ import annotations

import base64
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from openai import OpenAI

from config import IMAGE_CONFIG, PROJECT_ROOT


def is_openai_image_configured() -> bool:
    """Return whether a non-empty API key is available."""
    return bool(IMAGE_CONFIG.get("api_key", "").strip())


def _safe_output_path() -> Path:
    output_dir = PROJECT_ROOT / "outputs" / "api"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / f"openai_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000:06d}.png"


def _save_response_image(data: dict, destination: Path) -> Path | None:
    """Save either base64 or URL image responses without exposing remote URLs."""
    encoded = data.get("b64_json")
    if encoded:
        destination.write_bytes(base64.b64decode(encoded))
        return destination

    image_url = data.get("url")
    if not image_url or urlparse(image_url).scheme not in {"http", "https"}:
        return None
    response = requests.get(image_url, timeout=IMAGE_CONFIG["timeout"])
    response.raise_for_status()
    destination.write_bytes(response.content)
    return destination


def generate_openai_image(
    positive_prompt: str,
    negative_prompt: str = "",
    size: str | None = None,
    quality: str | None = None,
) -> dict:
    """Generate an image through the OpenAI Images API.

    The negative prompt is appended as an explicit constraint because the
    Images API accepts one natural-language prompt rather than SD parameters.
    """
    if not is_openai_image_configured():
        return {
            "success": False,
            "provider": "openai",
            "image_path": None,
            "error": "未配置 OPENAI_API_KEY",
        }

    prompt = positive_prompt.strip()
    if negative_prompt.strip():
        prompt += f"\nAvoid: {negative_prompt.strip()}"

    try:
        client = OpenAI(
            api_key=IMAGE_CONFIG["api_key"],
            base_url=IMAGE_CONFIG["api_base"],
            timeout=IMAGE_CONFIG["timeout"],
        )
        response = client.images.generate(
            model=IMAGE_CONFIG["model"],
            prompt=prompt,
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
        destination = _safe_output_path()
        path = _save_response_image(data, destination)
        if path is None:
            return {
                "success": False,
                "provider": "openai",
                "image_path": None,
                "error": "API 返回中没有可保存的 b64_json 或 URL",
            }
        return {
            "success": True,
            "provider": "openai",
            "image_path": str(path),
            "model": IMAGE_CONFIG["model"],
            "error": None,
        }
    except Exception as exc:
        return {
            "success": False,
            "provider": "openai",
            "image_path": None,
            "error": f"OpenAI Images API 调用失败：{exc}",
        }
