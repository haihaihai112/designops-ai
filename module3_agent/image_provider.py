"""Capability-based image provider boundary for the product pipeline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from config import IMAGE_CONFIG
from module3_agent.openai_image_client import generate_openai_image


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str
    generation: bool
    editing: bool
    local: bool


class ImageProvider(Protocol):
    capabilities: ProviderCapabilities

    def generate(self, positive_prompt: str, negative_prompt: str, **params) -> dict: ...


class OpenAIImageProvider:
    capabilities = ProviderCapabilities(
        name="openai",
        generation=True,
        editing=True,
        local=False,
    )

    def generate(self, positive_prompt: str, negative_prompt: str, **params) -> dict:
        result = generate_openai_image(positive_prompt, negative_prompt)
        result["capabilities"] = asdict(self.capabilities)
        result["estimated_cost_usd"] = (
            IMAGE_CONFIG["estimated_cost_usd"] if result.get("success") else 0.0
        )
        return result


class ComfyUIAdapter:
    """Optional local adapter retained for private deployments, not product UI."""

    capabilities = ProviderCapabilities(
        name="comfyui",
        generation=True,
        editing=False,
        local=True,
    )

    def generate(self, positive_prompt: str, negative_prompt: str, **params) -> dict:
        if not IMAGE_CONFIG["enable_comfyui_adapter"]:
            raise RuntimeError("ComfyUI 适配器未启用")
        from module3_agent.comfyui_client import check_comfyui_available, generate_image

        if not check_comfyui_available():
            return {
                "success": False,
                "provider": "comfyui",
                "image_path": None,
                "error": "ComfyUI 服务不可用",
                "capabilities": asdict(self.capabilities),
                "estimated_cost_usd": 0.0,
            }
        result = generate_image(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            steps=params.get("steps", 30),
            cfg_scale=params.get("cfg_scale", 7.0),
            sampler=params.get("sampler", "euler_ancestral"),
        )
        result["provider"] = "comfyui"
        result["capabilities"] = asdict(self.capabilities)
        result["estimated_cost_usd"] = 0.0
        return result


def get_image_provider(name: str | None = None) -> ImageProvider:
    provider_name = (name or IMAGE_CONFIG["provider"] or "openai").lower()
    if provider_name == "openai":
        return OpenAIImageProvider()
    if provider_name == "comfyui":
        return ComfyUIAdapter()
    raise ValueError(f"不支持的图像 Provider: {provider_name}")
