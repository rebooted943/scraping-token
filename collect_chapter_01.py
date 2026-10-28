#!/usr/bin/env python3
"""
Sleep Token Lore Collector — Capitolo 1: Sundowning (2019), The Room Below (2020), 12 Sigilli.

Python 3.11+, solo libreria standard. Nessuna identità civile e nessun verso integrale:
i brani live arrivano già parafrasati. Un JSON per traccia più chapter.json.
Le letture geometriche dei sigilli restano source_class=community.
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

CHAPTER_DIR = Path("chapters/01-sundowning")
USER_AGENT = "Mozilla/5.0 (compatible; LoreArchivistBot/1.0; +https://example.org/lore-research)"
REQUEST_DELAY_SEC = 1.5
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

CLOSED_SOURCES: list[dict[str, str]] = [
    {
        "id": "lore_sundowning",
        "url": "https://loreofsleeptoken.com/sundowning/",
        "source_class": "community",
        "title": "Lore of Sleep Token - Sundowning Album & Sigils",
    },
    {
        "id": "lore_logo_sigils",
        "url": "https://loreofsleeptoken.com/logo/",
        "source_class": "community",
        "title": "Lore of Sleep Token - Logo & The 12 Sigils Geometry",
    },
    {
        "id": "fandom_sundowning",
        "url": "https://sleep-token-collective.fandom.com/wiki/Sundowning",
        "source_class": "community",
        "title": "Sleep Token Collective Wiki - Sundowning",
    },
    {
        "id": "fandom_room_below",
        "url": "https://sleep-token-collective.fandom.com/wiki/The_Room_Below",
        "source_class": "community",
        "title": "Sleep Token Collective Wiki - The Room Below",
    },
    {
        "id": "wiki_sundowning",
        "url": "https://en.wikipedia.org/wiki/Sundowning_(Sleep_Token_album)",
        "source_class": "editorial",
        "title": "Wikipedia - Sundowning (album)",
    },
    {
        "id": "louder_every_song_p1",
        "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song",
        "source_class": "editorial",
        "title": "Louder / Metal Hammer - The story behind every Sleep Token song (Page 1)",
    },
    {
        "id": "louder_every_song_p2",
        "url": "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/2",
        "source_class": "editorial",
        "title": "Louder / Metal Hammer - The story behind every Sleep Token song (Page 2)",
    },
    {
        "id": "boolin_lore",
        "url": "https://boolintunes.com/featured/the-lore-of-sleep-token/",
        "source_class": "editorial",
        "title": "Boolin Tunes - The Lore of Sleep Token (Sundowning Section)",
    },
]

FANDOM_API = "https://sleep-token-collective.fandom.com/api.php"
# L'HTML della wiki risponde 403. L'API pubblica legge la stessa voce.
FANDOM_API_PAGES: dict[str, str] = {
    "fandom_sundowning": "Sundowning",
    "fandom_room_below": "The Room Below",
    "The Night Does Not Belong to God": "The Night Does Not Belong to God",
    "The Offering": "The Offering",
    "Levitate": "Levitate",
    "Dark Signs": "Dark Signs",
    "Higher": "Higher",
    "Take Aim": "Take Aim",
    "Give": "Give",
    "Gods": "Gods",
    "Sugar": "Sugar",
    "Say That You Will": "Say That You Will",
    "Drag Me Under": "Drag Me Under",
    "Blood Sport": "Blood Sport",
    "Blood Sport (from the room below)": "Blood Sport",
    "Shelter (from the room below)": "Shelter",
    "When the Party's Over (from the room below)": "Sundowning",
    "I Wanna Dance With Somebody (from the room below)": "Sundowning",
}
FANDOM_SONG_URLS: dict[str, str] = {
    title: "https://sleep-token-collective.fandom.com/wiki/" + page.replace(" ", "_")
    for title, page in FANDOM_API_PAGES.items()
    if not title.startswith("fandom_")
}
KEYWORD_STOP = {"night", "light", "dream", "sleep", "cover", "video", "white", "black", "smile", "taste", "arms"}

# Il brief chiede kerrang.com/*sundowning* 2019-2021. Le catture stanno su www e la recensione
# d'album è del 2021-12-06, fuori da un confronto numerico con to=2021. Si tengono entrambe.
WAYBACK_CDX_QUERIES = (
    "https://web.archive.org/cdx/search/cdx?url=kerrang.com/*sundowning*&output=json&from=2019&to=2021&filter=statuscode:200&collapse=urlkey&limit=10",
    "https://web.archive.org/cdx/search/cdx?url=www.kerrang.com/*sundowning*&output=json&from=2019&to=20211231235959&filter=statuscode:200&collapse=urlkey&limit=10",
)
KERRANG_KNOWN_SNAPSHOT = {
    "timestamp": "20211206032254",
    "original_url": "https://www.kerrang.com/album-review-sleep-token-sundowning",
    "wayback_url": "https://web.archive.org/web/20211206032254/https://www.kerrang.com/album-review-sleep-token-sundowning",
    "source_class": "editorial",
}

REDDIT_SONG_QUERIES: dict[str, str] = {
    "The Night Does Not Belong to God": 'title:"The Night Does Not Belong to God" (lore OR meaning OR sigil OR Euclid)',
    "The Offering": 'title:"The Offering" (lore OR meaning OR sigil OR callback)',
    "Levitate": 'title:"Levitate" (lore OR meaning OR sigil OR theory)',
    "Dark Signs": 'title:"Dark Signs" (lore OR meaning OR sigil OR theory)',
    "Higher": 'title:"Higher" (lore OR meaning OR sigil OR theory)',
    "Take Aim": 'title:"Take Aim" (lore OR meaning OR sigil OR theory)',
    "Give": 'title:"Give" (lore OR meaning OR sigil OR theory)',
    "Gods": 'title:"Gods" (lore OR meaning OR sigil OR theory)',
    "Sugar": 'title:"Sugar" (lore OR meaning OR sigil OR theory)',
    "Say That You Will": 'title:"Say That You Will" (lore OR meaning OR sigil OR theory)',
    "Drag Me Under": 'title:"Drag Me Under" (lore OR meaning OR sigil OR theory)',
    "Blood Sport": 'title:"Blood Sport" (lore OR meaning OR sigil OR theory)',
    "Blood Sport (from the room below)": 'title:"Blood Sport" ("room below" OR piano OR lore)',
    "Shelter (from the room below)": 'title:"Shelter" ("room below" OR lore OR meaning)',
    "When the Party's Over (from the room below)": '("When the Party\'s Over" OR "Room Below") (lore OR meaning OR cover)',
    "I Wanna Dance With Somebody (from the room below)": '("I Wanna Dance With Somebody" OR "Room Below") (lore OR meaning OR cover)',
}

_DEPTH_GAP = (
    "La batimetria traccia-per-traccia in metri e fathom appartiene a "
    "This Place Will Become Your Tomb (Capitolo 2)."
)
_RUNE_GAP = (
    "Il cifrario runico lettera-per-lettera viene introdotto in Take Me Back to Eden (Capitolo 3)."
)
_SIGIL_GAP = (
    "Shelter e le due cover di The Room Below non hanno un glifo proprio: i sigilli di Sundowning "
    "sono 12, uno per traccia standard. Spinefarm non ha pubblicato una legenda che li battezzi; "
    "ogni lettura geometrica resta source_class=community."
)
_CREATURE_GAP = "Nessuna creatura specifica canonizzata per questa traccia."
_QUOTE_GAP = (
    "Nel ciclo Sundowning (2019-2020) non ci sono interviste traccia-per-traccia: "
    "restano i comunicati rituali del rilascio al tramonto."
)
_UNCLOSED_GAPS = [
    "Nessuna legenda ufficiale dei 12 sigilli oltre al titolo del brano. Letture alchemiche = community.",
    "Visualiser YouTube 2019 e il video pianistico di Blood Sport (from the room below) non sono acquisiti: youtube.com è bloccato.",
    "Silenzio stampa in-character sul ciclo 2019-2020, dopo le dichiarazioni raccolte nel Capitolo 0.",
]

# Letture geometriche di community, non canon. Nessun nome ufficiale del glifo oltre al titolo.
SUNDOWNING_SIGILS: dict[int, dict[str, str]] = {
    1: {
        "track": "The Night Does Not Belong to God",
        "release_date": "2019-06-20",
        "reading_class": "community",
        "geometry": "Asse verticale coronato da un rombo superiore aperto e segmenti diagonali simmetrici verso il basso.",
        "symbolic_reading": "Calare della notte al solstizio d'estate e chiave superiore dell'emblema madre.",
    },
    2: {
        "track": "The Offering",
        "release_date": "2019-07-04",
        "reading_class": "community",
        "geometry": "Calice o coppa rovesciata, losanga centrale e bracci protesi come fauci o altare.",
        "symbolic_reading": "Altare sacrificale e corpo centrale dell'emblema composito.",
    },
    3: {
        "track": "Levitate",
        "release_date": "2019-07-18",
        "reading_class": "community",
        "geometry": "Vertici ascendenti lungo uno stelo verticale, con ali laterali.",
        "symbolic_reading": "Ascensione e sublimazione alchemica: dallo stato terreno a quello aereo.",
    },
    4: {
        "track": "Dark Signs",
        "release_date": "2019-08-01",
        "reading_class": "community",
        "geometry": "Croce obliqua inscritta in un rombo spezzato, con tagli trasversali.",
        "symbolic_reading": "Incrocio fatale e presagio notturno ignorato.",
    },
    5: {
        "track": "Higher",
        "release_date": "2019-08-15",
        "reading_class": "community",
        "geometry": "Doppia cuspide contrapposta lungo l'asse verticale.",
        "symbolic_reading": "Escalation simmetrica del conflitto: ogni offesa alza il debito.",
    },
    6: {
        "track": "Take Aim",
        "release_date": "2019-08-29",
        "reading_class": "community",
        "geometry": "Mirino o punta di freccia che attraversa un rombo.",
        "symbolic_reading": "Desiderio unidirezionale e offerta di sé come bersaglio.",
    },
    7: {
        "track": "Give",
        "release_date": "2019-09-12",
        "reading_class": "community",
        "geometry": "Due semicerchi convergenti che formano un nodo al centro.",
        "symbolic_reading": "Patto di reciprocità in cui donatore e ricevente si fondono.",
    },
    8: {
        "track": "Gods",
        "release_date": "2019-09-26",
        "reading_class": "community",
        "geometry": "Figura tagliente a spada o folgore verticale, con guardia spezzata.",
        "symbolic_reading": "Ira divina e distruzione del tempio interiore.",
    },
    9: {
        "track": "Sugar",
        "release_date": "2019-10-10",
        "reading_class": "community",
        "geometry": "Esagono o rombo sfaccettato, simile a un cristallo o a una clessidra.",
        "symbolic_reading": "Cristallo di saccarosio e distillazione chimica della dipendenza.",
    },
    10: {
        "track": "Say That You Will",
        "release_date": "2019-10-24",
        "reading_class": "community",
        "geometry": "Stelo verticale attraversato da sbarre orizzontali e diagonali.",
        "symbolic_reading": "Contratto forzato e supplica che cerca di trattenere l'altro.",
    },
    11: {
        "track": "Drag Me Under",
        "release_date": "2019-11-07",
        "reading_class": "community",
        "geometry": "Tridente o ancora rivolta verso il basso.",
        "symbolic_reading": "Inverte la spinta di Levitate e punta al fondale di TPWBYT.",
    },
    12: {
        "track": "Blood Sport",
        "release_date": "2019-11-21",
        "reading_class": "community",
        "geometry": "Stemma spezzato alla base dell'asse centrale.",
        "symbolic_reading": "Arena del sacrificio compiuto. Chiude i 12 frammenti dell'emblema.",
    },
}

LOUDER = "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song"
LOUDER_P2 = LOUDER + "/2"
LORE = "https://loreofsleeptoken.com/sundowning/"
BOOLIN = "https://boolintunes.com/featured/the-lore-of-sleep-token/"
WIKI = "https://en.wikipedia.org/wiki/Sundowning_(Sleep_Token_album)"


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


def _song(**fields: Any) -> dict[str, Any]:
    symbols = {
        "sigil": fields.pop("sigil"),
        "depth": fields.pop("depth", None),
        "rune": None,
        "creature": fields.pop("creature", None),
        "object": fields.pop("object"),
        "color": fields.pop("color"),
    }
    fields["symbols"] = symbols
    fields.setdefault("in_character_quotes", [])
    fields.setdefault("gaps", [])
    return fields


SONGS_CATALOG: list[dict[str, Any]] = [
    _song(
        slug="01-the-night-does-not-belong-to-god",
        title="The Night Does Not Belong to God",
        release="Sundowning",
        track_number=1,
        year=2019,
        genius_annotations_count=2,
        keywords=["The Night Does Not Belong to God", "TNDNBTG", "sundown", "curtain", "Euclid"],
        era_role=(
            "Apre Sundowning e la trilogia, al tramonto del solstizio d'estate (20 giugno 2019). "
            "Con il buio cessa la giurisdizione divina diurna e inizia il regno di Sleep: "
            "l'amato esiste solo nel sonno."
        ),
        in_character_quotes=[{
            "quote": (
                "Parafrasi del comunicato Spinefarm del giugno 2019: il ciclo è una sequenza di offerte "
                "rilasciate al calare del sole nel Regno Unito, per invitare la congregazione nel dominio notturno di Sleep."
            ),
            "source_title": "Spinefarm Records / Sundowning launch, via Wikipedia chronology",
            "url": WIKI,
            "date": "2019-06-20",
            "source_class": "canon",
        }],
        editorial_reading=[_edit(
            "Louder e Boolin Tunes leggono gli arpeggi di synth e pianoforte come portale liturgico: "
            "la sindrome neurologica del tramonto (confusione e amnesia serale) diventa una teologia privata.",
            "Louder - The story behind every Sleep Token song", LOUDER, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[1],
        object="La cortina che cala al tramonto; vesti chiare macchiate d'ombra",
        color="Avorio della copertina che sfuma nel blu-nero crepuscolare",
        references=[
            _ref(
                "medicina / neuropsichiatria",
                "La sundowning syndrome è agitazione, delirio e perdita di memoria al calare del sole nei pazienti con demenza.",
                "Amnesia serale: al calare dell'ombra l'altro non viene più riconosciuto.",
                "Lore of Sleep Token - Sundowning", LORE,
            ),
            _ref(
                "teologia",
                "La notte viene sottratta al creatore di Genesi 1:5 e consegnata a una divinità onirica.",
                "Il titolo assegna la notte a un'entità diversa dal dio diurno.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
        ],
        callbacks=[
            _cb(
                "Thread the Needle / When the Bough Breaks (One, 2016)",
                "Riprende il ramo che si spezza e l'oscurità che scende come un sipario.",
                "Sleep Token Collective Wiki - The Night Does Not Belong to God",
                "https://sleep-token-collective.fandom.com/wiki/The_Night_Does_Not_Belong_to_God",
            ),
            _cb(
                "Euclid (Take Me Back to Eden, 2023)",
                "Euclid riprende progressione, ritmo e temi di questa apertura e chiude il ciclo: la notte resta a Vessel.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
        ],
        community_theories=[_theory(
            "Con 2 annotazioni Genius, la lettura ricorrente è un ciclo chiuso: ogni tramonto cancella il trauma e l'adorazione ricomincia.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        gaps=["2 annotazioni Genius in archivio. Il cardine della trilogia è ricostruito dal confronto con Euclid e dalla pagina Sundowning."],
    ),
    _song(
        slug="02-the-offering",
        title="The Offering",
        release="Sundowning",
        track_number=2,
        year=2019,
        genius_annotations_count=4,
        keywords=["The Offering", "sacrifice", "altar"],
        era_role=(
            "Seconda offerta (4 luglio 2019). Scena la notte, inizia il rito: Vessel offre corpo e anima a Sleep "
            "come comunione carnale e liturgica."
        ),
        editorial_reading=[_edit(
            "Louder la indica come inno d'apertura dei Rituals: groove djent e synth R&B trasformano l'eucaristia in un invito predatorio.",
            "Louder - The story behind every Sleep Token song", LOUDER, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[2],
        object="Offerta sull'altare; eucaristia invertita",
        color="Nero e oro liturgico",
        references=[_ref(
            "liturgia",
            "Inversione dell'eucaristia: il fedele implora la divinità di divorarlo per sentirsi desiderato.",
            "Il ritornello invita a consumare l'offerta.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[
            _cb("Jaws (2018)", "Prosegue il motivo delle fauci introdotto nel singolo del 2018.", "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial"),
            _cb(
                "Take Me Back to Eden (2023) e Vore (2023)",
                "L'imperativo del morso torna nel climax della title-track; essere inghiottiti è il tema di Vore.",
                "Sleep Token Collective Wiki - The Offering",
                "https://sleep-token-collective.fandom.com/wiki/The_Offering",
            ),
        ],
        community_theories=[_theory(
            "Il contratto volontario legittima gli abusi successivi: chi ha chiesto di essere consumato non può ritirare il voto senza romperlo.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
    ),
    _song(
        slug="03-levitate",
        title="Levitate",
        release="Sundowning",
        track_number=3,
        year=2019,
        genius_annotations_count=4,
        keywords=["Levitate", "angels", "gravity"],
        era_role=(
            "Terza offerta (18 luglio 2019). Prima disillusione asimmetrica: l'altro sale verso la guarigione, "
            "Vessel resta a terra per peso e trauma."
        ),
        editorial_reading=[_edit(
            "Ballata al pianoforte che esplode nel post-metal. La stampa legge un abbandono verticale: l'ascensione dell'altro non è condivisa.",
            "Louder - The story behind every Sleep Token song", LOUDER, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[3],
        creature="Figure alate irraggiungibili",
        object="Gravità, massa, sangue",
        color="Bianco etereo contro grigio piombo",
        references=[_ref(
            "fisica / escatologia",
            "La levitazione mistica è contrapposta alla massa che trattiene il corpo ferito.",
            "Domanda ricorrente: l'altro può salire dove il narratore non arriva.",
            "Sleep Token Collective Wiki - Levitate",
            "https://sleep-token-collective.fandom.com/wiki/Levitate",
        )],
        callbacks=[_cb(
            "Drag Me Under (traccia 11) e Ascensionism (2023)",
            "L'asse verticale dell'album: chi non sale in Levitate viene trascinato giù in Drag Me Under. Ascensionism ribalta la spinta.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        community_theories=[_theory(
            "L'anima che sale dimenticando chi resta può essere sia la morte di una persona cara sia il distacco di un partner che ha chiuso la rottura.",
            "Sleep Token Collective Wiki - Levitate",
            "https://sleep-token-collective.fandom.com/wiki/Levitate",
        )],
    ),
    _song(
        slug="04-dark-signs",
        title="Dark Signs",
        release="Sundowning",
        track_number=4,
        year=2019,
        genius_annotations_count=10,
        keywords=["Dark Signs", "omen", "alarm", "scars"],
        era_role=(
            "Quarta offerta (1 agosto 2019). Lucidità retrospettiva: i presagi c'erano prima del patto e sono stati ignorati."
        ),
        editorial_reading=[_edit(
            "Dark-pop e beat elettronico. Il mito si fonde con il rimpianto per l'autodistruzione.",
            "Louder - The story behind every Sleep Token song", LOUDER, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[4],
        object="Fari nella nebbia, allarmi, presagi",
        color="Nero pece e rosso d'allarme",
        references=[_ref(
            "divinazione / incidente notturno",
            "Il lessico degli auspici si sovrappone a un incidente per assenza di visibilità.",
            "Segnali oscuri visti e campanelli d'allarme ignorati, da un passato già nero.",
            "Sleep Token Collective Wiki - Dark Signs",
            "https://sleep-token-collective.fandom.com/wiki/Dark_Signs",
        )],
        callbacks=[_cb(
            "Granite (2023)",
            "La guida notturna verso uno schianto anticipa la metafora automobilistica di Granite.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        community_theories=[_theory(
            "Smonta l'alibi dell'innocenza: Vessel arriva già da un luogo nero e cerca una forza che lo distrugga.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
    ),
    _song(
        slug="05-higher",
        title="Higher",
        release="Sundowning",
        track_number=5,
        year=2019,
        genius_annotations_count=13,
        keywords=["Higher", "debt", "fire"],
        era_role=(
            "Quinta offerta (15 agosto 2019). Il legame è simmetrico: le due parti si feriscono e il debito emotivo sale."
        ),
        editorial_reading=[_edit(
            "Boolin Tunes lo legge come ritratto della codipendenza tossica travestita da culto, retto dall'intreccio ritmico di II.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        sigil=SUNDOWNING_SIGILS[5],
        object="Fuoco e ghiaccio, cicatrici, bilancia del debito",
        color="Rosso brace e azzurro glaciale",
        references=[_ref(
            "economia morale",
            "Il debito si accumula a ogni offesa, tra freddezza glaciale e impulsività incendiaria.",
            "Il mantra finale fa salire il debito sempre più in alto.",
            "Sleep Token Collective Wiki - Higher",
            "https://sleep-token-collective.fandom.com/wiki/Higher",
        )],
        callbacks=[_cb(
            "The Summoning / Ascensionism (2023)",
            "La guerra psicologica tra due entità che non si lasciano prepara il conflitto centrale di Take Me Back to Eden.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        community_theories=[_theory(
            "Scompare il confine tra vittima e carnefice: Vessel è una minaccia per l'altro quanto Sleep lo è per lui.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
    ),
    _song(
        slug="06-take-aim",
        title="Take Aim",
        release="Sundowning",
        track_number=6,
        year=2019,
        genius_annotations_count=1,
        keywords=["Take Aim", "arrow", "weapons"],
        era_role=(
            "Sesta offerta (29 agosto 2019), a metà album. Dopo Higher, Vessel torna alla supplica: "
            "chiede di essere colpito, purché l'altro finga di amarlo."
        ),
        editorial_reading=[_edit(
            "Louder nota l'orchestrazione eterea e il falsetto quasi gospel, in contrasto con il masochismo del tema.",
            "Louder - The story behind every Sleep Token song", LOUDER, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[6],
        creature="Preda volontaria",
        object="Arco, freccia e mirino, che è anche il sigillo della traccia",
        color="Oro pallido e bianco",
        references=[_ref(
            "mitologia / martirio",
            "Freccia d'amore e martirio volontario, sull'iconografia di chi invita l'arciere a mirare al petto.",
            "Invito a prendere la mira e a spezzare il narratore pur di farlo sentire amato.",
            "Sleep Token Collective Wiki - Take Aim",
            "https://sleep-token-collective.fandom.com/wiki/Take_Aim",
        )],
        callbacks=[_cb(
            "The Love You Want (TPWBYT, 2021)",
            "Armi, lame e il tentativo di conformarsi al desiderio dell'altro continuano nel quinto brano del secondo album.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        community_theories=[_theory(
            "Con 1 annotazione Genius, i thread leggono la regressione massima: sapendo che l'amore di Sleep è letale, Vessel preferisce la ferita all'indifferenza.",
            "Sleep Token Collective Wiki - Take Aim",
            "https://sleep-token-collective.fandom.com/wiki/Take_Aim",
        )],
        gaps=["1 annotazione Genius. Integrato con la wiki e con r/SleepToken."],
    ),
    _song(
        slug="07-give",
        title="Give",
        release="Sundowning",
        track_number=7,
        year=2019,
        genius_annotations_count=2,
        keywords=["Give", "shadows", "promises"],
        era_role=(
            "Settima offerta (12 settembre 2019). La seconda metà dell'album passa dalla supplica al possesso reciproco nel buio."
        ),
        editorial_reading=[_edit(
            "R&B notturno. La voce diventa protettiva e insieme ossessiva.",
            "Louder - The story behind every Sleep Token song", LOUDER, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[7],
        creature="Predatori nell'ombra",
        object="Ombre intrecciate, giaciglio notturno",
        color="Indaco e ambra",
        references=[_ref(
            "patto",
            "Riformulazione del do ut des: proteggere e imprigionare nel buio diventano lo stesso gesto.",
            "Promessa di dare in misura uguale a ciò che viene concesso nell'oscurità.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[_cb(
            "Mine (2021) e Provider (2025)",
            "Anticipa il possesso devoto di Mine e il ruolo di chi provvede in Provider.",
            "Sleep Token Collective Wiki - Give",
            "https://sleep-token-collective.fandom.com/wiki/Give",
        )],
        community_theories=[_theory(
            "Lettura diffusa: la traccia è cantata da Sleep, o dalle due voci sovrapposte, che seduce promettendo protezione in cambio dell'anima.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        gaps=["2 annotazioni Genius. Integrata la lettura a prospettiva invertita."],
    ),
    _song(
        slug="08-gods",
        title="Gods",
        release="Sundowning",
        track_number=8,
        year=2019,
        genius_annotations_count=3,
        keywords=["Gods", "broken glass", "heaven"],
        era_role=(
            "Ottava offerta (26 settembre 2019). Dopo la seduzione di Give, la devozione cade in un assalto heavy: "
            "silenzio e crudeltà degli dèi."
        ),
        editorial_reading=[_edit(
            "All'uscita era il brano più pesante del catalogo, accostato dalla stampa a Loathe e ai Deftones, con scream dal primo istante.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[8],
        creature="Divinità cadute",
        object="Vetro infranto, denti spezzati",
        color="Cremisi e nero",
        references=[_ref(
            "tragedia",
            "Rovesciamento del pantheon: quando il paradiso brucia non resta un dio a cui pregare, solo un culto tradito.",
            "Interrogativo sarcastico sull'assenza degli dèi nel momento della rovina.",
            "Sleep Token Collective Wiki - Gods",
            "https://sleep-token-collective.fandom.com/wiki/Gods",
        )],
        callbacks=[_cb(
            "Nazareth (2017) e Vore (2023)",
            "Anello centrale dei brani estremi, tra Nazareth e lo scream di Vore.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
        )],
        community_theories=[_theory(
            "Primo tentativo di ribellione contro Sleep, oppure furia di Sleep che punisce l'infedeltà. La traccia successiva, Sugar, è la ricaduta.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
    ),
    _song(
        slug="09-sugar",
        title="Sugar",
        release="Sundowning",
        track_number=9,
        year=2019,
        genius_annotations_count=15,
        keywords=["Sugar", "addiction"],
        era_role=(
            "Nona offerta (10 ottobre 2019). La ribellione di Gods fallisce perché il legame agisce come dipendenza chimica."
        ),
        editorial_reading=[_edit(
            "Slow-burn R&B che esplode nel blues-metal. La stampa lo legge come ossessione erotica che divora la volontà.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[9],
        object="Cristalli di zucchero, veleno dolce",
        color="Ambra e viola scuro",
        references=[_ref(
            "neurobiologia",
            "Lo zucchero è l'archetipo della ricompensa immediata che maschera la tossicità.",
            "Confessione di un gusto ossessivo e irreversibile per l'altro.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[_cb(
            "Alkaline (2021), Aqua Regia (2023), Caramel (2025)",
            "Apre le metafore chimiche: zucchero, pH, acido che scioglie l'oro, zucchero bruciato.",
            "Sleep Token Collective Wiki - Sugar",
            "https://sleep-token-collective.fandom.com/wiki/Sugar",
        )],
        community_theories=[_theory(
            "Subito dopo Gods riproduce il ciclo del trauma bonding: all'esplosione segue la riconciliazione che reincatena.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
    ),
    _song(
        slug="10-say-that-you-will",
        title="Say That You Will",
        release="Sundowning",
        track_number=10,
        year=2019,
        genius_annotations_count=4,
        keywords=["Say That You Will", "impulse", "leaves"],
        era_role=(
            "Decima offerta (24 ottobre 2019). Finita l'euforia di Sugar, resta il terrore dell'abbandono: "
            "basta una falsa promessa per attraversare l'inverno."
        ),
        editorial_reading=[_edit(
            "Traccia spesso sottovalutata: dalla voce quasi sussurrata a un muro di chitarre.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[10],
        creature="Falena attratta dalla luce artificiale",
        object="Foglie che cadono, luce accecante",
        color="Grigio autunnale e bianco freddo",
        references=[_ref(
            "entomologia",
            "Fototassi: l'insetto notturno scambia una luce artificiale per la luna e si brucia.",
            "Essere ipnotizzati da una luce e cedere all'impulso autodistruttivo.",
            "Sleep Token Collective Wiki - Say That You Will",
            "https://sleep-token-collective.fandom.com/wiki/Say_That_You_Will",
        )],
        callbacks=[_cb(
            "Thread the Needle (2016) e l'artwork di Take Me Back to Eden (2023)",
            "Le falene notturne sono già nel primo video e tornano nell'artwork del terzo album.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        community_theories=[_theory(
            "Il rilascio di fine ottobre coincide con le foglie morte del tema: il ciclo solare muore verso il solstizio d'inverno.",
            "Sleep Token Collective Wiki - Say That You Will",
            "https://sleep-token-collective.fandom.com/wiki/Say_That_You_Will",
        )],
    ),
    _song(
        slug="11-drag-me-under",
        title="Drag Me Under",
        release="Sundowning",
        track_number=11,
        year=2019,
        genius_annotations_count=0,
        keywords=["Drag Me Under", "underwater", "Atlantic"],
        era_role=(
            "Undicesima offerta (7 novembre 2019). Priorità d'archivio: 0 annotazioni Genius. "
            "Vessel smette di lottare e accetta la sommersione. È il preludio diretto di Atlantic."
        ),
        editorial_reading=[_edit(
            "Boolin Tunes la descrive come ninna nanna funebre per pianoforte e voci riverberate, senza percussioni: la resa suona serena.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        sigil=SUNDOWNING_SIGILS[11],
        depth="Superficie dell'acqua, prima dell'immersione di Atlantic. Non è ancora una quota in metri.",
        creature="Angeli del profondo",
        object="L'acqua che si chiude sopra la testa",
        color="Blu abissale e argento lunare",
        references=[_ref(
            "sonno / mito acquatico",
            "Paralisi ipnagogica (sprofondare mentre ci si addormenta) fusa con le figure che trascinano i mortali col sorriso.",
            "Invocazione a essere trascinati giù quando le figure celesti hanno perso la voce.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[
            _cb(
                "Levitate (traccia 3)",
                "Simmetria interna: in traccia 3 le figure salgono; in traccia 11 tacciono e il moto diventa caduta.",
                "Sleep Token Collective Wiki - Drag Me Under",
                "https://sleep-token-collective.fandom.com/wiki/Drag_Me_Under",
            ),
            _cb(
                "Atlantic (TPWBYT, traccia 1, 2021)",
                "Essere trascinati sotto la superficie conduce al risveglio dopo l'annegamento di Atlantic.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
        ],
        community_theories=[_theory(
            "Punto di svolta tra i primi due album: l'elemento dominante passa dall'aria e dalla notte all'acqua e all'abisso.",
            "Sleep Token Collective Wiki - Drag Me Under",
            "https://sleep-token-collective.fandom.com/wiki/Drag_Me_Under",
        )],
        gaps=["0 annotazioni Genius. Chiuso incrociando Boolin Tunes, loreofsleeptoken.com, la wiki e la simmetria con Levitate e Atlantic."],
    ),
    _song(
        slug="12-blood-sport",
        title="Blood Sport",
        release="Sundowning",
        track_number=12,
        year=2019,
        genius_annotations_count=3,
        keywords=["Blood Sport", "crimson", "weapon"],
        era_role=(
            "Dodicesima offerta (21 novembre 2019). L'adorazione non redime: diventa un'arena. "
            "In studio il brano si chiude sul pianto non filtrato di Vessel."
        ),
        editorial_reading=[_edit(
            "Kerrang! e Metal Hammer lo indicano come vertice emotivo: i singhiozzi finali rompono la maschera rituale.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[12],
        creature="Predatore e preda nella stessa arena",
        object="L'arma scelta dall'altro, il sangue, le lacrime finali",
        color="Rosso sangue sul bianco della copertina",
        references=[_ref(
            "arena",
            "La devozione è un combattimento il cui scopo è lo spargimento di sangue, non la pace.",
            "Riconoscimento di un errore fatale: uno sport di sangue da cui il paradiso non li accoglie.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[_cb(
            "Take Aim (traccia 6) e Euclid (2023)",
            "Riprende l'essere l'arma scelta dall'altro e prepara la catarsi di Euclid.",
            "Sleep Token Collective Wiki - Blood Sport",
            "https://sleep-token-collective.fandom.com/wiki/Blood_Sport",
        )],
        community_theories=[_theory(
            "I singhiozzi sono la prima incrinatura del contenitore. Aver sbagliato ad accettare il patto apre la crisi di TPWBYT.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN,
        )],
    ),
    _song(
        slug="13-blood-sport-from-the-room-below",
        title="Blood Sport (from the room below)",
        release="Sundowning (Deluxe) / The Room Below",
        track_number=13,
        year=2020,
        genius_annotations_count=0,
        keywords=["Blood Sport", "from the room below", "piano"],
        era_role=(
            "Apre l'appendice del 20 giugno 2020, un anno dopo l'inizio del ciclo. "
            "Toglie la band e lascia Vessel al pianoforte, in una stanza sotto il rito."
        ),
        editorial_reading=[_edit(
            "Pubblicata con un piano-sequenza al pianoforte. Inaugura The Room Below come cripta sotto il palco rituale.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        sigil=SUNDOWNING_SIGILS[12],
        depth="Livello ipogeo: The Room Below, sotto la superficie e prima della batimetria oceanica.",
        object="Pianoforte isolato nel buio",
        color="Chiaroscuro",
        references=[_ref(
            "architettura sacra",
            "La Room Below funziona come la cripta sotto l'altare: il sacerdote si spoglia dei paramenti e confessa da solo.",
            "Etichetta ufficiale 'from the room below' sulle quattro tracce bonus del 2020.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[_cb(
            "Blood Sport (traccia 12, 2019)",
            "Riesecuzione per voce e pianoforte della chiusura dell'album standard.",
            "Sleep Token Collective Wiki - Blood Sport",
            "https://sleep-token-collective.fandom.com/wiki/Blood_Sport",
        )],
        community_theories=[_theory(
            "Limbo tra il tramonto e la tomba oceanica: la discesa sotto il suolo precede l'Atlantico.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
    ),
    _song(
        slug="14-shelter-from-the-room-below",
        title="Shelter (from the room below)",
        release="Sundowning (Deluxe) / The Room Below",
        track_number=14,
        year=2020,
        genius_annotations_count=0,
        keywords=["Shelter", "from the room below", "wings"],
        era_role=(
            "Unico inedito dell'appendice (giugno 2020). Lato protettivo: Vessel offre un rifugio, "
            "sapendo quanto pesano i segreti custoditi."
        ),
        editorial_reading=[_edit(
            "Ballata pianistica che mostra la scrittura nuda, senza la produzione stratificata dell'album.",
            "Louder - The story behind every Sleep Token song (Page 2)", LOUDER_P2, "2023-05-19",
        )],
        sigil=None,
        depth="The Room Below, spazio ipogeo protetto.",
        object="Riparo dalla tempesta; ali chiuse",
        color="Seppia",
        references=[_ref(
            "attaccamento",
            "Santuario in cui due anime ferite si riparano dal mondo, anche quando il riparo diventa prigione.",
            "Offerta di essere un rifugio nonostante il dolore.",
            "Sleep Token Collective Wiki - Shelter",
            "https://sleep-token-collective.fandom.com/wiki/Shelter",
        )],
        callbacks=[_cb(
            "Give (traccia 7) e Euclid (2023)",
            "La promessa protettiva di Give, in chiave acustica, e la tenerezza che chiude la trilogia.",
            "Sleep Token Collective Wiki - Shelter",
            "https://sleep-token-collective.fandom.com/wiki/Shelter",
        )],
        community_theories=[_theory(
            "Ipotesi ricorrente: scritto durante Sundowning ed escluso dai 12 perché troppo empatico per la griglia dei sigilli.",
            "Sleep Token Collective Wiki - Shelter",
            "https://sleep-token-collective.fandom.com/wiki/Shelter",
        )],
    ),
    _song(
        slug="15-when-the-partys-over-from-the-room-below",
        title="When the Party's Over (from the room below)",
        release="Sundowning (Deluxe) / The Room Below (cover)",
        track_number=15,
        year=2020,
        genius_annotations_count=0,
        keywords=["When the Party's Over", "Billie Eilish", "room below"],
        era_role=(
            "Cover (Billie Eilish / Finneas, 2018) scelta perché la festa illusoria di Sundowning è finita "
            "e resta da lasciare andare chi fa del male. Nessun verso del brano originale è archiviato."
        ),
        editorial_reading=[_edit(
            "La critica nota l'incontro tra il falsetto di Vessel e il minimalismo funebre del brano del 2018.",
            "Wikipedia - Sundowning (album)", WIKI, "2020-06-20",
        )],
        sigil=None,
        depth="The Room Below",
        object="Silenzio dopo il rito",
        color="Bianco e nero",
        references=[_ref(
            "cover",
            "Rielaborazione per pianoforte e voce. Si archivia solo la funzione: la fine dell'illusione collettiva.",
            "Tema del silenzio che resta quando la festa finisce, senza citazione del testo originale.",
            "Sleep Token Collective Wiki - Sundowning",
            "https://sleep-token-collective.fandom.com/wiki/Sundowning",
        )],
        callbacks=[_cb(
            "Hey Ya (2018) e Missing Limbs (2021)",
            "Prosegue la linea di cover intime sulla rassegnazione dopo la rottura.",
            "Sleep Token Collective Wiki - Sundowning",
            "https://sleep-token-collective.fandom.com/wiki/Sundowning",
        )],
        community_theories=[_theory(
            "La community collega il pianto della cover all'acqua salata del secondo album, senza trattare il testo originale come lore primaria.",
            "Sleep Token Collective Wiki - Sundowning",
            "https://sleep-token-collective.fandom.com/wiki/Sundowning",
        )],
    ),
    _song(
        slug="16-i-wanna-dance-with-somebody-from-the-room-below",
        title="I Wanna Dance With Somebody (from the room below)",
        release="Sundowning (Deluxe) / The Room Below (cover)",
        track_number=16,
        year=2020,
        genius_annotations_count=0,
        keywords=["I Wanna Dance With Somebody", "Whitney Houston", "sundown"],
        era_role=(
            "Chiusura del Deluxe (giugno 2020). Cover di Whitney Houston (Merrill / Rubicam, 1987) scelta perché "
            "l'incipit originale nomina l'orologio, il tramonto e la solitudine notturna: la definizione umana di Sundowning. "
            "Il verso non è archiviato."
        ),
        editorial_reading=[_edit(
            "Come Hey Ya nel 2018, un inno da discoteca diventa una ballata funebre al pianoforte sulla solitudine serale.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        sigil=None,
        depth="The Room Below",
        object="L'orologio che segna il tramonto",
        color="Nero",
        references=[_ref(
            "cover",
            "Il brano del 1987 è scelto per l'angoscia che subentra quando cala il sole, non per il ritornello da dancefloor.",
            "Legame tematico tra il tramonto nella prima strofa originale e il titolo Sundowning. Testo non riprodotto.",
            "Lore of Sleep Token - Sundowning", LORE,
        )],
        callbacks=[
            _cb(
                "Hey Ya (2018) e Dancing in the Dark (2018)",
                "Chiude le cover decostruite al pianoforte sul ballare da soli nel buio.",
                "Sleep Token Collective Wiki - Sundowning",
                "https://sleep-token-collective.fandom.com/wiki/Sundowning",
            ),
            _cb(
                "The Night Does Not Belong to God (traccia 1)",
                "Torna all'immagine del sole che tramonta da cui era partita la traccia 1.",
                "Lore of Sleep Token - Sundowning", LORE,
            ),
        ],
        community_theories=[_theory(
            "Tolta la mitologia dei sigilli, alla radice del patto resta il bisogno di calore umano quando scende la sera.",
            "Lore of Sleep Token - Sundowning", LORE,
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
    """Toglie le citazioni lunghe. Resta solo la sintesi analitica."""
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
    """Il titolo deve stare nella finestra che poi salviamo, così un saggio lungo non attacca la traccia sbagliata."""
    del keywords
    window = paragraph[:480].lower()
    base = title.lower().replace(" (from the room below)", "")
    if len(base) < 6:
        return re.search(rf"\b{re.escape(base)}\b", window) is not None
    return base in window


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
            gaps_log.append("Invalid JSON from Wayback CDX for Kerrang Sundowning.")
            continue
        for row in rows[1:]:
            if len(row) >= 3 and str(row[1]).isdigit():
                timestamp, original = row[1], row[2]
                found[original] = {
                    "timestamp": timestamp,
                    "original_url": original,
                    "wayback_url": f"https://web.archive.org/web/{timestamp}/{original}",
                    "source_class": "editorial",
                }
    if not found:
        gaps_log.append(
            "Wayback CDX vuota per kerrang.com/*sundowning*. "
            f"Fallback allo snapshot noto {KERRANG_KNOWN_SNAPSHOT['timestamp']}."
        )
        found[KERRANG_KNOWN_SNAPSHOT["original_url"]] = dict(KERRANG_KNOWN_SNAPSHOT)
    return list(found.values())


def fetch_reddit_threads(query: str, gaps_log: list[str]) -> list[dict[str, Any]]:
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
    reasons = {
        "sigil": _SIGIL_GAP,
        "depth": _DEPTH_GAP,
        "rune": _RUNE_GAP,
        "creature": _CREATURE_GAP,
    }
    for key, value in list(filled.items()):
        if value is None:
            filled[f"{key}_gap_reason"] = reasons.get(key, "Nessun valore canonizzato per questo campo.")
    return filled


def main() -> None:
    CHAPTER_DIR.mkdir(parents=True, exist_ok=True)
    chapter_gaps: list[str] = []
    corpus: dict[str, dict[str, Any]] = {}
    fandom_cache: dict[str, str | None] = {}

    for src in CLOSED_SOURCES:
        page = FANDOM_API_PAGES.get(src["id"])
        html = None
        if page:
            candidates = [page]
            if src["id"] == "fandom_room_below":
                candidates = ["The Room Below", "From the Room Below", "Blood Sport (From the Room Below)"]
            for candidate in candidates:
                html = fetch_fandom_page(candidate, chapter_gaps)
                if html:
                    page = candidate
                    break
                time.sleep(REQUEST_DELAY_SEC)
            fandom_cache[page] = html
        else:
            html = fetch_url(src["url"], chapter_gaps)
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
            if any(token in lower for token in ("sundown", "sigil", "room below", "vessel", "blood sport")):
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
                for paragraph in fandom_parser.paragraphs:
                    if kept >= 3:
                        break
                    if paragraph_matches(paragraph, title, keywords) or "sigil" in paragraph.lower():
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

    wiki_paragraphs = corpus.get("wiki_sundowning", {}).get("paragraphs", [])
    chronology_hits = [
        paraphrase_extract(paragraph)
        for paragraph in wiki_paragraphs
        if any(token in paragraph.lower() for token in ("lever", "spinefarm", "deluxe", "november 2019", "june 2020"))
    ][:4]
    producer = "George Lever" if any("lever" in item.lower() for item in chronology_hits) else None
    chapter = {
        "chapter_number": 1,
        "slug": "01-sundowning",
        "title": "Capitolo 1 — Sundowning (2019), The Room Below (2020) e i 12 Sigilli",
        "why_before_chapter_2": (
            "Sundowning apre la trilogia prima di This Place Will Become Your Tomb: ciclo quindicinale al tramonto, "
            "doppio senso clinico e mitico del titolo, primo sistema di 12 sigilli, e la Room Below come soglia verticale verso l'abisso."
        ),
        "release_cycle_mechanics": {
            "biweekly_sundown_ritual": (
                "Dal 20 giugno 2019 (solstizio d'estate) al 21 novembre 2019, una traccia ogni due settimane "
                "al tramonto nel Regno Unito, ciascuna con un visualiser e un sigillo."
            ),
            "medical_and_mythic_meaning": (
                "Sundowning unisce la sindrome clinica del tramonto (agitazione, delirio, amnesia serale) "
                "al momento in cui la mente diurna cede e inizia il dominio di Sleep."
            ),
            "the_room_below_2020": (
                "Il 20 giugno 2020 il Deluxe aggiunge quattro brani from the room below: Blood Sport al pianoforte, "
                "l'inedito Shelter, e le cover di Billie Eilish e Whitney Houston. La cripta prepara TPWBYT."
            ),
        },
        "public_chronology": {
            "label": "Spinefarm Records",
            "producer": producer,
            "producer_gap_reason": None if producer else "I paragrafi Wikipedia estratti non nominano il produttore.",
            "standard_window": "2019-06-20 — 2019-11-21",
            "deluxe_date": "2020-06-20",
            "press_named": ["Kerrang!", "Metal Hammer", "Distorted Sound"],
            "source_class": "editorial",
            "source_url": WIKI,
            "note": "Cronologia pubblica. I paragrafi live di Wikipedia sono in live_extracts; Louder e Kerrang sono accodati ai singoli brani.",
            "live_extracts": chronology_hits,
        },
        "the_12_sigils_table": {str(number): sigil for number, sigil in SUNDOWNING_SIGILS.items()},
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
