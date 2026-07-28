"""Indexação da base de conhecimento — roda UMA vez, offline, jogo fechado.

Transforma os 119 .md de BroPilot-Knowledge/data/02_trusted/ (~1M tokens, que
NÃO cabem no contexto de um LLM) num índice vetorial pesquisável. É o passo
que torna o RAG possível.

Custo de recurso: embeddings em lote são pesados, mas rodam uma vez. Reindexar
só é necessário quando a base muda (novo scraper rodou). Idempotência: pular
chunks cujo doc-fonte não mudou (hash), seguindo o espírito skip-if-exists dos
scrapers do repo.

Escreve o índice em bropilot_core/index/store/ (fora do git — ver .gitignore).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import lancedb
import pyarrow as pa
import tiktoken

from ..llm import OpenAIProvider

if TYPE_CHECKING:
    from ..llm import LLMProvider

# Caminho padrão da camada trusted do ETL, relativo à raiz do repo.
TRUSTED_DIR = Path("BroPilot-Knowledge/data/02_trusted")
STORE_DIR = Path("bropilot_core/index/store")

_TABLE_NAME = "chunks"
_MANIFEST_NAME = "manifest.json"

# cl100k_base é a encoding do text-embedding-3-small (ver llm.OpenAIProvider) —
# tem que ser a mesma usada aqui para o teto de tokens ter sentido.
_ENCODING = tiktoken.get_encoding("cl100k_base")
_MAX_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 64

_SOURCE_PREFIXES = ("forum", "youtube", "steam", "build")
_HEADER_RE = re.compile(r"^#{1,6}\s+.+$")


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
    vector: list[float] | None = None  # preenchido na fase de embedding


def classify_source(filename: str) -> str:
    """Deduz o tipo da fonte pelo nome do arquivo (convenção do ETL).

    forum_*.md -> "forum", youtube_*.md -> "youtube", steam_*.md -> "steam",
    build_*.md -> "build"; o resto (wiki) -> "wiki". Usado como metadado de
    filtro/boost no retriever.
    """
    prefix = filename.split("_", 1)[0]
    return prefix if prefix in _SOURCE_PREFIXES else "wiki"


def _count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def _clamp_tokens(text: str) -> str:
    """Trava final do teto de tokens. O orçamento em _split_oversized soma
    contagens de heading e corpo calculadas em separado; a tokenização real
    do texto concatenado pode variar por 1-2 tokens no limite (efeito de
    fronteira do BPE). Truncar aqui garante o teto de forma incondicional,
    em vez de perseguir esse epsilon com mais heurística."""
    tokens = _ENCODING.encode(text)
    if len(tokens) <= _MAX_CHUNK_TOKENS:
        return text
    return _ENCODING.decode(tokens[:_MAX_CHUNK_TOKENS])


def _split_into_sections(markdown: str) -> list[tuple[str | None, str]]:
    """Divide o markdown em (heading, body) a cada linha de header (qualquer
    nível). Texto antes do primeiro header vira uma seção com heading=None."""
    heading: str | None = None
    body_lines: list[str] = []
    sections: list[tuple[str | None, list[str]]] = []

    for line in markdown.splitlines():
        if _HEADER_RE.match(line):
            if heading is not None or body_lines:
                sections.append((heading, body_lines))
            heading = line.strip()
            body_lines = []
        else:
            body_lines.append(line)
    if heading is not None or body_lines:
        sections.append((heading, body_lines))

    return [(h, "\n".join(lines).strip()) for h, lines in sections]


def _window_tokens(text: str, size: int, overlap: int) -> Iterator[str]:
    """Fallback para texto sem quebra de parágrafo aproveitável (ex.:
    transcript bruto do youtube_manual.md): janela deslizante em tokens."""
    tokens = _ENCODING.encode(text)
    if not tokens:
        return
    step = max(size - overlap, 1)
    for start in range(0, len(tokens), step):
        yield _ENCODING.decode(tokens[start : start + size])
        if start + size >= len(tokens):
            break


def _split_oversized(heading: str | None, body: str) -> Iterator[str]:
    """Fatia o corpo de UMA seção grande demais para um chunk só.

    Empacota parágrafos (separados por linha em branco) até o teto de tokens,
    com overlap entre pedaços consecutivos. Um parágrafo que já excede o teto
    sozinho (sem quebras internas) cai para _window_tokens."""
    heading_tokens = _count_tokens(heading + "\n\n") if heading else 0
    budget = max(_MAX_CHUNK_TOKENS - heading_tokens, 128)

    paragraphs = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    buffer: list[str] = []

    def joined_tokens(paras: list[str]) -> int:
        # conta tokens do texto JÁ UNIDO — os separadores "\n\n" também
        # consomem tokens, então somar contagens por parágrafo isoladamente
        # subestima o total (é o que causava overflow do teto antes).
        return _count_tokens("\n\n".join(paras)) if paras else 0

    def carry_from(paras: list[str]) -> list[str]:
        # cauda de até _OVERLAP_TOKENS tokens do buffer fechado, pra dar
        # overlap com o próximo chunk sem herdar o tamanho dele por completo.
        tokens = _ENCODING.encode("\n\n".join(paras))[-_OVERLAP_TOKENS:]
        decoded = _ENCODING.decode(tokens).strip()
        return [decoded] if decoded else []

    for para in paragraphs:
        para_tokens = _count_tokens(para)

        if para_tokens > budget:
            if buffer:
                yield "\n\n".join(buffer)
            yield from _window_tokens(para, budget, _OVERLAP_TOKENS)
            buffer = []
            continue

        candidate = buffer + [para]
        if buffer and joined_tokens(candidate) > budget:
            yield "\n\n".join(buffer)
            carry = carry_from(buffer)
            # só carrega overlap se ele + o parágrafo novo ainda couber no
            # teto; senão abre mão do overlap nesta transição (correção do
            # teto tem prioridade sobre overlap).
            candidate = carry + [para] if joined_tokens(carry + [para]) <= budget else [para]
        buffer = candidate

    if buffer:
        yield "\n\n".join(buffer)


def chunk_document(path: Path) -> Iterator[Chunk]:
    """Fatia UM documento markdown em chunks.

    Split header-aware: cada seção (delimitada por um header de qualquer
    nível) que já cabe no teto de ~512 tokens vira um chunk só, prefixada pelo
    seu header para contexto. Seções maiores (outliers como youtube_manual.md,
    ~140K tokens) são fatiadas por parágrafo com overlap via _split_oversized,
    sem estourar memória — cada chunk é gerado e consumido um a um.
    """
    markdown = path.read_text(encoding="utf-8")
    source_file = path.name
    source_type = classify_source(source_file)
    index = 0

    for heading, body in _split_into_sections(markdown):
        if not body:
            continue

        prefixed = f"{heading}\n\n{body}" if heading else body
        if _count_tokens(prefixed) <= _MAX_CHUNK_TOKENS:
            yield Chunk(_clamp_tokens(prefixed), source_file, source_type, index)
            index += 1
            continue

        for piece in _split_oversized(heading, body):
            text = f"{heading}\n\n{piece}" if heading else piece
            yield Chunk(_clamp_tokens(text), source_file, source_type, index)
            index += 1


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_manifest(store_dir: Path) -> dict[str, str]:
    manifest_path = store_dir / _MANIFEST_NAME
    if not manifest_path.exists():
        return {}
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _save_manifest(store_dir: Path, manifest: dict[str, str]) -> None:
    (store_dir / _MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def _table_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            pa.field("text", pa.string()),
            pa.field("source_file", pa.string()),
            pa.field("source_type", pa.string()),
            pa.field("chunk_index", pa.int64()),
            pa.field("vector", pa.list_(pa.float32(), dim)),
        ]
    )


def _escape_literal(value: str) -> str:
    return value.replace("'", "''")


def build_index(
    trusted_dir: Path = TRUSTED_DIR,
    store_dir: Path = STORE_DIR,
    *,
    rebuild: bool = False,
    llm: "LLMProvider | None" = None,
) -> int:
    """Pipeline completo: lê .md -> chunk -> embed (via OpenAIProvider.embed)
    -> grava no LanceDB em store_dir. Retorna o nº de chunks indexados NESTA
    execução (documentos inalterados e pulados não contam).

    `rebuild=True` apaga a tabela e reindexa tudo do zero — caminho principal,
    sólido para rodar sempre que a KB crescer. `rebuild=False` (default) é
    incremental por hash de arquivo-fonte: só reprocessa docs novos/mudados,
    e remove do índice os que saíram de trusted_dir.

    Segurança do incremental: o manifest (hash por arquivo) só é gravado em
    disco DEPOIS que as linhas daquele arquivo já foram escritas no LanceDB.
    Se o processo cair no meio, no pior caso um arquivo fica sem reindexar
    até a próxima execução — nunca um índice com metade de um doc gravado e
    o manifest já dizendo que ele está atualizado.
    """
    provider = llm if llm is not None else OpenAIProvider()
    store_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(store_dir))

    existing_tables = set(db.list_tables().tables)

    if rebuild and _TABLE_NAME in existing_tables:
        db.drop_table(_TABLE_NAME)

    manifest = {} if rebuild else _load_manifest(store_dir)
    table = None
    if not rebuild and _TABLE_NAME in existing_tables:
        table = db.open_table(_TABLE_NAME)

    source_files = sorted(trusted_dir.glob("*.md"))
    current_names = {p.name for p in source_files}

    if table is not None:
        for stale_name in sorted(set(manifest) - current_names):
            table.delete(f"source_file = '{_escape_literal(stale_name)}'")
            manifest.pop(stale_name, None)
            print(f"removido do índice (arquivo não existe mais): {stale_name}")
        if set(manifest) - current_names:
            _save_manifest(store_dir, manifest)

    total = len(source_files)
    indexed_chunks = 0

    for i, path in enumerate(source_files, start=1):
        file_hash = _file_hash(path)
        if not rebuild and manifest.get(path.name) == file_hash:
            print(f"[{i}/{total}] {path.name}: sem mudanças, pulando.")
            continue

        chunks = list(chunk_document(path))
        if not chunks:
            manifest[path.name] = file_hash
            _save_manifest(store_dir, manifest)
            print(f"[{i}/{total}] {path.name}: vazio, nada a indexar.")
            continue

        vectors = provider.embed([c.text for c in chunks])
        records = [
            {
                "text": c.text,
                "source_file": c.source_file,
                "source_type": c.source_type,
                "chunk_index": c.chunk_index,
                "vector": vector,
            }
            for c, vector in zip(chunks, vectors)
        ]

        if table is None:
            table = db.create_table(_TABLE_NAME, schema=_table_schema(len(vectors[0])))
        elif path.name in manifest:
            # arquivo já indexado antes e mudou: descarta as linhas antigas
            # dele antes de reinserir, senão ficam duplicadas/obsoletas.
            table.delete(f"source_file = '{_escape_literal(path.name)}'")

        table.add(records)
        manifest[path.name] = file_hash
        _save_manifest(store_dir, manifest)

        indexed_chunks += len(records)
        print(f"[{i}/{total}] {path.name}: {len(records)} chunks indexados.")

    total_rows = table.count_rows() if table is not None else 0
    print(
        f"Concluído: {indexed_chunks} chunks indexados nesta execução "
        f"({total_rows} chunks no total do índice)."
    )
    return indexed_chunks


if __name__ == "__main__":
    # Ponto de entrada: `python -m bropilot_core.index.build [--rebuild]`
    import argparse

    parser = argparse.ArgumentParser(
        description="Indexa BroPilot-Knowledge/data/02_trusted/ em LanceDB."
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Apaga o índice existente e reindexa tudo do zero.",
    )
    args = parser.parse_args()

    build_index(rebuild=args.rebuild)
