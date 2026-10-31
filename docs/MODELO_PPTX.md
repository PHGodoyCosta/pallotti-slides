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
| `@pallotti oe=slot` | **Marcador** do lugar da Oração Eucarística no modelo: no resultado ele é trocado pelos slides do arquivo da OE escolhida (§5) e nunca aparece. Exatamente um no modelo (é uma cópia do primeiro slide do bloco, só para a prévia). |
| `@pallotti oe=<id>` | Slide do bloco da Oração Eucarística `<id>` (I, II, III, IV…). Só vale **dentro do arquivo da OE** (`eucharistic_prayers/<id>.pptx`, §5); no modelo principal é erro. Etiquetas não aceitam espaço: `oe=DC_IV` corresponde ao valor `DC IV` do enum (`VARIOUS_NEEDS_IV`; aparece no nome do arquivo). |

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

**Provisório no M2 (2026-10-24), a confirmar no portão:** bloco OE III =
slides 47–60 do exemplo; fim = 66 Cordeiro, 67 "Senhor, eu não sou digno",
68 hóstia (fixo), depois separador (Jesus) + comunhão, separador + pós-comunhão,
separador + saída, 69 final. Desde o M3b o modelo tem 49 slides: os blocos das
OEs (14 slides da OE III, 18 da DC IV) ficam nos arquivos da §5 e, no lugar
deles, o marcador `@pallotti oe=slot`.

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

Cada OE tem o **seu próprio arquivo** em
`src/pallotti_slides/resources/eucharistic_prayers/<id>.pptx` (`<id>` é o da
etiqueta, sem espaço). O arquivo traz só os slides do bloco, em ordem, cada um
com `@pallotti oe=<id>` nas anotações, e usa os mesmos layouts (nomes) e o mesmo
tamanho de slide do modelo principal. O modelo principal guarda só o marcador
`@pallotti oe=slot` (§1).

As 14 Orações Eucarísticas do Missal (3ª edição típica) estão na pasta:

| Arquivo | Id / valor do enum | Rótulo |
|---|---|---|
| `I.pptx` … `V.pptx` | `I`, `II`, `III`, `IV`, `V` | I … V |
| `R_I.pptx`, `R_II.pptx` | `R I`, `R II` | Reconciliação I, II |
| `DC_I.pptx` … `DC_IV.pptx` | `DC I` … `DC IV` | Diversas Circunstâncias I … IV |
| `C_I.pptx` … `C_III.pptx` | `C I` … `C III` | Crianças I, II, III |

O `III.pptx` e o `DC_IV.pptx` foram separados do modelo por
`scripts/create_template_from_example.py`, sem retoque; o `II.pptx` é uma cópia
do `III.pptx` feita por `scripts/create_prayer_ii_from_iii.py`. Os outros onze
são montados por `scripts/create_prayer_blocks.py`, que duplica os slides do
`III.pptx` (imagem, resposta, mistério da fé e Amém) e troca o texto das
respostas no nível do *run*. Esse script roda antes o modo `--check`: ele remonta
os blocos **já aprovados** (II, III e DC IV) e só escreve se o resultado bater
com os arquivos da pasta.

O **bloco só tem as respostas da assembleia**, intercaladas com a imagem da
hóstia: uma resposta por slide, na ordem do Missal, do que vem **depois do
Santo** (que é slide fixo do modelo) até o Amém da doxologia. As três opções de
resposta do "Mistério da fé" viram um único slide com a etiqueta
`{{liturgia.misterio_fe}}`, preenchida com o texto do folheto — inclusive na OE V
e nas das Crianças, que têm aclamação própria. Na OE das Crianças I as duas
aclamações "Glória a vós, Senhor, que tanto nos amais!" ficam no prefácio,
**antes** do Santo, e por isso não entram no bloco.

A lista de OEs do programa é a lista de arquivos da pasta: para acrescentar
uma OE, copie um arquivo existente (para herdar o tema), troque os slides e
salve como `<id>.pptx`. Arquivo com nome desconhecido é ignorado (aviso).

Ao gerar, os slides da OE escolhida são **importados** para o lugar do
marcador (parte do slide, imagens sem duplicar, layout de mesmo nome do modelo
e anotações), e as etiquetas `{{...}}` deles (ex.: `{{liturgia.misterio_fe}}`)
são preenchidas como no modelo.

| Bloco | Estado | Fonte do texto | Aprovado por / data |
|---|---|---|---|
| OE III | MVP (vem do exemplo) | Exemplo 26/09/2026 | — |
| OE Diversas Circunstâncias IV | pronto | respostas fornecidas pelo Pedro | Pedro, 2026-10-24 |
| OE II | pronto | folheto "O Domingo" 02/11/2026 | Pedro, 2026-10-30 |
| OE I, IV, V, Reconciliação I–II, Diversas Circunstâncias I–III, Crianças I–III | pronto | "Orações Eucarísticas — 3ª edição típica do Missal Romano" (PDF, 45 p.), cada bloco conferido numa segunda fonte que cita a página do Missal | Pedro, 2026-10-30 |

Correção registrada na conferência: o PDF repete "Caminhamos na estrada de
Jesus!" na OE V, onde o Missal (p. 564-568) traz "Lembrai-vos, ó Pai, da vossa
Igreja!" como resposta ao 2C. Vale o Missal. Na OE I, as grafias "de vossos
filhos!" e "Em comunhão com os vossos Santos vos louvamos!" seguem o PDF e as
transcrições que citam a p. 523; há fontes com "dos vossos filhos!" e "com
vossos Santos".

Um bloco só entra na pasta depois de aprovado aqui. O agente
pode **montar o rascunho** de um bloco (respostas da assembleia a partir de
fonte indicada pelo usuário), mas a aprovação é humana.

### Cache de cantos

Os slides de cada canto também vêm de um pptx próprio, gerado pelo programa em
`<pasta de dados>/songs/<chave>.pptx` (`Paths.data/songs`): o protótipo do
momento repetido uma vez por página da paginação, com o corpo já preenchido e
`{{canto.rotulo}}` ainda como etiqueta. A chave é um hash das estrofes na ordem
de execução, da `TypographyConfig`, da fonte de medida e do **slide protótipo**
(XML e imagens). Mudou a letra, a tipografia ou o protótipo, o arquivo é gerado
de novo automaticamente; usar o mesmo canto em outro momento com protótipo
igual (comunhão, pós-comunhão, saída) reaproveita o arquivo e só troca o
rótulo. A pasta pode ser apagada a qualquer momento.

## 6. Inspetor (`pallotti template inspect`)

Falha (código de saída ≠ 0) quando:
- um slide tem etiqueta desconhecida ou mal formada;
- falta protótipo para algum momento, ou há protótipo duplicado;
- uma etiqueta `{{...}}` está dividida em vários runs ou é desconhecida;
- um protótipo de canto não tem `{{canto.texto}}`;
- falta o marcador `@pallotti oe=slot`, ele está duplicado, ou há slide
  `@pallotti oe=<id>` no modelo principal;
- não há nenhum arquivo de OE na pasta, ou um arquivo não abre;
- um arquivo de OE tem slide sem `@pallotti oe=<id>` do próprio arquivo, etiqueta
  `{{...}}` desconhecida/dividida ou `{{canto.*}}`, layout que o modelo não tem
  ou tamanho de slide diferente;
- um bloco de OE não tem slide com `{{liturgia.misterio_fe}}` (aviso, não erro,
  para OEs sem aclamação no slide).

As linhas da tabela são as do modelo principal; os problemas dos arquivos de OE
aparecem com o nome do arquivo (ex.: `III.pptx, slide 3`).

Imprime uma tabela: nº do slide, etiqueta, campos e uma miniatura opcional
(`--preview`).
