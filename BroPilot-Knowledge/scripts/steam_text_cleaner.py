import os
import re
from bs4 import BeautifulSoup
from markdownify import markdownify as md

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("🧹 Iniciando a limpeza dos guias da Steam...")

for nome_arquivo in os.listdir(pasta_raw):
    if not (nome_arquivo.startswith("steam_") and nome_arquivo.endswith(".html")):
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

        secoes = sopa.find_all("div", class_="subSection")

        if secoes:
            blocos = []
            for secao in secoes:
                titulo_secao_tag = secao.select_one(".subSectionTitle")
                desc_tag = secao.select_one(".subSectionDesc")
                titulo_secao = titulo_secao_tag.get_text(strip=True) if titulo_secao_tag else ""
                texto_secao = md(str(desc_tag), heading_style="ATX").strip() if desc_tag else ""
                texto_secao = re.sub(r"\n{3,}", "\n\n", texto_secao)
                blocos.append(f"## {titulo_secao}\n\n{texto_secao}")
            corpo = "\n\n".join(blocos)
        else:
            corpo = md(str(sopa), heading_style="ATX").strip()
            corpo = re.sub(r"\n{3,}", "\n\n", corpo)

        with open(caminho_trusted, "w", encoding="utf-8") as f:
            f.write(f"# {titulo}\n\n{fonte}\n\n{corpo}")

        print(f"✅ Limpo: {novo_nome}")

    except Exception as e:
        print(f"❌ Erro ao processar {nome_arquivo}: {e}")

print("\n🚀 Limpeza dos guias da Steam concluída!")
