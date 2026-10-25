"""``LLMClient`` backed by LangChain ``ChatOpenAI`` (Responses API; ARQUITETURA §8).

The model never writes lyrics or liturgical text: it extracts, returns URLs and
classifies by id (CLAUDE.md, rule 1).
"""

import base64
import logging
from typing import Any

import openai
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from pallotti_slides.llm.client import (
    DEFAULT_TEXT,
    SEARCH_PROMPT,
    SearchResult,
    T,
    collect_results,
    content_blocks,
    pick,
)
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
    """``LLMClient`` backed by LangChain's ``ChatOpenAI`` (Responses API)."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        effort: str = "low",
        chat_model: BaseChatModel | None = None,
    ) -> None:
        self._chat: BaseChatModel = (
            chat_model
            if chat_model is not None
            else ChatOpenAI(
                model=model,
                api_key=SecretStr(api_key),
                use_responses_api=True,
                output_version="responses/v1",
                reasoning_effort=effort,
                max_completion_tokens=8192,
                store=False,
            )
        )

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
                    "type": "file",
                    "file": {
                        "filename": "folheto.pdf",
                        "file_data": f"data:application/pdf;base64,{data}",
                        "detail": "high",  # scanned leaflets need full-quality rendering
                    },
                }
            )
        content.append({"type": "text", "text": text or DEFAULT_TEXT})
        messages = [SystemMessage(instruction), HumanMessage(content=content)]  # type: ignore[arg-type]
        try:
            runnable = self._chat.with_structured_output(
                schema, method="json_schema", include_raw=True
            )
            out: dict[str, Any] = runnable.invoke(messages)  # type: ignore[assignment]
        except Exception as error:
            _log.warning("Falha na chamada ao LLM: %s", type(error).__name__)
            raise _translate_error(error) from error
        raw = out["raw"]
        if (getattr(raw, "response_metadata", None) or {}).get("status") == "incomplete":
            raise LLMError("A resposta do modelo foi cortada antes de terminar. Tente de novo.")
        parsed = out["parsed"]
        if not isinstance(parsed, schema):
            if _has_refusal(raw):
                raise LLMError("O modelo se recusou a processar este arquivo.")
            raise LLMError("O modelo não devolveu uma resposta no formato esperado.")
        return parsed

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        tool = {"type": "web_search", "filters": {"allowed_domains": domains}}
        try:
            response = self._chat.bind_tools(
                [tool], include=["web_search_call.action.sources"], max_tool_calls=3
            ).invoke(SEARCH_PROMPT.format(query=query))
        except Exception as error:
            _log.warning("Falha na busca web: %s", type(error).__name__)
            raise _translate_error(error) from error
        if _has_refusal(response):
            raise LLMError("O modelo se recusou a fazer esta busca.")
        hits: list[tuple[str, str]] = []
        for block in content_blocks(response):
            kind = pick(block, "type")
            if kind == "web_search_call":
                action = pick(block, "action")
                hits.extend((pick(s, "url") or "", "") for s in pick(action, "sources") or [])
            elif kind == "text":
                hits.extend(
                    (pick(n, "url") or "", pick(n, "title") or "")
                    for n in pick(block, "annotations") or []
                    if pick(n, "type") == "url_citation"
                )
        return collect_results(hits, domains, max_results)


def _has_refusal(message: Any) -> bool:
    return any(pick(block, "type") == "refusal" for block in content_blocks(message))
