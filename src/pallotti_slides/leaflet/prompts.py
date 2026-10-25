"""Extraction prompt. The model only copies what is printed; it never invents."""

LEAFLET_INSTRUCTION = """\
Você lê o folheto litúrgico de domingo (PDF, possivelmente digitalizado) e preenche \
os campos pedidos. Copie SOMENTE o que está impresso no folheto.

Regras:
- NUNCA invente, complete de memória ou deduza texto litúrgico. Se um campo não \
estiver no folheto ou não estiver legível, devolva null (nunca string vazia ou "N/D").
- Se o PDF não for um folheto litúrgico de missa, devolva todos os campos null e \
explique em notes.
- Não extraia cantos, letras de música, textos das leituras nem orações.
- Registre em notes qualquer dúvida ou leitura incerta.

Campos e formato:
- title: título da celebração como impresso, ex.: "26º Domingo do Tempo Comum".
- date: data impressa do domingo (AAAA-MM-DD).
- season: tempo litúrgico, só se constar ou for inequívoco pelo título.
- year: ano litúrgico "A", "B" ou "C", só se constar (ex.: "ANO A").
- first_reading, second_reading, gospel: apenas a referência bíblica no formato \
abreviado, ex.: "Ez 18,25-28", "Fl 2,1-11", "Mt 21,28-32", "1Ts 1,5c-10". \
second_reading = null quando não houver 2ª leitura.
- psalm_number: número do salmo exatamente como impresso, ex.: "24(25)".
- psalm_refrain: o refrão do salmo (frase em negrito sob o título SALMO).
- intercessions_response: a resposta da assembleia nas preces (o "AS:" do bloco \
PRECES DA ASSEMBLEIA), sem o prefixo "AS:".
- eucharistic_prayer: I, II, III ou IV, apenas se o folheto indicar uma das quatro \
Orações Eucarísticas. Se for outra (ex.: "para diversas circunstâncias", \
"Reconciliação"), devolva null e explique em notes.
- mystery_of_faith: texto EXATO da aclamação da assembleia após a consagração \
("Mistério da fé"), copiado do folheto sem o prefixo "AS:", sem alterar palavras, \
pontuação nem hifenizações de fim de linha (junte as sílabas separadas).
"""
