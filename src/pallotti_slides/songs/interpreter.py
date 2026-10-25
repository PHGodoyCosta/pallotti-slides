"""Free text -> ``SongRequest`` per moment (F4). The LLM only classifies; it never writes lyrics."""

from pydantic import BaseModel

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import SongRequest
from pallotti_slides.llm.client import LLMClient
from pallotti_slides.songs.parser import detect_request_kind

__all__ = ["InterpretedRequest", "InterpretedRequests", "RequestInterpreter"]


class InterpretedRequest(BaseModel):
    """One piece of the free text: the moment and exactly what the user wrote for it."""

    moment: SongMoment
    text: str


class InterpretedRequests(BaseModel):
    """Structured answer of the LLM."""

    requests: list[InterpretedRequest]


def _instruction() -> str:
    moments = "\n".join(f"- {moment.value}: {moment.label}" for moment in SongMoment)
    return (
        "O usuário descreve os cantos de uma missa em texto livre (por exemplo "
        '"Entrada: Me chamaste; Ofertório: https://...; Comunhão: Pão da vida"). '
        "Para cada canto mencionado, devolva em requests o momento e o texto que o usuário "
        "escreveu para ele (um título, um trecho, uma URL ou uma letra colada), copiado "
        "exatamente como veio. Não escreva, complete nem corrija letras e não invente cantos. "
        "Ignore momentos sem canto. Momentos válidos (use o identificador):\n" + moments
    )


class RequestInterpreter:
    """Turns pasted free text into one ``SongRequest`` per moment."""

    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    def interpret(self, free_text: str) -> list[SongRequest]:
        """Requests in the order of the Mass; the last text given for a moment wins."""
        if not free_text.strip():
            return []
        answer = self._llm.extract_structured(
            instruction=_instruction(), schema=InterpretedRequests, text=free_text
        )
        by_moment: dict[SongMoment, SongRequest] = {}
        for item in answer.requests:
            text = item.text.strip()
            if text:
                by_moment[item.moment] = SongRequest(
                    moment=item.moment, text=text, kind=detect_request_kind(text)
                )
        return [by_moment[moment] for moment in SongMoment if moment in by_moment]
