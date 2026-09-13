"""
全局配置文件 —— 所有模块从这里读取参数。
修改此文件即可切换模型、路径、LoRA 等设置。

敏感信息（API Key）从 .env 文件读取，不硬编码在代码中。
"""

import os
from pathlib import Path

# 尝试加载 .env 文件（如果 python-dotenv 可用）
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass  # python-dotenv 未安装时忽略，直接读系统环境变量

# ==================== 项目根目录 ====================
PROJECT_ROOT = Path(__file__).parent.resolve()

# ==================== LLM 配置（Agent 大脑） ====================
# 支持 OpenAI 兼容接口：DeepSeek、Qwen、本地 Ollama 等
LLM_CONFIG = {
    "backend": os.getenv("LLM_BACKEND", "openai").lower(),
    "api_base": os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1"),
    "api_key": os.getenv("LLM_API_KEY", ""),
    "model": os.getenv("LLM_MODEL", "deepseek-chat"),
    # LiteLLM requires an explicit provider prefix, for example
    # deepseek/deepseek-chat or openai/qwen2.5:7b for a custom endpoint.
    "litellm_model": os.getenv("LITELLM_MODEL", "deepseek/deepseek-chat"),
    "temperature": 0.7,
    "max_tokens": 2048,
}

# ==================== 可观测性配置 ====================
OBSERVABILITY_CONFIG = {
    "enabled": os.getenv("PHOENIX_ENABLED", "0").lower() in {"1", "true", "yes", "on"},
    "project_name": os.getenv("PHOENIX_PROJECT_NAME", "interiorforge-ai"),
    "endpoint": os.getenv(
        "PHOENIX_COLLECTOR_ENDPOINT",
        "http://localhost:6006/v1/traces",
    ),
}

# 如果使用本地 Ollama，取消下面注释并注释上面
# LLM_CONFIG = {
#     "api_base": "http://localhost:11434/v1",
#     "api_key": "ollama",
#     "model": "qwen2.5:7b",
#     "temperature": 0.7,
#     "max_tokens": 2048,
# }

# ==================== Embedding 配置（RAG 向量化） ====================
EMBEDDING_CONFIG = {
    "model_name": os.getenv("EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5"),
    "device": os.getenv("EMBEDDING_DEVICE", "cpu"),
}

# ==================== ChromaDB 配置 ====================
CHROMA_CONFIG = {
    "persist_directory": str(PROJECT_ROOT / "module2_rag" / "chroma_db"),
    "collection_name": "interior_design_knowledge",
}

# ==================== ComfyUI 配置 ====================
COMFYUI_CONFIG = {
    "api_base": os.getenv("COMFYUI_API_BASE", "http://127.0.0.1:8188"),
    "timeout": int(os.getenv("COMFYUI_TIMEOUT", "120")),
    "output_dir": os.getenv("COMFYUI_OUTPUT_DIR", str(PROJECT_ROOT / "outputs")),
}

# ==================== 应用服务配置 ====================
APP_CONFIG = {
    "server_name": os.getenv("GRADIO_SERVER_NAME", "127.0.0.1"),
    "server_port": int(os.getenv("GRADIO_SERVER_PORT", "7860")),
    "auth_user": os.getenv("GRADIO_AUTH_USER", ""),
    "auth_password": os.getenv("GRADIO_AUTH_PASSWORD", ""),
    "auto_build_knowledge_base": os.getenv("AUTO_BUILD_KNOWLEDGE_BASE", "1").lower()
    in {"1", "true", "yes", "on"},
    "hf_endpoint": os.getenv("HF_ENDPOINT", "https://hf-mirror.com"),
    "cors_origins": [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
}

# ==================== 图像 API 配置 ====================
# 产品默认使用 OpenAI；私有化场景可显式启用隐藏的 ComfyUI 适配器。
IMAGE_CONFIG = {
    "provider": os.getenv("IMAGE_PROVIDER", "openai").lower(),
    "api_base": os.getenv("OPENAI_IMAGE_API_BASE", "https://api.openai.com/v1"),
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
    "size": os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
    "quality": os.getenv("OPENAI_IMAGE_QUALITY", "auto"),
    "timeout": int(os.getenv("OPENAI_IMAGE_TIMEOUT", "180")),
    "estimated_cost_usd": float(os.getenv("IMAGE_ESTIMATED_COST_USD", "0")),
    "enable_comfyui_adapter": os.getenv("ENABLE_COMFYUI_ADAPTER", "0").lower()
    in {"1", "true", "yes", "on"},
}

VISION_CONFIG = {
    "api_base": os.getenv("VISION_API_BASE", "https://api.openai.com/v1"),
    "api_key": os.getenv("VISION_API_KEY", os.getenv("OPENAI_API_KEY", "")),
    # Kept empty by default so deployments explicitly select an available
    # vision-capable model instead of assuming account access.
    "model": os.getenv("VISION_MODEL", ""),
    "detail": os.getenv("VISION_IMAGE_DETAIL", "low"),
}

# ==================== 异步任务与预算 ====================
TASK_CONFIG = {
    "backend": os.getenv("TASK_QUEUE_BACKEND", "inline").lower(),
    "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    "queue_name": os.getenv("TASK_QUEUE_NAME", "interiorforge"),
    "timeout_seconds": int(os.getenv("TASK_TIMEOUT_SECONDS", "600")),
    "max_retries": int(os.getenv("TASK_MAX_RETRIES", "2")),
}

BUDGET_CONFIG = {
    "per_job_usd": float(os.getenv("MAX_JOB_COST_USD", "0")),
    "monthly_usd": float(os.getenv("MONTHLY_IMAGE_BUDGET_USD", "0")),
}

# ==================== LoRA 配置 ====================
# 当前暂无风格 LoRA，设为 None 跳过 LoRA 注入
LORA_CONFIG = {
    "lora_name": None,
    "lora_strength": 0.8,
    "trigger_words": "",
}

# ==================== SD 生成默认参数 ====================
SD_DEFAULTS = {
    "checkpoint": "majicmixRealistic_v7.safetensors",  # SD 1.5 写实模型
    "width": 512,
    "height": 768,
    "steps": 30,
    "cfg_scale": 7.0,
    "sampler": "euler_ancestral",
    "negative_prompt": (
        "ugly, blurry, low quality, distorted, bad anatomy, "
        "watermark, text, signature, cropped, jpeg artifacts"
    ),
}
