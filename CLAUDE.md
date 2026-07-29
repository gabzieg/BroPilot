# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

BroPilot is a local assistant for Baldur's Gate 3 min-maxing (builds, action economy, equipment). It has three independent subsystems plus a thin LLM chat layer at the root — they don't import each other and each has its own dependency setup.

```
BroPilot/
├── bropilot.py                # LLM chat REPL (Gemini) — root venv
├── verificar_modelos.py        # Lists Gemini models available to the API key
├── BroPilot-Knowledge/         # ETL pipeline that builds the RAG knowledge base
│   └── .venv                   # venv for this subsystem (NOT the root venv)
├── BroPilot-SaveParser/        # Native parser for BG3's .lsv/.lsf save format + companion Lua mod
└── bropilot-ui/                # Electron overlay prototype (glassmorphism HUD over the game)
```

## Running things

There is no test suite, linter, or build system in this repo. "Development" means running the scrapers/cleaners or the chat REPL directly.

### Root chat REPL (`bropilot.py`)
```bash
source venv/bin/activate
export GEMINI_API_KEY=...
python bropilot.py
```
It concatenates **every** `.md` file under `BroPilot-Knowledge/data/02_trusted/` into the Gemini system prompt (full-context stuffing, not a vector search — there is no embeddings/retrieval step). If that directory grows much larger, this will eventually blow the context window; that's the thing to watch if editing this file.

### Knowledge ETL (`BroPilot-Knowledge/`)
Uses its own venv — **not** the root one:
```bash
cd BroPilot-Knowledge
source .venv/bin/activate
```
There's also a `.venv-1` in this folder — it's a stale, incomplete first attempt (missing `cloudscraper`/`youtube_transcript_api`/`yt-dlp`). Ignore it; always use `.venv`.

Each data source follows a `Medallion` pattern: a scraper writes raw HTML/JSON to `data/01_raw/`, then a paired `_text_cleaner.py` converts it to Markdown in `data/02_trusted/`. Run the scraper, then the cleaner:
```bash
python scripts/wiki_scraper.py && python scripts/text_cleaner.py
python scripts/youtube_parser.py            # writes directly to both layers, no separate cleaner
python scripts/forum_scraper.py && python scripts/forum_text_cleaner.py
python scripts/steam_guide_scraper.py && python scripts/steam_text_cleaner.py
python scripts/moxifer_dialog_index.py      # writes straight to data/03_refined/, see below
```
All scrapers are idempotent — they skip any output file that already exists — so it's always safe to re-run one after a partial/failed run.

**Known rate-limit behavior** (don't mistake these for bugs):
- `youtube_parser.py` (via `youtube_transcript_api`) gets IP-blocked by YouTube after roughly ~30 requests in a burst. It's temporary (tens of minutes). Just re-run later — the skip-if-exists logic means it resumes where it left off.
- `steam_guide_scraper.py` hits Steam's rate limit after roughly ~10 guide fetches even with a delay between requests. Same recovery approach: wait, re-run.
- `steam_guide_scraper.py` also depends on hardcoded mature-content cookies (`wants_mature_content_apps`, `birthtime`, `lastagecheckage`) because BG3 is flagged mature on Steam — without them the guide listing silently returns zero results, it doesn't error.
- `youtube_transcript_api` is on the v1.x API (instance-based: `YouTubeTranscriptApi().list(...)`, not the old static `.list_transcripts(...)`). Don't "fix" it back to the old API style.

**Reddit is intentionally not a source.** Its scraper (`reddit_parser.py`) and cleaner are archived under `BroPilot-Knowledge/_archive/reddit/`, out of the active pipeline. The public `.json` endpoint is Cloudflare-blocked even through `cloudscraper`, and Reddit stopped offering free API app registration for AI-related use. Don't resurrect this without a real access path.

**`moxifer_dialog_index.py` is the odd one out**: `dialog.moxifer.com` hosts ~9,000 raw dialogue-engine exports (UUIDs, `.lsf`/`.lsx` paths, engine metadata) rather than prose. Instead of bulk-downloading all of them into `02_trusted`, this script only pulls the searchable manifest into `data/03_refined/dialog_index.json` (path/speaker lookup table), for on-demand fetching later rather than upfront ETL. Keep that distinction if adding to it.

### Save parser (`BroPilot-SaveParser/`)
Needs **two third-party packages** — `lspk.py` imports `lz4.block`, `lz4.frame` and `zstandard` to decompress the `.lsv` container, so the package fails to import without them. Everything else in `src/bropilot/` is stdlib. There is no `requirements.txt` here; install into whichever venv will import the parser (the root `venv/` is what `bropilot_core` uses):
```bash
pip install lz4 zstandard
python BroPilot-SaveParser/scripts/parse_save.py
```
- Save location resolves **per platform** via `save.py`'s `default_save_root()`, which is what `find_saves()`/`latest_save()` use when no path is passed: `MACOS_SAVE_ROOT` (`~/Documents/Larian Studios/Baldur's Gate 3/PlayerProfiles/Public/Savegames/Story` — verified against a real install) on macOS, `DEFAULT_SAVE_ROOT` (the `%LOCALAPPDATA%` path) everywhere else, which is also the least-bad guess for Linux under Proton. `DEFAULT_SAVE_ROOT` is still exported and still the Windows value — don't repoint it. Override either with the `BROPILOT_SAVE_ROOT` env var.
- **`SaveInfo.json`'s "Active Party" includes summons**, not just player characters — a conjured elemental or dryad shows up as a "character". They're distinguishable by `Classes` being null; real members always have a class (with `Sub` empty until level 3). `bropilot_core/serialize.py` filters on that.
- The package (`src/bropilot/`) reads `.lsv` (LSPK container) → `SaveInfo.json`, `meta.lsf`, `Globals.lsf`, `StorySave.bin` (Osiris quest/fact database) — all reverse-engineered binary formats, parsed natively (`lspk.py`, `lsf.py`, `osiris_parser.py`/`osiris_nodes.py`/`osiris_common.py`). `SaveContext` (`models.py`) is the high-level façade over party/quest/item state.
- **Static save data alone only gives level, race, classes and position per character** — no UUID, stats, equipment or inventory. Everything richer (`Equipment`, `Items`, `BuildStats`/abilities/HP/AC/proficiency, `ActionResource` spell slots, passives, resistances) comes from the companion mod's live snapshot; `SaveContext.party`/`SaveContext.items` merge it in via `_apply_dump` when present, and `_match_dump` joins save-side `Origin` (e.g. `"Laezel"`) against the snapshot's `Template` field since `SaveInfo.json` never exposes character UUIDs directly.

#### Companion mod (`exporter/BroPilotExporter/`)
A Script Extender (Norbyte) Lua mod, `BootstrapServer.lua`, that runs live in-game and writes `bropilot_inventory.json` (schema 3) to the Script Extender folder every ~5s (only on change) or on demand via `!bropilot_export`. The repo (`exporter/BroPilotExporter/`) is the only source of truth — always edit there and rebuild, never the installed copies.

Packaging/installing goes through `scripts/build_exporter.py`, not a manual copy:
```bash
python BroPilot-SaveParser/scripts/build_exporter.py           # stage + validate only
python BroPilot-SaveParser/scripts/build_exporter.py --pack    # validate, pack with Divine.exe, install
python BroPilot-SaveParser/scripts/build_exporter.py --check   # inspect the latest in-game snapshot
```
Requires [LSLib](https://github.com/Norbyte/lslib/releases) (`Divine.exe`) + .NET 8 Desktop Runtime; the script looks for `Divine.exe` under `~/Tools/LSLib/`, `~/Downloads/LSLib/`, then `PATH`.

Two path rules that are easy to get wrong and silently fail (no error, mod just doesn't show up):
- `meta.lsx` must be packed at `Mods/<name>/meta.lsx` — that's what the game's Mod Manager scans per `.pak`. It moved there from the package root in this repo's history; don't move it back.
- `ScriptExtender/Config.json` and `ScriptExtender/Lua/` stay at the package **root** — BG3SE scans that path directly, bypassing the Mods/ prefix entirely.
- A loose folder under `Mods/` (not packed as `.pak`) is ignored by the game, and without a `modsettings.lsx` entry Osiris never builds the `ModTable`, so `BootstrapServer.lua` never runs at all.

Re-run `--pack` after every Lua change — the game reads the `.pak`, not the repo. `--check` reports which stat blocks resolved (via the snapshot's `Diagnostics` block) and flags when a Script Extender API route doesn't exist in the current game version — a `0` count there means "route not found," not "character has no data." If a block comes back empty, `!bropilot_probe` in-game dumps the real ECS component/field names for that Script Extender version to `bropilot_probe.json`, since component names vary across versions.

Known limits (don't mistake these for bugs): build stats (abilities, HP/AC, spell slots, passives) don't exist in `Globals.lsf` at all in BG3 4.1.1 — that file's `Character` node only has transform/crime-state/trader flags, and its `Level` field is a map name, not character level. This data only exists via ECS components reachable through the Script Extender, hence the mod.

### UI overlay (`bropilot-ui/`)
Early Electron prototype for an in-game glassmorphism HUD (frameless, transparent, always-on-top window). Not wired to the rest of the repo yet — no calls into `bropilot.py`, the RAG knowledge base, or the save parser's live snapshot; the "assistant" response shown on `Ctrl+0` is a hardcoded 3-second-delay stub in `electron-main.js`, not a real LLM call.
```bash
cd bropilot-ui
npm install
npm run dev        # starts the Vite dev server on :5173
npm run electron   # separate terminal — loads that dev server in the Electron window
```
- The actual overlay markup/styling lives in the **root** `index.html` / `style.css` — that's what `electron-main.js`'s `globalShortcut` handler (`Ctrl+0`) manipulates via `executeJavaScript`, targeting `#bropilot-panel`/`#assistant-text`/`.status-indicator`.
- `src/main.js`, `src/counter.js`, `src/style.css` and the `src/assets/*` images are unused leftover scaffold from `npm create vite` — `index.html` never references `src/main.js` (it loads root `/main.js`, which doesn't exist as a file; nothing currently serves it). Don't assume `src/` is where overlay logic lives or try to "fix" the broken script tag without checking with the collaborator first — this whole subsystem is prototype-stage.

## Conventions to follow when extending the knowledge pipeline

- One scraper + one cleaner per source, named `<source>_scraper.py`/`<source>_parser.py` + `<source>_text_cleaner.py`, matching the existing files.
- Scrapers write to `01_raw`, cleaners to `02_trusted`, both keyed by the same id in the filename (e.g. `forum_938252.html` → `forum_938252.md`).
- New scrapers should skip files that already exist in their output dir (see any existing scraper for the pattern) rather than re-fetching — this is what makes recovery from rate-limits/blocks painless.
- Before assuming a new source's HTML structure, verify it against a live fetch — this codebase's cleaners are built around each site's actual markup (MediaWiki's `mw-parser-output`, UBB.threads' `id="body\d+"`, Steam's `.subSection.detailBox`), not general-purpose HTML-to-text conversion.
