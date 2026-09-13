from types import SimpleNamespace

import pytest

from module3_agent import model_gateway


def _response(content="ok"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


def test_openai_backend_uses_compatible_client(monkeypatch):
    calls = {}

    class FakeCompletions:
        def create(self, **kwargs):
            calls.update(kwargs)
            return _response("openai result")

    class FakeOpenAI:
        def __init__(self, **kwargs):
            calls["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

    import openai

    monkeypatch.setattr(openai, "OpenAI", FakeOpenAI)
    result = model_gateway.complete_chat(
        [{"role": "user", "content": "hello"}],
        {
            "backend": "openai",
            "api_base": "http://localhost:11434/v1",
            "api_key": "ollama",
            "model": "qwen2.5:7b",
            "temperature": 0.2,
            "max_tokens": 100,
        },
    )

    assert result == "openai result"
    assert calls["client"]["base_url"] == "http://localhost:11434/v1"
    assert calls["model"] == "qwen2.5:7b"


def test_litellm_backend_uses_provider_model(monkeypatch):
    calls = {}

    def fake_completion(**kwargs):
        calls.update(kwargs)
        return {"choices": [{"message": {"content": "litellm result"}}]}

    fake_module = SimpleNamespace(completion=fake_completion)
    monkeypatch.setitem(__import__("sys").modules, "litellm", fake_module)
    result = model_gateway.complete_chat(
        [{"role": "user", "content": "hello"}],
        {
            "backend": "litellm",
            "api_base": "https://api.deepseek.com/v1",
            "api_key": "secret",
            "litellm_model": "deepseek/deepseek-chat",
            "temperature": 0.3,
            "max_tokens": 200,
        },
    )

    assert result == "litellm result"
    assert calls["model"] == "deepseek/deepseek-chat"


def test_unknown_backend_is_rejected():
    with pytest.raises(ValueError, match="LLM_BACKEND"):
        model_gateway.complete_chat([], {"backend": "unknown"})
