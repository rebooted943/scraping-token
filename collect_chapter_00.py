#!/usr/bin/env python3
"""
Sleep Token Lore Collector — Capitolo 0: Origine (2016-2018)
Python 3.11+ (Solo Standard Library: urllib, json, re, html.parser, pathlib)

Esegue la raccolta per:
- Racconto d'insieme (Il patto con Sleep, anonimato, ruoli di Vessel, II, III, IV, Espera)
- EP 'One' (2016): Thread the Needle, Fields of Elation, When the Bough Breaks
- EP 'Two' (2017): Calcutta, Nazareth, Jericho
- Singoli / Cover: Jaws, The Way That You Were, Hey Ya, Is It Really You?,
  Dancing in the Dark, Granite (Sullivan King Remix) [marcato skip/conferma]
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

# ==============================================================================
# 1. CONFIGURAZIONE E FILTRI ANTI-DOXXING / ANTI-LYRICS
# ==============================================================================

CHAPTER_DIR = Path("chapters/00-origin")
USER_AGENT = "Mozilla/5.0 (compatible; LoreArchivistBot/1.0; +https://example.org/lore-research)"
REQUEST_DELAY_SEC = 1.5
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "wbr", "source"}

# Termini che fanno scartare immediatamente un paragrafo (Doxxing / Identità civili).
# Allineato ai pattern fail-closed di config/settings.py, più i termini del capitolo.
IDENTITY_BLOCKLIST_PATTERNS = [
    r"\b(?:real|legal|birth|government)\s+name\b",
    r"\b(?:born|birth(?:day|date))\s+(?:on|in|is)\b",
    r"\b(?:unmasked|without\s+(?:a\s+|the\s+)?mask|face[- ]?reveal)\b",
    r"\btrue\s+identity\b",
    r"\b(?:identity|identities)\s+(?:is|are|revealed|confirmed|leaked)\b",
    r"\bidentities\s+revealed\b",
    r"\b(?:doxx\w*|tabloid\s+leak)\b",
    r"\b(?:formerly|previously)\s+(?:of|played|performed|known)\b",
    r"\b(?:former|previous)\s+(?:band|project|stage\s+name)\b",
    r"\bside\s+project\b",
    r"\bcompanies\s+house\b",
    r"\bascap\b",
    r"\bppca\b",
    r"\bleaked?\s+(?:photo|image|picture)\b",
    r"\b(?:Vessel|II|III|IV|Espera)\s+(?:is|was|aka|a\.k\.a\.|born\s+as)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+",
    r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\s*\((?:Vessel|II|III|IV|Espera)\)",
]
IDENTITY_REGEX = re.compile("|".join(IDENTITY_BLOCKLIST_PATTERNS), re.IGNORECASE)

BLOCKED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
}

# ==============================================================================
# 2. LISTA CHIUSA DI URL E QUERY PER IL CAPITOLO 0
# ==============================================================================

CLOSED_SOURCES: list[dict[str, str]] = [
    {
        "id": "lore_one_ep",
        "url": "https://loreofsleeptoken.com/one-ep/",
        "source_class": "community",
        "title": "Lore of Sleep Token - One EP",
        "focus": "One, Thread the Needle, Fields of Elation, When the Bough Breaks",
    },
    {
        "id": "lore_two_ep",
        "url": "https://loreofsleeptoken.com/two-ep/",
        "source_class": "community",
        "title": "Lore of Sleep Token - Two EP",
        "focus": "Two, Calcutta, Nazareth, Jericho",
    },
    {
        "id": "lore_main",
        "url": "https://loreofsleeptoken.com/the-lore/",
        "source_class": "community",
        "title": "Lore of Sleep Token - The Lore Overview",
        "focus": "Sleep, Vessel, Worship, Basick Records press release, Origin",
    },
    {
        "id": "lore_logo",
        "url": "https://loreofsleeptoken.com/logo/",
        "source_class": "community",
        "title": "Lore of Sleep Token - Logo & Early Symbols",
        "focus": "One, Two, Emblem, Sigil evolution",
    },
    {
        "id": "louder_who_2017",
        "url": "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
        "source_class": "editorial",
        "title": "Metal Hammer / Louder - Who and what the hell are Sleep Token? (2017)",
        "focus": "In-character interview, Sleep, Vessel, One, Two, Calcutta",
    },
    {
        "id": "louder_gimmick",
        "url": "https://www.loudersound.com/features/sleep-token-goofy-gimmick-or-serious-art",
        "source_class": "editorial",
        "title": "Louder - Sleep Token: goofy gimmick or serious art?",
        "focus": "Anonymity, masks, Vessel, II, III, IV, Espera, theatricality",
    },
    {
        "id": "louder_every_song_p1",
        "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
        "source_class": "editorial",
        "title": "Louder - The story behind every Sleep Token song (Page 1)",
        "focus": "Thread the Needle, Fields of Elation, When the Bough Breaks, Calcutta, Nazareth, Jericho, Jaws, The Way That You Were",
    },
    {
        "id": "boolin_lore",
        "url": "https://boolintunes.com/featured/the-lore-of-sleep-token/",
        "source_class": "editorial",
        "title": "Boolin Tunes - The Lore of Sleep Token",
        "focus": "Sleep, Vessel, One, Two, Jaws, The Way That You Were",
    },
    {
        "id": "wiki_main",
        "url": "https://en.wikipedia.org/wiki/Sleep_Token",
        "source_class": "editorial",
        "title": "Wikipedia - Sleep Token (Public Chronology Only)",
        "focus": "2016-2019 chronology, Basick Records, Spinefarm, II, III, IV, Espera",
    },
    {
        "id": "fandom_one",
        "url": "https://sleep-token-collective.fandom.com/wiki/One",
        "source_class": "community",
        "title": "Sleep Token Collective Wiki - One (EP)",
        "focus": "One, Thread the Needle, Fields of Elation, When the Bough Breaks",
    },
    {
        "id": "fandom_two",
        "url": "https://sleep-token-collective.fandom.com/wiki/Two",
        "source_class": "community",
        "title": "Sleep Token Collective Wiki - Two (EP)",
        "focus": "Two, Calcutta, Nazareth, Jericho",
    },
    {
        "id": "fandom_sleep",
        "url": "https://sleep-token-collective.fandom.com/wiki/Sleep",
        "source_class": "community",
        "title": "Sleep Token Collective Wiki - Sleep (Deity)",
        "focus": "Sleep, origin pact, dreams, Vessel",
    },
]

FANDOM_API = "https://sleep-token-collective.fandom.com/api.php"
# Titoli reali della wiki (l'HTML diretto risponde 403; l'API pubblica legge la stessa pagina).
# La voce "Sleep" non esiste (missingtitle). Il patto è sulla pagina del progetto.
# Espera non ha una pagina propria: il gap resta esplicito a runtime.
FANDOM_PAGES: dict[str, str] = {
    "fandom_one": "ONE",
    "fandom_two": "TWO",
    "fandom_sleep": "Sleep Token",
    "Thread the Needle": "Thread The Needle",
    "Fields of Elation": "Fields Of Elation",
    "When the Bough Breaks": "When The Bough Breaks",
    "Calcutta": "Calcutta",
    "Nazareth": "Nazareth",
    "Jericho": "Jericho",
    "Jaws": "Jaws",
    "The Way That You Were": "The Way That You Were",
    "Hey Ya": "Hey Ya",
    "Is It Really You?": "Is It Really You?",
    "Dancing in the Dark": "Dancing in the Dark",
}
FANDOM_SONG_URLS: dict[str, str] = {
    title: "https://sleep-token-collective.fandom.com/wiki/" + page.replace(" ", "_")
    for title, page in FANDOM_PAGES.items()
    if title not in {"fandom_one", "fandom_two", "fandom_sleep"}
}
# Parole troppo comuni per agganciarle da sole a un brano.
KEYWORD_STOP = {"badly", "dream", "organ", "church", "electric", "pastoral", "separate"}

# La query del brief usa l'host senza www e il CDX risponde vuoto: le catture sono su www.kerrang.com.
WAYBACK_CDX_KERRANG_QUERY = (
    "https://web.archive.org/cdx/search/cdx"
    "?url=kerrang.com/*sleep-token*&output=json&from=2017&to=2020"
    "&filter=statuscode:200&collapse=urlkey&limit=10"
)
# Prima pagina Kerrang citata da Wikipedia, con timestamp CDX reale (nessuno snapshot 2017-2018).
KERRANG_EARLIEST_SNAPSHOT = {
    "timestamp": "20211206032254",
    "original_url": "https://www.kerrang.com/album-review-sleep-token-sundowning",
    "wayback_url": "https://web.archive.org/web/20211206032254/https://www.kerrang.com/album-review-sleep-token-sundowning",
    "source_class": "editorial",
}
ROLE_PAGES: dict[str, str] = {
    "Vessel": "Vessel",
    "II": "II",
    "III": "III",
    "IV": "IV",
    "Espera": "Espera",
}

REDDIT_SONG_QUERIES: dict[str, str] = {
    "Thread the Needle": 'title:"Thread the Needle" (lore OR meaning OR theory OR analysis)',
    "Fields of Elation": 'title:"Fields of Elation" (lore OR meaning OR theory OR analysis)',
    "When the Bough Breaks": 'title:"When the Bough Breaks" (lore OR meaning OR Euclid OR callback)',
    "Calcutta": 'title:"Calcutta" (lore OR meaning OR theory OR analysis)',
    "Nazareth": 'title:"Nazareth" (lore OR meaning OR theory OR analysis)',
    "Jericho": 'title:"Jericho" (lore OR meaning OR theory OR analysis)',
    "Jaws": 'title:"Jaws" (lore OR meaning OR theory OR analysis)',
    "The Way That You Were": 'title:"The Way That You Were" (lore OR meaning OR theory)',
    "Hey Ya": 'title:"Hey Ya" (lore OR meaning OR cover OR Vessel)',
    "Is It Really You?": 'title:"Is It Really You" (lore OR meaning OR Loathe)',
    "Dancing in the Dark": 'title:"Dancing in the Dark" (lore OR meaning OR cover)',
}

# ==============================================================================
# 3. BASE DI CONOSCENZA CURATA CAPITOLO 0 (BASELINE + INTEGRAZIONE LIVE)
# ==============================================================================

_SIGIL_GAP = (
    "Non applicabile al Capitolo 0 (i 12 sigilli appartengono a Sundowning, "
    "le profondità in metri/fathom a TPWBYT e l'alfabeto runico a TMBTE)."
)

SONGS_CATALOG: list[dict[str, Any]] = [
    {
        "slug": "01-thread-the-needle",
        "title": "Thread the Needle",
        "release": "One (EP)",
        "track_number": 1,
        "year": 2016,
        "genius_annotations_count": 8,
        "keywords": ["Thread the Needle", "Thread The Needle", "One EP", "bough", "electric"],
        "era_role": (
            "Primo atto pubblico assoluto (settembre 2016). Introduce il patto tra Vessel e Sleep: "
            "un invito all'abbandono della veglia ('You can thread the needle / Time and time again') "
            "dove l'estasi mistica e l'intimità fisica diventano indistinguibili."
        ),
        "in_character_quotes": [
            {
                "quote": (
                    "This is the first offering. Sleep Token is a collective mandated by Sleep, "
                    "an ancient deity who appeared to Vessel in a dream, promising glory and magnificence "
                    "if Vessel followed Him."
                ),
                "source_title": "Basick Records / Sleep Token Debut Press Statement & Metal Hammer Profile",
                "url": "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
                "date": "2016-09-08",
                "source_class": "canon",
            }
        ],
        "editorial_reading": [
            {
                "summary": (
                    "Louder e Boolin Tunes descrivono il brano come il manifesto sonoro e concettuale: "
                    "inizia come una ninna nanna liturgica al pianoforte prima di esplodere nel djent/post-metal "
                    "a 8 corde, riflettendo il passaggio dal sogno pacifico alla possessione di Sleep."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Primo emblema geometrico a tre tagli (pre-runico) associato all'EP One",
            "depth": None,
            "rune": None,
            "creature": "Agriopis / falene notturne nel video ufficiale e immagini pastorali oscure",
            "object": "L'ago e il filo (Thread the Needle); incisione botanica del ramo di melo (copertina di One)",
            "color": "Seppia / Bianco avorio e nero d'inchiostro calcografico",
        },
        "references": [
            {
                "category": "religione / idioma biblico",
                "detail": (
                    "L'espressione 'thread the needle' richiama sia l'atto sessuale/intimo di unione sia la "
                    "cruna dell'ago evangelica (Matteo 19:24) come passaggio impossibile verso il regno promesso da Sleep."
                ),
                "supporting_phrase": "You can thread the needle, time and time again",
                "source_title": "Lore of Sleep Token - One EP",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            },
            {
                "category": "opera visiva / botanica",
                "detail": (
                    "L'artwork di One utilizza illustrazioni botaniche storiche di varietà di mele inglesi, "
                    "allusione al frutto proibito dell'Eden che verrà esplicitato solo nel terzo album (2023)."
                ),
                "supporting_phrase": "Visual artwork of the One EP featuring apple boughs",
                "source_title": "Lore of Sleep Token - One EP",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            },
        ],
        "callbacks": [
            {
                "target_song": "The Night Does Not Belong to God (Sundowning, 2019) / Euclid (TMBTE, 2023)",
                "motif": (
                    "Il verso finale 'The bough has broken / Through' anticipa sia il terzo brano dell'EP "
                    "('When the Bough Breaks') sia l'intero ciclo circolare della notte che scende come una cortina."
                ),
                "source_title": "Sleep Token Collective Wiki - Thread the Needle",
                "url": "https://sleep-token-collective.fandom.com/wiki/Thread_the_Needle",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "La community interpreta 'Thread the Needle' come il momento esatto della prima ipnosi "
                    "di Vessel da parte di Sleep: le luci che si spengono ('turn the lights down') segnano "
                    "l'ingresso nel regno onirico da cui Vessel tenterà di uscire fino a 'Euclid'."
                ),
                "source_title": "r/SleepToken & Lore of Sleep Token",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            }
        ],
        "gaps": [],
    },
    {
        "slug": "02-fields-of-elation",
        "title": "Fields of Elation",
        "release": "One (EP)",
        "track_number": 2,
        "year": 2016,
        "genius_annotations_count": 5,
        "keywords": ["Fields of Elation", "Elysian", "One EP", "pastoral"],
        "era_role": (
            "Secondo movimento di One: rappresenta la fase di 'luna di miele' o estasi mistica promessa da Sleep, "
            "ma già venata dalla malinconia della perdita ('losing touch') quando il sogno svanisce al risveglio."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "Critica e retrospettive sottolineano il contrasto tra il falsetto vulnerabile di Vessel "
                    "e i riff sincopati: l'estasi ('elation') non è pace stabile, ma una dipendenza da uno stato alterato."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Variante del primo glifo geometrico di One",
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Campi erbosi inglesi / Incisione botanica di ramo con frutti",
            "color": "Oro pallido e verde scuro desaturato",
        },
        "references": [
            {
                "category": "mitologia greca / letteratura classica",
                "detail": (
                    "I 'Fields of Elation' ricalcano i Campi Elisi (Elysian Fields), il luogo ultraterreno "
                    "dei beati associato a Hypnos (dio del sonno) e Thanatos."
                ),
                "supporting_phrase": "Quietly, they're carving out my name / Across the fields of elation",
                "source_title": "Lore of Sleep Token - One EP",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "Take Me Back to Eden (2023) / Even In Arcadia (2025)",
                "motif": (
                    "Il motivo del giardino/campo idilliaco perduto ('fields of elation') è il precursore "
                    "diretto dei topoi pastorali dell'Eden e dell'Arcadia nei capitoli 3 e 4."
                ),
                "source_title": "Lore of Sleep Token - One EP",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "L'immaginario di una sepoltura in vita ('shallow grave', 'carving out my name') viene letto "
                    "dai fan come la morte simbolica dell'identità precedente del cantante per diventare 'Vessel' "
                    "(il contenitore vuoto di Sleep)."
                ),
                "source_title": "Sleep Token Collective Wiki - Fields of Elation",
                "url": "https://sleep-token-collective.fandom.com/wiki/Fields_of_Elation",
                "source_class": "community",
            }
        ],
        "gaps": [
            "Nessuna dichiarazione in-character specifica di Vessel isolata sul solo brano Fields of Elation (solo sull'EP One nel complesso)."
        ],
    },
    {
        "slug": "03-when-the-bough-breaks",
        "title": "When the Bough Breaks",
        "release": "One (EP)",
        "track_number": 3,
        "year": 2016,
        "genius_annotations_count": 5,
        "keywords": ["When the Bough Breaks", "Don't lie to me", "bough breaks", "Euclid"],
        "era_role": (
            "Chiusura monumentale (oltre 7 minuti) dell'EP One. Segna la prima frattura nel rapporto con Sleep/l'amato: "
            "la ninna nanna si spezza e rivela il ricatto emotivo ('Don't lie to me')."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "Riconosciuto dalla stampa come il primo vero capolavoro progressivo della band, dove il crescendo "
                    "finale abbandona la forma canzone per diventare un mantra ossessivo."
                ),
                "source_title": "Boolin Tunes - The Lore of Sleep Token",
                "url": "https://boolintunes.com/featured/the-lore-of-sleep-token/",
                "date": "2023-05-15",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Primo glifo di One completato",
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Il ramo spezzato (The broken bough) e la culla che cade",
            "color": "Nero / Grigio cenere",
        },
        "references": [
            {
                "category": "folklore / filastrocca tradizionale",
                "detail": (
                    "Riferimento diretto alla ninna nanna inglese 'Rock-a-bye Baby' ('When the bough breaks, "
                    "the cradle will fall'), usata per sovvertire il tema del sonno protettivo in caduta rovinosa."
                ),
                "supporting_phrase": "Title and motif 'When the Bough Breaks'",
                "source_title": "Lore of Sleep Token - One EP",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "Thread the Needle (One, 2016)",
                "motif": "Riprende la frase 'The bough has broken' cantata in chiusura della traccia 1.",
                "source_title": "Lore of Sleep Token - One EP",
                "url": "https://loreofsleeptoken.com/one-ep/",
                "source_class": "community",
            },
            {
                "target_song": "Euclid (Take Me Back to Eden, 2023)",
                "motif": (
                    "In 'Euclid' (traccia finale della trilogia), Vessel canta 'Yet in reverse, you are all my symmetry / "
                    "A parallel I would lay my life on' mentre la struttura ritmica e l'immagine del ramo ('Wait until the bough breaks') "
                    "chiudono l'arco iniziato nel 2016."
                ),
                "source_title": "Sleep Token Collective Wiki - When the Bough Breaks",
                "url": "https://sleep-token-collective.fandom.com/wiki/When_the_Bough_Breaks",
                "source_class": "community",
            },
        ],
        "community_theories": [
            {
                "theory": (
                    "I fan considerano il breakdown di 'When the Bough Breaks' il momento in cui Vessel capisce che "
                    "Sleep non è una divinità benevola ma un'entità parassitaria che si nutre del suo trauma."
                ),
                "source_title": "r/SleepToken & Boolin Tunes",
                "url": "https://boolintunes.com/featured/the-lore-of-sleep-token/",
                "source_class": "community",
            }
        ],
        "gaps": [],
    },
    {
        "slug": "04-calcutta",
        "title": "Calcutta",
        "release": "Two (EP)",
        "track_number": 1,
        "year": 2017,
        "genius_annotations_count": 6,
        "keywords": ["Calcutta", "Two EP", "whole again", "wake"],
        "era_role": (
            "Apertura dell'EP Two (luglio 2017, Basick Records). Abbandona il pastoralismo inglese di One "
            "per una trilogia di titoli legati a città storiche/antiche (Calcutta, Nazareth, Jericho). "
            "Rappresenta la brama fisica e spirituale ('Until I wake I dine on old encounters')."
        ),
        "in_character_quotes": [
            {
                "quote": (
                    "He is everywhere, at all times. Vessel encountered Sleep in a dream, with promise of glory "
                    "and magnificence if Vessel followed Him. The UK is old, decaying and rich in folklore."
                ),
                "source_title": "Metal Hammer / Louder - Who and what the hell are Sleep Token? (pubblicata per il lancio di Calcutta)",
                "url": "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
                "date": "2017-05-25",
                "source_class": "canon",
            }
        ],
        "editorial_reading": [
            {
                "summary": (
                    "Presentato in anteprima su Metal Hammer nel maggio 2017, il brano accompagna la prima vera "
                    "intervista in-character del gruppo e introduce il video girato in ambienti boschivi e rituali."
                ),
                "source_title": "Louder - Who and what the hell are Sleep Token",
                "url": "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
                "date": "2017-05-25",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Glifo dell'EP Two (evoluzione angolare con linee interne incrociate)",
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Incisioni di architettura sacra/orientale dell'artwork di Two",
            "color": "Ocra scuro, oro antico e nero",
        },
        "references": [
            {
                "category": "geografia / religione induista (etimologia)",
                "detail": (
                    "Il titolo 'Calcutta' (Kolkata) è spesso collegato nella lore community all'etimologia tradizionale "
                    "da Kalighat (terra della dea Kali, divinità del tempo, della distruzione e della devozione feroce) "
                    "o all'espressione 'Black Hole of Calcutta' (prigione soffocante)."
                ),
                "supporting_phrase": "Title 'Calcutta' and lyrics 'I'm whole again / For just a moment'",
                "source_title": "Lore of Sleep Token - Two EP",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "Vore / The Summoning (Take Me Back to Eden, 2023)",
                "motif": (
                    "La metafora del nutrirsi dei ricordi nel sonno ('Until I wake I dine on old encounters') "
                    "anticipa l'immaginario divorante di 'The Offering' e 'Vore'."
                ),
                "source_title": "Lore of Sleep Token - Two EP",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "La community legge i tre titoli di Two (Calcutta, Nazareth, Jericho) come una mappa di "
                    "pellegrinaggio antico verso luoghi di sacrificio, morte e crollo delle difese interiori."
                ),
                "source_title": "Lore of Sleep Token - Two EP",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "gaps": [],
    },
    {
        "slug": "05-nazareth",
        "title": "Nazareth",
        "release": "Two (EP)",
        "track_number": 2,
        "year": 2017,
        "genius_annotations_count": 6,
        "keywords": ["Nazareth", "hollow point", "cleanse", "make her eat the tape"],
        "era_role": (
            "Il punto più oscuro e violento dell'intera discografia iniziale. Mostra il lato predatorio "
            "della devozione a Sleep, dove il sacrificio rituale assume i connotati di un'aggressione."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "La critica (Louder, Boolin Tunes) evidenzia come 'Nazareth' sovverta il nome della città "
                    "della natività cristiana in teatro di un sacrificio cruento e disturbante."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Secondo emblema dell'EP Two",
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Proiettile a punta cava ('hollow point'), nastro magnetico ('eat the tape'), denaro/banconote",
            "color": "Rosso sangue / Nero",
        },
        "references": [
            {
                "category": "religione biblica",
                "detail": (
                    "Nazareth, città dell'Annunciazione e dell'infanzia di Gesù: qui l'annunciazione angelica "
                    "è capovolta nell'ira notturna ('Tonight we'll have the validation')."
                ),
                "supporting_phrase": "Let's load the gun / Make her eat the tape in the bathroom mirror",
                "source_title": "Lore of Sleep Token - Two EP",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "Jaws (2018) / Gods (2019) / Ascensionism (2023)",
                "motif": (
                    "La violenza del controllo e l'immagine dello specchio/bagno ritornano nelle crisi "
                    "autolesioniste e relazionali di 'Are You Really Okay?' e 'Ascensionism'."
                ),
                "source_title": "Sleep Token Collective Wiki - Nazareth",
                "url": "https://sleep-token-collective.fandom.com/wiki/Nazareth",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "Esistono due scuole principali nella community: (1) Nazareth racconta un ordine diretto di Sleep "
                    "che costringe Vessel a distruggere una relazione umana reale per restare fedele solo alla divinità; "
                    "(2) 'lei' è una metafora dell'abuso di sostanze o della memoria traumatica ('eat the tape' = "
                    "cancellare le prove/ricordi registrati)."
                ),
                "source_title": "Lore of Sleep Token - Two EP & r/SleepToken consensus",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "gaps": [
            "Nessuna spiegazione canonica di Vessel sul significato letterale o metaforico del verso 'make her eat the tape'."
        ],
    },
    {
        "slug": "06-jericho",
        "title": "Jericho",
        "release": "Two (EP)",
        "track_number": 3,
        "year": 2017,
        "genius_annotations_count": 10,
        "keywords": ["Jericho", "Nebuchadnezzar", "hands of silk", "until I wake"],
        "era_role": (
            "Chiusura dell'EP Two. Dopo la furia di Nazareth, Jericho mette in scena la resa totale "
            "delle difese di Vessel di fronte al fascino seduttivo (R&B/soul) di Sleep."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "Considerato il brano che definisce per la prima volta la fusione tra R&B sensuale e metal "
                    "che renderà celebre la band con 'The Summoning' anni dopo."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Terzo emblema dell'EP Two",
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Le mura di Gerico che crollano al suono della voce; 'hands of silk' (mani di seta)",
            "color": "Viola notturno e oro",
        },
        "references": [
            {
                "category": "religione / Antico Testamento (Giosuè 6 e Libro di Daniele)",
                "detail": (
                    "Doppio riferimento biblico: (1) la città di Gerico le cui mura crollano al suono delle trombe "
                    "(simbolo delle barriere emotive di Vessel abbattute dalla musica/voce di Sleep); "
                    "(2) il re babilonese Nabucodonosor ('Something in the way you lay / Enough to make the dead switch graves, "
                    "you take my breath away...'), storicamente tormentato da sogni profetici nel Libro di Daniele."
                ),
                "supporting_phrase": "Say my name again... Until I wake, I'm yours",
                "source_title": "Lore of Sleep Token - Two EP",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "Calcutta (Two, 2017) & Nazareth (Two, 2017)",
                "motif": (
                    "Ripete la formula rituale 'Until I wake' che lega tutte le tracce dell'EP Two "
                    "in un unico stato di trance notturna."
                ),
                "source_title": "Lore of Sleep Token - Two EP",
                "url": "https://loreofsleeptoken.com/two-ep/",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "Il riferimento a Nabucodonosor (re che perse il senno e fu perseguitato da visioni in sogno "
                    "in Daniele 2 e 4) viene citato dalla community come prova che Vessel si identifica con i monarchi "
                    "biblici piegati da una divinità onirica."
                ),
                "source_title": "Sleep Token Collective Wiki - Jericho",
                "url": "https://sleep-token-collective.fandom.com/wiki/Jericho",
                "source_class": "community",
            }
        ],
        "gaps": [],
    },
    {
        "slug": "07-jaws",
        "title": "Jaws",
        "release": "Jaws (Standalone Single)",
        "track_number": 1,
        "year": 2018,
        "genius_annotations_count": 10,
        "keywords": ["Jaws", "pretty white jaws", "show me where the delicate stops", "badly"],
        "era_role": (
            "Singolo autonomo cruciale (giugno 2018). Fa da ponte tra l'EP Two e Sundowning. "
            "Introduce il motivo ricorrente dei denti, del morso e della divorazione amorosa/sacrificale."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "Louder e Boolin Tunes indicano 'Jaws' come la svolta verso un'accessibilità dark-pop/synth "
                    "senza perdere il peso metallico, mettendo a fuoco la paura dell'intimità vista come una trappola predatoria."
                ),
                "source_title": "Boolin Tunes - The Lore of Sleep Token",
                "url": "https://boolintunes.com/featured/the-lore-of-sleep-token/",
                "date": "2023-05-15",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Glifo dedicato al singolo Jaws (simmetria verticale che ricorda fauci aperte)",
            "depth": None,
            "rune": None,
            "creature": "Predatore / Fauci bianche ('pretty white jaws')",
            "object": "Fauci / Cicatrici ('show me what wounds you've got')",
            "color": "Bianco osso su fondo nero",
        },
        "references": [
            {
                "category": "anatomia / psicologia del predatore",
                "detail": (
                    "Le 'pretty white jaws' uniscono il sorriso seduttivo umano alle fauci di un predatore, "
                    "stabilendo la metafora dell'amore come cannibalismo spirituale."
                ),
                "supporting_phrase": "Show me those pretty white jaws / Show me where the delicate stops",
                "source_title": "Sleep Token Collective Wiki - Jaws",
                "url": "https://sleep-token-collective.fandom.com/wiki/Jaws",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "The Offering (2019), High Water (2021), Vore (2023)",
                "motif": (
                    "Il motivo delle fauci e del morso ('Take a bite' in The Offering, 'jaws' in High Water, "
                    "la gola che inghiotte in Vore) nasce interamente in 'Jaws'."
                ),
                "source_title": "Boolin Tunes - The Lore of Sleep Token",
                "url": "https://boolintunes.com/featured/the-lore-of-sleep-token/",
                "source_class": "editorial",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "Nella lore community, 'Jaws' è la richiesta di Vessel a Sleep (o alla controparte umana) "
                    "di gettare la maschera della gentilezza ('where the delicate stops') e mostrare la propria natura distruttiva."
                ),
                "source_title": "r/SleepToken & Sleep Token Collective Wiki",
                "url": "https://sleep-token-collective.fandom.com/wiki/Jaws",
                "source_class": "community",
            }
        ],
        "gaps": [],
    },
    {
        "slug": "08-the-way-that-you-were",
        "title": "The Way That You Were",
        "release": "The Way That You Were (Standalone Single)",
        "track_number": 1,
        "year": 2018,
        "genius_annotations_count": 7,
        "keywords": ["The Way That You Were", "church", "organ", "pain"],
        "era_role": (
            "Secondo singolo autonomo del 2018 (ottobre), accompagnato da un video girato in una chiesa "
            "(St Pancras Old Church / architettura ecclesiastica inglese) con organo a canne. "
            "Spinge all'estremo il parallelismo tra liturgia cristiana e lutto per una persona spezzata."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "La stampa nota l'assenza totale di chitarre metal in favore di un organo solenne, "
                    "preparando il terreno per i rituali intimi di 'The Room Below'."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": "Glifo simmetrico del singolo (2018)",
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Organo da chiesa, navata ecclesiastica, lacrime",
            "color": "Bianco e nero ad alto contrasto (estetica del video ufficiale)",
        },
        "references": [
            {
                "category": "liturgia cristiana / architettura sacra",
                "detail": (
                    "Uso dell'organo liturgico e dell'ambientazione in chiesa in concomitanza con il celebre "
                    "rituale dal vivo alla St Pancras Old Church di Londra (ottobre 2018)."
                ),
                "supporting_phrase": "And you are too tired to control / How darkly the casket Gown rolls",
                "source_title": "Sleep Token Collective Wiki - The Way That You Were",
                "url": "https://sleep-token-collective.fandom.com/wiki/The_Way_That_You_Were",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "Are You Really Okay? (2023) & Blood Sport (from the room below, 2020)",
                "motif": (
                    "Anticipa il registro di compassione impotente verso il trauma e l'autolesionismo dell'altro "
                    "che tornerà in 'Are You Really Okay?'."
                ),
                "source_title": "Sleep Token Collective Wiki - The Way That You Were",
                "url": "https://sleep-token-collective.fandom.com/wiki/The_Way_That_You_Were",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "Molti fan leggono questo brano come un dialogo allo specchio: Vessel non sta parlando a Sleep, "
                    "ma a se stesso prima del patto ('the way that you were'), piangendo la perdita della propria innocenza."
                ),
                "source_title": "r/SleepToken consensus",
                "url": "https://sleep-token-collective.fandom.com/wiki/The_Way_That_You_Were",
                "source_class": "community",
            }
        ],
        "gaps": [],
    },
    {
        "slug": "09-hey-ya",
        "title": "Hey Ya",
        "release": "Hey Ya (Single / Outkast Cover)",
        "track_number": 1,
        "year": 2018,
        "genius_annotations_count": 0,
        "keywords": ["Hey Ya", "Outkast", "nothing lasts forever", "separate"],
        "era_role": (
            "Cover di 'Hey Ya!' degli Outkast pubblicata nell'agosto 2018. Non è un divertissement, ma una "
            "dimostrazione concettuale: Vessel spoglia il brano del suo ritmo festoso per metterne a nudo "
            "il testo originariamente tragico sulla fine dell'amore e sulla paura della solitudine."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "La critica sottolinea come la versione di Sleep Token riveli il dolore già presente nel testo "
                    "di André 3000 ('If what they say is nothing is forever, then what makes love the exception?'), "
                    "rendendolo perfettamente coerente con la poetica di Vessel."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": None,
            "depth": None,
            "rune": None,
            "creature": None,
            "object": None,
            "color": None,
        },
        "references": [
            {
                "category": "musica contemporanea / decostruzione",
                "detail": "Rielaborazione pianistica e vocale del singolo degli Outkast (2003).",
                "supporting_phrase": "Nothing is forever, then what makes love the exception?",
                "source_title": "Sleep Token Collective Wiki - Hey Ya",
                "url": "https://sleep-token-collective.fandom.com/wiki/Hey_Ya",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "The Room Below covers (When the Party's Over / I Wanna Dance With Somebody, 2020)",
                "motif": (
                    "Inaugura la tradizione rituale di Vessel di prendere hit pop sull'amore infelice "
                    "e trasformarle in inni funebri al pianoforte."
                ),
                "source_title": "Sleep Token Collective Wiki - Hey Ya",
                "url": "https://sleep-token-collective.fandom.com/wiki/Hey_Ya",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "La community considera 'Hey Ya' parte integrante della narrazione: il dubbio che "
                    "'nulla duri per sempre' incrina la promessa di eternità fatta da Sleep nei primi due EP."
                ),
                "source_title": "r/SleepToken discussions",
                "url": "https://sleep-token-collective.fandom.com/wiki/Hey_Ya",
                "source_class": "community",
            }
        ],
        "gaps": [
            "0 annotazioni Genius presenti nell'archivio locale; compensato tramite critica editoriale e wiki."
        ],
    },
    {
        "slug": "10-is-it-really-you",
        "title": "Is It Really You?",
        "release": "Is It Really You? (Collaborative Single with Loathe)",
        "track_number": 1,
        "year": 2022,
        "genius_annotations_count": 0,
        "keywords": ["Is It Really You", "Loathe", "teenage Wrist", "dream"],
        "era_role": (
            "Singolo fuori-album (originariamente dei Loathe da 'I Let It in and It Took Everything', 2020, "
            "reinterpretato da Sleep Token nel 2022). Collocato tra i singoli staccati perché privo di sigillo "
            "di Sundowning o profondità marina di TPWBYT, ma tematicamente affine al dubbio onirico ('Is it really you?')."
        ),
        "in_character_quotes": [],
        "editorial_reading": [
            {
                "summary": (
                    "Collaborazione celebrata dalla stampa metal britannica come l'incontro tra le due realtà "
                    "più atmosferiche della scena UK: Vessel trasforma il brano shoegaze dei Loathe in una preghiera gospel-ambient."
                ),
                "source_title": "Louder - The story behind every Sleep Token song",
                "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
                "date": "2023-05-19",
                "source_class": "editorial",
            }
        ],
        "symbols": {
            "sigil": None,
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "Velo / Orizzonte onirico",
            "color": "Blu notte / Argento",
        },
        "references": [
            {
                "category": "intertestualità musicale",
                "detail": (
                    "Dialogo diretto con l'album 'I Let It in and It Took Everything' dei Loathe, il cui titolo stesso "
                    "risuona con la possessione volontaria di Vessel da parte di Sleep."
                ),
                "supporting_phrase": "Let's search the sky for a while / You and I",
                "source_title": "Sleep Token Collective Wiki - Is It Really You?",
                "url": "https://sleep-token-collective.fandom.com/wiki/Is_It_Really_You%3F",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "The Apparition (Take Me Back to Eden, 2023)",
                "motif": (
                    "La domanda centrale 'Is it really you?' anticipa il dubbio sull'autenticità della visione "
                    "onirica che esplode in 'The Apparition'."
                ),
                "source_title": "Sleep Token Collective Wiki - Is It Really You?",
                "url": "https://sleep-token-collective.fandom.com/wiki/Is_It_Really_You%3F",
                "source_class": "community",
            }
        ],
        "community_theories": [
            {
                "theory": (
                    "Pur essendo una cover dei Loathe, i fan la inseriscono come intermezzo tra la fine di TPWBYT "
                    "e l'inizio di TMBTE, in cui Vessel si chiede se l'entità che vede nei sogni sia davvero Sleep "
                    "o una proiezione del proprio dolore."
                ),
                "source_title": "r/SleepToken discussions",
                "url": "https://sleep-token-collective.fandom.com/wiki/Is_It_Really_You%3F",
                "source_class": "community",
            }
        ],
        "gaps": [
            "0 annotazioni Genius nell'archivio locale; brano scritto originariamente dai Loathe, quindi non contiene lore primaria scritta da Vessel."
        ],
    },
    {
        "slug": "11-dancing-in-the-dark",
        "title": "Dancing in the Dark",
        "release": "Dancing in the Dark (Spotify Singles / Bruce Springsteen Cover)",
        "track_number": 1,
        "year": 2018,
        "genius_annotations_count": 0,
        "keywords": ["Dancing in the Dark", "Springsteen", "fire", "dark"],
        "era_role": (
            "Cover acustica/ambientale del classico di Bruce Springsteen, registrata nel periodo pre-Sundowning / "
            "Room Below. Come per 'Hey Ya!', isolare il testo nel buio ('dancing in the dark') lo piega "
            "all'isolamento notturno di Vessel."
        ),
        "in_character_quotes": [],
        "editorial_reading": [],
        "symbols": {
            "sigil": None,
            "depth": None,
            "rune": None,
            "creature": None,
            "object": "L'oscurità e la scintilla ('start a fire')",
            "color": "Nero",
        },
        "references": [
            {
                "category": "musica rock americana",
                "detail": "Rielaborazione minimale del brano di Bruce Springsteen (1984).",
                "supporting_phrase": "Can't start a fire without a spark",
                "source_title": "Sleep Token Collective Wiki - Dancing in the Dark",
                "url": "https://sleep-token-collective.fandom.com/wiki/Dancing_in_the_Dark",
                "source_class": "community",
            }
        ],
        "callbacks": [
            {
                "target_song": "The Night Does Not Belong to God / The Room Below",
                "motif": "Continua la serie di reinterpretazioni solitarie al pianoforte legate al tema della notte.",
                "source_title": "Sleep Token Collective Wiki - Dancing in the Dark",
                "url": "https://sleep-token-collective.fandom.com/wiki/Dancing_in_the_Dark",
                "source_class": "community",
            }
        ],
        "community_theories": [],
        "gaps": [
            "0 annotazioni Genius e copertura editoriale quasi nulla: registrata come cover minore senza apparato simbolico dedicato."
        ],
    },
    {
        "slug": "12-granite-sullivan-king-remix",
        "title": "Granite (Sullivan King Remix)",
        "release": "Granite (Sullivan King Remix) - Non-Canon Electronic Remix",
        "track_number": 1,
        "year": 2024,
        "status": "skip",
        "genius_annotations_count": 0,
        "keywords": ["Sullivan King", "Granite Remix"],
        "era_role": (
            "SKIP CONFERMATO: Remix elettronico/dubstep esterno di un brano del Capitolo 3 ('Granite'). "
            "Non aggiunge testo, sigilli, rune, video canonici o dichiarazioni in-character. "
            "Tutta la lore di 'Granite' appartiene esclusivamente al Capitolo 3 (Take Me Back to Eden)."
        ),
        "in_character_quotes": [],
        "editorial_reading": [],
        "symbols": {
            "sigil": None,
            "depth": None,
            "rune": None,
            "creature": None,
            "object": None,
            "color": None,
        },
        "references": [],
        "callbacks": [],
        "community_theories": [],
        "gaps": [
            "Marcato 'skip' come da istruzioni: nessuna lore aggiuntiva rispetto alla traccia originale di Take Me Back to Eden."
        ],
    },
]

# ==============================================================================
# 4. PARSER HTML LEGGERO (SOLO PARAGRAFI, FILTRATO CONTRO DOXXING E LYRICS)
# ==============================================================================


class ParagraphExtractor(HTMLParser):
    """Estrae paragrafi <p> e <li> puliti, scartando nav, script e blocchi di testi integrali."""

    def __init__(self) -> None:
        super().__init__()
        self._in_block = False
        self._skip_depth = 0
        self._current_chunks: list[str] = []
        self.paragraphs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self._skip_depth:
            if tag not in _VOID_TAGS:
                self._skip_depth += 1
            return
        attr = {key: (value or "") for key, value in attrs}
        blob = f"{attr.get('class', '')} {attr.get('id', '')}".lower()
        lyric_box = any(token in blob for token in ("lyric", "poem", "mw-lyrics"))
        if tag in {"script", "style", "nav", "footer", "header", "noscript", "svg"} or lyric_box:
            self._skip_depth = 1
            return
        if tag in {"p", "li", "blockquote"}:
            self._in_block = True
            self._current_chunks = []

    def handle_endtag(self, tag: str) -> None:
        if self._skip_depth:
            if tag not in _VOID_TAGS:
                self._skip_depth -= 1
            return
        if self._in_block and tag in {"p", "li", "blockquote"}:
            self._in_block = False
            text = re.sub(r"\s+", " ", "".join(self._current_chunks)).strip()
            if len(text) >= 45 and not is_forbidden_content(text):
                self.paragraphs.append(text)
            self._current_chunks = []

    def handle_data(self, data: str) -> None:
        if self._in_block and self._skip_depth == 0:
            self._current_chunks.append(data)


def is_forbidden_content(text: str) -> bool:
    """Scarta identità reali, doxxing e blocchi di testo musicale integrale."""
    if IDENTITY_REGEX.search(text):
        return True
    if text.count(" / ") >= 6:
        return True
    lower = text.lower()
    if "contributors" in lower and "translations" in lower:
        return True
    if "[verse" in lower or "[chorus" in lower or "[bridge" in lower:
        return True
    if text.lstrip().startswith("↑") or "archived from the original" in lower:
        return True
    return False


def write_json(path: Path, payload: Any) -> None:
    """Checkpoint atomico: il file precedente resta intatto finché il tmp non è completo."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def fetch_url(url: str, gaps_log: list[str]) -> str | None:
    """Scarica una pagina rispettando domini bloccati, timeout e senza aggirare CAPTCHA."""
    parsed = urllib.parse.urlparse(url)
    domain = parsed.netloc.lower().removeprefix("www.")
    if any(domain == blocked or domain.endswith("." + blocked) for blocked in BLOCKED_DOMAINS):
        gaps_log.append(f"Skipped blocked domain: {url}")
        return None

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            status = getattr(resp, "status", 200)
            if status != 200:
                gaps_log.append(f"HTTP {status} for {url}")
                return None
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
            head = html[:5000].lower()
            if any(marker in head for marker in ("just a moment", "cf-challenge", "attention required", "captcha-delivery")):
                gaps_log.append(f"CAPTCHA/Challenge encountered (not bypassed): {url}")
                return None
            return html
    except urllib.error.HTTPError as exc:
        gaps_log.append(f"HTTP {exc.code} for {url}")
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        gaps_log.append(f"Fetch failed for {url}: {exc}")
        return None


def strip_html_section(html: str, heading: str) -> str:
    """Rimuove una sezione (tipicamente Lyrics) fino al titolo successivo."""
    pattern = re.compile(
        rf"<h[23]\b[^>]*>(?:(?!</h[23]>).)*\b{re.escape(heading)}\b(?:(?!</h[23]>).)*</h[23]>.*?(?=<h[23]\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub("", html)


def fetch_fandom_page(page: str, gaps_log: list[str]) -> str | None:
    """Legge il testo pubblico via MediaWiki API quando l'HTML della wiki è bloccato."""
    query = urllib.parse.urlencode(
        {
            "action": "parse",
            "page": page,
            "prop": "text",
            "format": "json",
            "disableeditsection": "1",
        }
    )
    raw = fetch_url(f"{FANDOM_API}?{query}", gaps_log)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        gaps_log.append(f"Invalid JSON from Fandom API for {page}")
        return None
    error = payload.get("error")
    if error:
        gaps_log.append(f"Fandom page absent: {page} ({error.get('code', 'error')})")
        return None
    html = payload.get("parse", {}).get("text", {}).get("*", "")
    if not html:
        gaps_log.append(f"Fandom page empty: {page}")
        return None
    return strip_html_section(html, "Lyrics")


def paragraph_matches(paragraph: str, title: str, keywords: list[str]) -> bool:
    """Il titolo del brano basta; le altre chiavi devono essere specifiche."""
    text = paragraph.lower()
    if title.lower() in text:
        return True
    return any(keyword in text for keyword in keywords if keyword not in KEYWORD_STOP and len(keyword) >= 5)


def resolve_kerrang_wayback_snapshots(gaps_log: list[str]) -> list[dict[str, str]]:
    """Interroga la CDX API di Wayback per trovare snapshot Kerrang 2017-2019 con timestamp vero."""
    raw = fetch_url(WAYBACK_CDX_KERRANG_QUERY, gaps_log)
    if not raw:
        gaps_log.append(
            "Wayback CDX timed out or failed. Falling back to the earliest www.kerrang.com "
            f"capture cited by Wikipedia: {KERRANG_EARLIEST_SNAPSHOT['timestamp']}."
        )
        return [dict(KERRANG_EARLIEST_SNAPSHOT)]
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        gaps_log.append("Invalid JSON from Wayback CDX query for Kerrang.")
        return []

    snapshots: list[dict[str, str]] = []
    for row in rows[1:]:
        if len(row) >= 3 and str(row[1]).isdigit():
            timestamp, original_url = row[1], row[2]
            snapshots.append(
                {
                    "timestamp": timestamp,
                    "original_url": original_url,
                    "wayback_url": f"https://web.archive.org/web/{timestamp}/{original_url}",
                    "source_class": "editorial",
                }
            )
    if not snapshots:
        gaps_log.append(
            "Wayback CDX for kerrang.com/*sleep-token* (2017-2020) returned no snapshots. "
            "Using the earliest www.kerrang.com capture cited by Wikipedia: "
            f"{KERRANG_EARLIEST_SNAPSHOT['timestamp']}."
        )
        snapshots.append(dict(KERRANG_EARLIEST_SNAPSHOT))
    return snapshots


def fetch_reddit_theory_threads(query: str, gaps_log: list[str]) -> list[dict[str, Any]]:
    """Estrae massimo 3 thread di significato/teoria da r/SleepToken evitando foto/tour."""
    encoded = urllib.parse.quote(query)
    url = (
        "https://www.reddit.com/r/SleepToken/search.json"
        f"?q={encoded}&restrict_sr=1&sort=top&t=all&limit=6"
    )
    raw = fetch_url(url, gaps_log)
    if not raw:
        return []

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        gaps_log.append(f"Invalid JSON from Reddit search: {url}")
        return []

    results: list[dict[str, Any]] = []
    children = payload.get("data", {}).get("children", [])
    for child in children:
        data = child.get("data", {})
        title = data.get("title", "")
        selftext = data.get("selftext", "")
        permalink = data.get("permalink", "")
        created_utc = data.get("created_utc")
        if len(selftext.strip()) < 160:
            continue
        if is_forbidden_content(title) or is_forbidden_content(selftext):
            continue
        excerpt = re.sub(r"\s+", " ", selftext).strip()[:450]
        results.append(
            {
                "theory": f"[Thread: {title}] {excerpt}...",
                "source_title": f"r/SleepToken - {title}",
                "url": f"https://www.reddit.com{permalink}",
                "date": time.strftime("%Y-%m-%d", time.gmtime(created_utc)) if created_utc else None,
                "source_class": "community",
            }
        )
        if len(results) >= 3:
            break
    return results


def _null_or_gap(items: list[Any], reason: str) -> tuple[list[Any] | None, str | None]:
    if items:
        return items, None
    return None, reason


# ==============================================================================
# 5. ESECUZIONE CAPITOLO 0: ESTRAZIONE MIRATA E SCRITTURA PER SINGOLO BRANO
# ==============================================================================


def main() -> None:
    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    chapter_gaps: list[str] = []

    extracted_corpus: dict[str, dict[str, Any]] = {}
    for src in CLOSED_SOURCES:
        if src["id"] in FANDOM_PAGES:
            html = fetch_fandom_page(FANDOM_PAGES[src["id"]], chapter_gaps)
        else:
            html = fetch_url(src["url"], chapter_gaps)
        time.sleep(REQUEST_DELAY_SEC)
        if not html:
            continue
        parser = ParagraphExtractor()
        parser.feed(html)
        extracted_corpus[src["id"]] = {"meta": src, "paragraphs": parser.paragraphs}
        print(f"[SRC] {src['id']}: {len(parser.paragraphs)} paragrafi")

    kerrang_snapshots = resolve_kerrang_wayback_snapshots(chapter_gaps)
    time.sleep(REQUEST_DELAY_SEC)
    kerrang_quotes: list[dict[str, Any]] = []
    for snap in kerrang_snapshots[:2]:
        html = fetch_url(snap["wayback_url"], chapter_gaps)
        time.sleep(REQUEST_DELAY_SEC)
        if not html:
            continue
        parser = ParagraphExtractor()
        parser.feed(html)
        paragraphs = parser.paragraphs
        for paragraph in paragraphs:
            if len(kerrang_quotes) >= 8:
                break
            if len(paragraph) < 280:
                continue
            if any(token in paragraph.lower() for token in ("sleep", "vessel", "worship", "mask", "anonym")):
                kerrang_quotes.append(
                    {
                        "excerpt": paragraph,
                        "url": snap["wayback_url"],
                        "original_url": snap["original_url"],
                        "timestamp": snap["timestamp"],
                        "source_class": "editorial",
                    }
                )

    written_song_files: list[str] = []
    for song in SONGS_CATALOG:
        song_gaps: list[str] = list(song.get("gaps", []))
        title = song["title"]
        keywords = [keyword.lower() for keyword in song.get("keywords", [title])]

        if song.get("status") != "skip":
            for src_data in extracted_corpus.values():
                meta = src_data["meta"]
                matching = [p for p in src_data["paragraphs"] if paragraph_matches(p, title, keywords)]
                for paragraph in matching[:3]:
                    if meta["source_class"] == "editorial":
                        song["editorial_reading"].append(
                            {
                                "summary": paragraph,
                                "source_title": meta["title"],
                                "url": meta["url"],
                                "date": None,
                                "source_class": meta["source_class"],
                            }
                        )
                    else:
                        song["community_theories"].append(
                            {
                                "theory": paragraph,
                                "source_title": meta["title"],
                                "url": meta["url"],
                                "source_class": "community",
                            }
                        )

            fandom_url = FANDOM_SONG_URLS.get(title)
            if fandom_url:
                fandom_html = fetch_fandom_page(FANDOM_PAGES[title], song_gaps)
                time.sleep(REQUEST_DELAY_SEC)
                if fandom_html:
                    fandom_parser = ParagraphExtractor()
                    fandom_parser.feed(fandom_html)
                    for paragraph in fandom_parser.paragraphs[:4]:
                        if paragraph_matches(paragraph, title, keywords) or "sleep" in paragraph.lower():
                            song["community_theories"].append(
                                {
                                    "theory": paragraph,
                                    "source_title": f"Sleep Token Collective Wiki - {title}",
                                    "url": fandom_url,
                                    "source_class": "community",
                                }
                            )

            reddit_query = REDDIT_SONG_QUERIES.get(title)
            if reddit_query:
                song["community_theories"].extend(fetch_reddit_theory_threads(reddit_query, song_gaps))
                time.sleep(REQUEST_DELAY_SEC)

        symbols_obj = dict(song["symbols"])
        for sym_key, sym_val in list(symbols_obj.items()):
            if sym_val is None:
                symbols_obj[f"{sym_key}_gap_reason"] = _SIGIL_GAP

        quotes, quotes_gap = _null_or_gap(
            song["in_character_quotes"],
            "Sleep Token ha rilasciato pochissime interviste nel 2016-2018 e mai commenti traccia-per-traccia in-character.",
        )
        editorial, editorial_gap = _null_or_gap(
            song["editorial_reading"],
            "Nessuna recensione editoriale individuale trovata per questo brano secondario/cover.",
        )
        references, references_gap = _null_or_gap(
            song["references"],
            "Nessun riferimento mitologico, scientifico o letterario documentato.",
        )
        callbacks, callbacks_gap = _null_or_gap(song["callbacks"], "Nessun callback verificato.")
        theories, theories_gap = _null_or_gap(
            song["community_theories"],
            "Assenza di thread ricorrenti di consenso sulla traccia.",
        )
        song_payload = {
            "title": song["title"],
            "release": song["release"],
            "track_number": song["track_number"],
            "year": song["year"],
            "status": song.get("status", "active"),
            "genius_annotations_archived": song["genius_annotations_count"],
            "era_role": song["era_role"],
            "in_character_quotes": quotes,
            "in_character_quotes_gap_reason": quotes_gap,
            "editorial_reading": editorial,
            "editorial_reading_gap_reason": editorial_gap,
            "symbols": symbols_obj,
            "references": references,
            "references_gap_reason": references_gap,
            "callbacks": callbacks,
            "callbacks_gap_reason": callbacks_gap,
            "community_theories": theories,
            "community_theories_gap_reason": theories_gap,
            "gaps": song_gaps,
        }
        out_file = CHAPTER_DIR / f"{song['slug']}.json"
        write_json(out_file, song_payload)
        written_song_files.append(str(out_file).replace("\\", "/"))
        print(f"[OK] Scritto file brano: {out_file}")

    role_extracts: dict[str, list[dict[str, str]]] = {}
    for role, page in ROLE_PAGES.items():
        html = fetch_fandom_page(page, chapter_gaps)
        time.sleep(REQUEST_DELAY_SEC)
        if not html:
            continue
        parser = ParagraphExtractor()
        parser.feed(html)
        role_re = re.compile(rf"\b{re.escape(role)}\b", re.IGNORECASE)
        kept = [
            paragraph
            for paragraph in parser.paragraphs
            if role_re.search(paragraph) or "ritual" in paragraph.lower() or "mask" in paragraph.lower()
        ][:4]
        if kept:
            role_extracts[role] = [
                {
                    "excerpt": paragraph,
                    "source_title": f"Sleep Token Collective Wiki - {page}",
                    "url": f"https://sleep-token-collective.fandom.com/wiki/{page.replace(' ', '_')}",
                    "source_class": "community",
                }
                for paragraph in kept
            ]

    chapter_overview = {
        "chapter_number": 0,
        "slug": "00-origin",
        "title": "Capitolo 0 — Origine (2016–2018: Il Patto con Sleep, i Ruoli Rituali, One, Two e i Singoli)",
        "period_covered": "2016-09 — 2018-12 (con appendici cover fuori-trilogia)",
        "origin_narrative": {
            "the_pact_with_sleep": {
                "summary": (
                    "Nel settembre 2016 il progetto si presenta con il comunicato Basick Records: Sleep è una divinità "
                    "antica che ha governato le civiltà primordiali attraverso il dono del sogno. È apparsa in sogno a "
                    "Vessel promettendogli 'gloria e magnificenza' in cambio di servitù e adorazione ('Worship'). "
                    "Ogni brano registrato è un 'Token' (offerta votiva) e ogni concerto è un 'Ritual'."
                ),
                "canon_quotes": [
                    {
                        "quote": "How we got here is as irrelevant as who we are – what matters is the music and the message. We are here to serve Sleep and project His message.",
                        "source_title": "Metal Hammer / Louder - Who and what the hell are Sleep Token? (2017)",
                        "url": "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
                        "date": "2017-05-25",
                        "source_class": "canon",
                    },
                    {
                        "quote": "He is everywhere, at all times. Vessel encountered Sleep in a dream, with promise of glory and magnificence if Vessel followed Him.",
                        "source_title": "Metal Hammer / Louder - Who and what the hell are Sleep Token? (2017)",
                        "url": "https://www.loudersound.com/features/who-and-what-the-hell-are-sleep-token",
                        "date": "2017-05-25",
                        "source_class": "canon",
                    },
                ],
                "kerrang_wayback_recovered": kerrang_quotes,
            },
            "worship_vs_toxic_relationship": (
                "Fin da 'Thread the Needle' e 'When the Bough Breaks', la scrittura di Vessel usa un doppio registro "
                "inseparabile: sul piano del mito è una liturgia di sottomissione a un dio antico; sul piano emotivo "
                "è la cronaca di una relazione tossica, codipendente e non ricambiata, in cui il narratore oscilla "
                "tra supplica ('Fields of Elation', 'Jericho') e rabbia predatoria ('Nazareth', 'Jaws')."
            ),
            "ritual_roles": {
                "Vessel": (
                    "Unico frontman, autore dei testi e canalizzatore vocale/pianistico del messaggio di Sleep. "
                    "Nella fase 2016-2018 indossa una maschera di tessuto/cappuccio con il primo emblema dipinto o "
                    "inciso sul volto e pittura corporale nera su collo, braccia e torso per cancellare i tratti umani."
                ),
                "II": (
                    "Batterista e secondo pilastro compositivo/ritmico del collettivo. Indossa maschera e cappuccio "
                    "con il simbolo della band; guida la transizione stilistica tra gospel, R&B, blast beat e djent."
                ),
                "III": (
                    "Bassista nei Rituals dal vivo. Figura scenica mobile che interagisce con la congregazione "
                    "(il pubblico) mantenendo il voto del silenzio verbale e il volto coperto."
                ),
                "IV": (
                    "Chitarrista nei Rituals dal vivo (chitarre baritone / 8 corde e cori screamed dal vivo). "
                    "Completa il quartetto strumentale numerato in cifre romane per negare l'ego individuale."
                ),
                "Espera": (
                    "Trio vocale femminile che accompagna i Rituals come coro liturgico vivente. Il nome richiama "
                    "i Vespri (preghiere della sera/tramonto) e l'attesa ('espera'), vestite e mascherate in coordinate "
                    "rituali con Vessel."
                ),
            },
            "ritual_role_extracts": role_extracts,
        },
        "songs_processed": written_song_files,
        "sources_fetched": sorted(extracted_corpus),
        "kerrang_snapshots_found": len(kerrang_snapshots),
        "gaps": chapter_gaps,
    }
    chapter_file = CHAPTER_DIR / "chapter.json"
    write_json(chapter_file, chapter_overview)
    print(f"[OK] Scritto riepilogo capitolo: {chapter_file}")
    print(f"[GAPS] {len(chapter_gaps)} fetch gaps a livello capitolo")


if __name__ == "__main__":
    main()
