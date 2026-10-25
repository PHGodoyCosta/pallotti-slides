# Glossário de nomes (português → inglês)

> **Contrato.** Decisão de 2026-10-24: tudo o que é código usa nomes em
> **inglês**: pacotes, módulos, arquivos, classes, funções, variáveis, tabelas,
> colunas, valores de enum gravados no banco/JSON, comandos do CLI, variáveis de
> ambiente, docstrings e comentários.
> Ficam em **português**: os documentos em `docs/`, as mensagens e textos para o
> usuário (interface, erros, `--help`), o nome do arquivo gerado
> (`Missa - … - OE III.pptx`) e as **etiquetas do modelo PowerPoint**
> (`@pallotti canto=entrada`, `{{liturgia.primeira_leitura}}`), que a equipe
> edita no PowerPoint. `presentation/template.py` faz o mapeamento
> etiqueta → campo.
>
> Agentes usam **exatamente** estes nomes. Nome novo que não está aqui: siga o
> mesmo estilo e, se for contrato (classe pública, tabela, comando), adicione
> aqui.

## Pacotes e módulos (`src/pallotti_slides/`)

| Antes | Agora |
|---|---|
| `dominio/` enums, modelos, regras, texto | `domain/` `enums.py`, `models.py`, `rules.py`, `text.py` |
| `llm/cliente.py` | `llm/client.py` |
| `folheto/` esquema, prompts, extrator | `leaflet/` `schema.py`, `prompts.py`, `extractor.py` |
| `cantos/` baixadores, analisador, interpretador, buscador_web, resolvedor | `songs/` `downloaders.py`, `parser.py`, `interpreter.py`, `web_search.py`, `resolver.py` |
| `apresentacao/` modelo, medidor, paginador, planejador, xml_slides, montador, pdf, previa | `presentation/` `template.py`, `measurer.py`, `paginator.py`, `planner.py`, `slides_xml.py`, `builder.py`, `pdf.py`, `preview.py` |
| `banco/` sessao, tabelas, repositorios, migrations | `db/` `session.py`, `tables.py`, `repositories.py`, `migrations/` |
| `aplicacao/` gerar_missa, preparar_missa, container | `application/` `generate_mass.py`, `prepare_mass.py`, `container.py` |
| `ui/` app, janela_principal, tarefas | `ui/` `app.py`, `main_window.py`, `tasks.py` |
| `ui/paginas/` inicio, nova_missa/(pagina, etapa_dados, etapa_liturgia, etapa_cantos, etapa_revisao), biblioteca, historico, configuracoes, sobre | `ui/pages/` `home.py`, `new_mass/`(`page.py`, `step_data.py`, `step_liturgy.py`, `step_songs.py`, `step_review.py`), `library.py`, `history.py`, `settings.py`, `about.py` |
| `ui/componentes/` editor_canto, cartao_momento, previa_slides | `ui/components/` `song_editor.py`, `moment_card.py`, `slides_preview.py` |
| `recursos/modelo/modelo_missa.pptx`, `recursos/imagens/` | `resources/template/mass_template.pptx`, `resources/images/` |
| `config.py`, `cli.py`, `__main__.py` | iguais |

## Domínio

| Antes | Agora (valores gravados entre parênteses) |
|---|---|
| `TempoLiturgico` ADVENTO, NATAL, QUARESMA, TRIDUO_PASCAL, PASCOA, COMUM | `LiturgicalSeason` ADVENT, CHRISTMAS, LENT, PASCHAL_TRIDUUM, EASTER, ORDINARY_TIME (`advent`, …, `ordinary_time`) |
| `MomentoCanto` MANTRA, ENTRADA, ATO_PENITENCIAL, GLORIA, ACLAMACAO, OFERTORIO, COMUNHAO, POS_COMUNHAO, SAIDA; `.rotulo` | `SongMoment` MANTRA, ENTRANCE, PENITENTIAL_ACT, GLORIA, ACCLAMATION, OFFERTORY, COMMUNION, POST_COMMUNION, RECESSIONAL (`mantra`, `entrance`, …); `.label` → "Canto de Entrada" (texto em português) |
| `OracaoEucaristica` I, II, III, IV | `EucharisticPrayer` I, II, III, IV |
| `TipoEstrofe` VERSO, REFRAO | `StanzaType` VERSE, CHORUS (`verse`, `chorus`) |
| `FonteCanto` LETRAS_MUS, CIFRA_CLUB, MANUAL, OUTRO | `SongSource` LETRAS_MUS, CIFRA_CLUB, MANUAL, OTHER (`letras_mus`, `cifra_club`, `manual`, `other`) |
| `Linha(texto, negrito)` | `Line(text, bold)` |
| `Estrofe(id, tipo, linhas)` | `Stanza(id, type, lines)` |
| `Canto(titulo, artista, fonte, fonte_url, estrofes, ordem)`, `sequencia()` | `Song(title, artist, source, source_url, stanzas, order)`, `sequence()` |
| `Celebracao(titulo, data, tempo, ano)` + título curto | `Celebration(title, short_title, date, season, year)` |
| `Liturgia(primeira_leitura, salmo_numero, salmo_refrao, segunda_leitura, evangelho, preces_refrao, oracao_eucaristica, misterio_fe)` | `Liturgy(first_reading, psalm_number, psalm_refrain, second_reading, gospel, intercessions_response, eucharistic_prayer, mystery_of_faith)` |
| `Missa(celebracao, liturgia, tem_gloria, cantos)` | `Mass(celebration, liturgy, has_gloria, songs)` |
| `PedidoCanto(momento, texto, tipo: titulo/url/letra)` | `SongRequest(moment, text, kind: title/url/lyrics)` |
| `Aviso(nivel: info/atencao/erro, mensagem, campo)` | `Notice(level: info/warning/error, message, field)` |
| `tem_gloria_padrao()`, `validar_missa()`, `nome_arquivo()`, regra do título curto, próximo domingo | `default_has_gloria()`, `validate_mass()`, `output_file_name()`, `short_title_rule()`, `next_sunday()` |
| `normalizar_busca()`, `parece_url()`, normalizar título | `normalize_search()`, `looks_like_url()`, `normalize_title()` |

## Apresentação

| Antes | Agora |
|---|---|
| `ModeloMissa` (`carregar`, `slides`, `validar`, `oes_disponiveis`) | `MassTemplate` (`load`, `slides`, `validate`, `available_prayers`) |
| `SlideModelo(indice, etiqueta, campos, caixa_texto)`, `EtiquetaSlide` | `TemplateSlide(index, tag, fields, text_box)`, `SlideTag` |
| `MedidorTexto` (`altura`, `cabe`), `Caixa` | `TextMeasurer` (`height`, `fits`), `Box` |
| `PaginadorCanto.paginar()`, `PaginaCanto(linhas, tamanho_pt)` | `SongPaginator.paginate()`, `SongPage(lines, size_pt)` |
| `PlanejadorMontagem.planejar()`, `PlanoSlides`, `SlideDestino(origem, substituicoes)`, `ConteudoTexto` | `BuildPlanner.plan()`, `SlidePlan`, `TargetSlide(source, replacements)`, `TextContent` |
| `MontadorPptx.montar(caminho_modelo, plano, destino)` | `PptxBuilder.build(template_path, plan, destination)` |
| `ConversorPdf.converter(pptx, pasta)`, `ConversorLibreOffice`, `ConversorPowerPoint` | `PdfConverter.convert(pptx, folder)`, `LibreOfficeConverter`, `PowerPointConverter` |

## Cantos, folheto e LLM

| Antes | Agora |
|---|---|
| `BaixadorLetra` (`suporta`, `baixar`), `LetraBruta(titulo, artista, texto, fonte, url)` | `LyricsDownloader` (`supports`, `download`), `RawLyrics(title, artist, text, source, url)` |
| `BaixadorLetrasMus`, `BaixadorCifraClub` | `LetrasMusDownloader`, `CifraClubDownloader` |
| `AnalisadorLetra.analisar()`, `DetectorRefrao` | `LyricsParser.parse() -> tuple[Song, list[Notice]]`, `ChorusDetector.detect()`, `ChorusIds` (resposta do LLM) |
| detecção do tipo de pedido; remoção de acordes | `detect_request_kind()` (`songs/parser.py`), `strip_chords()` (`songs/downloaders.py`) |
| `InterpretadorPedido.interpretar()` | `RequestInterpreter.interpret()` |
| `BuscadorWebCantos.buscar()`, `CandidatoCanto(titulo, artista, url)` | `WebSongSearcher.search()`, `SongCandidate(title, artist, url)` |
| `ResolvedorCantos` (`resolver`, `confirmar`), `ResultadoResolucao(canto, origem, candidatos, avisos)` | `SongResolver` (`resolve`, `confirm`), `ResolutionResult(song, origin, candidates, notices)` |
| `DadosFolheto(…, observacoes)`, `ExtratorFolheto.extrair()` | `LeafletData(…, notes)`, `LeafletExtractor.extract()` |
| `ClienteLLM` (`extrair_estruturado(instrucao, esquema, pdf, texto)`, `buscar_urls(consulta, dominios, maximo)`), `ResultadoBusca` | `LLMClient` (`extract_structured(instruction, schema, pdf, text)`, `search_urls(query, domains, max_results)`), `SearchResult` |
| `ClienteClaude`, `ClienteLLMFalso` | `ClaudeClient`, `FakeLLMClient` |
| cliente OpenAI; fábrica de cliente; provedor | `OpenAIClient` (`llm/openai_client.py`), `create_llm_client()`, `Settings.llm_provider` (`openai` \| `anthropic`) |

## Banco

| Antes | Agora |
|---|---|
| `criar_engine()`, `fabrica_sessao()`, `aplicar_migracoes()` | `make_engine()`, `session_factory()`, `apply_migrations()` |
| ORM `CantoTabela`, `ApelidoCantoTabela`, `MissaTabela`, `MissaCantoTabela` | `SongRow`, `SongAliasRow`, `MassRow`, `MassSongRow` |
| tabela `cantos`: titulo, titulo_busca, primeira_linha_busca, artista, fonte, fonte_url, letra_original, estrutura, momentos_habituais, revisado, criado_em, atualizado_em | `songs`: title, title_search, first_line_search, artist, source, source_url, original_lyrics, structure, usual_moments, reviewed, created_at, updated_at |
| `cantos_apelidos`: canto_id, apelido_busca | `song_aliases`: song_id, alias_search |
| `missas`: data, titulo, tempo, oracao_eucaristica, dados, arquivo_pptx, arquivo_pdf, criado_em | `masses`: date, title, season, eucharistic_prayer, data, pptx_path, pdf_path, created_at |
| `missas_cantos`: missa_id, momento, canto_id | `mass_songs`: mass_id, moment, song_id |
| `RepositorioCantos` (`por_url`, `buscar`, apelidos), `Correspondencia(canto, pontuacao)` | `SongRepository` (`add`, `get`, `by_url`, `update`, `delete`, `list_all`, `add_alias`, `aliases`, `search`), `Match(song_id, song, score)` |
| arquivos e resumo de missa salva; erros do repositório | `MassFiles(pptx, pdf)`, `MassSummary`; `DuplicateError`, `NotFoundError` (herdam de `PallottiError`) |
| `RepositorioMissas` (`salvar`, `listar`, `obter`) | `MassRepository` (`save`, `list`, `get`) |
| revisão `0001_esquema_inicial` | `0001_initial_schema` |

## Aplicação, interface, configuração e erros

| Antes | Agora |
|---|---|
| `PreparadorMissa.preparar()`, `RascunhoMissa` | `MassPreparer.prepare()`, `MassDraft` |
| `GeradorMissa.gerar(missa, pasta_saida)`, `ResultadoGeracao(pptx, pdf, avisos)` | `MassGenerator.generate(mass, output_dir)`, `GenerationResult(pptx, pdf, notices)` |
| `criar_container(config)` | `create_container(settings)` |
| `Tarefa` (sinais `concluida`, `falhou`, `progresso`), `EditorCanto` | `Task` (`finished`, `failed`, `progress`), `SongEditor` |
| `Caminhos(dados, config, logs)`, `Configuracoes`, `ConfigTipografia(fonte_min, fonte_max, max_linhas)`, `LocalizadorFonte` | `Paths(data, config, logs)`, `Settings`, `TypographyConfig(min_font, max_font, max_lines)`, `FontLocator` |
| `ErroPallotti`, `ErroLLM`, `ErroDownload`, `ErroModelo`, `ErroConversaoPdf` | `PallottiError`, `LLMError`, `DownloadError`, `TemplateError`, `PdfConversionError` |
| onde ficam os erros | `domain/errors.py` (`PallottiError`), `llm/errors.py` (`LLMError`), `leaflet/errors.py` (`LeafletError`), `db/repositories.py` (`DuplicateError`, `NotFoundError`), `presentation/errors.py` (`TemplateError`, `PdfConversionError`) |
| ferramentas do modelo para o CLI | `application/template_tools.py` (`TemplateTools`) |
| convenções de `presentation/` | `TemplateSlide.index` começa em 0; `Box` em EMU (`presentation/measurer.py`) |
| `PALLOTTI_FONTES_DIR`, `PALLOTTI_DB_URL` | `PALLOTTI_FONTS_DIR`, `PALLOTTI_DB_URL` |

## CLI

| Antes | Agora |
|---|---|
| `pallotti gerar --missa m.json --saida dir` | `pallotti generate --mass m.json --output dir` |
| `pallotti folheto extrair f.pdf` | `pallotti leaflet extract f.pdf` |
| `pallotti cantos resolver "…"`, `pallotti cantos importar --url …` | `pallotti songs resolve "…"`, `pallotti songs import --url …` |
| `pallotti modelo inspecionar`, `pallotti modelo previa --saida dir` | `pallotti template inspect`, `pallotti template preview --output dir` |
| `pallotti diagnostico` | `pallotti doctor` |

## Scripts e testes

| Antes | Agora |
|---|---|
| `scripts/gerar_fixture_exemplo.py`, `criar_modelo_a_partir_do_exemplo.py`, `salvar_html.py` | `scripts/generate_example_fixture.py`, `create_template_from_example.py`, `save_html.py` |
| `tests/integracao/` | `tests/integration/` |
| `tests/unit/test_camadas.py`, `tests/unit/dominio/` etc. | `tests/unit/test_layers.py`, `tests/unit/domain/` (subpastas = nomes dos pacotes) |
| `test_exemplo.py`, `test_fluxo.py`, `test_folheto_live.py`, `test_cantos_live.py`, `test_oes.py`, `test_modelo.py`, `test_resolvedor.py`, `test_interpretador.py` | `test_example.py`, `test_flow.py`, `test_leaflet_live.py`, `test_songs_live.py`, `test_eucharistic_prayers.py`, `test_template.py`, `test_resolver.py`, `test_interpreter.py` |
| `tests/fixtures/missas/26tc_2026.json`, `completa_9_cantos.json` | `tests/fixtures/masses/26tc_2026.json`, `full_9_songs.json` |
| `tests/fixtures/folhetos/`, `*.esperado.json` | `tests/fixtures/leaflets/`, `*.expected.json` |
