from pathlib import Path

from PIL import Image

from module3_agent import floorplan_image


def test_floorplan_prompt_locks_layout_and_uses_rag(tmp_path, monkeypatch):
    source = tmp_path / "plan.jpg"
    Image.new("RGB", (120, 80), "white").save(source)

    monkeypatch.setattr(floorplan_image, "is_floorplan_generation_configured", lambda: True)
    monkeypatch.setattr(
        floorplan_image,
        "query_design_knowledge",
        lambda query, top_k=4: [{"text": "墙面使用微水泥，灯光采用 3000K", "source": "lighting.md", "distance": 0.1}],
    )

    captured = {}

    class FakeImages:
        def edit(self, **kwargs):
            captured.update(kwargs)
            return type("Response", (), {"data": []})()

    class FakeClient:
        def __init__(self, **kwargs):
            self.images = FakeImages()

    monkeypatch.setattr(floorplan_image, "OpenAI", FakeClient)
    result = floorplan_image.generate_floorplan_render(source, "现代简约", "客厅主视角")

    assert result["success"] is False
    assert "HARD CONSTRAINTS" in captured["prompt"]
    assert "wall positions" in captured["prompt"]
    assert "3000K" in captured["prompt"]
    assert result["error"] == "API 返回中没有可保存的图片数据"
