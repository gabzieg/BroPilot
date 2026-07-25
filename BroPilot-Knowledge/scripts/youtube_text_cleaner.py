import os
import re

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("🧹 Iniciando a faxina na transcrição manual do YouTube...")

# Expressão regular para encontrar os marcadores de tempo (ex: 0:00, 1:23:45, 12:34)
padrao_tempo = r'^\d{1,2}:\d{2}(:\d{2})?$'

for nome_arquivo in os.listdir(pasta_raw):
    if nome_arquivo.endswith('.txt') and 'youtube' in nome_arquivo.lower():
        caminho_raw = os.path.join(pasta_raw, nome_arquivo)
        novo_nome = nome_arquivo.replace('.txt', '.md')
        caminho_trusted = os.path.join(pasta_trusted, novo_nome)
        
        try:
            with open(caminho_raw, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
                
            texto_limpo = []
            
            for linha in linhas:
                linha_limpa = linha.strip()
                
                # Ignora linhas vazias
                if not linha_limpa:
                    continue
                    
                # Ignora as linhas que são apenas marcadores de tempo
                if re.match(padrao_tempo, linha_limpa):
                    continue
                    
                # Se passou pelos filtros, é texto útil
                texto_limpo.append(linha_limpa)
            
            # Junta tudo separando por um espaço (vira um parágrafo contínuo)
            texto_final = " ".join(texto_limpo)
            
            with open(caminho_trusted, 'w', encoding='utf-8') as f:
                f.write(f"# Dossiê YouTube (Extração Manual)\n\n")
                f.write("## Transcript\n\n")
                f.write(texto_final)
                
            print(f"✨ Sucesso! Texto limpo e transformado em: {novo_nome}")
            
        except Exception as e:
            print(f"❌ Erro ao processar o arquivo {nome_arquivo}: {e}")

print("\n🚀 Pipeline do YouTube concluído! Ouro puro para a IA.")