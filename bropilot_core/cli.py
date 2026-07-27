"""CLI de teste — a superfície onde se valida a integração antes de qualquer UI.

Substitui, na prática, o papel do bropilot.py da raiz (que fazia context stuffing
no Gemini). Aqui o loop é: lê o save mais recente -> pergunta do jogador ->
Orchestrator.ask() -> imprime. Terminal primeiro; a UI Electron é a última milha,
depois que o cérebro estiver provado aqui.

Uso pretendido:
    python -m bropilot_core.cli [--dump CAMINHO_DO_bropilot_inventory.json]

O --dump permite testar no Mac com um snapshot salvo do mod, sem o jogo aberto
(fixture) — contornando a dependência de plataforma (mod Lua só roda no Windows).
"""

from __future__ import annotations

import sys
from pathlib import Path


def _bootstrap_saveparser_path() -> None:
    """Adiciona BroPilot-SaveParser/src ao sys.path.

    Gambiarra consciente enquanto não há packaging unificado: os subsistemas do
    repo não se importam entre si e cada um tem seu venv. O bropilot_core é o
    primeiro a cruzar essa fronteira, então precisa localizar o pacote do parser.
    Ver README do bropilot_core para o plano de resolver isso via editable install.
    """
    raise NotImplementedError("scaffold")


def main(argv: list[str] | None = None) -> int:
    """Loop do REPL. Passos:
    1. bootstrap do path + health_check do Ollama (falha cedo se offline).
    2. carrega o save mais recente (ou avisa que não achou).
    3. constrói o Orchestrator default.
    4. loop: pergunta -> ask() -> imprime resposta + fontes.
    Retorna exit code.
    """
    raise NotImplementedError("scaffold")


if __name__ == "__main__":
    sys.exit(main())
