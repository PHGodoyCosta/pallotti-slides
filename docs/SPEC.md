# Pallotti Slides — Especificação do Produto

> Documento-fonte do **o quê** e do **quando está pronto**. O **como** está em
> [ARQUITETURA.md](ARQUITETURA.md); a **ordem de execução** em [PLANO.md](PLANO.md);
> o contrato do modelo PowerPoint em [MODELO_PPTX.md](MODELO_PPTX.md).

## 1. Visão

Programa desktop para a Paróquia São Cristóvão que gera, em poucos minutos, os
slides projetados na missa de domingo. O usuário informa o folheto litúrgico
(PDF) e as músicas; o programa preenche um **modelo PowerPoint fixo** — mesmas
imagens, mesmo layout — e entrega um `.pptx` e um `.pdf`.

Tema visual do programa: **São Vicente Pallotti**.

### Princípios

1. **Substituir, nunca criar.** O programa só preenche campos e duplica/remove
   slides que já existem no modelo. Nenhum layout, imagem ou estilo novo.
2. **A IA não escreve conteúdo.** O LLM *extrai* dados de um PDF e *classifica*
   textos que já existem. Ele **nunca** gera letra de música nem texto litúrgico.
   Letras vêm de sites ou do usuário; orações vêm do modelo validado.
3. **Tudo é revisável antes de gerar.** O que foi extraído ou baixado aparece em
   campos editáveis. O que vai para o telão é responsabilidade do usuário, e o
   programa facilita a conferência.
4. **Memória local.** Toda música usada fica no banco local. Na segunda vez que é
   pedida, não há busca na internet.
5. **Determinístico onde dá.** Montagem dos slides, paginação e tipografia são
   código puro e testável, sem IA.

## 2. Glossário

| Termo | Significado |
|---|---|
| **Folheto** | PDF litúrgico do domingo (ex.: folheto da CNBB) com título da celebração, leituras, salmo, preces e oração eucarística. |
| **Modelo** | `mass_template.pptx`: o PowerPoint-base com todos os slides possíveis, marcados com etiquetas. Ver [MODELO_PPTX.md](MODELO_PPTX.md). |
| **Momento** | Ponto da missa onde entra um canto: mantra, entrada, ato penitencial, glória, aclamação, ofertório, comunhão, pós-comunhão, saída. |
| **Estrofe** | Bloco de linhas de uma letra. Tipo verso (`verse`) ou refrão (`chorus`). |
| **Ordem de execução** | Sequência das estrofes como são cantadas (ex.: V1, R, V2, R). |
| **Grupo** | Conjunto de slides do modelo que entra ou sai junto (ex.: imagem separadora + slides do canto de comunhão). |
| **Bloco de OE** | Slides de resposta de uma Oração Eucarística específica (I, II, III…). |
| **Tempo litúrgico** | Advento, Natal, Quaresma, Tríduo Pascal, Páscoa, Tempo Comum. |

## 3. Estrutura da missa gerada

A ordem é definida pelo modelo, não pelo código. Referência (exemplo de
26/09/2026, OE III):

| # | Bloco | Origem do conteúdo | Pode sair? |
|---|---|---|---|
| 1 | Aviso do celular | fixo | não |
| 2 | Título da celebração ("26º Domingo do Tempo Comum") | folheto / usuário | não |
| 3 | Mantra | canto do usuário | sim, sem canto |
| 4 | Canto de entrada (+ imagem separadora) | canto do usuário | sim |
| 5 | Ato penitencial | canto do usuário | sim |
| 6 | Glória | canto do usuário | sim, sem canto **ou** quando `has_gloria = false` |
| 7 | 1ª leitura: imagem + referência ("Ez 18,25-28") + "Palavra do Senhor" | folheto / usuário | não |
| 8 | Salmo: número + refrão | folheto / usuário | não |
| 9 | 2ª leitura: imagem + referência + "Palavra do Senhor" | folheto / usuário | sim, quando não há 2ª leitura |
| 10 | Aclamação ao Evangelho | canto do usuário | sim |
| 11 | Evangelho: "Glória a vós, Senhor" + referência + "Glória a vós, Senhor" | folheto / usuário | não |
| 12 | Preces: refrão da assembleia | folheto / usuário | não |
| 13 | Oração da Partilha (2 slides) | fixo | **nunca** |
| 14 | Ofertório | canto do usuário | sim |
| 15 | "Receba o Senhor…", Prefácio (diálogo), Santo | fixo | não |
| 16 | Bloco da Oração Eucarística escolhida | biblioteca de OEs no modelo | troca pelo bloco escolhido |
| 17 | "Vosso é o Reino…", "Amém", "O amor de Cristo nos uniu" | fixo | não |
| 18 | Cordeiro, "Senhor, eu não sou digno(a)…" | fixo | não |
| 19 | Comunhão | canto do usuário | sim |
| 20 | Pós-comunhão | canto do usuário | sim |
| 21 | Saída | canto do usuário | sim |
| 22 | Imagem final | fixo | não |

As leituras aparecem **só como referência bíblica** sobre a imagem, sem o texto
completo, como no exemplo.

## 4. Funcionalidades

Cada funcionalidade tem **comportamento** e **critérios de aceite**. Uma
funcionalidade só está pronta quando todos os critérios passam.

---

### F1 — Nova missa: entrada de dados

**Comportamento**
- O usuário inicia uma missa nova informando:
  - **data** da celebração (obrigatória; padrão: próximo domingo);
  - **folheto PDF** (opcional);
  - **cantos**, um campo por momento (ver F4);
  - **texto livre** opcional ("prompt"), interpretado e usado para preencher os
    campos acima (ver F4).
- Sem folheto, todos os campos litúrgicos são digitados à mão (F3).

**Aceite**
- [ ] É possível chegar à tela de revisão (F7) com folheto e sem folheto.
- [ ] Data inválida ou ausente bloqueia o avanço com mensagem clara.

---

### F2 — Extração do folheto (IA)

**Comportamento**
- Envia o PDF ao LLM com um esquema de saída estruturada (`LeafletData`) e
  extrai:
  - título da celebração ("26º Domingo do Tempo Comum");
  - tempo litúrgico e ano litúrgico (A/B/C), se constarem;
  - referência da 1ª leitura, do Evangelho e, se houver, da 2ª leitura;
  - número do salmo, no formato do folheto ("24(25)"), e seu refrão;
  - refrão das preces da assembleia;
  - oração eucarística indicada (I, II, III…);
  - texto da aclamação do mistério da fé, como escrito no folheto (varia
    conforme o rito e a oração eucarística).
- O folheto traz **cantos sugeridos**, mas eles **nunca** são extraídos nem
  usados: os cantos vêm só do que o usuário informar (F4).
- Campo não encontrado volta **vazio**, nunca inventado. O usuário é avisado de
  quais campos faltam.
- Pode-se usar o mesmo folheto de novo sem nova chamada: o resultado fica em
  cache pelo hash do PDF.

**Aceite**
- [ ] Para cada folheto de teste em `tests/fixtures/leaflets/`, a extração (teste
      `live`) acerta **100%** de: título, referências das leituras, número do
      salmo, refrão do salmo, refrão das preces e OE.
- [ ] Um PDF que não é folheto retorna erro amigável, sem travar.
- [ ] Sem chave de API configurada, a extração fica desabilitada e a interface
      explica o motivo. O fluxo manual (F3) continua funcionando.
- [ ] Testes unitários usam um LLM falso; nenhum teste padrão acessa a rede.

---

### F3 — Liturgia manual

**Comportamento**
- Formulário com os mesmos campos da F2. Para a OE, uma lista com as orações
  disponíveis no modelo.
- `has_gloria` vem preenchido pela regra do tempo litúrgico (falso no Advento e
  na Quaresma) e pode ser alterado (solenidades).

**Aceite**
- [ ] Todos os campos obrigatórios são validados: título, 1ª leitura, salmo
      (número e refrão), Evangelho, refrão das preces, OE e aclamação do
      mistério da fé.
- [ ] A lista de OEs mostra apenas os blocos que existem no modelo.

---

### F4 — Entrada de cantos

**Comportamento**
- Para cada momento, o usuário pode informar uma destas opções:
  1. **título** (ou um trecho, ex.: "me chamaste para caminhar");
  2. **URL** (Letras.mus.br, Cifra Club e outros sites suportados);
  3. **letra colada** (texto livre).
- O tipo é detectado sozinho: URL por padrão de endereço; letra colada quando há
  mais de 2 linhas; título nos demais casos.
- **Texto livre**: o usuário pode colar algo como "Entrada: Me chamaste;
  Ofertório: https://…; Comunhão: Pão da vida". O LLM converte isso em
  `SongRequest` por momento e **preenche o formulário**. O formulário continua
  sendo a fonte da verdade.
- Momento sem canto = grupo removido da apresentação. Os cantos sugeridos no
  folheto são ignorados (ver F2).

**Aceite**
- [ ] A detecção de tipo acerta nos casos de teste (URL, título, letra com
      estrofes).
- [ ] O texto livre de exemplo preenche os momentos certos (teste com LLM falso
      e um teste `live`).

---

### F5 — Resolução de cantos (banco → internet)

**Comportamento** — para cada pedido, em ordem:
1. **URL informada:** se essa URL já está no banco, usa o registro salvo. Se
   não, baixa, analisa (F6) e salva.
2. **Título/trecho:** busca aproximada no banco local por título, apelidos e
   primeira linha.
   - Uma correspondência forte (pontuação ≥ 90) é pré-selecionada.
   - Pontuação entre 70 e 89 gera candidatos que o usuário escolhe.
3. **Nada no banco:** busca na internet (busca web do LLM, restrita aos sites
   suportados). Retorna até 5 **candidatos** (título, artista, URL). O usuário
   confirma um; o programa baixa, analisa e salva.
4. **Letra colada:** analisa (F6) e salva com `source = manual`.
- O texto pedido pelo usuário vira um **apelido** do canto escolhido. Assim,
  "me chamaste" passa a achar "Te amarei, Senhor" direto no banco.
- O LLM devolve **URLs**, nunca letras. O texto da letra sempre vem do site
  baixado ou do usuário.

**Aceite**
- [ ] Pedir o mesmo canto duas vezes: na segunda não há acesso à rede (o teste
      verifica que o baixador e o buscador não foram chamados).
- [ ] "me chamaste" encontra o canto cuja primeira linha é "Me chamaste para
      caminhar na vida contigo".
- [ ] Falha de rede ou site fora do ar gera um aviso por momento, sem
      interromper os outros cantos.

---

### F6 — Estruturação da letra

**Comportamento**
- Converte o texto bruto em `Song`: estrofes (separadas por linha em branco),
  tipo de cada estrofe, destaque (negrito) por linha e **ordem de execução**.
- Detecção de refrão, em ordem de prioridade:
  1. marcações do site ou do texto ("Refrão", "Ref.:", "R:", "[Refrão]");
  2. estrofe que se repete igual (após normalizar) é refrão;
  3. se ainda houver dúvida: o LLM recebe as estrofes **numeradas** e devolve
     apenas os **números** das que são refrão;
  4. o usuário pode corrigir na revisão.
- Linhas como "Refrão" ou "(Refrão)" no meio da letra viram referência à estrofe
  de refrão na ordem de execução.
- Acordes (Cifra Club) são removidos.
- Linhas de refrão saem em **negrito**. Linhas de verso podem ser marcadas como
  destaque individualmente (ex.: "Glória, glória, glória, glória" no Glória).

**Aceite**
- [ ] Os cantos do exemplo ("Te amarei, Senhor", "Um coração para amar", Glória,
      Ato Penitencial), salvos como HTML de teste, geram exatamente a estrutura
      esperada (`*.expected.json`).
- [ ] Nenhum acorde sobra no texto final dos fixtures do Cifra Club.

---

### F7 — Revisão e edição

**Comportamento**
- Tela única com:
  - dados da celebração e da liturgia (editáveis);
  - cada canto com suas estrofes. É possível editar o texto, alternar
    verso/refrão, marcar linhas em negrito, reordenar a execução e remover o
    canto;
  - avisos (campos faltando, refrão não identificado, Glória com
    `has_gloria = false` etc.);
  - **pré-visualização** dos slides (miniaturas do PDF gerado).
- Edições em um canto podem ser salvas no banco ("atualizar na biblioteca") ou
  valer só para esta missa.

**Aceite**
- [ ] Toda informação que vai para os slides é editável nesta tela.
- [ ] O botão "Gerar" fica desabilitado enquanto houver erro bloqueante.

---

### F8 — Montagem do PowerPoint

**Comportamento**
- Abre uma cópia do modelo e:
  1. remove grupos desligados (cantos ausentes, Glória fora de época, 2ª leitura
     ausente);
  2. mantém só o bloco da OE escolhida;
  3. para cada canto, duplica o slide-protótipo do momento, um slide por página
     (F9);
  4. substitui as etiquetas `{{...}}` mantendo a formatação do modelo;
  5. remove as etiquetas das anotações do orador no arquivo final.
- Nome do arquivo: `Missa - {título curto} - {dd.mm.aaaa} - OE {n}.pptx`. O
  título curto é editável; por padrão aplica a regra "Domingo"→"Dom" e "do
  Tempo Comum"→"do T.C", mantendo o resto. A data é a da celebração.
  (ex.: `Missa - 26° Dom do T.C - 26.09.2026 - OE III.pptx`).

**Aceite**
- [ ] **Teste de referência:** a partir de `tests/fixtures/masses/26tc_2026.json`,
      a apresentação gerada tem a **mesma sequência de slides e os mesmos textos**
      do exemplo `examples/Missa - 26° Dom do T.C - 26.09.2026 - OE III.pptx`.
      Alinhamento e tamanho de fonte dos cantos podem diferir, seguindo F9.
- [ ] Nenhuma etiqueta `{{` ou `@pallotti` sobra no arquivo gerado.
- [ ] O arquivo abre sem erro no python-pptx e no LibreOffice e passa no
      validador OOXML.
- [ ] Com todos os 9 momentos preenchidos, os cantos aparecem na ordem da
      Seção 3.

---

### F9 — Paginação e tipografia dos cantos

**Regras**
- **Uma estrofe por slide**, na ordem de execução. Um refrão repetido gera um
  slide repetido, como no exemplo.
- Texto **centralizado**. Refrão em **negrito**.
- Rótulo do momento no canto superior esquerdo (vermelho, como no modelo).
- **Tamanho de fonte por canto**: o maior tamanho entre `max_font` (54 pt) e
  `min_font` (40 pt), em passos de 2 pt, em que **todas** as páginas do canto
  cabem na caixa. Assim o canto inteiro fica com o mesmo tamanho e todos os
  cantos ficam na mesma faixa.
- Estrofe com mais de `max_lines` (6) linhas, ou que não cabe nem em
  `min_font`, é dividida em páginas equilibradas, sempre entre linhas (nunca no
  meio de uma linha).
- A medição usa as métricas reais da fonte do modelo (Aptos), incluindo quebra
  automática de linha.
- `min_font`, `max_font` e `max_lines` ficam nas Configurações.

**Aceite**
- [ ] **Calibração:** o medidor diz que todos os slides de canto do exemplo cabem
      nos tamanhos em que estão.
- [ ] Um canto com uma estrofe de 12 linhas vira 2 slides de 6 linhas.
- [ ] Na inspeção visual (PDF → imagem) de uma missa com os 9 cantos, nenhum
      texto sai da caixa ou do slide.

---

### F10 — Oração eucarística

**Comportamento**
- O modelo contém um bloco por OE suportada, com as respostas da assembleia e as
  imagens intercaladas. A OE indicada no folheto (ou escolhida) define o bloco
  mantido.
- O slide do mistério da fé usa o texto da aclamação **extraído do folheto**
  (ou digitado pelo usuário). Ela varia conforme o rito e a OE; não há texto
  padrão e o programa nunca a preenche de memória.
- O texto de cada bloco é **validado pelo usuário** contra o Missal Romano (3ª
  edição) ou o folheto antes de ser marcado como pronto.

**Aceite**
- [ ] MVP: OE III idêntica ao exemplo.
- [ ] Marco posterior: OE I, II e IV (e outras que a paróquia usar), cada uma com
      aprovação registrada em `docs/MODELO_PPTX.md` (tabela de blocos).

---

### F11 — Exportação PDF

**Comportamento**
- Converte o `.pptx` em `.pdf` pelo LibreOffice (`soffice --headless`). No
  Windows com PowerPoint instalado, pode usar o PowerPoint (opcional).
- Salva os dois arquivos na pasta de saída e oferece "Abrir pasta".

**Aceite**
- [ ] O PDF tem o mesmo número de páginas que o `.pptx` tem de slides.
- [ ] Sem LibreOffice, o `.pptx` é gerado mesmo assim, com um aviso de que o PDF
      não pôde ser criado e de como resolver.

---

### F12 — Biblioteca de cantos

**Comportamento**
- Lista os cantos do banco com busca (título, apelido, primeira linha) e filtro
  por momento habitual.
- Permite criar, editar (estrutura completa, como na F7), mesclar duplicados,
  gerenciar apelidos e excluir.
- Mostra quantas vezes e quando cada canto foi usado.

**Aceite**
- [ ] Operações de criar, editar e excluir funcionam e persistem.
- [ ] A busca encontra por título, apelido e primeira linha, sem diferenciar
      acentos e maiúsculas.

---

### F13 — Histórico de missas

**Comportamento**
- Cada geração salva a `Mass` completa (JSON) e os caminhos dos arquivos.
- É possível reabrir (para corrigir e gerar de novo) e **duplicar** (usar como
  ponto de partida para o domingo seguinte).

**Aceite**
- [ ] Reabrir uma missa e gerar de novo sem alterar nada produz o mesmo conteúdo.

---

### F14 — Configurações

- Provedor de IA: **OpenAI** (padrão) ou **Anthropic**, com o modelo de cada um.
- Chave da API de cada provedor, informada pelo usuário e guardada no cofre do
  sistema via `keyring`.
- Pasta de saída padrão.
- Caminho do LibreOffice (detectado automaticamente; editável).
- Caminho do modelo `.pptx` (padrão: o que vem com o programa).
- Tipografia: `min_font`, `max_font`, `max_lines`.
- Tema claro/escuro/sistema.

**Aceite**
- [ ] As configurações persistem entre execuções.
- [ ] Um diagnóstico mostra o estado de: chave da API, LibreOffice, fonte Aptos e
      modelo válido.

---

### F15 — Linha de comando (para desenvolvimento e agentes)

Tudo o que a interface faz pode ser feito sem interface gráfica:

```
pallotti generate --mass mass.json --output ./saida        # JSON → pptx + pdf
pallotti leaflet extract leaflet.pdf > data.json           # F2
pallotti songs resolve "me chamaste"                       # F5
pallotti songs import --url https://www.letras.mus.br/...
pallotti template inspect                                  # lista slides, etiquetas e problemas
pallotti template preview --output ./previa                # gera PNGs de cada slide
pallotti doctor                                            # F14 (diagnóstico)
```

**Aceite**
- [ ] Cada comando tem `--help` e um teste de integração.

## 5. Requisitos não funcionais

| Requisito | Meta |
|---|---|
| Tempo de geração (com cantos já no banco, sem LLM) | < 15 s, incluindo PDF |
| Tempo de ponta a ponta (com folheto e 3 cantos novos) | < 2 min |
| Funcionamento offline | Tudo, menos extração do folheto e busca de cantos novos |
| Plataformas | Linux (desenvolvimento) e Windows (paróquia, a confirmar) |
| Dados | Banco SQLite local na pasta de dados do usuário; nada vai para a nuvem além das chamadas ao LLM e aos sites de letras |
| Segurança | A chave de API nunca é gravada em texto puro nem em log |
| Custo de IA | Poucos centavos de dólar por missa no modelo padrão, com cache do folheto e banco de cantos; modelo configurável |

## 6. Fora do escopo (MVP)

- Ritos especiais: Ramos, Tríduo Pascal, Vigília, batizados, crismas,
  casamentos.
- Projeção ao vivo / controle de slides.
- Texto completo das leituras nos slides.
- Edição do layout do modelo pelo programa (o modelo é editado no PowerPoint).
- Calendário litúrgico automático, que calcularia o domingo e as leituras pela
  data. Fica para o backlog: [PLANO.md](PLANO.md) §6.
- Sincronização entre computadores e banco remoto (a arquitetura permite; não
  será feito agora).
