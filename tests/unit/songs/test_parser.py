from collections import Counter
from pathlib import Path

import pytest
from pydantic import BaseModel

from pallotti_slides.domain.enums import SongSource, StanzaType
from pallotti_slides.domain.models import Mass, Song
from pallotti_slides.llm.client import LLMClient, SearchResult
from pallotti_slides.llm.errors import LLMError
from pallotti_slides.songs.downloaders import RawLyrics
from pallotti_slides.songs.parser import (
    ChorusDetector,
    ChorusIds,
    LyricsParser,
    detect_request_kind,
)

MASS = Path(__file__).resolve().parents[2] / "fixtures" / "masses" / "26tc_2026.json"
SONGS = Mass.model_validate_json(MASS.read_text(encoding="utf-8")).songs


class FakeChorusLLM:
    """Local fake: answers with fixed ids and records what it received."""

    def __init__(self, ids: list[int] | None = None, error: bool = False) -> None:
        self.ids = ids or []
        self.error = error
        self.texts: list[str | None] = []

    def extract_structured[T: BaseModel](
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T:
        self.texts.append(text)
        if self.error:
            raise LLMError("Falha de teste.")
        assert schema is ChorusIds
        return schema.model_validate({"chorus_ids": self.ids})

    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]:
        raise AssertionError("not used")


def _raw(text: str) -> RawLyrics:
    return RawLyrics(title="Teste", text=text, source=SongSource.MANUAL)


def _parser(llm: LLMClient | None = None) -> LyricsParser:
    return LyricsParser(ChorusDetector(llm))


def _pasted(song: Song) -> str:
    """Pasted text: stanzas written in full each time they are sung.

    A chorus sung only once has no repetition to reveal it, so it gets a "Refrão:" line.
    """
    counts = Counter(stanza.id for stanza in song.sequence())
    blocks = []
    for stanza in song.sequence():
        lines = [line.text for line in stanza.lines]
        if stanza.type is StanzaType.CHORUS and counts[stanza.id] == 1:
            lines.insert(0, "Refrão:")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


@pytest.mark.parametrize("moment", list(SONGS))
def test_fixture_songs_roundtrip(moment: object) -> None:
    expected = SONGS[moment]  # type: ignore[index]
    song, notices = _parser().parse(_raw(_pasted(expected)))
    assert [s.type for s in song.stanzas] == [s.type for s in expected.stanzas]
    expected_lines = [[line.text for line in s.lines] for s in expected.stanzas]
    if moment == "penitential_act":  # repeated block shown once, marked as repeatable (F6)
        expected_lines[1] = ["/*Senhor piedade! Cristo, piedade!", "Tem piedade ó Senhor!*/"]
    assert [[line.text for line in s.lines] for s in song.stanzas] == expected_lines
    assert song.order == expected.order
    for stanza in song.stanzas:  # chorus = bold; the verse-line highlight is not inferred
        assert all(line.bold for line in stanza.lines) == (stanza.type is StanzaType.CHORUS)
    has_chorus = any(s.type is StanzaType.CHORUS for s in expected.stanzas)
    assert bool(notices) == (not has_chorus)  # only the Glória has no detectable chorus


def test_reference_line_is_expanded_in_order() -> None:
    text = "Verso um\nlinha b\n\nRefrão:\nCoro a\nCoro b\n\nVerso dois\nlinha d\n\n(Refrão)"
    song, notices = _parser().parse(_raw(text))
    assert song.order == [1, 2, 3, 2]
    assert [s.type for s in song.stanzas] == [StanzaType.VERSE, StanzaType.CHORUS, StanzaType.VERSE]
    assert notices == []


def test_reference_line_inside_a_stanza_splits_it() -> None:
    text = "[Refrão] Coro a\nCoro b\n\nVerso\nlinha\nRefrão\nOutro verso"
    song, _ = _parser().parse(_raw(text))
    assert song.order == [1, 2, 1, 3]
    assert song.stanzas[0].lines[0].text == "Coro a"


@pytest.mark.parametrize("marker", ["Refrão:", "Ref.:", "R:", "[Refrão]", "(Refrão)", "REFRÃO"])
def test_marker_flags_chorus_and_is_removed(marker: str) -> None:
    song, notices = _parser().parse(_raw(f"Verso\nlinha\n\n{marker}\nCoro\nmais coro"))
    assert [s.type for s in song.stanzas] == [StanzaType.VERSE, StanzaType.CHORUS]
    assert [line.text for line in song.stanzas[1].lines] == ["Coro", "mais coro"]
    assert all(line.bold for line in song.stanzas[1].lines)
    assert notices == []


def test_marker_with_text_on_same_line() -> None:
    song, _ = _parser().parse(_raw("Verso\n\nRef.: Coro aqui\nsegunda"))
    assert [line.text for line in song.stanzas[1].lines] == ["Coro aqui", "segunda"]


def test_repeated_stanza_is_one_chorus_and_spaces_are_normalized() -> None:
    text = "A  b\n\nCoro,   lá\n\nC d\n\ncoro, lá!"
    song, notices = _parser().parse(_raw(text))
    assert song.order == [1, 2, 3, 2]
    assert song.stanzas[1].type is StanzaType.CHORUS
    assert song.stanzas[1].lines[0].text == "Coro, lá"
    assert notices == []


def test_consecutive_equal_ids_collapse_in_order() -> None:
    text = "a\n\nb\n\nc\n\nc\n\nd\n\ne\n\nc\n\nc\n\nc"
    song, _ = _parser().parse(_raw(text))
    assert song.order == [1, 2, 3, 4, 5, 3]
    song, _ = _parser().parse(_raw("a\n\nb\n\nc\n\nd\n\ne\n\nb\n\nb"))
    assert song.order == [1, 2, 3, 4, 5, 2]


def test_reference_next_to_same_chorus_collapses() -> None:
    song, _ = _parser().parse(_raw("Refrão:\nCoro\n\n(Refrão)\n\nVerso\nx"))
    assert song.order == [1, 2]


def test_stanza_with_repeated_block_is_bold_chorus() -> None:
    song, notices = _parser().parse(_raw("Verso\nlinha\n\nSenhor piedade\nSenhor piedade\nOutra"))
    assert [s.type for s in song.stanzas] == [StanzaType.VERSE, StanzaType.CHORUS]
    assert [line.text for line in song.stanzas[1].lines] == ["/*Senhor piedade*/", "Outra"]
    assert all(line.bold for line in song.stanzas[1].lines)
    assert notices == []


def test_markers_like_2x_are_kept() -> None:
    song, _ = _parser().parse(_raw("Aleluia (2x)\nbis\n\nOutro"))
    assert [line.text for line in song.stanzas[0].lines] == ["Aleluia (2x)", "bis"]


def test_no_detectable_chorus_warns_and_keeps_verses() -> None:
    song, notices = _parser().parse(_raw("um\ndois\n\ntrês\nquatro"))
    assert all(s.type is StanzaType.VERSE for s in song.stanzas)
    assert song.order == [1, 2]
    assert [n.level for n in notices] == ["warning"]


def test_llm_path_receives_numbered_stanzas_and_returns_ids() -> None:
    llm = FakeChorusLLM(ids=[2, 9])  # 9 does not exist and is ignored
    song, notices = _parser(llm).parse(_raw("um\ndois\n\ntrês\nquatro\n\ncinco"))
    assert [s.type for s in song.stanzas] == [
        StanzaType.VERSE,
        StanzaType.CHORUS,
        StanzaType.VERSE,
    ]
    assert notices == []
    assert llm.texts == ["[1]\num\ndois\n\n[2]\ntrês\nquatro\n\n[3]\ncinco"]


def test_llm_is_not_called_when_markers_or_repetition_decide() -> None:
    llm = FakeChorusLLM(ids=[1])
    _parser(llm).parse(_raw("a\n\nRefrão:\nb"))
    _parser(llm).parse(_raw("a\n\nb\n\na"))
    assert llm.texts == []


def test_llm_failure_becomes_warning() -> None:
    song, notices = _parser(FakeChorusLLM(error=True)).parse(_raw("um\n\ndois"))
    assert all(s.type is StanzaType.VERSE for s in song.stanzas)
    assert [n.level for n in notices] == ["warning"]


def test_llm_with_no_chorus_warns() -> None:
    _, notices = _parser(FakeChorusLLM(ids=[])).parse(_raw("um\n\ndois"))
    assert [n.level for n in notices] == ["warning"]


def test_metadata_is_carried_to_song() -> None:
    raw = RawLyrics(
        title="T", artist="A", text="x\n\nx", source=SongSource.LETRAS_MUS, url="https://x.y/z"
    )
    song, _ = _parser().parse(raw)
    assert (song.title, song.artist, song.source, song.source_url) == (
        "T",
        "A",
        SongSource.LETRAS_MUS,
        "https://x.y/z",
    )


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("https://www.letras.mus.br/artista/musica/", "url"),
        ("  www.cifraclub.com.br/a/b/ ", "url"),
        ("me chamaste para caminhar", "title"),
        ("linha 1\nlinha 2", "title"),
        ("linha 1\n\nlinha 2\n\n", "title"),
        ("linha 1\nlinha 2\nlinha 3", "lyrics"),
        ("a\n\nb\n\nc", "lyrics"),
    ],
)
def test_detect_request_kind(text: str, kind: str) -> None:
    assert detect_request_kind(text) == kind


def test_bracket_marker_block_marks_next_stanza_as_chorus() -> None:
    text = (
        "Verso\nlinha\n\n[Refrão]\n\nCoro a\nCoro b\n\nOutro verso\nlinha\n\n"
        "[Refrão Final]\n\nCoro a\nCoro b"
    )
    song, notices = _parser().parse(_raw(text))
    assert [s.type for s in song.stanzas] == [StanzaType.VERSE, StanzaType.CHORUS, StanzaType.VERSE]
    assert song.order == [1, 2, 3, 2]
    assert [line.text for line in song.stanzas[1].lines] == ["Coro a", "Coro b"]
    assert notices == []


def test_final_bracket_marker_with_nothing_after_is_a_reference() -> None:
    song, _ = _parser().parse(_raw("Refrão:\nCoro\n\nVerso\n\n[Refrão]"))
    assert song.order == [1, 2, 1]


def test_block_repeated_in_sequence_appears_once_with_repeat_marks() -> None:
    text = (
        "Refrão:\nSenhor piedade\nSenhor piedade\nPra fazer\nPra viver\nPra fazer\nPra viver\nFim"
    )
    song, _ = _parser().parse(_raw(text))
    assert [line.text for line in song.stanzas[0].lines] == [
        "/*Senhor piedade*/",
        "/*Pra fazer",
        "Pra viver*/",
        "Fim",
    ]


def test_prolongations_are_cleaned_in_pasted_text() -> None:
    song, _ = _parser().parse(_raw("os que foram liberta..dos\nnossas culpas perdoa....ai"))
    assert [line.text for line in song.stanzas[0].lines] == [
        "os que foram libertados",
        "nossas culpas perdoai",
    ]
