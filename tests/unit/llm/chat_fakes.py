"""Offline stand-ins for LangChain chat models (no network)."""

from collections.abc import Callable
from typing import Any

import httpx
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import Runnable, RunnableLambda
from pydantic import BaseModel, Field


class FakeChat(BaseChatModel):
    """Replays ``reply``/``parsed`` (or raises ``error``) and records what it was asked."""

    reply: AIMessage = AIMessage(content="")
    parsed: Any = None
    error: Exception | None = None
    seen: list[Any] = Field(default_factory=list)
    schemas: list[Any] = Field(default_factory=list)
    tools: list[Any] = Field(default_factory=list)
    tool_kwargs: dict[str, Any] = Field(default_factory=dict)

    @property
    def _llm_type(self) -> str:
        return "fake-chat"

    def _generate(self, messages: list[BaseMessage], *args: Any, **kwargs: Any) -> ChatResult:
        self.seen.append(messages)
        if self.error:
            raise self.error
        return ChatResult(generations=[ChatGeneration(message=self.reply)])

    def bind_tools(self, tools: Any, **kwargs: Any) -> Runnable[Any, Any]:  # type: ignore[override]
        self.tools.extend(tools)
        self.tool_kwargs.update(kwargs)
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any) -> Runnable[Any, Any]:  # type: ignore[override]
        self.schemas.append((schema, kwargs))

        def run(messages: Any) -> dict[str, Any]:
            self.seen.append(messages)
            if self.error:
                raise self.error
            return {"raw": self.reply, "parsed": self.parsed, "parsing_error": None}

        return RunnableLambda(run)


def make_chat(**fields: Any) -> FakeChat:
    """A fresh ``FakeChat``."""
    return FakeChat(**fields)


def status_error(cls: Callable[..., Exception], code: int, url: str) -> Exception:
    request = httpx.Request("POST", url)
    return cls("x", response=httpx.Response(code, request=request), body=None)


class Out(BaseModel):
    value: str | None = None
