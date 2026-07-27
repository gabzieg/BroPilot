import os
import re

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("🧹 Iniciando a faxina no texto manual do Reddit...")

# Lista de palavras exatas que são lixo da interface do Reddit copiadas no Ctrl+C
lixo_exato = [
    'Share', 'Save', 'Hide', 'Report', 'Reply', 'Award', 
    'Upvote', 'Downvote', 'User avatar', 'level 1', 'level 2', 'level 3'
]

# Expressões regulares para pegar lixos variáveis (ex: "2 days ago", "15 hr. ago")
padroes_lixo = [
    r'^\d+ (days?|hr\.|min\.) ago$',
    r'^\d+ upvotes?$',
    r'^r/BG3Builds$',
    r'^Posted by u/.*'
]

for nome_arquivo in os.listdir(pasta_raw):
    # Vai procurar qualquer arquivo .txt que tenha 'reddit' no nome
    if nome_arquivo.endswith('.txt') and 'reddit' in nome_arquivo.lower():
        caminho_raw = os.path.join(pasta_raw, nome_arquivo)
        novo_nome = nome_arquivo.replace('.txt', '.md')
        caminho_trusted = os.path.join(pasta_trusted, novo_nome)
        
        try:
            with open(caminho_raw, 'r', encoding='utf-8') as f:
                linhas = f.readlines()
                
            texto_limpo = []
            
            for linha in linhas:
                linha_limpa = linha.strip()
                
                # 1. Ignora linhas vazias
                if not linha_limpa:
                    continue
                    
                # 2. Ignora linhas que são exatamente os botões do Reddit
                if linha_limpa in lixo_exato:
                    continue
                    
                # 3. Testa contra os padrões variáveis (como datas e upvotes)
                ignorar_por_regex = any(re.match(padrao, linha_limpa, re.IGNORECASE) for padrao in padroes_lixo)
                if ignorar_por_regex:
                    continue
                    
                # Se sobreviveu aos filtros, é texto útil da build!
                texto_limpo.append(linha_limpa)
            
            # Junta o texto sobrevivente com duplas quebras de linha (padrão Markdown)
            texto_final = "\n\n".join(texto_limpo)
            
            with open(caminho_trusted, 'w', encoding='utf-8') as f:
                f.write(f"# Dossiê Reddit (Extração Manual)\n\n{texto_final}")
                
            print(f"✨ Sucesso! Texto limpo e transformado em: {novo_nome}")
            
        except Exception as e:
            print(f"❌ Erro ao processar o arquivo {nome_arquivo}: {e}")

print("\n🚀 Pipeline de limpeza manual concluído. Pronto para a IA ler!")