# Pallotti Slides

Programa desktop (PySide6 + QFluentWidgets) que gera os slides da missa de
domingo da Paróquia São Cristóvão: lê o folheto litúrgico (PDF) e os cantos,
preenche um modelo PowerPoint fixo e exporta `.pptx` + `.pdf`. Tema visual: São
Vicente Pallotti.

## Documentos (leia antes de codar)

- `docs/SPEC.md`: funcionalidades F1–F15 e critérios de aceite.
- `docs/ARQUITETURA.md`: stack, camadas, pastas, classes (contrato), banco, LLM.
- `docs/PLANO.md`: marcos M0–M11, ordem, critérios de parada, decisões pendentes.
- `docs/MODELO_PPTX.md`: etiquetas do modelo PowerPoint.
- `docs/ORQUESTRACAO.md`: papéis (orquestrador/subagentes), orçamento, Telegram.
- `docs/PROGRESSO.md`: estado atual dos marcos (criado na Fase 0).
- `examples/`: missa real de referência (26/09/2026, OE III). **Somente leitura.**

Ao trabalhar num marco, leia a seção dele no PLANO e só as seções do SPEC e da
ARQUITETURA que ele referencia.

## Comandos

```bash
uv sync                                  # instalar
uv run pallotti-gui                      # abrir o app
uv run pallotti --help                   # CLI (gerar, folheto, cantos, modelo, diagnostico)
uv run pytest                            # testes padrão (offline)
uv run pytest -m soffice                 # testes que precisam do LibreOffice
uv run pytest -m live                    # testes com rede/LLM real (manual)
uv run ruff check . && uv run ruff format .
uv run mypy src
uv run alembic revision --autogenerate -m "descricao"   # após mudar banco/tabelas.py
uv run alembic check
uv run pallotti modelo inspecionar       # após editar o modelo .pptx
```

## Regras invioláveis

1. **O LLM nunca escreve letra de música nem texto litúrgico.** Ele extrai do
   PDF, devolve URLs e classifica estrofes por **id**. Letras vêm de sites ou do
   usuário; orações vêm do modelo validado. Não preencha respostas de Oração
   Eucarística de memória.
2. **Nada novo nos slides.** Só manter, remover, duplicar e reordenar slides do
   modelo e trocar etiquetas `{{...}}`. Nenhuma forma, imagem ou estilo criado
   por código.
3. **Camadas** (ARQUITETURA §2): `dominio/` é puro; só `ui/` importa
   Qt/qfluentwidgets; só `llm/cliente.py` importa `anthropic`; só `banco/`
   importa `sqlalchemy`. `tests/unit/test_camadas.py` verifica isso.
4. **Testes padrão não acessam a rede.** LLM e HTTP entram por `Protocol` e são
   trocados por versões falsas. Rede só sob `@pytest.mark.live`.
5. **Banco:** toda mudança em `banco/tabelas.py` vem com uma revisão Alembic
   revisada à mão, e `alembic check` passa.
6. **Não altere `examples/`** nem as fixtures `*.esperado.json` para fazer um
   teste passar. Se o esperado estiver errado, pare e pergunte.
7. **Nunca commite nem empacote a fonte Aptos** (licença Microsoft, sem
   redistribuição). Em desenvolvimento use `PALLOTTI_FONTES_DIR=src/assets/fonts`
   (pasta ignorada pelo git). No app, ela é localizada no sistema
   (ARQUITETURA §12).
8. **Git:** subagentes não commitam. Só o orquestrador faz commits locais, com
   mensagem descritiva e **sem** coautoria do Claude (`Co-Authored-By`). Nunca
   merge nem push.

## Convenções

- Python 3.13, type hints em tudo, `mypy --strict` em `dominio/`, `apresentacao/`
  e `cantos/`.
- Nomes de domínio e serviços **em português, sem acento** (`Missa`, `Estrofe`,
  `ResolvedorCantos`). Termos técnicos consagrados em inglês (`Protocol`,
  `engine`, `migrations`).
- pydantic v2 para modelos; SQLAlchemy 2.0 com `Mapped[...]`; `pathlib.Path`
  sempre.
- Dependências externas entram pelo construtor; `aplicacao/container.py` monta
  as reais.
- Erro recuperável = `Aviso` no resultado; erro fatal = subclasse de
  `ErroPallotti` com mensagem em português para o usuário.
- Logs nunca contêm a chave de API nem letras completas.
- Mensagens de interface e de erro em português do Brasil.

## PowerPoint: armadilhas conhecidas

- O python-pptx não duplica slides. Use `apresentacao/xml_slides.py` (cópia da
  parte + relações + `presentation.xml`).
- `text_frame.text = ...` apaga a formatação. Substitua no nível do **run** e
  copie `pPr`/`rPr` do protótipo.
- Parse e escrita de OOXML com `lxml`, preservando namespaces. Nunca use
  `xml.etree` para reescrever.
- O LibreOffice substitui fontes ausentes: sem a Aptos instalada, o PDF e a
  medição de texto ficam errados. `pallotti diagnostico` verifica.
- Para QA visual: `pallotti modelo previa` ou gere o PDF e converta em PNG
  (`pdftoppm -r 50`). **Olhe as imagens** antes de declarar pronto.

## Definição de pronto

Critérios de parada do marco passando (cole a saída no resumo), mais
`ruff`, `mypy` e `pytest` verdes, docs atualizados se um contrato mudou, e o
portão humano aprovado quando o marco tiver um. Se o plano estiver ambíguo,
pergunte em vez de inventar.
