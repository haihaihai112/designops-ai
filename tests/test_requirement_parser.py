from module3_agent.requirement_parser import format_structured_brief, parse_design_requirement


def test_parse_complete_chinese_requirement():
    parsed = parse_design_requirement(
        "设计一个25平米侘寂风客厅，带落地窗、亚麻沙发和原木茶几，要安静有呼吸感"
    )

    assert parsed["style_code"] == "wabisabi"
    assert parsed["style_name"] == "侘寂风"
    assert parsed["room"] == "客厅"
    assert parsed["area_sqm"] == 25
    assert {"落地窗", "亚麻", "沙发", "原木", "茶几", "安静", "呼吸感"}.issubset(parsed["keywords"])
    assert parsed["completeness"] == 100


def test_format_brief_handles_missing_area():
    parsed = parse_design_requirement("北欧风书房，需要原木书架和自然光")
    brief = format_structured_brief(parsed)

    assert "Style: 北欧风" in brief
    assert "Room: 书房" in brief
    assert "Area: not specified" in brief

