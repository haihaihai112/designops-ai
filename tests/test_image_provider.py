from module3_agent import image_provider


def test_openai_provider_adds_capabilities_and_cost(monkeypatch):
    monkeypatch.setitem(image_provider.IMAGE_CONFIG, "estimated_cost_usd", 0.04)
    monkeypatch.setattr(
        image_provider,
        "generate_openai_image",
        lambda positive, negative: {
            "success": True,
            "provider": "openai",
            "image_path": "result.png",
            "error": None,
        },
    )

    result = image_provider.get_image_provider("openai").generate("prompt", "bad")

    assert result["capabilities"]["editing"] is True
    assert result["capabilities"]["local"] is False
    assert result["estimated_cost_usd"] == 0.04


def test_comfyui_adapter_is_hidden_by_default(monkeypatch):
    monkeypatch.setitem(image_provider.IMAGE_CONFIG, "enable_comfyui_adapter", False)

    try:
        image_provider.get_image_provider("comfyui").generate("prompt", "bad")
    except RuntimeError as exc:
        assert "未启用" in str(exc)
    else:
        raise AssertionError("hidden adapter should not run")
