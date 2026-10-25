# Pallotti Slides — Plano de Implementação

> Ordem de construção, dependências e **critérios de parada** de cada marco.
> Marcos referenciam funcionalidades do [SPEC.md](SPEC.md) (F1…F15) e classes da
> [ARQUITETURA.md](ARQUITETURA.md).

## 1. Como executar com agentes

**Unidade de trabalho = um marco = uma sessão de agente = um commit na `main` local.**

1. O agente lê `CLAUDE.md`, a seção do marco aqui e as seções referenciadas do
   SPEC e da ARQUITETURA. Mais nada é necessário.
2. Trabalha no checkout principal ou, em paralelo, numa worktree destacada da
   `main` (sem novas branches).
3. Escreve primeiro os testes dos critérios de parada, depois o código.
4. Itera até **todos** os critérios de parada passarem (é aqui que o "loop"
   funciona: os critérios são comandos objetivos).
5. Devolve o resumo com a saída dos comandos de verificação. **Não commita**:
   o orquestrador revisa, atualiza a caixa do marco na tabela da §3 e faz o
   commit local (sem merge, sem push, sem coautoria do Claude; ver
   ORQUESTRACAO §2).
6. **Portões humanos** (🧑) exigem a sua aprovação antes de o marco ser dado
   como concluído.

### Prompt-padrão para iniciar um marco

```
Implemente o marco <MX> descrito em docs/PLANO.md.
Leia CLAUDE.md e as seções do SPEC/ARQUITETURA que o marco referencia.
Trabalhe no diretório indicado no briefing. Escreva os testes dos critérios de parada
primeiro. Só considere concluído quando todos os comandos de verificação
passarem; cole a saída deles no resumo final. Não faça commit. Se algo no plano
estiver ambíguo ou errado, pare e pergunte em vez de inventar.
```

### Paralelismo

Só depois que o **contrato** estiver fixo (M1: modelos de domínio). Antes disso,
agentes em paralelo inventam formatos incompatíveis. Use git worktrees destacadas (`--detach`), uma por
agente.

```
Onda 0 (sequencial):   M0 ─► M1
Onda 1 (paralelo):     M2 ─► M3        M4        M5        M6*
Onda 2 (paralelo):          M7 (precisa de M4, M5)   M8 (precisa de M3, M4)
Onda 3:                M9 (precisa de M7, M8)   M10 (precisa de M3)
Onda 4:                M11
                                       * M6 precisa dos folhetos de exemplo (D1)
```

## 2. Pré-requisitos do usuário (antes da Onda 1)

| # | O que | Para qual marco |
|---|---|---|
| P1 | 2 ou 3 **folhetos PDF reais** (de preferência um do Tempo Comum, um da Quaresma ou do Advento e um de solenidade). O PDF em `examples/` é a exportação dos slides, **não** o folheto. | M6 |
| P2 | Chave de API Anthropic para os testes `live` (`ANTHROPIC_API_KEY`). | M6, M7 |
| P3 | 5 a 10 URLs de cantos que a paróquia usa (Letras.mus.br e Cifra Club), incluindo os do exemplo. | M5 |
| P4 | Respostas às decisões pendentes da §5. | variados |
| P5 | Texto validado das OEs I, II e IV (Missal ou folheto). | M10 |

## 3. Marcos

| Marco | Nome | Onda | Depende de | Portão 🧑 | Estado |
|---|---|---|---|---|---|
| M0 | Fundação do repositório | 0 | — | — | ☐ |
| M1 | Domínio e fixture de referência | 0 | M0 | revisar modelos | ☐ |
| M2 | Modelo PPTX etiquetado | 1 | M1 | aprovar visual | ☐ |
| M3 | Motor de apresentação | 1 | M2 | aprovar PDF gerado | ☐ |
| M4 | Banco de dados | 1 | M1 | — | ☐ |
| M5 | Letras: baixar e analisar | 1 | M1 | — | ☐ |
| M6 | Extração do folheto | 1 | M1, P1 | conferir extração | ☐ |
| M7 | Resolução de cantos | 2 | M4, M5 | — | ☐ |
| M8 | Casos de uso + CLI | 2 | M3, M4 | — | ☐ |
| M9 | Interface gráfica | 3 | M7, M8 | aprovar fluxo | ☐ |
| M10 | Biblioteca de OEs | 3 | M3, P5 | aprovar textos | ☐ |
| M11 | Empacotamento | 4 | M9 | testar na máquina da paróquia | ☐ |

---

### M0 — Fundação do repositório

**Objetivo:** projeto limpo, sem Flet, com a estrutura da ARQUITETURA §3 e as
ferramentas funcionando.

**Tarefas**
- Remover o Flet: `src/main.py`, `tests/test_main.py`, `[tool.flet]`, as
  dependências `flet*`, `requirements.txt`, `build/`, `.flet/`.
- `pyproject.toml` com uv, Python 3.13, as dependências da ARQUITETURA §1,
  `[project.scripts]` `pallotti = "pallotti_slides.cli:app"` e
  `pallotti-gui = "pallotti_slides.ui.app:main"`, e configurações do ruff, mypy e
  pytest (marcadores `live`, `soffice`).
- Criar o pacote `src/pallotti_slides/` com os subpacotes vazios (`__init__.py`).
- Mover as imagens para `src/pallotti_slides/recursos/imagens/`. As fontes
  **não** vão junto: `src/assets/fonts/` fica onde está, ignorada pelo git (D5).
  `LocalizadorFonte` conforme a ARQUITETURA §12.
- `cli.py` com `pallotti --help` e `pallotti diagnostico` (versão, Python,
  soffice encontrado?, Aptos encontrada?).
- `tests/unit/test_camadas.py`: verifica as regras de importação da
  ARQUITETURA §2.
- Atualizar o `README.md` (como rodar, links para `docs/`) e o `.gitignore`.

**Critérios de parada**
```bash
uv sync
uv run ruff check . && uv run ruff format --check .
uv run mypy src
uv run pytest
uv run pallotti --help
uv run pallotti diagnostico
```

---

### M1 — Domínio e fixture de referência

**Objetivo:** fixar o contrato de dados (ARQUITETURA §4).

**Tarefas**
- `dominio/enums.py`, `modelos.py`, `regras.py` e `texto.py` conforme a
  ARQUITETURA §4.
- `scripts/gerar_fixture_exemplo.py`: lê o pptx do exemplo e produz
  `tests/fixtures/missas/26tc_2026.json` (cantos com estrofes, tipo e negrito
  vindos do próprio pptx). O resultado é revisado à mão e versionado.
- Testes: validação da fixture, ida e volta em JSON, `tem_gloria_padrao` por
  tempo, `validar_missa` (campos faltando), `nome_arquivo` igual ao do exemplo,
  `normalizar_busca`, `Canto.sequencia()`.

**Critérios de parada**
```bash
uv run pytest tests/unit/dominio -q
uv run mypy src/pallotti_slides/dominio --strict
```
🧑 Você revisa os modelos e a fixture JSON.

---

### M2 — Modelo PPTX etiquetado

**Objetivo:** `recursos/modelo/modelo_missa.pptx` seguindo o
[MODELO_PPTX.md](MODELO_PPTX.md).

**Tarefas**
- Script `scripts/criar_modelo_a_partir_do_exemplo.py` (pode ser descartável):
  parte do exemplo, mantém **um** protótipo por canto, coloca as etiquetas nas
  anotações e as etiquetas `{{...}}` nos textos, e cria os protótipos novos de
  comunhão, pós-comunhão e saída copiando o protótipo do ofertório.
- `apresentacao/modelo.py`: `ModeloMissa.carregar()`, `validar()`,
  `oes_disponiveis()`.
- `pallotti modelo inspecionar` e `pallotti modelo previa`.

**Critérios de parada**
```bash
uv run pallotti modelo inspecionar          # sai com código 0, sem erros
uv run pytest tests/unit/apresentacao/test_modelo.py -q
uv run pallotti modelo previa --saida /tmp/previa-modelo   # PNGs gerados
```
🧑 Você abre o modelo no PowerPoint e aprova: mesma aparência do exemplo,
etiquetas nos lugares certos, limites do bloco da OE corretos.

---

### M3 — Motor de apresentação

**Objetivo:** `Missa` → `.pptx` + `.pdf` (F8, F9, F11). É o marco de maior
risco técnico.

**Tarefas**
- `medidor.py`, `paginador.py`, `planejador.py`, `xml_slides.py`, `montador.py`,
  `pdf.py`, `previa.py` (ARQUITETURA §5).
- Teste de calibração do medidor com os slides de canto do exemplo.
- Teste de referência: fixture → pptx → comparação com o exemplo (sequência de
  slides e textos normalizados).
- Fixture extra `tests/fixtures/missas/completa_9_cantos.json` com os 9
  momentos, um canto longo (estrofe de 12 linhas), sem 2ª leitura e com
  `tem_gloria = falso`.

**Critérios de parada**
```bash
uv run pytest tests/unit/apresentacao tests/integracao/test_exemplo.py -q
uv run pytest -m soffice -q                 # gera PDF de verdade
uv run pallotti gerar --missa tests/fixtures/missas/completa_9_cantos.json --saida /tmp/saida
# validador OOXML sem erros no pptx gerado
```
- O agente converte o PDF gerado em PNG e **inspeciona todas as páginas**:
  nenhum texto fora da caixa, nenhuma etiqueta sobrando, ordem correta.

🧑 Você abre o pptx e o PDF gerados e aprova.

---

### M4 — Banco de dados

**Objetivo:** persistência de cantos e missas (ARQUITETURA §9).

**Tarefas**
- `banco/tabelas.py`, `sessao.py`, `repositorios.py`.
- Alembic: `alembic.ini` na raiz, `banco/migrations/env.py` usando o
  `metadata` de `tabelas.py`, revisão inicial `0001_esquema_inicial`.
- `aplicar_migracoes()` chamado pelo container.
- Busca aproximada com rapidfuzz (título, apelido, primeira linha).

**Critérios de parada**
```bash
uv run alembic upgrade head                 # em banco vazio
uv run alembic check                        # modelos == migrações
uv run alembic downgrade base && uv run alembic upgrade head
uv run pytest tests/unit/banco -q
```
Testes obrigatórios: CRUD de canto; URL única; apelido único; "me chamaste" →
canto com primeira linha "Me chamaste para caminhar…"; busca sem diferenciar
acentos e maiúsculas; salvar e reabrir uma `Missa` sem perda.

---

### M5 — Letras: baixar e analisar

**Objetivo:** URL ou texto → `Canto` (F6).

**Tarefas**
- Salvar o HTML real das URLs de P3 em `tests/fixtures/html/` (uma vez, com o
  script `scripts/salvar_html.py`). Escrever à mão o `*.esperado.json` de cada
  um.
- `baixadores.py`, `analisador.py` (com `DetectorRefrao` sem LLM; o caminho com
  LLM fica desligável).

**Critérios de parada**
```bash
uv run pytest tests/unit/cantos -q          # sem rede (respx bloqueia)
```
Testes obrigatórios: cada HTML → estrutura igual ao esperado; nenhum acorde nos
fixtures do Cifra Club; "(Refrão)" expandido na ordem; letra colada com estrofes
repetidas → refrão detectado.

---

### M6 — Extração do folheto

**Objetivo:** PDF → `DadosFolheto` (F2). **Bloqueado por P1.**

**Tarefas**
- `llm/cliente.py` (`ClienteClaude`, `ClienteLLMFalso`), `folheto/esquema.py`,
  `prompts.py`, `extrator.py`, com cache por hash.
- Para cada folheto: `*.esperado.json` escrito por você (ou pelo agente e
  conferido por você).
- Gravar as respostas reais em `tests/fixtures/llm/` para os testes offline.

**Critérios de parada**
```bash
uv run pytest tests/unit/folheto -q                    # offline, com LLM falso
uv run pytest -m live tests/integracao/test_folheto_live.py   # 100% dos campos-chave
uv run pallotti folheto extrair tests/fixtures/folhetos/<um>.pdf
```
🧑 Você confere a extração de pelo menos um folheto que **não** foi usado para
ajustar o prompt.

---

### M7 — Resolução de cantos

**Objetivo:** F4 (interpretação do texto livre) e F5.

**Tarefas**
- `interpretador.py`, `buscador_web.py`, `resolvedor.py`.
- `pallotti cantos resolver "<texto>"` e `pallotti cantos importar --url`.

**Critérios de parada**
```bash
uv run pytest tests/unit/cantos/test_resolvedor.py tests/unit/cantos/test_interpretador.py -q
uv run pytest -m live tests/integracao/test_cantos_live.py
```
Testes obrigatórios: banco antes da internet; segunda resolução sem rede
(baixador e buscador falsos não chamados); apelido gravado; falha de rede vira
`Aviso`; candidatos web só de domínios permitidos.

---

### M8 — Casos de uso + CLI

**Objetivo:** fluxo completo sem interface (F15).

**Tarefas**
- `aplicacao/preparar_missa.py`, `gerar_missa.py`, `container.py`.
- Completar o `cli.py` com todos os comandos da F15.
- Registro no histórico (`RepositorioMissas`) a cada geração.

**Critérios de parada**
```bash
uv run pytest tests/integracao/test_cli.py tests/integracao/test_fluxo.py -q
uv run pallotti gerar --missa tests/fixtures/missas/26tc_2026.json --saida /tmp/saida
```
Teste de ponta a ponta com fakes: folheto (LLM falso) + pedidos de canto
(baixador falso) → pptx + pdf + registro no banco.

---

### M9 — Interface gráfica

**Objetivo:** F1, F3, F7, F12, F13 e F14 em PySide6 + qfluentwidgets
(ARQUITETURA §11). Pode ser dividido entre agentes por página **depois** que
`janela_principal.py` e `tarefas.py` existirem.

**Sub-marcos:** M9a janela, navegação, tema, Início e Sobre · M9b Nova Missa
(4 etapas) · M9c Biblioteca · M9d Histórico e Configurações (com diagnóstico).

**Critérios de parada**
```bash
uv run pytest tests/ui -q                   # pytest-qt, container falso
uv run pallotti-gui                         # abre sem erros no console
```
- O agente tira capturas de tela de cada página (claro e escuro) e confere.

🧑 Você executa o roteiro manual: missa nova com folheto real → 3 cantos novos
e 2 do banco → editar um refrão → gerar → abrir o PDF. Depois duplica essa
missa no histórico.

---

### M10 — Biblioteca de Orações Eucarísticas

**Objetivo:** F10 além da OE III.

**Tarefas**
- Para cada OE (I, II, IV…): o agente monta o bloco no modelo, copiando a
  estrutura do bloco III (imagem + resposta), com as respostas tiradas da
  **fonte fornecida por você** (P5), nunca de memória.
- Atualizar a tabela de blocos no MODELO_PPTX.md.

**Critérios de parada**
```bash
uv run pallotti modelo inspecionar
uv run pytest tests/integracao/test_oes.py -q   # gera uma missa por OE
```
🧑 Você aprova o texto de cada bloco e registra a data na tabela.

---

### M11 — Empacotamento

**Objetivo:** executável para a máquina da paróquia.

**Tarefas**
- Spec do PyInstaller (inclui `recursos/`, `migrations/` e os plugins Qt;
  **exclui** qualquer arquivo de fonte proprietária, com verificação no build).
- Primeira execução: assistente de diagnóstico (chave de API, LibreOffice, fonte
  Aptos) com instruções de instalação.
- Ícone, splash e metadados com a identidade Pallotti.

**Critérios de parada**
- O build roda no sistema operacional alvo.
- 🧑 Numa máquina limpa: instalar, configurar e gerar a missa do domingo.

## 4. Definição de pronto (vale para todo marco)

- [ ] Critérios de parada do marco passando (saída no relatório e resumida na
      mensagem de commit).
- [ ] `uv run ruff check . && uv run mypy src && uv run pytest` verdes.
- [ ] Nenhum teste padrão acessa a rede.
- [ ] Docs atualizados se algum contrato mudou (ARQUITETURA, MODELO_PPTX).
- [ ] Portão humano aprovado, quando houver.

## 5. Decisões pendentes

Cada item tem um **padrão** adotado no plano. Se você não responder, o agente
segue o padrão.

| # | Decisão | Padrão adotado |
|---|---|---|
| D1 | Qual folheto a paróquia usa (CNBB "O Domingo", "Liturgia Diária" ou outro)? | **Decidido (2026-10-24):** "O Domingo" (semanário litúrgico-catequético). Exemplo: `examples/folheto_example.pdf` (30º Dom TC, 25/10/2026), **digitalizado, sem camada de texto**. Os cantos sugeridos no folheto só são usados se o usuário pedir expressamente (SPEC F2/F4). |
| D2 | O QFluentWidgets exige Qt, então o **Flet sai do projeto**. Confirma? | Sim: PySide6 + qfluentwidgets |
| D3 | Licença: o QFluentWidgets é GPLv3 e o repositório está em Apache-2.0. | Trocar o repositório para **GPLv3** (uso paroquial, sem fins comerciais) |
| D4 | Sistema operacional das máquinas da paróquia. | Windows + LibreOffice; PowerPoint opcional para o PDF |
| D5 | Fonte Aptos: a licença da Microsoft (gravada no próprio arquivo TTF) **proíbe redistribuir**, então ela não pode ir no executável nem no GitHub. | Usar a Aptos instalada na máquina (Office/Windows ou download gratuito da Microsoft); `src/assets/fonts/` só para desenvolvimento local, ignorada pelo git; diagnóstico orienta a instalação |
| D12 | Alternativa à D5: trocar a fonte do modelo por uma livre (OFL), que **pode** ir no executável, como Inter, Source Sans 3 ou Noto Sans. | Manter a Aptos (preserva o visual atual). Reavaliar no M11 se a instalação na paróquia der trabalho |
| D6 | Provedor e modelo de LLM. | Anthropic, `claude-opus-5-5`, configurável |
| D7 | Quais OEs a paróquia usa de fato. | MVP: III; M10: I, II e IV |
| D8 | Aclamação do mistério da fé: fixa ou varia? | **Decidido (2026-10-24):** varia conforme o rito e a OE; vem do folheto (texto extraído, não enum) ou é digitada. Sem texto padrão. |
| D9 | Advento/Quaresma: sem Glória. Muda mais alguma coisa (cor, imagem, aclamação)? | **Parcial (2026-10-24):** Quaresma sem Glória; há outros tempos sem Glória ou sem certos cantos, a definir no M1 com perguntas específicas. Cor: ignorar por ora. O título de cada domingo vem escrito no folheto. |
| D10 | Marcadores "(2x)" e "bis" nas letras: manter ou expandir? | Manter como escrito |
| D11 | Onde ficam as imagens separadoras dos novos cantos (comunhão, pós, saída)? | **Parcial (2026-10-24):** a imagem separadora é sempre a de Jesus. Detalhes de outros modelos de fim de missa: perguntas específicas no M2. |
| D13 | Direitos autorais de exemplos, letras e folhetos no repositório público. | **Decidido (2026-10-24):** já resolvido; repositório segue público e tudo é versionado. |
| D14 | Fluxo de git. | **Decidido (2026-10-24):** só commits locais feitos pelo orquestrador, mensagem descritiva, sem coautoria do Claude. Sem merge, sem push. |
| D15 | Horário do orçamento (ORQUESTRACAO §5). | **Decidido (2026-10-24):** horário local da máquina (UTC−4). |

## 6. Backlog (depois do MVP)

- Calendário litúrgico automático: data → título do domingo, tempo, ano A/B/C e
  sugestão das referências (via algoritmo da Páscoa + tabela do lecionário ou
  uma API de liturgia diária, sempre como sugestão revisável).
- Sugestão de cantos por tempo litúrgico, com base no histórico.
- Ritos especiais (Ramos, Tríduo, Natal).
- Exportar e importar a biblioteca de cantos (JSON) e banco compartilhado entre
  equipes.
- Pré-visualização ao vivo enquanto edita.
