import os
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("🧹 Iniciando a limpeza dos HTMLs da Wiki...")

for nome_arquivo in os.listdir(pasta_raw):
    if not nome_arquivo.endswith('.html'):
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

    except Exception as e:
        print(f"❌ Erro ao processar {nome_arquivo}: {e}")

print("\n🚀 Limpeza concluída!")
