import os
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

# 01_raw guarda o HTML de VÁRIAS fontes no mesmo diretório. As outras fontes
# têm prefixo próprio no nome do arquivo e seu próprio cleaner pareado
# (forum_text_cleaner.py, steam_text_cleaner.py, youtube_text_cleaner.py) —
# "não é meu" para este script. A wiki é a única fonte SEM prefixo (o nome do
# arquivo é só o slug da página, ex. "battle_master.html"), então o filtro
# certo aqui é por EXCLUSÃO desses prefixos, não por um prefixo próprio da
# wiki (que não existe). Sem isto, este laço processava TODO *.html —
# incluindo forum/steam/youtube — com o parser de mw-parser-output errado e
# SOBRESCREVIA em 02_trusted o markdown que o cleaner correto de cada fonte
# já tinha produzido, silenciosamente (aconteceu de verdade ao raspar as
# subclasses da wiki: corrompeu 59 arquivos forum_*/steam_* antes de ser
# revertido).
_PREFIXOS_DE_OUTRAS_FONTES = ("forum_", "steam_", "youtube_")

print("🧹 Iniciando a limpeza dos HTMLs da Wiki...")

pulados = 0
processados = 0

for nome_arquivo in os.listdir(pasta_raw):
    if not nome_arquivo.endswith('.html'):
        continue

    if nome_arquivo.startswith(_PREFIXOS_DE_OUTRAS_FONTES):
        pulados += 1
        continue

    caminho_raw = os.path.join(pasta_raw, nome_arquivo)
    novo_nome = nome_arquivo.replace('.html', '.md')
    caminho_trusted = os.path.join(pasta_trusted, novo_nome)

    try:
        with open(caminho_raw, 'r', encoding='utf-8') as f:
            html = f.read()

        sopa = BeautifulSoup(html, 'html.parser')

        # Remove lixo de interface do MediaWiki que sobrevive dentro do mw-parser-output
        seletores_lixo = '.mw-editsection, .mw-editsection-like, .mw-headline-anchor, sup.reference, .navbox, .toc, .noprint, script, style'
        for lixo in sopa.select(seletores_lixo):
            lixo.decompose()

        texto_markdown = md(str(sopa), heading_style="ATX", bullets="-")

        # Compacta 3+ quebras de linha seguidas em no máximo 2
        texto_markdown = re.sub(r'\n{3,}', '\n\n', texto_markdown).strip()

        titulo = nome_arquivo.replace('.html', '').replace('_', ' ').title()

        with open(caminho_trusted, 'w', encoding='utf-8') as f:
            f.write(f"# {titulo}\n\n{texto_markdown}")

        print(f"✅ Limpo: {novo_nome}")
        processados += 1

    except Exception as e:
        print(f"❌ Erro ao processar {nome_arquivo}: {e}")

print(f"\n🚀 Limpeza concluída! {processados} processados, "
      f"{pulados} pulados (de outra fonte).")
