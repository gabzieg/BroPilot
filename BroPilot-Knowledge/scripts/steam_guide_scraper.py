import os
import re
import time
import requests
from bs4 import BeautifulSoup

APP_ID = 1086940  # Baldur's Gate 3

PAGINAS = 5          # ~30 guias por página
TOP_N = 40           # quantos guias baixar no total

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_destino = os.path.join(base_dir, "data", "01_raw")

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

# BG3 é marcado como "mature content" na Steam: sem esses cookies a listagem
# de guias vem sempre vazia ("No items matching your search criteria").
cookies = {
    "birthtime": "283993201",
    "lastagecheckage": "1-0-1980",
    "wants_mature_content_apps": str(APP_ID),
}


def parece_ingles(texto, limiar=0.85):
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return True
    ascii_letras = [c for c in letras if c.isascii()]
    return (len(ascii_letras) / len(letras)) >= limiar


print("📗 Iniciando o Crawler de Guias da Steam Community...")

candidatos = {}
for pagina in range(1, PAGINAS + 1):
    url = (
        f"https://steamcommunity.com/app/{APP_ID}/guides/"
        f"?browsefilter=toprated&browsesort=toprated&p={pagina}"
    )
    try:
        resposta = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        resposta.raise_for_status()
    except Exception as erro:
        print(f"❌ Erro ao listar página {pagina}: {erro}")
        continue

    sopa = BeautifulSoup(resposta.text, "html.parser")
    itens = sopa.select(".workshopItemCollectionContainer")
    print(f"  Página {pagina}: {len(itens)} guias encontrados")

    for item in itens:
        link = item.select_one('a[href*="filedetails/?id="]')
        titulo_tag = item.select_one(".workshopItemTitle")
        if not link or not titulo_tag:
            continue

        match = re.search(r"id=(\d+)", link["href"])
        if not match:
            continue

        guide_id = match.group(1)
        titulo = titulo_tag.get_text(strip=True)

        if guide_id in candidatos or not parece_ingles(titulo):
            continue

        candidatos[guide_id] = titulo

    time.sleep(1)

print(f"\n{len(candidatos)} guias em inglês encontrados, baixando os {TOP_N} primeiros...")

for guide_id, titulo in list(candidatos.items())[:TOP_N]:
    nome_arquivo = f"steam_{guide_id}.html"
    caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)

    if os.path.exists(caminho_arquivo):
        print(f"⏭️  Já existe, pulando: {nome_arquivo}")
        continue

    url_guia = f"https://steamcommunity.com/sharedfiles/filedetails/?id={guide_id}"
    print(f"Buscando: {titulo[:60]}")

    try:
        resposta = requests.get(url_guia, headers=headers, cookies=cookies, timeout=15)
        resposta.raise_for_status()

        sopa = BeautifulSoup(resposta.text, "html.parser")
        secoes = sopa.select(".subSection.detailBox")

        if secoes:
            html_corpo = "".join(str(s) for s in secoes)
        else:
            desc = sopa.select_one(".guideTopDescription") or sopa.select_one(".detailBox.workshopItemDescription")
            html_corpo = str(desc) if desc else ""

        if not html_corpo:
            print(f"⚠️  Guia sem conteúdo reconhecível: {guide_id}")
            continue

        with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
            arquivo.write(f"<h1>{titulo}</h1>\n")
            arquivo.write(f"<p>Fonte: {url_guia}</p>\n")
            arquivo.write(html_corpo)

        print(f"✅ Salvo como: {nome_arquivo}")

    except Exception as erro:
        print(f"❌ Erro ao baixar guia {guide_id}: {erro}")

    time.sleep(5)

print("\n🎉 Garimpo dos guias da Steam finalizado!")
