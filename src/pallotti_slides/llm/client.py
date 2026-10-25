"""LLM access (ARQUITETURA §8). The only module that imports ``anthropic``.

The model never writes lyrics or liturgical text: it extracts, returns URLs and
classifies by id (CLAUDE.md, rule 1).
"""

import base64
import hashlib
import json
import logging
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any, Protocol, TypeVar

import anthropic
from pydantic import BaseModel

from pallotti_slides.llm.errors import LLMError

T = TypeVar("T", bound=BaseModel)

DEFAULT_MODEL = "claude-opus-5-5"
KEYRING_SERVICE = "PallottiSlides"
KEYRING_USER = "anthropic_api_key"
API_KEY_VAR = "ANTHROPIC_API_KEY"
WEB_SEARCH_TOOL = "web_search_20260209"

NO_KEY_MESSAGE = (
    "A chave da API da Anthropic não está configurada. Informe a chave nas "
    "Configurações do programa (ou defina ANTHROPIC_API_KEY). Sem ela, a extração "
    "automática do folheto fica desligada; o preenchimento manual continua funcionando."
)

_log = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """One web search hit."""

    url: str
    title: str = ""


class LLMClient(Protocol):
    """What the rest of the program needs from a language model."""

    def extract_structured(
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T: ...

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]: ...


def _keyring_get() -> str | None:
    """Read the key saved in the OS keyring (``None`` if unavailable)."""
    try:
        import keyring

        value = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:  # keyring backends fail in many ways (no backend, locked...)
        return None
    return value or None


def load_api_key(
    env: Mapping[str, str] | None = None,
    keyring_get: Callable[[], str | None] | None = None,
) -> str | None:
    """API key from the keyring, falling back to ``ANTHROPIC_API_KEY`` (development)."""
    key = (keyring_get or _keyring_get)()
    if key:
        return key
    value = (os.environ if env is None else env).get(API_KEY_VAR, "").strip()
    return value or None


def _translate_error(error: Exception) -> LLMError:
    """Turn an SDK exception into a user-facing ``LLMError`` (never logs the key)."""
    if isinstance(error, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        return LLMError(
            "A chave da API da Anthropic foi recusada. Confira a chave nas Configurações."
        )
    if isinstance(error, anthropic.RateLimitError):
        return LLMError("Limite de uso da API atingido. Aguarde um pouco e tente de novo.")
    if isinstance(error, anthropic.APITimeoutError):
        return LLMError("A API da Anthropic demorou demais para responder. Tente de novo.")
    if isinstance(error, anthropic.APIConnectionError):
        return LLMError("Sem conexão com a API da Anthropic. Verifique a internet e tente de novo.")
    if isinstance(error, anthropic.APIStatusError) and error.status_code == 413:
        return LLMError("O PDF é grande demais para ser enviado.")
    if isinstance(error, anthropic.BadRequestError):
        return LLMError("A API não aceitou o arquivo enviado. Confira se é um PDF válido.")
    if isinstance(error, anthropic.APIStatusError):
        return LLMError(
            f"A API da Anthropic está com problemas (código {error.status_code}). "
            "Tente de novo em instantes."
        )
    return LLMError("Falha inesperada ao falar com a API da Anthropic.")


class ClaudeClient:
    """``LLMClient`` backed by the ``anthropic`` SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        effort: str = "low",
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._effort = effort
        self._client: Any = client if client is not None else anthropic.Anthropic(api_key=api_key)

    @classmethod
    def from_environment(
        cls,
        model: str = DEFAULT_MODEL,
        env: Mapping[str, str] | None = None,
        keyring_get: Callable[[], str | None] | None = None,
    ) -> "ClaudeClient":
        """Build with the stored key; ``LLMError`` (in Portuguese) when there is none."""
        key = load_api_key(env, keyring_get)
        if key is None:
            raise LLMError(NO_KEY_MESSAGE)
        return cls(key, model=model)

    def extract_structured(
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T:
        content: list[dict[str, Any]] = []
        if pdf is not None:
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.standard_b64encode(pdf).decode("ascii"),
                    },
                }
            )
        content.append({"type": "text", "text": text or "Extraia os dados conforme as instruções."})
        try:
            response = self._client.messages.parse(
                model=self._model,
                max_tokens=4096,
                system=instruction,
                messages=[{"role": "user", "content": content}],
                output_format=schema,
                output_config={"effort": self._effort},
            )
        except anthropic.AnthropicError as error:
            _log.warning("Falha na chamada ao LLM: %s", type(error).__name__)
            raise _translate_error(error) from error
        if response.stop_reason == "refusal":
            raise LLMError("O modelo se recusou a processar este arquivo.")
        if response.stop_reason == "max_tokens":
            raise LLMError("A resposta do modelo foi cortada antes de terminar. Tente de novo.")
        parsed = response.parsed_output
        if parsed is None:
            raise LLMError("O modelo não devolveu uma resposta no formato esperado.")
        return parsed  # type: ignore[no-any-return]

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        tool = {
            "type": WEB_SEARCH_TOOL,
            "name": "web_search",
            "allowed_domains": domains,
            "max_uses": 3,
        }
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": f"Busque nos sites permitidos: {query}. Não escreva letras.",
                    }
                ],
                tools=[tool],
                output_config={"effort": self._effort},
            )
        except anthropic.AnthropicError as error:
            _log.warning("Falha na busca web: %s", type(error).__name__)
            raise _translate_error(error) from error
        if response.stop_reason == "refusal":
            raise LLMError("O modelo se recusou a fazer esta busca.")
        results: list[SearchResult] = []
        seen: set[str] = set()
        for block in response.content:
            if getattr(block, "type", None) != "web_search_tool_result":
                continue
            hits = block.content
            if not isinstance(hits, list):  # error payload
                continue
            for hit in hits:
                if hit.url not in seen:
                    seen.add(hit.url)
                    results.append(SearchResult(url=hit.url, title=hit.title or ""))
        return results[:max_results]


class FakeLLMClient:
    """Offline ``LLMClient`` that replays recorded responses.

    ``extract_structured`` looks for ``<sha256 of the PDF>.json`` in ``directory``
    (falling back to ``<schema name>.json``). The file holds the response either
    directly or under a ``"response"`` key (the other keys are metadata, such as
    ``"synthetic": true``). Every call is appended to ``calls``.
    """

    def __init__(
        self,
        directory: Path,
        search_results: list[SearchResult] | None = None,
    ) -> None:
        self._directory = directory
        self._search_results = search_results or []
        self.calls: list[dict[str, Any]] = []

    def extract_structured(
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T:
        self.calls.append({"instruction": instruction, "schema": schema, "pdf": pdf, "text": text})
        names = [f"{schema.__name__}.json"]
        if pdf is not None:
            names.insert(0, f"{hashlib.sha256(pdf).hexdigest()}.json")
        for name in names:
            path = self._directory / name
            if path.is_file():
                raw = path.read_text(encoding="utf-8")
                return _load_recorded(raw, schema)
        raise LLMError("Não há resposta gravada para esta chamada (LLM falso).")

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        self.calls.append({"query": query, "domains": domains, "max_results": max_results})
        return self._search_results[:max_results]


def _load_recorded[M: BaseModel](raw: str, schema: type[M]) -> M:
    data = json.loads(raw)
    if isinstance(data, dict) and "response" in data:
        data = data["response"]
    return schema.model_validate(data)
