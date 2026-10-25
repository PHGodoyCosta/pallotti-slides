# Pallotti Slides

Programa desktop (PySide6 + QFluentWidgets) que gera os slides da missa de domingo
da Paróquia São Cristóvão: lê o folheto litúrgico (PDF) e os cantos, preenche um
modelo PowerPoint fixo e exporta `.pptx` + `.pdf`. Tema visual: São Vicente Pallotti.

> Estado: em construção. Fundação (M0) pronta; a interface gráfica chega no M9.

## Requisitos

- [uv](https://docs.astral.sh/uv/) (instala o Python 3.13 sozinho)
- LibreOffice (`soffice`) para converter em PDF
- Fonte **Aptos** instalada no sistema (licença Microsoft, não é distribuída com o
  projeto). Em desenvolvimento: `export PALLOTTI_FONTS_DIR=src/assets/fonts`
  (pasta ignorada pelo git).

## Como rodar

```bash
uv sync                      # instala as dependências
uv run pallotti --help       # CLI
uv run pallotti doctor  # confere Python, LibreOffice e Aptos
uv run pallotti-gui          # interface gráfica (ainda não implementada)
```

## Desenvolvimento

```bash
uv run pytest                # testes offline
uv run pytest -m soffice     # testes que precisam do LibreOffice
uv run ruff check . && uv run ruff format .
uv run mypy src
```

## Documentação

- [`CLAUDE.md`](CLAUDE.md): regras do projeto
- [`docs/SPEC.md`](docs/SPEC.md): funcionalidades e critérios de aceite
- [`docs/ARQUITETURA.md`](docs/ARQUITETURA.md): stack, camadas e contratos
- [`docs/PLANO.md`](docs/PLANO.md): marcos M0–M11
- [`docs/MODELO_PPTX.md`](docs/MODELO_PPTX.md): etiquetas do modelo PowerPoint
- [`docs/ORQUESTRACAO.md`](docs/ORQUESTRACAO.md): papéis e fluxo de trabalho

## Licença

GPL-3.0-or-later (ver [`LICENSE`](LICENSE)).
