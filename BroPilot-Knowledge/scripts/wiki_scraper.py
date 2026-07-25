import requests
from bs4 import BeautifulSoup
import os
import time

# A lista completa de URLs para garimpar
urls_para_garimpar = [
    "https://bg3.wiki/wiki/Damage_mechanics",
    "https://bg3.wiki/wiki/Action_economy",
    "https://bg3.wiki/wiki/Classes",
    "https://bg3.wiki/wiki/Feats",
    "https://bg3.wiki/wiki/Weapons"
]

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_destino = os.path.join(base_dir, "data", "01_raw")

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
}

print("🕷️ Iniciando o Crawler do BroPilot...")

for url in urls_para_garimpar:
    nome_arquivo = url.split('/')[-1].lower() + ".html"
    caminho_arquivo = os.path.join(pasta_destino, nome_arquivo)
    
    print(f"Buscando: {url}")
    
    try:
        resposta = requests.get(url, headers=headers)
        resposta.raise_for_status()
        
        sopa = BeautifulSoup(resposta.text, 'html.parser')
        conteudo_principal = sopa.find('div', class_='mw-parser-output')
        
        html_final = str(conteudo_principal) if conteudo_principal else resposta.text
        
        with open(caminho_arquivo, 'w', encoding='utf-8') as arquivo:
            arquivo.write(html_final)
            
        print(f"✅ Salvo como: {nome_arquivo}")
        
    except Exception as erro:
        print(f"❌ Erro ao baixar {url}: {erro}")
        
    # Pausa de 2 segundos para não tomar ban do servidor
    time.sleep(2)

print("\n🎉 Garimpo finalizado!")