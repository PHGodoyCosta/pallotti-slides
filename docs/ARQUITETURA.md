# Pallotti Slides — Arquitetura

> O **como**. Complementa o [SPEC.md](SPEC.md) (o quê) e o [PLANO.md](PLANO.md)
> (a ordem). Nomes de classes e módulos aqui são o **contrato**: agentes podem
> criar funções auxiliares livremente, mas não devem renomear nem mover o que
> está listado sem atualizar este documento.
>
> **Glossário de nomes (português → inglês): [NOMES.md](NOMES.md).** É o
> contrato dos identificadores de código; este documento já usa os nomes novos.

## 1. Stack

| Camada | Biblioteca | Para quê |
|---|---|---|
| Linguagem | Python **3.13** | Versão com wheels estáveis para PySide6 e PyInstaller |
| Ambiente | **uv** | Dependências, lockfile, `uv run` |
| Interface | **PySide6** (≥ 6.8) | Qt para desktop |
| Componentes visuais | **PySide6-Fluent-Widgets** (`qfluentwidgets`) | Janela Fluent, navegação, cartões, ícones (`FluentIcon`), InfoBar, tema |
| Pré-visualização de PDF | **QtPdf** (já vem no PySide6) | Miniaturas dos slides gerados |
| PowerPoint | **python-pptx** (≥ 1.0) + **lxml** | Ler o modelo, substituir texto, manipular o XML dos slides |
| Medição de texto | **Pillow** (`ImageFont`) | Largura e altura reais com a fonte Aptos |
| PDF | **LibreOffice** (`soffice --headless`) | Conversão pptx → pdf (dependência externa) |
| Modelos de dados | **pydantic** v2 | Domínio, validação, JSON e esquema de saída do LLM |
| Banco | **SQLAlchemy** 2.0 (ORM tipado) | SQLite hoje, outro banco amanhã |
| Migrações | **Alembic** | Pasta `migrations/`; aplicadas na inicialização |
| LLM | **openai** (Responses API) e **anthropic** (SDKs oficiais); provedor escolhido pelo usuário, padrão OpenAI | Extração do folheto, interpretação do texto livre, busca web de cantos, classificação de refrão |
| HTTP | **httpx** | Baixar páginas de letras |
| HTML | **beautifulsoup4** (parser `lxml`) | Extrair letras do HTML |
| Busca aproximada | **rapidfuzz** | Achar cantos por título, apelido ou primeira linha |
| Caminhos | **platformdirs** | Pastas de dados e configuração por sistema operacional |
| Segredos | **keyring** | Chave de API no cofre do sistema |
| CLI | **typer** | Comandos `pallotti ...` |
| Testes | **pytest**, **pytest-qt**, **respx** | Unitários, interface, mock de HTTP |
| Qualidade | **ruff** (lint + format), **mypy** | Estilo e tipos |
| Distribuição | **PyInstaller** | Executável para Windows e Linux |

> **Licença:** o PySide6-Fluent-Widgets é **GPLv3** para uso não comercial. Um
> executável distribuído com ele fica sob GPLv3. Ver decisão D3 no PLANO.

## 2. Camadas e regras de dependência

```
            ┌──────────────────────────────┐   ┌───────────┐
            │ ui/  (PySide6 + qfluentwidgets) │   │  cli.py   │
            └───────────────┬────────────────┘   └─────┬─────┘
                            ▼                          ▼
            ┌───────────────────────────────────────────────┐
            │ application/   casos de uso (MassGenerator, ...) │
            └──┬──────────┬───────────┬──────────┬──────────┘
               ▼          ▼           ▼          ▼
         leaflet/     songs/   presentation/   db/
               └────┬─────┘           │          │
                    ▼                 │          │
                  llm/                │          │
                    └────────┬────────┴──────────┘
                             ▼
                         domain/   (pydantic puro, sem I/O)
```

Regras (verificadas por teste de importação em `tests/unit/test_layers.py`):

1. `domain/` não importa nada do projeto e não faz I/O.
2. Nenhum módulo fora de `ui/` importa `PySide6` ou `qfluentwidgets`.
3. `ui/` e `cli.py` só usam `application/` (e `domain/` para tipos). Não acessam
   `db/`, `llm/` ou `presentation/` diretamente.
4. Só `llm/` importa `anthropic` e `openai` (`llm/client.py` e `llm/openai_client.py`).
5. Só `db/` importa `sqlalchemy`.
6. Dependências externas (LLM, HTTP, conversor PDF, relógio) entram por
   **Protocol** no construtor, para que os testes usem versões falsas.

## 3. Estrutura de pastas

```
Gerador-pallotti-slide/
├── CLAUDE.md
├── pyproject.toml            # uv; scripts: pallotti (CLI), pallotti-gui
├── uv.lock
├── alembic.ini               # script_location = src/pallotti_slides/db/migrations
├── docs/                     # SPEC, ARQUITETURA, PLANO, NOMES, MODELO_PPTX, PROMPTS_IMAGENS
├── examples/                 # missa real de referência (pptx + pdf), não editar
├── scripts/                  # utilitários de desenvolvimento (ex.: generate_example_fixture.py)
├── src/pallotti_slides/
│   ├── __init__.py
│   ├── __main__.py           # python -m pallotti_slides → abre a GUI
│   ├── cli.py                # Typer
│   ├── config.py             # Settings, Paths, FontLocator
│   ├── domain/
│   │   ├── enums.py          # LiturgicalSeason, SongMoment, EucharisticPrayer, ...
│   │   ├── models.py         # Mass, Celebration, Liturgy, Song, Stanza, Line, ...
│   │   ├── rules.py          # default_has_gloria(), validate_mass(), output_file_name()
│   │   └── text.py           # normalize_search(), looks_like_url(), ...
│   ├── llm/
│   │   └── client.py         # LLMClient (Protocol), ClaudeClient, FakeLLMClient
│   ├── leaflet/
│   │   ├── schema.py         # LeafletData (saída estruturada)
│   │   ├── prompts.py        # textos de sistema/instrução
│   │   └── extractor.py      # LeafletExtractor
│   ├── songs/
│   │   ├── downloaders.py    # LyricsDownloader (Protocol), LetrasMusDownloader, CifraClubDownloader
│   │   ├── parser.py         # LyricsParser, ChorusDetector
│   │   ├── interpreter.py    # RequestInterpreter (texto livre → SongRequest[])
│   │   ├── web_search.py     # WebSongSearcher
│   │   └── resolver.py       # SongResolver
│   ├── presentation/
│   │   ├── template.py       # MassTemplate, TemplateSlide, SlideTag (etiquetas em português → campos/enums em inglês)
│   │   ├── measurer.py       # TextMeasurer, Box
│   │   ├── paginator.py      # SongPaginator, SongPage
│   │   ├── planner.py        # BuildPlanner → SlidePlan
│   │   ├── slides_xml.py     # duplicar/remover/reordenar slides (lxml)
│   │   ├── builder.py        # PptxBuilder (executa o plano)
│   │   ├── pdf.py            # PdfConverter (Protocol), LibreOfficeConverter, PowerPointConverter
│   │   └── preview.py        # pdf → PNGs (para CLI e QA)
│   ├── db/
│   │   ├── session.py        # make_engine(), session_factory(), apply_migrations()
│   │   ├── tables.py         # ORM: SongRow, SongAliasRow, MassRow, MassSongRow
│   │   ├── repositories.py   # SongRepository, MassRepository
│   │   └── migrations/       # Alembic: env.py, script.py.mako, versions/
│   ├── application/
│   │   ├── generate_mass.py  # MassGenerator
│   │   ├── prepare_mass.py   # MassPreparer (folheto + pedidos → rascunho de Mass)
│   │   └── container.py      # monta as dependências reais (injeção manual)
│   ├── ui/
│   │   ├── app.py            # QApplication, tema, janela
│   │   ├── main_window.py    # FluentWindow + navegação
│   │   ├── tasks.py          # Task (QRunnable) + sinais
│   │   ├── pages/
│   │   │   ├── home.py
│   │   │   ├── new_mass/     # page.py, step_data.py, step_liturgy.py, step_songs.py, step_review.py
│   │   │   ├── library.py
│   │   │   ├── history.py
│   │   │   ├── settings.py
│   │   │   └── about.py
│   │   └── components/       # song_editor.py, moment_card.py, slides_preview.py
│   └── resources/
│       ├── template/mass_template.pptx
│       └── images/           # pallotti_*.png, icone.ico/.png, splash
│                             # (sem fontes: a Aptos não pode ser redistribuída — ver §12)
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── masses/26tc_2026.json
    │   ├── leaflets/<nome>.pdf + <nome>.expected.json
    │   ├── html/letras_mus/*.html, html/cifra_club/*.html (+ *.expected.json)
    │   └── llm/              # respostas gravadas para o FakeLLMClient
    ├── unit/                 # subpastas = nomes dos pacotes (domain/, songs/, ...)
    ├── integration/
    └── ui/
```

Convenção de nomes: **todo identificador de código em inglês**, conforme o
glossário [NOMES.md](NOMES.md) (`Mass`, `Stanza`, `SongResolver`). Ficam em
português: a documentação, as mensagens ao usuário, o nome do arquivo gerado e
as etiquetas do modelo PowerPoint. Identificadores sem acento.

## 4. Domínio (`domain/`)

```python
# enums.py
class LiturgicalSeason(StrEnum): ADVENT, CHRISTMAS, LENT, PASCHAL_TRIDUUM, EASTER, ORDINARY_TIME
class SongMoment(StrEnum):
    MANTRA, ENTRANCE, PENITENTIAL_ACT, GLORIA, ACCLAMATION,
    OFFERTORY, COMMUNION, POST_COMMUNION, RECESSIONAL
    # ordem de declaração = ordem na missa; propriedade .label → "Canto de Entrada"
class EucharisticPrayer(StrEnum): I, II, III, IV, ...   # só as que existem no modelo
class StanzaType(StrEnum): VERSE, CHORUS
class SongSource(StrEnum): LETRAS_MUS, CIFRA_CLUB, MANUAL, OTHER

# models.py  (pydantic BaseModel, frozen onde fizer sentido)
class Line:      text: str; bold: bool = False
class Stanza:    id: int; type: StanzaType; lines: list[Line]
class Song:
    title: str; artist: str | None; source: SongSource; source_url: str | None
    stanzas: list[Stanza]; order: list[int]            # ids de Stanza
    def sequence(self) -> list[Stanza]: ...            # estrofes na ordem de execução
class Celebration:
    title: str              # já normalizado: "30° Domingo do Tempo Comum"
    short_title: str | None # editável; None = short_title_rule(title)
    date: date; season: LiturgicalSeason; year: Literal["A","B","C"] | None
class Liturgy:
    first_reading: str; psalm_number: str; psalm_refrain: str
    second_reading: str | None; gospel: str; intercessions_response: str
    eucharistic_prayer: EucharisticPrayer
    mystery_of_faith: str   # texto do folheto (varia com rito/OE); vazio = erro em validate_mass
class Mass:
    celebration: Celebration; liturgy: Liturgy; has_gloria: bool
    songs: dict[SongMoment, Song]                      # momento ausente = sem canto
class SongRequest: moment: SongMoment; text: str; kind: Literal["title","url","lyrics"]
class Notice:      level: Literal["info","warning","error"]; message: str; field: str | None

# rules.py (funções puras)
def default_has_gloria(season: LiturgicalSeason) -> bool   # False só em ADVENT e LENT
def validate_mass(mass: Mass) -> list[Notice]
def output_file_name(mass: Mass) -> str      # "Missa - 26° Dom do T.C - 26.09.2026 - OE III"
                                             # usa short_title ou short_title_rule(title); data = celebration.date
def short_title_rule(title: str) -> str      # "Domingo"→"Dom", "do Tempo Comum"→"do T.C", resto igual
def next_sunday(today: date) -> date         # data padrão da missa nova: hoje se for domingo, senão o próximo

# text.py (funções puras)
def normalize_title(text: str) -> str        # "30º DOMINGO DO TEMPO COMUM" → "30° Domingo do Tempo Comum"
                                             # iniciais maiúsculas, preposições/artigos minúsculos, º/ª ordinal → °
def normalize_search(text: str) -> str; def looks_like_url(text: str) -> bool
```

## 5. Modelo PowerPoint e montagem (`presentation/`)

Contrato completo em [MODELO_PPTX.md](MODELO_PPTX.md). Resumo: cada slide do
modelo tem, na **primeira linha das anotações**, uma etiqueta `@pallotti ...`
que diz se ele é fixo, de um grupo opcional, protótipo de canto ou parte de um
bloco de OE. Os textos variáveis são etiquetas `{{campo}}` dentro dos slides.

As etiquetas do modelo ficam **em português** (a equipe as edita no
PowerPoint); `presentation/template.py` mapeia essas etiquetas para os campos e
enums em inglês (por exemplo, `canto=entrada` → `SongMoment.ENTRANCE`,
`{{liturgia.primeira_leitura}}` → `Liturgy.first_reading`).

### Separação planejar × executar

```
Mass ──► SongPaginator (por canto) ──► BuildPlanner ──► SlidePlan ──► PptxBuilder ──► .pptx
               ▲                           ▲             (puro)         (XML)
          TextMeasurer                MassTemplate (etiquetas lidas do modelo)
```

- **`MassTemplate`**: `load(path) -> MassTemplate`; `slides: list[TemplateSlide]`;
  `validate() -> list[Notice]`; `available_prayers() -> list[EucharisticPrayer]`.
  `TemplateSlide(index, tag: SlideTag, fields: set[str], text_box: Box | None)`.
- **`TextMeasurer(regular_font: Path, bold_font: Path)`**:
  `height(lines: list[Line], size_pt: float, box: Box) -> float` (com
  quebra automática) e `fits(...) -> bool`. Usa `ImageFont.truetype(...).getlength`.
  Altura da linha e espaçamento entre parágrafos **calibrados** com o exemplo (ver
  teste de calibração na F9).
- **`SongPaginator(measurer, config: TypographyConfig)`**:
  `paginate(song: Song, box: Box) -> list[SongPage]`, com
  `SongPage(lines: list[Line], size_pt: int)`. Algoritmo:
  1. `sequence()` → uma página por estrofe;
  2. estrofe com mais de `max_lines` → divide em pedaços equilibrados;
  3. para `t` de `max_font` até `min_font`, passo 2: se todas as páginas cabem
     em `t`, usa `t` para o canto inteiro;
  4. se nenhuma cabe em `min_font`, divide as páginas que não cabem e volta ao
     passo 3.
- **`BuildPlanner.plan(template, mass, pages: dict[SongMoment, list[SongPage]]) -> SlidePlan`**:
  função pura. `SlidePlan` é uma lista ordenada de
  `TargetSlide(source: int, replacements: dict[str, TextContent])`. Slides do
  modelo que não aparecem no plano são removidos. Um protótipo de canto aparece N
  vezes (uma por página).
- **`PptxBuilder.build(template_path, plan, destination) -> Path`**:
  1. duplica/remove/reordena slides no XML (`slides_xml.py`: copia a parte do
     slide e as relações, atualiza `presentation.xml`, remove partes órfãs);
  2. substitui as etiquetas **no nível do run**, preservando `rPr`/`pPr`. Para o
     corpo do canto, recria os parágrafos copiando o `pPr` do protótipo, com
     `algn="ctr"`, `sz` do tamanho escolhido e `b="1"` nas linhas em negrito;
  3. limpa as anotações `@pallotti`.
  O python-pptx não duplica slides nem preserva formatação com
  `text_frame.text = ...`. Por isso a manipulação é feita no XML.
- **`PdfConverter`** (Protocol): `convert(pptx: Path, folder: Path) -> Path`.
  `LibreOfficeConverter` acha o `soffice` (PATH, `/usr/bin`,
  `C:\Program Files\LibreOffice\program`) e roda com perfil temporário
  (`-env:UserInstallation=file:///tmp/...`) para não travar se outra instância
  estiver aberta. `PowerPointConverter` (Windows, via `comtypes`) é opcional.

## 6. Cantos (`songs/`)

```
SongRequest ─► SongResolver
                 ├─ url?    ─► SongRepository.by_url ─► (não achou) LyricsDownloader ─► LyricsParser ─► salvar
                 ├─ lyrics? ─► LyricsParser ─► salvar (source=MANUAL)
                 └─ title?  ─► SongRepository.search (fuzzy)
                                 ├─ ≥ 90 ─► usa
                                 ├─ 70–89 ─► candidatos (usuário escolhe)
                                 └─ nada ─► WebSongSearcher ─► candidatos (URLs) ─► usuário escolhe ─► baixa/analisa/salva
```

- **`LyricsDownloader`** (Protocol): `supports(url) -> bool`; `download(url) -> RawLyrics(title, artist, text, source, url)`.
  - `LetrasMusDownloader`: extrai o bloco da letra (estrofes em `<p>`, linhas em `<br>`).
  - `CifraClubDownloader`: primeiro tenta a página equivalente no Letras.mus.br
    (mesmo `artista/musica`, mesma empresa). Se falhar, extrai do `<pre>` da cifra
    e remove acordes (tags de acorde e linhas só de acordes/tablatura).
  - Seletores CSS **confirmados com HTML salvo** em `tests/fixtures/html/`, nunca
    de memória. Cabeçalho `User-Agent` identificado, timeout de 15 s, sem
    paralelismo agressivo.
- **`LyricsParser(detector: ChorusDetector)`**: `parse(RawLyrics) -> Song`.
  Separa estrofes, normaliza espaços e expande marcadores "(Refrão)".
- **`ChorusDetector(llm: LLMClient | None)`**: marcações → repetição → LLM com
  estrofes numeradas (o LLM devolve **só os ids**) → indefinido (gera `Notice`).
- **`RequestInterpreter(llm)`**: `interpret(free_text) -> list[SongRequest]`
  (saída estruturada).
- **`WebSongSearcher(llm)`**: `search(title, artist=None) -> list[SongCandidate(title, artist, url)]`.
  Usa a ferramenta de busca web do servidor com `allowed_domains` restrito aos
  sites suportados. Os candidatos vêm dos blocos `web_search_result` (URL e
  título), não de texto livre do modelo.
- **`SongResolver(repo, downloaders, parser, searcher)`**:
  `resolve(request) -> ResolutionResult(song | None, origin, candidates, notices)`;
  `confirm(request, candidate) -> Song` (baixa, salva e registra o apelido).

## 7. Folheto (`leaflet/`)

- **`LeafletData`** (pydantic): todos os campos da Liturgy e da Celebration são
  **opcionais**, mais `notes: list[str]`. É o esquema da saída estruturada.
- **`LeafletExtractor(llm, cache_dir)`**: `extract(pdf: Path) -> LeafletData`.
  Envia o PDF como bloco `document` (base64) e chama
  `client.messages.parse(..., output_format=LeafletData)`. O cache é por SHA-256
  do PDF.
- O prompt de extração (`prompts.py`) proíbe inventar: campo ausente = `null`.
  Inclui exemplos de formato ("Ez 18,25-28", "24(25)", "26º Domingo do Tempo
  Comum").

## 8. LLM (`llm/client.py`)

```python
class LLMClient(Protocol):
    def extract_structured(
        self,
        *,
        instruction: str,
        schema: type[T],
        pdf: bytes | None = None,
        text: str | None = None,
    ) -> T: ...
    def search_urls(
        self, *, query: str, domains: list[str], max_results: int
    ) -> list[SearchResult]: ...
```

- **Provedores:** `OpenAIClient` (`llm/openai_client.py`, SDK `openai`, Responses API:
  `responses.parse` com saída estruturada, PDF como `input_file`, ferramenta
  `web_search` com filtro de domínios; modelo padrão `gpt-6-astra`, a confirmar na
  documentação da OpenAI ao implementar) e `ClaudeClient`. `create_llm_client(settings)`
  escolhe pelo `Settings.llm_provider` (`openai` padrão | `anthropic`). Chave por
  provedor no `keyring` (ou `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` em desenvolvimento).
- `ClaudeClient` implementa com o SDK `anthropic`:
  - modelo configurável, padrão `claude-opus-5-5`, com `output_config.effort`
    baixo/médio para extração;
  - `client.messages.parse(output_format=...)` para saída estruturada;
  - ferramenta de busca web do servidor `web_search_20260209` com
    `allowed_domains`;
  - tratamento de `stop_reason == "refusal"` e erros tipados (`RateLimitError`,
    `APIConnectionError`…) convertidos em `LLMError` com mensagem para o usuário;
  - chave vinda de `keyring` (ou `ANTHROPIC_API_KEY` em desenvolvimento).
- `FakeLLMClient` lê respostas gravadas em `tests/fixtures/llm/`. É usado em
  todos os testes padrão.
- Testes com a API real: marcador `@pytest.mark.live`, desligado por padrão
  (`pytest -m live` para rodar).

## 9. Banco de dados (`db/`)

SQLAlchemy 2.0 com `Mapped[...]`. Tipos portáveis: `JSON` (SQLite/Postgres) e
enums gravados como texto (`Enum(..., native_enum=False)`).

```
songs
  id                 INTEGER PK
  title              VARCHAR(200) NOT NULL
  title_search       VARCHAR(200) NOT NULL, INDEX       -- normalize_search(title)
  first_line_search  VARCHAR(300) NOT NULL, INDEX       -- normalize_search(1ª linha)
  artist             VARCHAR(200) NULL
  source             VARCHAR(20)  NOT NULL              -- SongSource
  source_url         VARCHAR(500) NULL, UNIQUE
  original_lyrics    TEXT NOT NULL                      -- texto como baixado/colado (auditoria)
  structure          JSON NOT NULL                      -- {"stanzas":[...], "order":[...]}
  usual_moments      JSON NOT NULL DEFAULT '[]'         -- ["entrance", ...] (sugestão)
  reviewed           BOOLEAN NOT NULL DEFAULT false     -- usuário conferiu a estrutura
  created_at, updated_at  DATETIME NOT NULL

song_aliases
  id            INTEGER PK
  song_id       FK → songs.id ON DELETE CASCADE
  alias_search  VARCHAR(200) NOT NULL, UNIQUE           -- "me chamaste"

masses
  id                 INTEGER PK
  date               DATE NOT NULL, INDEX
  title              VARCHAR(200) NOT NULL
  season             VARCHAR(20) NOT NULL
  eucharistic_prayer VARCHAR(10) NOT NULL
  data               JSON NOT NULL                      -- Mass.model_dump(mode="json")
  pptx_path          VARCHAR(500) NULL
  pdf_path           VARCHAR(500) NULL
  created_at         DATETIME NOT NULL

mass_songs
  mass_id   FK → masses.id ON DELETE CASCADE
  moment    VARCHAR(20) NOT NULL
  song_id   FK → songs.id ON DELETE SET NULL
  PK (mass_id, moment)
```

- **Busca** (`SongRepository.search(term, limit=5) -> list[Match(song_id, song, score)]`):
  normaliza o termo; correspondência exata em `title_search`, `alias_search` ou
  prefixo de `first_line_search` = 100. Senão, `rapidfuzz.process.extract`
  com `token_set_ratio` sobre títulos, apelidos e primeiras linhas carregados em
  memória. Mesmo com milhares de cantos isso é instantâneo, e funciona igual em
  qualquer banco.
- **Migrações**: Alembic em `src/pallotti_slides/db/migrations/` (vai junto
  no executável). `apply_migrations(engine)` roda `upgrade head` na
  inicialização. Toda mudança em `tables.py` exige uma nova revisão
  (`uv run alembic revision --autogenerate -m "..."`), revisada à mão.
  `uv run alembic check` precisa passar. Revisão inicial: `0001_initial_schema`.
- **URL do banco**: padrão `sqlite:///{user_data_dir}/pallotti.db`, que pode ser
  trocada por `PALLOTTI_DB_URL` (ex.: Postgres no futuro).
- `SongRepository.by_url(url) -> tuple[int, Song] | None`; `add_alias(song_id, alias)`
  (normaliza; `DuplicateError` se já existir). `Song` não tem id: os ids vêm
  junto (`Match.song_id`, tuplas).
- `MassRepository`: `save(mass, files: MassFiles | None) -> int`, `list(limit) -> list[MassSummary]`,
  `get(id) -> Mass`.

## 10. Casos de uso (`application/`)

- **`MassPreparer(extractor, interpreter, resolver, rules)`**:
  `prepare(date, leaflet: Path | None, requests: list[SongRequest], free_text: str | None) -> MassDraft`.
  `MassDraft` = Mass parcial + resultados de resolução por momento + avisos
  (`Notice`). Cada etapa é independente: falhar na extração não impede resolver
  os cantos.
- **`MassGenerator(template, paginator, planner, builder, converter, mass_repo)`**:
  `generate(mass, output_dir) -> GenerationResult(pptx, pdf | None, notices)`.
- **`container.py`**: `create_container(settings) -> Container`, que monta tudo com
  as implementações reais. Os testes montam com versões falsas.

## 11. Interface (`ui/`)

- `FluentWindow` (qfluentwidgets) com navegação lateral: **Início**, **Nova
  Missa**, **Biblioteca**, **Histórico**; no rodapé, **Configurações** e
  **Sobre**. Ícones de `FluentIcon`.
- **Nova Missa** em 4 etapas com indicador de progresso (`Pivot`/`SegmentedWidget`):
  1. *Dados*: data (`CalendarPicker`), folheto (arrastar e soltar), texto livre;
  2. *Liturgia*: formulário (`LineEdit`, `ComboBox`, `SwitchButton` para Glória);
  3. *Cantos*: um `CardWidget` por momento, com campo de entrada, estado
     (banco/internet/manual), candidatos e botão "editar letra"
     (`SongEditor`: estrofes, verso/refrão, negrito por linha, ordem com
     arrastar);
  4. *Revisão*: avisos (`InfoBar`), miniaturas (QtPdf) e "Gerar" (`PrimaryPushButton`).
- Operações longas (LLM, rede, LibreOffice) rodam em `QThreadPool` via
  `Task(QRunnable)`, com sinais `finished`, `failed` e `progress`. A
  interface nunca bloqueia; durante a operação aparece um `StateToolTip`.
- Tema: claro/escuro/sistema (`setTheme`), cor de destaque litúrgica
  configurável (padrão vinho `#7A1F2B`). Imagens de Pallotti no Início e no
  Sobre.

## 12. Configuração e caminhos (`config.py`)

- `Paths`: `data = user_data_dir("PallottiSlides")` (banco, cache),
  `config = user_config_dir(...)/config.json`, `logs = user_log_dir(...)`.
- `Settings` (pydantic, salvo em JSON): provedor de LLM (`openai` | `anthropic`) e
  modelo de cada provedor (as chaves ficam no `keyring`, nunca no JSON), pasta de saída, caminho
  do soffice, caminho do modelo pptx, `TypographyConfig(min_font=40,
  max_font=54, max_lines=6)`, tema.
- **Fontes** (`FontLocator` em `config.py`): a Aptos é da Microsoft e sua
  licença **não permite redistribuição**. Ela não vai para o git nem para o
  executável. Ordem de busca dos arquivos TTF (regular e negrito):
  1. caminho configurado pelo usuário (Configurações → Tipografia);
  2. variável `PALLOTTI_FONTS_DIR`; em desenvolvimento, aponte para
     `src/assets/fonts/`, que é ignorada pelo git;
  3. fontes do sistema: `fc-match -f '%{file}' Aptos` no Linux;
     `C:\Windows\Fonts` e `%LOCALAPPDATA%\Microsoft\Windows\Fonts` no Windows;
  4. fontes "na nuvem" do Microsoft 365 (`%LOCALAPPDATA%\Microsoft\FontCache\4\CloudFonts\Aptos\`,
     caminho a confirmar na máquina da paróquia).
  Se nada for encontrado: o medidor usa uma fonte substituta com 10% de folga,
  emite um `Notice` e `pallotti doctor` orienta a instalar a Aptos (download
  gratuito da Microsoft).
- Para o **PDF**, a Aptos precisa estar *instalada* (o LibreOffice não enxerga as
  fontes na nuvem do Office). No Windows com PowerPoint, o `PowerPointConverter`
  evita esse problema.

## 13. Erros, logs e avisos

- Exceções do projeto herdam de `PallottiError` (`LLMError`, `DownloadError`,
  `TemplateError`, `PdfConversionError`), sempre com uma mensagem amigável em
  português.
- Problema recuperável = `Notice` no resultado, não exceção.
- `logging` padrão, arquivo rotativo em `Paths.logs`. Nunca registrar a chave
  de API nem letras completas (só título e URL).

## 14. Testes

| Tipo | Onde | Rede? | Observação |
|---|---|---|---|
| Unitário | `tests/unit/` | não | Domínio, paginador, planejador, parser, repositórios (SQLite em arquivo temporário) |
| Integração | `tests/integration/` | não | Montagem real do pptx, migrações, CLI, resolver com fakes |
| Referência ("golden") | `tests/integration/test_example.py` | não | Fixture JSON → pptx comparado com `examples/` |
| PDF | marcador `soffice` | não | Pulado se o LibreOffice não estiver instalado |
| Interface | `tests/ui/` (pytest-qt) | não | Cada página abre; fluxo feliz com container falso |
| Ao vivo | marcador `live` | **sim** | LLM real e sites reais; manual, nunca no CI |

QA visual (agentes): `pallotti template preview` ou `pallotti generate` +
conversão para PNG. O agente **olha as imagens** procurando texto estourado
antes de dar um marco como concluído.
