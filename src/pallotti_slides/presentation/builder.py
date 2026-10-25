"""Executes a ``SlidePlan`` on a copy of the template (ARQUITETURA §5, SPEC F8)."""

from pathlib import Path

from pptx import Presentation
from pptx.slide import Slide

from pallotti_slides.presentation.errors import TemplateError
from pallotti_slides.presentation.planner import SlidePlan, TextContent
from pallotti_slides.presentation.slides_xml import (
    BodyLine,
    duplicate_slide,
    keep_slides,
    remove_note_lines,
    replace_body,
    replace_run_tags,
    text_tags,
)
from pallotti_slides.presentation.template import FIELD_BY_TAG, TAG_BY_FIELD, TAG_PREFIX


class PptxBuilder:
    """Writes the deck: duplicates/removes/reorders slides and fills the ``{{...}}`` tags.

    1. every slide of the plan is the template slide itself (first use) or a copy made from
       the untouched template slide (next uses); unused slides are removed;
    2. tags are replaced at the run level (formatting kept); the song body is rebuilt as one
       centred paragraph per line (``slides_xml.replace_body``);
    3. the ``@pallotti`` lines are removed from the speaker notes.
    The template file is never modified.
    """

    def build(self, template_path: Path, plan: SlidePlan, destination: Path) -> Path:
        try:
            presentation = Presentation(str(template_path))
        except Exception as error:  # python-pptx raises many kinds of errors on bad files
            raise TemplateError(
                f"Não foi possível abrir o modelo {template_path.name}: {error}"
            ) from error
        originals = list(presentation.slides)
        for target in plan:
            if not 0 <= target.source < len(originals):
                raise TemplateError(
                    f"O plano cita o slide {target.source + 1}, que não existe no modelo."
                )

        # 1. Allocate the slides first, so every copy comes from an untouched template slide.
        used: set[int] = set()
        slides: list[Slide] = []
        for target in plan:
            original = originals[target.source]
            if target.source in used:
                slides.append(duplicate_slide(presentation, original))
            else:
                used.add(target.source)
                slides.append(original)

        # 2. Texts.
        for slide, target in zip(slides, plan, strict=True):
            self._fill(slide, target.replacements, target.source)

        # 3. Order, removal and notes.
        keep_slides(presentation, slides)
        for slide in slides:
            if slide.has_notes_slide:
                remove_note_lines(slide.notes_slide.element, TAG_PREFIX)

        # Write next to the destination and rename: a failure never leaves half a file.
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.stem}.partial.pptx")
        try:
            presentation.save(str(temporary))
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    @staticmethod
    def _fill(slide: Slide, replacements: dict[str, TextContent], source: int) -> None:
        root = slide.element
        for field, content in replacements.items():
            if content.is_body:
                tag = TAG_BY_FIELD[field]
                lines = [BodyLine(line.text, line.bold) for line in content.lines]
                try:
                    replace_body(root, tag, lines, content.size_pt or 0)
                except ValueError as error:
                    raise TemplateError(
                        f"O slide {source + 1} do modelo não tem {{{{{tag}}}}}."
                    ) from error

        def value(tag: str) -> str:
            field = FIELD_BY_TAG.get(tag)
            content = replacements.get(field) if field else None
            if content is None or content.is_body:
                raise TemplateError(
                    f"A etiqueta {{{{{tag}}}}} do slide {source + 1} do modelo não tem valor."
                )
            return content.text

        replace_run_tags(root, value)
        left = text_tags(root)
        if left:
            raise TemplateError(f"Etiquetas sem substituição no slide {source + 1}: {left}.")
