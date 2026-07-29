# Run #5 — geração via nuvem (gpt-4o-mini), embedding continua local

Preparado, verificado só com mock (nenhuma chamada de rede paga rodou nesta
sessão). Quando você tiver a `OPENAI_API_KEY`, rode o bloco abaixo — é a
única coisa que falta.

## O que muda em relação aos runs #1-#4

**Só a GERAÇÃO.** O embedding/retrieval continua em Ollama/bge-m3, o mesmo
espaço vetorial (1024 dim) com que o índice LanceDB foi construído — trocar
isso faria a busca voltar lixo ou quebrar por incompatibilidade de dimensão.
Índice, as 10 perguntas do `--showcase`, o prompt e o save carregado
continuam idênticos aos runs anteriores.

## Pré-requisitos

1. `ollama serve` rodando (o embedding via `bge-m3` continua precisando dele).
2. `OPENAI_API_KEY` exportada — é o único back-end pago desta chamada; o
   custo estimado das 10 perguntas no `gpt-4o-mini` é da ordem de ~1 centavo
   de dólar.

## Comando

```bash
cd ~/bropilot

# 1. garante o Ollama no ar (para o bge-m3 do embedding) — pula se já estiver
pgrep -f "ollama serve" >/dev/null || (nohup ollama serve > /tmp/ollama_serve.log 2>&1 & sleep 2)

# 2. sua key da OpenAI — cole a key de verdade aqui antes de rodar
export OPENAI_API_KEY=sk-...

# 3. o run #5: --gen-provider openai troca SÓ a geração; --showcase roda as
#    mesmas 10 perguntas contra o mesmo índice/save; BROPILOT_TEMPERATURE=0 e
#    BROPILOT_SEED=42 são os defaults já embutidos no código (explícitos aqui
#    só para deixar a receita auto-contida, como nos runs #3/#4)
source venv/bin/activate
BROPILOT_TEMPERATURE=0 BROPILOT_SEED=42 python -m bropilot_core.scripts.eval_rag \
  --showcase --gen-provider openai \
  --output bropilot_core/eval/showcase_accuracy_gpt4omini_temp0_$(date +%Y%m%d_%H%M%S).md
```

## O que esperar

- O relatório sai em `bropilot_core/eval/showcase_accuracy_gpt4omini_temp0_<timestamp>.md`,
  no mesmo formato dos runs anteriores (pergunta, resposta verbatim, fontes,
  latência).
- O cabeçalho do relatório mostra explicitamente `Backend de geração:
  openai` / `Backend de embedding: ollama` — confira essas duas linhas antes
  de julgar qualquer resposta, é a prova de que a variável única se manteve
  única.
- A coluna **Veredito** sai **em branco** (`_(a preencher)_`) em todas as 10
  perguntas, como nos runs anteriores — o julgamento de acerto/alucinação é
  de um juiz externo, depois, não deste script.
- Latência esperada: gpt-4o-mini via API costuma ser mais rápido por
  pergunta que o 14b local (~15-25s/pergunta é uma faixa razoável, mas isso
  é chute — meça de verdade).

## Depois de rodar

1. Copie o relatório para `docs/ACCURACY_REPORT_gpt4omini_temp0.md` (mesmo
   padrão dos runs #3/#4) se quiser versioná-lo.
2. Adicione uma linha nova em `docs/ACCURACY_TRACKING.md` (run #5) com o
   placar julgado, para fechar o acompanhamento antes×depois.
