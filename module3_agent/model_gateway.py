"""Unified text-model gateway with OpenAI-compatible and LiteLLM backends."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from config import LLM_CONFIG


def _message_content(response: Any) -> str:
    """Extract text from OpenAI-style object or dictionary responses."""
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError):
        try:
            content = response["choices"][0]["message"]["content"]
        except (IndexError, KeyError, TypeError) as exc:
            raise ValueError("模型响应缺少 choices[0].message.content") from exc
    if not isinstance(content, str) or not content.strip():
        raise ValueError("模型返回了空文本")
    return content


def complete_chat(
    messages: Sequence[Mapping[str, str]],
    config: Mapping[str, Any] | None = None,
) -> str:
    """Complete a chat request through the configured model backend."""
    settings = dict(LLM_CONFIG if config is None else config)
    backend = str(settings.get("backend", "openai")).lower()
    common = {
        "messages": [dict(message) for message in messages],
        "temperature": settings.get("temperature", 0.7),
        "max_tokens": settings.get("max_tokens", 2048),
    }

    if backend == "openai":
        from openai import OpenAI

        client = OpenAI(
            base_url=settings.get("api_base"),
            api_key=settings.get("api_key"),
        )
        response = client.chat.completions.create(
            model=settings["model"],
            **common,
        )
        return _message_content(response)

    if backend == "litellm":
        try:
            from litellm import completion
        except ImportError as exc:
            raise RuntimeError(
                "LLM_BACKEND=litellm 需要安装 requirements-aiops.txt"
            ) from exc

        response = completion(
            model=settings["litellm_model"],
            api_base=settings.get("api_base"),
            api_key=settings.get("api_key"),
            **common,
        )
        return _message_content(response)

    raise ValueError(f"不支持的 LLM_BACKEND: {backend}")
