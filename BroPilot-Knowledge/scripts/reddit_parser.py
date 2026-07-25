import cloudscraper
import json
import os
import time

# As threads de ouro do r/BG3Builds
urls_reddit = [
    "https://www.reddit.com/r/BG3Builds/comments/190r158/bg3_party_building_templates",
    "https://www.reddit.com/r/BG3Builds/comments/17y9ot9/bg3_build_tier_list",
    "https://www.reddit.com/r/BG3Builds/comments/181x4x1/best_builds_for_honor_mode"
]

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("🥷 Iniciando extração furtiva do Reddit (Bypassing Cloudflare)...")

# 1. Aqui está a mágica: criamos um "Navegador Fantasma"
scraper = cloudscraper.create_scraper(browser={
    'browser': 'chrome',
    'platform': 'darwin',
    'desktop': True
})

for url in urls_reddit:
    json_url = url.rstrip('/') + '.json'
    post_id = url.split('/comments/')[1].split('/')[0]
    
    print(f"\nInfiltrando na Thread ID: {post_id}")
    
    try:
        # Usamos o scraper furtivo em vez do requests padrão
        resposta = scraper.get(json_url)
        resposta.raise_for_status()
        
        dados = resposta.json()
        
        # Salva RAW para backup
        caminho_raw = os.path.join(pasta_raw, f"reddit_{post_id}.json")
        with open(caminho_raw, 'w', encoding='utf-8') as f:
            json.dump(dados, f, indent=4)
            
        # Extrai e salva Markdown limpo para a IA
        post_principal = dados[0]['data']['children'][0]['data']
        titulo = post_principal.get('title', 'Sem Titulo')
        texto_markdown = post_principal.get('selftext', '')
        
        caminho_trusted = os.path.join(pasta_trusted, f"reddit_{post_id}.md")
        with open(caminho_trusted, 'w', encoding='utf-8') as f:
            f.write(f"# {titulo}\n\n")
            f.write(texto_markdown)
            
        print(f"✅ Sucesso! Conhecimento roubado: reddit_{post_id}.md")
        
    except Exception as erro:
        print(f"❌ Erro ao passar pela segurança no post {post_id}: {erro}")
        
    time.sleep(3)

print("\n🚀 Infiltração concluída. Base de dados atualizada!")