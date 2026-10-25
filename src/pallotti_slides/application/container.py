"""Dependency container: wires the real implementations (ARQUITETURA §10)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel

from pallotti_slides.application.generate_mass import MassGenerator
from pallotti_slides.application.prepare_mass import MassPreparer, ResolverAdapter
from pallotti_slides.config import (
    FontLocator,
    Paths,
    Settings,
    TypographyConfig,
    default_db_url,
)
from pallotti_slides.db.repositories import MassRepository, SongRepository
from pallotti_slides.db.session import apply_migrations, make_engine, session_factory
from pallotti_slides.leaflet.extractor import LeafletExtractor
from pallotti_slides.llm.client import LLMClient, SearchResult, create_llm_client
from pallotti_slides.presentation.builder import PptxBuilder
from pallotti_slides.presentation.measurer import TextMeasurer
from pallotti_slides.presentation.paginator import SongPaginator
from pallotti_slides.presentation.pdf import LibreOfficeConverter, PdfConverter
from pallotti_slides.presentation.planner import BuildPlanner
from pallotti_slides.presentation.template import MassTemplate
from pallotti_slides.songs.downloaders import (
    CifraClubDownloader,
    LetrasMusDownloader,
    LyricsDownloader,
)
from pallotti_slides.songs.interpreter import RequestInterpreter
from pallotti_slides.songs.parser import ChorusDetector, LyricsParser
from pallotti_slides.songs.repertoire import RepertoireImporter
from pallotti_slides.songs.resolver import SongResolver
from pallotti_slides.songs.web_search import WebSongSearcher

__all__ = ["Container", "LazyLLMClient", "create_container"]


class LazyLLMClient:
    """``LLMClient`` created on first use; without an API key only that use fails."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: LLMClient | None = None

    def _get(self) -> LLMClient:
        if self._client is None:
            self._client = create_llm_client(self._settings)  # LLMError without a key
        return self._client

    def extract_structured[T: BaseModel](
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T:
        return self._get().extract_structured(
            instruction=instruction,
            schema=schema,
            pdf=pdf,
            text=text,
        )

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        return self._get().search_urls(query=query, domains=domains, max_results=max_results)


class _Closeable(Protocol):
    def close(self) -> None: ...


@dataclass
class Container:
    """Everything the CLI and the GUI need, already wired."""

    settings: Settings
    paths: Paths
    session: _Closeable  # DB session, closed by ``close()``
    mass_repo: MassRepository
    template: MassTemplate
    llm: LLMClient
    leaflet_extractor: LeafletExtractor
    parser: LyricsParser
    generator: MassGenerator
    preparer: MassPreparer
    song_repo: SongRepository
    resolver: SongResolver
    interpreter: RequestInterpreter
    repertoire_importer: RepertoireImporter

    def close(self) -> None:
        self.session.close()


def create_container(
    settings: Settings,
    *,
    paths: Paths | None = None,
    db_url: str | None = None,
    template_path: Path | None = None,
    with_pdf: bool = True,
    typography: TypographyConfig | None = None,
    llm: LLMClient | None = None,
    converter: PdfConverter | None = None,
) -> Container:
    """Real container; ``llm`` and ``converter`` can be replaced (tests).

    The LLM is lazy: without an API key everything except the leaflet extraction (and the
    chorus detection fallback) keeps working.
    """
    paths = paths or Paths.default()
    engine = make_engine(db_url or default_db_url(paths))
    apply_migrations(engine)
    session = session_factory(engine)()
    mass_repo = MassRepository(session)

    template = MassTemplate.load(template_path)
    fonts = FontLocator().locate()
    measurer = TextMeasurer(fonts.regular, fonts.bold)
    paginator = SongPaginator(measurer, typography or TypographyConfig())
    if converter is None and with_pdf:
        converter = LibreOfficeConverter()
    generator = MassGenerator(
        template=template,
        paginator=paginator,
        planner=BuildPlanner(),
        builder=PptxBuilder(),
        converter=converter if with_pdf else None,
        mass_repo=mass_repo,
    )

    client: Any = llm or LazyLLMClient(settings)
    extractor = LeafletExtractor(client, paths.data / "cache" / "leaflets")
    parser = LyricsParser(ChorusDetector(client))
    song_repo = SongRepository(session)
    downloaders: list[LyricsDownloader] = [LetrasMusDownloader(), CifraClubDownloader()]
    resolver = SongResolver(song_repo, downloaders, parser, WebSongSearcher(client))
    interpreter = RequestInterpreter(client)
    preparer = MassPreparer(extractor, ResolverAdapter(resolver), interpreter)
    return Container(
        settings=settings,
        paths=paths,
        session=session,
        mass_repo=mass_repo,
        template=template,
        llm=client,
        leaflet_extractor=extractor,
        parser=parser,
        generator=generator,
        preparer=preparer,
        song_repo=song_repo,
        resolver=resolver,
        interpreter=interpreter,
        repertoire_importer=RepertoireImporter(),
    )
