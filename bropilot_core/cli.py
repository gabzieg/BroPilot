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
    raiz = Path(__file__).resolve().parent.parent / "BroPilot-SaveParser" / "src"
    if raiz.is_dir() and str(raiz) not in sys.path:
        sys.path.insert(0, str(raiz))


def carregar_save(dump: str | None = None):
    """Save mais recente + snapshot do mod, se houver. Devolve (ctx, aviso).

    Nunca levanta: save é dado OPCIONAL. Qualquer falha — parser ausente,
    caminho inexistente, .lsv corrompido — vira aviso e o CLI segue no modo
    sem-save. Travar a experiência por falta de dado opcional seria pior que
    responder só com a base de conhecimento.
    """
    _bootstrap_saveparser_path()
    try:
        from bropilot.models import SaveContext
        from bropilot.save import SaveGame, default_save_root, latest_save
    except ImportError as exc:
        return None, f"SaveParser indisponível ({exc}) — seguindo sem save."

    try:
        caminho = latest_save()
        if caminho is None:
            return None, (
                f"Nenhum save encontrado em {default_save_root()} — "
                "seguindo sem save."
            )
        ctx = SaveContext(SaveGame(caminho), inventory_dump=dump)
        ctx.party  # força a leitura agora, para falhar aqui e não na 1a pergunta
        return ctx, f"Save carregado: {caminho.name}"
    except Exception as exc:  # noqa: BLE001 — save é opcional, nada aqui é fatal
        return None, f"Falha ao ler o save ({type(exc).__name__}: {exc}) — seguindo sem save."


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
        help="snapshot bropilot_inventory.json do mod (Windows). Sem ele, o "
             "save em disco só dá nível/raça/classe.",
    )
    parser.add_argument(
        "--sem-save",
        action="store_true",
        help="ignora o savegame e responde só com a base de conhecimento.",
    )
    parser.add_argument(
        "--store", metavar="CAMINHO", help="diretório do índice (default: o do build)."
    )
    parser.add_argument(
        "-k", type=int, default=6, help="quantos chunks recuperar por pergunta."
    )
    args = parser.parse_args(argv)

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

    ctx = None
    if args.sem_save:
        print("BroPilot — modo sem save (--sem-save).")
    else:
        ctx, aviso = carregar_save(args.dump)
        print(f"BroPilot — {aviso}")
        if ctx is not None:
            from .serialize import serialize_party
            # Mostrar a ficha no boot deixa explícito o que o modelo vai ver,
            # incluindo o aviso de fidelidade degradada quando não há mod.
            print(serialize_party(ctx))

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

        # ask_stream() só monta o prompt (retrieval -> boost -> dedup ->
        # orçamento) — a geração em si só começa quando `streamed.chunks` é
        # iterado logo abaixo, então um Ctrl+C aqui interrompe antes da parte
        # lenta (~60s) sequer começar.
        try:
            streamed = orchestrator.ask_stream(question, ctx)
        except RuntimeError as exc:
            print(f"erro: {exc}\n", file=sys.stderr)
            continue
        except KeyboardInterrupt:
            print("\n(geração interrompida)\n")
            continue

        # Escreve cada pedaço com flush imediato, sem quebra de linha entre
        # eles: é isto que faz a resposta aparecer se formando no terminal em
        # vez de tudo de uma vez ao final (a latência TOTAL não muda — a
        # PERCEBIDA sim, e é ela que decide se dá pra usar isto jogando).
        sys.stdout.write("\nbropilot > ")
        sys.stdout.flush()
        try:
            for pedaco in streamed.chunks:
                sys.stdout.write(pedaco)
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\n\n(geração interrompida)\n")
            continue
        except RuntimeError as exc:
            print(f"\nerro: {exc}\n", file=sys.stderr)
            continue

        print("\n")
        # As fontes SEMPRE acompanham a resposta — só que agora depois do
        # stream inteiro, nunca no meio: é como se verifica se o RAG puxou o
        # material certo, em vez de o modelo estar inventando.
        print(f"  fontes: {', '.join(streamed.sources) or '(nenhuma)'}\n")


if __name__ == "__main__":
    sys.exit(main())
