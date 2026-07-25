import google.generativeai as genai
import os

api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    print("API Key não encontrada no terminal.")
    exit()

genai.configure(api_key=api_key)

print("Consultando a API do Google...\n")
print("Modelos disponíveis para a sua chave:")
print("-" * 40)

# Lista todos os modelos disponíveis
for m in genai.list_models():
    # Filtra apenas os que servem para gerar conteúdo (chat)
    if 'generateContent' in m.supported_generation_methods:
        print(m.name)

print("-" * 40)

