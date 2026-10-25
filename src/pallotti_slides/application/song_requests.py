"""Use cases around song requests: free text, URL import and repertoire links (F4, F5)."""

from dataclasses import dataclass

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.models import SongRequest
from pallotti_slides.songs.interpreter import RequestInterpreter
from pallotti_slides.songs.parser import detect_request_kind
from pallotti_slides.songs.repertoire import RepertoireImporter, RepertoireProposal
from pallotti_slides.songs.resolver import ResolutionResult, SongResolver

__all__ = [
    "RequestOutcome",
    "ResolutionResult",
    "import_song",
    "propose_repertoire",
    "resolve_text",
]


@dataclass(frozen=True)
class RequestOutcome:
    """A request and how it was resolved."""

    request: SongRequest
    result: ResolutionResult


def resolve_text(
    text: str,
    resolver: SongResolver,
    interpreter: RequestInterpreter,
    moment: SongMoment | None = None,
) -> list[RequestOutcome]:
    """With ``moment``: one request for ``text``. Without: ``text`` is free text (LLM)."""
    if moment is not None:
        requests = [SongRequest(moment=moment, text=text.strip(), kind=detect_request_kind(text))]
    else:
        requests = interpreter.interpret(text)
    return [RequestOutcome(request, resolver.resolve(request)) for request in requests]


def import_song(url: str, resolver: SongResolver) -> ResolutionResult:
    """Download, structure and save the song of ``url`` into the library."""
    return resolver.import_url(url)


def propose_repertoire(url: str, importer: RepertoireImporter) -> RepertoireProposal:
    """Proposal for a repertoire link; it is never applied without the user's confirmation."""
    return importer.load(url)
