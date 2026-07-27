# Decisão de arquitetura: RAG local com Ollama

> Registro da decisão que originou o pacote `bropilot_core`. Formato ADR
> (Architecture Decision Record): contexto → decisão → consequências.

## Contexto

O BroPilot tinha três motores prontos que **não se falavam**: o `SaveParser`
(estado da party ao vivo), a base de conhecimento em `02_trusted/` (RAG) e um
esboço de LLM (`bropilot.py`, usando Gemini). A pergunta era como integrá-los.

Dois fatos mudaram o desenho durante a discussão:

1. **O Gemini era só o esboço inicial, não um requisito.** Uma vez destravado
   esse apego, o LLM passou a ser uma peça plugável, e o eixo real da decisão
   virou *onde* o modelo roda (API vs local), não *qual* fornecedor.

2. **A base tem ~1M tokens** (119 arquivos `.md`, 4.5 MB). Medido:
   `chars/4 ≈ 1.113.535 tokens`. Um único arquivo (`youtube_manual.md`, 573 KB
   ≈ 140K tokens) já estoura sozinho o contexto de um modelo local.

## Decisão

**MVP: RAG local com Ollama, na mesma máquina do jogo.**

- LLM local via Ollama (default `qwen2.5:7b-instruct-q4_K_M`, quantizado para não
  brigar por VRAM com o BG3).
- Embeddings locais via `nomic-embed-text` no mesmo Ollama — um runtime, dois
  usos, zero dependência externa.
- Vector store embarcado (LanceDB).
- Etapa seguinte (fora do MVP): um modelo de custo baixo via API, trocável sem
  reescrever nada, atrás da interface `LLMProvider`.

## Consequências

### A que mais pega: RAG deixou de ser "fase 2" e virou piso

No Gemini, a janela de contexto gigante permitia enfiar a base inteira no prompt
(*context stuffing*) como muleta temporária, e migrar para RAG depois. **Num LLM
local isso é impossível** — ~1M tokens não cabem em 8K–32K de contexto útil.

Portanto, a escolha de rodar local **fundiu as duas fases**: não existe versão do
stuffing que rode localmente. O RAG (chunking + embeddings + retrieval) é o
requisito mínimo para *qualquer coisa* funcionar, não uma otimização futura.

Isso não é custo — é benefício disfarçado: ir local **forçou a arquitetura certa
desde o primeiro commit**, em vez de construir uma muleta (stuffing) destinada ao
lixo em um mês. O tamanho da base já apontava para isso; a mudança de modelo
apenas tornou inescapável.

### O estado do save vira filtro do retrieval, não texto solto

O diferencial do produto não está no LLM (qualquer um usa um modelo de
prateleira), está em **cruzar o estado do save com o conhecimento certo**. O save
entra duas vezes: como texto no prompt (o modelo enxerga a party) e como sinal de
busca (dirige o retrieval — *state-aware*). Ex.: Monge Open Hand nível 5 →
`build_monk_openhand.md` sobe no ranking mesmo sem a pergunta citá-lo.

### Trade-offs aceitos

- **VRAM compartilhada com o BG3.** Setup "mesma máquina": modelo quantizado
  pequeno é obrigatório, não preferência. Indexação (pesada) roda uma vez, com o
  jogo fechado; runtime é leve (1 embedding da pergunta + 1 geração).
- **Qualidade de raciocínio menor** que um modelo de API forte — aceito no MVP em
  troca de custo zero, privacidade e offline. A etapa 2 sobe esse teto quando
  fizer sentido.
- **Dependência de plataforma real:** os stats ricos (equipamento, HP/CA, spell
  slots) só existem com o mod Lua rodando no BG3/Windows. No Mac, testa-se via um
  `bropilot_inventory.json` fixture (`--dump`). O MVP é, na prática, Windows-first.

## Alternativas descartadas

- **Fine-tuning de um modelo.** Regras de BG3 mudam a cada patch; fine-tuning
  congela conhecimento e ensina estilo, não fatos frescos. Britadeira para pregar
  um quadro.
- **Context stuffing no local.** Descrito acima — não cabe.
- **Amarrar o Gemini.** Era o esboço, não um requisito. A abstração `LLMProvider`
  substitui o apego a fornecedor por liberdade de trocar.
- **Agente com tools (function calling).** Visão de longo prazo, overkill para o
  MVP: mais latência, mais superfície de erro, e modelos locais menores derrapam
  em function calling confiável.
