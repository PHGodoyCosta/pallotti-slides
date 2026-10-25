"""``LLMClient`` backed by the ``openai`` SDK (Responses API; ARQUITETURA §8).

The model never writes lyrics or liturgical text: it extracts, returns URLs and
classifies by id (CLAUDE.md, rule 1).
"""

import base64
import logging
from typing import Any

import openai

from pallotti_slides.llm.client import SearchResult, T
from pallotti_slides.llm.errors import LLMError

DEFAULT_MODEL = "gpt-6-astra"

_log = logging.getLogger(__name__)


def _translate_error(error: Exception) -> LLMError:
    """Turn an SDK exception into a user-facing ``LLMError`` (never logs the key)."""
    if isinstance(error, openai.AuthenticationError | openai.PermissionDeniedError):
        return LLMError("A chave da API da OpenAI foi recusada. Confira a chave nas Configurações.")
    if isinstance(error, openai.RateLimitError):
        return LLMError("Limite de uso da API atingido. Aguarde um pouco e tente de novo.")
    if isinstance(error, openai.APITimeoutError):
        return LLMError("A API da OpenAI demorou demais para responder. Tente de novo.")
    if isinstance(error, openai.APIConnectionError):
        return LLMError("Sem conexão com a API da OpenAI. Verifique a internet e tente de novo.")
    if isinstance(error, openai.APIStatusError) and error.status_code == 413:
        return LLMError("O PDF é grande demais para ser enviado.")
    if isinstance(error, openai.BadRequestError):
        return LLMError("A API não aceitou o arquivo enviado. Confira se é um PDF válido.")
    if isinstance(error, openai.APIStatusError):
        return LLMError(
            f"A API da OpenAI está com problemas (código {error.status_code}). "
            "Tente de novo em instantes."
        )
    if isinstance(error, openai.LengthFinishReasonError):
        return LLMError("A resposta do modelo foi cortada antes de terminar. Tente de novo.")
    if isinstance(error, openai.ContentFilterFinishReasonError):
        return LLMError("O modelo se recusou a processar este arquivo.")
    return LLMError("Falha inesperada ao falar com a API da OpenAI.")


class OpenAIClient:
    """``LLMClient`` using ``responses.parse`` and the ``web_search`` tool."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        effort: str = "low",
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._effort = effort
        self._client: Any = client if client is not None else openai.OpenAI(api_key=api_key)

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
            data = base64.standard_b64encode(pdf).decode("ascii")
            content.append(
                {
                    "type": "input_file",
                    "filename": "folheto.pdf",
                    "file_data": f"data:application/pdf;base64,{data}",
                    "detail": "high",  # scanned leaflets need full-quality rendering
                }
            )
        content.append(
            {"type": "input_text", "text": text or "Extraia os dados conforme as instruções."}
        )
        try:
            response = self._client.responses.parse(
                model=self._model,
                instructions=instruction,
                input=[{"role": "user", "content": content}],
                text_format=schema,
                reasoning={"effort": self._effort},
                max_output_tokens=8192,
                store=False,
            )
        except (openai.OpenAIError, openai.LengthFinishReasonError) as error:
            _log.warning("Falha na chamada ao LLM: %s", type(error).__name__)
            raise _translate_error(error) from error
        if getattr(response, "status", None) == "incomplete":
            raise LLMError("A resposta do modelo foi cortada antes de terminar. Tente de novo.")
        parsed = response.output_parsed
        if parsed is None:
            if _has_refusal(response):
                raise LLMError("O modelo se recusou a processar este arquivo.")
            raise LLMError("O modelo não devolveu uma resposta no formato esperado.")
        return parsed  # type: ignore[no-any-return]

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        tool = {"type": "web_search", "filters": {"allowed_domains": domains}}
        try:
            response = self._client.responses.create(
                model=self._model,
                input=f"Busque nos sites permitidos: {query}. Não escreva letras.",
                tools=[tool],
                include=["web_search_call.action.sources"],
                reasoning={"effort": self._effort},
                max_tool_calls=3,
                max_output_tokens=4096,
                store=False,
            )
        except openai.OpenAIError as error:
            _log.warning("Falha na busca web: %s", type(error).__name__)
            raise _translate_error(error) from error
        if _has_refusal(response):
            raise LLMError("O modelo se recusou a fazer esta busca.")
        results: list[SearchResult] = []
        seen: set[str] = set()

        def add(url: str, title: str = "") -> None:
            if url not in seen:
                seen.add(url)
                results.append(SearchResult(url=url, title=title))

        for item in response.output:
            kind = getattr(item, "type", None)
            if kind == "web_search_call":
                for source in getattr(getattr(item, "action", None), "sources", None) or []:
                    add(source.url)
            elif kind == "message":
                for part in item.content:
                    for note in getattr(part, "annotations", None) or []:
                        if getattr(note, "type", None) == "url_citation":
                            add(note.url, note.title or "")
        return results[:max_results]


def _has_refusal(response: Any) -> bool:
    for item in getattr(response, "output", None) or []:
        if getattr(item, "type", None) == "message":
            for part in item.content:
                if getattr(part, "type", None) == "refusal":
                    return True
    return False
