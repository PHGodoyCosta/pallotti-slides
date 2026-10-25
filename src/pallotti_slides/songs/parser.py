"""Lyrics structuring (F6): raw text -> ``Song`` (stanzas, types, order)."""

import re
from typing import Literal

from pydantic import BaseModel

from pallotti_slides.domain.enums import StanzaType
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Line, Notice, Song, Stanza
from pallotti_slides.domain.text import looks_like_url, normalize_search
from pallotti_slides.llm.client import LLMClient
from pallotti_slides.songs.downloaders import RawLyrics

_NAME = r"refr[aã]o|ref\.?|r"
# Marker at the start of a stanza: "[Refrão]", "(Refrão)", "Refrão:", "Ref.:", "R:", "Refrão".
_MARKER = re.compile(
    rf"^\s*(?:\[\s*refr[aã]o\s*\]|\(\s*refr[aã]o\s*\)|(?:{_NAME})\s*:|refr[aã]o\s*$)\s*(.*)$",
    re.IGNORECASE,
)
# A line that only points to the chorus: "Refrão", "(Refrão)", "[Refrão]", "Refrão:".
_REFERENCE = re.compile(r"^\s*[\[(]?\s*refr[aã]o\s*[\])]?\s*:?\s*$", re.IGNORECASE)

_NO_CHORUS = (
    "Não foi possível identificar o refrão desta letra; todas as estrofes ficaram como verso. "
    "Corrija na revisão."
)


class ChorusIds(BaseModel):
    """LLM answer: only the numbers of the stanzas that are chorus."""

    chorus_ids: list[int]


def detect_request_kind(text: str) -> Literal["url", "lyrics", "title"]:
    """F4: URL by address pattern; lyrics when there are more than 2 lines; else title."""
    stripped = text.strip()
    if looks_like_url(stripped):
        return "url"
    lines = [line for line in stripped.splitlines() if line.strip()]
    return "lyrics" if len(lines) > 2 else "title"


def _key(lines: list[str]) -> str:
    return normalize_search(" ".join(lines))


class ChorusDetector:
    """Decides which stanzas are chorus: markers -> repetition -> LLM -> undefined."""

    def __init__(self, llm: LLMClient | None = None) -> None:
        self._llm = llm

    def detect(
        self, stanzas: list[list[str]], marked: set[int], repeated: set[int]
    ) -> tuple[set[int], list[Notice]]:
        """Indexes (0-based, into ``stanzas``) of the chorus stanzas, plus notices.

        ``marked``: stanzas carrying an explicit marker; ``repeated``: stanzas that appear
        more than once. The LLM is only asked when both are empty.
        """
        found = marked | repeated
        if found:
            return found, []
        if self._llm is not None:
            try:
                from_llm = self._ask_llm(self._llm, stanzas)
            except PallottiError as error:
                return set(), [Notice(level="warning", message=f"{error} {_NO_CHORUS}")]
            if from_llm:
                return from_llm, []
        return set(), [Notice(level="warning", message=_NO_CHORUS)]

    def _ask_llm(self, llm: LLMClient, stanzas: list[list[str]]) -> set[int]:
        numbered = "\n\n".join(
            f"[{number}]\n" + "\n".join(lines) for number, lines in enumerate(stanzas, start=1)
        )
        answer = llm.extract_structured(
            instruction=(
                "Você recebe as estrofes numeradas de um canto litúrgico. Devolva em chorus_ids "
                "apenas os números das estrofes que são refrão. Não escreva nem altere nenhuma "
                "letra; se nenhuma for refrão, devolva a lista vazia."
            ),
            schema=ChorusIds,
            text=numbered,
        )
        return {number - 1 for number in answer.chorus_ids if 1 <= number <= len(stanzas)}


class LyricsParser:
    """Turns ``RawLyrics`` into a ``Song`` (stanzas, chorus detection, execution order)."""

    def __init__(self, detector: ChorusDetector) -> None:
        self._detector = detector

    def parse(self, raw: RawLyrics) -> tuple[Song, list[Notice]]:
        """Structure the lyrics; recoverable problems come back as notices."""
        notices: list[Notice] = []
        unique: list[list[str]] = []
        index_by_key: dict[str, int] = {}
        marked: set[int] = set()
        repeated: set[int] = set()
        sequence: list[int | None] = []  # None = reference to the chorus

        for block in self._blocks(raw.text):
            for kind, lines in self._split_references(block):
                if kind == "reference":
                    sequence.append(None)
                    continue
                lines, has_marker = self._strip_marker(lines)
                if not lines:
                    continue
                key = _key(lines)
                if key in index_by_key:
                    index = index_by_key[key]
                    repeated.add(index)
                else:
                    index = len(unique)
                    index_by_key[key] = index
                    unique.append(lines)
                if has_marker:
                    marked.add(index)
                sequence.append(index)

        chorus, detector_notices = self._detector.detect(unique, marked, repeated)
        notices.extend(detector_notices)

        order: list[int] = []
        for position, item in enumerate(sequence):
            if item is not None:
                order.append(item + 1)
                continue
            target = self._reference_target(sequence, position, chorus)
            if target is None:
                notices.append(
                    Notice(
                        level="warning",
                        message='A letra tem uma linha "Refrão", mas nenhum refrão foi '
                        "identificado; a linha foi ignorada.",
                    )
                )
            else:
                order.append(target + 1)

        stanzas = [
            Stanza(
                id=index + 1,
                type=StanzaType.CHORUS if index in chorus else StanzaType.VERSE,
                lines=[Line(text=text, bold=index in chorus) for text in lines],
            )
            for index, lines in enumerate(unique)
        ]
        song = Song(
            title=raw.title,
            artist=raw.artist,
            source=raw.source,
            source_url=raw.url,
            stanzas=stanzas,
            order=order,
        )
        return song, notices

    @staticmethod
    def _blocks(text: str) -> list[list[str]]:
        """Blank-line separated blocks of whitespace-normalized, non-empty lines."""
        blocks: list[list[str]] = [[]]
        for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
            clean = " ".join(line.split())
            if clean:
                blocks[-1].append(clean)
            elif blocks[-1]:
                blocks.append([])
        return [block for block in blocks if block]

    @staticmethod
    def _split_references(
        block: list[str],
    ) -> list[tuple[Literal["reference", "stanza"], list[str]]]:
        """Split reference lines ("(Refrão)") out of a block.

        A reference line in the first position of a block with more lines is a marker
        (kept in the stanza); anywhere else it is a reference to the chorus.
        """
        parts: list[tuple[Literal["reference", "stanza"], list[str]]] = []
        current: list[str] = []
        for position, line in enumerate(block):
            if _REFERENCE.match(line) and not (position == 0 and len(block) > 1):
                if current:
                    parts.append(("stanza", current))
                    current = []
                parts.append(("reference", []))
            else:
                current.append(line)
        if current:
            parts.append(("stanza", current))
        return parts

    @staticmethod
    def _strip_marker(lines: list[str]) -> tuple[list[str], bool]:
        match = _MARKER.match(lines[0])
        if match is None:
            return lines, False
        rest = match.group(1).strip()
        return ([rest] if rest else []) + lines[1:], True

    @staticmethod
    def _reference_target(
        sequence: list[int | None], position: int, chorus: set[int]
    ) -> int | None:
        """Chorus stanza a reference points to: the last one before it, else the first overall."""
        for item in reversed(sequence[:position]):
            if item is not None and item in chorus:
                return item
        return min(chorus) if chorus else None
