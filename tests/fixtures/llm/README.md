# Respostas gravadas do LLM

Usadas pelo `FakeLLMClient` nos testes offline. Cada arquivo se chama
`<sha256 do PDF>.json` e traz a resposta sob a chave `response`.

- `257a23f841d1cb7b0a75264f083355beb159dd677b3210a736b96119def81bfd.json`: folheto `tests/fixtures/leaflets/30tc_2026.pdf`.
  **SINTÉTICO** (`"synthetic": true`): escrito à mão a partir do
  `30tc_2026.expected.json`, não é saída real do modelo. Substituir pela
  gravação real quando houver chave de API (P2).
