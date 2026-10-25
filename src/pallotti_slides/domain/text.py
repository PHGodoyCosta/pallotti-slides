"""Pure text helpers."""

import re
import unicodedata

_LOWERCASE_WORDS = frozenset(
    {"a", "o", "as", "os", "de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos"}
    | {"ao", "aos", "à", "às", "com", "para", "por", "pela", "pelo", "pelas", "pelos"}
)
_ORDINAL_MARKS = str.maketrans({"º": "°", "ª": "°", "˚": "°"})
_ROMAN_NUMERAL = re.compile(r"(?=[IVXLCDM])M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})")
_URL = re.compile(r"(https?://|www\.)\S+", re.IGNORECASE)


def _capitalize(word: str) -> str:
    return word[:1].upper() + word[1:].lower()


def _title_word(word: str, first: bool) -> str:
    if _ROMAN_NUMERAL.fullmatch(word):
        return word  # e.g. "II" in "II Domingo da Páscoa"
    if not first and word.lower() in _LOWERCASE_WORDS:
        return word.lower()
    return "-".join(_capitalize(part) for part in word.split("-"))


def normalize_title(text: str) -> str:
    """Normalize a celebration title.

    "30º DOMINGO DO TEMPO COMUM" -> "30° Domingo do Tempo Comum": capitalized
    words, articles/prepositions in lowercase, ordinal marks (º, ª) turned into °.
    """
    words = text.translate(_ORDINAL_MARKS).split()
    return " ".join(_title_word(word, first=index == 0) for index, word in enumerate(words))


def normalize_search(text: str) -> str:
    """Key used to compare titles: no accents, lowercase, only letters/digits, single spaces."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^0-9a-z]+", " ", without_accents).split())


def looks_like_url(text: str) -> bool:
    """True when the whole text is an http(s) or www address (no spaces)."""
    return _URL.fullmatch(text.strip()) is not None
