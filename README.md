# 🎲 BroPilot - Baldur's Gate 3 Min-Maxing Assistant

O **BroPilot** é um assistente virtual (Copilot) desenvolvido para rodar localmente e auxiliar jogadores de Baldur's Gate 3 com decisões de min-maxing, otimização de *builds*, economia de ações (*Action Economy*) e escolhas de equipamentos.

## 🎯 Objetivo (MVP)
Um motor que é acionado via atalho (ex: `Ctrl + 0`) durante a gameplay. O gatilho força um Quicksave (`F5`), o BroPilot descompacta o arquivo `.lsv`, lê o estado atual da *party* (níveis, itens, atributos) e cruza isso com uma base de conhecimento (RAG) para sugerir a melhor jogada, item de mercador ou nó de diálogo.

## 🏗️ Arquitetura do Projeto

O projeto é dividido em dois grandes motores:
1. **Pipeline de Dados (ETL/Knowledge Base):** Scripts em Python que fazem scraping e limpeza da BG3 Wiki e fóruns focados em *builds*. Usa a arquitetura Medallion:
   - `01_raw`: Arquivos HTML brutos.
   - `02_trusted`: Arquivos convertidos para Markdown (textos limpos e mecânicas estruturadas).
   - `03_refined`: Matrizes de itens e mercadores (WIP).
2. **Cérebro da IA (Save Parser + LLM):** Motor que extrai o JSON do *save* do jogo e alimenta um LLM com os dados estruturados para devolver respostas rápidas e precisas no terminal.

## 📁 Estrutura de Pastas
```text
BroPilot/
├── bropilot.py                   # Orquestrador da IA (LLM Core)
├── BroPilot-Knowledge/           # Base de dados (RAG)
│   ├── data/
│   │   ├── 01_raw/               # Dumps de HTML e Wikis
│   │   ├── 02_trusted/           # Textos curados em Markdown
│   │   └── 03_refined/           # Matrizes e JSONs de itens
│   ├── scripts/
│   │   ├── wiki_crawler.py       # Aranha para baixar páginas da Wiki
│   │   └── text_cleaner.py       # Limpa o HTML e converte para Markdown
└── README.md