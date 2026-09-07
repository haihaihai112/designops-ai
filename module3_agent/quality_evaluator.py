"""Lightweight, explainable quality checks for generated design bundles."""

from __future__ import annotations


TECHNICAL_TERMS = (
    "render", "photorealistic", "wide angle", "interior", "lighting", "material",
)

STYLE_ALIASES = {
    "wabisabi": ("wabisabi", "wabi-sabi", "wabi sabi", "japandi"),
    "french_cream": ("french cream", "parisian", "paris"),
    "minimalist": ("minimalist", "minimalism"),
    "modern_luxury": ("modern luxury", "quiet luxury"),
    "scandinavian": ("scandinavian", "nordic"),
}

KEYWORD_ALIASES = {
    "亚麻": ("linen",), "原木": ("natural wood", "oak", "wood"),
    "实木": ("solid wood",), "微水泥": ("microcement",), "大理石": ("marble",),
    "黄铜": ("brass",), "藤编": ("rattan", "woven"), "丝绒": ("velvet",),
    "皮革": ("leather",), "石膏线": ("plaster molding", "molding"),
    "陶器": ("pottery", "ceramic"), "沙发": ("sofa",), "茶几": ("coffee table",),
    "床": ("bed",), "衣柜": ("wardrobe",), "书架": ("bookshelf",),
    "书桌": ("desk",), "餐桌": ("dining table",), "餐椅": ("dining chair", "chairs"),
    "收纳柜": ("storage", "cabinet"), "地毯": ("rug",), "橱柜": ("cabinetry",),
    "落地窗": ("floor-to-ceiling window", "large window"), "自然光": ("natural light",),
    "无主灯": ("track lighting", "indirect lighting"), "轨道灯": ("track light",),
    "灯带": ("light strip", "linear light"), "吊灯": ("pendant", "chandelier"),
    "壁灯": ("wall lamp", "sconce"), "纸灯": ("paper lamp", "paper lantern"),
    "柔光": ("soft light", "diffused light"), "暖光": ("warm light", "warm ambient"),
    "留白": ("negative space", "uncluttered"), "低矮": ("low furniture", "low-profile"),
    "通透": ("open space", "airy"), "温暖": ("warm",), "安静": ("quiet", "calm"),
    "禅意": ("zen",), "治愈": ("cozy", "soothing"), "浪漫": ("romantic",),
    "高级感": ("high-end", "refined", "luxury"), "呼吸感": ("breathing room", "airy"),
    "克制": ("restrained",), "自然": ("natural",), "温馨": ("cozy", "warm"),
    "明亮": ("bright",), "干净": ("clean",), "奶油色": ("cream",),
    "米色": ("beige",), "灰色": ("grey", "gray"), "白色": ("white",),
    "原木色": ("natural wood",), "暖色": ("warm tone",), "低饱和": ("muted",),
    "大地色": ("earth tone",), "蓝色": ("blue",), "绿色": ("green",),
    "棕色": ("brown",), "金色": ("gold",), "黑色": ("black",),
}


def _keyword_is_covered(keyword: str, prompt: str) -> bool:
    terms = (keyword.lower(), *KEYWORD_ALIASES.get(keyword, ()))
    return any(term in prompt for term in terms)


def evaluate_design_bundle(parsed_requirement: dict, result: dict) -> dict:
    """Score prompt coverage and deliverable completeness without another LLM call."""
    positive = result.get("positive_prompt", "").lower()
    source = parsed_requirement.get("raw", "").lower()
    keywords = parsed_requirement.get("keywords", [])

    keyword_hits = [keyword for keyword in keywords if _keyword_is_covered(keyword, positive)]
    if keywords:
        requirement_coverage = round(len(keyword_hits) / len(keywords) * 100)
    else:
        requirement_coverage = 70 if positive else 0

    room = parsed_requirement.get("room", "")
    room_aliases = {
        "客厅": ("living room", "客厅"),
        "卧室": ("bedroom", "卧室"),
        "餐厅": ("dining", "餐厅"),
        "厨房": ("kitchen", "厨房"),
        "书房": ("study", "office", "书房"),
        "卫生间": ("bathroom", "卫生间"),
        "儿童房": ("kids", "children", "儿童"),
    }
    room_covered = any(alias in positive for alias in room_aliases.get(room, (room.lower(),)))
    style_code = parsed_requirement.get("style_code")
    style_terms = STYLE_ALIASES.get(style_code, ())
    style_covered = not style_code or any(term in positive for term in style_terms) or any(
        token in positive for token in parsed_requirement.get("style_name", "").lower().split()
    )
    intent_score = round((int(room_covered) + int(style_covered)) / 2 * 100)

    deliverables = ["analysis", "coohom_brief", "asset_tags", "social_copy"]
    complete_count = sum(bool(str(result.get(field) or "").strip()) for field in deliverables)
    deliverable_score = round(complete_count / len(deliverables) * 100)

    technical_hits = sum(term in positive for term in TECHNICAL_TERMS)
    prompt_score = min(100, round(len(positive) / 5) + technical_hits * 5) if positive else 0

    overall = round(
        requirement_coverage * 0.35
        + intent_score * 0.25
        + deliverable_score * 0.2
        + prompt_score * 0.2
    )
    missing = [keyword for keyword in keywords if keyword not in keyword_hits]
    notes = []
    if missing:
        notes.append(f"未在提示词中直接覆盖：{', '.join(missing[:6])}")
    if deliverable_score < 100:
        notes.append("部分运营交付物缺失")
    if not notes:
        notes.append("需求关键词和运营交付物覆盖完整")

    return {
        "overall": overall,
        "requirement_coverage": requirement_coverage,
        "intent_alignment": intent_score,
        "deliverable_completeness": deliverable_score,
        "prompt_quality": prompt_score,
        "covered_keywords": keyword_hits,
        "missing_keywords": missing,
        "notes": notes,
        "source_length": len(source),
    }
