from pallotti_slides.songs.downloaders import strip_chords


def test_chord_only_lines_are_removed() -> None:
    text = "  Am       G/B     C\nTe amarei, Senhor\nD7(9)  F#m  Bb\nEu só encontro a paz"
    assert strip_chords(text) == "Te amarei, Senhor\nEu só encontro a paz"


def test_bracketed_chords_are_removed() -> None:
    assert strip_chords("Te [Am]amarei, [G/B]Senhor") == "Te amarei, Senhor"
    assert strip_chords("[Am] [G]\nverso") == "verso"


def test_labelled_chord_lines_and_tablature_are_removed() -> None:
    text = "Intro: Am G C (2x)\ne|---0---3---|\nB|-1-----0---|\nLetra aqui\n[Solo] Em D"
    assert strip_chords(text) == "Letra aqui"


def test_lyrics_and_section_names_survive() -> None:
    text = "[Refrão]\nA graça de Deus\n\n\n\nMe dá a paz\nEm Cristo, a luz"
    assert strip_chords(text) == "[Refrão]\nA graça de Deus\n\nMe dá a paz\nEm Cristo, a luz"


def test_no_chord_left_in_synthetic_sheet() -> None:
    sheet = "Intro: C G\n\n   C        G\nSenhor, tem piedade\n   Am       F\nCristo, tem piedade\n"
    assert strip_chords(sheet) == "Senhor, tem piedade\nCristo, tem piedade"
