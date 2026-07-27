import os
import re
import time
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter
import json

# Cole seus vídeos aqui
# Lista curada em 2026-07-26: top 10 mais vistos + top 10 mais recentes
# (com "Baldur"/"BG3" no título) de cada canal.
videos_youtube = [
    # DnDDeepDive
    "https://www.youtube.com/watch?v=Q4iw6MPxSDg",  # Top *5* Baldur's Gate 3 Multiclass Builds! Vol. 1
    "https://www.youtube.com/watch?v=6DBOv0QC-Ck",  # Top Multiclass Builds for Baldur's Gate 3: Vol. 2
    "https://www.youtube.com/watch?v=YOgipqWEUV0",  # Optimizing Every Companion in Baldur's Gate 3 (Part 1)
    "https://www.youtube.com/watch?v=PEWnGa-GSJg",  # Top Multiclass Builds for Baldur's Gate: Vol. 3
    "https://www.youtube.com/watch?v=2WQ3omiC9gE",  # Top Multiclass Builds for Baldur's Gate: Vol. 4
    "https://www.youtube.com/watch?v=fCJ0Oftn_ig",  # Update to My BG3 Multiclass Builds Video!
    "https://www.youtube.com/watch?v=sHp-AeBuu0k",  # Optimizing Every Companion for Baldur's Gate 3 (Part 2)
    "https://www.youtube.com/watch?v=sd9WavTJXVE",  # The Ultimate Honor Mode Party: BG3 #10
    "https://www.youtube.com/watch?v=hdK-75LW6Tc",  # The Avatar, Arachnophobia, and The Killer Bard: BG3 Ep #7
    "https://www.youtube.com/watch?v=lEGW2UOdPes",  # The Best Damn Build in Baldur's Gate: BG3 Episode #13
    "https://www.youtube.com/watch?v=dS8rrFCVSBc",  # The Bladesinger and the Hexblade: BG3 Ep #15
    "https://www.youtube.com/watch?v=AWGbLyv0VBc",  # The Ice Breaker: BG3 Episode #11
    "https://www.youtube.com/watch?v=55WkExA19os",  # The Knight Radiant: BG3 Episode #12
    "https://www.youtube.com/watch?v=Yta-cQ5hn5E",  # More *Amazing* Patch 8 Builds! BG3 Ep #16
    "https://www.youtube.com/watch?v=f9uuvqtsz_0",  # The Ultimate Assassin: BG3 Episode #14
    "https://www.youtube.com/watch?v=OfJ9aoEyVuY",  # OP Ice Breaker Build for BG3: Game Play and Tutorial
    "https://www.youtube.com/watch?v=L4bo32uO3ZU",  # Arcane Archer and Crown Pally Tank! BG3 Ep #17
    "https://www.youtube.com/watch?v=gQgpgeEUifs",  # Builds for Halsin, Jaheira, Minthara, and Minsc in BG3
    # ProxyGateTactician
    "https://www.youtube.com/watch?v=V9a38oslKxg",  # 10 Instant Death Cutscenes in Baldur's Gate 3 (Acts 1 and 2 Only)
    "https://www.youtube.com/watch?v=FrhMXqazGYY",  # Can You Beat Baldur's Gate 3 Without Killing Anything?
    "https://www.youtube.com/watch?v=JsX9DzZuuvU",  # Can You Beat Baldur's Gate 3 As a Cat?
    "https://www.youtube.com/watch?v=s3C--0c1U_Y",  # Baldur's Gate 3: 9 Tips and Tricks I Wish I Knew Before I Started Playing (No Spoilers)
    "https://www.youtube.com/watch?v=Y8BNXo3f5Wk",  # Can You Beat Baldur's Gate 3 As The Unluckiest Man In The World?
    "https://www.youtube.com/watch?v=gprjaAjlETg",  # What Happens in Baldur's Gate 3 Without A Player?
    "https://www.youtube.com/watch?v=lD66EtJB-SE",  # Finding the Hidden Fail-Safes in Baldur's Gate 3
    "https://www.youtube.com/watch?v=roTy-5P5T8Q",  # Baldur's Gate 3 - 10 of the Most Secret Encounters You Probably MISSED
    "https://www.youtube.com/watch?v=oPTzx-M-_mo",  # Busting Myths In Baldur's Gate 3
    "https://www.youtube.com/watch?v=CRBKsmKbF4k",  # Can You Collect Every Legendary In Baldur's Gate 3 At Level One?
    "https://www.youtube.com/watch?v=6F67Nw9tXGE",  # Can You Beat Baldur's Gate 3 Using Things No One Uses?
    "https://www.youtube.com/watch?v=-o-xwfSovw0",  # Can You Beat Baldur's Gate 3 Using Only Pink Actions?
    "https://www.youtube.com/watch?v=GLtIitBtb48",  # Can You Beat Baldur's Gate 3 as a Slayer?
    "https://www.youtube.com/watch?v=QKSusAlBiqQ",  # Can You Beat Baldur's Gate 3 Using ONLY Shove?
    "https://www.youtube.com/watch?v=LhIzwKJCcIU",  # Can You Beat Baldur's Gate 3 Without Talking To Others?
    "https://www.youtube.com/watch?v=EkFaX3gSc4g",  # Can You Beat Baldur's Gate 3 Using ONLY Poison Damage?
    "https://www.youtube.com/watch?v=drvanW6rTPk",  # Can You Beat Baldur's Gate 3 Using A Companion Cube?
    "https://www.youtube.com/watch?v=4fVMuwwtWSU",  # Can You Beat Baldur's Gate 3 Using ONLY The Keyboard?
    "https://www.youtube.com/watch?v=HKW2gZ-60Y4",  # Does Baldur's Gate Have Any Boring Places?
    # Cephalopocalypse
    "https://www.youtube.com/watch?v=G_ShgMOS7zg",  # The BEST PARTY In Baldur's Gate 3 - Honor Mode Full Party Build Guide
    "https://www.youtube.com/watch?v=bGupbGD2Fw0",  # The 11 BEST BUILDS in Baldur's Gate 3 - Honour Mode Guide
    "https://www.youtube.com/watch?v=-gnyG9gH-no",  # The BEST CHARACTER in Baldur's Gate 3 - Swords Bard Archer Honour Build Guide
    "https://www.youtube.com/watch?v=AwU71WqBJEE",  # CLASS TIER LIST - Single Class Characters - Baldur's Gate 3 Honour Mode Guide
    "https://www.youtube.com/watch?v=8t8Tmo2IAQ4",  # The BEST CLERIC in Baldur's Gate 3 - [Updated] Shadowheart Honour Build Guide
    "https://www.youtube.com/watch?v=WE8_0fvPuCI",  # The HIGHEST POSSIBLE AC - 57 AC Without Exploits - BG3 Honour Build Guide
    "https://www.youtube.com/watch?v=9JFz6IviB9Y",  # The BEST MULTICLASSES for EVERY CLASS - Baldur's Gate 3 Honour Tier List and Build Guide
    "https://www.youtube.com/watch?v=B9QWSmbl7Eg",  # NEW SUBCLASS TIER LIST - Single Class Characters - BG3 Honour Mode Guide
    "https://www.youtube.com/watch?v=l9EUgdqgMIk",  # The BEST SPELLS in Baldur's Gate 3 - Complete Guide to Spells of Every Level
    "https://www.youtube.com/watch?v=GtljSKjZm-A",  # The BEST CLERIC in Baldur's Gate 3 - Shadowheart Build Guide
    "https://www.youtube.com/watch?v=f7uewDCrrqQ",  # FEATS Tier List - [Updated] Baldur's Gate 3 Honour Mode Guide
    "https://www.youtube.com/watch?v=P-8IG1KkR0U",  # The MOST UNDERRATED SUBCLASSES in Baldur's Gate 3
    "https://www.youtube.com/watch?v=iVOxw7TWYa0",  # BURN IT ALL DOWN - [Updated] Baldur's Gate 3 Fire Sorcerer Honour Build Guide
    "https://www.youtube.com/watch?v=Jk0KrLcfeCA",  # The BEST CONTROL PARTY In Baldur's Gate 3 - Honor Mode Full Party Build Guide
    "https://www.youtube.com/watch?v=4SCUKcM3mZw",  # The MIGHTIEST Party In Baldur's Gate 3 - Honor Mode Devilfoil Mask Full Party Build Guide
    "https://www.youtube.com/watch?v=KR6AfOn4XLM",  # TEN MORE GREAT MODS for Consoles / Macs / PC - BG3 Mod Highlights April 2026
    "https://www.youtube.com/watch?v=Ie2BhFO_VtM",  # COMPLETE Beast Master Ranger Companions Guide - BG3 Mechanics and Summons Deep Dive
    "https://www.youtube.com/watch?v=KaS6zqeSkP8",  # COMPLETE Conjure Elemental Guide - BG3 Mechanics and Summons Deep Dive
    "https://www.youtube.com/watch?v=MknqT-JsyQY",  # This Build Is Actually Four Dogs - Baldur's Gate 3 Honour Build Guide
    "https://www.youtube.com/watch?v=TTZZFDdmAXg",  # COMPLETE Wild Shape Guide - BG3 Druid Mechanics Deep Dive
    # cRPGBro
    "https://www.youtube.com/watch?v=ZNaZOkbFlk4",  # BG3 - SHADOWHEART Cleric TANK Build: 36 AC, FULL RESISTS & AUTO HEAL BUFFS + AoEs - TACTICIAN READY
    "https://www.youtube.com/watch?v=Gnr-zizPcEw",  # BG3 - TANKIEST Nuclear TANK Build: 41 AC + 50% RESISTS & -20 ATK DEBUFF Aura & Auto Buffs TACTICIAN
    "https://www.youtube.com/watch?v=ETjbbHbQuTE",  # BG3 - CIRCLE OF SPORES Druid BUILD: The BEST SUMMONER/NECROMANCER - TACTICIAN READY
    "https://www.youtube.com/watch?v=Bb7Jx8ogKfI",  # BG3 - SWORDS BARD TURRET Build: The HIGHEST ATKS/TURN, 15 SHOTS/Round! Tactician Ready
    "https://www.youtube.com/watch?v=pddy6geisPs",  # BG3 - Highest DMG ELDRITCH BLAST CRIT Build: 700+ DMG/TURN & 50% CRITS - Tactician & PATCH 3 Ready!
    "https://www.youtube.com/watch?v=nNOWTLggypc",  # BG3 - MONK ONE PUNCH Build - 10+ ATKS/TURN, 90+ DMG/FLURRY & 99% TO HIT - Tactician Ready
    "https://www.youtube.com/watch?v=3jH9d4Xb22M",  # BG3 - ASTARION MACHINEGUN Build: 10+ ATKS/TURN - The XBOW ASSASSIN - TACTICIAN Ready!
    "https://www.youtube.com/watch?v=v6QDyE0jILY",  # BG3 - PALALOCK SMITELORD Wyll & MC Build: 370-1K+ DMG & 12 ATKS/TURN
    "https://www.youtube.com/watch?v=JSzt6m_8OdE",  # BG3 - DRAGON SORCERER Build: The BEST AT DMG & CC All in One - TACTICIAN READY
    "https://www.youtube.com/watch?v=ICwwAJ6Dv_0",  # BG3 - KARLACH THROWMANCER Build: 60+ DMG & 7+ ATKS - Why THROWING IS OP - Tactician Ready!
    "https://www.youtube.com/watch?v=3jUgD2uRhfE",  # BG3 - The BEST HONOUR Mode PARTY for 100% WINRATE: 12 ATKs/Char, 4 BUILDS & STRATS
    "https://www.youtube.com/watch?v=VCOMcRGAT-A",  # BG3 - DRUID Circle of the Land BUILD - 30 DC & 100+ AoEs HONOUR & Tactician Ready
    "https://www.youtube.com/watch?v=f8h-jfkXyAU",  # BG3 - JAHEIRA/MC Fighter/DRUID Gish Build: 7+ ATKS & 70+ AoEs, HONOR & TACTICIAN Ready!
    "https://www.youtube.com/watch?v=Ciy9OMCwUX0",  # BG3 - The HIGHEST DC Caster Build: 30+ DC CCs & RNG MANIPULATION! HONOR & Tactician Ready
    "https://www.youtube.com/watch?v=1qEBL2jaeZo",  # BG3 - ELEMENTAL Bender MONK BUILD: RANGED Punches & Spells! HONOUR & Tactician Ready
    "https://www.youtube.com/watch?v=FM-TYwZAsQQ",  # BG3 - ASTARION Arcane TRICKSTER Build: SNEAKS, SPELLS & DICE TRICKS - HONOUR & Tactician Ready
    "https://www.youtube.com/watch?v=doIBPam2-V8",  # BG3- HONOUR Mode Guide: ALL CHANGES & MECHANICS Explained: ACTION Economy & DMG NERFS & More!
    "https://www.youtube.com/watch?v=L5SMSqVbGfc",  # BG3 - Beating BG3 with a TORCH! 90+ TORCH DMG Build - HONOR & Tactician Ready
    "https://www.youtube.com/watch?v=3jKVUZYQ0dA",  # BG3 - New PATCH 6 Released! - The BUFFS, NERFS & QoL Highlights
    "https://www.youtube.com/watch?v=JaoG28QronI",  # BG3 - BIG Patch 8 NEWS: 12 NEW SUBCLASSES OVERVIEW & More!
    # WolfheartFPS
    "https://www.youtube.com/watch?v=-RavauwcjMI",  # 15 Mistakes You Make in Baldur's Gate 3 (Beginner's Guide)
    "https://www.youtube.com/watch?v=rsnlokMpx-c",  # Baldur's Gate 3 - Let's Play Part 1: Infected
    "https://www.youtube.com/watch?v=5OEIosyLymw",  # Baldur's Gate 3 - An Overview of ALL Classes | CHOOSE NOW
    "https://www.youtube.com/watch?v=vaa1r7wHHLU",  # I Played the Full Version of Baldur's Gate 3...
    "https://www.youtube.com/watch?v=4aXgJVy9QyE",  # Baldur's Gate 3 - Ranger Knight Class Build (Dual Wielding Damage Tank)
    "https://www.youtube.com/watch?v=68DVHwiF7vM",  # Baldur's Gate 3 - Let's Play Part 2: Crypts & Goblins
    "https://www.youtube.com/watch?v=OiBA4W841Aw",  # The Most Important Decision in Baldur's Gate 3
    "https://www.youtube.com/watch?v=1Mh9DzEaQJg",  # Going Over One-Star Baldur's Gate 3 Reviews...
    "https://www.youtube.com/watch?v=fdPmeREf724",  # Baldur's Gate 3 News - Larian reveals data & Lae'zel is NOT HAPPY (Player Update)
    "https://www.youtube.com/watch?v=AN0ZDPoS5y4",  # Baldur's Gate 3 - Ultimate Beginner's Guide to Gameplay Mechanics (Learn Now)
    "https://www.youtube.com/watch?v=Ugm-vAVx32o",  # Baldur's Gate 3 - Which New Subclass is for You? CHOOSE NOW Patch 8
    "https://www.youtube.com/watch?v=yyenrLsZODg",  # Larian's New RPG 'Divinity' Will Be Bigger Than BG3 | Everything We Know
    "https://www.youtube.com/watch?v=GU-oRREatpU",  # Baldur's Gate 3 Two FULL Years Later... wow
    "https://www.youtube.com/watch?v=8qefP9U1E4c",  # Baldur's Gate 3 HUGE Patch 8 Update! (Notes & Overview)
    "https://www.youtube.com/watch?v=XALlKYfxeGE",  # Baldur's Gate 4 has been confirmed...
    "https://www.youtube.com/watch?v=j1deyC1n-5k",  # Baldur's Gate 3 - Three Years Later
    "https://www.youtube.com/watch?v=HPauwn6NZDc",  # Baldur's Gate 3 New Community Update! - Player Stats & Next Game Will be 'Loads' of Fun...
    "https://www.youtube.com/watch?v=WIcEWDkv6rg",  # Baldur's Gate 3 Just Got Some BIG Patch 8 News
    "https://www.youtube.com/watch?v=OCl5BxzTMLI",  # Baldur's Gate 3 News - Community Update! (Mods Mods Mods, Game Awards, Challenge Run....)
    "https://www.youtube.com/watch?v=2yrxuzy_TuM",  # Baldur's Gate 3 Unexpected News - HBO TV Series... (What We Know & My Thoughts)
    # LarianStudios
    "https://www.youtube.com/watch?v=XuCfkgaaa08",  # Baldur's Gate 3: Launch Trailer
    "https://www.youtube.com/watch?v=fcmH0c3ywxk",  # Baldur's Gate 3 Accolades Trailer
    "https://www.youtube.com/watch?v=NOWGnC3h9WQ",  # Baldur's Gate 3 - The Game Awards Trailer
    "https://www.youtube.com/watch?v=jNY7AEQ59-8",  # Baldur's Gate 3 Opening Cinematic
    "https://www.youtube.com/watch?v=iWtEDCuc4s4",  # Baldur's Gate 3 Early Access Release Window Announcement Trailer
    "https://www.youtube.com/watch?v=j_5KuItVaoY",  # Breaking down Multiplayer & Cinematics in Baldur's Gate 3 - Update #6
    "https://www.youtube.com/watch?v=sS_fzCWkoHc",  # Baldur's Gate 3 - The Game Awards 2022 Teaser
    "https://www.youtube.com/watch?v=_3nxRjgGcv4",  # Baldur's Gate 3: Of Valour and Lore - Bard
    "https://www.youtube.com/watch?v=42S03eaRics",  # Baldur's Gate 3 - The Panel From Hell 3 - Twitch Plays: A Most Noble Sacrifice
    "https://www.youtube.com/watch?v=CwCyTt8fSAU",  # Baldur's Gate 3: The Final Patch - An Animated Short
    "https://www.youtube.com/watch?v=6w6MJ8FzfjM",  # Baldur's Gate 3: Modding Mayhem - An Animated Short
    "https://www.youtube.com/watch?v=N56xp4tAxuY",  # Baldur's Gate 3: Christmas Gift - An Animated Short
    "https://www.youtube.com/watch?v=2p-5RXAitTI",  # Baldur's Gate 3: Launch Party - An Animated Short
    "https://www.youtube.com/watch?v=_wW4Fdh6zFM",  # Baldur's Gate 3 - PlayStation 5 Pre-Launch Trailer
    "https://www.youtube.com/watch?v=1_nOikdM7oo",  # Baldur's Gate 3: Maggie Robertson on becoming a shapeshifting evil
    "https://www.youtube.com/watch?v=_TmGocqpY0Y",  # Baldur's Gate 3: Release Teaser
    "https://www.youtube.com/watch?v=03TwMYuizoI",  # Baldur's Gate 3: The Greatest Foe - An Animated Short
    # LarianCFH
    "https://www.youtube.com/watch?v=eTWMYiroHC0",  # Five Very Silly Mods To Add To Baldur's Gate 3
    "https://www.youtube.com/watch?v=iHlbagHZR2U",  # How Baldur's Gate 3 Mods Are Curated For Console
    "https://www.youtube.com/watch?v=2qb1_BTa1xg",  # How To Find Your Baldur's Gate 3 Mods
    "https://www.youtube.com/watch?v=ID_N8qgEhFY",  # Connecting With Cross-Play - How to set up Cross-Play with Baldur's Gate 3 Patch 8
    "https://www.youtube.com/watch?v=qaohqWGY4Nk",  # Baldur's Gate 3 Ambiences - Hag Hut Hangout
    "https://www.youtube.com/watch?v=lxO-BoDe6EQ",  # Baldur's Gate 3 Ambiences - Elfsong Sounds
    "https://www.youtube.com/watch?v=OiJSfCEXWog",  # Baldur's Gate 3 Ambiences - Tiefling Time-Out
    "https://www.youtube.com/watch?v=s4DhedOkQZY",  # Baldur's Gate 3 Ambiences - Forest Free-Time
    "https://www.youtube.com/watch?v=-aHDdQCBgSs",  # Baldur's Gate 3 Ambiences - Docks After Dawn
    "https://www.youtube.com/watch?v=PIoS9zBNMto",  # Larian plays Baldur's Gate 3 | Aoife's Dark Urge Part 3 - Trade Secrets (with Jack Surman)
    "https://www.youtube.com/watch?v=JeB8H3wN9tI",  # Baldur's Gate 3 - Chill Demonic Beats To Long Rest To
    "https://www.youtube.com/watch?v=WJ_sB2qlkTs",  # A Very Normal Anniversary Compilation | Larian plays Baldur's Gate 3 (Dark Urge highlights)
    "https://www.youtube.com/watch?v=XkxdCbqfttk",  # Larian plays Baldur's Gate 3 | Aoife's Dark Urge Part 4 - Feared for Alfira (She's Probably Fine)
    "https://www.youtube.com/watch?v=4yi2vSeU054",  # Photo Mode Tips And Tricks For Beginners In Baldur's Gate 3's Patch 8
    "https://www.youtube.com/watch?v=Kh6XxfmHJWA",  # Guide To New Subclasses In Baldur's Gate 3 Patch 8 (Part 3)
    "https://www.youtube.com/watch?v=rJyJt97EOFk",  # Guide To New Subclasses In Baldur's Gate 3 Patch 8 (Part 2)
    "https://www.youtube.com/watch?v=wa9lqZr113w",  # Guide To New Subclasses In Baldur's Gate 3 Patch 8 (Part 1)
    "https://www.youtube.com/watch?v=2RrZaWrZG-8",  # How to Get Started with Baldur's Gate 3 Patch 8 Photo Mode
]

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pasta_raw = os.path.join(base_dir, "data", "01_raw")
pasta_trusted = os.path.join(base_dir, "data", "02_trusted")

print("▶️ Iniciando extração de Transcripts do YouTube...")

def extrair_id_video(url):
    padrao = r'(?:v=|\/)([0-9A-Za-z_-]{11}).*'
    match = re.search(padrao, url)
    return match.group(1) if match else None

# A partir da v1.0 a lib deixou de expor métodos estáticos: precisa instanciar.
ytt_api = YouTubeTranscriptApi()
formatador = TextFormatter()

for url in videos_youtube:
    video_id = extrair_id_video(url)

    if not video_id:
        print(f"⚠️ Não consegui achar o ID na URL: {url}")
        continue

    caminho_trusted = os.path.join(pasta_trusted, f"youtube_{video_id}.md")
    if os.path.exists(caminho_trusted):
        print(f"⏭️  Já existe, pulando: youtube_{video_id}.md")
        continue

    print(f"\nBaixando legendas do vídeo: {video_id}")

    try:
        # Lista todas as legendas disponíveis no vídeo primeiro
        lista_legendas = ytt_api.list(video_id)

        # Tenta pegar em inglês. Se não tiver, pega a primeira que aparecer (ex: PT-BR)
        try:
            legenda = lista_legendas.find_transcript(['en'])
        except Exception:
            legenda = next(iter(lista_legendas))

        # Baixa o texto bruto (FetchedTranscript, não é mais serializável direto em JSON)
        transcript_raw = legenda.fetch()

        caminho_raw = os.path.join(pasta_raw, f"youtube_{video_id}.json")
        with open(caminho_raw, 'w', encoding='utf-8') as f:
            json.dump(transcript_raw.to_raw_data(), f, indent=4, ensure_ascii=False)

        texto_limpo = formatador.format_transcript(transcript_raw)
        texto_blocos = texto_limpo.replace('\n', ' ')
        
        with open(caminho_trusted, 'w', encoding='utf-8') as f:
            f.write(f"# YouTube Guide - Video ID: {video_id}\n\n")
            f.write(f"**URL:** {url}\n\n")
            f.write("## Transcript\n\n")
            f.write(texto_blocos)

        print(f"✅ Ouro extraído e formatado: youtube_{video_id}.md")

    except Exception as e:
        print(f"❌ Erro ao baixar legenda do vídeo {video_id}: {e}")

    time.sleep(1)

print("\n🚀 Pipeline do YouTube concluído!")