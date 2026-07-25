"""Script de exemplo para parsing e inspeção do savegame mais recente do BG3."""

import sys
from pathlib import Path

# Configura codificação UTF-8 no stdout para evitar erros no Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Adiciona o pacote bropilot ao PYTHONPATH
src_dir = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(src_dir))

from bropilot import SaveGame, latest_save, SaveContext

def main():
    save_path = latest_save()
    if not save_path:
        print("[!] Nenhum savegame do Baldur's Gate 3 foi encontrado no diretório padrão.")
        return

    print(f"[*] Lendo savegame: {save_path.name}")
    save = SaveGame(save_path)
    ctx = SaveContext(save)

    print("\n--- Summary ---")
    print(f"Party Ativa: {ctx.party}")
    print(f"Quests Rastreadas: {len(ctx.quests)}")
    print(f"Itens Globais: {len(ctx.items)}")

    # Exemplo de listagem das quests aceitas
    accepted_quests = [q for q in ctx.quests.values() if q.status == "Accepted"]
    print(f"\nQuests Aceitas ({len(accepted_quests)}):")
    for q in accepted_quests[:5]:
        print(f"  - {q.quest_id} (Flags: {len(q.flags)})")
    if len(accepted_quests) > 5:
        print(f"  ... e mais {len(accepted_quests) - 5} quests.")

if __name__ == "__main__":
    main()
