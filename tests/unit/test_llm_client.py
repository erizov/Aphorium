"""LLM provider routing tests."""

from types import SimpleNamespace

from config import settings
from services import llm_client


class _FakeCompletions:
    def __init__(self, calls):
        self.calls = calls

    def create(self, **kwargs):
        self.calls.append(kwargs)
        msg = SimpleNamespace(content="Generated aphorism.")
        choice = SimpleNamespace(message=msg)
        return SimpleNamespace(choices=[choice])


class _FakeOpenAI:
    calls = []
    init_kwargs = []

    def __init__(self, **kwargs):
        self.init_kwargs.append(kwargs)
        self.chat = SimpleNamespace(
            completions=_FakeCompletions(self.calls)
        )


def _reset_fake() -> None:
    _FakeOpenAI.calls = []
    _FakeOpenAI.init_kwargs = []


def test_sanitize_error_masks_openai_key_shapes():
    raw = "Incorrect API key provided: sk-abc123****************XYZ."
    assert "abc123" not in llm_client._sanitize_error(raw)
    assert llm_client._sanitize_error(raw).count("sk-***") == 1


class _FailingOpenAI:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=self)

    def create(self, **kwargs):
        raise RuntimeError("proxy failed")


class _FakeDirectResponse:
    status_code = 200

    def json(self):
        return {
            "choices": [
                {"message": {"content": "Direct aphorism."}},
            ],
        }


class _FakeSession:
    created = []

    def __init__(self):
        self.trust_env = True
        self.posts = []
        self.created.append(self)

    def post(self, url, **kwargs):
        kwargs["url"] = url
        self.posts.append(kwargs)
        return _FakeDirectResponse()


def test_auto_provider_uses_openai_when_key_exists(monkeypatch):
    _reset_fake()
    monkeypatch.setattr(llm_client, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_model", "gpt-test")

    result = llm_client.chat_complete(
        [{"role": "user", "content": "hello"}],
        max_tokens=12,
    )

    assert result == "Generated aphorism."
    assert _FakeOpenAI.init_kwargs[0]["api_key"] == "sk-test"
    assert "base_url" not in _FakeOpenAI.init_kwargs[0]
    assert _FakeOpenAI.calls[0]["model"] == "gpt-test"


def test_auto_provider_uses_direct_openai_after_sdk_failure(monkeypatch):
    _FakeSession.created = []
    monkeypatch.setattr(llm_client, "OpenAI", _FailingOpenAI)
    monkeypatch.setattr(llm_client.requests, "Session", _FakeSession)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")
    monkeypatch.setattr(settings, "openai_model", "gpt-test")

    result = llm_client.chat_complete(
        [{"role": "user", "content": "hello"}],
        max_tokens=12,
    )

    assert result == "Direct aphorism."
    assert _FakeSession.created[0].trust_env is False
    post = _FakeSession.created[0].posts[0]
    assert post["json"]["model"] == "gpt-test"
    assert post["headers"]["Authorization"] == "Bearer sk-test"


def test_auto_provider_uses_local_without_openai_key(monkeypatch):
    _reset_fake()
    monkeypatch.setattr(llm_client, "OpenAI", _FakeOpenAI)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "openai_api_key", None)
    monkeypatch.setattr(settings, "local_llm_base_url", "http://local/v1")
    monkeypatch.setattr(settings, "local_llm_api_key", "local-key")
    monkeypatch.setattr(settings, "local_llm_model", "local-model")

    result = llm_client.chat_complete(
        [{"role": "user", "content": "hello"}],
        max_tokens=12,
    )

    assert result == "Generated aphorism."
    assert _FakeOpenAI.init_kwargs[0]["base_url"] == "http://local/v1"
    assert _FakeOpenAI.init_kwargs[0]["api_key"] == "local-key"
    assert _FakeOpenAI.calls[0]["model"] == "local-model"


def test_auto_provider_does_not_try_local_when_openai_key_exists(monkeypatch):
    monkeypatch.setattr(llm_client, "OpenAI", _FailingOpenAI)
    monkeypatch.setattr(llm_client.requests, "Session", _FakeSession)
    monkeypatch.setattr(settings, "llm_provider", "auto")
    monkeypatch.setattr(settings, "openai_api_key", "sk-test")

    llm_client.chat_complete(
        [{"role": "user", "content": "hello"}],
        max_tokens=12,
    )

    assert llm_client._provider_order() == ["openai", "openai_direct"]
