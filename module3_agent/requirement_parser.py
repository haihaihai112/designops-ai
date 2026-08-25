"""Deterministic requirement parsing for the design agent.

The parser intentionally stays local and predictable. Its output is used for
retrieval, prompt coverage checks, persistence, and the operations dashboard.
"""

from __future__ import annotations

import re


STYLE_RULES = {
    "wabisabi": ("侘寂风", ["侘寂", "wabisabi", "wabi-sabi", "日式", "禅意"]),
    "french_cream": ("法式奶油风", ["法式奶油", "奶油风", "法式", "french cream", "巴黎"]),
    "minimalist": ("极简风", ["极简", "无主灯", "简约", "minimalist", "现代简约"]),
    "modern_luxury": ("现代轻奢", ["现代轻奢", "轻奢", "modern luxury", "quiet luxury"]),
    "scandinavian": ("北欧风", ["北欧", "scandinavian", "nordic", "自然风"]),
}

ROOM_RULES = {
    "客厅": ["客厅", "起居室", "living room"],
    "卧室": ["卧室", "主卧", "次卧", "bedroom"],
    "餐厅": ["餐厅", "饭厅", "dining"],
    "厨房": ["厨房", "kitchen"],
    "书房": ["书房", "工作室", "study", "office"],
    "卫生间": ["卫生间", "浴室", "bathroom"],
    "儿童房": ["儿童房", "儿童卧室", "kids room"],
}

CATEGORY_RULES = {
    "materials": [
        "亚麻", "原木", "实木", "微水泥", "大理石", "黄铜", "藤编", "丝绒",
        "玻璃", "皮革", "木地板", "石膏线", "陶器", "瓷砖", "棉麻",
    ],
    "lighting": [
        "自然光", "落地窗", "无主灯", "轨道灯", "灯带", "吊灯", "壁灯", "纸灯",
        "柔光", "暖光", "冷光", "采光", "窗户", "百叶窗",
    ],
    "furniture": [
        "沙发", "茶几", "床", "床头柜", "衣柜", "书架", "书桌", "餐桌", "餐椅",
        "收纳柜", "地毯", "岛台", "橱柜", "座椅", "蒲团",
    ],
    "layout": [
        "开放式", "一体化", "动静分区", "干湿分离", "隐藏式", "悬浮", "低矮",
        "留白", "对称", "不对称", "通透", "宽敞", "紧凑",
    ],
    "mood": [
        "温暖", "安静", "禅意", "治愈", "浪漫", "高级感", "呼吸感", "克制",
        "自然", "温馨", "明亮", "沉稳", "松弛", "干净",
    ],
    "colors": [
        "奶油色", "米色", "灰色", "白色", "原木色", "暖色", "冷色", "低饱和",
        "大地色", "蓝色", "绿色", "棕色", "金色", "黑色",
    ],
}


def _first_match(text: str, rules: dict[str, list[str]], default: str | None = None) -> str | None:
    lowered = text.lower()
    for key, keywords in rules.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            return key
    return default


def parse_design_requirement(user_input: str) -> dict:
    """Convert a free-form design request into a stable structured brief."""
    text = " ".join(user_input.strip().split())
    lowered = text.lower()

    style_code = None
    style_name = "未指定"
    for code, (name, keywords) in STYLE_RULES.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            style_code = code
            style_name = name
            break

    room = _first_match(text, ROOM_RULES, "客厅")
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:平米|平方米|㎡|m2|m²)", lowered)
    area_sqm = float(area_match.group(1)) if area_match else None

    constraints = {}
    all_terms = []
    for category, keywords in CATEGORY_RULES.items():
        matches = [keyword for keyword in keywords if keyword.lower() in lowered]
        constraints[category] = matches
        all_terms.extend(matches)

    completeness_fields = [style_code, room, area_sqm, all_terms]
    completeness = round(sum(bool(value) for value in completeness_fields) / len(completeness_fields) * 100)

    return {
        "raw": text,
        "style_code": style_code,
        "style_name": style_name,
        "room": room,
        "area_sqm": area_sqm,
        "constraints": constraints,
        "keywords": list(dict.fromkeys(all_terms)),
        "completeness": completeness,
    }


def format_structured_brief(parsed: dict) -> str:
    """Format parsed requirements for prompt injection and UI display."""
    constraint_lines = []
    for category, values in parsed["constraints"].items():
        if values:
            constraint_lines.append(f"- {category}: {', '.join(values)}")
    constraints = "\n".join(constraint_lines) or "- constraints: follow the original request"
    area = f"{parsed['area_sqm']:g} sqm" if parsed["area_sqm"] is not None else "not specified"
    return (
        f"Style: {parsed['style_name']}\n"
        f"Room: {parsed['room']}\n"
        f"Area: {area}\n"
        f"Requirement completeness: {parsed['completeness']}%\n"
        f"Constraints:\n{constraints}"
    )
