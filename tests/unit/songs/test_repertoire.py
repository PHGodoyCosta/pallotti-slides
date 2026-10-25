from pathlib import Path

import pytest

from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.songs.downloaders import DownloadError
from pallotti_slides.songs.repertoire import RepertoireImporter, propose_moments

HTML = (
    Path(__file__).resolve().parents[2]
    / "fixtures"
    / "html"
    / "cifra_club"
    / "repertorio_57846361.html"
)
URL = "https://www.cifraclub.com.br/@32936533/repertorio/57846361/"


def test_saved_page_gives_seven_items_in_order_with_proposals() -> None:
    importer = RepertoireImporter(fetch=lambda _url: HTML.read_text(encoding="utf-8"))
    proposal = importer.load(URL)
    assert proposal.requires_confirmation is True
    assert [i.title for i in proposal.items] == [
        "Eis-me Aqui, Senhor",
        "Pelos Pecados - Ato Penitencial",
        "Glória a Deus Nos Altos Céus",
        "Um Coração Para Amar",
        "Tu És Minha Vida, Outro Deus Não Ha",
        "O Povo de Deus",
        "Ave Maria",
    ]
    assert proposal.items[0].url == "https://www.cifraclub.com.br/catolicas/eis-me-aqui-senhor/"
    moments = {i.title: (i.moment, i.confidence) for i in proposal.items}
    assert moments["Pelos Pecados - Ato Penitencial"] == (SongMoment.PENITENTIAL_ACT, "high")
    assert moments["Glória a Deus Nos Altos Céus"] == (SongMoment.GLORIA, "high")
    assert moments["Eis-me Aqui, Senhor"] == (SongMoment.ENTRANCE, "low")
    assert proposal.unassigned == []
    assigned = [i.moment for i in proposal.items]
    assert len(set(assigned)) == 7


def test_hints_and_overflow() -> None:
    songs = [
        ("Aleluia, Aleluia", None, "u1"),
        ("Santo, Santo, Santo", None, "u2"),
        ("Cordeiro de Deus", None, "u3"),
        *[(f"Canto {n}", None, f"c{n}") for n in range(6)],
    ]
    proposal = propose_moments(songs)
    by_title = {i.title: i for i in proposal.items}
    assert by_title["Aleluia, Aleluia"].moment is SongMoment.ACCLAMATION
    assert by_title["Santo, Santo, Santo"].moment is None
    assert by_title["Cordeiro de Deus"].moment is None
    # 5 free moments for 6 plain songs: the last one is left unassigned
    assert [i.title for i in proposal.unassigned][-1] == "Canto 5"
    assert len(proposal.unassigned) == 3


def test_other_site_and_unreadable_page_are_download_errors() -> None:
    with pytest.raises(DownloadError):
        RepertoireImporter(fetch=lambda _u: "").load("https://example.com/x")
    with pytest.raises(DownloadError):
        RepertoireImporter(fetch=lambda _u: "<html></html>").load(URL)
