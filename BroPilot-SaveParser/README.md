# 📦 BroPilot-SaveParser — Baldur's Gate 3 Savegame Extractor

O **BroPilot-SaveParser** é o motor de leitura e descompactação do estado atual do jogo Baldur's Gate 3 a partir de arquivos `.lsv` (arquivos de save do Larian Engine) e integração em tempo real via Script Extender.

---

## 🏗️ Estrutura da Pasta

```text
BroPilot-SaveParser/
├── exporter/
│   └── BroPilotExporter/       # Mod em Lua (Script Extender) para exportação de inventário em tempo real
│       ├── Mods/
│       │   └── BroPilotExporter/
│       │       └── meta.lsx    # aqui, não na raiz — é onde o jogo indexa módulos
│       └── ScriptExtender/     # aqui na raiz — é onde o BG3SE varre cada .pak
│           ├── Config.json
│           └── Lua/
│               └── BootstrapServer.lua
├── scripts/
│   ├── parse_save.py           # Script CLI para inspeção e testes rápidos de saves do BG3
│   └── build_exporter.py       # Prepara o mod para empacotamento e verifica a instalação
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

# Equipamento vestido, por personagem (requer o mod rodando)
for c in ctx.party.characters:
    for slot, item in c.equipment.items():
        print(c.name, slot, item.stats_id)
```

### 2. Teste Rápido via CLI
```bash
python BroPilot-SaveParser/scripts/parse_save.py
```

### 3. Integrador de Inventário em Tempo Real (Script Extender Mod)
O mod `BroPilotExporter` é executado diretamente dentro do jogo através do **BG3 Script Extender** (Norbyte). Ele grava `bropilot_inventory.json` na pasta do Script Extender.

#### Instalando o mod

O jogo carrega mods a partir de arquivos `.pak` registrados no `modsettings.lsx` — **uma pasta solta em `Mods/` é ignorada**, e sem entrada no `modsettings.lsx` o Osiris nunca monta o `ModTable`, então o `BootstrapServer.lua` nunca roda.

**O `meta.lsx` precisa ficar em `Mods/<Nome>/meta.lsx` dentro do pacote, não na raiz.** É esse caminho que o motor de mods do jogo varre em cada `.pak` para descobrir módulos instalados — com `meta.lsx` na raiz, o mod nunca aparece em Menu Principal → Gerenciador de Mods → Instalados, nem grafado como desativado: some por completo. Já `ScriptExtender/Config.json` e `ScriptExtender/Lua/` ficam na raiz do pacote mesmo — é ali que o BG3SE varre, sistema à parte do Gerenciador de Mods.

Requer o [LSLib](https://github.com/Norbyte/lslib/releases) (o `Divine.exe` empacota) e .NET 8 Desktop Runtime. O script procura o `Divine.exe` em `~/Tools/LSLib/`, `~/Downloads/LSLib/` e no `PATH`.

```bash
# Valida a estrutura, empacota com o Divine, relê o .pak com o parser do
# próprio projeto e instala em Mods/.
python BroPilot-SaveParser/scripts/build_exporter.py --pack
```

Depois de ativar o mod (BG3 Mod Manager, ou uma entrada `ModuleShortDesc` no `modsettings.lsx`), carregue um save, rode `!bropilot_export` no console e confira:

```bash
python BroPilot-SaveParser/scripts/build_exporter.py --check
```

Rode `--pack` de novo a cada mudança no Lua — o jogo lê o `.pak`, não o repositório.

O `--check` lê o snapshot, mostra quais blocos de stats resolveram e diz quando uma rota de API não existe naquela versão do Script Extender.

O repositório é a única fonte de verdade do mod: edite sempre `exporter/BroPilotExporter/` e reconstrua o staging, nunca as cópias instaladas.

- **Automático**: reexporta a cada ~5 s, mas só escreve em disco quando o conteúdo muda.
- **Manual**: `!bropilot_export` no console do Script Extender força uma gravação imediata.
- **Sondagem**: `!bropilot_probe` grava `bropilot_probe.json` com os componentes e campos visíveis do personagem controlado. Use quando um bloco de stats voltar vazio, para descobrir o nome real do componente naquela versão do Script Extender.

---

## 🔗 Contrato do Snapshot (`bropilot_inventory.json`, schema 3)

```jsonc
{
  "SchemaVersion": 3,
  // Quantos personagens tiveram cada bloco resolvido. Bloco em 0 = a rota de
  // API não existe nesta versão do Script Extender.
  "Diagnostics": { "PartySize": 4, "Abilities": 4, "MaxHp": 4, "Skills": 0, "...": 0 },
  "Characters": [
    {
      "UUID": "58a69333-...",
      "DisplayName": "Lae'zel",             // nome traduzido, só para exibição
      "Template": "S_Player_Laezel_<guid>",  // chave do join com SaveInfo.json

      "Abilities": { "Strength": 17, "Dexterity": 14, "...": 0 },
      "Vitals": {
        "Hp": 61, "MaxHp": 68, "TemporaryHp": 5,
        "ArmorClass": 18, "ProficiencyBonus": 3,
        "SpellCastingAbility": "Intelligence" // "None" para quem não conjura
      },
      "ActionResources": [                   // spell slots, ki, superiority dice
        { "Name": "SpellSlot", "Level": 1, "Amount": 2, "MaxAmount": 4 }
      ],
      "Passives": ["ActionSurge", "GreatWeaponMaster"],
      "Skills": null,                        // null quando a rota não resolveu
      "ProficiencyFlags": null,
      "Resistances": [0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0],

      "Equipment": {                         // apenas o que está vestido
        "MeleeMainHand": { "UUID": "...", "Template": "...", "Stats": "WPN_Greatsword", "Amount": 1, "Slot": "MeleeMainHand" }
      },
      "Items": [                             // inventário completo; Slot vazio = mochila
        { "UUID": "...", "Template": "...", "Stats": "CONS_Potion_Healing", "Amount": 4, "Slot": "" }
      ]
    }
  ]
}
```

**Por que o `Template` importa:** o `SaveInfo.json` do save **não expõe UUID** de personagem — só o campo `Origin` (`"Laezel"`, `"Shadowheart"`). O join acontece extraindo a parte legível do root template e comparando com o `Origin` normalizado. Quando o template não deriva do Origin (protagonista Tav ou Dark Urge), o parser só pareia se sobrar exatamente um personagem e um dump — na dúvida, deixa `uuid=None` em vez de arriscar equipamento trocado.

**`Resistances`** sai crua porque o formato varia: array indexado por tipo de dano, ou mapa já nomeado. O lado Python aceita os dois e nomeia o array pela ordem em `DAMAGE_TYPES`.

Os formatos antigos (schema 2, e a lista pura sem `SchemaVersion`) continuam sendo lidos.

### Lendo o diagnóstico em Python

```python
from bropilot import load_dump_file

dump = load_dump_file()
print(dump.schema_version, len(dump))
print("blocos sem rota de API:", dump.unresolved())
```

---

## 🛠️ Recursos Extraídos
- **LSF & LSPK Parsing**: Descompactação nativa em Python dos formatos proprietários da Larian Studios (`.lsv`, `.lsf`).
- **Osiris Story Parser**: Leitura do banco de dados de eventos e quests do jogo (`StorySave.bin`), identificando estados de quests (`DB_QuestIsAccepted`, `DB_QuestIsOpened`, `DB_QuestIsClosed`).
- **Party & Items Extraction**: Leitura dos personagens da party ativa, seus níveis, posições, classes e itens globais.
- **Equipamento por Slot**: Via mod companion, o que cada personagem está vestindo (`MeleeMainHand`, `Breast`, `Amulet`, ...) separado do que está na mochila.
- **Stats de Build**: Via mod companion, atributos, HP/CA, bônus de proficiência, spell slots e outros recursos de ação, passivas e resistências.

---

## ⚠️ Limites Conhecidos
- **Stats de build só existem com o mod rodando.** Eles não estão no `Globals.lsf`: o node `Character` de lá só carrega transform, crime state e flags de trader — o campo `Level` ali é o nome do mapa (ex. `"BGO_Main_A"`), não o nível do personagem. Em BG3 4.1.1 esses dados vivem em componentes ECS, alcançáveis apenas pelo Script Extender.
- **Nomes de componente ECS variam entre versões do Script Extender.** Cada leitura de stat tenta uma cascata de rotas e falha em silêncio, então um bloco vazio significa "rota não encontrada", não "personagem sem o dado". O bloco `Diagnostics` do JSON diz quais falharam; `!bropilot_probe` mostra os nomes reais.
- Sem o mod rodando, os personagens vêm apenas com nível, raça, classes e posição — sem UUID, stats, equipamento ou inventário.
