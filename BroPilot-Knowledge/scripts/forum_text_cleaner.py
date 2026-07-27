import os
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("🧹 Iniciando a limpeza dos tópicos do fórum...")

for nome_arquivo in os.listdir(pasta_raw):
    if not (nome_arquivo.startswith("forum_") and nome_arquivo.endswith(".html")):
        continue

    caminho_raw = os.path.join(pasta_raw, nome_arquivo)
    novo_nome = nome_arquivo.replace(".html", ".md")
    caminho_trusted = os.path.join(pasta_trusted, novo_nome)

    try:
        with open(caminho_raw, "r", encoding="utf-8") as f:
            html = f.read()

        sopa = BeautifulSoup(html, "html.parser")

        titulo_tag = sopa.find("h1")
        titulo = titulo_tag.get_text(strip=True) if titulo_tag else nome_arquivo

        fonte_tag = sopa.find("p")
        fonte = fonte_tag.get_text(strip=True) if fonte_tag else ""

        posts = sopa.find_all("div", id=re.compile(r"^body\d+$"))

        blocos = []
        for i, post in enumerate(posts):
            texto_post = md(str(post), heading_style="ATX").strip()
            texto_post = re.sub(r"\n{3,}", "\n\n", texto_post)
            rotulo = "Post original" if i == 0 else f"Resposta #{i}"
            blocos.append(f"### {rotulo}\n\n{texto_post}")

        corpo = "\n\n---\n\n".join(blocos)

        with open(caminho_trusted, "w", encoding="utf-8") as f:
            f.write(f"# {titulo}\n\n{fonte}\n\n{corpo}")

        print(f"✅ Limpo: {novo_nome}")

    except Exception as e:
        print(f"❌ Erro ao processar {nome_arquivo}: {e}")

print("\n🚀 Limpeza do fórum concluída!")
