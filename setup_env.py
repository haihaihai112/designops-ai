"""Interactive environment setup for InteriorForge AI."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env"


def _ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main() -> None:
    parser = argparse.ArgumentParser(description="配置 InteriorForge AI 的 API 和运行参数")
    parser.add_argument("--non-interactive", action="store_true", help="只在 .env 不存在时写入默认配置")
    args = parser.parse_args()

    if args.non_interactive:
        if not ENV_FILE.exists():
            ENV_FILE.write_text((ROOT / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
        print(f"已准备配置文件：{ENV_FILE}")
        return

    print("InteriorForge AI 配置向导")
    print("直接按回车可保留默认值。没有 API Key 也可以使用本地模板模式。\n")

    llm_base = _ask("LLM API 地址", "https://api.deepseek.com/v1")
    llm_key = _ask("LLM API Key", "")
    llm_model = _ask("LLM 模型", "deepseek-chat")
    llm_backend = _ask("LLM 调用后端（openai/litellm）", "openai").lower()
    litellm_model = _ask("LiteLLM 模型（需要 provider 前缀）", "deepseek/deepseek-chat")
    phoenix_enabled = _ask("启用 Phoenix 追踪（0/1）", "0")
    openai_key = _ask("OpenAI Images API Key（可留空）", "")
    vision_model = _ask("图片评测模型（留空则关闭）", "")
    server_name = _ask("服务监听地址", "127.0.0.1")
    server_port = _ask("服务端口", "7860")

    content = "\n".join(
        [
            "# InteriorForge AI 自动生成的配置文件",
            f"LLM_BACKEND={llm_backend}",
            f"LLM_API_BASE={llm_base}",
            f"LLM_API_KEY={llm_key}",
            f"LLM_MODEL={llm_model}",
            f"LITELLM_MODEL={litellm_model}",
            f"PHOENIX_ENABLED={phoenix_enabled}",
            "PHOENIX_PROJECT_NAME=interiorforge-ai",
            "PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006/v1/traces",
            "IMAGE_PROVIDER=openai",
            f"OPENAI_API_KEY={openai_key}",
            "OPENAI_IMAGE_MODEL=gpt-image-1",
            "OPENAI_IMAGE_SIZE=1024x1024",
            "OPENAI_IMAGE_QUALITY=auto",
            "IMAGE_ESTIMATED_COST_USD=0",
            "ENABLE_COMFYUI_ADAPTER=0",
            "VISION_API_BASE=https://api.openai.com/v1",
            f"VISION_API_KEY={openai_key}",
            f"VISION_MODEL={vision_model}",
            "VISION_IMAGE_DETAIL=low",
            "TASK_QUEUE_BACKEND=inline",
            "REDIS_URL=redis://localhost:6379/0",
            "TASK_QUEUE_NAME=interiorforge",
            "TASK_TIMEOUT_SECONDS=600",
            "TASK_MAX_RETRIES=2",
            "MAX_JOB_COST_USD=0",
            "MONTHLY_IMAGE_BUDGET_USD=0",
            f"GRADIO_SERVER_NAME={server_name}",
            f"GRADIO_SERVER_PORT={server_port}",
            "API_SERVER_NAME=127.0.0.1",
            "API_SERVER_PORT=8000",
            "CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000",
            "AUTO_BUILD_KNOWLEDGE_BASE=1",
            "",
        ]
    )
    ENV_FILE.write_text(content, encoding="utf-8")
    print(f"\n配置已保存到：{ENV_FILE}")


if __name__ == "__main__":
    main()
