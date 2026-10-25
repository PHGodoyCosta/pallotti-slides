"""Text measurement for the song pages (ARQUITETURA §5, SPEC F9).

The layout model was calibrated against the example deck rendered by LibreOffice
(``examples/Missa - 26° Dom do T.C - 26.09.2026 - OE III.pdf``):

* a single line is ``LINE_HEIGHT_EM`` x font size tall, multiplied by the paragraph line
  spacing (``lnSpc``, 90 % in the song prototypes);
* between two paragraphs come ``spcAft`` of the first plus ``spcBef`` of the second; the
  ``spcBef`` of the first paragraph is ignored;
* glyphs go ``DESCENT_OVERHANG_EM`` x size below the box of the last line;
* lines wrap at spaces; the first line of a paragraph starts ``marL + indent`` after the left
  inset and the following ones ``marL`` (hanging indent of the prototypes).

With these rules the wrapped line count of every song slide of the example is the one of the
PDF and the measured height matches the PDF within 1 pt (``tests/unit/presentation``).
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from PIL import ImageFont

from pallotti_slides.domain.models import Line, Notice

EMU_PER_POINT = 12700

LINE_HEIGHT_EM = 1.2
"""Single line height / font size (Aptos in LibreOffice): 58.32 pt per line at 54 pt, 90 %."""

DESCENT_OVERHANG_EM = 0.06
"""Glyphs below the box of the last line / font size (measured 3.1 pt at 54 pt)."""

SUBSTITUTE_SLACK = 1.10
"""Safety factor on widths and heights when Aptos is missing and a substitute font is used."""

SUBSTITUTE_FONT_NOTICE = (
    "Fonte Aptos não encontrada: a medição dos cantos usou uma fonte substituta com 10% de "
    "folga, então o tamanho das letras pode ficar menor que o ideal. Instale a Aptos (download "
    "gratuito da Microsoft) ou indique a pasta dela nas Configurações; veja `pallotti doctor`."
)

_REFERENCE_SIZE = 1000  # fonts are loaded once at this size; widths scale linearly
_SUBSTITUTES_REGULAR = ("DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "arial.ttf")
_SUBSTITUTES_BOLD = ("DejaVuSans-Bold.ttf", "LiberationSans-Bold.ttf", "arialbd.ttf")

type _Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


@dataclass(frozen=True)
class Box:
    """Frame of a text shape on the slide, in EMU (1 pt = 12700 EMU)."""

    left: int
    top: int
    width: int
    height: int

    @property
    def width_pt(self) -> float:
        return self.width / EMU_PER_POINT

    @property
    def height_pt(self) -> float:
        return self.height / EMU_PER_POINT

    @property
    def bottom(self) -> int:
        return self.top + self.height


@dataclass(frozen=True)
class BodyFormat:
    """Paragraph and frame settings that drive the layout of a song body.

    Read from the song prototype (``pPr`` of the ``{{canto.texto}}`` paragraph and the insets
    of ``bodyPr``). The defaults are the values of most song prototypes of the template.
    ``line_spacing_pt`` is set only for an exact line spacing (``lnSpc/spcPts``).
    """

    line_spacing: float = 0.9
    line_spacing_pt: float | None = None
    space_before_pt: float = 11.91
    space_after_pt: float = 9.92
    margin_left_pt: float = 18.0
    indent_pt: float = -18.0
    inset_left_pt: float = 7.2
    inset_right_pt: float = 7.2
    inset_top_pt: float = 3.6
    inset_bottom_pt: float = 3.6

    @property
    def paragraph_gap_pt(self) -> float:
        return self.space_after_pt + self.space_before_pt

    def line_pitch(self, size_pt: float) -> float:
        """Distance between two lines of the same paragraph."""
        if self.line_spacing_pt is not None:
            return self.line_spacing_pt
        return LINE_HEIGHT_EM * size_pt * self.line_spacing

    def first_line_width(self, box: Box) -> float:
        return self._inner_width(box) - max(self.margin_left_pt + self.indent_pt, 0.0)

    def other_lines_width(self, box: Box) -> float:
        return self._inner_width(box) - max(self.margin_left_pt, 0.0)

    def _inner_width(self, box: Box) -> float:
        return box.width_pt - self.inset_left_pt - self.inset_right_pt


DEFAULT_BODY_FORMAT = BodyFormat()


def _load(path: Path | None) -> _Font | None:
    if path is None or not path.is_file():
        return None
    try:
        return ImageFont.truetype(str(path), _REFERENCE_SIZE)
    except OSError:
        return None


def _load_substitute(names: tuple[str, ...]) -> _Font:
    for name in names:
        try:
            return ImageFont.truetype(name, _REFERENCE_SIZE)
        except OSError:
            continue
    return ImageFont.load_default(_REFERENCE_SIZE)


class TextMeasurer:
    """Measures song lines with the real metrics of the template font (Aptos).

    Without Aptos a substitute font is used with ``SUBSTITUTE_SLACK`` (10 %) of safety margin
    on widths and heights, and ``notices`` tells the user how to install the font.
    """

    def __init__(self, regular_font: Path | None, bold_font: Path | None) -> None:
        regular, bold = _load(regular_font), _load(bold_font)
        self._notices: list[Notice] = []
        self._slack = 1.0
        if regular is None or bold is None:
            regular = _load_substitute(_SUBSTITUTES_REGULAR)
            bold = _load_substitute(_SUBSTITUTES_BOLD)
            self._slack = SUBSTITUTE_SLACK
            self._notices.append(Notice(level="warning", message=SUBSTITUTE_FONT_NOTICE))
        self._fonts: dict[bool, _Font] = {False: regular, True: bold}

    @property
    def notices(self) -> list[Notice]:
        return list(self._notices)

    @property
    def uses_substitute(self) -> bool:
        return self._slack != 1.0

    def text_width(self, text: str, bold: bool, size_pt: float) -> float:
        """Width of ``text`` on a single line, in points."""
        width = float(self._fonts[bold].getlength(text))
        return width * size_pt / _REFERENCE_SIZE * self._slack

    def wrap(
        self, text: str, bold: bool, size_pt: float, first_width: float, other_width: float
    ) -> list[str]:
        """Split ``text`` into the lines the renderer draws (wrapping at spaces).

        A word wider than the line is broken inside the word by the renderer; it counts as
        many lines as needed.
        """
        words = text.split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            limit = first_width if not lines else other_width
            candidate = f"{current} {word}" if current else word
            if not current or self.text_width(candidate, bold, size_pt) <= limit:
                current = candidate
                continue
            lines.extend(self._break_long(current, bold, size_pt, limit))
            current = word
        limit = first_width if not lines else other_width
        lines.extend(self._break_long(current, bold, size_pt, limit))
        return lines

    def _break_long(self, text: str, bold: bool, size_pt: float, limit: float) -> list[str]:
        width = self.text_width(text, bold, size_pt)
        if width <= limit or limit <= 0:
            return [text]
        return [text] * math.ceil(width / limit)

    def line_count(
        self, line: Line, size_pt: float, box: Box, body: BodyFormat = DEFAULT_BODY_FORMAT
    ) -> int:
        """How many rendered lines one ``Line`` (one paragraph) takes in ``box``."""
        first, other = body.first_line_width(box), body.other_lines_width(box)
        return len(self.wrap(line.text, line.bold, size_pt, first, other))

    def height(
        self,
        lines: Sequence[Line],
        size_pt: float,
        box: Box,
        body: BodyFormat = DEFAULT_BODY_FORMAT,
    ) -> float:
        """Height in points of ``lines`` (one paragraph each) laid out in ``box``.

        Measured from the top of the text area (below the top inset) to the bottom of the
        glyphs of the last line, with automatic line wrapping.
        """
        if not lines:
            return 0.0
        rendered = sum(self.line_count(line, size_pt, box, body) for line in lines)
        total = rendered * body.line_pitch(size_pt)
        total += (len(lines) - 1) * body.paragraph_gap_pt
        total += DESCENT_OVERHANG_EM * size_pt
        return total * self._slack

    def fits(
        self,
        lines: Sequence[Line],
        size_pt: float,
        box: Box,
        body: BodyFormat = DEFAULT_BODY_FORMAT,
    ) -> bool:
        """True when ``lines`` fit inside ``box`` (the glyphs may use the bottom inset)."""
        return body.inset_top_pt + self.height(lines, size_pt, box, body) <= box.height_pt
