"""Extrai o glossário de nomes próprios canônicos das wikis de 02_trusted.

Por que existe: a transcrição do YouTube destrói exatamente os termos que o
retrieval precisa casar — "Devon brawler" era Tavern Brawler, "micronut colony"
era Myconid Colony, "held the scar more" era Helldusk Armour. Corrigir isso de
memória é convite a canonizar erro. Este script produz a LISTA CANÔNICA contra a
qual as correções devem casar; nome que não casar com nada aqui fica como está
no original.

A fonte é só a wiki (arquivos de 02_trusted sem prefixo de fonte) porque ela já
é densa, estruturada e derivada da wiki oficial — é referência, não alvo de
refino.

Saída: data/03_refined/glossario_wiki.json

Uso:
    python scripts/wiki_glossary.py [--out CAMINHO]
"""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TRUSTED_DIR = BASE_DIR / "data" / "02_trusted"
DEFAULT_OUT = BASE_DIR / "data" / "03_refined" / "glossario_wiki.json"

#: Prefixos de fonte da comunidade. O que não tem prefixo é wiki.
_PREFIXOS_FONTE = ("forum_", "youtube_", "steam_", "build_")

#: Sequência Title Case ("Gauntlets of Hill Giant Strength"). Pega nomes que não
#: estão em link nem em negrito — a wiki cita muita coisa só na prosa.
_TITLE_CASE = re.compile(
    r"\b(?:[A-Z][a-z']+)"
    r"(?:\s+(?:of|the|and|de|to|in|a|for|from)\s+[A-Z][a-z']+|\s+[A-Z][a-z']+)+"
)

#: Categoria inferida pelo arquivo em que o termo aparece. Não é exata (um item
#: citado em all_quests.md vira "quest"), mas serve para o humano inspecionar e
#: para o refinador priorizar dicas relevantes.
_CATEGORIA_POR_ARQUIVO = {
    "feats.md": "feat",
    "items.md": "item",
    "weapons.md": "item",
    "armour_class.md": "item",
    "classes.md": "classe",
    "races.md": "raca",
    "backgrounds.md": "background",
    "spells.md": "magia",
    "list_of_all_spells.md": "magia",
    "conditions.md": "condicao",
    "list_of_locations.md": "local",
    "list_of_characters.md": "npc",
    "companions.md": "npc",
    "origins.md": "npc",
    "illithid_powers.md": "poder",
    "skills.md": "pericia",
    "abilities.md": "atributo",
    "damage_types.md": "dano",
    "damage_mechanics.md": "mecanica",
    "gameplay_mechanics.md": "mecanica",
    "weapon_actions.md": "mecanica",
    "resting.md": "mecanica",
    "d&d_5e_rule_changes.md": "mecanica",
    "all_quests.md": "quest",
    "patch_notes.md": "patch",
    "guide_guides.md": "guia",
}

#: Palavras que sozinhas não são nome próprio de jogo — cortam ruído do
#: Title Case ("The Game", "You Can").
_RUIDO = {
    "the", "you", "your", "this", "that", "there", "here", "and", "but", "for",
    "with", "from", "when", "what", "which", "while", "how", "why", "all",
    "main", "article", "see", "also", "note", "example", "however", "if", "it",
    "in", "on", "at", "to", "of", "as", "is", "are", "was", "were", "be",
}


def _limpar(termo: str) -> str:
    termo = " ".join(termo.split())
    return termo.strip(" .,;:!?*_-–—\"'()[]")


def _aceitavel(termo: str) -> bool:
    if not (3 <= len(termo) <= 60):
        return False
    if termo.startswith(("Category:", "File:", "Guide:", "Template:")):
        return False
    palavras = termo.split()
    if len(palavras) > 6:
        return False
    # descarta se TODAS as palavras são ruído gramatical
    if all(p.lower().strip("'s") in _RUIDO for p in palavras):
        return False
    # descarta o que termina em palavra funcional ("Auntie Ethel We")
    if palavras[-1].lower() in _RUIDO:
        return False
    return any(c.isalpha() for c in termo)


def normalizar(termo: str) -> str:
    """Chave de comparação: minúsculas, só letras/dígitos/espaço."""
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", termo.lower())).strip()


def arquivos_wiki(trusted_dir: Path = TRUSTED_DIR) -> list[Path]:
    return sorted(
        p for p in trusted_dir.glob("*.md")
        if not p.name.startswith(_PREFIXOS_FONTE)
    )


def extrair(trusted_dir: Path = TRUSTED_DIR) -> dict:
    termos: dict[str, dict] = {}
    origens: dict[str, set] = defaultdict(set)

    def registrar(bruto: str, arquivo: str, padrao: str) -> None:
        termo = _limpar(bruto)
        if not _aceitavel(termo):
            return
        chave = normalizar(termo)
        if not chave:
            return
        entrada = termos.setdefault(
            chave, {"canonico": termo, "padroes": set(), "arquivos": set()}
        )
        # Título de link é a forma mais confiável: sobrescreve as heurísticas.
        if padrao == "link" and entrada["canonico"] != termo:
            entrada["canonico"] = termo
        entrada["padroes"].add(padrao)
        entrada["arquivos"].add(arquivo)
        origens[chave].add(arquivo)

    for caminho in arquivos_wiki(trusted_dir):
        texto = caminho.read_text(encoding="utf-8")
        nome = caminho.name

        for t in re.findall(r'\]\(/wiki/[^)]*?"([^"]+)"\)', texto):
            registrar(t, nome, "link")
        for t in re.findall(r"^#{2,4}\s+(.+?)\s*$", texto, re.M):
            registrar(t, nome, "header")
        for t in re.findall(r"!\[([^\]]+)\]\(", texto):
            registrar(t, nome, "imagem")
        for t in re.findall(r"\*\*([^*]{3,60})\*\*", texto):
            registrar(t, nome, "negrito")

        # Title Case só na prosa: remove markup de link/imagem antes, senão
        # capta pedaço de URL e nome de arquivo de imagem.
        prosa = re.sub(r"\[!\[[^\]]*\]\([^)]*\)\]\([^)]*\)", " ", texto)
        prosa = re.sub(r"\]\(/wiki/[^)]*\)|\(/w/images[^)]*\)", " ", prosa)
        prosa = re.sub(r"https?://\S+", " ", prosa)
        for t in _TITLE_CASE.findall(prosa):
            registrar(t, nome, "prosa")
            # Também os nomes atômicos dentro do span: o regex casa o trecho
            # mais longo, então "Get Help from Auntie Ethel" engoliria
            # "Auntie Ethel" e o nome próprio que interessa nunca entraria.
            for parte in re.split(
                r"\s+(?:of|the|and|de|to|in|a|for|from)\s+", t
            ):
                if parte != t:
                    registrar(parte, nome, "prosa")

    saida = {}
    for chave, entrada in termos.items():
        arquivos = sorted(entrada["arquivos"])
        categorias = sorted(
            {_CATEGORIA_POR_ARQUIVO.get(a, "outro") for a in arquivos}
        )
        saida[chave] = {
            "canonico": entrada["canonico"],
            "categorias": categorias,
            "padroes": sorted(entrada["padroes"]),
            "arquivos": arquivos,
        }
    return saida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Extrai glossário canônico das wikis de 02_trusted."
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args(argv)

    fontes = arquivos_wiki()
    print(f"Lendo {len(fontes)} arquivos de wiki em {TRUSTED_DIR}")
    glossario = extrair()

    destino = Path(args.out)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(
        json.dumps(
            {
                "termos": glossario,
                "gerado_de": [p.name for p in fontes],
                "total": len(glossario),
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    por_categoria: dict[str, int] = defaultdict(int)
    for e in glossario.values():
        for c in e["categorias"]:
            por_categoria[c] += 1
    print(f"{len(glossario)} termos canônicos -> {destino}")
    for categoria, n in sorted(por_categoria.items(), key=lambda x: -x[1]):
        print(f"  {categoria:12} {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
