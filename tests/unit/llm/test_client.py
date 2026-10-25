from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx
import pytest
from pydantic import BaseModel

from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.llm.client import (
    NO_KEY_MESSAGE,
    ClaudeClient,
    FakeLLMClient,
    SearchResult,
    load_api_key,
)
from pallotti_slides.llm.errors import LLMError


class Out(BaseModel):
    value: str | None = None


def test_key_from_keyring_wins() -> None:
    assert load_api_key({"ANTHROPIC_API_KEY": "env"}, lambda: "kr") == "kr"


def test_key_from_env_and_none() -> None:
    assert load_api_key({"ANTHROPIC_API_KEY": " env "}, lambda: None) == "env"
    assert load_api_key({}, lambda: None) is None


def test_no_key_gives_friendly_error() -> None:
    with pytest.raises(LLMError) as info:
        ClaudeClient.from_environment(env={}, keyring_get=lambda: None)
    assert str(info.value) == NO_KEY_MESSAGE
    assert isinstance(info.value, PallottiError)


class _Messages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error, self.kwargs = response, error, {}

    def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response

    create = parse


def _client(messages: _Messages) -> ClaudeClient:
    return ClaudeClient("k", client=SimpleNamespace(messages=messages))


def test_extract_sends_pdf_document_and_schema() -> None:
    messages = _Messages(SimpleNamespace(stop_reason="end_turn", parsed_output=Out(value="x")))
    result = _client(messages).extract_structured(instruction="i", schema=Out, pdf=b"%PDF-1")
    assert result.value == "x"
    block = messages.kwargs["messages"][0]["content"][0]
    assert block["type"] == "document"
    assert block["source"]["media_type"] == "application/pdf"
    assert messages.kwargs["output_format"] is Out
    assert messages.kwargs["model"] == "claude-opus-5-5"


def test_refusal_becomes_llm_error() -> None:
    messages = _Messages(SimpleNamespace(stop_reason="refusal", parsed_output=None))
    with pytest.raises(LLMError, match="recusou"):
        _client(messages).extract_structured(instruction="i", schema=Out)


def _status_error(cls: type[anthropic.APIStatusError], code: int) -> anthropic.APIStatusError:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("x", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (_status_error(anthropic.RateLimitError, 429), "Limite de uso"),
        (_status_error(anthropic.AuthenticationError, 401), "chave"),
        (
            anthropic.APIConnectionError(
                request=httpx.Request("POST", "https://api.anthropic.com")
            ),
            "Sem conexão",
        ),
    ],
)
def test_sdk_errors_are_translated(error: Exception, fragment: str) -> None:
    with pytest.raises(LLMError, match=fragment):
        _client(_Messages(error=error)).extract_structured(instruction="i", schema=Out)


def test_search_urls_uses_allowed_domains_and_dedupes() -> None:
    hit = lambda url: SimpleNamespace(url=url, title="t")  # noqa: E731
    blocks = [
        SimpleNamespace(type="text"),
        SimpleNamespace(
            type="web_search_tool_result",
            content=[hit("https://a"), hit("https://a"), hit("https://b")],
        ),
        SimpleNamespace(type="web_search_tool_result", content=SimpleNamespace(error_code="x")),
    ]
    messages = _Messages(SimpleNamespace(stop_reason="end_turn", content=blocks))
    found = _client(messages).search_urls(query="q", domains=["letras.mus.br"], max_results=5)
    assert [r.url for r in found] == ["https://a", "https://b"]
    tool = messages.kwargs["tools"][0]
    assert tool["type"] == "web_search_20260209"
    assert tool["allowed_domains"] == ["letras.mus.br"]


def test_fake_client_without_recording_fails_friendly(tmp_path: Path) -> None:
    with pytest.raises(LLMError):
        FakeLLMClient(tmp_path).extract_structured(instruction="i", schema=Out, pdf=b"x")


def test_fake_client_by_schema_name_and_search(tmp_path: Path) -> None:
    (tmp_path / "Out.json").write_text('{"response": {"value": "ok"}, "synthetic": true}')
    fake = FakeLLMClient(tmp_path, [SearchResult(url="https://a"), SearchResult(url="https://b")])
    assert fake.extract_structured(instruction="i", schema=Out).value == "ok"
    assert len(fake.search_urls(query="q", domains=[], max_results=1)) == 1
