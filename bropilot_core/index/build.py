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
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Iterator

import lancedb
import pyarrow as pa
import tiktoken

from ..llm import create_provider

if TYPE_CHECKING:
    from ..llm import LLMProvider

# Caminho padrão da camada trusted do ETL, relativo à raiz do repo.
TRUSTED_DIR = Path("BroPilot-Knowledge/data/02_trusted")
STORE_DIR = Path("bropilot_core/index/store")

_TABLE_NAME = "chunks"
_MANIFEST_NAME = "manifest.json"

# cl100k_base é a encoding exata do text-embedding-3-small; para o bge-m3
# (tokenizer XLM-RoBERTa) é aproximação, usada como MEDIDA DE TAMANHO de chunk,
# não como contrato com o modelo. Serve para os dois porque 512 tokens aqui fica
# folgado sob o limite de contexto de ambos — o que importa é o chunk não passar
# do que o modelo aceita, e a margem cobre a diferença de tokenizer.
_ENCODING = tiktoken.get_encoding("cl100k_base")
_MAX_CHUNK_TOKENS = 512
_OVERLAP_TOKENS = 64

_SOURCE_PREFIXES = ("forum", "youtube", "steam", "build")
_HEADER_RE = re.compile(r"^#{1,6}\s+.+$")

# --- Índice FTS (BM25), o segundo índice desta base -------------------------
#
# Ver bropilot_core/DECISION_hybrid_search.md: a similaridade densa não
# discrimina em corpus mono-domínio (tudo é BG3), e o sinal que falta é
# LEXICAL — "Superiority Dice" como string literal. O FTS nativo do LanceDB
# (lance-index/BM25) fornece esse sinal.
#
# Ele é criado sobre a coluna `text` DENTRO de build_index, nunca em passo
# separado: um índice vetorial sem FTS faria a híbrida degradar em silêncio
# para vetorial pura, que é o modo de falha que esta decisão existe para
# evitar. O manifest registra a existência (ver _FTS_MANIFEST) para que o
# Retriever detecte a ausência e falhe cedo, em vez de servir busca pior sem
# avisar.
_FTS_COLUMN = "text"
# Inglês porque o corpus é ~97% inglês (medido em 28/07: 146 de 150 arquivos).
# Stemming + stop words em inglês fazem "dice"/"dices" e "Battle Master"
# casarem; um tokenizer neutro perderia isso.
_FTS_LANGUAGE = "English"
# Versão do CONFIG do FTS acima. Subir quando o tokenizer/idioma mudar: é o
# gancho para detectar "índice FTS existe, mas foi construído com outra
# configuração" sem depender de inspecionar o índice por dentro.
_FTS_VERSION = 1
_FTS_MANIFEST = {
    "column": _FTS_COLUMN,
    "language": _FTS_LANGUAGE,
    "version": _FTS_VERSION,
}


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


def _load_manifest(store_dir: Path) -> dict:
    """Manifest do índice: identidade do embedding + hash por arquivo-fonte.

    Formato: {"embed_model": str|None, "embed_dim": int|None,
              "fts": {"column": str, "language": str, "version": int}|None,
              "files": {nome_do_arquivo: sha256}}.

    embed_model/embed_dim existem para tornar DETECTÁVEL a incompatibilidade
    de espaço vetorial. A dimensão diverge por acidente em alguns pares de
    modelos (bge-m3=1024 vs text-embedding-3-small=1536, que o LanceDB
    rejeitaria por schema), mas dois modelos de mesma dimensão passariam
    silenciosamente — a checagem explícita não depende dessa sorte.

    `fts` existe pela MESMA razão, um nível acima: um índice construído antes
    da busca híbrida tem vetores válidos e nenhum índice FTS. Sem registro,
    a híbrida rodaria com o lado lexical vazio e devolveria silenciosamente o
    ranking vetorial puro — o problema que a decisão existe para consertar.
    None = índice pré-híbrida, precisa de rebuild.
    """
    manifest_path = store_dir / _MANIFEST_NAME
    if not manifest_path.exists():
        return {"embed_model": None, "embed_dim": None, "fts": None, "files": {}}

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.setdefault("embed_model", None)
    manifest.setdefault("embed_dim", None)
    manifest.setdefault("fts", None)
    manifest.setdefault("files", {})
    return manifest


def _save_manifest(store_dir: Path, manifest: dict) -> None:
    (store_dir / _MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def index_embed_model(store_dir: Path = STORE_DIR) -> str | None:
    """Com que modelo de embedding o índice em store_dir foi construído.

    None quando não há índice/manifest ainda."""
    return _load_manifest(store_dir).get("embed_model")


def assert_embedding_compatible(
    provider: "LLMProvider", store_dir: Path = STORE_DIR
) -> None:
    """Falha ALTO se o índice foi construído com um modelo de embedding
    diferente do que `provider` usa para vetorizar a query.

    Mora aqui, e não no Retriever, porque quem define o formato do manifest é
    este módulo — o retriever só chama isto no __init__. É a trava que
    transforma o pior modo de falha do RAG (busca silenciosamente errada,
    porque os dois espaços vetoriais não se correspondem) em erro imediato e
    acionável.
    """
    indexed_model = index_embed_model(store_dir)
    if indexed_model is None:
        return  # sem índice ainda; quem abre o índice trata a ausência

    query_model = provider.embed_model
    if indexed_model != query_model:
        raise RuntimeError(
            f"Índice em {store_dir} foi construído com embeddings de "
            f"'{indexed_model}', mas a query seria vetorizada com "
            f"'{query_model}'. Os dois espaços vetoriais não se correspondem "
            "e a busca devolveria resultados errados sem acusar erro.\n"
            "Reconstrua o índice com o modelo atual:\n"
            "  python -m bropilot_core.index.build --rebuild"
        )


def index_fts_config(store_dir: Path = STORE_DIR) -> dict | None:
    """Configuração do índice FTS registrada no manifest, ou None se o índice
    foi construído antes da busca híbrida (ou sem FTS)."""
    return _load_manifest(store_dir).get("fts")


def assert_fts_available(table, store_dir: Path = STORE_DIR) -> None:
    """Falha ALTO se o índice vetorial existe mas o FTS não.

    Gêmea de `assert_embedding_compatible`, e pela mesma lógica: o LanceDB
    aceita `query_type="hybrid"` numa tabela sem índice FTS — o lado lexical
    apenas volta vazio e o reranker devolve o ranking vetorial puro. Ou seja,
    a busca híbrida "funcionaria", só que sem híbrida nenhuma, e nada no
    resultado denunciaria isso. Um índice antigo (pré-decisão) cairia
    exatamente nesse buraco.

    Confere as DUAS pontas — o registro no manifest e o índice de verdade na
    tabela — porque cada uma pega uma falha diferente: manifest sem `fts`
    revela índice antigo; tabela sem índice FTS revela manifest que ficou
    para trás (store copiado pela metade, índice removido à mão).
    """
    if index_fts_config(store_dir) is None:
        raise RuntimeError(
            f"O índice em {store_dir} não registra um índice FTS (busca "
            "lexical/BM25) no manifest — provavelmente foi construído antes "
            "da busca híbrida. A híbrida rodaria só com o lado vetorial e "
            "devolveria resultados piores sem acusar erro.\n"
            "Reconstrua o índice:\n"
            "  python -m bropilot_core.index.build --rebuild"
        )

    colunas_fts = {
        coluna
        for indice in table.list_indices()
        if str(indice.index_type).upper().endswith("FTS")
        for coluna in indice.columns
    }
    if _FTS_COLUMN not in colunas_fts:
        raise RuntimeError(
            f"O manifest de {store_dir} diz que existe um índice FTS sobre "
            f"'{_FTS_COLUMN}', mas a tabela '{_TABLE_NAME}' não tem esse "
            "índice. O manifest e o índice estão fora de sincronia.\n"
            "Reconstrua o índice:\n"
            "  python -m bropilot_core.index.build --rebuild"
        )


def ensure_fts_index(table) -> dict:
    """Cria o índice FTS sobre a coluna `text` e incorpora as linhas escritas
    depois da última criação.

    Chamar SEMPRE no fim do build (rebuild e incremental) é o que mantém FTS e
    vetores em sincronia sem um passo separado que possa ser esquecido.

    Duas armadilhas medidas neste setup, e a razão de esta função existir em
    vez de um `create_fts_index` solto:

    1. Criar o índice ANTES de escrever as linhas indexa ZERO linhas. O
       índice existe, `list_indices()` o mostra, a busca FTS até devolve
       resultados — por um caminho de varredura sobre as linhas não indexadas,
       com pontuação BM25 diferente da do índice. Medido na base real: com as
       4409 linhas fora do índice, a wiki sumiu do top-6 de TODOS os pesos e o
       recall de Monge caiu de 4/5 para 1/5. Ou seja, falha silenciosa que
       parece funcionar — daí a checagem explícita de `num_unindexed_rows`.
    2. Todo `table.add` posterior cai num delta não indexado. `optimize()` é
       o que o incorpora ao índice.

    Devolve o descritor para o manifest. O CHAMADOR só deve gravá-lo depois
    desta função retornar: manifest que promete um FTS inexistente é pior que
    manifest desatualizado, porque a checagem de falha-cedo passaria.
    """
    colunas_fts = {
        coluna
        for indice in table.list_indices()
        if str(indice.index_type).upper().endswith("FTS")
        for coluna in indice.columns
    }
    if _FTS_COLUMN not in colunas_fts:
        table.create_fts_index(
            _FTS_COLUMN,
            use_tantivy=False,
            language=_FTS_LANGUAGE,
            stem=True,              # "dice"/"dices", "maneuver"/"maneuvers"
            remove_stop_words=True,
            lower_case=True,
            ascii_folding=True,
            replace=True,
        )
        print(f"índice FTS criado sobre '{_FTS_COLUMN}' (idioma {_FTS_LANGUAGE}).")

    # Folda o delta (linhas gravadas depois da criação do índice) para dentro
    # dele. Barato quando não há delta.
    table.optimize()

    restantes = table.index_stats("text_idx").num_unindexed_rows
    if restantes:
        raise RuntimeError(
            f"O índice FTS ficou com {restantes} linha(s) fora dele mesmo "
            "depois de optimize(). A busca híbrida pontuaria essas linhas por "
            "um caminho diferente do resto da base.\nReconstrua do zero:\n"
            "  python -m bropilot_core.index.build --rebuild"
        )
    return dict(_FTS_MANIFEST)


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
    include_source_types: set[str] | None = None,
) -> int:
    """Pipeline completo: lê .md -> chunk -> embed (via LLMProvider.embed)
    -> grava no LanceDB em store_dir. Retorna o nº de chunks indexados NESTA
    execução (documentos inalterados e pulados não contam).

    O provider vem de create_provider() quando não injetado — ou seja, respeita
    BROPILOT_LLM (default ollama). Indexar e consultar PRECISAM usar o mesmo
    back-end de embedding; hardcodar um provider aqui era justamente o jeito de
    construir o índice com um modelo e consultá-lo com outro.

    `rebuild=True` apaga a tabela e reindexa tudo do zero — caminho principal,
    sólido para rodar sempre que a KB crescer. `rebuild=False` (default) é
    incremental por hash de arquivo-fonte: só reprocessa docs novos/mudados,
    e remove do índice os que saíram de trusted_dir. O incremental é RECUSADO
    se o modelo de embedding mudou desde a construção do índice — misturar dois
    espaços vetoriais na mesma tabela é pior que reindexar tudo.

    `include_source_types` restringe o corpus a certos source_type (ver
    classify_source), ex.: {"wiki", "build"} para indexar só material curado e
    denso, deixando transcrição de fora. None = tudo, comportamento inalterado.
    O filtro passa a fazer parte da identidade do índice (gravado no manifest),
    pela mesma razão do embed_model: rodar incremental depois sem o filtro
    mudaria o corpus em silêncio.

    Segurança do incremental: o manifest (hash por arquivo) só é gravado em
    disco DEPOIS que as linhas daquele arquivo já foram escritas no LanceDB.
    Se o processo cair no meio, no pior caso um arquivo fica sem reindexar
    até a próxima execução — nunca um índice com metade de um doc gravado e
    o manifest já dizendo que ele está atualizado.
    """
    provider = llm if llm is not None else create_provider()
    embed_model = provider.embed_model
    tipos = sorted(include_source_types) if include_source_types else None
    store_dir.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(store_dir))

    existing_tables = set(db.list_tables().tables)

    manifest = _load_manifest(store_dir)
    if not rebuild and manifest["embed_model"] not in (None, embed_model):
        raise RuntimeError(
            f"Índice em {store_dir} foi construído com embeddings de "
            f"'{manifest['embed_model']}', mas o provider atual usa "
            f"'{embed_model}'. Indexar por cima misturaria dois espaços "
            "vetoriais na mesma tabela e a busca ficaria silenciosamente "
            "errada.\nReconstrua do zero:\n"
            "  python -m bropilot_core.index.build --rebuild"
        )

    if not rebuild and manifest.get("source_types", tipos) != tipos:
        raise RuntimeError(
            f"Índice em {store_dir} foi construído com source_types="
            f"{manifest.get('source_types')}, mas esta execução pede {tipos}. "
            "Indexar por cima misturaria dois corpora diferentes na mesma "
            "tabela.\nReconstrua do zero:\n"
            "  python -m bropilot_core.index.build --rebuild"
        )

    if rebuild:
        if _TABLE_NAME in existing_tables:
            db.drop_table(_TABLE_NAME)
        manifest = {
            "embed_model": embed_model, "embed_dim": None, "fts": None, "files": {}
        }

    manifest["embed_model"] = embed_model
    manifest["source_types"] = tipos
    files = manifest["files"]

    table = None
    if not rebuild and _TABLE_NAME in existing_tables:
        table = db.open_table(_TABLE_NAME)
        if not files:
            # Tabela existe mas o manifest não sabe de nenhum arquivo (manifest
            # apagado/corrompido). Seguir incremental reindexaria tudo SEM
            # apagar as linhas antigas — índice duplicado. Reconstruir é a
            # única saída consistente.
            raise RuntimeError(
                f"O índice em {store_dir} tem uma tabela '{_TABLE_NAME}', mas o "
                "manifest não registra nenhum arquivo — não dá para saber o que "
                "já está indexado e o incremental duplicaria tudo.\n"
                "Reconstrua do zero:\n"
                "  python -m bropilot_core.index.build --rebuild"
            )

    source_files = sorted(trusted_dir.glob("*.md"))
    if include_source_types is not None:
        # Mesma classify_source do resto do módulo — uma lógica de
        # classificação só, senão o filtro e o metadado gravado divergem.
        source_files = [
            p for p in source_files
            if classify_source(p.name) in include_source_types
        ]
    current_names = {p.name for p in source_files}

    if table is not None:
        stale = sorted(set(files) - current_names)
        for stale_name in stale:
            table.delete(f"source_file = '{_escape_literal(stale_name)}'")
            files.pop(stale_name, None)
            print(f"removido do índice (arquivo não existe mais): {stale_name}")
        if stale:
            _save_manifest(store_dir, manifest)

    total = len(source_files)
    indexed_chunks = 0

    for i, path in enumerate(source_files, start=1):
        file_hash = _file_hash(path)
        if not rebuild and files.get(path.name) == file_hash:
            print(f"[{i}/{total}] {path.name}: sem mudanças, pulando.")
            continue

        chunks = list(chunk_document(path))
        if not chunks:
            files[path.name] = file_hash
            _save_manifest(store_dir, manifest)
            print(f"[{i}/{total}] {path.name}: vazio, nada a indexar.")
            continue

        vectors = provider.embed([c.text for c in chunks])
        dim = len(vectors[0])
        if manifest["embed_dim"] is None:
            manifest["embed_dim"] = dim
        elif manifest["embed_dim"] != dim:
            raise RuntimeError(
                f"'{embed_model}' devolveu vetores de dimensão {dim}, mas o "
                f"índice foi construído com dimensão {manifest['embed_dim']}. "
                "Reconstrua com --rebuild."
            )

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
            table = db.create_table(_TABLE_NAME, schema=_table_schema(dim))
        elif path.name in files:
            # arquivo já indexado antes e mudou: descarta as linhas antigas
            # dele antes de reinserir, senão ficam duplicadas/obsoletas.
            table.delete(f"source_file = '{_escape_literal(path.name)}'")

        table.add(records)
        files[path.name] = file_hash
        _save_manifest(store_dir, manifest)

        indexed_chunks += len(records)
        print(f"[{i}/{total}] {path.name}: {len(records)} chunks indexados.")

    if table is not None:
        # DEPOIS de todas as escritas, nunca antes: criar o índice FTS numa
        # tabela vazia indexa zero linhas (ver ensure_fts_index). É também o
        # que incorpora, no incremental, as linhas deste build.
        #
        # A ordem também é o que preserva a garantia do manifest: `fts` só é
        # gravado depois de o índice existir de verdade e cobrir tudo. Uma
        # queda no meio do laço deixa o manifest SEM `fts` — o Retriever
        # recusa a busca e pede rebuild, em vez de servir híbrida meio-boca.
        manifest["fts"] = ensure_fts_index(table)
        _save_manifest(store_dir, manifest)

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
    parser.add_argument(
        "--store",
        metavar="CAMINHO",
        help=f"Diretório do índice (default: {STORE_DIR}). Use um diretório "
             "separado para experimentos, para não destruir o índice atual.",
    )
    parser.add_argument(
        "--only-types",
        metavar="LISTA",
        help="Indexa só estes source_type, separados por vírgula "
             f"(ex.: wiki,build). Válidos: {','.join(sorted(_SOURCE_PREFIXES + ('wiki',)))}.",
    )
    args = parser.parse_args()

    tipos = None
    if args.only_types:
        tipos = {t.strip() for t in args.only_types.split(",") if t.strip()}
        validos = set(_SOURCE_PREFIXES) | {"wiki"}
        if not tipos <= validos:
            sys.exit(
                f"erro: source_type inválido: {', '.join(sorted(tipos - validos))}. "
                f"Válidos: {', '.join(sorted(validos))}"
            )

    # As falhas previstas aqui (índice incompatível, Ollama fora do ar, modelo
    # não baixado) são condições que o usuário resolve — merecem a mensagem, não
    # um traceback.
    try:
        build_index(
            store_dir=Path(args.store) if args.store else STORE_DIR,
            rebuild=args.rebuild,
            include_source_types=tipos,
        )
    except RuntimeError as exc:
        sys.exit(f"\nerro: {exc}")
