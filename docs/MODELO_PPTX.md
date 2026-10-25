# Modelo PowerPoint — contrato

O arquivo `src/pallotti_slides/resources/template/mass_template.pptx` é a **única
fonte de layout**. O programa nunca cria formas, imagens ou estilos: só mantém,
remove, duplica e reordena slides do modelo e troca textos marcados.

Qualquer pessoa pode editar o modelo **no PowerPoint** (trocar uma imagem,
ajustar uma cor, corrigir uma resposta) sem mexer no código, desde que respeite
as etiquetas abaixo. Depois de editar, rode `pallotti template inspect`.

## 1. Etiqueta do slide (anotações do orador)

A **primeira linha das anotações** de cada slide define o papel dele:

| Etiqueta | Significado |
|---|---|
| `@pallotti fixo` | Sempre presente. (Slide sem etiqueta = fixo, mas o inspetor avisa.) |
| `@pallotti grupo=<id>` | Entra ou sai junto com o grupo `<id>`. |
| `@pallotti canto=<momento>` | **Protótipo** do canto daquele momento: duplicado uma vez por página do canto. Pertence ao grupo `canto:<momento>`. |
| `@pallotti oe=<id>` | Faz parte do bloco da Oração Eucarística `<id>` (I, II, III, IV…). Só o bloco escolhido fica. |

Grupos reconhecidos:

| Grupo | Some quando |
|---|---|
| `canto:<momento>` | Não há canto para o momento. Momentos: `mantra`, `entrada`, `ato_penitencial`, `gloria`, `aclamacao`, `ofertorio`, `comunhao`, `pos_comunhao`, `saida`. |
| `canto:gloria` | Também some quando `has_gloria = false`. |
| `segunda_leitura` | `second_reading` está vazia. |

As etiquetas ficam em português, porque a equipe as edita no PowerPoint;
`presentation/template.py` as mapeia para os campos e enums em inglês. Os
momentos de `canto:<momento>` e `canto=<momento>` correspondem a `SongMoment`:
`mantra`→`MANTRA`, `entrada`→`ENTRANCE`, `ato_penitencial`→`PENITENTIAL_ACT`,
`gloria`→`GLORIA`, `aclamacao`→`ACCLAMATION`, `ofertorio`→`OFFERTORY`,
`comunhao`→`COMMUNION`, `pos_comunhao`→`POST_COMMUNION`,
`saida`→`RECESSIONAL`.

A **imagem separadora** que antecede um canto leva a etiqueta do grupo do canto
(`@pallotti grupo=canto:entrada`), para sumir junto.

## 2. Etiquetas de texto (dentro dos slides)

Escritas no próprio texto do slide, com a formatação desejada aplicada à
etiqueta. A substituição mantém fonte, cor, tamanho e negrito do run onde a
etiqueta está.

| Etiqueta | Exemplo de valor |
|---|---|
| `{{celebracao.titulo}}` | 26° Domingo do Tempo Comum |
| `{{liturgia.primeira_leitura}}` | Ez 18,25-28 |
| `{{liturgia.salmo_numero}}` | 24(25) |
| `{{liturgia.salmo_refrao}}` | Recordai, Senhor meu Deus, vossa ternura e compaixão! |
| `{{liturgia.segunda_leitura}}` | Fl 2,1-11 |
| `{{liturgia.evangelho}}` | Mt 21,28-32 |
| `{{liturgia.preces_refrao}}` | Vinde em nosso auxílio, Senhor! |
| `{{liturgia.misterio_fe}}` | texto da aclamação extraído do folheto (dentro de cada bloco de OE) |
| `{{canto.rotulo}}` | Canto de Entrada (só em protótipo de canto) |
| `{{canto.texto}}` | corpo do canto (só em protótipo de canto; ocupa a caixa inteira) |

Regras:
- Uma etiqueta deve ficar **inteira em um único run**. O PowerPoint às vezes
  divide o texto digitado em pedaços; o inspetor detecta isso. Para corrigir,
  apague e digite a etiqueta de novo de uma vez, ou cole como texto sem
  formatação.
- O `R:` vermelho das respostas fica **fora** da etiqueta (ex.: run vermelho
  `R: ` + run preto `{{liturgia.preces_refrao}}`).
- A caixa de `{{canto.texto}}` define a área disponível para a paginação (F9).

## 3. Mapa do exemplo → modelo

Baseado em `examples/Missa - 26° Dom do T.C - 26.09.2026 - OE III.pptx`
(69 slides, 13,33" × 7,5", fonte Aptos).

| Slides do exemplo | Conteúdo | Etiqueta no modelo |
|---|---|---|
| 1 | Desligue o celular | `fixo` |
| 2 | Título do domingo | `fixo` + `{{celebracao.titulo}}` |
| 3 | Mantra | `canto=mantra` |
| 4 | Imagem (Jesus) | `grupo=canto:entrada` |
| 5–8 | Canto de entrada | **um** protótipo `canto=entrada` |
| 9 | Imagem | `grupo=canto:ato_penitencial` |
| 10–13 | Ato penitencial | protótipo `canto=ato_penitencial` |
| 14 | Imagem | `grupo=canto:gloria` |
| 15–19 | Glória | protótipo `canto=gloria` |
| 20 | Imagem (Jesus) | `fixo` |
| 21 | Imagem + `Ez 18,25-28` | `fixo` + `{{liturgia.primeira_leitura}}` |
| 22 | Palavra do Senhor | `fixo` |
| 23 | Salmo | `fixo` + `{{liturgia.salmo_numero}}`, `{{liturgia.salmo_refrao}}` |
| 24 | Imagem (Bíblia) + `Fl 2,1-11` | `grupo=segunda_leitura` + `{{liturgia.segunda_leitura}}` |
| 25 | Palavra do Senhor | `grupo=segunda_leitura` |
| 26 | Aclamação | protótipo `canto=aclamacao` |
| 27 | R: Glória a vós, Senhor | `fixo` |
| 28 | Imagem + `Mt 21,28-32` | `fixo` + `{{liturgia.evangelho}}` |
| 29 | R: Glória a vós, Senhor | `fixo` |
| 30 | Imagem (homilia) | `fixo` |
| 31 | Preces | `fixo` + `{{liturgia.preces_refrao}}` |
| 32 | Imagem | `fixo` |
| 33–34 | Oração da Partilha | `fixo` (**nunca sai**) |
| 35 | Imagem | `grupo=canto:ofertorio` |
| 36–39 | Ofertório | protótipo `canto=ofertorio` |
| 40 | Imagem | `fixo` |
| 41 | R: Receba o Senhor… | `fixo` |
| 42 | Imagem (hóstia) | `fixo` |
| 43 | Prefácio (diálogo) | `fixo` |
| 44 | Imagem | `fixo` |
| 45–46 | Santo | `fixo` |
| 47–60 | Respostas da OE III intercaladas com imagens | `oe=III` (com `{{liturgia.misterio_fe}}` no slide 50) |
| 61 | Imagem | `fixo` |
| 62 | R: Vosso é o Reino… | `fixo` |
| 63 | R: Amém | `fixo` |
| 64 | R: O amor de Cristo nos uniu | `fixo` |
| 65 | Imagem | `fixo` |
| 66 | Cordeiro | `fixo` |
| 67 | Senhor, eu não sou digno(a) | `fixo` |
| 68 | Imagem | `fixo` |
| — | **novo**: imagem + protótipo de comunhão | `grupo=canto:comunhao` + `canto=comunhao` |
| — | **novo**: protótipo de pós-comunhão | `canto=pos_comunhao` |
| — | **novo**: imagem + protótipo de saída | `grupo=canto:saida` + `canto=saida` |
| 69 | Imagem final | `fixo` |

**Decidido (2026-10-24):** a imagem separadora dos cantos é sempre a de Jesus
(slides 4, 9, 14…). Os slides 42/44/61/65/68 são a hóstia.

**A confirmar com o usuário** (marco M2, com perguntas específicas): os limites
exatos do bloco da OE (47–60), a posição dos novos cantos de comunhão,
pós-comunhão e saída e de seus separadores, e se o slide 68 pertence ao grupo
da comunhão.

## 4. Padrão do protótipo de canto

Derivado dos slides de canto do exemplo:

- rótulo: caixa no canto superior esquerdo, Aptos 28 pt, negrito, vermelho
  `#FF0000` → `{{canto.rotulo}}`;
- corpo: caixa de conteúdo de cerca de 12,5" × 5,4" a partir de (0,4", 1,4"),
  Aptos, `noAutofit` → `{{canto.texto}}`;
- o programa define: alinhamento **centralizado**, tamanho entre 40 e 54 pt (um
  tamanho para o canto inteiro), negrito nas linhas de refrão/destaque.

## 5. Blocos de Oração Eucarística

| Bloco | Estado | Fonte do texto | Aprovado por / data |
|---|---|---|---|
| OE III | MVP (vem do exemplo) | Exemplo 26/09/2026 | — |
| OE I | pendente | Missal Romano 3ª ed. / folheto | — |
| OE II | pendente | Missal Romano 3ª ed. / folheto | — |
| OE IV | pendente | Missal Romano 3ª ed. / folheto | — |

Um bloco só entra na lista de OEs do programa depois de aprovado aqui. O agente
pode **montar o rascunho** de um bloco (respostas da assembleia a partir de
fonte indicada pelo usuário), mas a aprovação é humana.

## 6. Inspetor (`pallotti template inspect`)

Falha (código de saída ≠ 0) quando:
- um slide tem etiqueta desconhecida ou mal formada;
- falta protótipo para algum momento, ou há protótipo duplicado;
- uma etiqueta `{{...}}` está dividida em vários runs ou é desconhecida;
- um protótipo de canto não tem `{{canto.texto}}`;
- um bloco de OE não tem slide com `{{liturgia.misterio_fe}}` (aviso, não erro,
  para OEs sem aclamação no slide).

Imprime uma tabela: nº do slide, etiqueta, campos e uma miniatura opcional
(`--preview`).
