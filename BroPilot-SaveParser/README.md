# 📦 BroPilot-SaveParser — Baldur's Gate 3 Savegame Extractor

O **BroPilot-SaveParser** é o motor de leitura e descompactação do estado atual do jogo Baldur's Gate 3 a partir de arquivos `.lsv` (arquivos de save do Larian Engine) e integração em tempo real via Script Extender.

---

## 🏗️ Estrutura da Pasta

```text
BroPilot-SaveParser/
├── exporter/
│   └── BroPilotExporter/       # Mod em Lua (Script Extender) para exportação de inventário em tempo real
│       ├── meta.lsx
│       └── ScriptExtender/
│           └── Lua/
│               └── BootstrapServer.lua
├── scripts/
│   └── parse_save.py           # Script CLI para inspeção e testes rápidos de saves do BG3
└── src/
    └── bropilot/               # Pacote principal de extração de save (Python)
        ├── __init__.py
        ├── lsf.py              # Leitor/descompactador binário de LSF (Globals.lsf, meta.lsf)
        ├── lspk.py             # Leitor de pacotes binários LSPK (.lsv)
        ├── models.py           # Modelos de dados (SaveContext, Party, CharacterSummary, QuestState, Item)
        ├── osiris_common.py    # Tipos e estruturas do Osiris Story
        ├── osiris_nodes.py     # Nós de sintaxe e bancos do Osiris
        ├── osiris_parser.py    # Parser binário do StorySave.bin (bancos de dados de quests e fatos)
        └── save.py             # Localizador e abstração principal (SaveGame, find_saves, latest_save)
```

---

## 🚀 Como Usar

### 1. Leitura via Código Python
```python
from bropilot import SaveGame, latest_save, SaveContext

# Localiza o savegame mais recente no computador
save_path = latest_save()
save = SaveGame(save_path)
ctx = SaveContext(save)

# Acessa os dados extraídos
print("Party:", ctx.party)
print("Quests:", len(ctx.quests))
print("Itens:", len(ctx.items))
```

### 2. Teste Rápido via CLI
```bash
python BroPilot-SaveParser/scripts/parse_save.py
```

### 3. Integrador de Inventário em Tempo Real (Script Extender Mod)
O mod `BroPilotExporter` é executado diretamente dentro do jogo através do **BG3 Script Extender** (Norbyte). Ele gera o arquivo `bropilot_inventory.json` na pasta do Script Extender com o inventário completo e atualizado da party.

---

## 🛠️ Recursos Extraídos
- **LSF & LSPK Parsing**: Descompactação nativa em Python dos formatos proprietários da Larian Studios (`.lsv`, `.lsf`).
- **Osiris Story Parser**: Leitura do banco de dados de eventos e quests do jogo (`StorySave.bin`), identificando estados de quests (`DB_QuestIsAccepted`, `DB_QuestIsOpened`, `DB_QuestIsClosed`).
- **Party & Items Extraction**: Leitura dos personagens da party ativa, seus níveis, posições, classes e itens globais.
