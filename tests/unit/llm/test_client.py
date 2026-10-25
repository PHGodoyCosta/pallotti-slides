import base64
from pathlib import Path

import anthropic
import httpx
import pytest
from chat_fakes import Out, make_chat, status_error
from langchain_core.messages import AIMessage, HumanMessage

from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.llm.client import (
    NO_KEY_MESSAGE,
    ClaudeClient,
    FakeLLMClient,
    SearchResult,
    load_api_key,
)
from pallotti_slides.llm.errors import LLMError

URL = "https://api.anthropic.com/v1/messages"


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


def _client(chat: object) -> ClaudeClient:
    return ClaudeClient("k", chat_model=chat)  # type: ignore[arg-type]


def test_extract_returns_parsed_and_sends_pdf_block() -> None:
    chat = make_chat(parsed=Out(value="x"), reply=AIMessage("", response_metadata={}))
    result = _client(chat).extract_structured(instruction="i", schema=Out, pdf=b"%PDF-1")
    assert result.value == "x"
    assert chat.schemas[0][0] is Out
    system, human = chat.seen[0]
    assert system.content == "i"
    block = human.content[0]
    assert block["type"] == "file"
    assert block["mime_type"] == "application/pdf"
    assert base64.b64decode(block["base64"]) == b"%PDF-1"


def test_real_chat_model_payload_has_document_effort_and_tool() -> None:
    client = ClaudeClient("k")
    chat = client._chat
    block = {"type": "file", "base64": "AAA", "mime_type": "application/pdf"}
    payload = chat._get_request_payload([HumanMessage(content=[block])])  # type: ignore[attr-defined]
    assert payload["messages"][0]["content"][0]["type"] == "document"
    assert payload["output_config"]["effort"] == "low"
    assert payload["model"] == "claude-opus-5-5"


def test_refusal_and_truncation_become_llm_error() -> None:
    refused = make_chat(reply=AIMessage("", response_metadata={"stop_reason": "refusal"}))
    with pytest.raises(LLMError, match="recusou"):
        _client(refused).extract_structured(instruction="i", schema=Out)
    cut = make_chat(reply=AIMessage("", response_metadata={"stop_reason": "max_tokens"}))
    with pytest.raises(LLMError, match="cortada"):
        _client(cut).extract_structured(instruction="i", schema=Out)
    empty = make_chat(reply=AIMessage("", response_metadata={}))
    with pytest.raises(LLMError, match="formato"):
        _client(empty).extract_structured(instruction="i", schema=Out)


@pytest.mark.parametrize(
    ("error", "fragment"),
    [
        (status_error(anthropic.RateLimitError, 429, URL), "Limite de uso"),
        (status_error(anthropic.AuthenticationError, 401, URL), "chave"),
        (
            anthropic.APIConnectionError(request=httpx.Request("POST", URL)),
            "Sem conexão",
        ),
    ],
)
def test_sdk_errors_are_translated(error: Exception, fragment: str) -> None:
    with pytest.raises(LLMError, match=fragment):
        _client(make_chat(error=error)).extract_structured(instruction="i", schema=Out)
    with pytest.raises(LLMError, match=fragment):
        _client(make_chat(error=error)).search_urls(query="q", domains=["a.com"], max_results=1)


def test_search_urls_filters_domains_and_dedupes() -> None:
    hit = lambda url: {"type": "web_search_result", "url": url, "title": "t"}  # noqa: E731
    blocks = [
        {"type": "text", "text": "texto livre do modelo"},
        {
            "type": "web_search_tool_result",
            "content": [
                hit("https://letras.mus.br/a"),
                hit("https://letras.mus.br/a"),
                hit("https://www.letras.mus.br/b"),
                hit("https://evil.com/c"),
            ],
        },
        {"type": "web_search_tool_result", "content": {"error_code": "x"}},
    ]
    chat = make_chat(reply=AIMessage(blocks, response_metadata={}))  # type: ignore[arg-type]
    found = _client(chat).search_urls(query="q", domains=["letras.mus.br"], max_results=5)
    assert [r.url for r in found] == ["https://letras.mus.br/a", "https://www.letras.mus.br/b"]
    assert found[0].title == "t"
    tool = chat.tools[0]
    assert tool["type"] == "web_search_20260209"
    assert tool["allowed_domains"] == ["letras.mus.br"]
    assert len(_client(chat).search_urls(query="q", domains=["letras.mus.br"], max_results=1)) == 1


def test_search_refusal() -> None:
    chat = make_chat(reply=AIMessage("", response_metadata={"stop_reason": "refusal"}))
    with pytest.raises(LLMError, match="recusou"):
        _client(chat).search_urls(query="q", domains=[], max_results=1)


def test_fake_client_without_recording_fails_friendly(tmp_path: Path) -> None:
    with pytest.raises(LLMError):
        FakeLLMClient(tmp_path).extract_structured(instruction="i", schema=Out, pdf=b"x")


def test_fake_client_by_schema_name_and_search(tmp_path: Path) -> None:
    (tmp_path / "Out.json").write_text('{"response": {"value": "ok"}, "synthetic": true}')
    fake = FakeLLMClient(tmp_path, [SearchResult(url="https://a"), SearchResult(url="https://b")])
    assert fake.extract_structured(instruction="i", schema=Out).value == "ok"
    assert len(fake.search_urls(query="q", domains=[], max_results=1)) == 1
