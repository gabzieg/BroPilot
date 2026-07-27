import requests
import json
import os
import sys
import time
from dotenv import load_dotenv

# As threads de ouro do r/BG3Builds
urls_reddit = [
    "https://www.reddit.com/r/BG3Builds/comments/190r158/bg3_party_building_templates",
    "https://www.reddit.com/r/BG3Builds/comments/17y9ot9/bg3_build_tier_list",
    "https://www.reddit.com/r/BG3Builds/comments/181x4x1/best_builds_for_honor_mode"
]

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

load_dotenv(os.path.join(base_dir, ".env"))

CLIENT_ID = os.environ.get("REDDIT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET")
USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "bropilot-bg3-assistant/0.1")

if not CLIENT_ID or not CLIENT_SECRET:
    print(
        "❌ Faltam credenciais da API do Reddit.\n"
        "Crie um app em https://www.reddit.com/prefs/apps (tipo 'script') e defina, "
        f"em {os.path.join(base_dir, '.env')}:\n"
        "  REDDIT_CLIENT_ID=...\n"
        "  REDDIT_CLIENT_SECRET=...\n"
        "  REDDIT_USER_AGENT=bropilot-bg3-assistant/0.1 (by /u/seu_usuario)\n"
    )
    sys.exit(1)

print("🔑 Autenticando na API oficial do Reddit (OAuth2)...")

resposta_token = requests.post(
    "https://www.reddit.com/api/v1/access_token",
    auth=(CLIENT_ID, CLIENT_SECRET),
    data={"grant_type": "client_credentials"},
    headers={"User-Agent": USER_AGENT},
    timeout=15,
)

if not resposta_token.ok:
    print(f"❌ Falha na autenticação ({resposta_token.status_code}): {resposta_token.text}")
    sys.exit(1)

access_token = resposta_token.json()["access_token"]
headers = {
    "Authorization": f"bearer {access_token}",
    "User-Agent": USER_AGENT,
}

print("✅ Autenticado. Iniciando extração via API oficial...")

bloqueios = 0

for url in urls_reddit:
    post_id = url.split('/comments/')[1].split('/')[0]
    caminho_url = url.split('reddit.com')[1].rstrip('/')
    api_url = f"https://oauth.reddit.com{caminho_url}.json"

    print(f"\nBuscando Thread ID: {post_id}")

    try:
        resposta = requests.get(api_url, headers=headers, timeout=15)
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

        print(f"✅ Sucesso! Conhecimento extraído: reddit_{post_id}.md")

    except requests.exceptions.HTTPError as erro:
        status = erro.response.status_code if erro.response is not None else None
        if status == 403:
            bloqueios += 1
        print(f"❌ Erro HTTP {status} no post {post_id}: {erro}")

    except Exception as erro:
        print(f"❌ Erro ao processar o post {post_id}: {erro}")

    time.sleep(2)

if bloqueios:
    print(
        f"\n⚠️ {bloqueios}/{len(urls_reddit)} threads bloqueadas mesmo via API oficial.\n"
        "Use o Modo de Contingência: abra a thread no navegador, Ctrl+A/Ctrl+C o conteúdo, "
        "cole em data/01_raw/reddit_<nome>_manual.txt e rode scripts/reddit_text_cleaner.py."
    )

print("\n🚀 Extração concluída. Base de dados atualizada!")
