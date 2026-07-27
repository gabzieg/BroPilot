import os
import re
import time
import requests
from bs4 import BeautifulSoup

# Boards relevantes do forums.larian.com para Baldur's Gate 3
boards = {
    102: "Build Discussion",
    90: "Mega-threads and Guides",
    88: "Help Tips and Tricks",
}

PAGINAS_POR_BOARD = 3   # ~30 tópicos por página
TOP_N_POR_BOARD = 20    # quantos tópicos (por views) baixar de cada board

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_destino = os.path.join(base_dir, "data", "01_raw")

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

print("🏰 Iniciando o Crawler do Fórum Oficial da Larian...")


def listar_topicos(board_id):
    topicos = {}
    for pagina in range(1, PAGINAS_POR_BOARD + 1):
        url = f"https://forums.larian.com/ubbthreads.php?ubb=postlist&Board={board_id}&page={pagina}"
        try:
            resposta = requests.get(url, headers=headers, timeout=15)
            resposta.raise_for_status()
        except Exception as erro:
            print(f"  ❌ Erro ao listar página {pagina} do board {board_id}: {erro}")
            continue

        sopa = BeautifulSoup(resposta.text, "html.parser")
        # Links com rel="nofollow" são o "Last Post" (data/autor), não o título do tópico
        for link in sopa.select('a[href*="ubb=showflat"]'):
            if link.get("rel"):
                continue
            match = re.search(r"Number=(\d+)", link.get("href", ""))
            if not match:
                continue
            numero = match.group(1)
            titulo = link.get_text(strip=True)
            if not titulo or numero in topicos:
                continue

            # Sobe até a linha da tabela para achar o contador de Views
            linha = link.find_parent("tr") or link.find_parent("div")
            views_match = re.search(r"Views:\s*([\d,]+)", linha.get_text()) if linha else None
            views = int(views_match.group(1).replace(",", "")) if views_match else 0

            topicos[numero] = {"titulo": titulo, "views": views}

        time.sleep(1)

    return topicos


for board_id, nome_board in boards.items():
    print(f"\n📋 Board: {nome_board} (ID {board_id})")
    topicos = listar_topicos(board_id)
    print(f"  {len(topicos)} tópicos únicos encontrados")

    top_topicos = sorted(topicos.items(), key=lambda item: -item[1]["views"])[:TOP_N_POR_BOARD]

    for numero, info in top_topicos:
        nome_arquivo = f"forum_{numero}.html"
        caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)

        if os.path.exists(caminho_arquivo):
            print(f"  ⏭️  Já existe, pulando: {nome_arquivo}")
            continue

        url_topico = f"https://forums.larian.com/ubbthreads.php?ubb=showflat&Number={numero}"
        print(f"  Buscando: {info['titulo'][:60]} ({info['views']} views)")

        try:
            resposta = requests.get(url_topico, headers=headers, timeout=15)
            resposta.raise_for_status()

            sopa = BeautifulSoup(resposta.text, "html.parser")
            posts = sopa.find_all("div", id=re.compile(r"^body\d+$"))
            # A página duplica os posts (layout desktop + mobile); fica só com a 1ª ocorrência de cada id
            vistos = set()
            posts_unicos = []
            for p in posts:
                if p["id"] not in vistos:
                    vistos.add(p["id"])
                    posts_unicos.append(p)
            html_posts = "".join(str(p) for p in posts_unicos) if posts_unicos else resposta.text

            with open(caminho_arquivo, "w", encoding="utf-8") as arquivo:
                arquivo.write(f"<h1>{info['titulo']}</h1>\n")
                arquivo.write(f"<p>Fonte: {url_topico} | Board: {nome_board}</p>\n")
                arquivo.write(html_posts)

            print(f"  ✅ Salvo como: {nome_arquivo}")

        except Exception as erro:
            print(f"  ❌ Erro ao baixar tópico {numero}: {erro}")

        time.sleep(2)

print("\n🎉 Garimpo do fórum finalizado!")
