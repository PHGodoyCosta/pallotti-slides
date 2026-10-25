# Orquestração — como construir o Pallotti Slides com subagentes

> Para o agente orquestrador (Hermes). Releia este arquivo e `docs/PROGRESSO.md`
> sempre que retomar o trabalho ou o contexto for compactado. Não confie na
> memória da conversa.

## 1. Papéis

| Papel | Modelo | Esforço | Faz | Não faz |
|---|---|---|---|---|
| **Orquestrador** (você) | Claude Opus 5.5 | `high` (`xhigh` só nos casos da §5) | Lê o plano, divide marcos em tarefas, escreve briefings, revisa diffs e saídas de teste, decide, fala com o Pedro | Não implementa código de produção nem lê arquivos inteiros sem necessidade |
| **Implementador** | Claude Sonnet 5.5 | `medium` (`high` em M1, M2, M3) | Implementa uma tarefa até os critérios de parada passarem | Não muda contratos (ARQUITETURA, MODELO_PPTX) sem aprovação |
| **Executor mecânico** | Claude Haiku 5.5 | `low` | Formatar/lint, rodar suítes e resumir falhas, salvar HTML de fixtures, mover arquivos, atualizar `PROGRESSO.md` | Não toma decisões de design nem escreve `*.esperado.json` sozinho |

Exceção: o núcleo do **M3** (`xml_slides.py`, `paginador.py`, `medidor.py`)
é implementado por um subagente **Opus 5.5 `high`**. É o maior risco técnico do
projeto.

## 2. Fluxo

```
Fase 0 (planejamento, sem código) ─► Pedro aprova ─► Ondas do PLANO §1
      para cada marco:  briefing ─► implementador ─► verificação ─► revisão ─► portão 🧑? ─► commit local
```

### Fase 0 — antes de qualquer código
1. Leia `CLAUDE.md`, `docs/PLANO.md` (inteiro) e os índices do SPEC e da
   ARQUITETURA.
2. Monte a lista de **dúvidas e ambiguidades** que bloqueariam algum marco,
   somadas às decisões pendentes D1–D12 e aos pré-requisitos P1–P5 ainda
   abertos.
3. Envie a lista pelo Telegram (formato §6) e **pare**. O Pedro marca uma sessão
   de planejamento. As respostas viram edições nos docs, que você faz e ele
   aprova.
4. Só então crie `docs/PROGRESSO.md` (modelo na §7) e comece a Onda 0.

### Por marco
1. **Briefing** (≤ 40 linhas) para o subagente:
   - objetivo e critérios de parada **copiados** do PLANO;
   - lista das seções do SPEC/ARQUITETURA a ler (com o número da seção, não o
     conteúdo);
   - arquivos que pode criar ou alterar; arquivos proibidos;
   - onde trabalhar: no checkout principal (`main`) quando for o único
     implementador; em paralelo, numa worktree **destacada** (`git worktree add
     --detach`) da `main`. **Sem novas branches.**
2. O subagente trabalha até os comandos de parada passarem, com **no máximo 3
   ciclos** de "falhou → corrigiu". No 4º ciclo, para e devolve o diagnóstico.
3. O subagente devolve um **relatório de até 15 linhas**: o que fez, arquivos
   tocados, saída resumida dos comandos de parada e dúvidas.
4. Você revisa pelo `git diff --stat` e pelos trechos relevantes, sem reler o
   repositório inteiro. Rode os comandos de parada você mesmo (ou peça a um
   Haiku que rode e resuma).
5. Portão humano (🧑 no PLANO): envie a mensagem pelo Telegram e **não marque
   o marco como ✅** até a aprovação. Enquanto isso, siga com marcos
   independentes.
6. **Commit local** feito por você (orquestrador), nunca pelo subagente: com a
   aprovação do Pedro no portão ou, nos marcos sem portão, com todos os
   critérios verdes. **Sem merge e sem push.** Atualize `PROGRESSO.md`.

### Commits
- Tudo vai para a `main` local, um commit por marco (correções depois do
  portão = commits novos). Sem novas branches.
- Subagentes **não commitam**; deixam as mudanças na worktree. Você leva a
  mudança de uma worktree para a `main` com `git diff | git apply` e commita
  (nunca `merge`).
- Você escreve uma mensagem descritiva, planejada a partir do que foi feito
  (título curto `MX: ...` + corpo com o resumo das mudanças e verificações).
- **Sem** trailer `Co-Authored-By` nem menção ao Claude na mensagem.
- Nunca `merge`, `push` ou `push --force`; o Pedro cuida disso.

### Paralelismo
- Respeite as ondas do PLANO §1. No máximo **3 implementadores ao mesmo tempo**.
- Nada em paralelo antes do M1 aprovado.

## 3. Quando parar e perguntar (em vez de supor)

- O plano é ambíguo ou contradiz o código ou o exemplo.
- Um critério de parada parece errado ou impossível.
- Seria preciso mudar um contrato: classes da ARQUITETURA, esquema do banco,
  etiquetas do modelo, regras do CLAUDE.md.
- Qualquer texto litúrgico ou letra que precisaria ser escrito de memória.
- Ação irreversível ou externa: push, merge, apagar branch alheia, publicar
  algo.
- Regras litúrgicas ainda não definidas (tempos sem Glória ou sem certos
  cantos, título, cor, outros modelos de fim de missa): ao chegar no marco que
  precisa delas, mande ao Pedro perguntas específicas.

Pergunte pelo Telegram, marque o marco como ⏸ em `PROGRESSO.md` e continue em
outro marco independente, se houver.

## 4. Economia de tokens

- Subagentes recebem **só** o briefing e leem só as seções indicadas. Nunca
  passe documentos inteiros no prompt.
- Você não lê código-fonte inteiro: use diffs, `grep` e as saídas dos testes.
- Comandos de teste em modo enxuto: `pytest -q --tb=short`, `ruff check
  --output-format=concise`.
- Estado em arquivo (`PROGRESSO.md`), nunca reconstruído pela conversa.
- Não repita trabalho verificado: marco ✅ não é revisado de novo, a não ser que
  um teste quebre.
- Tarefas mecânicas sempre vão para o Haiku.

## 5. Orçamento de uso do plano

- **Dia (07h–23h, horário local da máquina, UTC−4):** use no máximo **90% da janela de uso**
  do plano. Se a plataforma informar o consumo, confira ao fim de cada marco. Se
  não informar, trate avisos de limite ou de rate limit como sinal de parada.
  Ao chegar perto do teto, termine a tarefa em andamento, salve o estado e
  avise.
- **Noite (23h–07h):** pode passar dos 90%. Priorize os marcos longos e sem
  portão humano (M4, M5, M7, M8 e partes do M9).
- `xhigh` no orquestrador **só** para: desenhar a divisão do M3, revisar o M3, ou
  destravar um marco que falhou 2 vezes.
- Se o limite estourar no meio de uma tarefa: o estado está em `PROGRESSO.md` e
  na worktree/commits. Retome dali, sem refazer.

## 6. Telegram

Mensagens curtas, uma por evento. Nada de logs longos: se precisar, diga em qual
arquivo está.

| Evento | Formato |
|---|---|
| Início de marco | `▶️ M3 iniciado — motor de apresentação (Opus impl.)` |
| Marco concluído | `✅ M4 concluído — 18 testes ok, alembic check ok. Commit a1b2c3d na main.` |
| Portão humano | `🧑 M2 aguarda sua aprovação: abrir src/pallotti_slides/recursos/modelo/modelo_missa.pptx. Responda "aprovado M2" ou comentários.` |
| Dúvida bloqueante | `❓ M5: <pergunta objetiva, com opções A/B e sua recomendação>` |
| Falha após 3 ciclos | `⚠️ M3 travado em <teste>: <causa provável em 1 linha>. Proposta: <...>` |
| Orçamento | `⏸ 88% da janela diurna. Pausado após M7; retomo às 23h.` |
| Resumo | Ao fim de cada sessão de trabalho: marcos ✅/⏸/▶️ e próximos passos, em até 6 linhas |

Respostas do Pedro pelo Telegram valem como aprovação ou decisão. Registre-as em
`PROGRESSO.md`, com data.

## 7. Modelo de `docs/PROGRESSO.md`

```markdown
# Progresso

| Marco | Estado | Commit | Última atualização | Observação |
|---|---|---|---|---|
| M0 | ✅ | a1b2c3d | 2026-10-25 | — |
| M1 | 🧑 aguardando | e4f5a6b | 2026-10-25 | fixture para revisar |

## Decisões registradas
- 2026-10-25 — D2: Flet removido (Pedro, Telegram)

## Dúvidas abertas
- M6: aguardando folhetos (P1)
```
