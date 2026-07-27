"""
模块三：Agent 智能体编排 —— 主控管道

这是整个系统的核心："需求理解 → RAG检索 → Prompt生成 → 图像生成"

使用方式：
    python agent_pipeline.py "设计一个20平米的侘寂风客厅，需要带落地窗，空间要有呼吸感"

或作为模块：
    from module3_agent.agent_pipeline import run_agent
    result = run_agent("20平米侘寂风客厅，带落地窗")
"""

import re
import sys
import io
from pathlib import Path

# 修复 Windows GBK 环境下 emoji 打印导致的 UnicodeEncodeError
if hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LLM_CONFIG, LORA_CONFIG
from module2_rag.query_knowledge import query_design_knowledge, format_results
from module3_agent.prompt_templates import (
    AGENT_SYSTEM_PROMPT,
    PROMPT_GENERATION_TEMPLATE,
    STYLE_PRESETS,
    BASE_NEGATIVE_PROMPT,
)
from module3_agent.comfyui_client import generate_image, check_comfyui_available
from openai import OpenAI


def _get_llm_client():
    """获取 OpenAI 兼容的 LLM 客户端（DeepSeek / Qwen / Ollama）"""
    return OpenAI(
        base_url=LLM_CONFIG["api_base"],
        api_key=LLM_CONFIG["api_key"],
    )


def _should_use_llm() -> bool:
    """判断当前配置是否足够调用 LLM。Ollama 等本地服务允许使用占位 key。"""
    api_base = LLM_CONFIG["api_base"].lower()
    has_key = bool(LLM_CONFIG["api_key"].strip())
    is_local = "localhost" in api_base or "127.0.0.1" in api_base
    return has_key or is_local


def _detect_style(user_input: str) -> str:
    """从用户输入中检测设计风格类型"""
    style_keywords = {
        "wabisabi": ["侘寂", "wabisabi", "wabi-sabi", "日式", "禅意"],
        "french_cream": ["法式奶油", "奶油风", "法式", "french cream", "巴黎"],
        "minimalist": ["极简", "无主灯", "简约", "minimalist", "现代简约"],
        "modern_luxury": ["现代轻奢", "轻奢", "modern luxury", "quiet luxury", "大理石", "黄铜"],
        "scandinavian": ["北欧", "scandinavian", "nordic", "原木", "自然风"],
    }
    for style, keywords in style_keywords.items():
        for kw in keywords:
            if kw.lower() in user_input.lower():
                return style
    return None


def _detect_room_type(user_input: str) -> str:
    """检测房间类型"""
    room_keywords = {
        "客厅": ["客厅", "起居室", "living room"],
        "卧室": ["卧室", "主卧", "次卧", "bedroom"],
        "餐厅": ["餐厅", "饭厅", "dining"],
        "厨房": ["厨房", "kitchen"],
        "书房": ["书房", "工作室", "study", "office"],
        "卫生间": ["卫生间", "浴室", "bathroom"],
    }
    for room, keywords in room_keywords.items():
        for kw in keywords:
            if kw in user_input:
                return room
    return "客厅"  # 默认


def _fallback_prompt_bundle(user_input: str, style: str | None, room: str, reason: str) -> dict:
    """
    LLM 不可用时的本地兜底输出。
    这样演示现场即使没有 API Key，也能继续调 ComfyUI 生成图片。
    """
    room_prompt = {
        "客厅": "living room, sofa area, coffee table, large window, balanced layout",
        "卧室": "bedroom, bed with headboard, nightstands, soft bedding, calm atmosphere",
        "餐厅": "dining room, dining table, chairs, pendant lamp, warm gathering space",
        "厨房": "kitchen, cabinetry, countertop, clean functional layout, natural light",
        "书房": "study room, desk, bookshelves, reading corner, focused atmosphere",
        "卫生间": "bathroom, vanity, mirror, shower area, spa-like clean design",
    }.get(room, "interior space, balanced furniture layout")

    style_name = {
        "wabisabi": "wabi-sabi",
        "french_cream": "french cream",
        "minimalist": "minimalist",
        "modern_luxury": "modern luxury",
        "scandinavian": "scandinavian natural",
    }.get(style, "contemporary")

    negative_boost = STYLE_PRESETS.get(style or "", {}).get("negative_boost", "")

    positive = (
        f"{style_name} interior, {room_prompt}, {user_input}, professional interior rendering, "
        "wide angle view, realistic material texture, soft natural light, detailed furniture, "
        "architectural visualization, high quality, photorealistic"
    )
    negative = f"{negative_boost}, {BASE_NEGATIVE_PROMPT}" if negative_boost else BASE_NEGATIVE_PROMPT

    return {
        "positive": positive,
        "negative": negative,
        "cfg_scale": 7.0,
        "steps": 24,
        "sampler": "euler_ancestral",
        "analysis": (
            f"LLM 未启用，已使用本地兜底模板生成提示词。原因：{reason}。"
            f"当前方案按「{style_name}」和「{room}」组织空间、材质、灯光与相机视角，"
            "可用于现场演示 ComfyUI 出图链路。"
        ),
        "coohom_brief": (
            f"Room type: {room}\n"
            f"Target style: {style_name}\n"
            f"Area and layout: Extract from user request: {user_input}\n"
            "Key furniture: Main furniture first, then lighting, rug, decor and plants\n"
            "Material palette: Match style tags, keep wood/fabric/stone/metal consistent\n"
            "Lighting setup: Soft ambient light plus accent light, avoid overexposure\n"
            "Camera angle: 24-35mm wide angle, eye level 1.2m-1.5m\n"
            "Render notes: Check furniture scale, vertical lines, material realism and focal point"
        ),
        "asset_tags": (
            f"Category: interior scene, furniture set\n"
            f"Room: {room}\n"
            f"Style tags: {style_name}, interior design, AI rendering\n"
            "Material tags: wood, fabric, wall finish, lighting, decor\n"
            "Color tags: warm neutral, cream, greige, natural tone\n"
            f"Coohom keywords: {style_name} {room}, sofa, lighting, rug, decor, natural material\n"
            "Quality notes: Check scale, texture clarity, no watermark, reusable asset naming"
        ),
        "social_copy": (
            f"Title: {style_name.title()} {room} Concept\n"
            f"Caption: A {style_name} {room} concept generated from an AI-assisted design brief, "
            "focused on natural materials, balanced lighting and a calm spatial mood.\n"
            f"Hashtags: #{style_name.replace(' ', '')} #{room} #interiordesign #aiinterior #coohom\n"
            "Short video script: Show final render first, then reveal the user brief, material palette, "
            "lighting setup, camera angle, and final reusable design tags."
        ),
        "raw_llm_response": f"LLM fallback used: {reason}",
        "llm_warning": reason,
    }


def _query_rag(user_input: str, style: str | None, top_k: int = 5) -> str:
    """查询 RAG 知识库，返回格式化的上下文字符串"""
    queries = [user_input]

    if style:
        # 追加风格相关查询，提高检索召回率
        style_queries = {
            "wabisabi": "侘寂风 材质 灯光 色彩 空间布局",
            "french_cream": "法式奶油风 材质 色彩 石膏线 家具",
            "minimalist": "极简风 无主灯 材质 配色 灯光设计",
            "modern_luxury": "现代轻奢 大理石 黄铜 皮革 灯光 高级感",
            "scandinavian": "北欧自然风 原木 亚麻 绿植 自然光",
        }
        if style in style_queries:
            queries.append(style_queries[style])

    queries.extend([
        "酷家乐 Coohom 英文 brief 方案图 建模 出图 流程",
        "家居模型素材库 标签 分类 材质 风格 关键词",
        "海外设计趋势 社媒内容发布 图文 短视频",
    ])

    all_results = []
    seen = set()
    for q in queries:
        results = query_design_knowledge(q, top_k=3)
        for r in results:
            if r["text"][:50] not in seen:
                seen.add(r["text"][:50])
                all_results.append(r)

    # 按距离排序，取 top_k
    all_results.sort(key=lambda x: x["distance"] if x["distance"] else 999)
    top_results = all_results[:top_k]

    return format_results(user_input, top_results)


def _parse_llm_response(response: str) -> dict:
    """解析 LLM 的结构化输出"""
    result = {
        "positive": "",
        "negative": BASE_NEGATIVE_PROMPT,
        "cfg_scale": 7.0,
        "steps": 30,
        "sampler": "euler_ancestral",
        "analysis": "",
        "coohom_brief": "",
        "asset_tags": "",
        "social_copy": "",
    }

    def extract_section(name: str, following: list[str] | None = None) -> str:
        following = following or [
            "POSITIVE", "NEGATIVE", "PARAMS", "ANALYSIS",
            "COOHOM_BRIEF", "ASSET_TAGS", "SOCIAL_COPY",
        ]
        other_sections = "|".join(s for s in following if s != name)
        match = re.search(
            rf"\[{name}\]\s*\n(.*?)(?=\[({other_sections})\]|$)",
            response,
            re.DOTALL,
        )
        return match.group(1).strip() if match else ""

    # 提取正向提示词
    positive = extract_section("POSITIVE")
    if positive:
        result["positive"] = positive

    # 提取反向提示词
    negative = extract_section("NEGATIVE")
    if negative:
        result["negative"] = negative

    # 提取参数
    params_str = extract_section("PARAMS")
    if params_str:
        cfg = re.search(r"CFG[:\s]*([\d.]+)", params_str, re.IGNORECASE)
        steps = re.search(r"Steps[:\s]*(\d+)", params_str, re.IGNORECASE)
        sampler = re.search(r"Sampler[:\s]*(\w+)", params_str, re.IGNORECASE)
        if cfg: result["cfg_scale"] = float(cfg.group(1))
        if steps: result["steps"] = int(steps.group(1))
        if sampler: result["sampler"] = sampler.group(1)

    # 提取分析
    result["analysis"] = extract_section("ANALYSIS")
    result["coohom_brief"] = extract_section("COOHOM_BRIEF")
    result["asset_tags"] = extract_section("ASSET_TAGS")
    result["social_copy"] = extract_section("SOCIAL_COPY")

    return result


def run_agent(user_input: str, generate: bool = True) -> dict:
    """
    Agent 主入口：接收中文设计需求，输出 Prompt + 可选图像。

    参数:
        user_input: 中文设计需求，如 "20平米侘寂风客厅，带落地窗"
        generate: 是否调用 ComfyUI 生成图像（需要 ComfyUI 在运行）

    返回:
        {
            "user_input": str,
            "detected_style": str,
            "detected_room": str,
            "rag_context": str,
            "positive_prompt": str,
            "negative_prompt": str,
            "params": {cfg, steps, sampler},
            "analysis": str,
            "coohom_brief": str,
            "asset_tags": str,
            "social_copy": str,
            "image": {success, image_path, error} | None,
            "raw_llm_response": str,
        }
    """
    print("=" * 60)
    print(f"🎨 室内设计 AI Agent")
    print(f"📝 需求: {user_input}")
    print("=" * 60)

    # Step 1: 意图识别
    style = _detect_style(user_input)
    room = _detect_room_type(user_input)
    print(f"\n[Step 1] 意图识别 → 风格: {style or '未识别'}, 房间: {room}")

    # Step 2: RAG 检索
    print(f"\n[Step 2] 查询设计知识库...")
    rag_context = _query_rag(user_input, style)
    print(f"  检索到 {rag_context.count('---')} 条相关知识")

    # Step 3: LLM 生成提示词
    print(f"\n[Step 3] LLM 生成提示词 ({LLM_CONFIG['model']})...")

    lora_info = LORA_CONFIG if style else {"lora_name": "N/A", "trigger_words": "N/A", "lora_strength": "N/A"}

    prompt = PROMPT_GENERATION_TEMPLATE.format(
        user_input=f"{user_input}（房间类型：{room}）",
        rag_context=rag_context,
        lora_name=lora_info.get("lora_name", "N/A"),
        trigger_words=lora_info.get("trigger_words", "N/A"),
        lora_strength=lora_info.get("lora_strength", "N/A"),
    )

    llm_warning = ""
    if _should_use_llm():
        try:
            client = _get_llm_client()
            response = client.chat.completions.create(
                model=LLM_CONFIG["model"],
                messages=[
                    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=LLM_CONFIG["temperature"],
                max_tokens=LLM_CONFIG["max_tokens"],
            )
            llm_output = response.choices[0].message.content
            parsed = _parse_llm_response(llm_output)
        except Exception as e:
            llm_warning = f"LLM 调用失败，已切换本地兜底模板：{e}"
            print(f"  ⚠️ {llm_warning}")
            parsed = _fallback_prompt_bundle(user_input, style, room, llm_warning)
            llm_output = parsed["raw_llm_response"]
    else:
        llm_warning = "未检测到 LLM_API_KEY，已切换本地兜底模板"
        print(f"  ⚠️ {llm_warning}")
        parsed = _fallback_prompt_bundle(user_input, style, room, llm_warning)
        llm_output = parsed["raw_llm_response"]

    # 如果检测到风格，追加风格预设增强提示词质量
    if style and style in STYLE_PRESETS:
        preset = STYLE_PRESETS[style]
        parsed["positive"] = f"{preset['positive_boost']}, {parsed['positive']}"
        if not parsed["negative"] or parsed["negative"] == BASE_NEGATIVE_PROMPT:
            parsed["negative"] = f"{preset['negative_boost']}, {parsed['negative']}"

    # 确保触发词在提示词中
    if style and lora_info.get("trigger_words", "N/A") != "N/A":
        if lora_info["trigger_words"] not in parsed["positive"]:
            parsed["positive"] = f"{lora_info['trigger_words']}, {parsed['positive']}"

    print(f"\n  ✅ 正向提示词: {parsed['positive'][:100]}...")
    print(f"  ✅ 参数: CFG={parsed['cfg_scale']}, Steps={parsed['steps']}, Sampler={parsed['sampler']}")

    result = {
        "user_input": user_input,
        "detected_style": style,
        "detected_room": room,
        "rag_context": rag_context,
        "positive_prompt": parsed["positive"],
        "negative_prompt": parsed["negative"],
        "params": {
            "cfg_scale": parsed["cfg_scale"],
            "steps": parsed["steps"],
            "sampler": parsed["sampler"],
        },
        "analysis": parsed["analysis"],
        "coohom_brief": parsed["coohom_brief"],
        "asset_tags": parsed["asset_tags"],
        "social_copy": parsed["social_copy"],
        "image": None,
        "raw_llm_response": llm_output,
        "llm_warning": llm_warning,
    }

    # Step 4: 图像生成
    if generate:
        print(f"\n[Step 4] 调用 ComfyUI 生成图像...")

        if not check_comfyui_available():
            print(f"  ⚠️ ComfyUI 未运行，跳过图像生成")
            print(f"  提示: 先启动 ComfyUI，然后重新运行本脚本")
            result["image"] = {"success": False, "error": "ComfyUI 未运行", "image_path": None}
        else:
            image_result = generate_image(
                positive_prompt=parsed["positive"],
                negative_prompt=parsed["negative"],
                steps=parsed["steps"],
                cfg_scale=parsed["cfg_scale"],
                sampler=parsed["sampler"],
            )
            result["image"] = image_result
            if image_result["success"]:
                print(f"  ✅ 图像已保存: {image_result['image_path']}")
            else:
                print(f"  ❌ 生成失败: {image_result['error']}")

    print(f"\n{'=' * 60}")
    if parsed["analysis"]:
        print(f"📊 设计分析:\n{parsed['analysis']}")
    print(f"{'=' * 60}")

    return result


# CLI 入口
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python agent_pipeline.py <设计需求>")
        print('示例: python agent_pipeline.py "20平米侘寂风客厅，带落地窗，空间要有呼吸感"')
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])
    result = run_agent(user_input)

    if result.get("error"):
        print(f"\n❌ {result['error']}")
