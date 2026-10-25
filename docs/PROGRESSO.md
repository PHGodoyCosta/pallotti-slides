# Progresso

> Fluxo: tudo na `main` local, um commit por marco, sem novas branches, sem
> merge, sem push (ORQUESTRACAO §2).

| Marco | Estado | Commit | Última atualização | Observação |
|---|---|---|---|---|
| M0 | ✅ | 6c7d744 | 2026-10-24 | 29 testes; `pallotti doctor` ok |
| M1 | ✅ | bc8879e | 2026-10-24 | aprovado pelo Pedro (TUI) |
| M2 | ✅ | 156e50e | 2026-10-24 | aprovado pelo Pedro (M2-a..d ok) |
| M3 | ✅ | 2d91d70 | 2026-10-24 | aprovado; ajustes aplicados (M3-fix) |
| M3b | ▶️ | — | 2026-10-24 | depois do M3; cache automático de cantos |
| M4 | ✅ | ef4d40f | 2026-10-24 | 11 testes db; alembic check ok |
| M5 | ✅ | cd1ec12 | 2026-10-25 | M5a + M5b; expected.json gerados pelo pipeline e conferidos (Pedro pode revisar) |
| M6 | 🧑 parcial | af28f72 | 2026-10-24 | parte offline ok; conferir 30tc_2026.expected.json; live aguarda P2; pedir mais 1–2 folhetos |
| M6b | ✅ | (ver log) | 2026-10-24 | gpt-6-astra padrão; live pula sem OPENAI_API_KEY |
| M6c | ✅ | (este commit) | 2026-10-25 | LangChain; 40 testes llm/leaflet |
| M7 | ▶️ | — | — | — |
| M8 | ✅ | 42ed840 | 2026-10-25 | 18 testes CLI/fluxo; resolução por título/URL e texto livre ficam no M7 |
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
- 2026-10-24 — M3 aprovado com ajustes: rótulo "Canto de Saída"; refrão curto com fonte maior; texto nunca vaza, centralizado e grande; caixas do corpo alargadas (M3-b) e estendidas até perto do pé do slide, voltando à regra "a caixa define a área" (M3-a) (Pedro, TUI)
- 2026-10-25 — LLM via LangChain (langchain-openai/anthropic), mantendo o Protocol LLMClient (Pedro, TUI)
- 2026-10-25 — Repertório por link: sempre propor momentos e pedir confirmação; chat de acompanhamento e telas de confirmação na interface (Pedro, TUI)
- 2026-10-25 — Refrão com bloco repetido aparece uma vez entre `/*` e `*/` (Pedro, TUI)
- 2026-10-25 — Missa de 25/10 gerada (OE DC IV) em ~/Documentos/Missa-25-10-2026 a partir do folheto e da playlist do Cifra Club; respostas da OE DC IV fornecidas pelo Pedro
- 2026-10-24 — Sem resposta, vale o padrão do PLANO §5: D2, D3, D4, D5, D6, D7, D10, D12

## Dúvidas abertas
- M6-b: folheto 30/10 indica "OE para Diversas Circunstâncias IV" (fora do enum I–IV). Hoje: eucharistic_prayer = null + nota. Ampliar D7?
- M6-c: referências por extenso no folheto ("Mateus 22,34-40") gravadas abreviadas ("Mt 22,34-40"). Confirmar
- M2-a..d, M1-a, M6-a enviadas no Telegram em 2026-10-24 22:55 (padrões aplicados enquanto isso)
- P2: `ANTHROPIC_API_KEY` (testes live M6/M7)
- P3: URLs de cantos (M5)
- P5: textos validados das OEs I, II, IV (M10)
