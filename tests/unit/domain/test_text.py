"""Domain text helpers."""

import pytest

from pallotti_slides.domain.text import looks_like_url, normalize_search, normalize_title


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("30º DOMINGO DO TEMPO COMUM", "30° Domingo do Tempo Comum"),
        ("26° Domingo do Tempo Comum", "26° Domingo do Tempo Comum"),
        ("  2ª  semana   da quaresma ", "2° Semana da Quaresma"),
        ("NATAL DO SENHOR", "Natal do Senhor"),
        ("SOLENIDADE DE NOSSA SENHORA APARECIDA", "Solenidade de Nossa Senhora Aparecida"),
        ("II DOMINGO DA PÁSCOA", "II Domingo da Páscoa"),
        ("DE PROFUNDIS", "De Profundis"),
        ("", ""),
    ],
)
def test_normalize_title(raw: str, expected: str) -> None:
    assert normalize_title(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ó Luz do Senhor!", "o luz do senhor"),
        ("  AVE,   Maria  ", "ave maria"),
        ("Coração de Jesus (2x)", "coracao de jesus 2x"),
        ("Pão da Vida - Pe. Zezinho", "pao da vida pe zezinho"),
        ("", ""),
    ],
)
def test_normalize_search(raw: str, expected: str) -> None:
    assert normalize_search(raw) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://www.letras.mus.br/padre-zezinho/ave-maria/", True),
        ("http://cifraclub.com.br/x/y", True),
        ("  www.letras.mus.br/x  ", True),
        ("HTTPS://LETRAS.MUS.BR/X", True),
        ("Ave Maria", False),
        ("https://letras.mus.br/x depois", False),
        ("", False),
    ],
)
def test_looks_like_url(text: str, expected: bool) -> None:
    assert looks_like_url(text) is expected
