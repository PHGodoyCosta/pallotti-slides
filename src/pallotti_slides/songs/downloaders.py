"""Raw lyrics and the downloader contract (ARQUITETURA §6).

The concrete downloaders (Letras.mus.br, Cifra Club) come later, with saved HTML fixtures.
"""

import re
from typing import Protocol

from pydantic import BaseModel, ConfigDict

from pallotti_slides.domain.enums import SongSource


class RawLyrics(BaseModel):
    """Lyrics as obtained from a site or pasted by the user, before structuring."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    artist: str | None = None
    text: str
    source: SongSource
    url: str | None = None


class LyricsDownloader(Protocol):
    """Fetches the lyrics of one URL."""

    def supports(self, url: str) -> bool: ...

    def download(self, url: str) -> RawLyrics: ...


_CHORD = r"[A-G][#b]?(?:maj|min|dim|aug|sus|add|m|M)?\d*(?:\([^)\s]*\))?(?:/[A-G][#b]?)?"
_CHORD_TOKEN = re.compile(rf"{_CHORD}")
_FILLER_TOKEN = re.compile(r"[|()\-x/.:]+|\(?\d+x\)?|x\d+", re.IGNORECASE)
_LABEL = re.compile(
    r"^\s*\[?\s*(?:intro(?:du[cç][aã]o)?|solo|ponte|final|interl[uú]dio|riff|base|refr[aã]o)"
    r"[^\]:]*\]?\s*:?\s*",
    re.IGNORECASE,
)
_TAB_LINE = re.compile(r"^\s*[EADGBe]?\s*\|[-\dhpbrx/\\~^()|\s.]*$")
_BRACKET_CHORD = re.compile(rf"\[\s*{_CHORD}\s*\]")
_BLANK_RUN = re.compile(r"\n{3,}")


def _is_chord_line(line: str) -> bool:
    """True when the line holds only chords (and bar/repeat marks), and at least one chord."""
    tokens = line.split()
    if not tokens:
        return False
    chords = 0
    for token in tokens:
        if _CHORD_TOKEN.fullmatch(token):
            chords += 1
        elif not _FILLER_TOKEN.fullmatch(token):
            return False
    return chords > 0


def strip_chords(text: str) -> str:
    """Remove chords from the ``<pre>`` text of a chord sheet.

    Drops chord-only lines (also after labels such as "Intro:"), tablature lines and
    bracketed chords inside lyric lines ("Te [Am]amarei" -> "Te amarei").
    """
    kept: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if _TAB_LINE.match(raw):
            continue
        label = _LABEL.match(raw)
        rest = raw[label.end() :] if label else raw
        if _is_chord_line(rest):
            continue
        line = _BRACKET_CHORD.sub("", raw)
        if line != raw:
            line = re.sub(r"[ \t]{2,}", " ", line).rstrip()
            if not line.strip():
                continue
        kept.append(line.rstrip())
    return _BLANK_RUN.sub("\n\n", "\n".join(kept)).strip("\n")
