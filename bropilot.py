import google.generativeai as genai
import os

# 1. Autenticação da API
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("❌ Erro: API Key não encontrada no terminal.")
    exit()

genai.configure(api_key=api_key)

# 2. Carregando a Base de Dados Local (A camada Trusted do nosso ETL)
# O script descobre automaticamente onde ele está salvo no seu Mac
base_dir = os.path.dirname(os.path.abspath(__file__))
pasta_trusted = os.path.join(base_dir, "BroPilot-Knowledge", "data", "02_trusted")

conhecimento_bg3 = ""
print("Carregando os dados da Wiki e do Reddit...\n")

if os.path.exists(pasta_trusted):
    # Lê todos os arquivos .md e junta em um grande texto para a IA
    for nome_arquivo in os.listdir(pasta_trusted):
        if nome_arquivo.endswith(".md"):
            caminho_arquivo = os.path.join(pasta_trusted, nome_arquivo)
            with open(caminho_arquivo, 'r', encoding='utf-8') as f:
                conhecimento_bg3 += f"\n--- INÍCIO DO DOCUMENTO: {nome_arquivo} ---\n"
                conhecimento_bg3 += f.read()
                conhecimento_bg3 += f"\n--- FIM DO DOCUMENTO: {nome_arquivo} ---\n"
    print(f"✅ Conhecimento carregado com sucesso da pasta: {pasta_trusted}\n")
else:
    print(f"⚠️ Aviso: Pasta {pasta_trusted} não encontrada. O BroPilot não terá contexto local.")

# 3. Configurando a Persona e injetando o conhecimento
instrucao_sistema = f"""
Você é o BroPilot, um assistente virtual focado em min-maxing e otimização para Baldur's Gate 3.
Seu objetivo é ajudar o jogador a tomar as melhores decisões de builds e equipamentos.

Abaixo está a sua Base de Conhecimento Oficial extraída da Wiki e do Reddit. 
Use ESSES DADOS como sua fonte primária de verdade para responder:

{conhecimento_bg3}

Responda de forma analítica e focada em extrair o máximo de dano (Damage Riders). 
Fale como um parceiro de jogatina (Bro).
"""

# Usando a tag latest para evitar os erros 404 de versão
model = genai.GenerativeModel(
    model_name="gemini-flash-latest",
    system_instruction=instrucao_sistema
)

chat = model.start_chat(history=[])

print("==================================================")
print("🎲 BroPilot Inicializado! O Assistente de Min-Maxing.")
print("Digite 'sair' para encerrar.")
print("==================================================\n")

# 4. O loop da conversa
while True:
    pergunta = input("Você: ")
    
    if pergunta.lower() == 'sair':
        print("BroPilot: Falou, bro! Até o próximo save.")
        break
        
    if pergunta.strip() == "":
        continue

    print("BroPilot consultando os pergaminhos...")
    
    try:
        resposta = chat.send_message(pergunta)
        print(f"\nBroPilot: {resposta.text}\n")
        print("-" * 50)
    except Exception as e:
        print(f"\n❌ Erro de conexão com a API: {e}\n")