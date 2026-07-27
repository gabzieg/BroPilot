import os
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import json

# Cole seus vídeos aqui
videos_youtube = [
    "https://www.youtube.com/watch?v=urBoLuIq7Mo",
]

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("▶️ Iniciando extração de Transcripts do YouTube...")

def extrair_id_video(url):
    padrao = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(padrao, url)
    return match.group(1) if match else None

# A partir da v1.0 a lib deixou de expor métodos estáticos: precisa instanciar.
ytt_api = YouTubeTranscriptApi()
formatador = TextFormatter()

for url in videos_youtube:
    video_id = extrair_id_video(url)

    if not video_id:
        print(f"⚠️ Não consegui achar o ID na URL: {url}")
        continue

    print(f"\nBaixando legendas do vídeo: {video_id}")

    try:
        # Lista todas as legendas disponíveis no vídeo primeiro
        lista_legendas = ytt_api.list(video_id)

        # Tenta pegar em inglês. Se não tiver, pega a primeira que aparecer (ex: PT-BR)
        try:
            legenda = lista_legendas.find_transcript(['en'])
        except Exception:
            legenda = next(iter(lista_legendas))

        # Baixa o texto bruto (FetchedTranscript, não é mais serializável direto em JSON)
        transcript_raw = legenda.fetch()

        caminho_raw = os.path.join(pasta_raw, f"youtube_{video_id}.json")
        with open(caminho_raw, 'w', encoding='utf-8') as f:
            json.dump(transcript_raw.to_raw_data(), f, indent=4, ensure_ascii=False)

        texto_limpo = formatador.format_transcript(transcript_raw)
        texto_blocos = texto_limpo.replace('\n', ' ')
        
        caminho_trusted = os.path.join(pasta_trusted, f"youtube_{video_id}.md")
        with open(caminho_trusted, 'w', encoding='utf-8') as f:
            f.write(f"# YouTube Guide - Video ID: {video_id}\n\n")
            f.write(f"**URL:** {url}\n\n")
            f.write("## Transcript\n\n")
            f.write(texto_blocos)
            
        print(f"✅ Ouro extraído e formatado: youtube_{video_id}.md")
        
    except Exception as e:
        print(f"❌ Erro ao baixar legenda do vídeo {video_id}: {e}")

print("\n🚀 Pipeline do YouTube concluído!")