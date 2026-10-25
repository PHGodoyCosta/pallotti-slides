from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import openai
import pytest
from pydantic import BaseModel

from pallotti_slides.config import Settings
from pallotti_slides.llm.client import ClaudeClient, create_llm_client, no_key_message
from pallotti_slides.llm.errors import LLMError
from pallotti_slides.llm.openai_client import OpenAIClient


class Out(BaseModel):
    value: str | None = None


class _Responses:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error, self.kwargs = response, error, {}

    def parse(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response

    create = parse


def _client(responses: _Responses) -> OpenAIClient:
    return OpenAIClient("k", client=SimpleNamespace(responses=responses))


def _message(*parts: Any) -> Any:
    return SimpleNamespace(type="message", content=list(parts))


def test_extract_sends_pdf_as_input_file_and_schema() -> None:
    responses = _Responses(
        SimpleNamespace(status="completed", output=[], output_parsed=Out(value="x"))
    )
    result = _client(responses).extract_structured(instruction="i", schema=Out, pdf=b"%PDF-1")
    assert result.value == "x"
    block = responses.kwargs["input"][0]["content"][0]
    assert block["type"] == "input_file"
    assert block["detail"] == "high"
    assert block["file_data"].startswith("data:application/pdf;base64,")
    assert responses.kwargs["text_format"] is Out
    assert responses.kwargs["instructions"] == "i"
    assert responses.kwargs["model"] == "gpt-6-astra"


def test_refusal_and_incomplete_become_llm_error() -> None:
    refusal = _message(SimpleNamespace(type="refusal"))
    responses = _Responses(
        SimpleNamespace(status="completed", output=[refusal], output_parsed=None)
    )
    with pytest.raises(LLMError, match="recusou"):
        _client(responses).extract_structured(instruction="i", schema=Out)
    cut = _Responses(SimpleNamespace(status="incomplete", output=[], output_parsed=None))
    with pytest.raises(LLMError, match="cortada"):
        _client(cut).extract_structured(instruction="i", schema=Out)
    empty = _Responses(SimpleNamespace(status="completed", output=[], output_parsed=None))
    with pytest.raises(LLMError, match="formato"):
        _client(empty).extract_structured(instruction="i", schema=Out)


def _status_error(cls: type[openai.APIStatusError], code: int) -> openai.APIStatusError:
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return cls("x", response=httpx.Response(code, request=request), body=None)


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (_status_error(openai.RateLimitError, 429), "Limite de uso"),
        (_status_error(openai.AuthenticationError, 401), "chave"),
        (_status_error(openai.InternalServerError, 500), "código 500"),
        (
            openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com")),
            "Sem conexão",
        ),
    ],
)
def test_sdk_errors_are_translated(error: Exception, fragment: str) -> None:
    with pytest.raises(LLMError, match=fragment) as info:
        _client(_Responses(error=error)).extract_structured(instruction="i", schema=Out)
    assert "sk-" not in str(info.value)


def test_search_urls_uses_allowed_domains_and_dedupes() -> None:
    def source(url: str) -> Any:
        return SimpleNamespace(type="url", url=url)

    call = SimpleNamespace(
        type="web_search_call",
        action=SimpleNamespace(sources=[source("https://a"), source("https://a")]),
    )
    note = SimpleNamespace(type="url_citation", url="https://b", title="B")
    output = [call, _message(SimpleNamespace(type="output_text", annotations=[note]))]
    responses = _Responses(SimpleNamespace(output=output))
    found = _client(responses).search_urls(query="q", domains=["letras.mus.br"], max_results=5)
    assert [r.url for r in found] == ["https://a", "https://b"]
    assert found[1].title == "B"
    tool = responses.kwargs["tools"][0]
    assert tool == {"type": "web_search", "filters": {"allowed_domains": ["letras.mus.br"]}}
    assert len(_client(responses).search_urls(query="q", domains=[], max_results=1)) == 1


def test_factory_chooses_provider() -> None:
    env = {"OPENAI_API_KEY": "o", "ANTHROPIC_API_KEY": "a"}
    none = lambda _p: None  # noqa: E731
    assert isinstance(create_llm_client(Settings(), env, none), OpenAIClient)
    anthropic_settings = Settings(llm_provider="anthropic")
    assert isinstance(create_llm_client(anthropic_settings, env, none), ClaudeClient)


def test_factory_keyring_is_per_provider() -> None:
    asked: list[str] = []

    def keyring_get(provider: str) -> str | None:
        asked.append(provider)
        return "kr"

    create_llm_client(Settings(llm_provider="anthropic"), {}, keyring_get)
    assert asked == ["anthropic"]


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_factory_without_key_is_friendly(provider: str) -> None:
    with pytest.raises(LLMError) as info:
        create_llm_client(Settings(llm_provider=provider), {}, lambda _p: None)
    assert str(info.value) == no_key_message(provider)
    assert "Configurações" in str(info.value)


def test_factory_unknown_provider() -> None:
    with pytest.raises(LLMError, match="desconhecido"):
        create_llm_client(Settings(llm_provider="x"), {}, lambda _p: None)


def test_settings_round_trip(tmp_path: Path) -> None:
    from pallotti_slides.config import load_settings, save_settings

    path = tmp_path / "sub" / "config.json"
    assert load_settings(path) == Settings()
    assert Settings().llm_provider == "openai"
    saved = Settings(llm_provider="anthropic", openai_model="m")
    save_settings(saved, path)
    assert load_settings(path) == saved
    assert "key" not in path.read_text()
    path.write_text("{lixo")
    assert load_settings(path) == Settings()
