"""Cria o bloco da Oração Eucarística II a partir do bloco III (MODELO_PPTX.md §5).

Nada novo é criado: o arquivo é uma cópia do ``III.pptx`` e só o texto das respostas da
assembleia é trocado, no nível do *run* (preservando rPr/pPr). As respostas vêm do folheto
"O Domingo" de 02/11/2026 (Todos os Fiéis Defuntos), item 12 — Oração Eucarística II.

Sequência das respostas na OE II (folheto), nesta ordem:
  1. Enviai o vosso Espírito Santo!            (igual à OE III)
  2. {{liturgia.misterio_fe}}                  (etiqueta, igual à OE III)
  3. Aceitai, ó Senhor, a nossa oferta!        (igual à OE III)
  4. O Espírito nos una num só corpo!          (igual à OE III)
  5. Lembrai-vos, ó Pai, da vossa Igreja!      (estava no slide 12 da OE III)
  6. Concedei-lhes, ó Senhor, a luz eterna!    (própria da OE II)
  7. Amém!                                     (igual à OE III)

A OE III tem exatamente o mesmo número de slides de resposta (7), então basta trocar o texto
de dois deles: nenhum slide é criado, apagado ou reordenado.
"""

import shutil
from pathlib import Path

from pptx import Presentation

PRAYERS = Path(__file__).resolve().parents[1] / "src/pallotti_slides/resources/eucharistic_prayers"
SOURCE = PRAYERS / "III.pptx"
TARGET = PRAYERS / "II.pptx"

# slide (1-based) -> (texto esperado hoje, texto novo)
REPLACEMENTS: dict[int, tuple[str, str]] = {
    10: ("Fazei de nós uma perfeita oferenda!", "Lembrai-vos, ó Pai, da vossa Igreja!"),
    12: ("Lembrai-vos, ó Pai, da vossa Igreja!", "Concedei-lhes, ó Senhor, a luz eterna!"),
}

TAG = "@pallotti oe=II"


def main() -> None:
    shutil.copyfile(SOURCE, TARGET)
    presentation = Presentation(str(TARGET))
    done: set[int] = set()
    for number, slide in enumerate(presentation.slides, start=1):
        slide.notes_slide.notes_text_frame.text = TAG
        if number not in REPLACEMENTS:
            continue
        expected, new = REPLACEMENTS[number]
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    if run.text.strip() == expected:
                        run.text = new  # run level: rPr is preserved
                        done.add(number)
    missing = sorted(set(REPLACEMENTS) - done)
    if missing:
        raise SystemExit(f"texto esperado não encontrado nos slides {missing}")
    presentation.save(str(TARGET))
    print(f"escrito: {TARGET}")
    for number, slide in enumerate(Presentation(str(TARGET)).slides, start=1):
        texts = [
            " ".join(run.text for par in shape.text_frame.paragraphs for run in par.runs)
            for shape in slide.shapes
            if shape.has_text_frame
        ]
        body = " ".join(text for text in texts if text.strip())
        print(f"  {number:>2}  {body or '(imagem)'}")


if __name__ == "__main__":
    main()
