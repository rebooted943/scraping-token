#!/usr/bin/env python3
"""
Sleep Token Lore Collector — Capitolo 2: This Place Will Become Your Tomb (2021).

Python 3.11+, solo libreria standard. Nessuna identità civile e nessun verso integrale.
La batimetria del booklet è una lettura di community finché una fonte live non la conferma.
Un JSON per traccia più chapter.json. Alkaline è ricostruito solo sul piano semantico.
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

CHAPTER_DIR = Path("chapters/02-this-place-will-become-your-tomb")
USER_AGENT = "Mozilla/5.0 (compatible; LoreArchivistBot/1.0; +https://example.org/lore-research)"
REQUEST_DELAY_SEC = 1.5
FATHOM_METERS = 1.8288
_VOID_TAGS = {"br", "img", "hr", "meta", "link", "input", "wbr", "source"}

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
_QUOTED = re.compile(r'["“”«»][^"“”«»]{8,}["“”«»]|[‘][^‘’]{8,}[’]')

BLOCKED_DOMAINS = {
    "youtube.com",
    "youtu.be",
    "instagram.com",
    "facebook.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "genius.com",
}

LORE_TPWBYT = "https://loreofsleeptoken.com/tpwbyt/"
LORE_TPWBYT_FALLBACK = "https://loreofsleeptoken.com/this-place-will-become-your-tomb/"
LORE_MAIN = "https://loreofsleeptoken.com/the-lore/"
FANDOM_ALBUM = "https://sleep-token-collective.fandom.com/wiki/This_Place_Will_Become_Your_Tomb"
WIKI = "https://en.wikipedia.org/wiki/This_Place_Will_Become_Your_Tomb"
LOUDER_P2 = "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/2"
LOUDER_P3 = "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/3"
BOOLIN = "https://boolintunes.com/featured/the-lore-of-sleep-token/"
FANDOM_API = "https://sleep-token-collective.fandom.com/api.php"

CLOSED_SOURCES: list[dict[str, str]] = [
    {"id": "lore_tpwbyt", "url": LORE_TPWBYT, "source_class": "community", "title": "Lore of Sleep Token - This Place Will Become Your Tomb"},
    {"id": "lore_main", "url": LORE_MAIN, "source_class": "community", "title": "Lore of Sleep Token - General Lore & Ocean Descent"},
    {"id": "fandom_tpwbyt", "url": FANDOM_ALBUM, "source_class": "community", "title": "Sleep Token Collective Wiki - This Place Will Become Your Tomb"},
    {"id": "wiki_tpwbyt", "url": WIKI, "source_class": "editorial", "title": "Wikipedia - This Place Will Become Your Tomb"},
    {"id": "louder_every_song_p2", "url": LOUDER_P2, "source_class": "editorial", "title": "Louder / Metal Hammer - The story behind every Sleep Token song (Page 2)"},
    {"id": "louder_every_song_p3", "url": LOUDER_P3, "source_class": "editorial", "title": "Louder / Metal Hammer - The story behind every Sleep Token song (Page 3)"},
    {"id": "boolin_lore", "url": BOOLIN, "source_class": "editorial", "title": "Boolin Tunes - The Lore of Sleep Token (TPWBYT Analysis)"},
]

FANDOM_API_PAGES: dict[str, str] = {
    "fandom_tpwbyt": "This Place Will Become Your Tomb",
    "Atlantic": "Atlantic",
    "Hypnosis": "Hypnosis",
    "Mine": "Mine",
    "Like That": "Like That",
    "The Love You Want": "The Love You Want",
    "Fall for Me": "Fall For Me",
    "Alkaline": "Alkaline",
    "Distraction": "Distraction",
    "Descending": "Descending",
    "Telomeres": "Telomeres",
    "High Water": "High Water",
    "Missing Limbs": "Missing Limbs",
}
FANDOM_SONG_URLS: dict[str, str] = {
    title: "https://sleep-token-collective.fandom.com/wiki/" + page.replace(" ", "_")
    for title, page in FANDOM_API_PAGES.items()
    if not title.startswith("fandom_")
}

WAYBACK_CDX_QUERIES = (
    "https://web.archive.org/cdx/search/cdx?url=kerrang.com/*tomb*&output=json&from=2021&to=2022&filter=statuscode:200&collapse=urlkey&limit=10",
    "https://web.archive.org/cdx/search/cdx?url=www.kerrang.com/*tomb*&output=json&from=2021&to=20221231235959&filter=statuscode:200&collapse=urlkey&limit=10",
    "https://web.archive.org/cdx/search/cdx?url=www.kerrang.com/*sleep-token*&output=json&from=2021&to=20221231235959&filter=statuscode:200&collapse=urlkey&limit=10",
)

REDDIT_SONG_QUERIES: dict[str, str] = {
    "Atlantic": 'title:"Atlantic" (lore OR meaning OR depth OR hospital OR suicide)',
    "Hypnosis": 'title:"Hypnosis" (lore OR meaning OR depth OR theory)',
    "Mine": 'title:"Mine" (lore OR meaning OR depth OR theory)',
    "Like That": 'title:"Like That" (lore OR meaning OR depth OR theory)',
    "The Love You Want": 'title:"The Love You Want" (lore OR meaning OR video OR depth)',
    "Fall for Me": 'title:"Fall for Me" (lore OR meaning OR video OR text OR depth)',
    "Alkaline": 'title:"Alkaline" (lore OR meaning OR chemistry OR video OR depth)',
    "Distraction": 'title:"Distraction" (lore OR meaning OR depth OR theory)',
    "Descending": 'title:"Descending" (lore OR meaning OR depth OR theory)',
    "Telomeres": 'title:"Telomeres" (lore OR meaning OR biology OR depth OR theory)',
    "High Water": 'title:"High Water" (lore OR meaning OR depth OR theory)',
    "Missing Limbs": 'title:"Missing Limbs" (lore OR meaning OR depth OR Chokehold)',
}

_SIGIL_GAP = (
    "I 12 sigilli geometrici appartengono a Sundowning (Capitolo 1). "
    "In TPWBYT il sistema simbolico primario è la quota batimetrica e il booklet marino."
)
_RUNE_GAP = "L'alfabeto runico sostitutivo viene introdotto in Take Me Back to Eden (Capitolo 3)."
_QUOTE_GAP = (
    "Nessuna intervista traccia-per-traccia nel ciclo 2021. "
    "L'unica confessione diretta in-character dell'era sta nei cartelli del video di Fall for Me."
)
_UNCLOSED_GAPS = [
    "Le tavole tassonomiche del booklet fisico 2021 non sono testo strutturato sul sito della band: si usano le trascrizioni wiki e loreofsleeptoken.com.",
    "I frame di Alkaline, The Love You Want e Fall for Me non sono acquisiti: youtube.com è bloccato. Restano le parafrasi delle fonti secondarie.",
    "Nel 2021 la band non ha concesso interviste tradizionali. Il messaggio diretto del personaggio resta il testo a schermo di Fall for Me.",
]
_SHORT_TITLES = {"mine"}


def _depth(track: str, fathoms: int, zone: str, specimen: str, meaning: str) -> dict[str, Any]:
    return {
        "track": track,
        "fathoms": fathoms,
        "meters": round(fathoms * FATHOM_METERS),
        "fathom_meters": FATHOM_METERS,
        "reading_class": "community",
        "fathoms_status": "unverified: la wiki dell'album non pubblica una tabella in fathom",
        "oceanic_zone": zone,
        "booklet_specimen": specimen,
        "booklet_specimen_source": "Sleep Token Collective Wiki, sezione Trivia",
        "descent_meaning": meaning,
    }


TPWBYT_BATHYMETRY: dict[int, dict[str, Any]] = {
    1: _depth(
        "Atlantic", 500,
        "Confine mesopelagico / batipelagico (circa 914 m, dove cessa la luce solare)",
        "Black swallower (Chiasmodon niger), dalla trivia della wiki",
        "Dopo il tramonto di Sundowning, la luce diurna si spegne e Vessel entra nell'oscurità in seguito a un atto di autodistruzione.",
    ),
    2: _depth(
        "Hypnosis", 958,
        "Zona batipelagica superiore (circa 1.752 m)",
        "Brittle star (stella serpentina), dalla trivia della wiki",
        "La lettura a spirale di nautilus non è la copertina. La stella serpentina rigenera le braccia: Sleep riafferma la presa dopo Atlantic.",
    ),
    3: _depth(
        "Mine", 1416,
        "Zona batipelagica media (circa 2.590 m)",
        "Comb jelly (ctenoforo), dalla trivia della wiki",
        "La pressione diventa possesso: le due anime sono descritte come rami corallini intrecciati nel buio.",
    ),
    4: _depth(
        "Like That", 1872,
        "Zona batipelagica inferiore (circa 3.424 m)",
        "Faceless cusk, dalla trivia della wiki",
        "Il contatto con l'altro si rivela velenoso: il piacere altrui sta nel vedere Vessel intrappolato.",
    ),
    5: _depth(
        "The Love You Want", 2328,
        "Zona abissopelagica superiore (circa 4.257 m)",
        "Deepsea lizardfish, dalla trivia della wiki. Nel video: danzatrici con spade",
        "Sulla piana abissale si misura la distanza tra l'amore offerto e quello richiesto.",
    ),
    6: _depth(
        "Fall for Me", 2784,
        "Zona abissopelagica media (circa 5.091 m)",
        "Whalefall in fase di affondamento, dalla trivia della wiki",
        "Senza strumenti, solo voce processata. La copertina mostra una carcassa che inizia a scendere.",
    ),
    7: _depth(
        "Alkaline", 3240,
        "Confine abissopelagico / hadopelagico (circa 5.925 m)",
        "Anglerfish (rana pescatrice), dalla trivia della wiki",
        "La copertina è la rana pescatrice, non una sorgente idrotermale. La chimica del pH resta la metafora del testo; l'esca luminosa è l'attrazione nel buio.",
    ),
    8: _depth(
        "Distraction", 3696,
        "Zona hadopelagica superiore (circa 6.759 m)",
        "Cookiecutter shark, dalla trivia della wiki",
        "Ogni distrazione dal dolore fallisce: è troppo tardi per risalire.",
    ),
    9: _depth(
        "Descending", 4152,
        "Zona hadopelagica media (circa 7.593 m)",
        "Reverse jewel squid (Histioteuthis reversa), dalla trivia della wiki",
        "La discesa non è più una caduta accidentale: è un moto dichiarato.",
    ),
    10: _depth(
        "Telomeres", 4608,
        "Zona hadopelagica profonda (circa 8.427 m, vicino al limite dei pesci ossei)",
        "Telescope octopus, dalla trivia della wiki",
        "La rigenerazione dei telomeri resta la metafora biologica. La copertina è il polpo telescopio, non lo snailfish.",
    ),
    11: _depth(
        "High Water", 5064,
        "Fossa delle Marianne inferiore (circa 9.261 m)",
        "Hadal snailfish, dalla trivia della wiki",
        "L'acqua alta riempie i polmoni: Vessel non trattiene più il respiro né il perdono verso di sé.",
    ),
    12: _depth(
        "Missing Limbs", 5973,
        "Challenger Deep, fondo della Fossa delle Marianne (circa 10.923 m)",
        "Whalefall, dalla trivia della wiki. Su Fall for Me la carcassa sta ancora scendendo",
        "Non si scende oltre. La tomba è compiuta e resta il dolore dell'arto fantasma.",
    ),
}


def _ref(category: str, detail: str, phrase: str, title: str, url: str, source_class: str = "community") -> dict[str, str]:
    return {
        "category": category,
        "detail": detail,
        "supporting_phrase": phrase,
        "source_title": title,
        "url": url,
        "source_class": source_class,
    }


def _cb(target: str, motif: str, title: str, url: str, source_class: str = "community") -> dict[str, str]:
    return {"target_song": target, "motif": motif, "source_title": title, "url": url, "source_class": source_class}


def _theory(text: str, title: str, url: str) -> dict[str, str]:
    return {"theory": text, "source_title": title, "url": url, "source_class": "community"}


def _edit(summary: str, title: str, url: str, date: str) -> dict[str, str]:
    return {"summary": summary, "source_title": title, "url": url, "date": date, "source_class": "editorial"}


def _wiki(title: str) -> str:
    return FANDOM_SONG_URLS[title]


def _song(**fields: Any) -> dict[str, Any]:
    number = fields["track_number"]
    fields["symbols"] = {
        "sigil": None,
        "depth": TPWBYT_BATHYMETRY[number],
        "rune": None,
        "creature": fields.pop("creature"),
        "object": fields.pop("object"),
        "color": fields.pop("color"),
    }
    fields.setdefault("in_character_quotes", [])
    fields.setdefault("gaps", [])
    return fields


SONGS_CATALOG: list[dict[str, Any]] = [
    _song(
        slug="01-atlantic",
        title="Atlantic",
        release="This Place Will Become Your Tomb",
        track_number=1,
        year=2021,
        genius_annotations_count=9,
        keywords=["Atlantic", "bandage", "flood", "hospital"],
        era_role=(
            "Apre l'album sulla quota di community di 500 fathom (circa 914 m), subito dopo Blood Sport e Drag Me Under. "
            "La trivia della wiki registra la lettura più diffusa, non una dichiarazione della band: "
            "risveglio clinico dopo un gesto autolesivo, e richiesta di essere lasciato nell'Atlantico."
        ),
        editorial_reading=[_edit(
            "Louder e Boolin Tunes legano l'incipit al pianoforte al trauma clinico: l'inondazione salata coincide con il rifiuto di tornare alla coscienza diurna.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        creature="Black swallower",
        object="Luci blu d'emergenza, bende, acqua oceanica",
        color="Blu cobalto e bianco clinico",
        references=[
            _ref(
                "oceanografia",
                "500 fathom segnano l'ingresso nella zona afotica, dove la luce solare si estingue.",
                "Quota di community 500 F. La wiki documenta il black swallower, non questa cifra.",
                "Progressione batimetrica di community", LORE_MAIN,
            ),
            _ref(
                "medicina d'urgenza",
                "Post-ricovero dopo un gesto autolesivo: sirene blu, occhi bendati, colpa per il dolore causato al mattino.",
                "Supplica di non essere svegliato, in una stanza che somiglia a un pronto soccorso.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
        ],
        callbacks=[
            _cb(
                "Drag Me Under e Blood Sport (Sundowning, 2019)",
                "Dopo aver chiesto di essere trascinato sott'acqua, Vessel si ritrova sommerso.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
            _cb(
                "Are You Really Okay? (2023) e Infinite Baths (2025)",
                "Sangue, ferite autoinflitte e acqua che sommerge il corpo tornano in quei due brani.",
                "Sleep Token Collective Wiki - Atlantic", _wiki("Atlantic"),
            ),
        ],
        community_theories=[_theory(
            "Due letture convivono: sul piano umano, un tentativo di suicidio dopo Sundowning; sul piano mitico, Sleep impedisce la morte perché gli serve ancora il contenitore, e lo condanna a una tomba liquida.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="02-hypnosis",
        title="Hypnosis",
        release="This Place Will Become Your Tomb",
        track_number=2,
        year=2021,
        genius_annotations_count=5,
        keywords=["Hypnosis", "nautilus", "spiral"],
        era_role=(
            "Seconda tappa, 958 fathom (circa 1.752 m). Superato lo shock di Atlantic, Vessel torna sotto l'incantesimo di Sleep. "
            "Il groove di II funziona come un mulinello a cui il protagonista acconsente."
        ),
        editorial_reading=[_edit(
            "Louder nota il ritmo ipnotico di II e le chitarre baritone come un'onda fisica: resa totale alla forza che tira verso il basso.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        creature="Brittle star",
        object="Spirale dell'ipnosi e onda che chiude",
        color="Blu profondo e argento",
        references=[_ref(
            "mito greco / trance",
            "Hypnos è la personificazione greca del sonno. Il soggetto in trance esegue una volontà altrui.",
            "Il titolo chiede di essere ipnotizzato e consumato per intero.",
            "Sleep Token Collective Wiki - Hypnosis", _wiki("Hypnosis"),
        )],
        callbacks=[_cb(
            "The Offering (Sundowning, 2019)",
            "Seconda traccia di entrambi i primi album: lì Sleep doveva prendere un morso, qui deve prendere tutto.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        community_theories=[_theory(
            "Con 5 annotazioni Genius, la trivia della wiki assegna alla copertina una brittle star, non un nautilus. Le braccia che si rigenerano restano la lettura biologica della resa a Sleep.",
            "Sleep Token Collective Wiki - Hypnosis", _wiki("Hypnosis"),
        )],
        gaps=["5 annotazioni Genius. Integrato con la trivia della wiki: la copertina è una brittle star."],
    ),
    _song(
        slug="03-mine",
        title="Mine",
        release="This Place Will Become Your Tomb",
        track_number=3,
        year=2021,
        genius_annotations_count=7,
        keywords=["Mine", "infinity", "possess"],
        era_role=(
            "Terza tappa, 1.416 fathom (circa 2.590 m). La voce passa dalla sottomissione a una certezza ossessiva: "
            "nonostante la rottura, l'altro è già suo."
        ),
        editorial_reading=[_edit(
            "Aperture synth luminose contro un sottotesto di possesso. L'arrangiamento trionfale rende più inquietante la pretesa.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        creature="Comb jelly",
        object="Vincolo d'infinito, esplosione di colore nel buio",
        color="Ciano bioluminescente e viola",
        references=[_ref(
            "ossessione",
            "Il rifiuto amoroso diventa fatalismo: due anime sarebbero già unite su un piano superiore.",
            "Ripetizione della certezza che l'interlocutore appartiene al narratore.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Give (2019) e Rain (2023)",
            "Prosegue il patto di appartenenza di Give e anticipa la rinascita cromatica di Rain.",
            "Sleep Token Collective Wiki - Mine", _wiki("Mine"),
        )],
        community_theories=[_theory(
            "Come in Give, una lettura inverte il punto di vista: è Sleep a parlare a Vessel mentre affonda, e a ricordargli a chi appartiene l'anima.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="04-like-that",
        title="Like That",
        release="This Place Will Become Your Tomb",
        track_number=4,
        year=2021,
        genius_annotations_count=4,
        keywords=["Like That", "trapped", "reflex"],
        era_role=(
            "Quarta tappa, 1.872 fathom (circa 3.424 m). La fantasia di Mine si rompe: "
            "Vessel accusa l'altro di godere nel vederlo intrappolato e sanguinante."
        ),
        editorial_reading=[_edit(
            "Groove basso e batteria sincopata. Boolin Tunes lo legge come il risentimento di Higher sotto 3.400 metri d'acqua.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        creature="Faceless cusk",
        object="Trappola e veleno",
        color="Verde abissale e nero",
        references=[_ref(
            "sadismo relazionale",
            "Il dolore è uno spettacolo. Ogni difesa di Vessel viene smontata con compiacimento.",
            "Domanda retorica: all'altro piace vederlo ridotto così.",
            "Sleep Token Collective Wiki - Like That", _wiki("Like That"),
        )],
        callbacks=[_cb(
            "Higher (2019) e Granite (2023)",
            "Accusa di manipolazione reciproca, poi il tono disilluso di Granite.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        community_theories=[_theory(
            "Con 4 annotazioni Genius, chi abbraccia la creatura urticante del booklet a questa quota resta paralizzato dal contatto.",
            "Sleep Token Collective Wiki - Like That", _wiki("Like That"),
        )],
        gaps=["4 annotazioni Genius. La trivia della wiki dà un faceless cusk; la quota in fathom resta di community."],
    ),
    _song(
        slug="05-the-love-you-want",
        title="The Love You Want",
        release="This Place Will Become Your Tomb",
        track_number=5,
        year=2021,
        genius_annotations_count=10,
        keywords=["The Love You Want", "white flag", "sword", "dancer"],
        era_role=(
            "Quinta tappa, 2.328 fathom (circa 4.257 m), ingresso abissale, e secondo singolo. "
            "Vessel è pieno dell'amore che l'altro vuole e non di quello di cui avrebbe bisogno, in un ciclo di rifiuti."
        ),
        editorial_reading=[_edit(
            "Struttura pop-gospel e break di II. Nel video Vessel si avvicina a una figura circondata da danzatrici armate, viene respinto a ogni ciclo e si rialza.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        creature="Deepsea lizardfish; danzatrici con spade nel video",
        object="Bandiere bianche macchiate, lame",
        color="Avorio, argento e rosso nel video",
        references=[_ref(
            "resa",
            "Anche il gesto di pace viene trasformato in ferita: le bandiere bianche finiscono rosse.",
            "Si continua a combattere fino a sporcare di sangue il segnale di resa.",
            "Sleep Token Collective Wiki - The Love You Want", _wiki("The Love You Want"),
        )],
        callbacks=[
            _cb(
                "Take Aim (Sundowning, 2019)",
                "Stessa supplica: essere amati anche a costo di essere trafitti.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
            _cb(
                "I cicli di Even In Arcadia (2025)",
                "Il loop del video (tentativo, morte per spada, reset) è il prototipo visivo dei cicli successivi.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
        ],
        community_theories=[_theory(
            "Le danzatrici armate sono lette come difese del trauma, o come sacerdotesse di Sleep che anticipano le Espera, e impediscono un contatto autentico.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="06-fall-for-me",
        title="Fall for Me",
        release="This Place Will Become Your Tomb",
        track_number=6,
        year=2021,
        genius_annotations_count=6,
        keywords=["Fall for Me", "vocoder", "subtitle", "beach"],
        era_role=(
            "Sesta tappa, 2.784 fathom (circa 5.091 m), a metà disco, terzo singolo. "
            "Solo voce e vocoder, nessun strumento: a 5 km di profondità resta la voce moltiplicata che chiede all'altro di cadere insieme."
        ),
        in_character_quotes=[{
            "quote": (
                "Parafrasi dei cartelli muti del video ufficiale (settembre 2021), non del testo cantato: "
                "Vessel si dice intrappolato nella propria mente, teme di non bastare a nessuno, "
                "si odia e insieme chiede che qualcuno lo tiri fuori da quel buio."
            ),
            "source_title": "Fall for Me official video on-screen text, via Fandom and Lore of Sleep Token",
            "url": _wiki("Fall for Me"),
            "date": "2021-09-17",
            "source_class": "canon",
        }],
        editorial_reading=[_edit(
            "Singolo metal senza chitarre né batteria. Il video su una spiaggia ventosa usa scritte a schermo come confessione diretta.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        creature="Whalefall in affondamento",
        object="Spiaggia, sabbia bagnata, cartelli neri",
        color="Grigio costiero e nero",
        references=[_ref(
            "confessione muta",
            "Gli intertitoli contraddicono il canto: la voce invoca un amore, la scrittura mostra depressione e ideazione suicidaria.",
            "Contrappunto tra armonie e confessioni scritte nel video. Il testo cantato non è archiviato.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Drag Me Under (2019) e DYWTYLM (2023)",
            "Cadere significa sia innamorarsi sia sprofondare. L'autoodio dei cartelli diventa esplicito in DYWTYLM.",
            "Sleep Token Collective Wiki - Fall for Me", _wiki("Fall for Me"),
        )],
        community_theories=[_theory(
            "I cartelli sono uno dei pochi momenti in cui Vessel parla senza il filtro di Sleep, prima della rottura della quarta parete del 2025.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="07-alkaline",
        title="Alkaline",
        release="This Place Will Become Your Tomb",
        track_number=7,
        year=2021,
        genius_annotations_count=8,
        local_archive_repair_note=(
            "Il file testuale locale di Alkaline risultava troncato a 22 caratteri (archivio del 21 ottobre 2026). "
            "Qui non si ricostruisce il testo protetto: si ricostruisce il significato chimico, batimetrico e del video."
        ),
        keywords=["Alkaline", "acid", "chemistry", "pH", "hydrothermal"],
        era_role=(
            "Settima tappa, 3.240 fathom (circa 5.925 m), primo singolo (giugno 2021). "
            "L'entità amata non sta su un estremo della scala del pH, né nella luce né nel buio: "
            "è una forza non classificata che altera la chimica del corpo."
        ),
        editorial_reading=[_edit(
            "Metal Hammer, Kerrang! e Boolin Tunes lo indicano come il brano che consacra la band prima del 2023. "
            "La scala del pH descrive una figura che non è angelo né demone.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        creature="Anglerfish; nel video, figure armate e fili rossi",
        object="Scala del pH e ragnatela di fili rossi",
        color="Rosso neon e blu abissale",
        references=[
            _ref(
                "chimica e geochimica",
                "Sotto pH 7 una soluzione è acida, sopra è basica. Intorno ai 6.000 m le sorgenti idrotermali alcaline sono, in biologia evolutiva, una culla chimica della vita.",
                "L'amata è descritta come né acida né alcalina, un elemento ancora non scoperto. Nessun verso è archiviato.",
                "Sleep Token Collective Wiki - Alkaline", _wiki("Alkaline"),
            ),
            _ref(
                "coincidentia oppositorum",
                "Luce diurna e tenebra, santità e peccato, coincidono in una figura sola.",
                "Il ritornello oppone in modo simmetrico il giorno e il buio, senza citarne i versi.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
        ],
        callbacks=[_cb(
            "Sugar (2019) e Aqua Regia (2023)",
            "Secondo capitolo chimico: dopo la dipendenza organica di Sugar, l'equilibrio acido-base, poi l'acqua regia che scioglie l'oro.",
            "Sleep Token Collective Wiki - Alkaline", _wiki("Alkaline"),
        )],
        community_theories=[_theory(
            "Nel video Vessel abbatte figure in tenuta tattica e finisce immobilizzato da fili rossi davanti a una figura velata. "
            "I poteri dati da Sleep funzionano nel sogno e servono solo a spingerlo più a fondo nella trappola.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        gaps=["Scheda locale da 22 caratteri sanata sul piano semantico. Il testo cantato resta fuori dall'archivio."],
    ),
    _song(
        slug="08-distraction",
        title="Distraction",
        release="This Place Will Become Your Tomb",
        track_number=8,
        year=2021,
        genius_annotations_count=6,
        keywords=["Distraction", "too late"],
        era_role=(
            "Ottava tappa, 3.696 fathom (circa 6.759 m), dentro la fossa. "
            "Dopo l'estasi di Alkaline, ogni tentativo di distrarsi da lei o da Sleep fallisce: è troppo tardi."
        ),
        editorial_reading=[_edit(
            "Struttura lenta. Le sovraincisioni vocali simulano pensieri intrusivi a cui non si sfugge.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        creature="Cookiecutter shark",
        object="Ancora sul fondo, voci sovrapposte",
        color="Nero e bagliore freddo",
        references=[_ref(
            "bioluminescenza / evitamento",
            "Oltre i 6.000 m l'unica luce è l'esca di un predatore, una distrazione fatale. Sul piano psichico, l'evitamento non regge.",
            "È troppo tardi, ed è già spezzato dentro. Parafrasi, non citazione.",
            "Sleep Token Collective Wiki - Distraction", _wiki("Distraction"),
        )],
        callbacks=[_cb(
            "Say That You Will (2019)",
            "Di nuovo un'esca luminosa nel buio, e la rassegnazione che ne segue.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        community_theories=[_theory(
            "Le distrazioni sarebbero sia relazioni sostitutive sia la musica stessa: niente zittisce il richiamo di Sleep.",
            "Sleep Token Collective Wiki - Distraction", _wiki("Distraction"),
        )],
    ),
    _song(
        slug="09-descending",
        title="Descending",
        release="This Place Will Become Your Tomb",
        track_number=9,
        year=2021,
        genius_annotations_count=5,
        keywords=["Descending", "corrupt"],
        era_role=(
            "Nona tappa, 4.152 fathom (circa 7.593 m). Il titolo nomina il moto dell'album. "
            "R&B oscuro: Vessel chiede cosa ci sia di affascinante nel corromperlo."
        ),
        editorial_reading=[_edit(
            "Tinte synth-wave. La critica lo mette accanto a Dark Signs e Like That.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        creature="Reverse jewel squid",
        object="Acque nere che salgono",
        color="Viola scuro e nero",
        references=[_ref(
            "catabasi",
            "La discesa agli inferi è traslata nella fossa: non porta conoscenza, esaurisce le difese morali.",
            "Il titolo dichiara la discesa e interroga il tradimento reciproco.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Dark Signs (2019) e Like That",
            "Chiude il trittico sulle accuse di manipolazione.",
            "Sleep Token Collective Wiki - Descending", _wiki("Descending"),
        )],
        community_theories=[_theory(
            "Con 5 annotazioni Genius, è l'ultimo brano ritmico prima del trittico Telomeres, High Water, Missing Limbs.",
            "Sleep Token Collective Wiki - Descending", _wiki("Descending"),
        )],
        gaps=["5 annotazioni Genius. Integrato con la wiki."],
    ),
    _song(
        slug="10-telomeres",
        title="Telomeres",
        release="This Place Will Become Your Tomb",
        track_number=10,
        year=2021,
        genius_annotations_count=6,
        keywords=["Telomeres", "tide", "chromosome"],
        era_role=(
            "Decima tappa, 4.608 fathom (circa 8.427 m), vicino al limite fisiologico dei pesci. "
            "Si apre uno squarcio shoegaze: le maree guidano i due, e l'amore sembra invertire l'invecchiamento cellulare."
        ),
        editorial_reading=[_edit(
            "Boolin Tunes e Louder notano l'assolo finale, raro nei primi due album, come ultima illusione di salvezza prima di High Water.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        creature="Telescope octopus",
        object="Telomeri, maree, catene",
        color="Oro bioluminescente e blu",
        references=[
            _ref(
                "biologia molecolare",
                "I telomeri proteggono i cromosomi e si accorciano a ogni divisione. L'unione sul fondale è vissuta come una telomerasi che ferma la morte.",
                "Il titolo invoca le maree perché portino via il passato e rigenerino il legame. Testo non archiviato.",
                "Sleep Token Collective Wiki - Telomeres", _wiki("Telomeres"),
            ),
            _ref(
                "oceanografia biologica",
                "Intorno agli 8.300–8.400 m l'osmolito TMAO non basta più a impedire il collasso delle proteine dei pesci sotto pressione.",
                "Quota di community 4.608 F. La trivia della wiki assegna alla copertina un telescope octopus, non questa cifra.",
                "Progressione batimetrica di community", LORE_MAIN,
            ),
        ],
        callbacks=[_cb(
            "Is It Really You? (2022) e Euclid (2023)",
            "Il shoegaze luminoso anticipa la collaborazione con i Loathe e la catarsi di Euclid.",
            "Sleep Token Collective Wiki - Telomeres", _wiki("Telomeres"),
        )],
        community_theories=[_theory(
            "Lettura da narcosi: poco prima dello schiacciamento di High Water, il subacqueo allucina pace e immortalità biologica.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="11-high-water",
        title="High Water",
        release="This Place Will Become Your Tomb",
        track_number=11,
        year=2021,
        genius_annotations_count=8,
        keywords=["High Water", "breath", "forgive"],
        era_role=(
            "Undicesima tappa, 5.064 fathom (circa 9.261 m). L'allucinazione di Telomeres cede. "
            "Vessel non perdona se stesso e non trattiene più il respiro. Il brano si taglia su uno scream strozzato."
        ),
        editorial_reading=[_edit(
            "Climax equivalente a Blood Sport per il secondo album: synth ostinato e chitarre a 8 corde come collasso sotto la colonna d'acqua.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        creature="Hadal snailfish",
        object="Respiro spezzato, cicatrici riaperte",
        color="Nero e rosso sangue",
        references=[_ref(
            "idioma / annegamento",
            "Rovescia il modo di dire inglese che promette di arrivare nonostante l'inferno o l'acqua alta: qui entrambi sono arrivati e hanno vinto.",
            "Confessione di non riuscire più a trattenere il respiro. Parafrasi.",
            "Sleep Token Collective Wiki - High Water", _wiki("High Water"),
        )],
        callbacks=[
            _cb(
                "Jaws (2018)",
                "Le fauci del 2018 hanno trascinato Vessel sul fondo della fossa. Il motivo è richiamato senza riprodurre il verso.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
            _cb(
                "Chokehold (2023)",
                "Il taglio sul respiro soffocato prepara il soffocamento che apre il terzo album.",
                "Sleep Token Collective Wiki - High Water", _wiki("High Water"),
            ),
        ],
        community_theories=[_theory(
            "Accettare i sorrisi falsi dell'altro costa l'impossibilità di perdonarsi. È la morte dell'autostima a questa quota.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="12-missing-limbs",
        title="Missing Limbs",
        release="This Place Will Become Your Tomb",
        track_number=12,
        year=2021,
        genius_annotations_count=12,
        keywords=["Missing Limbs", "phantom", "Challenger", "Chokehold"],
        era_role=(
            "Ultima tappa, 5.973 fathom (circa 10.923 m), Challenger Deep. "
            "Dopo High Water resta una chitarra acustica: la perdita è il dolore neurologico di un arto amputato che il cervello continua a sentire."
        ),
        editorial_reading=[_edit(
            "Simmetria con Blood Sport: chiusura spogliata dopo un climax pesante, poi un outro ambientale che si salda all'album successivo.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        creature="Whalefall",
        object="Arto fantasma, chitarra acustica, cima recisa",
        color="Nero del fondale",
        references=[
            _ref(
                "geografia oceanica",
                "5.973 fathom è una cifra di community per il Challenger Deep. La pagina wiki dell'album non la pubblica.",
                "La trivia di Missing Limbs documenta un whalefall, non i 5.973 fathom.",
                "Progressione batimetrica di community", LORE_MAIN,
            ),
            _ref(
                "neurologia",
                "Dopo un'amputazione la mappa corticale continua a cercare la parte mancante e ne sente il dolore.",
                "Metafora del dolore per un legame reciso che il corpo sente ancora presente.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
        ],
        callbacks=[
            _cb(
                "Blood Sport (Sundowning, traccia 12)",
                "Entrambe chiudono un album a voce nuda dopo il climax, e confessano la sconfitta.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
            _cb(
                "Chokehold (Take Me Back to Eden, traccia 1, 2023)",
                "Il drone degli ultimi secondi prosegue nell'attacco di Chokehold e segna la riemersione. Il verso non è archiviato.",
                "Sleep Token Collective Wiki - Missing Limbs", _wiki("Missing Limbs"),
            ),
        ],
        community_theories=[_theory(
            "Negli ultimi versi Vessel vorrebbe soffrire al posto dell'altro per permettergli di dimenticare, e insieme darebbe qualsiasi cosa per ricordare il contatto. Si ricollega all'amnesia di Sundowning.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
]


class ParagraphExtractor(HTMLParser):
    """Estrae p, li e blockquote. Scarta script, nav e blocchi marcati come testi."""

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
        if tag in {"script", "style", "nav", "footer", "header", "noscript", "svg", "pre"} or lyric_box:
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
    if IDENTITY_REGEX.search(text):
        return True
    if text.count(" / ") >= 4:
        return True
    lower = text.lower()
    if "[verse" in lower or "[chorus" in lower or "[bridge" in lower:
        return True
    if "contributors" in lower and "translations" in lower:
        return True
    if text.lstrip().startswith("↑") or "archived from the original" in lower:
        return True
    return False


def paraphrase_extract(text: str) -> str:
    cleaned = _QUOTED.sub("[riferimento testuale]", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:420]


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def fetch_url(url: str, gaps_log: list[str]) -> str | None:
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
            body = raw.decode(charset, errors="replace")
            head = body[:5000].lower()
            if any(marker in head for marker in ("just a moment", "cf-challenge", "attention required", "captcha-delivery")):
                gaps_log.append(f"CAPTCHA/Challenge encountered (not bypassed): {url}")
                return None
            return body
    except urllib.error.HTTPError as exc:
        gaps_log.append(f"HTTP {exc.code} for {url}")
        return None
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        gaps_log.append(f"Fetch failed for {url}: {exc}")
        return None


def strip_html_section(html: str, heading: str) -> str:
    pattern = re.compile(
        rf"<h[23]\b[^>]*>(?:(?!</h[23]>).)*\b{re.escape(heading)}\b(?:(?!</h[23]>).)*</h[23]>.*?(?=<h[23]\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return pattern.sub("", html)


def fetch_fandom_page(page: str, gaps_log: list[str]) -> str | None:
    query = urllib.parse.urlencode({
        "action": "parse",
        "page": page,
        "prop": "text",
        "format": "json",
        "redirects": "1",
        "disableeditsection": "1",
    })
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
    del keywords
    window = paragraph[:480].lower()
    base = title.lower()
    if not re.search(rf"\b{re.escape(base)}\b", window):
        return False
    if base in _SHORT_TITLES:
        return any(token in window for token in ("sleep", "vessel", "track", "song", "fathom", "tomb", "cover", "creature"))
    return True


def resolve_kerrang_snapshots(gaps_log: list[str]) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for query in WAYBACK_CDX_QUERIES:
        raw = fetch_url(query, gaps_log)
        time.sleep(REQUEST_DELAY_SEC)
        if not raw:
            continue
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            gaps_log.append("Invalid JSON from Wayback CDX for Kerrang TPWBYT.")
            continue
        for row in rows[1:]:
            if len(row) < 3 or not str(row[1]).isdigit():
                continue
            timestamp, original = row[1], row[2]
            blob = original.lower()
            if "sleep" not in blob and "tomb" not in blob and "alkaline" not in blob:
                continue
            found[original] = {
                "timestamp": timestamp,
                "original_url": original,
                "wayback_url": f"https://web.archive.org/web/{timestamp}/{original}",
                "source_class": "editorial",
            }
    if not found:
        gaps_log.append("Wayback CDX vuota per le query Kerrang 2021-2022 su tomb / sleep-token.")
    return list(found.values())


def fetch_reddit_threads(query: str, gaps_log: list[str]) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    hosts = ("https://www.reddit.com", "https://old.reddit.com")
    raw = None
    for host in hosts:
        url = f"{host}/r/SleepToken/search.json?q={encoded}&restrict_sr=1&sort=top&t=all&limit=6"
        raw = fetch_url(url, gaps_log)
        if raw:
            break
        time.sleep(REQUEST_DELAY_SEC)
    if not raw:
        return []
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        gaps_log.append(f"Invalid JSON from Reddit search: {query}")
        return []
    threads: list[dict[str, Any]] = []
    for child in payload.get("data", {}).get("children", []):
        data = child.get("data", {})
        title = str(data.get("title", ""))
        selftext = str(data.get("selftext", ""))
        if len(selftext.strip()) < 160:
            continue
        if is_forbidden_content(title) or is_forbidden_content(selftext):
            continue
        summary = paraphrase_extract(selftext)
        if summary.lower().count("[riferimento testuale]") >= 3:
            continue
        created = data.get("created_utc")
        threads.append({
            "theory": f"[Thread: {title}] {summary}",
            "source_title": f"r/SleepToken - {title}",
            "url": "https://www.reddit.com" + str(data.get("permalink", "")),
            "date": time.strftime("%Y-%m-%d", time.gmtime(created)) if created else None,
            "source_class": "community",
        })
        if len(threads) >= 3:
            break
    return threads


def _null_or_gap(items: list[Any], reason: str) -> tuple[list[Any] | None, str | None]:
    if items:
        return items, None
    return None, reason


def _append_unique(bucket: list[dict[str, Any]], item: dict[str, Any], key: str, limit: int) -> None:
    if len(bucket) >= limit:
        return
    if any(existing.get(key) == item.get(key) for existing in bucket):
        return
    bucket.append(item)


def _symbol_gaps(symbols: dict[str, Any]) -> dict[str, Any]:
    filled = dict(symbols)
    reasons = {"sigil": _SIGIL_GAP, "rune": _RUNE_GAP}
    for key, value in list(filled.items()):
        if value is None:
            filled[f"{key}_gap_reason"] = reasons.get(key, "Nessun valore canonizzato per questo campo.")
    return filled


def _load_closed_source(src: dict[str, str], gaps: list[str], fandom_cache: dict[str, str | None]) -> str | None:
    if src["id"] == "fandom_tpwbyt":
        page = FANDOM_API_PAGES[src["id"]]
        html = fetch_fandom_page(page, gaps)
        fandom_cache[page] = html
        return html
    html = fetch_url(src["url"], gaps)
    if src["id"] == "lore_tpwbyt" and not html:
        gaps.append(f"Fallback lore URL: {LORE_TPWBYT_FALLBACK}")
        html = fetch_url(LORE_TPWBYT_FALLBACK, gaps)
        if html:
            src["url"] = LORE_TPWBYT_FALLBACK
    return html


def main() -> None:
    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    chapter_gaps: list[str] = []
    corpus: dict[str, dict[str, Any]] = {}
    fandom_cache: dict[str, str | None] = {}

    for src in CLOSED_SOURCES:
        html = _load_closed_source(src, chapter_gaps, fandom_cache)
        time.sleep(REQUEST_DELAY_SEC)
        if not html:
            continue
        parser = ParagraphExtractor()
        parser.feed(html)
        corpus[src["id"]] = {"meta": src, "paragraphs": parser.paragraphs}
        print(f"[SRC] {src['id']}: {len(parser.paragraphs)} paragrafi")

    kerrang_snapshots = resolve_kerrang_snapshots(chapter_gaps)
    kerrang_excerpts: list[dict[str, str]] = []
    for snap in kerrang_snapshots[:2]:
        html = fetch_url(snap["wayback_url"], chapter_gaps)
        time.sleep(REQUEST_DELAY_SEC)
        if not html:
            continue
        parser = ParagraphExtractor()
        parser.feed(html)
        for paragraph in parser.paragraphs:
            if len(kerrang_excerpts) >= 6:
                break
            lower = paragraph.lower()
            if any(token in lower for token in ("tomb", "alkaline", "atlantic", "vessel", "sleep token")):
                kerrang_excerpts.append({
                    "excerpt": paraphrase_extract(paragraph),
                    "url": snap["wayback_url"],
                    "original_url": snap["original_url"],
                    "timestamp": snap["timestamp"],
                    "source_class": "editorial",
                })

    written: list[str] = []
    for song in SONGS_CATALOG:
        song_gaps: list[str] = list(song.get("gaps", []))
        title = song["title"]
        keywords = [keyword.lower() for keyword in song.get("keywords", [title])]

        for item in corpus.values():
            meta = item["meta"]
            hits = [p for p in item["paragraphs"] if paragraph_matches(p, title, keywords)]
            for paragraph in hits[:2]:
                summary = paraphrase_extract(paragraph)
                if meta["source_class"] == "editorial":
                    _append_unique(song["editorial_reading"], {
                        "summary": summary,
                        "source_title": meta["title"],
                        "url": meta["url"],
                        "date": None,
                        "source_class": "editorial",
                    }, "summary", 8)
                else:
                    _append_unique(song["community_theories"], {
                        "theory": summary,
                        "source_title": meta["title"],
                        "url": meta["url"],
                        "source_class": "community",
                    }, "theory", 12)

        page = FANDOM_API_PAGES.get(title)
        if page:
            if page not in fandom_cache:
                fandom_cache[page] = fetch_fandom_page(page, song_gaps)
                time.sleep(REQUEST_DELAY_SEC)
            fandom_html = fandom_cache[page]
            if fandom_html:
                fandom_parser = ParagraphExtractor()
                fandom_parser.feed(fandom_html)
                kept = 0
                ordered = sorted(
                    fandom_parser.paragraphs,
                    key=lambda paragraph: 0 if "sea creature" in paragraph.lower() or "cover art" in paragraph.lower() else 1,
                )
                for paragraph in ordered:
                    if kept >= 3:
                        break
                    lower = paragraph.lower()
                    if paragraph_matches(paragraph, title, keywords) or any(
                        token in lower for token in ("fathom", "depth", "metre", "meter", "ocean")
                    ):
                        _append_unique(song["community_theories"], {
                            "theory": paraphrase_extract(paragraph),
                            "source_title": f"Sleep Token Collective Wiki - {title}",
                            "url": FANDOM_SONG_URLS[title],
                            "source_class": "community",
                        }, "theory", 12)
                        kept += 1

        query = REDDIT_SONG_QUERIES.get(title)
        if query:
            for thread in fetch_reddit_threads(query, song_gaps):
                _append_unique(song["community_theories"], thread, "url", 12)
            time.sleep(REQUEST_DELAY_SEC)

        quotes, quotes_gap = _null_or_gap(song["in_character_quotes"], _QUOTE_GAP)
        editorial, editorial_gap = _null_or_gap(song["editorial_reading"], "Nessuna lettura editoriale isolata.")
        references, references_gap = _null_or_gap(song["references"], "Nessun riferimento catalogato.")
        callbacks, callbacks_gap = _null_or_gap(song["callbacks"], "Nessun callback documentato.")
        theories, theories_gap = _null_or_gap(song["community_theories"], "Nessuna teoria di consenso registrata.")
        payload = {
            "title": title,
            "release": song["release"],
            "track_number": song["track_number"],
            "year": song["year"],
            "status": "active",
            "genius_annotations_archived": song["genius_annotations_count"],
            "local_archive_repair_note": song.get("local_archive_repair_note"),
            "era_role": song["era_role"],
            "in_character_quotes": quotes,
            "in_character_quotes_gap_reason": quotes_gap,
            "editorial_reading": editorial,
            "editorial_reading_gap_reason": editorial_gap,
            "symbols": _symbol_gaps(song["symbols"]),
            "references": references,
            "references_gap_reason": references_gap,
            "callbacks": callbacks,
            "callbacks_gap_reason": callbacks_gap,
            "community_theories": theories,
            "community_theories_gap_reason": theories_gap,
            "gaps": song_gaps,
        }
        out = CHAPTER_DIR / f"{song['slug']}.json"
        write_json(out, payload)
        written.append(str(out).replace("\\", "/"))
        print(f"[OK] {out}")

    wiki_paragraphs = corpus.get("wiki_tpwbyt", {}).get("paragraphs", [])
    chronology_hits = [
        paraphrase_extract(paragraph)
        for paragraph in wiki_paragraphs
        if any(token in paragraph.lower() for token in ("spinefarm", "lever", "september", "2021", "chart"))
    ][:4]
    producer = "George Lever" if any("lever" in item.lower() for item in chronology_hits) else None
    chapter = {
        "chapter_number": 2,
        "slug": "02-this-place-will-become-your-tomb",
        "title": "Capitolo 2 — This Place Will Become Your Tomb (2021) e la batimetria della discesa",
        "why_before_chapter_3": (
            "Dopo Sundowning e la Room Below, il secondo album sposta l'asse dalla terraferma agli abissi "
            "e va letto prima di Take Me Back to Eden: la discesa in fathom precede l'alchimia di Aqua Regia, "
            "fissa il lessico chimico di Alkaline e chiude il fondo oceanico da cui riparte Chokehold."
        ),
        "oceanic_architecture": {
            "concept_overview": (
                "Pubblicato il 24 settembre 2021. Se Sundowning era il ciclo solare, questo album è pressione idrostatica: "
                "dodici quote di community dalla fine della luce fino al Challenger Deep."
            ),
            "biblical_and_geographic_clues": (
                "Il titolo funziona da epitaffio. Le coordinate promozionali dell'era, nelle fonti di community, "
                "puntano a Point Nemo (48°52.6′S 123°23.6′W), il polo oceanico dell'inaccessibilità nel Pacifico meridionale."
            ),
            "point_nemo": {
                "latitude": "48°52.6′S",
                "longitude": "123°23.6′W",
                "reading_class": "community",
            },
            "alkaline_corrupted_text_resolution": (
                "La traccia 7 aveva un file locale di 22 caratteri. La scheda ricostruisce la scala del pH, "
                "la rana pescatrice della copertina e il video dei fili rossi. Il testo cantato non è stato ripristinato."
            ),
            "bathymetry_note": (
                "1 fathom = 1,8288 m. Le quote e le zone oceaniche restano reading_class=community: "
                "la pagina wiki dell'album non contiene una tabella in fathom. "
                "Le specie di copertina vengono dalla sezione Trivia di ogni brano."
            ),
        },
        "public_chronology": {
            "label": "Spinefarm Records",
            "release_date": "2021-09-24",
            "producer": producer,
            "producer_gap_reason": None if producer else "I paragrafi Wikipedia estratti non nominano il produttore.",
            "source_class": "editorial",
            "source_url": WIKI,
            "live_extracts": chronology_hits,
        },
        "bathymetric_table_track_by_track": {str(number): row for number, row in TPWBYT_BATHYMETRY.items()},
        "wayback_kerrang_snapshots": kerrang_snapshots,
        "wayback_kerrang_excerpts": kerrang_excerpts,
        "songs_processed": written,
        "sources_fetched": sorted(corpus),
        "gaps": chapter_gaps,
        "unclosed_gaps": _UNCLOSED_GAPS,
    }
    chapter_file = CHAPTER_DIR / "chapter.json"
    write_json(chapter_file, chapter)
    print(f"[OK] {chapter_file}")
    print(f"[GAPS] {len(chapter_gaps)}")


if __name__ == "__main__":
    main()
