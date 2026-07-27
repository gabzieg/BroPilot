"""Prepara o mod BroPilotExporter para empacotamento e verifica a instalação.

O repositório é a única fonte de verdade do mod. Este script monta uma pasta de
staging limpa a partir dele, valida o que o empacotador exige e aponta cópias
órfãs já instaladas no sistema — que silenciosamente sobrescrevem o mod real.

Uso:
    python scripts/build_exporter.py                   # monta staging e valida
    python scripts/build_exporter.py --pack            # valida, empacota e instala o .pak
    python scripts/build_exporter.py --check           # confere o snapshot pós-teste
    python scripts/build_exporter.py --check <arquivo> # confere um snapshot avulso
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "exporter" / "BroPilotExporter"
STAGING = REPO_ROOT / "build" / "BroPilotExporter"
PACKAGE = REPO_ROOT / "build" / "BroPilotExporter.pak"

#: Locais prováveis do Divine.exe (LSLib). O primeiro que existir é usado.
DIVINE_CANDIDATES = (
    Path.home() / "Tools" / "LSLib" / "Packed" / "Tools" / "Divine.exe",
    Path.home() / "Downloads" / "LSLib" / "Packed" / "Tools" / "Divine.exe",
    Path("C:/Program Files/LSLib/Packed/Tools/Divine.exe"),
)

BG3_DATA = (
    Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
    / "Larian Studios"
    / "Baldur's Gate 3"
)
MODS_DIR = BG3_DATA / "Mods"
SE_DIR = BG3_DATA / "Script Extender"
MODSETTINGS = BG3_DATA / "PlayerProfiles" / "Public" / "modsettings.lsx"
SNAPSHOT = SE_DIR / "bropilot_inventory.json"
PROBE = SE_DIR / "bropilot_probe.json"

#: Nome da pasta do mod, usado tanto em Mods/<MOD_FOLDER>/ dentro do pacote
#: quanto no atributo Folder do meta.lsx — os dois precisam bater.
MOD_FOLDER = "BroPilotExporter"

#: Arquivos obrigatórios dentro da pasta de staging, relativos à sua raiz.
#:
#: meta.lsx fica em Mods/<nome>/ porque é assim que o motor do jogo indexa
#: módulos instalados (o Gerenciador de Mods escaneia esse caminho dentro de
#: cada .pak). Já ScriptExtender/ fica na raiz do pacote: o BG3SE varre esse
#: caminho diretamente em cada .pak carregado, sem o prefixo Mods/<nome>/.
META_PATH = Path("Mods") / MOD_FOLDER / "meta.lsx"
REQUIRED_FILES = (
    META_PATH,
    Path("ScriptExtender/Config.json"),
    Path("ScriptExtender/Lua/BootstrapServer.lua"),
)


def build_staging() -> Path:
    """Recria a pasta de staging a partir do mod no repositório."""
    if STAGING.exists():
        shutil.rmtree(STAGING)
    STAGING.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE, STAGING)
    return STAGING


def validate(root: Path) -> list[str]:
    """Verifica o que o empacotador e o Script Extender exigem.

    Devolve a lista de problemas encontrados; vazia significa pronto para empacotar.
    """
    problems: list[str] = []

    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            problems.append(f"arquivo ausente: {relative.as_posix()}")

    config_path = root / "ScriptExtender" / "Config.json"
    if config_path.is_file():
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"Config.json inválido: {exc}")
        else:
            if not config.get("ModTable"):
                problems.append("Config.json sem 'ModTable'")
            if not config.get("RequiredVersion"):
                problems.append("Config.json sem 'RequiredVersion'")

    meta_path = root / META_PATH
    if meta_path.is_file():
        meta = meta_path.read_text(encoding="utf-8")
        for attribute in ("Folder", "Name", "UUID", "Version64"):
            if f'id="{attribute}"' not in meta:
                problems.append(f"meta.lsx sem o atributo '{attribute}'")
        # O Folder precisa bater com o nome da pasta Mods/<...>/, senão o
        # motor de mods do jogo não consegue casar o descritor com o pacote.
        expected = f'id="Folder" type="LSString" value="{MOD_FOLDER}"'
        if expected not in meta:
            problems.append(
                f"meta.lsx: atributo Folder difere de Mods/{MOD_FOLDER}/"
            )

    return problems


def read_mod_identity(root: Path) -> dict[str, str]:
    """Extrai Folder, Name e UUID do meta.lsx, para registrar no modsettings.lsx."""
    import re

    meta = (root / META_PATH).read_text(encoding="utf-8")
    identity = {}
    for attribute in ("Folder", "Name", "UUID", "Version64"):
        match = re.search(
            rf'id="{attribute}"[^>]*value="([^"]*)"', meta
        )
        if match:
            identity[attribute] = match.group(1)
    return identity


def find_stray_copies() -> list[Path]:
    """Localiza cópias instaladas do mod que competem com o .pak.

    Uma pasta solta em Mods/ não é carregada pelo jogo, mas um BootstrapServer.lua
    perdido em Script Extender/Lua/ pode rodar e mascarar a versão real.
    """
    candidates = [
        MODS_DIR / MOD_FOLDER,
        SE_DIR / "Lua" / "BootstrapServer.lua",
    ]
    return [p for p in candidates if p.exists()]


def is_registered() -> bool:
    """True quando o modsettings.lsx já referencia o mod."""
    if not MODSETTINGS.is_file():
        return False
    return "BroPilotExporter" in MODSETTINGS.read_text(encoding="utf-8")


def find_divine() -> Path | None:
    """Localiza o Divine.exe do LSLib, se instalado."""
    for candidate in DIVINE_CANDIDATES:
        if candidate.is_file():
            return candidate
    found = shutil.which("divine") or shutil.which("Divine.exe")
    return Path(found) if found else None


def pack_and_install(staging: Path) -> int:
    """Empacota o staging em .pak e instala em Mods/. Devolve o código de saída."""
    divine = find_divine()
    if divine is None:
        print("\n[!] Divine.exe (LSLib) não encontrado. Procurei em:")
        for candidate in DIVINE_CANDIDATES:
            print(f"      - {candidate}")
        print("    Baixe em https://github.com/Norbyte/lslib/releases")
        return 1

    print(f"\n[*] Divine  : {divine}")
    result = subprocess.run(
        [str(divine), "-g", "bg3", "-a", "create-package",
         "-c", "lz4", "-s", str(staging), "-d", str(PACKAGE)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"[!] Empacotamento falhou (exit {result.returncode}):")
        print(result.stdout.strip() or result.stderr.strip())
        return result.returncode

    print(f"[+] Pacote  : {PACKAGE} ({PACKAGE.stat().st_size:,} bytes)")

    # Relê o pacote com o parser do próprio projeto antes de instalar.
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from bropilot.lspk import Package, PackageError

    try:
        package = Package(PACKAGE)
        names = set(package.namelist())
    except PackageError as exc:
        print(f"[!] O .pak gerado não passou na releitura: {exc}")
        return 1

    expected = {p.as_posix() for p in REQUIRED_FILES}
    if not expected.issubset(names):
        print(f"[!] Faltam arquivos no .pak: {sorted(expected - names)}")
        return 1
    print(f"[+] Releitura OK (LSPK v{package.version}, {len(names)} arquivos)")

    MODS_DIR.mkdir(parents=True, exist_ok=True)
    target = MODS_DIR / PACKAGE.name
    shutil.copy2(PACKAGE, target)
    print(f"[+] Instalado: {target}")

    if not is_registered():
        print("\n[!] O modsettings.lsx ainda não registra o mod.")
        print("    Ative 'BroPilot Exporter' no BG3 Mod Manager e salve.")
        return 1

    print("\n[+] Pronto. Abra o jogo, carregue um save e rode !bropilot_export.")
    return 0


def check_snapshot(snapshot: Path | None = None) -> int:
    """Relata o resultado de um teste no jogo. Devolve o código de saída."""
    snapshot = snapshot or SNAPSHOT
    print(f"[*] Snapshot esperado em: {snapshot}")

    if not snapshot.is_file():
        print(f"[!] {snapshot.name} não existe.")
        print("    O mod não rodou. Confira, em ordem:")
        print("      1. o .pak está em Mods/ e o mod aparece ativo no BG3 Mod Manager")
        print("      2. modsettings.lsx registra o BroPilotExporter"
              f" (atual: {'sim' if is_registered() else 'NÃO'})")
        print("      3. o console do Script Extender abriu junto com o jogo")
        print("      4. um save foi carregado (o export só roda em sessão ativa)")
        return 1

    print(f"[+] {snapshot.name} presente ({snapshot.stat().st_size:,} bytes)")

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from bropilot import load_dump_file

    dump = load_dump_file(snapshot)
    print(f"    schema {dump.schema_version}, {len(dump)} personagens")

    if dump.diagnostics:
        party_size = dump.diagnostics.get("PartySize", 0)
        print("\n    Blocos resolvidos (personagens com o dado):")
        for key, count in sorted(dump.diagnostics.items()):
            if key == "PartySize":
                continue
            mark = "OK " if count else "-- "
            print(f"      {mark}{key:<18} {count}/{party_size}")

        missing = dump.unresolved()
        if missing:
            print(f"\n[!] Sem rota de API: {', '.join(missing)}")
            print("    Rode !bropilot_probe no console e confira bropilot_probe.json.")
        else:
            print("\n[+] Todas as rotas de API resolveram.")

    if PROBE.is_file():
        print(f"\n[*] bropilot_probe.json presente ({PROBE.stat().st_size:,} bytes)")

    return 0


def main() -> int:
    if "--check" in sys.argv:
        # Caminho opcional depois de --check, para inspecionar um snapshot
        # fora da pasta do Script Extender.
        index = sys.argv.index("--check")
        override = sys.argv[index + 1] if len(sys.argv) > index + 1 else None
        return check_snapshot(Path(override) if override else None)

    print(f"[*] Origem : {SOURCE}")
    root = build_staging()
    print(f"[+] Staging: {root}")

    problems = validate(root)
    if problems:
        print("\n[!] Problemas que impedem o empacotamento:")
        for problem in problems:
            print(f"      - {problem}")
        return 1
    print("[+] Estrutura do mod válida.")

    identity = read_mod_identity(root)
    print("\n--- Identidade do mod (para o modsettings.lsx) ---")
    for key, value in identity.items():
        print(f"    {key:<10} {value}")

    stray = find_stray_copies()
    if stray:
        print("\n[!] Cópias órfãs instaladas — remova antes de testar:")
        for path in stray:
            kind = "pasta" if path.is_dir() else "arquivo"
            print(f"      - ({kind}) {path}")
        print("    A pasta solta em Mods/ não é carregada pelo jogo, mas um")
        print("    BootstrapServer.lua em Script Extender/Lua/ pode rodar e")
        print("    mascarar a versão empacotada.")

    print(f"\n[*] Registrado no modsettings.lsx: {'sim' if is_registered() else 'NÃO'}")

    if "--pack" in sys.argv:
        return pack_and_install(root)

    print("\n--- Próximos passos ---")
    print("  python scripts/build_exporter.py --pack    # empacota e instala")
    print("  (no jogo) carregue um save e rode !bropilot_export")
    print("  python scripts/build_exporter.py --check   # confere o resultado")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
