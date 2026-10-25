# Progresso

> Fluxo: tudo na `main` local, um commit por marco, sem novas branches, sem
> merge, sem push (ORQUESTRACAO §2).

| Marco | Estado | Commit | Última atualização | Observação |
|---|---|---|---|---|
| M0 | ✅ | 6c7d744 | 2026-10-24 | 29 testes; `pallotti doctor` ok |
| M1 | ✅ | bc8879e | 2026-10-24 | aprovado pelo Pedro (TUI) |
| M2 | ☐ | — | — | perguntas antes: fim da missa, aclamação, Santo/Cordeiro, salmo/cântico |
| M3 | ☐ | — | — | — |
| M4 | ☐ | — | — | — |
| M5 | ☐ | — | — | aguarda P3 |
| M6 | ☐ | — | — | 1 folheto em `examples/` (P1 parcial); pedir mais 1–2 |
| M7 | ☐ | — | — | — |
| M8 | ☐ | — | — | — |
| M9 | ☐ | — | — | — |
| M10 | ☐ | — | — | aguarda P5 |
| M11 | ☐ | — | — | — |

## Decisões registradas
- 2026-10-24 — D1: folheto "O Domingo"; exemplo `examples/folheto_example.pdf`, digitalizado (sem texto). Cantos sugeridos do folheto só se o usuário pedir expressamente (Pedro, TUI)
- 2026-10-24 — D8: mistério da fé vem do folheto (texto), sem enum nem padrão (Pedro, TUI)
- 2026-10-24 — D9 parcial: Quaresma sem Glória; demais regras de tempo no M1 (Pedro, TUI)
- 2026-10-24 — D11 parcial: separador dos cantos = imagem de Jesus; resto no M2 (Pedro, TUI)
- 2026-10-24 — D13: direitos autorais resolvidos; repo público, tudo versionado (Pedro, TUI)
- 2026-10-24 — D14: commits locais na `main` pelo orquestrador, sem coautoria do Claude, sem novas branches, sem merge/push (Pedro, TUI)
- 2026-10-24 — D15: orçamento no horário local UTC−4 (Pedro, TUI)
- 2026-10-24 — D16: nomes de código em inglês (pacotes, arquivos, classes, funções, tabelas, valores de enum, comandos do CLI, docstrings/comentários); docs, mensagens ao usuário e etiquetas do modelo PowerPoint em português. Glossário-contrato: `docs/NOMES.md` (Pedro, TUI)
- 2026-10-24 — M1: Glória padrão falso só no Advento e na Quaresma; demais casos pela chave editável (Pedro, TUI)
- 2026-10-24 — M1: nome do arquivo usa título curto = regra ("Domingo"→"Dom", "do Tempo Comum"→"do T.C", resto igual) + campo `short_title` editável (Pedro, TUI)
- 2026-10-24 — M1: data padrão da missa nova = próximo domingo (Pedro, TUI)
- 2026-10-24 — M1: título normalizado para "30° Domingo do Tempo Comum" (iniciais maiúsculas, preposições minúsculas, símbolo °) (Pedro, TUI)
- 2026-10-24 — M1 aprovado (Pedro, TUI). Títulos dos cantos da fixture e rótulos Comunhão/Pós-Comunhão/Saída ainda a confirmar
- 2026-10-24 — Sem resposta, vale o padrão do PLANO §5: D2, D3, D4, D5, D6, D7, D10, D12

## Dúvidas abertas
- P2: `ANTHROPIC_API_KEY` (testes live M6/M7)
- P3: URLs de cantos (M5)
- P5: textos validados das OEs I, II, IV (M10)
