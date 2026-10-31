"""Cria os blocos de Oração Eucarística que faltam, a partir do bloco III (MODELO_PPTX.md §5).

Nada novo é criado (CLAUDE.md, regra 2): cada bloco é montado **só** com slides duplicados do
``III.pptx`` — o slide de imagem, o slide de resposta, o slide do ``{{liturgia.misterio_fe}}`` e o
slide final do "Amém" — na ordem imagem/resposta, e o texto das respostas é trocado no nível do
*run* (preserva ``rPr``/``pPr``). Nenhuma forma, imagem, estilo ou slide é desenhado por código.

Fonte do texto (CLAUDE.md, regra 1 — o texto litúrgico nunca vem de memória):
"Orações Eucarísticas — Terceira Edição Típica do Missal Romano" (45 p.), em
https://www.paroquiasaosebastiao.org.br/site/wp-content/uploads/Oracoes-Eucaristicas-3a-Edicao-do-Missal.pdf
As respostas abaixo são as falas da assembleia (``T:``) que vêm **depois** do Santo e até o Amém
final da doxologia, na ordem do Missal; o número de página do PDF vai no comentário de cada bloco.

Duas convenções, aplicadas ao copiar do Missal para o slide:

* as três opções de resposta do "Mistério da fé" viram **um** slide com a etiqueta
  ``{{liturgia.misterio_fe}}``, preenchida com o texto do folheto da missa (decisão do Pedro,
  2026-10-30; vale também para a OE V e as das Crianças, que têm aclamação própria);
* quando a mesma resposta já existe num bloco aprovado, vale a grafia do bloco aprovado
  (o Missal traz "Enviai o Vosso Espírito Santo!" na OE II e "Ajudai-nos a criar um mundo novo."
  na DC III; os blocos aprovados usam "vosso" e "novo!").

A OE das Crianças I tem, além destas, duas aclamações "Glória a vós, Senhor, que tanto nos amais!"
**dentro do prefácio**, antes do Santo; o bloco de OE do modelo começa depois do Santo, então elas
ficam de fora (decisão do Pedro, 2026-10-30).

Cada bloco foi conferido numa segunda fonte independente do PDF (transcrições que citam a página
do Missal, como hojeediadeliturgia.com.br e pspsp.curitiba.br). A única correção veio da OE V,
anotada na tabela abaixo.

Uso::

    python scripts/create_prayer_blocks.py            # escreve os blocos que faltam
    python scripts/create_prayer_blocks.py --check    # só confere que o método reproduz os
                                                      # blocos já aprovados (II, III, DC IV)
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

from pptx import Presentation
from pptx.presentation import Presentation as PresentationType
from pptx.slide import Slide

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pallotti_slides.presentation.slides_xml import duplicate_slide, keep_slides

PRAYERS = Path(__file__).resolve().parents[1] / "src/pallotti_slides/resources/eucharistic_prayers"
SOURCE = PRAYERS / "III.pptx"

MYSTERY = "{{liturgia.misterio_fe}}"

#: id da OE (etiqueta e nome do arquivo) -> respostas da assembleia, na ordem do Missal.
BLOCKS: dict[str, tuple[str, ...]] = {
    # OE I ou Cânon Romano (PDF, p. 2-6)
    "I": (
        "Abençoai nossa oferenda, ó Senhor!",
        "Lembrai-vos, ó Pai, de vossos filhos!",
        "Em comunhão com os vossos Santos vos louvamos!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
    # OE IV (PDF, p. 13-16)
    "IV": (
        "A todos socorrestes com bondade!",
        "Por amor nos enviastes vosso Filho!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Lembrai-vos, ó Pai, da vossa Igreja!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
    # OE V (PDF, p. 17-18)
    "V": (
        "Mandai vosso Espírito Santo!",
        MYSTERY,
        "Recebei, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Caminhamos na estrada de Jesus!",
        # O PDF repete aqui "Caminhamos na estrada de Jesus!"; é erro dele. A resposta ao 2C
        # ("Dai ao vosso servo, o Papa N. …") é "Lembrai-vos, ó Pai, da vossa Igreja!" em
        # https://pspsp.curitiba.br/liturgia-eucaristica-novo-missal-romano/oracao-eucaristica-v/
        # e em https://www.hojeediadeliturgia.com.br/2025/05/oracao-eucaristica-v-nova-edicao.html
        # (Missal Romano, p. 564-568).
        "Lembrai-vos, ó Pai, da vossa Igreja!",
        "Esperamos entrar na vida eterna!",
        "A todos dai a luz que não se apaga!",
        "Amém!",
    ),
    # OE sobre a Reconciliação I (PDF, p. 19-21)
    "R_I": (
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Amém!",
    ),
    # OE sobre a Reconciliação II (PDF, p. 22-24)
    "R_II": (
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Lembrai-vos, ó Pai, da vossa Igreja!",
        "Amém!",
    ),
    # OE para Diversas Circunstâncias I (PDF, p. 25-27)
    "DC_I": (
        "Bendito o vosso Filho, presente entre nós!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Confirmai na unidade a vossa Igreja!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
    # OE para Diversas Circunstâncias II (PDF, p. 28-30)
    "DC_II": (
        "Bendito o vosso Filho, presente entre nós!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Confirmai na unidade a vossa Igreja!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
    # OE para Diversas Circunstâncias III (PDF, p. 31-33)
    "DC_III": (
        "Bendito o vosso Filho, presente entre nós!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Confirmai na unidade a vossa Igreja!",
        "Ajudai-nos a criar um mundo novo!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
    # OE para Missa com as crianças I (PDF, p. 37-39)
    "C_I": (
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Com Jesus, recebei a nossa vida!",
        "Fazei de nós um só corpo e um só espírito!",
        "Amém!",
    ),
    # OE para Missa com as crianças II (PDF, p. 40-42)
    "C_II": (
        "Glória a vós, Senhor, que tanto nos amais!",
        "Glória a vós, Senhor, que tanto nos amais!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Com Jesus, recebei a nossa vida!",
        "Fazei de nós um só corpo e um só espírito!",
        "Fazei de nós um só corpo e um só espírito!",
        "Amém!",
    ),
    # OE para Missa com as crianças III (PDF, p. 43-45)
    "C_III": (
        "Glória a vós, ó Pai, que em Cristo nos salvais.",
        "Glória a vós, ó Pai, que em Cristo nos salvais.",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Com Jesus, recebei a nossa vida!",
        "Glória a vós, ó Pai, que em Cristo nos salvais.",
        "Fazei de nós um só corpo e um só espírito!",
        "Amém!",
    ),
}

#: Blocos já aprovados: não são reescritos, servem para conferir o método (``--check``).
APPROVED: dict[str, tuple[str, ...]] = {
    "II": (
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Lembrai-vos, ó Pai, da vossa Igreja!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
    "III": (
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Fazei de nós uma perfeita oferenda!",
        "Lembrai-vos, ó Pai, da vossa Igreja!",
        "Amém!",
    ),
    "DC_IV": (
        "Bendito o vosso Filho, presente entre nós!",
        "Enviai o vosso Espírito Santo!",
        MYSTERY,
        "Aceitai, ó Senhor, a nossa oferta!",
        "O Espírito nos una num só corpo!",
        "Confirmai na unidade a vossa Igreja!",
        "Ajudai-nos a criar um mundo novo!",
        "Concedei-lhes, ó Senhor, a luz eterna!",
        "Amém!",
    ),
}

# Protótipos dentro do III.pptx (1-based, conferidos por `pallotti template inspect`).
IMAGE_SLIDE = 1
RESPONSE_SLIDE = 2
MYSTERY_SLIDE = 4
AMEN_SLIDE = 14


def response_text(slide: Slide) -> str:
    """O texto da resposta do slide, sem o ``R:`` vermelho e sem espaços nas pontas."""
    parts = [
        run.text
        for shape in slide.shapes
        if shape.has_text_frame
        for paragraph in shape.text_frame.paragraphs
        for run in paragraph.runs
    ]
    return "".join(parts).removeprefix("R:").replace("\xa0", " ").strip()


def set_response(slide: Slide, text: str) -> None:
    """Troca o texto da resposta no nível do *run*, mantendo o ``R:`` e a formatação."""
    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        for paragraph in shape.text_frame.paragraphs:
            runs = paragraph.runs
            if not runs or runs[0].text.strip() != "R:":
                continue
            # protótipo da resposta: 'R:' + espaço + texto; do "Amém": 'R:' + ' Amém!'
            runs[-1].text = text if len(runs) > 2 else f" {text}"
            return
    raise SystemExit(f"slide sem a resposta 'R: …' para receber {text!r}")


def build_block(prayer: str, responses: Sequence[str], target: Path) -> None:
    """Escreve ``target`` com um slide de imagem + um de resposta para cada resposta."""
    presentation: PresentationType = Presentation(str(SOURCE))
    slides = list(presentation.slides)
    image = slides[IMAGE_SLIDE - 1]
    prototypes = {
        "response": slides[RESPONSE_SLIDE - 1],
        "mystery": slides[MYSTERY_SLIDE - 1],
        "amen": slides[AMEN_SLIDE - 1],
    }
    if response_text(prototypes["mystery"]) != MYSTERY:
        raise SystemExit(f"{SOURCE.name}: slide {MYSTERY_SLIDE} não é o do mistério da fé")

    ordered: list[Slide] = []
    last = len(responses) - 1
    for index, text in enumerate(responses):
        ordered.append(duplicate_slide(presentation, image))
        kind = "mystery" if text == MYSTERY else "amen" if index == last else "response"
        copy = duplicate_slide(presentation, prototypes[kind])
        if kind != "mystery":
            set_response(copy, text)
        ordered.append(copy)

    keep_slides(presentation, ordered)
    for slide in presentation.slides:
        slide.notes_slide.notes_text_frame.text = f"@pallotti oe={prayer}"
    presentation.save(str(target))


def block_summary(path: Path) -> tuple[int, tuple[str, ...]]:
    """Número de slides e as respostas (os slides de imagem não têm texto)."""
    presentation = Presentation(str(path))
    slides = list(presentation.slides)
    return len(slides), tuple(text for s in slides if (text := response_text(s)))


def check_approved() -> int:
    """Monta os blocos aprovados num diretório temporário e compara com os arquivos da pasta."""
    failures = 0
    with tempfile.TemporaryDirectory() as directory:
        for prayer, responses in APPROVED.items():
            built = Path(directory) / f"{prayer}.pptx"
            build_block(prayer, responses, built)
            expected = block_summary(PRAYERS / f"{prayer}.pptx")
            got = block_summary(built)
            status = "ok" if got == expected else "DIFERENTE"
            print(f"  {prayer:<6} {status}: {got[0]} slides, {len(got[1])} respostas")
            if got != expected:
                failures += 1
                for index, (one, other) in enumerate(zip(expected[1], got[1], strict=False), 1):
                    if one != other:
                        print(f"    resposta {index}: aprovado {one!r} != montado {other!r}")
    return failures


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="só confere os blocos aprovados")
    arguments = parser.parse_args()

    print(f"conferindo o método nos blocos aprovados (base: {SOURCE.name})")
    if check_approved():
        raise SystemExit("o método não reproduz um bloco aprovado; nada foi escrito")
    if arguments.check:
        return

    print("\nescrevendo os blocos que faltam")
    for prayer, responses in BLOCKS.items():
        target = PRAYERS / f"{prayer}.pptx"
        build_block(prayer, responses, target)
        slides, written = block_summary(target)
        if written != tuple(responses):
            raise SystemExit(f"{target.name}: as respostas escritas não são as esperadas")
        print(f"  {target.name:<12} {slides:>2} slides, {len(written)} respostas")


if __name__ == "__main__":
    main()
