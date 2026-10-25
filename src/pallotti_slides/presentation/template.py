"""The tagged PowerPoint template (MODELO_PPTX.md): read slide tags and text tags.

Tags in the template are in Portuguese (the team edits them in PowerPoint); this module maps
them to the English enums and field names of the code.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal, Self

from lxml.etree import _Element
from pptx import Presentation
from pptx.presentation import Presentation as PresentationType
from pptx.shapes.autoshape import Shape
from pptx.shapes.base import BaseShape
from pptx.slide import Slide

from pallotti_slides.domain.enums import EucharisticPrayer, SongMoment
from pallotti_slides.domain.models import Notice
from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.measurer import (
    EMU_PER_POINT,
    BodyFormat,
    Box,
)

TAG_PREFIX = "@pallotti"
SECOND_READING_GROUP = "segunda_leitura"
SONG_GROUP_PREFIX = "canto:"
# ``@pallotti oe=slot``: marker slide of the template where the chosen prayer block goes.
PRAYER_SLOT_ID = "slot"

# Tag moment id (Portuguese, as written in the template) <-> SongMoment.
MOMENT_BY_TAG: dict[str, SongMoment] = {
    "mantra": SongMoment.MANTRA,
    "entrada": SongMoment.ENTRANCE,
    "ato_penitencial": SongMoment.PENITENTIAL_ACT,
    "gloria": SongMoment.GLORIA,
    "aclamacao": SongMoment.ACCLAMATION,
    "ofertorio": SongMoment.OFFERTORY,
    "comunhao": SongMoment.COMMUNION,
    "pos_comunhao": SongMoment.POST_COMMUNION,
    "saida": SongMoment.RECESSIONAL,
}
MOMENT_TAGS: dict[SongMoment, str] = {moment: tag for tag, moment in MOMENT_BY_TAG.items()}

# ``{{tag}}`` written in the slides (Portuguese) -> field name used by the code (English).
FIELD_BY_TAG: dict[str, str] = {
    "celebracao.titulo": "celebration.title",
    "liturgia.primeira_leitura": "liturgy.first_reading",
    "liturgia.salmo_numero": "liturgy.psalm_number",
    "liturgia.salmo_refrao": "liturgy.psalm_refrain",
    "liturgia.segunda_leitura": "liturgy.second_reading",
    "liturgia.evangelho": "liturgy.gospel",
    "liturgia.preces_refrao": "liturgy.intercessions_response",
    "liturgia.misterio_fe": "liturgy.mystery_of_faith",
    "canto.rotulo": "song.label",
    "canto.texto": "song.text",
}
TAG_BY_FIELD: dict[str, str] = {name: tag for tag, name in FIELD_BY_TAG.items()}

SONG_LABEL_FIELD = "song.label"
SONG_TEXT_FIELD = "song.text"
MYSTERY_FIELD = "liturgy.mystery_of_faith"

Level = Literal["info", "warning", "error"]
_TEXT_TAG = re.compile(r"\{\{(.*?)\}\}")
# Tags cannot contain spaces, so the tag id is the enum value with "_" ("DC IV" -> "DC_IV").
_PRAYER_BY_ID = {prayer.value.replace(" ", "_"): prayer for prayer in EucharisticPrayer}
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
DEFAULT_SLIDE_SIZE = (12192000, 6858000)  # 16:9, EMU
# Insets of a:bodyPr when the attribute is absent (OOXML defaults), in EMU.
_DEFAULT_INSETS = {"lIns": 91440, "rIns": 91440, "tIns": 45720, "bIns": 45720}


class TagKind(StrEnum):
    """Role of a slide in the template."""

    FIXED = "fixed"
    GROUP = "group"
    SONG = "song"
    PRAYER = "prayer"
    PRAYER_SLOT = "prayer_slot"
    INVALID = "invalid"


@dataclass(frozen=True)
class SlideTag:
    """The ``@pallotti ...`` tag from the first line of a slide's notes.

    ``group`` is the group id as written in the template (``canto:entrada``,
    ``segunda_leitura``); song prototypes belong to ``canto:<moment>``.
    """

    kind: TagKind
    raw: str = ""
    explicit: bool = True
    group: str | None = None
    moment: SongMoment | None = None
    prayer: EucharisticPrayer | None = None
    error: str | None = None

    @classmethod
    def parse(cls, first_line: str | None) -> Self:
        """Parse the first line of the notes. Never raises: problems go to ``error``."""
        line = (first_line or "").strip()
        if not line.startswith(TAG_PREFIX):
            return cls(kind=TagKind.FIXED, raw=line, explicit=False)
        body = line[len(TAG_PREFIX) :].strip()
        if body == "fixo":
            return cls(kind=TagKind.FIXED, raw=line)
        key, sep, value = body.partition("=")
        key, value = key.strip(), value.strip()
        if sep and value and " " not in body:
            if key == "grupo":
                return cls._group(line, value)
            if key == "canto":
                moment = MOMENT_BY_TAG.get(value)
                if moment is not None:
                    return cls(
                        kind=TagKind.SONG,
                        raw=line,
                        group=f"{SONG_GROUP_PREFIX}{value}",
                        moment=moment,
                    )
                return cls._invalid(line, f"momento de canto desconhecido: '{value}'")
            if key == "oe":
                if value == PRAYER_SLOT_ID:
                    return cls(kind=TagKind.PRAYER_SLOT, raw=line)
                prayer = _PRAYER_BY_ID.get(value)
                if prayer is not None:
                    return cls(kind=TagKind.PRAYER, raw=line, prayer=prayer)
                return cls._invalid(line, f"Oração Eucarística desconhecida: '{value}'")
        return cls._invalid(line, "etiqueta mal formada")

    @classmethod
    def _group(cls, line: str, group: str) -> Self:
        known = group == SECOND_READING_GROUP or (
            group.startswith(SONG_GROUP_PREFIX)
            and group.removeprefix(SONG_GROUP_PREFIX) in MOMENT_BY_TAG
        )
        if not known:
            return cls._invalid(line, f"grupo desconhecido: '{group}'")
        moment = MOMENT_BY_TAG.get(group.removeprefix(SONG_GROUP_PREFIX))
        return cls(kind=TagKind.GROUP, raw=line, group=group, moment=moment)

    @classmethod
    def _invalid(cls, line: str, error: str) -> Self:
        return cls(kind=TagKind.INVALID, raw=line, error=error)


@dataclass(frozen=True)
class TemplateSlide:
    """One slide of the template. ``index`` is 0-based (``MassTemplate.slides[index]``)."""

    index: int
    tag: SlideTag
    fields: frozenset[str]
    text_box: Box | None = None
    unknown_tags: tuple[str, ...] = field(default=())
    split_tags: tuple[str, ...] = field(default=())
    body_format: BodyFormat | None = None  # paragraph/frame settings of ``{{canto.texto}}``


def default_template_path() -> Path:
    """Location of the template shipped with the program."""
    return Path(__file__).resolve().parents[1] / "resources" / "template" / "mass_template.pptx"


def default_prayers_dir() -> Path:
    """Folder of the Eucharistic prayer blocks shipped with the program (one .pptx per prayer)."""
    return Path(__file__).resolve().parents[1] / "resources" / "eucharistic_prayers"


def prayer_id(prayer: EucharisticPrayer) -> str:
    """Id of ``prayer`` in tags and file names (``DC IV`` -> ``DC_IV``)."""
    return prayer.value.replace(" ", "_")


@dataclass(frozen=True)
class PrayerBlock:
    """The slides of one Eucharistic prayer: ``<prayers_dir>/<id>.pptx`` (MODELO_PPTX.md §5)."""

    prayer: EucharisticPrayer
    path: Path
    slides: list[TemplateSlide]
    slide_size: tuple[int, int] = DEFAULT_SLIDE_SIZE
    layouts: frozenset[str] = frozenset()


def _open(path: Path, what: str) -> PresentationType:
    if not path.is_file():
        raise TemplateError(f"{what} não encontrado: {path}")
    try:
        return Presentation(str(path))
    except Exception as error:  # python-pptx raises many kinds of errors on bad files
        raise TemplateError(f"Não foi possível abrir {path.name}: {error}") from error


def _slide_size(presentation: PresentationType) -> tuple[int, int]:
    return (
        int(presentation.slide_width or DEFAULT_SLIDE_SIZE[0]),
        int(presentation.slide_height or DEFAULT_SLIDE_SIZE[1]),
    )


def _layout_names(presentation: PresentationType) -> frozenset[str]:
    return frozenset(
        layout.name for master in presentation.slide_masters for layout in master.slide_layouts
    )


def load_prayer_blocks(
    folder: Path,
) -> tuple[dict[EucharisticPrayer, PrayerBlock], list[Notice]]:
    """Every ``<id>.pptx`` of ``folder``; unreadable or unknown files become notices."""
    blocks: dict[EucharisticPrayer, PrayerBlock] = {}
    problems: list[Notice] = []
    files = sorted(folder.glob("*.pptx")) if folder.is_dir() else []
    for file in files:
        if file.name.startswith((".", "~$")):  # PowerPoint lock files, partial writes
            continue
        prayer = _PRAYER_BY_ID.get(file.stem)
        if prayer is None:
            problems.append(
                Notice(
                    level="warning",
                    message=f"Arquivo de OE com nome desconhecido (ignorado): {file.name}.",
                    field=file.name,
                )
            )
            continue
        try:
            presentation = _open(file, "Bloco de OE")
        except TemplateError as error:
            problems.append(Notice(level="error", message=str(error), field=file.name))
            continue
        slides = [_read_slide(i, slide) for i, slide in enumerate(presentation.slides)]
        blocks[prayer] = PrayerBlock(
            prayer=prayer,
            path=file,
            slides=slides,
            slide_size=_slide_size(presentation),
            layouts=frozenset(slide.slide_layout.name for slide in presentation.slides),
        )
    return blocks, problems


class MassTemplate:
    """The tagged template plus the prayer blocks, read once into memory (files never change)."""

    def __init__(
        self,
        path: Path,
        slides: list[TemplateSlide],
        slide_size: tuple[int, int] = DEFAULT_SLIDE_SIZE,
        prayers: Mapping[EucharisticPrayer, PrayerBlock] | None = None,
        problems: list[Notice] | None = None,
        layouts: frozenset[str] = frozenset(),
    ) -> None:
        self.path = path
        self.slides = slides
        self.slide_width, self.slide_height = slide_size
        self.prayers: dict[EucharisticPrayer, PrayerBlock] = dict(prayers or {})
        self.layouts = layouts
        self._problems = list(problems or [])

    @classmethod
    def load(cls, path: Path | None = None, prayers_dir: Path | None = None) -> Self:
        """Read the template and the prayer blocks (``default_prayers_dir()`` by default)."""
        path = path or default_template_path()
        presentation = _open(path, "Modelo do PowerPoint")
        slides = [_read_slide(index, slide) for index, slide in enumerate(presentation.slides)]
        prayers, problems = load_prayer_blocks(prayers_dir or default_prayers_dir())
        return cls(
            path,
            slides,
            _slide_size(presentation),
            prayers=prayers,
            problems=problems,
            layouts=_layout_names(presentation),
        )

    def prototype(self, moment: SongMoment) -> TemplateSlide | None:
        """The song prototype slide of ``moment`` (``@pallotti canto=...``)."""
        for slide in self.slides:
            if slide.tag.kind is TagKind.SONG and slide.tag.moment is moment:
                return slide
        return None

    def song_area(self, moment: SongMoment) -> Box:
        """Area for the song body of ``moment``: the prototype's ``{{canto.texto}}`` box itself."""
        prototype = self.prototype(moment)
        if prototype is None or prototype.text_box is None:
            tag = MOMENT_TAGS[moment]
            raise TemplateError(
                f"O modelo não tem o protótipo de canto '{tag}' com {{{{canto.texto}}}}."
            )
        return prototype.text_box

    def body_format(self, moment: SongMoment) -> BodyFormat:
        """Paragraph/frame settings of the song body of ``moment``."""
        prototype = self.prototype(moment)
        if prototype is None or prototype.body_format is None:
            return BodyFormat()
        return prototype.body_format

    def available_prayers(self) -> list[EucharisticPrayer]:
        """Eucharistic prayers that have a block file in the prayers folder, in numeric order."""
        return [prayer for prayer in EucharisticPrayer if prayer in self.prayers]

    def prayer_block(self, prayer: EucharisticPrayer) -> PrayerBlock:
        block = self.prayers.get(prayer)
        if block is None:
            raise TemplateError(
                f"Não há o bloco da Oração Eucarística {prayer.value} "
                f"({prayer_id(prayer)}.pptx na pasta das OEs)."
            )
        return block

    def prayer_slot(self) -> TemplateSlide | None:
        """The marker slide ``@pallotti oe=slot`` (where the chosen prayer block goes)."""
        return next((s for s in self.slides if s.tag.kind is TagKind.PRAYER_SLOT), None)

    def validate(self) -> list[Notice]:
        """Problems of the template and of the prayer blocks (MODELO_PPTX.md §6)."""
        notices: list[Notice] = list(self._problems)

        def add(level: Level, slide: TemplateSlide | None, message: str) -> None:
            where = f"slide {slide.index + 1}" if slide else None
            notices.append(Notice(level=level, message=message, field=where))

        prototypes: dict[SongMoment, list[TemplateSlide]] = {}
        slots: list[TemplateSlide] = []
        for slide in self.slides:
            if slide.tag.kind is TagKind.INVALID:
                add("error", slide, f"Etiqueta inválida ({slide.tag.error}): {slide.tag.raw!r}.")
            elif not slide.tag.explicit:
                add(
                    "warning",
                    slide,
                    "Slide sem etiqueta @pallotti nas anotações (tratado como fixo).",
                )
            if slide.tag.kind is TagKind.SONG and slide.tag.moment is not None:
                prototypes.setdefault(slide.tag.moment, []).append(slide)
            if slide.tag.kind is TagKind.PRAYER_SLOT:
                slots.append(slide)
            if slide.tag.kind is TagKind.PRAYER:
                add(
                    "error",
                    slide,
                    "Slides de Oração Eucarística ficam no arquivo da OE (pasta "
                    "eucharistic_prayers); no modelo fica só o marcador @pallotti oe=slot.",
                )
            for tag in slide.unknown_tags:
                add("error", slide, f"Etiqueta de texto desconhecida: {{{{{tag}}}}}.")
            for tag in slide.split_tags:
                add(
                    "error",
                    slide,
                    f"Etiqueta {{{{{tag}}}}} dividida em vários trechos de texto; "
                    "apague e digite de novo de uma vez.",
                )
            is_song = slide.tag.kind is TagKind.SONG
            if is_song and SONG_TEXT_FIELD not in slide.fields:
                add("error", slide, "Protótipo de canto sem {{canto.texto}}.")
            if is_song and SONG_LABEL_FIELD not in slide.fields:
                add("warning", slide, "Protótipo de canto sem {{canto.rotulo}}.")
            song_fields = slide.fields & {SONG_LABEL_FIELD, SONG_TEXT_FIELD}
            if song_fields and not is_song:
                add("error", slide, "Etiquetas {{canto.*}} só podem ficar em protótipo de canto.")

        for moment in SongMoment:
            found = prototypes.get(moment, [])
            tag = MOMENT_TAGS[moment]
            if not found:
                add("error", None, f"Falta o protótipo de canto '{tag}' ({moment.label}).")
            for extra in found[1:]:
                add("error", extra, f"Protótipo de canto '{tag}' duplicado.")

        if not slots:
            add("error", None, "Falta o slide marcador da Oração Eucarística (@pallotti oe=slot).")
        for extra in slots[1:]:
            add("error", extra, "Marcador @pallotti oe=slot duplicado.")
        for block in self.prayers.values():
            notices.extend(self._validate_block(block))
        if not self.available_prayers():
            add(
                "error",
                None,
                "Não há nenhum bloco de Oração Eucarística na pasta das OEs (<id>.pptx).",
            )
        return notices

    def _validate_block(self, block: PrayerBlock) -> list[Notice]:
        name = block.path.name
        expected = f"{TAG_PREFIX} oe={prayer_id(block.prayer)}"
        notices: list[Notice] = []

        def add(level: Level, slide: TemplateSlide | None, message: str) -> None:
            where = f"{name}, slide {slide.index + 1}" if slide else name
            notices.append(Notice(level=level, message=message, field=where))

        if not block.slides:
            add("error", None, f"O bloco da OE {block.prayer.value} não tem slides.")
        if block.slide_size != (self.slide_width, self.slide_height):
            add("error", None, "O tamanho dos slides é diferente do modelo.")
        for layout in sorted(block.layouts - self.layouts) if self.layouts else []:
            add("error", None, f"O modelo não tem o layout {layout!r} usado no bloco.")
        for slide in block.slides:
            if slide.tag.kind is not TagKind.PRAYER or slide.tag.prayer is not block.prayer:
                add("error", slide, f"A etiqueta do slide deve ser {expected!r}.")
            for tag in slide.unknown_tags:
                add("error", slide, f"Etiqueta de texto desconhecida: {{{{{tag}}}}}.")
            for tag in slide.split_tags:
                add(
                    "error",
                    slide,
                    f"Etiqueta {{{{{tag}}}}} dividida em vários trechos de texto; "
                    "apague e digite de novo de uma vez.",
                )
            if slide.fields & {SONG_LABEL_FIELD, SONG_TEXT_FIELD}:
                add("error", slide, "Etiquetas {{canto.*}} só podem ficar em protótipo de canto.")
        if block.slides and not any(MYSTERY_FIELD in s.fields for s in block.slides):
            add(
                "warning",
                None,
                f"O bloco da OE {block.prayer.value} não tem {{{{liturgia.misterio_fe}}}}.",
            )
        return notices


def _first_notes_line(slide: Slide) -> str | None:
    if not slide.has_notes_slide:
        return None
    text = slide.notes_slide.notes_text_frame.text if slide.notes_slide.notes_text_frame else ""
    for line in text.splitlines():
        if line.strip():
            return line
    return None


def _emu_pt(value: str | None, default: int) -> float:
    return (int(value) if value is not None else default) / EMU_PER_POINT


def _spacing_pt(ppr: _Element | None, name: str) -> float | None:
    """``a:spcBef``/``a:spcAft``/``a:lnSpc`` given in points (``spcPts``), if any."""
    if ppr is None:
        return None
    points = ppr.find(f"{_A}{name}/{_A}spcPts")
    return int(points.get("val", "0")) / 100 if points is not None else None


def read_body_format(text_body: _Element, paragraph: _Element) -> BodyFormat:
    """``BodyFormat`` of ``paragraph`` (``a:p``) inside ``text_body`` (``p:txBody``).

    Only values written in the slide are read; absent ones take the OOXML defaults (100 %
    line spacing, no paragraph spacing, no indent).
    """
    body_pr = text_body.find(f"{_A}bodyPr")
    insets = {
        name: _emu_pt(body_pr.get(name) if body_pr is not None else None, default)
        for name, default in _DEFAULT_INSETS.items()
    }
    ppr = paragraph.find(f"{_A}pPr")
    line_spacing = 1.0
    percent = ppr.find(f"{_A}lnSpc/{_A}spcPct") if ppr is not None else None
    if percent is not None:
        line_spacing = int(percent.get("val", "100000")) / 100000
    return BodyFormat(
        line_spacing=line_spacing,
        line_spacing_pt=_spacing_pt(ppr, "lnSpc"),
        space_before_pt=_spacing_pt(ppr, "spcBef") or 0.0,
        space_after_pt=_spacing_pt(ppr, "spcAft") or 0.0,
        margin_left_pt=_emu_pt(ppr.get("marL") if ppr is not None else None, 0),
        indent_pt=_emu_pt(ppr.get("indent") if ppr is not None else None, 0),
        inset_left_pt=insets["lIns"],
        inset_right_pt=insets["rIns"],
        inset_top_pt=insets["tIns"],
        inset_bottom_pt=insets["bIns"],
    )


def _shape_box(shape: BaseShape) -> Box | None:
    if None in (shape.left, shape.top, shape.width, shape.height):
        return None
    return Box(
        left=int(shape.left or 0),
        top=int(shape.top or 0),
        width=int(shape.width or 0),
        height=int(shape.height or 0),
    )


def _read_slide(index: int, slide: Slide) -> TemplateSlide:
    tag = SlideTag.parse(_first_notes_line(slide))
    fields: set[str] = set()
    unknown: list[str] = []
    split: list[str] = []
    text_box: Box | None = None
    body_format: BodyFormat | None = None
    for shape in slide.shapes:
        if not isinstance(shape, Shape) or not shape.has_text_frame:
            continue
        for paragraph in shape.text_frame.paragraphs:
            run_texts = [run.text for run in paragraph.runs]
            whole = _TEXT_TAG.findall("".join(run_texts))
            whole_in_run = [name for text in run_texts for name in _TEXT_TAG.findall(text)]
            for name in whole_in_run:
                known = FIELD_BY_TAG.get(name.strip())
                if known is None:
                    unknown.append(name)
                    continue
                fields.add(known)
                if known == SONG_TEXT_FIELD and text_box is None:
                    text_box = _shape_box(shape)
                    body_format = read_body_format(shape.text_frame._txBody, paragraph._p)
            if len(whole) != len(whole_in_run):
                split.extend(name for name in whole if name not in whole_in_run)
    return TemplateSlide(
        index=index,
        tag=tag,
        fields=frozenset(fields),
        text_box=text_box,
        unknown_tags=tuple(unknown),
        split_tags=tuple(split),
        body_format=body_format,
    )
