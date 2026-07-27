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
