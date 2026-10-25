# Pallotti Slides — Arquitetura

> O **como**. Complementa o [SPEC.md](SPEC.md) (o quê) e o [PLANO.md](PLANO.md)
> (a ordem). Nomes de classes e módulos aqui são o **contrato**: agentes podem
> criar funções auxiliares livremente, mas não devem renomear nem mover o que
> está listado sem atualizar este documento.

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
| LLM | **anthropic** (SDK oficial, 1.x) | Extração do folheto, interpretação do texto livre, busca web de cantos, classificação de refrão |
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
            │ aplicacao/   casos de uso (GeradorMissa, ...)  │
            └──┬──────────┬───────────┬──────────┬──────────┘
               ▼          ▼           ▼          ▼
         folheto/     cantos/   apresentacao/   banco/
               └────┬─────┘           │          │
                    ▼                 │          │
                  llm/                │          │
                    └────────┬────────┴──────────┘
                             ▼
                         dominio/   (pydantic puro, sem I/O)
```

Regras (verificadas por teste de importação em `tests/unit/test_camadas.py`):

1. `dominio/` não importa nada do projeto e não faz I/O.
2. Nenhum módulo fora de `ui/` importa `PySide6` ou `qfluentwidgets`.
3. `ui/` e `cli.py` só usam `aplicacao/` (e `dominio/` para tipos). Não acessam
   `banco/`, `llm/` ou `apresentacao/` diretamente.
4. Só `llm/cliente.py` importa `anthropic`.
5. Só `banco/` importa `sqlalchemy`.
6. Dependências externas (LLM, HTTP, conversor PDF, relógio) entram por
   **Protocol** no construtor, para que os testes usem versões falsas.

## 3. Estrutura de pastas

```
Gerador-pallotti-slide/
├── CLAUDE.md
├── pyproject.toml            # uv; scripts: pallotti (CLI), pallotti-gui
├── uv.lock
├── alembic.ini               # script_location = src/pallotti_slides/banco/migrations
├── docs/                     # SPEC, ARQUITETURA, PLANO, MODELO_PPTX, PROMPTS_IMAGENS
├── examples/                 # missa real de referência (pptx + pdf), não editar
├── scripts/                  # utilitários de desenvolvimento (ex.: gerar_fixture_exemplo.py)
├── src/pallotti_slides/
│   ├── __init__.py
│   ├── __main__.py           # python -m pallotti_slides → abre a GUI
│   ├── cli.py                # Typer
│   ├── config.py             # Configuracoes, Caminhos
│   ├── dominio/
│   │   ├── enums.py          # TempoLiturgico, MomentoCanto, OracaoEucaristica, ...
│   │   ├── modelos.py        # Missa, Celebracao, Liturgia, Canto, Estrofe, Linha, ...
│   │   ├── regras.py         # tem_gloria_padrao(), validar_missa(), nome_arquivo()
│   │   └── texto.py          # normalizar_busca(), parece_url(), ...
│   ├── llm/
│   │   └── cliente.py        # ClienteLLM (Protocol), ClienteClaude, ClienteLLMFalso
│   ├── folheto/
│   │   ├── esquema.py        # DadosFolheto (saída estruturada)
│   │   ├── prompts.py        # textos de sistema/instrução
│   │   └── extrator.py       # ExtratorFolheto
│   ├── cantos/
│   │   ├── baixadores.py     # BaixadorLetra (Protocol), BaixadorLetrasMus, BaixadorCifraClub
│   │   ├── analisador.py     # AnalisadorLetra, DetectorRefrao
│   │   ├── interpretador.py  # InterpretadorPedido (texto livre → PedidoCanto[])
│   │   ├── buscador_web.py   # BuscadorWebCantos
│   │   └── resolvedor.py     # ResolvedorCantos
│   ├── apresentacao/
│   │   ├── modelo.py         # ModeloMissa, SlideModelo, EtiquetaSlide
│   │   ├── medidor.py        # MedidorTexto, Caixa
│   │   ├── paginador.py      # PaginadorCanto, PaginaCanto
│   │   ├── planejador.py     # PlanejadorMontagem → PlanoSlides
│   │   ├── xml_slides.py     # duplicar/remover/reordenar slides (lxml)
│   │   ├── montador.py       # MontadorPptx (executa o plano)
│   │   ├── pdf.py            # ConversorPdf (Protocol), ConversorLibreOffice, ConversorPowerPoint
│   │   └── previa.py         # pdf → PNGs (para CLI e QA)
│   ├── banco/
│   │   ├── sessao.py         # criar_engine(), fabrica_sessao(), aplicar_migracoes()
│   │   ├── tabelas.py        # ORM: CantoTabela, ApelidoCantoTabela, MissaTabela, MissaCantoTabela
│   │   ├── repositorios.py   # RepositorioCantos, RepositorioMissas
│   │   └── migrations/       # Alembic: env.py, script.py.mako, versions/
│   ├── aplicacao/
│   │   ├── gerar_missa.py    # GeradorMissa
│   │   ├── preparar_missa.py # PreparadorMissa (folheto + pedidos → rascunho de Missa)
│   │   └── container.py      # monta as dependências reais (injeção manual)
│   ├── ui/
│   │   ├── app.py            # QApplication, tema, janela
│   │   ├── janela_principal.py   # FluentWindow + navegação
│   │   ├── tarefas.py        # Tarefa (QRunnable) + sinais
│   │   ├── paginas/
│   │   │   ├── inicio.py
│   │   │   ├── nova_missa/   # pagina.py, etapa_dados.py, etapa_liturgia.py, etapa_cantos.py, etapa_revisao.py
│   │   │   ├── biblioteca.py
│   │   │   ├── historico.py
│   │   │   ├── configuracoes.py
│   │   │   └── sobre.py
│   │   └── componentes/      # editor_canto.py, cartao_momento.py, previa_slides.py
│   └── recursos/
│       ├── modelo/modelo_missa.pptx
│       └── imagens/          # pallotti_*.png, icone.ico/.png, splash
│                             # (sem fontes: a Aptos não pode ser redistribuída — ver §12)
└── tests/
    ├── conftest.py
    ├── fixtures/
    │   ├── missas/26tc_2026.json
    │   ├── folhetos/<nome>.pdf + <nome>.esperado.json
    │   ├── html/letras_mus/*.html, html/cifra_club/*.html (+ *.esperado.json)
    │   └── llm/              # respostas gravadas para o ClienteLLMFalso
    ├── unit/
    ├── integracao/
    └── ui/
```

Convenção de nomes: **domínio e serviços em português** (`Missa`, `Estrofe`,
`ResolvedorCantos`). Termos técnicos consagrados ficam como estão (`Protocol`,
`migrations`, `engine`). Identificadores sem acento.

## 4. Domínio (`dominio/`)

```python
# enums.py
class TempoLiturgico(StrEnum): ADVENTO, NATAL, QUARESMA, TRIDUO_PASCAL, PASCOA, COMUM
class MomentoCanto(StrEnum):
    MANTRA, ENTRADA, ATO_PENITENCIAL, GLORIA, ACLAMACAO,
    OFERTORIO, COMUNHAO, POS_COMUNHAO, SAIDA
    # ordem de declaração = ordem na missa; propriedade .rotulo → "Canto de Entrada"
class OracaoEucaristica(StrEnum): I, II, III, IV, ...   # só as que existem no modelo
class TipoEstrofe(StrEnum): VERSO, REFRAO
class FonteCanto(StrEnum): LETRAS_MUS, CIFRA_CLUB, MANUAL, OUTRO

# modelos.py  (pydantic BaseModel, frozen onde fizer sentido)
class Linha:      texto: str; negrito: bool = False
class Estrofe:    id: int; tipo: TipoEstrofe; linhas: list[Linha]
class Canto:
    titulo: str; artista: str | None; fonte: FonteCanto; fonte_url: str | None
    estrofes: list[Estrofe]; ordem: list[int]          # ids de Estrofe
    def sequencia(self) -> list[Estrofe]: ...          # estrofes na ordem de execução
class Celebracao: titulo: str; data: date; tempo: TempoLiturgico; ano: Literal["A","B","C"] | None
class Liturgia:
    primeira_leitura: str; salmo_numero: str; salmo_refrao: str
    segunda_leitura: str | None; evangelho: str; preces_refrao: str
    oracao_eucaristica: OracaoEucaristica
    misterio_fe: str        # texto do folheto (varia com rito/OE); vazio = erro em validar_missa
class Missa:
    celebracao: Celebracao; liturgia: Liturgia; tem_gloria: bool
    cantos: dict[MomentoCanto, Canto]                  # momento ausente = sem canto
class PedidoCanto: momento: MomentoCanto; texto: str; tipo: Literal["titulo","url","letra"]
class Aviso:      nivel: Literal["info","atencao","erro"]; mensagem: str; campo: str | None

# regras.py (funções puras)
def tem_gloria_padrao(tempo: TempoLiturgico) -> bool
def validar_missa(missa: Missa) -> list[Aviso]
def nome_arquivo(missa: Missa) -> str        # "Missa - 26° Dom do T.C - 26.09.2026 - OE III"
```

## 5. Modelo PowerPoint e montagem (`apresentacao/`)

Contrato completo em [MODELO_PPTX.md](MODELO_PPTX.md). Resumo: cada slide do
modelo tem, na **primeira linha das anotações**, uma etiqueta `@pallotti ...`
que diz se ele é fixo, de um grupo opcional, protótipo de canto ou parte de um
bloco de OE. Os textos variáveis são etiquetas `{{campo}}` dentro dos slides.

### Separação planejar × executar

```
Missa ──► PaginadorCanto (por canto) ──► PlanejadorMontagem ──► PlanoSlides ──► MontadorPptx ──► .pptx
               ▲                              ▲                    (puro)         (XML)
          MedidorTexto                   ModeloMissa (etiquetas lidas do modelo)
```

- **`ModeloMissa`**: `carregar(caminho) -> ModeloMissa`; `slides: list[SlideModelo]`;
  `validar() -> list[Aviso]`; `oes_disponiveis() -> list[OracaoEucaristica]`.
  `SlideModelo(indice, etiqueta: EtiquetaSlide, campos: set[str], caixa_texto: Caixa | None)`.
- **`MedidorTexto(fonte_regular: Path, fonte_negrito: Path)`**:
  `altura(linhas: list[Linha], tamanho_pt: float, caixa: Caixa) -> float` (com
  quebra automática) e `cabe(...) -> bool`. Usa `ImageFont.truetype(...).getlength`.
  Altura da linha e espaçamento entre parágrafos **calibrados** com o exemplo (ver
  teste de calibração na F9).
- **`PaginadorCanto(medidor, config: ConfigTipografia)`**:
  `paginar(canto: Canto, caixa: Caixa) -> list[PaginaCanto]`, com
  `PaginaCanto(linhas: list[Linha], tamanho_pt: int)`. Algoritmo:
  1. `sequencia()` → uma página por estrofe;
  2. estrofe com mais de `max_linhas` → divide em pedaços equilibrados;
  3. para `t` de `fonte_max` até `fonte_min`, passo 2: se todas as páginas cabem
     em `t`, usa `t` para o canto inteiro;
  4. se nenhuma cabe em `fonte_min`, divide as páginas que não cabem e volta ao
     passo 3.
- **`PlanejadorMontagem.planejar(modelo, missa, paginas: dict[MomentoCanto, list[PaginaCanto]]) -> PlanoSlides`**:
  função pura. `PlanoSlides` é uma lista ordenada de
  `SlideDestino(origem: int, substituicoes: dict[str, ConteudoTexto])`. Slides do
  modelo que não aparecem no plano são removidos. Um protótipo de canto aparece N
  vezes (uma por página).
- **`MontadorPptx.montar(caminho_modelo, plano, destino) -> Path`**:
  1. duplica/remove/reordena slides no XML (`xml_slides.py`: copia a parte do
     slide e as relações, atualiza `presentation.xml`, remove partes órfãs);
  2. substitui as etiquetas **no nível do run**, preservando `rPr`/`pPr`. Para o
     corpo do canto, recria os parágrafos copiando o `pPr` do protótipo, com
     `algn="ctr"`, `sz` do tamanho escolhido e `b="1"` nas linhas em negrito;
  3. limpa as anotações `@pallotti`.
  O python-pptx não duplica slides nem preserva formatação com
  `text_frame.text = ...`. Por isso a manipulação é feita no XML.
- **`ConversorPdf`** (Protocol): `converter(pptx: Path, pasta: Path) -> Path`.
  `ConversorLibreOffice` acha o `soffice` (PATH, `/usr/bin`,
  `C:\Program Files\LibreOffice\program`) e roda com perfil temporário
  (`-env:UserInstallation=file:///tmp/...`) para não travar se outra instância
  estiver aberta. `ConversorPowerPoint` (Windows, via `comtypes`) é opcional.

## 6. Cantos (`cantos/`)

```
PedidoCanto ─► ResolvedorCantos
                 ├─ url?    ─► RepositorioCantos.por_url ─► (não achou) BaixadorLetra ─► AnalisadorLetra ─► salvar
                 ├─ letra?  ─► AnalisadorLetra ─► salvar (fonte=MANUAL)
                 └─ titulo? ─► RepositorioCantos.buscar (fuzzy)
                                 ├─ ≥ 90 ─► usa
                                 ├─ 70–89 ─► candidatos (usuário escolhe)
                                 └─ nada ─► BuscadorWebCantos ─► candidatos (URLs) ─► usuário escolhe ─► baixa/analisa/salva
```

- **`BaixadorLetra`** (Protocol): `suporta(url) -> bool`; `baixar(url) -> LetraBruta(titulo, artista, texto, fonte, url)`.
  - `BaixadorLetrasMus`: extrai o bloco da letra (estrofes em `<p>`, linhas em `<br>`).
  - `BaixadorCifraClub`: primeiro tenta a página equivalente no Letras.mus.br
    (mesmo `artista/musica`, mesma empresa). Se falhar, extrai do `<pre>` da cifra
    e remove acordes (tags de acorde e linhas só de acordes/tablatura).
  - Seletores CSS **confirmados com HTML salvo** em `tests/fixtures/html/`, nunca
    de memória. Cabeçalho `User-Agent` identificado, timeout de 15 s, sem
    paralelismo agressivo.
- **`AnalisadorLetra(detector: DetectorRefrao)`**: `analisar(LetraBruta) -> Canto`.
  Separa estrofes, normaliza espaços e expande marcadores "(Refrão)".
- **`DetectorRefrao(llm: ClienteLLM | None)`**: marcações → repetição → LLM com
  estrofes numeradas (o LLM devolve **só os ids**) → indefinido (gera `Aviso`).
- **`InterpretadorPedido(llm)`**: `interpretar(texto_livre) -> list[PedidoCanto]`
  (saída estruturada).
- **`BuscadorWebCantos(llm)`**: `buscar(titulo, artista=None) -> list[CandidatoCanto(titulo, artista, url)]`.
  Usa a ferramenta de busca web do servidor com `allowed_domains` restrito aos
  sites suportados. Os candidatos vêm dos blocos `web_search_result` (URL e
  título), não de texto livre do modelo.
- **`ResolvedorCantos(repo, baixadores, analisador, buscador)`**:
  `resolver(pedido) -> ResultadoResolucao(canto | None, origem, candidatos, avisos)`;
  `confirmar(pedido, candidato) -> Canto` (baixa, salva e registra o apelido).

## 7. Folheto (`folheto/`)

- **`DadosFolheto`** (pydantic): todos os campos da Liturgia e da Celebração são
  **opcionais**, mais `observacoes: list[str]`. É o esquema da saída estruturada.
- **`ExtratorFolheto(llm, cache_dir)`**: `extrair(pdf: Path) -> DadosFolheto`.
  Envia o PDF como bloco `document` (base64) e chama
  `client.messages.parse(..., output_format=DadosFolheto)`. O cache é por SHA-256
  do PDF.
- O prompt de extração (`prompts.py`) proíbe inventar: campo ausente = `null`.
  Inclui exemplos de formato ("Ez 18,25-28", "24(25)", "26º Domingo do Tempo
  Comum").

## 8. LLM (`llm/cliente.py`)

```python
class ClienteLLM(Protocol):
    def extrair_estruturado(self, *, instrucao: str, esquema: type[T],
                            pdf: bytes | None = None, texto: str | None = None) -> T: ...
    def buscar_urls(self, *, consulta: str, dominios: list[str], maximo: int) -> list[ResultadoBusca]: ...
```

- `ClienteClaude` implementa com o SDK `anthropic`:
  - modelo configurável, padrão `claude-opus-5-5`, com `output_config.effort`
    baixo/médio para extração;
  - `client.messages.parse(output_format=...)` para saída estruturada;
  - ferramenta de busca web do servidor `web_search_20260209` com
    `allowed_domains`;
  - tratamento de `stop_reason == "refusal"` e erros tipados (`RateLimitError`,
    `APIConnectionError`…) convertidos em `ErroLLM` com mensagem para o usuário;
  - chave vinda de `keyring` (ou `ANTHROPIC_API_KEY` em desenvolvimento).
- `ClienteLLMFalso` lê respostas gravadas em `tests/fixtures/llm/`. É usado em
  todos os testes padrão.
- Testes com a API real: marcador `@pytest.mark.live`, desligado por padrão
  (`pytest -m live` para rodar).

## 9. Banco de dados (`banco/`)

SQLAlchemy 2.0 com `Mapped[...]`. Tipos portáveis: `JSON` (SQLite/Postgres) e
enums gravados como texto (`Enum(..., native_enum=False)`).

```
cantos
  id                 INTEGER PK
  titulo             VARCHAR(200) NOT NULL
  titulo_busca       VARCHAR(200) NOT NULL, INDEX       -- normalizar_busca(titulo)
  primeira_linha_busca VARCHAR(300) NOT NULL, INDEX     -- normalizar_busca(1ª linha)
  artista            VARCHAR(200) NULL
  fonte              VARCHAR(20)  NOT NULL               -- FonteCanto
  fonte_url          VARCHAR(500) NULL, UNIQUE
  letra_original     TEXT NOT NULL                       -- texto como baixado/colado (auditoria)
  estrutura          JSON NOT NULL                       -- {"estrofes":[...], "ordem":[...]}
  momentos_habituais JSON NOT NULL DEFAULT '[]'          -- ["entrada", ...] (sugestão)
  revisado           BOOLEAN NOT NULL DEFAULT false      -- usuário conferiu a estrutura
  criado_em, atualizado_em  DATETIME NOT NULL

cantos_apelidos
  id         INTEGER PK
  canto_id   FK → cantos.id ON DELETE CASCADE
  apelido_busca VARCHAR(200) NOT NULL, UNIQUE            -- "me chamaste"

missas
  id                 INTEGER PK
  data               DATE NOT NULL, INDEX
  titulo             VARCHAR(200) NOT NULL
  tempo              VARCHAR(20) NOT NULL
  oracao_eucaristica VARCHAR(10) NOT NULL
  dados              JSON NOT NULL                       -- Missa.model_dump(mode="json")
  arquivo_pptx       VARCHAR(500) NULL
  arquivo_pdf        VARCHAR(500) NULL
  criado_em          DATETIME NOT NULL

missas_cantos
  missa_id  FK → missas.id ON DELETE CASCADE
  momento   VARCHAR(20) NOT NULL
  canto_id  FK → cantos.id ON DELETE SET NULL
  PK (missa_id, momento)
```

- **Busca** (`RepositorioCantos.buscar(termo, limite=5) -> list[Correspondencia(canto, pontuacao)]`):
  normaliza o termo; correspondência exata em `titulo_busca`, `apelido_busca` ou
  prefixo de `primeira_linha_busca` = 100. Senão, `rapidfuzz.process.extract`
  com `token_set_ratio` sobre títulos, apelidos e primeiras linhas carregados em
  memória. Mesmo com milhares de cantos isso é instantâneo, e funciona igual em
  qualquer banco.
- **Migrações**: Alembic em `src/pallotti_slides/banco/migrations/` (vai junto
  no executável). `aplicar_migracoes(engine)` roda `upgrade head` na
  inicialização. Toda mudança em `tabelas.py` exige uma nova revisão
  (`uv run alembic revision --autogenerate -m "..."`), revisada à mão.
  `uv run alembic check` precisa passar.
- **URL do banco**: padrão `sqlite:///{user_data_dir}/pallotti.db`, que pode ser
  trocada por `PALLOTTI_DB_URL` (ex.: Postgres no futuro).
- `RepositorioMissas`: `salvar(missa, arquivos) -> int`, `listar(limite)`,
  `obter(id) -> Missa`.

## 10. Casos de uso (`aplicacao/`)

- **`PreparadorMissa(extrator, interpretador, resolvedor, regras)`**:
  `preparar(data, folheto: Path | None, pedidos: list[PedidoCanto], texto_livre: str | None) -> RascunhoMissa`.
  `RascunhoMissa` = Missa parcial + resultados de resolução por momento + avisos.
  Cada etapa é independente: falhar na extração não impede resolver os cantos.
- **`GeradorMissa(modelo, paginador, planejador, montador, conversor, repo_missas)`**:
  `gerar(missa, pasta_saida) -> ResultadoGeracao(pptx, pdf | None, avisos)`.
- **`container.py`**: `criar_container(config) -> Container`, que monta tudo com
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
     (`EditorCanto`: estrofes, verso/refrão, negrito por linha, ordem com
     arrastar);
  4. *Revisão*: avisos (`InfoBar`), miniaturas (QtPdf) e "Gerar" (`PrimaryPushButton`).
- Operações longas (LLM, rede, LibreOffice) rodam em `QThreadPool` via
  `Tarefa(QRunnable)`, com sinais `concluida`, `falhou` e `progresso`. A
  interface nunca bloqueia; durante a operação aparece um `StateToolTip`.
- Tema: claro/escuro/sistema (`setTheme`), cor de destaque litúrgica
  configurável (padrão vinho `#7A1F2B`). Imagens de Pallotti no Início e no
  Sobre.

## 12. Configuração e caminhos (`config.py`)

- `Caminhos`: `dados = user_data_dir("PallottiSlides")` (banco, cache),
  `config = user_config_dir(...)/config.json`, `logs = user_log_dir(...)`.
- `Configuracoes` (pydantic, salvo em JSON): modelo LLM, pasta de saída, caminho
  do soffice, caminho do modelo pptx, `ConfigTipografia(fonte_min=40,
  fonte_max=54, max_linhas=6)`, tema.
- **Fontes** (`LocalizadorFonte` em `config.py`): a Aptos é da Microsoft e sua
  licença **não permite redistribuição**. Ela não vai para o git nem para o
  executável. Ordem de busca dos arquivos TTF (regular e negrito):
  1. caminho configurado pelo usuário (Configurações → Tipografia);
  2. variável `PALLOTTI_FONTES_DIR`; em desenvolvimento, aponte para
     `src/assets/fonts/`, que é ignorada pelo git;
  3. fontes do sistema: `fc-match -f '%{file}' Aptos` no Linux;
     `C:\Windows\Fonts` e `%LOCALAPPDATA%\Microsoft\Windows\Fonts` no Windows;
  4. fontes "na nuvem" do Microsoft 365 (`%LOCALAPPDATA%\Microsoft\FontCache\4\CloudFonts\Aptos\`,
     caminho a confirmar na máquina da paróquia).
  Se nada for encontrado: o medidor usa uma fonte substituta com 10% de folga,
  emite um `Aviso` e o diagnóstico orienta a instalar a Aptos (download gratuito
  da Microsoft).
- Para o **PDF**, a Aptos precisa estar *instalada* (o LibreOffice não enxerga as
  fontes na nuvem do Office). No Windows com PowerPoint, o `ConversorPowerPoint`
  evita esse problema.

## 13. Erros, logs e avisos

- Exceções do projeto herdam de `ErroPallotti` (`ErroLLM`, `ErroDownload`,
  `ErroModelo`, `ErroConversaoPdf`), sempre com uma mensagem amigável em
  português.
- Problema recuperável = `Aviso` no resultado, não exceção.
- `logging` padrão, arquivo rotativo em `Caminhos.logs`. Nunca registrar a chave
  de API nem letras completas (só título e URL).

## 14. Testes

| Tipo | Onde | Rede? | Observação |
|---|---|---|---|
| Unitário | `tests/unit/` | não | Domínio, paginador, planejador, analisador, repositórios (SQLite em arquivo temporário) |
| Integração | `tests/integracao/` | não | Montagem real do pptx, migrações, CLI, resolvedor com fakes |
| Referência ("golden") | `tests/integracao/test_exemplo.py` | não | Fixture JSON → pptx comparado com `examples/` |
| PDF | marcador `soffice` | não | Pulado se o LibreOffice não estiver instalado |
| Interface | `tests/ui/` (pytest-qt) | não | Cada página abre; fluxo feliz com container falso |
| Ao vivo | marcador `live` | **sim** | LLM real e sites reais; manual, nunca no CI |

QA visual (agentes): `pallotti modelo previa` ou `pallotti gerar` + conversão
para PNG. O agente **olha as imagens** procurando texto estourado antes de dar
um marco como concluído.
