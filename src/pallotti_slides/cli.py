"""Command-line interface (``pallotti ...``)."""

import platform
from pathlib import Path
from typing import Annotated

import typer

from pallotti_slides import __version__
from pallotti_slides.application.container import create_container
from pallotti_slides.application.generate_mass import load_mass
from pallotti_slides.application.leaflet_extraction import (
    extract_leaflet,
    make_leaflet_extractor,
)
from pallotti_slides.application.song_requests import (
    ResolutionResult,
    import_song,
    propose_repertoire,
    resolve_text,
)
from pallotti_slides.application.template_tools import TemplateTools
from pallotti_slides.config import FontLocator, load_settings, locate_soffice
from pallotti_slides.domain.enums import SongMoment
from pallotti_slides.domain.errors import PallottiError
from pallotti_slides.domain.models import Notice

app = typer.Typer(
    name="pallotti",
    help="Pallotti Slides: gera os slides da missa de domingo.",
    no_args_is_help=True,
    add_completion=False,
)
template_app = typer.Typer(
    help="Inspeciona e pré-visualiza o modelo PowerPoint.",
    no_args_is_help=True,
)
app.add_typer(template_app, name="template")

TemplateOption = Annotated[
    Path | None,
    typer.Option(
        "--template",
        help="Modelo .pptx a usar (padrão: o modelo do programa).",
        dir_okay=False,
    ),
]


leaflet_app = typer.Typer(help="Folheto litúrgico (PDF).", no_args_is_help=True)
app.add_typer(leaflet_app, name="leaflet")


def _line(label: str, path: Path | None, hint: str) -> str:
    if path is None:
        return f"{label}: NÃO encontrado. {hint}"
    return f"{label}: {path}"


@app.callback(help="Pallotti Slides: gera os slides da missa de domingo.")
def main_callback() -> None:
    """Root callback; help text is set on the Typer app."""


@app.command(
    "doctor",
    help="Mostra versão, Python, LibreOffice e fonte Aptos (sai 0 mesmo se faltar algo).",
)
def diagnose() -> None:
    """Show version, Python, LibreOffice and Aptos font (exit 0 even if something is missing)."""
    fonts = FontLocator().locate()
    typer.echo(f"Pallotti Slides: {__version__}")
    typer.echo(f"Python: {platform.python_version()}")
    typer.echo(
        _line(
            "LibreOffice (soffice)",
            locate_soffice(),
            "Instale o LibreOffice para gerar o PDF.",
        )
    )
    font_hint = "Instale a Aptos (download gratuito da Microsoft) ou defina PALLOTTI_FONTS_DIR."
    typer.echo(_line("Aptos regular", fonts.regular, font_hint))
    typer.echo(_line("Aptos negrito", fonts.bold, font_hint))


@app.command(
    "generate",
    help="Gera o PowerPoint e o PDF de uma missa a partir de um arquivo JSON.",
)
def generate(
    mass: Annotated[
        Path,
        typer.Option("--mass", help="Arquivo JSON da missa.", exists=True, dir_okay=False),
    ],
    output: Annotated[Path, typer.Option("--output", help="Pasta de saída.", file_okay=False)],
    template: TemplateOption = None,
    pdf: Annotated[
        bool, typer.Option("--pdf/--no-pdf", help="Gerar também o PDF (LibreOffice).")
    ] = True,
) -> None:
    """Generate the .pptx (and .pdf) of a Mass; exit 1 on a fatal error."""
    try:
        container = create_container(load_settings(), template_path=template, with_pdf=pdf)
        try:
            result = container.generator.generate(load_mass(mass), output)
        finally:
            container.close()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"PowerPoint: {result.pptx}")
    typer.echo(f"PDF: {result.pdf if result.pdf else '(não gerado)'}")
    for notice in result.notices:
        where = f" [{notice.field}]" if notice.field else ""
        typer.echo(f"{notice.level.upper()}{where}: {notice.message}", err=True)


_LEAFLET_FIELDS = (
    ("Título", "title"),
    ("Data", "date"),
    ("Tempo litúrgico", "season"),
    ("Ano", "year"),
    ("1ª leitura", "first_reading"),
    ("Salmo", "psalm_number"),
    ("Refrão do salmo", "psalm_refrain"),
    ("2ª leitura", "second_reading"),
    ("Evangelho", "gospel"),
    ("Refrão das preces", "intercessions_response"),
    ("Oração eucarística", "eucharistic_prayer"),
    ("Mistério da fé", "mystery_of_faith"),
)


@leaflet_app.command(
    "extract",
    help="Extrai os dados do folheto (PDF) com IA. Precisa da chave da API da Anthropic.",
)
def extract_leaflet_command(
    pdf: Annotated[
        Path, typer.Argument(help="Arquivo PDF do folheto.", exists=True, dir_okay=False)
    ],
) -> None:
    """Extract leaflet data and print it; exit code 1 on a fatal error."""
    try:
        result = extract_leaflet(pdf, make_leaflet_extractor())
    except PallottiError as error:
        typer.echo(f"Erro: {error}", err=True)
        raise typer.Exit(code=1) from error
    for label, attribute in _LEAFLET_FIELDS:
        value = getattr(result.data, attribute)
        typer.echo(f"{label}: {value if value not in (None, '') else '(não encontrado)'}")
    for notice in result.notices:
        typer.echo(f"[{notice.level}] {notice.message}", err=True)


history_app = typer.Typer(help="Histórico de missas geradas.", no_args_is_help=True)
app.add_typer(history_app, name="history")


@history_app.command("list", help="Lista as missas geradas (mais recentes primeiro).")
def history_list(
    limit: Annotated[int, typer.Option("--limit", help="Máximo de missas listadas.", min=1)] = 50,
) -> None:
    """Print one line per saved Mass."""
    try:
        container = create_container(load_settings(), with_pdf=False)
        try:
            rows = container.mass_repo.list(limit)
        finally:
            container.close()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    if not rows:
        typer.echo("Nenhuma missa no histórico.")
        return
    for row in rows:
        typer.echo(
            f"{row.id:>4}  {row.date:%d/%m/%Y}  OE {row.eucharistic_prayer.value:<3}  "
            f"{row.title}  {row.pptx_path or '(sem arquivo)'}"
        )


@history_app.command("show", help="Mostra uma missa do histórico como JSON.")
def history_show(
    mass_id: Annotated[int, typer.Argument(help="Número da missa (history list).")],
) -> None:
    """Print the saved Mass as JSON; exit 1 if it does not exist."""
    try:
        container = create_container(load_settings(), with_pdf=False)
        try:
            mass = container.mass_repo.get(mass_id)
        finally:
            container.close()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(mass.model_dump_json(indent=2))


@template_app.command(
    "inspect",
    help="Lista os slides do modelo, suas etiquetas e problemas (sai 1 se houver erros).",
)
def template_inspect(template: TemplateOption = None) -> None:
    """Print the slide table and the problems of the template; exit 1 on errors."""
    try:
        report = TemplateTools(template).inspect()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Modelo: {report.path}")
    typer.echo(f"{'Slide':>5}  {'Etiqueta':<28}  Campos")
    for row in report.rows:
        typer.echo(f"{row.number:>5}  {row.tag:<28}  {row.fields}")
    typer.echo(f"Orações Eucarísticas: {', '.join(report.prayers) or 'nenhuma'}")
    for notice in report.notices:
        where = f" [{notice.field}]" if notice.field else ""
        typer.echo(f"{notice.level.upper()}{where}: {notice.message}")
    errors = sum(1 for notice in report.notices if notice.level == "error")
    typer.echo(f"{len(report.rows)} slides, {errors} erro(s).")
    if report.has_errors:
        raise typer.Exit(1)


@template_app.command(
    "preview",
    help="Gera um PNG por slide do modelo (precisa do LibreOffice e do pdftoppm).",
)
def template_preview(
    output: Annotated[Path, typer.Option("--output", help="Pasta de saída dos PNGs.")],
    template: TemplateOption = None,
) -> None:
    """Render the template to PNGs, one per slide."""
    try:
        pages = TemplateTools(template).preview(output)
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"{len(pages)} imagens em {output}")


songs_app = typer.Typer(help="Cantos: busca, importação e repertório.", no_args_is_help=True)
app.add_typer(songs_app, name="songs")


def _echo_notices(notices: list[Notice]) -> None:
    for notice in notices:
        where = f" [{notice.field}]" if notice.field else ""
        typer.echo(f"{notice.level.upper()}{where}: {notice.message}", err=True)


def _echo_result(result: ResolutionResult) -> None:
    origins = {"library": "biblioteca", "web": "internet", "pasted": "letra colada", "none": "-"}
    if result.song is not None:
        song = result.song
        by = f" - {song.artist}" if song.artist else ""
        typer.echo(f"  {song.title}{by} ({origins[result.origin]}; {len(song.stanzas)} estrofes)")
    elif result.candidates:
        typer.echo("  Possibilidades (confirme importando o link com `songs import --url`):")
        for number, candidate in enumerate(result.candidates, start=1):
            where = candidate.url or "(na biblioteca)"
            by = f" - {candidate.artist}" if candidate.artist else ""
            typer.echo(f"  {number}. {candidate.title}{by}  {where}")
    else:
        typer.echo("  Nenhum canto encontrado.")
    _echo_notices(result.notices)


@songs_app.command(
    "resolve",
    help="Resolve cantos pela biblioteca e pela internet. Sem --moment, o texto é livre "
    '(ex.: "Entrada: Me chamaste; Comunhão: Pão da vida") e usa a IA.',
)
def songs_resolve(
    text: Annotated[str, typer.Argument(help="Título, link, letra ou texto livre.")],
    moment: Annotated[
        SongMoment | None,
        typer.Option("--moment", help="Momento do canto; com ele o texto é um único pedido."),
    ] = None,
) -> None:
    """Resolve the requests in ``text`` and print the outcome of each."""
    try:
        container = create_container(load_settings(), with_pdf=False)
        try:
            outcomes = resolve_text(text, container.resolver, container.interpreter, moment)
        finally:
            container.close()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    if not outcomes:
        typer.echo("Nenhum pedido de canto encontrado no texto.")
    for outcome in outcomes:
        typer.echo(f"{outcome.request.moment.label}: {outcome.request.text[:60]}")
        _echo_result(outcome.result)


@songs_app.command("import", help="Baixa e salva na biblioteca o canto de um link.")
def songs_import(
    url: Annotated[str, typer.Option("--url", help="Link do Letras.mus.br ou do Cifra Club.")],
) -> None:
    """Import one song by URL; exit 1 when it could not be imported."""
    try:
        container = create_container(load_settings(), with_pdf=False)
        try:
            result = import_song(url, container.resolver)
        finally:
            container.close()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    _echo_result(result)
    if result.song is None:
        raise typer.Exit(1)


@songs_app.command(
    "repertoire",
    help="Lê um repertório do Cifra Club e PROPÕE o momento de cada canto (nada é aplicado).",
)
def songs_repertoire(
    url: Annotated[str, typer.Argument(help="Link do repertório no Cifra Club.")],
) -> None:
    """Print the moment proposal for a repertoire link."""
    try:
        container = create_container(load_settings(), with_pdf=False)
        try:
            proposal = propose_repertoire(url, container.repertoire_importer)
        finally:
            container.close()
    except PallottiError as error:
        typer.echo(f"ERRO: {error}", err=True)
        raise typer.Exit(1) from error
    typer.echo(f"Repertório: {proposal.source_url}")
    for number, item in enumerate(proposal.items, start=1):
        moment = item.moment.label if item.moment else "(sem momento)"
        typer.echo(
            f"{number:>3}. {moment:<22} {item.title} - {item.artist or '?'}  [{item.reason}]"
        )
    if proposal.unassigned:
        typer.echo(f"{len(proposal.unassigned)} canto(s) sem momento sugerido.")
    typer.echo("Esta é só uma PROPOSTA: confira os momentos antes de usar. Precisa de confirmação.")
