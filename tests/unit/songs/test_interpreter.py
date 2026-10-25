import pytest

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.llm.errors import LLMError
from pallotti_slides.songs.interpreter import (
    InterpretedRequest,
    InterpretedRequests,
    RequestInterpreter,
)

from .fakes import FakeLLM

TEXT = "Entrada: Me chamaste; Ofertório: https://www.letras.mus.br/a/b/; Comunhão: Pão da vida"


def answer(*items: tuple[SongMoment, str]) -> InterpretedRequests:
    return InterpretedRequests(requests=[InterpretedRequest(moment=m, text=t) for m, t in items])


def test_example_fills_the_right_moments_with_detected_kinds() -> None:
    llm = FakeLLM(
        answer(
            (SongMoment.COMMUNION, "Pão da vida"),
            (SongMoment.ENTRANCE, "Me chamaste"),
            (SongMoment.OFFERTORY, "https://www.letras.mus.br/a/b/"),
        )
    )
    requests = RequestInterpreter(llm).interpret(TEXT)
    assert [(r.moment, r.kind) for r in requests] == [
        (SongMoment.ENTRANCE, "title"),
        (SongMoment.OFFERTORY, "url"),
        (SongMoment.COMMUNION, "title"),
    ]
    assert llm.extract_calls == [TEXT]


def test_pasted_lyrics_are_kind_lyrics_and_empty_texts_dropped() -> None:
    llm = FakeLLM(answer((SongMoment.ENTRANCE, "a\nb\nc"), (SongMoment.GLORIA, "  ")))
    requests = RequestInterpreter(llm).interpret("x")
    assert [(r.moment, r.kind) for r in requests] == [(SongMoment.ENTRANCE, "lyrics")]


def test_blank_text_does_not_call_the_llm() -> None:
    llm = FakeLLM(answer())
    assert RequestInterpreter(llm).interpret("   ") == []
    assert llm.extract_calls == []


def test_llm_failure_propagates_as_llm_error() -> None:
    with pytest.raises(LLMError):
        RequestInterpreter(FakeLLM(fail=True)).interpret("Entrada: x")
