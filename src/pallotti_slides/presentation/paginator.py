"""Song pagination and font size (SPEC F9, ARQUITETURA §5)."""

from collections.abc import Sequence
from dataclasses import dataclass

from pallotti_slides.config import TypographyConfig
from pallotti_slides.domain.enums import StanzaType
from pallotti_slides.domain.models import Line, Song
from pallotti_slides.presentation.measurer import (
    DEFAULT_BODY_FORMAT,
    BodyFormat,
    Box,
    TextMeasurer,
)

SIZE_STEP = 2


@dataclass(frozen=True)
class SongPage:
    """One slide of a song: its lines and the font size of its kind (verse or chorus)."""

    lines: list[Line]
    size_pt: int


def split_balanced(lines: Sequence[Line], pieces: int) -> list[list[Line]]:
    """Split ``lines`` into ``pieces`` consecutive chunks whose sizes differ by at most one.

    The first chunks get the extra line (7 lines in 2 pieces -> 4 + 3).
    """
    pieces = max(1, min(pieces, len(lines)))
    base, extra = divmod(len(lines), pieces)
    chunks: list[list[Line]] = []
    start = 0
    for index in range(pieces):
        end = start + base + (1 if index < extra else 0)
        chunks.append(list(lines[start:end]))
        start = end
    return chunks


@dataclass
class _Chunk:
    """A stanza (or a long stanza) and how many pages it is split into."""

    lines: list[Line]
    pieces: int
    chorus: bool

    def pages(self) -> list[list[Line]]:
        return split_balanced(self.lines, self.pieces)


class SongPaginator:
    """One page per stanza, in execution order; one size for the verses, one for the choruses.

    1. ``Song.sequence()`` -> one page per stanza (a repeated chorus repeats the page);
    2. a stanza with more than ``max_lines`` lines is split into balanced pages;
    3. verses and choruses are sized apart: from ``max_font`` down to ``min_font`` (step 2) the
       first size in which every page of the group fits is the size of the whole group (all the
       verses share one size, all the choruses share another, and a chorus may be larger);
    4. when nothing fits in ``min_font``, the stanzas of the group whose pages do not fit get one
       more page and the search starts again. A single line that never fits stays in
       ``min_font``.
    """

    def __init__(self, measurer: TextMeasurer, config: TypographyConfig | None = None) -> None:
        self.measurer = measurer
        self.config = config or TypographyConfig()

    def paginate(
        self, song: Song, box: Box, body: BodyFormat = DEFAULT_BODY_FORMAT
    ) -> list[SongPage]:
        config = self.config
        chunks: list[_Chunk] = []
        for stanza in song.sequence():
            if not stanza.lines:
                continue
            pieces = -(-len(stanza.lines) // config.max_lines)  # ceil
            chunks.append(_Chunk(list(stanza.lines), pieces, stanza.type is StanzaType.CHORUS))
        verse_size = self._fit([chunk for chunk in chunks if not chunk.chorus], box, body)
        chorus_size = self._fit([chunk for chunk in chunks if chunk.chorus], box, body)
        return [
            SongPage(lines=page, size_pt=chorus_size if chunk.chorus else verse_size)
            for chunk in chunks
            for page in chunk.pages()
        ]

    def _fit(self, chunks: list[_Chunk], box: Box, body: BodyFormat) -> int:
        """Size shared by ``chunks`` (may split them further); ``min_font`` if there are none."""
        config = self.config
        if not chunks:
            return config.min_font
        sizes = list(range(config.max_font, config.min_font - 1, -SIZE_STEP))
        if sizes[-1] != config.min_font:
            sizes.append(config.min_font)
        while True:
            for size in sizes:
                if all(
                    self.measurer.fits(page, size, box, body)
                    for chunk in chunks
                    for page in chunk.pages()
                ):
                    return size
            grown = False
            for chunk in chunks:
                failing = any(
                    not self.measurer.fits(page, config.min_font, box, body)
                    for page in chunk.pages()
                )
                if failing and chunk.pieces < len(chunk.lines):
                    chunk.pieces += 1
                    grown = True
            if not grown:
                return config.min_font
