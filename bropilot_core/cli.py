"""CLI de teste — a superfície onde se valida a integração antes de qualquer UI.

Substitui, na prática, o papel do bropilot.py da raiz (que fazia context stuffing
no Gemini). Aqui o loop é: lê o save mais recente -> pergunta do jogador ->
Orchestrator.ask() -> imprime. Terminal primeiro; a UI Electron é a última milha,
depois que o cérebro estiver provado aqui.

Uso pretendido:
    python -m bropilot_core.cli [--dump CAMINHO_DO_bropilot_inventory.json]

O --dump permite testar no Mac com um snapshot salvo do mod, sem o jogo aberto
(fixture) — contornando a dependência de plataforma (mod Lua só roda no Windows).

Back-end de LLM selecionável via env var BROPILOT_LLM=ollama|openai (default
ollama) — ver `llm.create_provider()`. A escolha só afeta generate(); os
embeddings do RAG continuam vindo do Ollama/bge-m3 independente do
back-end de geração (ver DECISION.md).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .llm import create_provider
from .orchestrator import build_default_orchestrator

_SAIR = {"sair", "exit", "quit", ":q"}


def _bootstrap_saveparser_path() -> None:
    """Adiciona BroPilot-SaveParser/src ao sys.path.

    Gambiarra consciente enquanto não há packaging unificado: os subsistemas do
    repo não se importam entre si e cada um tem seu venv. O bropilot_core é o
    primeiro a cruzar essa fronteira, então precisa localizar o pacote do parser.
    Ver README do bropilot_core para o plano de resolver isso via editable install.
    """
    raise NotImplementedError("entra quando o save for plugado")


def main(argv: list[str] | None = None) -> int:
    """Loop do REPL. Passos:
    1. health_check do provider selecionado (BROPILOT_LLM; falha cedo se
       offline/sem API key).
    2. constrói o Orchestrator default.
    3. loop: pergunta -> ask() -> imprime resposta + fontes.

    Ainda SEM save: o save entra no passo seguinte do roadmap; por isso
    _bootstrap_saveparser_path() não é chamado e --dump fica inerte.
    Retorna exit code.
    """
    parser = argparse.ArgumentParser(
        prog="python -m bropilot_core.cli",
        description="REPL do BroPilot — perguntas sobre BG3 contra a base indexada.",
    )
    parser.add_argument(
        "--dump",
        metavar="CAMINHO",
        help="snapshot bropilot_inventory.json do mod (ainda inerte: o save "
             "entra na próxima etapa).",
    )
    parser.add_argument(
        "--store", metavar="CAMINHO", help="diretório do índice (default: o do build)."
    )
    parser.add_argument(
        "-k", type=int, default=6, help="quantos chunks recuperar por pergunta."
    )
    args = parser.parse_args(argv)

    if args.dump:
        print("aviso: --dump ainda não faz nada; o save entra na próxima etapa.\n")

    # Falhar cedo e com mensagem acionável: Ollama fora do ar, modelo não
    # baixado ou índice inexistente são condições que o usuário resolve — não
    # merecem stack trace, e muito menos estourar no meio da primeira pergunta.
    try:
        provider = create_provider()
        provider.health_check()
        orchestrator = build_default_orchestrator(
            llm=provider, store_dir=Path(args.store) if args.store else None
        )
    except RuntimeError as exc:
        print(f"erro: {exc}", file=sys.stderr)
        return 1

    orchestrator.k = args.k

    print("BroPilot — modo sem save (só base de conhecimento).")
    print("Pergunte à vontade. 'sair', Ctrl+C ou Ctrl+D encerram.\n")

    while True:
        try:
            question = input("você > ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\naté a próxima!")
            return 0

        if not question:
            continue
        if question.lower() in _SAIR:
            print("até a próxima!")
            return 0

        try:
            answer = orchestrator.ask(question)
        except RuntimeError as exc:
            print(f"erro: {exc}\n", file=sys.stderr)
            continue
        except KeyboardInterrupt:
            print("\n(geração interrompida)\n")
            continue

        print(f"\nbropilot > {answer.text}\n")
        # As fontes SEMPRE acompanham a resposta: é como se verifica se o RAG
        # puxou o material certo, em vez de o modelo estar inventando.
        print(f"  fontes: {', '.join(answer.sources) or '(nenhuma)'}\n")


if __name__ == "__main__":
    sys.exit(main())
