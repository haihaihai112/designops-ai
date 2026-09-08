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
    "api_base": os.getenv("LLM_API_BASE", "https://api.deepseek.com/v1"),
    "api_key": os.getenv("LLM_API_KEY", ""),
    "model": os.getenv("LLM_MODEL", "deepseek-chat"),
    "temperature": 0.7,
    "max_tokens": 2048,
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
}

# ==================== 图像 API 配置 ====================
# provider=auto 时优先 ComfyUI，ComfyUI 不可用且配置了 Key 时切换 OpenAI。
IMAGE_CONFIG = {
    "provider": os.getenv("IMAGE_PROVIDER", "auto").lower(),
    "api_base": os.getenv("OPENAI_IMAGE_API_BASE", "https://api.openai.com/v1"),
    "api_key": os.getenv("OPENAI_API_KEY", ""),
    "model": os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1"),
    "size": os.getenv("OPENAI_IMAGE_SIZE", "1024x1024"),
    "quality": os.getenv("OPENAI_IMAGE_QUALITY", "auto"),
    "timeout": int(os.getenv("OPENAI_IMAGE_TIMEOUT", "180")),
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
