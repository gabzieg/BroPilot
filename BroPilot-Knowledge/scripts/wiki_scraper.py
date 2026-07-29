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

    # Páginas DEDICADAS de subclasse (58) — a wiki tinha só páginas de
    # CATEGORIA (Classes, Feats...) até aqui, que mencionam cada subclasse de
    # passagem mas não têm a progressão de recursos por nível (ex.: Battle
    # Master não tinha página própria, então "quantos dados de Superioridade
    # no nível 5?" não tinha resposta em lugar nenhum da base). Lista extraída
    # PROGRAMATICAMENTE de https://bg3.wiki/wiki/Classes em 2026-07-29 (fetch
    # ao vivo, não de memória): cada classe jogável tem um heading h3 com uma
    # seção "Subclasses" logo abaixo contendo os links reais da wiki,
    # incluindo o sufixo de desambiguação quando o nome colide entre classes
    # (ex.: "Wild Magic" existe em Barbarian E Sorcerer, e a própria wiki
    # resolve isso com "_(barbarian_subclass)"/"_(sorcerer_subclass)" no
    # href — por isso vem daqui e não de uma lista datilografada de memória).
    # Confirmado por fetch real que Battle_Master tem mw-parser-output e a
    # progressão "Level 3: Superiority Dice: 4 / Level 7: +1" — os dados que
    # faltavam.
    "https://bg3.wiki/wiki/Abjuration_School",
    "https://bg3.wiki/wiki/Arcane_Archer",
    "https://bg3.wiki/wiki/Arcane_Trickster",
    "https://bg3.wiki/wiki/Assassin",
    "https://bg3.wiki/wiki/Battle_Master",
    "https://bg3.wiki/wiki/Beast_Master",
    "https://bg3.wiki/wiki/Berserker",
    "https://bg3.wiki/wiki/Bladesinging",
    "https://bg3.wiki/wiki/Champion",
    "https://bg3.wiki/wiki/Circle_of_the_Land",
    "https://bg3.wiki/wiki/Circle_of_the_Moon",
    "https://bg3.wiki/wiki/Circle_of_the_Spores",
    "https://bg3.wiki/wiki/Circle_of_the_Stars",
    "https://bg3.wiki/wiki/College_of_Glamour",
    "https://bg3.wiki/wiki/College_of_Lore",
    "https://bg3.wiki/wiki/College_of_Swords",
    "https://bg3.wiki/wiki/College_of_Valour",
    "https://bg3.wiki/wiki/Conjuration_School",
    "https://bg3.wiki/wiki/Death_Domain",
    "https://bg3.wiki/wiki/Divination_School",
    "https://bg3.wiki/wiki/Draconic_Bloodline",
    "https://bg3.wiki/wiki/Eldritch_Knight",
    "https://bg3.wiki/wiki/Enchantment_School",
    "https://bg3.wiki/wiki/Evocation_School",
    "https://bg3.wiki/wiki/Giant_(barbarian_subclass)",
    "https://bg3.wiki/wiki/Gloom_Stalker",
    "https://bg3.wiki/wiki/Hunter",
    "https://bg3.wiki/wiki/Illusion_School",
    "https://bg3.wiki/wiki/Knowledge_Domain",
    "https://bg3.wiki/wiki/Life_Domain",
    "https://bg3.wiki/wiki/Light_Domain",
    "https://bg3.wiki/wiki/Nature_Domain",
    "https://bg3.wiki/wiki/Necromancy_School",
    "https://bg3.wiki/wiki/Oath_of_Devotion",
    "https://bg3.wiki/wiki/Oath_of_Vengeance",
    "https://bg3.wiki/wiki/Oath_of_the_Ancients",
    "https://bg3.wiki/wiki/Oath_of_the_Crown",
    "https://bg3.wiki/wiki/Oathbreaker",
    "https://bg3.wiki/wiki/Shadow_Magic",
    "https://bg3.wiki/wiki/Storm_Sorcery",
    "https://bg3.wiki/wiki/Swarmkeeper",
    "https://bg3.wiki/wiki/Swashbuckler",
    "https://bg3.wiki/wiki/Tempest_Domain",
    "https://bg3.wiki/wiki/The_Archfey",
    "https://bg3.wiki/wiki/The_Fiend",
    "https://bg3.wiki/wiki/The_Great_Old_One",
    "https://bg3.wiki/wiki/The_Hexblade",
    "https://bg3.wiki/wiki/Thief",
    "https://bg3.wiki/wiki/Transmutation_School",
    "https://bg3.wiki/wiki/Trickery_Domain",
    "https://bg3.wiki/wiki/War_Domain",
    "https://bg3.wiki/wiki/Way_of_Shadow",
    "https://bg3.wiki/wiki/Way_of_the_Drunken_Master",
    "https://bg3.wiki/wiki/Way_of_the_Four_Elements",
    "https://bg3.wiki/wiki/Way_of_the_Open_Hand",
    "https://bg3.wiki/wiki/Wild_Magic_(barbarian_subclass)",
    "https://bg3.wiki/wiki/Wild_Magic_(sorcerer_subclass)",
    "https://bg3.wiki/wiki/Wildheart",
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

    if os.path.exists(caminho_arquivo):
        print(f"⏭️  Já existe, pulando: {nome_arquivo}")
        continue

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