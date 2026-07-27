import requests
from bs4 import BeautifulSoup
from urllib.parse import unquote
import os
import time

# A lista completa de URLs para garimpar
urls_para_garimpar = [
    "https://bg3.wiki/wiki/Damage_mechanics",
    # "Action_economy" foi incorporada como seção dentro de Gameplay_mechanics
    "https://bg3.wiki/wiki/Classes",
    "https://bg3.wiki/wiki/Races",
    "https://bg3.wiki/wiki/Origins",
    "https://bg3.wiki/wiki/Backgrounds",
    "https://bg3.wiki/wiki/Feats",
    "https://bg3.wiki/wiki/Abilities",
    "https://bg3.wiki/wiki/Skills",
    "https://bg3.wiki/wiki/Gameplay_mechanics",
    "https://bg3.wiki/wiki/D%26D_5e_Rule_Changes",
    "https://bg3.wiki/wiki/Resting",
    "https://bg3.wiki/wiki/Conditions",
    "https://bg3.wiki/wiki/Damage_types",
    "https://bg3.wiki/wiki/Armour_Class",
    "https://bg3.wiki/wiki/List_of_all_spells",
    "https://bg3.wiki/wiki/Spells",
    "https://bg3.wiki/wiki/Weapon_actions",
    "https://bg3.wiki/wiki/Illithid_powers",
    "https://bg3.wiki/wiki/Companions",
    "https://bg3.wiki/wiki/List_of_Characters",
    "https://bg3.wiki/wiki/All_Quests",
    "https://bg3.wiki/wiki/Items",
    "https://bg3.wiki/wiki/Weapons",
    "https://bg3.wiki/wiki/List_of_Locations",
    "https://bg3.wiki/wiki/Guide:Guides",
    "https://bg3.wiki/wiki/Patch_notes",
]

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_destino = os.path.join(base_dir, "data", "01_raw")

headers = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
}

print("🕷️ Iniciando o Crawler do BroPilot...")

for url in urls_para_garimpar:
    nome_arquivo = unquote(url.split('/')[-1]).lower().replace(':', '_') + ".html"
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