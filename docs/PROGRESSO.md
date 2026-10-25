# Progresso

> Fluxo: tudo na `main` local, um commit por marco, sem novas branches, sem
> merge, sem push (ORQUESTRACAO §2).

| Marco | Estado | Commit | Última atualização | Observação |
|---|---|---|---|---|
| M0 | ✅ | 6c7d744 | 2026-10-24 | 29 testes; `pallotti doctor` ok |
| M1 | ✅ | bc8879e | 2026-10-24 | aprovado pelo Pedro (TUI) |
| M2 | ✅ | 156e50e | 2026-10-24 | aprovado pelo Pedro (M2-a..d ok) |
| M3 | ▶️ | — | 2026-10-24 | Opus high, worktree pallotti-wt/M3; parte do modelo M2 ainda provisório |
| M3b | ☐ | — | 2026-10-24 | depois do M3; cache automático de cantos |
| M4 | ✅ | ef4d40f | 2026-10-24 | 11 testes db; alembic check ok |
| M5 | ⏸ parcial | 182c38f | 2026-10-24 | M5a ok (parser, refrão, acordes); M5b downloaders + HTML aguardam P3 |
| M6 | 🧑 parcial | af28f72 | 2026-10-24 | parte offline ok; conferir 30tc_2026.expected.json; live aguarda P2; pedir mais 1–2 folhetos |
| M6b | ☐ | — | 2026-10-24 | OpenAI padrão; aguarda OPENAI_API_KEY no ambiente para live |
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
- 2026-10-24 — M2 aprovado, inclusive fim da missa, OE III 47–60, rótulos e aclamação/Santo/Cordeiro/salmo (Pedro, TUI)
- 2026-10-24 — M1-a: títulos reais na fixture: entrada "Te Amarei Senhor" (Pedro); ofertório "Um Coração para Amar" (do SPEC F6)
- 2026-10-24 — M6-a: cantos do folheto nunca são extraídos; só os que o usuário informar (Pedro, TUI)
- 2026-10-24 — M6-b: suportar todas as Orações Eucarísticas (lista a confirmar) (Pedro, TUI)
- 2026-10-24 — M6-c: referências bíblicas sempre abreviadas ("Mt 22,34-40") (Pedro, TUI)
- 2026-10-24 — LLM: OpenAI e Anthropic; usuário escolhe o padrão e a chave nas Configurações (Pedro, TUI) — desenho a confirmar
- 2026-10-24 — Toda pergunta no chat também vai para o Telegram (Pedro, TUI)
- 2026-10-24 — M3b: biblioteca de pptx (uma OE por arquivo; cache automático por canto, regenerado se letra/tipografia mudar); M3 termina como está (Pedro, TUI)
- 2026-10-24 — D6: provedor padrão OpenAI; D7: todas as OEs do Missal 3ª ed., lista confirmada no M10 (Pedro, TUI)
- 2026-10-24 — Sem resposta, vale o padrão do PLANO §5: D2, D3, D4, D5, D6, D7, D10, D12

## Dúvidas abertas
- M5b: rótulos de seção do Cifra Club ("[Intro]", "[Primeira Parte]") — decidir com o HTML real; letra de estrofe única sem marcação sai como verso + aviso
- M6-b: folheto 30/10 indica "OE para Diversas Circunstâncias IV" (fora do enum I–IV). Hoje: eucharistic_prayer = null + nota. Ampliar D7?
- M6-c: referências por extenso no folheto ("Mateus 22,34-40") gravadas abreviadas ("Mt 22,34-40"). Confirmar
- M2-a..d, M1-a, M6-a enviadas no Telegram em 2026-10-24 22:55 (padrões aplicados enquanto isso)
- P2: `ANTHROPIC_API_KEY` (testes live M6/M7)
- P3: URLs de cantos (M5)
- P5: textos validados das OEs I, II, IV (M10)
