"""Refino 1:1 de transcrições do YouTube: 02_trusted -> 03_refined.

O conteúdo dessas fontes é valioso (é onde mora a ESTRATÉGIA de min-max) mas a
forma é péssima: sem pontuação, com saudação e pedido de like, cortes no meio da
frase e — o pior — nomes próprios destruídos ("Devon brawler" era Tavern
Brawler, "micronut colony" era Myconid Colony). Esse último ponto é o que torna
o conteúdo irrecuperável por busca.

UM documento de entrada -> UM documento de saída. Não sintetiza múltiplas fontes
num doc canônico: isso é fase futura e outro risco.

O risco desta etapa é canonizar erro, e erro canonizado fica invisível. Daí:
- correção de nome próprio só contra o glossário da wiki (wiki_glossary.py),
  nunca de memória — o que não casar fica como está e vai para o log;
- números são copiados, nunca recalculados;
- opinião de meta do autor é conteúdo, preservada como opinião dele;
- toda saída passa por verificação mecânica (números e nomes próprios) e
  documento que falhar é marcado SUSPEITO no log, não descartado em silêncio.

Uso:
    python scripts/youtube_refiner.py [--limit N] [--only-types youtube]
                                      [--dry-run] [--out-dir CAMINHO]

Precisa do venv que tem `bropilot_core` (o venv da raiz do repo), porque usa
create_provider() para respeitar BROPILOT_LLM.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BASE_DIR.parent
TRUSTED_DIR = BASE_DIR / "data" / "02_trusted"
REFINED_DIR = BASE_DIR / "data" / "03_refined"
GLOSSARIO = REFINED_DIR / "glossario_wiki.json"
LOG_PATH = REFINED_DIR / "refino_log.jsonl"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from bropilot_core.llm import create_provider  # noqa: E402
from wiki_glossary import normalizar  # noqa: E402

#: Tamanho de cada parte enviada ao modelo, em caracteres. Transcrição não tem
#: parágrafo, então o corte é por tamanho com recuo até um limite de frase.
_CHARS_POR_PARTE = 9000
#: Quanto do refinado anterior volta como contexto de continuidade.
_CONTEXTO_CHARS = 700

_TITLE_CASE = re.compile(
    r"\b(?:[A-Z][a-z']+)"
    r"(?:\s+(?:of|the|and|de|to|in|a|for|from)\s+[A-Z][a-z']+|\s+[A-Z][a-z']+)+"
)
#: Dado de RPG (3d6) e número solto. Dado vem primeiro para não ser partido.
_NUMEROS = re.compile(r"\d+\s*d\s*\d+|\d+")

_REGRAS = """\
REGRAS INEGOCIÁVEIS:
1. NÃO INVENTE. Nada pode aparecer no texto refinado que não esteja no original.
   Se algo está confuso demais para entender, omita — não complete com o que
   "provavelmente era".
2. NÚMEROS SÃO SAGRADOS. Dado de dano, nível, número de usos, custo de recurso:
   copie exatamente. Se a transcrição está ambígua, escreva o número como está e
   marque com "(incerto)". Nunca escolha um valor.
3. NÃO CORRIJA A ESTRATÉGIA. As opiniões de meta do autor SÃO o conteúdo. Mesmo
   que você discorde, preserve — e deixe claro que é opinião dele ("o autor
   considera", "na opinião dele").
4. NOMES PRÓPRIOS: corrija apenas usando a lista de termos canônicos fornecida.
   Nome que não estiver na lista, mantenha exatamente como está no original.
5. REMOVA: saudação, despedida, pedido de like/inscrição, autopromoção e
   divagação sem conteúdo técnico.
6. ESTRUTURE: use headers markdown (##, ###) por assunto e prosa legível.
   Tabelas markdown quando a informação for naturalmente tabular.
"""


def carregar_glossario(caminho: Path = GLOSSARIO) -> dict:
    if not caminho.exists():
        raise SystemExit(
            f"erro: glossário não encontrado em {caminho}.\n"
            "Gere primeiro:  python scripts/wiki_glossary.py"
        )
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return dados["termos"]


def _tokens(texto: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", texto.lower())


def termos_relevantes(texto: str, glossario: dict, limite: int = 120) -> list[str]:
    """Termos canônicos plausivelmente presentes neste trecho.

    Mandar o glossário inteiro (3 mil termos) estouraria o contexto e afogaria o
    modelo. O filtro é por sobreposição de tokens: um termo entra se uma fração
    suficiente das suas palavras aparece no trecho, o que sobrevive à
    transcrição ter destruído parte do nome ("micronut colony" ainda tem
    "colony").
    """
    presentes = set(_tokens(texto))
    pontuados = []
    for chave, entrada in glossario.items():
        palavras = [p for p in chave.split() if len(p) > 2]
        if not palavras:
            continue
        acertos = sum(1 for p in palavras if p in presentes)
        if acertos == 0:
            continue
        cobertura = acertos / len(palavras)
        # Termo de uma palavra só entra com match exato; composto entra com
        # metade, porque é justamente o composto que a transcrição quebra.
        if cobertura >= (1.0 if len(palavras) == 1 else 0.5):
            pontuados.append((cobertura, len(palavras), entrada["canonico"]))
    pontuados.sort(key=lambda x: (-x[0], -x[1]))
    return [nome for _, _, nome in pontuados[:limite]]


def partir(texto: str, tamanho: int = _CHARS_POR_PARTE) -> list[str]:
    """Fatia a transcrição em partes, recuando até um fim de frase provável.

    Nunca trunca: documento longo (youtube_manual.md tem 560 KB) vira muitas
    partes encadeadas por contexto de continuidade.
    """
    partes, inicio = [], 0
    while inicio < len(texto):
        fim = min(inicio + tamanho, len(texto))
        if fim < len(texto):
            janela = texto[max(inicio, fim - 500):fim]
            corte = max(janela.rfind(". "), janela.rfind("? "), janela.rfind(" and "))
            if corte > 0:
                fim = max(inicio, fim - 500) + corte + 1
        partes.append(texto[inicio:fim].strip())
        inicio = fim
    return [p for p in partes if p]


def extrair_transcript(texto: str) -> tuple[str, str]:
    """Devolve (url, corpo do transcript) do .md de 02_trusted."""
    url_match = re.search(r"\*\*URL:\*\*\s*(\S+)", texto)
    url = url_match.group(1) if url_match else ""
    corpo = texto.split("## Transcript", 1)
    return url, (corpo[1] if len(corpo) > 1 else texto).strip()


def refinar_parte(
    llm, parte: str, termos: list[str], contexto: str, indice: int, total: int
) -> str:
    system = (
        "Você reescreve transcrições de vídeos de Baldur's Gate 3 em documentos "
        "técnicos, densos e bem estruturados em português. Você NÃO é um "
        "assistente conversacional: sua saída é o documento, sem preâmbulo, sem "
        "comentário sobre a tarefa e sem repetir estas instruções.\n\n" + _REGRAS
    )
    blocos = []
    if termos:
        blocos.append(
            "TERMOS CANÔNICOS (grafia correta; use-os para corrigir nomes mal "
            "transcritos — e SÓ estes):\n" + "\n".join(f"- {t}" for t in termos)
        )
    if contexto:
        blocos.append(
            "FIM DO TRECHO ANTERIOR JÁ REFINADO (continue de onde parou; não "
            "repita este conteúdo e não reabra headers já usados):\n"
            f"...{contexto}"
        )
    blocos.append(
        f"TRECHO {indice} DE {total} DA TRANSCRIÇÃO (refine este trecho):\n{parte}"
    )
    if indice > 1:
        blocos.append(
            "Comece direto no conteúdo, sem título de nível 1 (o documento já "
            "tem um)."
        )
    return llm.generate(system, "\n\n".join(blocos)).strip()


def gerar_frontmatter(llm, corpo: str, fonte: str, url: str) -> str:
    """Metadados no formato do padrão-ouro, derivados do documento já refinado."""
    system = (
        "Você extrai metadados de documentos de Baldur's Gate 3. Responda "
        "APENAS com JSON válido, sem cercas de código e sem comentário."
    )
    user = (
        "Extraia deste documento:\n"
        '{"titulo": "título curto e descritivo em português",\n'
        ' "classes": ["classes de BG3 citadas, em inglês"],\n'
        ' "subclasses": ["subclasses citadas, em inglês"],\n'
        ' "aliases_pt": ["termos de busca em português"],\n'
        ' "aliases_en": ["termos de busca em inglês"]}\n\n'
        "Só inclua o que o documento realmente cita.\n\n"
        f"DOCUMENTO:\n{corpo[:6000]}"
    )
    try:
        bruto = llm.generate(system, user).strip()
        bruto = re.sub(r"^```(?:json)?|```$", "", bruto, flags=re.M).strip()
        meta = json.loads(bruto[bruto.index("{"): bruto.rindex("}") + 1])
    except Exception:  # noqa: BLE001 — metadado é acessório, não trava o refino
        meta = {}

    def lista(chave):
        valores = [str(v).strip() for v in meta.get(chave, []) if str(v).strip()]
        return "[" + ", ".join(valores) + "]"

    titulo = str(meta.get("titulo") or Path(fonte).stem).replace('"', "'")
    return "\n".join([
        "---",
        f"fonte_original: {fonte}",
        f"url: {url}",
        "tipo: youtube",
        f'titulo: "{titulo}"',
        f"classes: {lista('classes')}",
        f"subclasses: {lista('subclasses')}",
        f"aliases_pt: {lista('aliases_pt')}",
        f"aliases_en: {lista('aliases_en')}",
        f"refinado_em: {date.today().isoformat()}",
        "nota: >",
        "  Refino 1:1 do transcript. Conteúdo e números preservados como ditos",
        "  pelo autor; apenas forma, estrutura e termos mal transcritos foram",
        "  corrigidos. Opiniões de meta são do criador do vídeo, não",
        "  verificadas contra a wiki.",
        "---",
    ])


def _candidatos_nome(texto: str) -> set[str]:
    """Nomes próprios do refinado, linha a linha e célula a célula.

    Sem quebrar por célula, o regex atravessa o pipe da tabela e inventa nomes
    como "Amuleto Amulet of Greater Health", que viram falso suspeito.
    """
    nomes = set()
    for linha in texto.splitlines():
        # markup vira SEPARADOR, não espaço: trocar por espaço colaria
        # "**Guild Artisan** (Insight...)" num falso nome "Guild Artisan Insight".
        limpo = re.sub(r"[*`>#\[\]()·—–:;,]+", "|", linha)
        for celula in limpo.split("|"):
            nomes.update(_TITLE_CASE.findall(celula))
    return nomes


def verificar(refinado: str, original: str, glossario: dict) -> dict:
    """Checagem mecânica do refinado contra o original + glossário."""
    corpo = refinado.split("---", 2)[-1]

    nums_orig = set(re.sub(r"\s+", "", n) for n in _NUMEROS.findall(original))
    nums_novos = sorted(
        {re.sub(r"\s+", "", n) for n in _NUMEROS.findall(corpo)} - nums_orig
    )

    orig_norm = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]", " ", original.lower())) + " "
    nomes_novos = []
    for nome in sorted(_candidatos_nome(corpo)):
        chave = normalizar(nome)
        if not chave:
            continue
        if f" {chave} " in orig_norm or chave in glossario:
            continue
        nomes_novos.append(nome)

    return {
        "numeros_nao_encontrados": nums_novos,
        "nomes_nao_verificados": nomes_novos,
        "suspeito": bool(nums_novos or nomes_novos),
    }


def refinar_documento(llm, caminho: Path, glossario: dict) -> tuple[str, dict]:
    bruto = caminho.read_text(encoding="utf-8")
    url, transcript = extrair_transcript(bruto)
    if len(transcript) < 400:
        raise ValueError(f"transcript curto demais ({len(transcript)} chars)")

    partes = partir(transcript)
    refinadas: list[str] = []
    for i, parte in enumerate(partes, start=1):
        termos = termos_relevantes(parte, glossario)
        contexto = refinadas[-1][-_CONTEXTO_CHARS:] if refinadas else ""
        print(f"      parte {i}/{len(partes)} ({len(parte)} chars, "
              f"{len(termos)} termos do glossário)", flush=True)
        refinadas.append(refinar_parte(llm, parte, termos, contexto, i, len(partes)))

    corpo = "\n\n".join(refinadas).strip()
    documento = gerar_frontmatter(llm, corpo, caminho.name, url) + "\n\n" + corpo + "\n"
    return documento, verificar(documento, bruto, glossario)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Refina transcrições de 02_trusted para 03_refined."
    )
    parser.add_argument("--limit", type=int, help="máximo de documentos.")
    parser.add_argument("--only-types", default="youtube",
                        help="prefixos de fonte, separados por vírgula.")
    parser.add_argument("--dry-run", action="store_true",
                        help="lista o que faria, sem chamar o modelo.")
    parser.add_argument("--out-dir", default=str(REFINED_DIR),
                        help="destino (use um temporário para validar).")
    parser.add_argument("--only-file", help="refina só este arquivo (nome).")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)
    prefixos = tuple(f"{t.strip()}_" for t in args.only_types.split(",") if t.strip())
    glossario = carregar_glossario()

    candidatos = sorted(
        p for p in TRUSTED_DIR.glob("*.md") if p.name.startswith(prefixos)
    )
    if args.only_file:
        candidatos = [p for p in candidatos if p.name == args.only_file]
        if not candidatos:
            return print(f"erro: {args.only_file} não encontrado.") or 1

    pendentes = [p for p in candidatos if not (out_dir / p.name).exists()]
    pulados = len(candidatos) - len(pendentes)
    if args.limit:
        pendentes = pendentes[: args.limit]

    print(f"glossário: {len(glossario)} termos")
    print(f"candidatos: {len(candidatos)} | já refinados (pulados): {pulados} "
          f"| a processar: {len(pendentes)}")
    if args.dry_run:
        for p in pendentes:
            print(f"  [dry-run] {p.name}")
        return 0
    if not pendentes:
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    llm = create_provider()
    llm.health_check()

    processados, suspeitos, falhas = 0, 0, 0
    for i, caminho in enumerate(pendentes, start=1):
        print(f"[{i}/{len(pendentes)}] {caminho.name}", flush=True)
        inicio = time.perf_counter()
        registro = {"arquivo": caminho.name, "quando": date.today().isoformat()}
        try:
            documento, check = refinar_documento(llm, caminho, glossario)
        except Exception as exc:  # noqa: BLE001 — um doc ruim não derruba o lote
            falhas += 1
            registro.update(status="falhou", erro=f"{type(exc).__name__}: {exc}")
            print(f"      !! {registro['erro']}", flush=True)
        else:
            # Grava documento a documento: queda no meio do lote não perde o
            # que já foi refinado, e a re-execução pula o que existe.
            (out_dir / caminho.name).write_text(documento, encoding="utf-8")
            origem = len(caminho.read_text(encoding="utf-8"))
            registro.update(
                status="suspeito" if check["suspeito"] else "ok",
                chars_origem=origem,
                chars_refinado=len(documento),
                reducao_pct=round(100 * (1 - len(documento) / origem), 1),
                segundos=round(time.perf_counter() - inicio, 1),
                **check,
            )
            processados += 1
            suspeitos += bool(check["suspeito"])
            print(f"      {registro['reducao_pct']}% menor, "
                  f"{registro['segundos']}s, "
                  f"{'SUSPEITO' if check['suspeito'] else 'ok'}", flush=True)
            for n in check["numeros_nao_encontrados"][:5]:
                print(f"         número não encontrado no original: {n}")
            for n in check["nomes_nao_verificados"][:5]:
                print(f"         nome não verificado: {n}")

        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(registro, ensure_ascii=False) + "\n")

    print(f"\nprocessados: {processados} | suspeitos: {suspeitos} | "
          f"falhas: {falhas} | pulados: {pulados}")
    print(f"log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
