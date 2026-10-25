import base64
from pathlib import Path

import httpx
import openai
import pytest
from chat_fakes import Out, make_chat, status_error
from langchain_core.messages import AIMessage, HumanMessage

from pallotti_slides.config import Settings
from pallotti_slides.llm.client import ClaudeClient, create_llm_client, no_key_message
from pallotti_slides.llm.errors import LLMError
from pallotti_slides.llm.openai_client import OpenAIClient

URL = "https://api.openai.com/v1/responses"


def _client(chat: object) -> OpenAIClient:
    return OpenAIClient("k", chat_model=chat)  # type: ignore[arg-type]


def test_extract_returns_parsed_and_sends_pdf_file_block() -> None:
    chat = make_chat(parsed=Out(value="x"), reply=AIMessage("", response_metadata={}))
    result = _client(chat).extract_structured(instruction="i", schema=Out, pdf=b"%PDF-1")
    assert result.value == "x"
    assert chat.schemas[0][0] is Out
    block = chat.seen[0][1].content[0]
    assert block["type"] == "file"
    assert block["file"]["detail"] == "high"
    assert block["file"]["file_data"].startswith("data:application/pdf;base64,")
    assert base64.b64decode(block["file"]["file_data"].split(",", 1)[1]) == b"%PDF-1"


def test_real_chat_model_payload_is_responses_input_file() -> None:
    chat = OpenAIClient("k")._chat
    block = {"type": "file", "file": {"filename": "f.pdf", "file_data": "data:x", "detail": "high"}}
    payload = chat._get_request_payload([HumanMessage(content=[block])])  # type: ignore[attr-defined]
    part = payload["input"][0]["content"][0]
    assert part == {
        "type": "input_file",
        "filename": "f.pdf",
        "file_data": "data:x",
        "detail": "high",
    }
    assert payload["reasoning"] == {"effort": "low"}
    assert payload["store"] is False
    assert payload["model"] == "gpt-6-astra"


def test_refusal_incomplete_and_empty_become_llm_error() -> None:
    refusal = make_chat(reply=AIMessage([{"type": "refusal", "refusal": "no"}]))  # type: ignore[arg-type]
    with pytest.raises(LLMError, match="recusou"):
        _client(refusal).extract_structured(instruction="i", schema=Out)
    cut = make_chat(reply=AIMessage("", response_metadata={"status": "incomplete"}))
    with pytest.raises(LLMError, match="cortada"):
        _client(cut).extract_structured(instruction="i", schema=Out)
    empty = make_chat(reply=AIMessage("", response_metadata={}))
    with pytest.raises(LLMError, match="formato"):
        _client(empty).extract_structured(instruction="i", schema=Out)


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (status_error(openai.RateLimitError, 429, URL), "Limite de uso"),
        (status_error(openai.AuthenticationError, 401, URL), "chave"),
        (status_error(openai.InternalServerError, 500, URL), "código 500"),
        (openai.APIConnectionError(request=httpx.Request("POST", URL)), "Sem conexão"),
    ],
)
def test_sdk_errors_are_translated(error: Exception, fragment: str) -> None:
    with pytest.raises(LLMError, match=fragment) as info:
        _client(make_chat(error=error)).extract_structured(instruction="i", schema=Out)
    assert "sk-" not in str(info.value)
    with pytest.raises(LLMError, match=fragment):
        _client(make_chat(error=error)).search_urls(query="q", domains=["a.com"], max_results=1)


def test_search_urls_filters_domains_and_dedupes() -> None:
    sources = [
        {"type": "url", "url": "https://cifraclub.com.br/a"},
        {"type": "url", "url": "https://evil.com/x"},
    ]
    blocks = [
        {"type": "web_search_call", "action": {"type": "search", "sources": sources}},
        {
            "type": "text",
            "text": "texto livre do modelo",
            "annotations": [
                {"type": "url_citation", "url": "https://cifraclub.com.br/a", "title": "A"},
                {"type": "url_citation", "url": "https://www.cifraclub.com.br/b", "title": "B"},
            ],
        },
    ]
    chat = make_chat(reply=AIMessage(blocks))  # type: ignore[arg-type]
    found = _client(chat).search_urls(query="q", domains=["cifraclub.com.br"], max_results=5)
    assert [r.url for r in found] == [
        "https://cifraclub.com.br/a",
        "https://www.cifraclub.com.br/b",
    ]
    assert chat.tools[0] == {
        "type": "web_search",
        "filters": {"allowed_domains": ["cifraclub.com.br"]},
    }
    assert chat.tool_kwargs["include"] == ["web_search_call.action.sources"]


def test_search_refusal() -> None:
    chat = make_chat(reply=AIMessage([{"type": "refusal", "refusal": "no"}]))  # type: ignore[arg-type]
    with pytest.raises(LLMError, match="recusou"):
        _client(chat).search_urls(query="q", domains=[], max_results=1)


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
