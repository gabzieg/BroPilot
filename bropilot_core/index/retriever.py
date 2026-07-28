"""Busca no índice vetorial — o coração do RAG state-aware.

O diferencial do BroPilot mora aqui. Um retriever burro embeda a pergunta e
devolve os k chunks mais próximos. Este devolve os k mais próximos PONDERADOS
pelo estado da party: se há um Monge Open Hand nível 5, `build_monk_openhand.md`
e os feats de nível 4-5 sobem no ranking mesmo que a pergunta não os mencione
literalmente. É o que transforma "chatbot de wiki" em "copiloto que enxerga o
jogo".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .build import STORE_DIR

if TYPE_CHECKING:
    from ..llm import LLMProvider
    from ..serialize import PartyStateSignals


@dataclass
class RetrievedChunk:
    """Resultado de busca: o texto + de onde veio + quão relevante."""
    text: str
    source_file: str
    score: float  # similaridade já ajustada pelos sinais da party


class Retriever:
    """Encapsula o vector store. Todo acesso ao LanceDB passa por aqui, para que
    trocar de store seja local a esta classe (ver __init__ do subpacote index).
    """

    def __init__(self, llm: "LLMProvider", store_dir: Path = STORE_DIR) -> None:
        """Guarda o provider (para embedar a query) e abre o índice em modo
        leitura. Falha cedo com mensagem útil se o índice não existe ("rode
        python -m bropilot_core.index.build primeiro").

        OBRIGATÓRIO ao implementar: chamar `assert_embedding_compatible(llm,
        store_dir)` (de .build) antes de servir qualquer query. Ela compara o
        modelo de embedding gravado no manifest do índice com o do provider
        que vetorizará a query, e falha alto se divergirem. Sem essa trava,
        indexar com um modelo e consultar com outro não dá erro — só devolve
        os chunks errados, que é o modo de falha mais caro do RAG porque
        parece que está funcionando.
        """
        raise NotImplementedError("scaffold")

    def search(
        self,
        query: str,
        *,
        signals: "PartyStateSignals | None" = None,
        k: int = 6,
    ) -> list[RetrievedChunk]:
        """Busca os k chunks mais relevantes para a query.

        Sem `signals`: kNN vetorial puro. Com `signals`: aplica boost/filtro
        pelas classes, subclasses e nível da party (state-aware). k pequeno de
        propósito — o prompt final tem que caber folgado no contexto local.
        """
        raise NotImplementedError("scaffold")

    def _apply_state_boost(
        self, hits: list[RetrievedChunk], signals: "PartyStateSignals"
    ) -> list[RetrievedChunk]:
        """Reordena os hits crus dando peso aos que casam com o estado da party.

        Onde a lógica de RPG vira código: mapear classe/subclasse -> arquivos e
        tópicos relevantes. Começar simples (match por nome de arquivo e
        source_type) e sofisticar depois.
        """
        raise NotImplementedError("scaffold")
