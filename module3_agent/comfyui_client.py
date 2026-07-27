"""
模块三：ComfyUI API 客户端

通过 ComfyUI 的 REST API 提交工作流并获取生成结果。
ComfyUI 需要在后台运行（默认 http://127.0.0.1:8188）。

流程：
    1. 加载预定义的 SDXL + LoRA 工作流模板
    2. 填入 Agent 生成的提示词和参数
    3. 提交任务 → 轮询进度 → 下载结果
"""

import json
import time
from pathlib import Path
from typing import Optional

import requests
from config import COMFYUI_CONFIG, LORA_CONFIG, SD_DEFAULTS

# 缓存：避免每次调用都重新构造工作流
_CACHED_WORKFLOW = None


def _load_workflow_template() -> dict:
    """
    加载 SD 1.5 文生图工作流模板。
    CheckpointLoaderSimple → CLIPTextEncode(正/负) → KSampler → VAEDecode → SaveImage
    """
    global _CACHED_WORKFLOW
    if _CACHED_WORKFLOW is not None:
        return json.loads(json.dumps(_CACHED_WORKFLOW))  # 深拷贝

    # SD 1.5 文生图工作流（ComfyUI API 格式）
    workflow = {
        "3": {  # CheckpointLoaderSimple
            "inputs": {"ckpt_name": SD_DEFAULTS["checkpoint"]},
            "class_type": "CheckpointLoaderSimple",
        },
        "4": {  # CLIPTextEncode (正向提示词)
            "inputs": {
                "text": "placeholder positive prompt",
                "clip": ["3", 1],
            },
            "class_type": "CLIPTextEncode",
        },
        "5": {  # CLIPTextEncode (负向提示词) — SDXL 用两个 text encoder
            "inputs": {
                "text": "placeholder negative prompt",
                "clip": ["3", 1],
            },
            "class_type": "CLIPTextEncode",
        },
        "6": {  # EmptyLatentImage
            "inputs": {
                "width": SD_DEFAULTS["width"],
                "height": SD_DEFAULTS["height"],
                "batch_size": 1,
            },
            "class_type": "EmptyLatentImage",
        },
        "7": {  # KSampler
            "inputs": {
                "seed": 42,
                "steps": SD_DEFAULTS["steps"],
                "cfg": SD_DEFAULTS["cfg_scale"],
                "sampler_name": SD_DEFAULTS["sampler"],
                "scheduler": "normal",
                "denoise": 1.0,
                "model": ["3", 0],
                "positive": ["4", 0],
                "negative": ["5", 0],
                "latent_image": ["6", 0],
            },
            "class_type": "KSampler",
        },
        "8": {  # VAEDecode
            "inputs": {
                "samples": ["7", 0],
                "vae": ["3", 2],
            },
            "class_type": "VAEDecode",
        },
        "9": {  # SaveImage
            "inputs": {
                "filename_prefix": "interior_design",
                "images": ["8", 0],
            },
            "class_type": "SaveImage",
        },
    }

    _CACHED_WORKFLOW = workflow
    return json.loads(json.dumps(workflow))


def _build_workflow(
    positive_prompt: str,
    negative_prompt: str,
    width: int = 512,
    height: int = 768,
    steps: int = 30,
    cfg_scale: float = 7.0,
    sampler: str = "euler_ancestral",
    seed: int = -1,
) -> dict:
    """
    构造 SD 1.5 文生图工作流，注入 Prompt 和参数。
    """
    import random
    if seed == -1:
        seed = random.randint(0, 2**31 - 1)

    wf = _load_workflow_template()
    wf["4"]["inputs"]["text"] = positive_prompt
    wf["5"]["inputs"]["text"] = negative_prompt
    wf["6"]["inputs"]["width"] = width
    wf["6"]["inputs"]["height"] = height
    wf["7"]["inputs"]["seed"] = seed
    wf["7"]["inputs"]["steps"] = steps
    wf["7"]["inputs"]["cfg"] = cfg_scale
    wf["7"]["inputs"]["sampler_name"] = sampler

    return wf


def queue_prompt(workflow: dict) -> str:
    """提交工作流到 ComfyUI，返回 prompt_id"""
    url = f"{COMFYUI_CONFIG['api_base']}/prompt"
    payload = {"prompt": workflow}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()["prompt_id"]


def get_history(prompt_id: str) -> dict:
    """获取指定 prompt 的执行历史"""
    url = f"{COMFYUI_CONFIG['api_base']}/history/{prompt_id}"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def wait_for_completion(prompt_id: str, timeout: int = 120) -> Optional[dict]:
    """轮询等待生成完成，返回历史记录或 None（超时）"""
    start = time.time()
    while time.time() - start < timeout:
        history = get_history(prompt_id)
        if prompt_id in history:
            return history[prompt_id]
        time.sleep(2)
    return None


def download_image(filename: str, output_dir: str) -> Optional[Path]:
    """从 ComfyUI 下载生成的图像"""
    url = f"{COMFYUI_CONFIG['api_base']}/view"
    params = {"filename": filename, "type": "output"}
    resp = requests.get(url, params=params, timeout=30)

    if resp.status_code != 200:
        return None

    dest = Path(output_dir) / filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "wb") as f:
        f.write(resp.content)
    return dest


def generate_image(
    positive_prompt: str,
    negative_prompt: str = "",
    width: int = 512,
    height: int = 768,
    steps: int = 30,
    cfg_scale: float = 7.0,
    sampler: str = "euler_ancestral",
    seed: int = -1,
) -> dict:
    """
    完整的图像生成流程：提交 → 等待 → 下载。

    返回:
        {
            "success": bool,
            "image_path": str | None,
            "seed": int,
            "prompt_id": str,
            "error": str | None,
        }
    """
    try:
        # 1. 构造工作流
        workflow = _build_workflow(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=width, height=height,
            steps=steps, cfg_scale=cfg_scale, sampler=sampler, seed=seed,
        )

        # 2. 提交
        prompt_id = queue_prompt(workflow)

        # 3. 等待
        history = wait_for_completion(prompt_id, timeout=COMFYUI_CONFIG["timeout"])
        if history is None:
            return {"success": False, "error": "生成超时", "prompt_id": prompt_id, "seed": None, "image_path": None}

        # 4. 提取文件名
        outputs = history.get("outputs", {})
        images = []
        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for img in node_output["images"]:
                    images.append(img)

        if not images:
            return {"success": False, "error": "没有生成图像", "prompt_id": prompt_id, "seed": None, "image_path": None}

        # 5. 下载第一张
        filename = images[0]["filename"]
        dest = download_image(filename, COMFYUI_CONFIG["output_dir"])

        if dest is None:
            return {
                "success": False,
                "image_path": None,
                "seed": workflow["7"]["inputs"]["seed"],
                "prompt_id": prompt_id,
                "error": "ComfyUI 已生成图像，但下载结果失败",
            }

        return {
            "success": True,
            "image_path": str(dest),
            "seed": workflow["7"]["inputs"]["seed"],
            "prompt_id": prompt_id,
            "error": None,
        }

    except requests.ConnectionError:
        return {
            "success": False,
            "error": f"无法连接 ComfyUI ({COMFYUI_CONFIG['api_base']})，请确保 ComfyUI 正在运行",
            "prompt_id": None,
            "seed": None,
            "image_path": None,
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "prompt_id": None,
            "seed": None,
            "image_path": None,
        }


def check_comfyui_available() -> bool:
    """检查 ComfyUI 是否在运行"""
    try:
        resp = requests.get(f"{COMFYUI_CONFIG['api_base']}/system_stats", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False
