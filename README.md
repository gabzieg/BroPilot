# 🎲 BroPilot - Baldur's Gate 3 Min-Maxing Assistant

O **BroPilot** é um assistente virtual (Copilot) desenvolvido para rodar localmente e auxiliar jogadores de Baldur's Gate 3 com decisões de min-maxing, otimização de *builds*, economia de ações (*Action Economy*) e escolhas de equipamentos.

## 🎯 Objetivo (MVP)
Um motor que é acionado via atalho (ex: `Ctrl + 0`) durante a gameplay. O gatilho força um Quicksave (`F5`), o BroPilot descompacta o arquivo `.lsv`, lê o estado atual da *party* (níveis, itens, atributos) e cruza isso com uma base de conhecimento (RAG) para sugerir a melhor jogada, item de mercador ou nó de diálogo.

## 🏗️ Arquitetura do Projeto

O projeto é dividido em dois grandes motores:
1. **Pipeline de Dados (ETL/Knowledge Base):** Scripts em Python que extraem dados da BG3 Wiki e transcrições de vídeos focados em *builds*. Usa a arquitetura Medallion:
   - `01_raw`: Arquivos HTML brutos e despejos de texto manual (`.txt`).
   - `02_trusted`: Arquivos convertidos para Markdown, limpos de tags HTML, lixos de interface e marcações de tempo.
   - `03_refined`: Matrizes de itens e mercadores (WIP).
2. **Cérebro da IA & Save Extractor:** Motor em Python (`BroPilot-SaveParser`) que extrai dados do *save* do jogo (`.lsv`, LSF, Osiris StorySave) + mod companion (`BroPilotExporter`) para alimentar o LLM (`bropilot.py`) com o estado da party em tempo real.

## 🚫 Reddit fora do pipeline
O Reddit foi removido das fontes de dados do BroPilot. A API pública (`.json`) está bloqueada por Cloudflare para scraping automatizado (confirmado mesmo com `cloudscraper`), e a API oficial (OAuth) deixou de oferecer registro gratuito de apps para uso relacionado a tratamento por IA. Sem uma via viável e sustentável de acesso, decidimos não depender do Reddit como fonte.

Os scripts e dados que existiam (`reddit_parser.py`, `reddit_text_cleaner.py`, `reddit_manual.txt/.md`) foram preservados em `BroPilot-Knowledge/_archive/reddit/` para referência, mas não fazem parte do fluxo ativo.

## 🧰 Modo de Contingência (API Humana)
Para fontes onde a extração automática falha (ex.: um vídeo do YouTube sem transcrição disponível), existe uma rotina de limpeza manual: dê `Ctrl+A` / `Ctrl+C` no conteúdo, cole em um arquivo `_manual.txt` na camada RAW e rode o script `_text_cleaner.py` correspondente para gerar o Markdown limpo.

## ⏳ Bloqueio de IP do YouTube: paciência em vez de proxy
`youtube_parser.py` roda sobre `youtube-transcript-api`, que depende de requisições diretas ao YouTube — sem chave de API. Passado de um certo volume de requisições, o YouTube bloqueia o IP (`IpBlocked`/`RequestBlocked`) e o bloqueio pode durar bem mais do que os "minutos" que a própria lib sugere; testamos e confirmamos que não é um bloqueio pontual de vídeo específico, é o IP inteiro.

A lib oferece dois contornos, e optamos por nenhum dos dois:
- **Cookies de autenticação**: além de resolver só bloqueio de vídeo *age-restricted* (não o bloqueio de IP por rate-limit), essa via está **desativada na versão instalada** (`youtube-transcript-api` 1.2.4) — o próprio autor removeu o suporte após uma mudança da API do YouTube quebrar a implementação anterior.
- **Proxy residencial rotativo** (ex.: Webshare): resolve de verdade, mas exige contratar e manter um serviço pago de terceiros — custo recorrente para um projeto que hoje é 100% local e sem custo externo.

Optamos por **paciência**: o script já é idempotente (pula vídeos já baixados em `01_raw`/`02_trusted`), então basta rodar `youtube_parser.py` aos poucos, espaçado ao longo de vários dias, até completar a lista curada. Mais lento, mas sem dependência de serviço pago nem risco de banir a conta usada nos cookies.

## 💰 Análise de Custo & Monetização

Análise completa de **custo de desenvolvimento + implementação + manutenção** cruzada com modelos de monetização, considerando o time de **4 sócios** (sem folha — dev é custo de oportunidade, não caixa).

📊 **[Planilha completa (Google Sheets)](https://docs.google.com/spreadsheets/d/1AjFbbCcDz8IZqTZgOYPhCQ13x6nRUbC8/edit?usp=sharing&ouid=109391157338588128384&rtpof=true&sd=true)** — 7 abas com fórmulas vivas: premissas editáveis, custo unitário, CAPEX de tempo, TCO local vs API, veredito e monetização.

### Achado principal

A escolha de **RAG local** partiu da suposição de que era mais barato — e está certa para o **custo de caixa** (token = $0, roda na máquina do usuário). Mas a análise revelou que, dado o **uso baixo** (~40 consultas/usuário/mês) e a **KB pequena** (1,1M tokens medidos: 119 arquivos `.md`, 4.5 MB), a via **API também sairia baratíssima**:

| Modelo (Fase 2) | Custo/usuário/mês | Custo/usuário/ano |
|---|---|---|
| Gemini Flash | ~$0.019 | ~$0.23 |
| GPT-4o-mini | ~$0.038 | ~$0.46 |
| Haiku 4.5 (pior caso) | ~$0.280 | ~$3.36 |
| RAG local (MVP) | $0 | $0 |

**Conclusão:** custo não é o critério que separa local de API aqui — ambos são baratos. A decisão real é **privacidade/offline** (local) vs. **qualidade de resposta + facilidade de instalação** (API). O "local" cobra o preço em **tempo de dev, suporte a hardware do usuário e atrito de instalação** (baixar Ollama + modelo ~5 GB), custos reais porém invisíveis no extrato.

### O gargalo é tempo, não dinheiro

Com 4 sócios sem folha, o custo de **caixa** do MVP local é mínimo — **~$215/ano** (code-signing Windows + domínio), coberto por **~21 vendas a $15**. O investimento pesado é **tempo**: estimadas **~230h restantes** até shippar = **~58h por sócio** (SaveParser, ETL e o scaffold do core RAG já estão escritos: ~4.550 LOC).

### Recomendação

- **Arquitetura:** manter o MVP local (já construído, com a abstração `LLMProvider` pronta), mas **antecipar a Fase 2 API** (Gemini Flash) como opção paralela — resolve o teto de qualidade e a barreira de instalação por ~$92/ano em 5k usuários. Deixe o jogador escolher: local (privado/grátis) ou cloud (melhor/mais fácil).
- **Monetização:** **one-time a $10–15** na cultura de mods de BG3 (caixa coberto trivialmente), com **BYOK** para quem quiser a versão cloud sem o time pagar token. Evitar assinatura no MVP (churn de jogo single-player mata MRR); freemium só faz sentido depois da Fase 2 API.

> ⚠️ Premissas de preço de token verificadas em jul/2026. A estimativa de 230h de dev restante é aproximada — ajuste a aba `CAPEX Dev (tempo)` na planilha conforme o escopo real.

## 📁 Estrutura de Pastas
```text
BroPilot/
├── bropilot.py                   # Orquestrador da IA (LLM Core)
├── BroPilot-Knowledge/           # Base de dados de conhecimento (RAG)
│   ├── data/
│   │   ├── 01_raw/               # Dumps de HTML e textos puros (Ctrl+C)
│   │   ├── 02_trusted/           # Textos curados em Markdown
│   │   └── 03_refined/           # Matrizes, JSONs de itens e índices (ex: dialog_index.json)
│   ├── scripts/
│   │   ├── wiki_scraper.py       # Crawler da Wiki oficial
│   │   ├── text_cleaner.py       # Conversor HTML -> Markdown
│   │   ├── youtube_parser.py     # Extrator de transcripts do YouTube
│   │   ├── youtube_text_cleaner.py # Removedor de timestamps do YouTube
│   │   ├── forum_scraper.py      # Crawler do fórum oficial (forums.larian.com)
│   │   ├── forum_text_cleaner.py # Conversor HTML -> Markdown dos tópicos do fórum
│   │   ├── steam_guide_scraper.py  # Crawler de guias da comunidade Steam
│   │   ├── steam_text_cleaner.py   # Conversor HTML -> Markdown dos guias da Steam
│   │   └── moxifer_dialog_index.py # Índice pesquisável de diálogos (dialog.moxifer.com)
│   └── _archive/reddit/          # Scripts e dados do Reddit (descontinuado)
├── BroPilot-SaveParser/          # Motor de extração do Save Game (.lsv)
│   ├── exporter/                 # Mod Lua (Script Extender) para exportação in-game
│   ├── scripts/                  # Scripts CLI de depuração/inspeção do save
│   └── src/bropilot/             # Parser Python nativo de LSF/LSPK e Osiris StorySave
└── README.md
```
