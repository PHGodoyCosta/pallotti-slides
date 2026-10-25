"""Fakes shared by the song tests (no network)."""

from pydantic import BaseModel

from pallotti_slides.domain.enums import SongSource
from pallotti_slides.llm.client import SearchResult
from pallotti_slides.llm.errors import LLMError
from pallotti_slides.songs.downloaders import DownloadError, RawLyrics


class FakeDownloader:
    """Serves ``pages`` (url -> RawLyrics) and counts calls."""

    def __init__(self, pages: dict[str, RawLyrics], fail: bool = False) -> None:
        self.pages = pages
        self.fail = fail
        self.calls: list[str] = []

    def supports(self, url: str) -> bool:
        return "letras.mus.br" in url or "cifraclub.com.br" in url

    def download(self, url: str) -> RawLyrics:
        self.calls.append(url)
        if self.fail:
            raise DownloadError("Sem conexão.")
        return self.pages[url]


class FakeLLM:
    """Records calls; ``answer`` is returned by ``extract_structured``."""

    def __init__(
        self,
        answer: BaseModel | None = None,
        results: list[SearchResult] | None = None,
        fail: bool = False,
    ) -> None:
        self.answer = answer
        self.results = results or []
        self.fail = fail
        self.search_calls: list[dict[str, object]] = []
        self.extract_calls: list[str | None] = []

    def extract_structured[T: BaseModel](
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T:
        self.extract_calls.append(text)
        if self.fail or self.answer is None:
            raise LLMError("Sem chave.")
        assert isinstance(self.answer, schema)
        return self.answer

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        self.search_calls.append({"query": query, "domains": domains, "max": max_results})
        if self.fail:
            raise LLMError("Sem rede.")
        return self.results[:max_results]


def raw(title: str, url: str, text: str, artist: str | None = "Autor") -> RawLyrics:
    return RawLyrics(title=title, artist=artist, text=text, source=SongSource.LETRAS_MUS, url=url)
