import os
import json
import requests

# dialog.moxifer.com expõe um banco pesquisável de ~9 mil diálogos brutos do jogo
# (export técnico do motor: UUIDs, nós, arquivos .lsf/.lsx). Não é texto de guia,
# então em vez de baixar as ~9 mil páginas individuais para 01_raw/02_trusted,
# guardamos só o índice em 03_refined. A partir dele dá para buscar por
# personagem/título e baixar sob demanda a página específica em tempo de execução:
# https://dialog.moxifer.com/{path sem ".html"}

MANIFEST_URL = "https://dialog.moxifer.com/dialog-manifest.json"

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_refined = os.path.join(base_dir, "data", "03_refined")
os.makedirs(pasta_refined, exist_ok=True)

print("📖 Baixando o índice de diálogos do moxifer.com...")

headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

resposta = requests.get(MANIFEST_URL, headers=headers, timeout=30)
resposta.raise_for_status()
manifesto = resposta.json()

documentos = manifesto.get("documents", [])

# Índice por falante, para consulta rápida tipo "todas as falas do Shadowheart"
por_falante = {}
for doc in documentos:
    for falante in doc.get("speakers", []):
        por_falante.setdefault(falante, []).append(doc["path"])

indice = {
    "gerado_em": manifesto.get("generated_at"),
    "total_dialogos": manifesto.get("dialog_count"),
    "base_url": "https://dialog.moxifer.com/",
    "documentos": documentos,
    "por_falante": por_falante,
}

caminho_indice = os.path.join(pasta_refined, "dialog_index.json")
with open(caminho_indice, "w", encoding="utf-8") as f:
    json.dump(indice, f, ensure_ascii=False, indent=2)

print(f"✅ Índice salvo: {caminho_indice}")
print(f"   {len(documentos)} diálogos catalogados, {len(por_falante)} falantes únicos")
print("\n🚀 Índice do moxifer.com concluído!")
