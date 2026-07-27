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
from bropilot.models import ABILITIES

def main():
    save_path = latest_save()
    if not save_path:
        print("[!] Nenhum savegame do Baldur's Gate 3 foi encontrado no diretório padrão.")
        return

    # Argumento opcional: caminho alternativo para o snapshot do mod.
    dump_path = sys.argv[1] if len(sys.argv) > 1 else None

    print(f"[*] Lendo savegame: {save_path.name}")
    save = SaveGame(save_path)
    ctx = SaveContext(save, inventory_dump=dump_path)

    print("\n--- Summary ---")
    print(f"Party Ativa: {ctx.party}")
    print(f"Quests Rastreadas: {len(ctx.quests)}")
    print(f"Itens Globais: {len(ctx.items)}")

    dump = ctx.live_dump
    if not dump:
        print("\n[!] Snapshot do mod BroPilotExporter ausente.")
        print("    Sem ele não há UUID, stats, equipamento nem inventário por personagem.")
    else:
        print(f"\n[*] Snapshot do mod: schema {dump.schema_version}, {len(dump)} personagens.")
        missing = dump.unresolved()
        if missing:
            print(f"[!] Blocos que nenhuma rota de API resolveu: {', '.join(missing)}")
            print("    Rode !bropilot_probe no console do jogo para inspecionar os componentes.")

    print("\n--- Party ---")
    for c in ctx.party.characters:
        classes = "/".join(
            f"{k.get('Main', '?')}:{k.get('Sub') or '-'}" for k in c.classes
        )
        print(f"\n{c.name} — Lvl {c.level} {c.race} [{classes}]")
        if c.uuid:
            print(f"  UUID: {c.uuid}")

        if c.stats:
            s = c.stats
            if s.abilities:
                print("  Atributos: " + "  ".join(
                    f"{name[:3].upper()} {s.abilities[name]}"
                    for name in ABILITIES if name in s.abilities
                ))
            v = s.vitals
            if v.max_hp is not None or v.armor_class is not None:
                line = f"  HP {v.hp}/{v.max_hp}"
                if v.temporary_hp:
                    line += f" (+{v.temporary_hp} temp)"
                if v.armor_class is not None:
                    line += f"   CA {v.armor_class}"
                if v.proficiency_bonus is not None:
                    line += f"   Prof +{v.proficiency_bonus}"
                print(line)
            slots = s.spell_slots
            if slots:
                print("  Spell slots: " + "  ".join(
                    f"N{r.level} {r.amount:g}/{r.max_amount:g}" for r in slots
                ))
            other = [r for r in s.action_resources if r not in slots]
            if other:
                print("  Recursos: " + "  ".join(
                    f"{r.name} {r.amount:g}/{r.max_amount:g}" for r in other[:6]
                ))
            if s.passives:
                print(f"  Passivas ({len(s.passives)}): {', '.join(s.passives[:8])}"
                      + (" ..." if len(s.passives) > 8 else ""))
            resist = {k: val for k, val in s.resistances.items()
                      if val not in ("", "0", "None")}
            if resist:
                print("  Resistências: " + "  ".join(
                    f"{k}={val}" for k, val in list(resist.items())[:8]
                ))

        if c.equipment:
            print(f"  Equipado ({len(c.equipment)}):")
            for slot, item in sorted(c.equipment.items()):
                print(f"    {slot:<16} {item.stats_id or item.template_id or '?'}")
        if c.inventory:
            bag = [i for i in c.inventory if not i.equipped]
            print(f"  Mochila: {len(bag)} itens")

    # Exemplo de listagem das quests aceitas
    accepted_quests = [q for q in ctx.quests.values() if q.status == "Accepted"]
    print(f"\nQuests Aceitas ({len(accepted_quests)}):")
    for q in accepted_quests[:5]:
        print(f"  - {q.quest_id} (Flags: {len(q.flags)})")
    if len(accepted_quests) > 5:
        print(f"  ... e mais {len(accepted_quests) - 5} quests.")

if __name__ == "__main__":
    main()
