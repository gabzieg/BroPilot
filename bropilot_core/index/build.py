"""Indexação da base de conhecimento — roda UMA vez, offline, jogo fechado.

Transforma os 119 .md de BroPilot-Knowledge/data/02_trusted/ (~1M tokens, que
NÃO cabem no contexto de um LLM local) num índice vetorial pesquisável. É o passo
que torna o RAG possível e, portanto, torna o setup local viável.

Custo de recurso: embeddings em lote são pesados, mas rodam uma vez e com o BG3
fechado — sem briga de VRAM. Reindexar só é necessário quando a base muda (novo
scraper rodou). Idempotência recomendada: pular chunks cujo doc-fonte não mudou
(hash), seguindo o espírito skip-if-exists dos scrapers do repo.

Escreve o índice em bropilot_core/index/store/ (fora do git — ver .gitignore).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Caminho padrão da camada trusted do ETL, relativo à raiz do repo.
TRUSTED_DIR = Path("BroPilot-Knowledge/data/02_trusted")
STORE_DIR = Path("bropilot_core/index/store")


@dataclass
class Chunk:
    """Um pedaço indexável de um documento da base.

    Metadados carregam de onde veio (source_file, source_type) para dois fins:
    citar a fonte na resposta, e permitir retrieval state-aware (filtrar por
    source_type='build' ou por classe no nome do arquivo).
    """
    text: str
    source_file: str          # ex.: "build_monk_openhand.md"
    source_type: str          # "wiki" | "youtube" | "forum" | "steam" | "build"
    chunk_index: int          # posição dentro do doc, para reconstruir contexto
    # embedding é preenchido depois, na fase de vetorização.


def classify_source(filename: str) -> str:
    """Deduz o tipo da fonte pelo nome do arquivo (convenção do ETL).

    forum_*.md -> "forum", youtube_*.md -> "youtube", steam_*.md -> "steam",
    build_*.md -> "build"; o resto (wiki) -> "wiki". Usado como metadado de
    filtro/boost no retriever.
    """
    raise NotImplementedError("scaffold")


def chunk_document(path: Path) -> Iterator[Chunk]:
    """Fatia UM documento markdown em chunks.

    Estratégia recomendada (a decidir na implementação): split por headers de
    markdown com overlap, respeitando um teto de tokens por chunk (~512). Cuidado
    com os outliers: youtube_manual.md tem 573KB (~140K tokens) — um único doc
    que precisa virar muitos chunks, não um só.
    """
    raise NotImplementedError("scaffold")


def build_index(
    trusted_dir: Path = TRUSTED_DIR,
    store_dir: Path = STORE_DIR,
    *,
    rebuild: bool = False,
) -> int:
    """Pipeline completo: lê .md -> chunk -> embed (via llm.OllamaProvider.embed)
    -> grava no LanceDB. Retorna o nº de chunks indexados.

    `rebuild=False` reaproveita embeddings de docs inalterados (por hash);
    `rebuild=True` recria o índice do zero. Deve imprimir progresso — indexar
    ~1M tokens localmente não é instantâneo, o usuário precisa ver que anda.
    """
    raise NotImplementedError("scaffold")


if __name__ == "__main__":
    # Ponto de entrada: `python -m bropilot_core.index.build [--rebuild]`
    raise NotImplementedError("scaffold")
