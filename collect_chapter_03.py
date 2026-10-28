#!/usr/bin/env python3
"""
Sleep Token Lore Collector — Capitolo 3: Take Me Back to Eden (2023).

Python 3.11+, solo libreria standard. Nessuna identità civile e nessun verso integrale.
Il cifrario runico e le 12 creature restano reading_class=community finché una fonte live
non le conferma. I glifi non sono Unicode: nessuna conversione SVG. Un JSON per traccia
più chapter.json.
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

CHAPTER_DIR = Path("chapters/03-take-me-back-to-eden")
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

LORE_TMBTE = "https://loreofsleeptoken.com/tmbte/"
LORE_TMBTE_FALLBACK = "https://loreofsleeptoken.com/take-me-back-to-eden/"
LORE_MAIN = "https://loreofsleeptoken.com/the-lore/"
OMNIGLOT = "https://www.omniglot.com/conscripts/sleeptokenalphabet.htm"
FANDOM_ALBUM = "https://sleep-token-collective.fandom.com/wiki/Take_Me_Back_To_Eden_(album)"
WIKI = "https://en.wikipedia.org/wiki/Take_Me_Back_to_Eden"
LOUDER_P3 = "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/3"
LOUDER_P4 = "https://www.loudersound.com/features/the-story-behind-every-sleep-token-song/4"
BOOLIN = "https://boolintunes.com/featured/the-lore-of-sleep-token/"
FANDOM_API = "https://sleep-token-collective.fandom.com/api.php"

CLOSED_SOURCES: list[dict[str, str]] = [
    {"id": "omniglot_alphabet", "url": OMNIGLOT, "source_class": "editorial", "title": "Omniglot - Sleep Token Alphabet"},
    {"id": "lore_tmbte", "url": LORE_TMBTE, "source_class": "community", "title": "Lore of Sleep Token - Take Me Back to Eden"},
    {"id": "lore_main", "url": LORE_MAIN, "source_class": "community", "title": "Lore of Sleep Token - Trilogy Resolution"},
    {"id": "fandom_tmbte", "url": FANDOM_ALBUM, "source_class": "community", "title": "Sleep Token Collective Wiki - Take Me Back to Eden"},
    {"id": "fandom_runes", "url": FANDOM_ALBUM, "source_class": "community", "title": "Sleep Token Collective Wiki - Runes (sezione album)"},
    {"id": "wiki_tmbte", "url": WIKI, "source_class": "editorial", "title": "Wikipedia - Take Me Back to Eden"},
    {"id": "louder_every_song_p3", "url": LOUDER_P3, "source_class": "editorial", "title": "Louder / Metal Hammer - The story behind every Sleep Token song (Page 3)"},
    {"id": "louder_every_song_p4", "url": LOUDER_P4, "source_class": "editorial", "title": "Louder / Metal Hammer - The story behind every Sleep Token song (Page 4)"},
    {"id": "boolin_lore", "url": BOOLIN, "source_class": "editorial", "title": "Boolin Tunes - The Lore of Sleep Token (Eden Finale)"},
]

FANDOM_API_PAGES: dict[str, str] = {
    "fandom_tmbte": "Take Me Back To Eden (album)",
    "Chokehold": "Chokehold",
    "The Summoning": "The Summoning",
    "Granite": "Granite",
    "Aqua Regia": "Aqua Regia",
    "Vore": "Vore",
    "Ascensionism": "Ascensionism",
    "Are You Really Okay?": "Are You Really Okay?",
    "The Apparition": "The Apparition",
    "DYWTYLM": "DYWTYLM",
    "Rain": "Rain",
    "Take Me Back to Eden": "Take Me Back To Eden (song)",
    "Euclid": "Euclid",
}
RUNE_PAGE_CANDIDATES = ("Runes", "Alphabet", "Take Me Back To Eden (album)")

FANDOM_SONG_URLS: dict[str, str] = {
    title: "https://sleep-token-collective.fandom.com/wiki/"
    + urllib.parse.quote(page.replace(" ", "_"), safe="()_")
    for title, page in FANDOM_API_PAGES.items()
    if not title.startswith("fandom_")
}

WAYBACK_CDX_QUERIES = (
    "https://web.archive.org/cdx/search/cdx?url=kerrang.com/*sleep-token*&output=json&from=2023&to=2024&filter=statuscode:200&collapse=urlkey&limit=12",
    "https://web.archive.org/cdx/search/cdx?url=www.kerrang.com/*sleep-token*&output=json&from=2023&to=20241231235959&filter=statuscode:200&collapse=urlkey&limit=12",
)

REDDIT_SONG_QUERIES: dict[str, str] = {
    "Chokehold": 'title:"Chokehold" (lore OR meaning OR creature OR Missing Limbs)',
    "The Summoning": 'title:"The Summoning" (lore OR meaning OR creature OR theory)',
    "Granite": 'title:"Granite" (lore OR meaning OR sulphur OR car OR theory)',
    "Aqua Regia": 'title:"Aqua Regia" (lore OR meaning OR alchemy OR gold OR chemistry)',
    "Vore": 'title:"Vore" (lore OR meaning OR swallow OR throat OR creature)',
    "Ascensionism": 'title:"Ascensionism" (lore OR meaning OR diamonds OR binary OR theory)',
    "Are You Really Okay?": 'title:"Are You Really Okay" (lore OR meaning OR Atlantic OR theory)',
    "The Apparition": 'title:"The Apparition" (lore OR meaning OR sleep paralysis OR dream)',
    "DYWTYLM": 'title:"DYWTYLM" (lore OR meaning OR mirror OR reflection OR Vessel)',
    "Rain": 'title:"Rain" (lore OR meaning OR cleanse OR snakes OR Eden)',
    "Take Me Back to Eden": 'title:"Take Me Back to Eden" (lore OR meaning OR callbacks OR moth)',
    "Euclid": 'title:"Euclid" (lore OR meaning OR head OR symmetry OR callbacks)',
}

_SIGIL_GAP = (
    "I 12 sigilli geometrici appartengono a Sundowning (Capitolo 1). "
    "In Take Me Back to Eden il sistema simbolico è il cifrario runico e le 12 creature."
)
_DEPTH_GAP = (
    "La batimetria marina appartiene a TPWBYT (Capitolo 2). "
    "Dopo la riemersione di Chokehold l'ambientazione è terrestre, lunare e alchemica."
)
_QUOTE_GAP = (
    "Nel 2023 Vessel non ha rilasciato interviste traccia-per-traccia. "
    "Le cover story di Kerrang! e Metal Hammer sul ciclo Eden sono saggi critici, non interviste al personaggio."
)
_UNCLOSED_GAPS = [
    "Le cover story Kerrang! e Metal Hammer del 2023 restano saggi critici: l'assenza di citazioni in-character non è un buco dello scraper.",
    "I 26 glifi dello Sleep Token Alphabet non hanno codepoint Unicode. Il JSON descrive la struttura e la traslitterazione, senza convertire i raster Omniglot in SVG.",
    "I messaggi parlati del Ritual al Wembley (16 dicembre 2023) circolano su video e social, domini bloccati. Restano solo i richiami indiretti su Reddit e sulla wiki.",
    "loreofsleeptoken.com/tmbte/ e /take-me-back-to-eden/ rispondono 404 e non hanno snapshot Wayback. Le letture di quel sito puntano a /the-lore/, che è online.",
]
_SHORT_TITLES = {"rain", "vore"}
_FANDOM_KEEP = ("rune", "character", "creature", "eden", "cipher", "visualiser", "visualizer", "alchemy", "vessel")


def _creature(
    track: str,
    rune: str,
    description: str,
    role: str,
) -> dict[str, str]:
    return {
        "track": track,
        "decoded_rune": rune,
        "entity_description": description,
        "ritual_role": role,
        "reading_class": "community",
        "glyph_status": "traslitterazione inglese; il glifo raster non è archiviato",
    }


TMBTE_CREATURES: dict[int, dict[str, str]] = {
    1: _creature(
        "Chokehold", "CHOKEHOLD",
        "Colosso biomeccanico avvolto da tentacoli o cavi neri che emergono dal fango, con gli arti aggrovigliati al collo.",
        "Riemersione dal fondale di Missing Limbs: l'ossessione resta una presa anche fuori dall'oceano.",
    ),
    2: _creature(
        "The Summoning", "THE SUMMONING",
        "Guerriero corazzato in una caverna rossa, con una grande alabarda o ascia bipenne incisa di rune.",
        "Guardiano dell'evocazione: forza seduttiva e marziale insieme.",
    ),
    3: _creature(
        "Granite", "GRANITE",
        "Golem scolpito nel granito scuro, con fratture da cui filtra luce e una postura inamovibile.",
        "Durezza emotiva e impatto fisico: il petto di pietra su cui si infrange la relazione.",
    ),
    4: _creature(
        "Aqua Regia", "AQUA REGIA",
        "Figura regale e alchemica con un calice o una struttura ramificata al posto del capo, e oro liquido che cola sull'armatura.",
        "Personificazione dell'acqua regia: l'acido che scioglie l'oro, metallo dei re.",
    ),
    5: _creature(
        "Vore", "VORE",
        "Creatura carnosa con fauci spalancate che si aprono nel torso, pronta a inghiottire la preda intera.",
        "Estremo di Jaws e The Offering: essere divorati per restare nelle viscere dell'altro.",
    ),
    6: _creature(
        "Ascensionism", "ASCENSIONISM",
        "Sovrano o angelo oscuro a gambe incrociate, in drappi neri e catene, sospeso sopra un'architettura gotica.",
        "Falso paradiso promesso da Sleep e accusa di aver fatto desiderare la scomparsa.",
    ),
    7: _creature(
        "Are You Really Okay?", "ARE YOU REALLY OKAY",
        "Entità arborea antropomorfa, contorta e sanguinante, con rami spogli piegati in un gesto di dolore.",
        "Cicatrici nella carne: il trauma come corteccia incisa che non si rimargina.",
    ),
    8: _creature(
        "The Apparition", "THE APPARITION",
        "Spettro velato, quasi privo di corpo, con lembi di tessuto sospesi nel vuoto notturno.",
        "Allucinazione al risveglio: la figura che svanisce appena si tenta di toccarla.",
    ),
    9: _creature(
        "DYWTYLM", "DYWTYLM",
        "Idolo dalle molte braccia che si regge il volto o si specchia in simmetria.",
        "Dissociazione allo specchio: incapacità di amare il proprio riflesso.",
    ),
    10: _creature(
        "Rain", "RAIN",
        "Figura sacerdotale avvolta da serpenti o radici sotto una pioggia battente, in posa di purificazione.",
        "Diluvio che lava il sale dell'oceano di TPWBYT.",
    ),
    11: _creature(
        "Take Me Back to Eden", "TAKE ME BACK TO EDEN",
        "Angelo-falena sospeso davanti a una luna piena o eclissata che contiene il sigillo della band.",
        "Unisce l'insetto notturno attratto dalla luce al guardiano del giardino.",
    ),
    12: _creature(
        "Euclid", "EUCLID",
        "Gigante in stracci rituali: spada nella mano destra e, nella sinistra, la testa mozzata di Vessel con la maschera della trilogia.",
        "Decapitazione simbolica del vecchio contenitore, prima di una forma nuova.",
    ),
}

RUNIC_CIPHER_SYSTEM: dict[str, Any] = {
    "reading_class": "community",
    "linguistic_classification": (
        "Cifrario di sostituzione monoalfabetica, 1:1 con le 26 lettere A-Z, catalogato su Omniglot come Sleep Token Alphabet. "
        "Niente punteggiatura e niente cifre."
    ),
    "geometric_derivation": (
        "Ogni glifo scompone il sigillo principale: aste verticali, diagonali, rombi aperti o chiusi, punti staccati. "
        "Omniglot registra la direzione abituale in colonne, dall'alto in basso, con le parole da sinistra a destra; "
        "a volte le stesse rune stanno su righe orizzontali."
    ),
    "structural_features": {
        "vowels_and_diamonds": (
            "Alcune lettere usano rombi o punti staccati dall'asta per distinguere glifi altrimenti simmetrici."
        ),
        "cover_art_inscriptions": (
            "Sulla copertina e sui visualiser le colonne verticali traslitterano il titolo dell'album e i titoli delle tracce."
        ),
        "unicode_gap": "Nessun codepoint Unicode. I raster Omniglot restano fuori dal JSON.",
        "late_letters": (
            "La wiki dell'album annota che J, X e Z non erano pubblici all'uscita e sono comparsi "
            "il 24 novembre 2023. Lettura di community, non una tabella ufficiale."
        ),
    },
    "key_decoded_phrases": [
        {
            "decoded_english": "TAKE ME BACK TO EDEN",
            "location": "Bordi verticali della copertina e visualiser della traccia 11",
            "meaning_in_lore": "Invocazione di ritorno a uno stato di innocenza precedente al patto o al trauma.",
            "reading_class": "community",
        },
        {
            "decoded_english": "THE NIGHT BELONGS TO YOU",
            "location": "Merchandising 2023 e chiusura del ciclo, associata a Euclid nelle letture di community",
            "meaning_in_lore": (
                "Rovescia il titolo di apertura di Sundowning, The Night Does Not Belong to God: "
                "la notte torna all'umano, o viene condivisa in piena coscienza."
            ),
            "reading_class": "community",
        },
        {
            "decoded_english": "I AM HUNTING SOMETHING AND IN TURN THAT SAME THING IS HUNTING ME",
            "location": "Iscrizioni promozionali legate al bestiario, lettura di community",
            "meaning_in_lore": "Chi insegue l'ossessione finisce inseguito da essa.",
            "reading_class": "community",
        },
    ],
}

SINGLES_SEED: list[dict[str, str]] = [
    {"title": "Chokehold", "date": "2023-01-05"},
    {"title": "The Summoning", "date": "2023-01-06"},
    {"title": "Granite", "date": "2023-01-19"},
    {"title": "Aqua Regia", "date": "2023-01-20"},
    {"title": "Vore", "date": "2023-02-16"},
    {"title": "DYWTYLM", "date": "2023-04-20"},
    {"title": "Take Me Back to Eden", "date": "2023-05-19"},
]


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
    creature = TMBTE_CREATURES[number]
    fields["symbols"] = {
        "sigil": fields.pop("sigil", None),
        "depth": fields.pop("depth", None),
        "rune": creature["decoded_rune"],
        "creature": creature["entity_description"],
        "ritual_role": creature["ritual_role"],
        "object": fields.pop("object"),
        "color": fields.pop("color"),
    }
    fields.setdefault("in_character_quotes", [])
    fields.setdefault("gaps", [])
    return fields


SONGS_CATALOG: list[dict[str, Any]] = [
    _song(
        slug="01-chokehold",
        title="Chokehold",
        release="Take Me Back to Eden",
        track_number=1,
        year=2023,
        genius_annotations_count=7,
        keywords=["Chokehold", "blade", "Northern Lights", "accident", "Missing Limbs"],
        era_role=(
            "Apre l'album. Singolo del 5 gennaio 2023. Si salda all'outro di Missing Limbs: "
            "Vessel riemerge dal Challenger Deep (circa 10.923 m nel Capitolo 2) e scopre che la presa al collo resta anche all'aria."
        ),
        sigil="Emblema inscritto nella luna eclissata",
        depth="Riemersione a quota 0, uscita dalle acque di Missing Limbs",
        editorial_reading=[_edit(
            "Louder e Boolin Tunes leggono l'apertura come fatalista: l'incontro con Sleep non è presentato come un caso. Carl Bown co-produce il muro djent e i synth industriali.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        object="Lama mostrata, aurora boreale, presa al collo",
        color="Nero fango, argento, bagliore rosso-lunare",
        references=[_ref(
            "geofisica",
            "Le aurore polari nascono dal vento solare che incontra la magnetosfera: una forza invisibile che governa il cielo notturno.",
            "Il ritorno sotto l'influenza dell'altro è paragonato al girare in tondo sotto l'aurora.",
            "Sleep Token Collective Wiki - Chokehold", _wiki("Chokehold"),
        )],
        callbacks=[_cb(
            "Missing Limbs e High Water (This Place Will Become Your Tomb, 2021)",
            "Il drone iniziale continua l'outro di Missing Limbs. Il soffocamento riprende la chiusura apneica di High Water.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
        )],
        community_theories=[_theory(
            "Con 7 annotazioni Genius, la community nota che l'idea di un incontro non accidentale torna nella title-track e incornicia l'album nel destino.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="02-the-summoning",
        title="The Summoning",
        release="Take Me Back to Eden",
        track_number=2,
        year=2023,
        genius_annotations_count=13,
        keywords=["The Summoning", "river", "sky", "elevate", "funk"],
        era_role=(
            "Seconda traccia, singolo del 6 gennaio 2023. Rituale di evocazione in tre tempi: "
            "furia metallica, lamento celeste, coda funk e R&B. È anche il brano che porta la band al pubblico di massa."
        ),
        editorial_reading=[_edit(
            "La stampa (Kerrang!, Metal Hammer, NME, Revolver) descrive il passaggio dal progressive metalcore allo shoegaze e poi a una coda funk-soul, letta come la voce seduttiva di Sleep.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        object="Alabarda runica, fiume rosso, cielo squarciato",
        color="Rosso cremisi e bronzo antico",
        references=[_ref(
            "esoterismo",
            "Nel lessico teurgico l'evocazione richiama la divinità nel corpo del tramite per oltrepassare il confine tra terra e cielo.",
            "Richiesta di essere sollevato oltre il proprio limite fino a vedere l'altro lato.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Levitate (2019) e Hypnosis (2021)",
            "Inverte Levitate, dove l'ascesa era negata, e occupa lo slot rituale della traccia 2, come The Offering e Hypnosis.",
            "Sleep Token Collective Wiki - The Summoning", _wiki("The Summoning"),
        )],
        community_theories=[_theory(
            "La coda funk dopo il silenzio ambient viene letta come un cambio di narratore: prima l'invocazione di Vessel, poi la risposta sensuale di Sleep.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN,
        )],
    ),
    _song(
        slug="03-granite",
        title="Granite",
        release="Take Me Back to Eden",
        track_number=3,
        year=2023,
        genius_annotations_count=13,
        keywords=["Granite", "sulphur", "passenger", "car crash", "breath"],
        era_role=(
            "Terza traccia, singolo del 19 gennaio 2023. Dopo l'estasi di The Summoning, "
            "due passeggeri in un'auto lanciata verso lo schianto: nessuno ammette la fine, entrambi preferiscono restare vedovi."
        ),
        editorial_reading=[_edit(
            "Louder nota beat R&B e pop-trap che esplodono in un muro di chitarre pesante quanto il titolo, e la freddezza dell'interlocutore.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        object="Zolfo, granito nel petto, vetri infranti",
        color="Grigio granito e giallo zolfo",
        references=[_ref(
            "alchimia / mineralogia",
            "Lo zolfo è uno dei Tria Prima di Paracelso, legato al fuoco e all'anima volatile. Il granito è una roccia ignea intrusiva, metafora di un cuore pietrificato.",
            "Lo zolfo sta sul respiro dell'altro e il granito nel petto di chi parla.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Dark Signs (Sundowning, 2019)",
            "L'immaginario automobilistico notturno di Dark Signs, dove i segnali venivano ignorati, qui è già lo schianto.",
            "Sleep Token Collective Wiki - Granite", _wiki("Granite"),
        )],
        community_theories=[_theory(
            "Una lettura su r/SleepToken collega il ricovero di Atlantic (luci blu, vetri, bende) a un incidente notturno rievocato in Granite. Resta un'ipotesi.",
            "Sleep Token Collective Wiki - Granite", _wiki("Granite"),
        )],
    ),
    _song(
        slug="04-aqua-regia",
        title="Aqua Regia",
        release="Take Me Back to Eden",
        track_number=4,
        year=2023,
        genius_annotations_count=14,
        keywords=["Aqua Regia", "oxytocin", "gold", "silicon", "alchemy", "Eden"],
        era_role=(
            "Quarta traccia, singolo del 20 gennaio 2023. Manifesto alchemico su un arrangiamento jazz-pop al pianoforte, senza chitarre metal: "
            "il mondo artificiale e il conflitto amoroso contro la nostalgia dell'Eden."
        ),
        editorial_reading=[_edit(
            "Kerrang!, Louder e Boolin Tunes sottolineano la scrittura jazzistica e la densità di chimica, informatica e mito che prepara il ritorno all'Eden.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        object="Acqua regia, oro disciolto, silicio, ossitocina",
        color="Oro liquido e arancio nitroso",
        references=[
            _ref(
                "chimica",
                "L'acqua regia è acido nitrico e acido cloridrico in rapporto 1:3. Scioglie oro e platino. Qui è una passione acida abbastanza da corrodere ciò che sembrava incorruttibile.",
                "Il titolo oppone il reagente dei re all'amore inteso come chimica.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
            _ref(
                "biochimica / semiconduttori",
                "L'ossitocina, ormone del legame, è opposta ai circuiti di silicio e ai firewall.",
                "Il legame chimico attraversa l'etere mentre i corpi danzano su un substrato di silicio.",
                "Sleep Token Collective Wiki - Aqua Regia", _wiki("Aqua Regia"),
            ),
        ],
        callbacks=[_cb(
            "Sugar (2019) e Alkaline (2021)",
            "Terzo vertice chimico: dopo lo zucchero organico e la neutralità acido-base, l'equilibrio si rompe nell'acido estremo.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
        )],
        community_theories=[_theory(
            "È il primo brano del disco in cui compare la parola Eden, e apre il filo che culmina nella traccia 11.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="05-vore",
        title="Vore",
        release="Take Me Back to Eden",
        track_number=5,
        year=2023,
        genius_annotations_count=13,
        keywords=["Vore", "throat", "gods", "swallow", "pain"],
        era_role=(
            "Quinta traccia, singolo del 16 febbraio 2023. Dopo il jazz di Aqua Regia, il brano più estremo del disco: "
            "essere inghiottiti nella gola degli dèi perché il dolore cessi nell'assimilazione."
        ),
        editorial_reading=[_edit(
            "Louder e Kerrang! accostano l'apertura urlata a Gods, e notano l'alternanza con un ritornello melodico disperato.",
            "Louder - The story behind every Sleep Token song (Page 3)", LOUDER_P3, "2023-05-19",
        )],
        object="Gola degli dèi, viscere, pareti interne",
        color="Rosso viscerale e nero",
        references=[_ref(
            "mitologia divorante",
            "Vore abbrevia il desiderio di essere divorati interi. Porta oltre il morso di The Offering: sparire nel corpo di Sleep.",
            "La domanda è se esista un punto di non ritorno nella gola degli dèi.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Jaws (2018), The Offering (2019), Gods (2019)",
            "Dalle fauci mostrate al morso offerto, fino alla deglutizione totale, con il lessico degli dèi di Gods.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
        )],
        community_theories=[_theory(
            "Nella lettura alchemica di community, Vore è la Nigredo: putrefazione nella pancia del mostro, sul modello di Giona, prima della purificazione.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="06-ascensionism",
        title="Ascensionism",
        release="Take Me Back to Eden",
        track_number=6,
        year=2023,
        genius_annotations_count=27,
        keywords=["Ascensionism", "diamonds", "code", "rose", "disappear"],
        era_role=(
            "Sesta traccia, circa sette minuti e mezzo, centro dell'album. Attraverso pianoforte, trap, post-rock e djent, "
            "Vessel smaschera il falso paradiso e accusa Sleep di avergli fatto desiderare di sparire."
        ),
        editorial_reading=[_edit(
            "Metal Hammer e Boolin Tunes lo mettono accanto alla title-track come vertice compositivo: il risentimento di tre dischi diventa un atto d'accusa.",
            "Louder - The story behind every Sleep Token song (Page 4)", LOUDER_P4, "2023-05-19",
        )],
        object="Diamanti grezzi, petali, codice digitale, labbra cianotiche",
        color="Nero, rosso rosa, blu elettrico",
        references=[_ref(
            "informatica / mineralogia",
            "L'interlocutore è descritto come un'illusione di luce digitale, algoritmi e ricompense materiali che coprono il vuoto.",
            "La domanda è chi abbia reso l'altro un ibrido di codice e di sogno.",
            "Sleep Token Collective Wiki - Ascensionism", _wiki("Ascensionism"),
        )],
        callbacks=[
            _cb(
                "Levitate (2019) e The Love You Want (2021)",
                "Rovescia Levitate: l'ascensione, prima venerata, qui è manipolazione.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
            _cb(
                "Caramel e Damocles (Even In Arcadia, 2025)",
                "Mercificazione, diamanti e desiderio di sparire anticipano la crisi della fama nel Capitolo 4.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
        ],
        community_theories=[_theory(
            "Con 27 annotazioni Genius, la community legge il climax come la rottura del contratto psicologico: Vessel smette di implorare e riconosce che il legame gli toglie la voglia di vivere.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN,
        )],
    ),
    _song(
        slug="07-are-you-really-okay",
        title="Are You Really Okay?",
        release="Take Me Back to Eden",
        track_number=7,
        year=2023,
        genius_annotations_count=13,
        keywords=["Are You Really Okay", "blood", "bathroom floor", "heal", "Atlantic"],
        era_role=(
            "Settima traccia. Ballata rock quasi priva di cripto-mito: chi parla trova l'altro sul pavimento, nel buio, "
            "dopo un gesto autolesivo, e lo supplica di smettere."
        ),
        editorial_reading=[_edit(
            "La stampa lo indica come il brano più letterale della discografia: salute mentale e impotenza di chi cerca di salvare una persona cara.",
            "Louder - The story behind every Sleep Token song (Page 4)", LOUDER_P4, "2023-05-19",
        )],
        object="Sangue sul pavimento, ferite, luce dell'alba",
        color="Rosso sangue e grigio alba",
        references=[_ref(
            "psicologia clinica",
            "Crisi autolesiva notturna e dolore di chi scopre le ferite.",
            "Supplica di non continuare a ferirsi, e domanda se l'altro stia davvero bene.",
            "Sleep Token Collective Wiki - Are You Really Okay?", _wiki("Are You Really Okay?"),
        )],
        callbacks=[_cb(
            "Atlantic (2021) e The Way That You Were (2018)",
            "Controcampo di Atlantic: là Vessel si sveglia ferito tra il pianto altrui; qui la scena è vista da chi ha trovato il sangue.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        community_theories=[_theory(
            "Tre narratori possibili: Vessel che ricorda di aver cercato di salvare un partner; una voce cara, o una parte sana, che gli parlava la notte di Atlantic; Sleep che teme di perdere il contenitore dopo Ascensionism.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="08-the-apparition",
        title="The Apparition",
        release="Take Me Back to Eden",
        track_number=8,
        year=2023,
        genius_annotations_count=7,
        keywords=["The Apparition", "dreaming", "paralysis", "echo", "wake"],
        era_role=(
            "Ottava traccia, solo 7 annotazioni Genius in archivio. Decostruisce il mito del 2016: "
            "Sleep compare nei sogni come apparizione e sparisce dal letto al risveglio."
        ),
        editorial_reading=[_edit(
            "Louder e Boolin Tunes descrivono synth-pop malinconico e riff pesanti sul confine tra sogno lucido, paralisi del sonno e lutto amoroso.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        object="Letto vuoto al risveglio, eco nella stanza, altare onirico",
        color="Blu notte e grigio nebbia",
        references=[_ref(
            "neurologia del sonno",
            "Allucinazione ipnopompica: visioni nella transizione dal sonno REM al risveglio, in cui la figura sembra nella stanza e poi si dissolve.",
            "La domanda è perché l'entità non sia mai reale e compaia solo mentre il narratore sogna.",
            "Sleep Token Collective Wiki - The Apparition", _wiki("The Apparition"),
        )],
        callbacks=[_cb(
            "Calcutta, Jericho (Two EP, 2017) e Is It Really You? (2022)",
            "Rovescia il patto dell'EP Two, accettato con devozione fino al risveglio: qui quella condizione è diventata una tortura.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        community_theories=[_theory(
            "Chiamare Sleep un'apparizione che non è mai reale segna il passaggio dalla fede cieca allo scetticismo: la divinità può essere una proiezione del trauma.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="09-dywtylm",
        title="DYWTYLM",
        release="Take Me Back to Eden",
        track_number=9,
        year=2023,
        genius_annotations_count=18,
        keywords=["DYWTYLM", "Do You Wish That You Loved Me", "mirror", "reflection", "smile"],
        era_role=(
            "Nona traccia, sesto singolo, 20 aprile 2023. L'acronimo scioglie Do You Wish That You Loved Me. "
            "Beat pop malinconico: l'interlocutore non è un partner né Sleep, ma il riflesso nello specchio."
        ),
        editorial_reading=[_edit(
            "La critica nota il contrasto tra una produzione pop-synth orecchiabile e uno dei testi più tristi del disco, rivolto al riflesso stesso.",
            "Louder - The story behind every Sleep Token song (Page 4)", LOUDER_P4, "2023-05-19",
        )],
        object="Specchio e riflesso che non sorride",
        color="Rosa pallido e argento specchiato",
        references=[_ref(
            "psicologia dell'identità",
            "Dopo anni di maschera al servizio di Sleep, l'uomo sotto il costume guarda lo specchio e si percepisce come un estraneo.",
            "Il sorriso cercato è quello del proprio riflesso.",
            "Sleep Token Collective Wiki - DYWTYLM", _wiki("DYWTYLM"),
        )],
        callbacks=[
            _cb(
                "Fall for Me (2021) e High Water (2021)",
                "Sviluppa la confessione a schermo di Fall for Me, l'incapacità di amarsi, e il mancato perdono di sé in High Water.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
            _cb(
                "Past Self e Damocles (Even In Arcadia, 2025)",
                "La frattura tra la persona allo specchio e la maschera apre le riflessioni di Past Self.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
        ],
        community_theories=[_theory(
            "La community la considera la svolta terapeutica: quando la domanda sull'amore è rivolta a sé, il ricatto di Sleep inizia a sciogliersi.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN,
        )],
    ),
    _song(
        slug="10-rain",
        title="Rain",
        release="Take Me Back to Eden",
        track_number=10,
        year=2023,
        genius_annotations_count=17,
        keywords=["Rain", "cleanse", "snakes", "eden", "chemically"],
        era_role=(
            "Decima traccia. Dopo lo specchio di DYWTYLM, l'acqua non è più l'oceano salato di TPWBYT: "
            "è pioggia che lava il veleno e restituisce la sensazione di essere vivi."
        ),
        editorial_reading=[_edit(
            "Louder descrive Rain come il momento più euforico del disco: synth luminosi e groove metal per una rinascita emotiva.",
            "Louder - The story behind every Sleep Token song (Page 4)", LOUDER_P4, "2023-05-19",
        )],
        object="Pioggia, serpenti nel giardino, spire",
        color="Verde smeraldo, argento pluviale, oro",
        references=[_ref(
            "alchimia / Genesi",
            "Dopo la Nigredo, l'Albedo chiede l'Ablutio: lavare la materia con acqua pura. Il testo unisce quel lavaggio ai serpenti del giardino.",
            "La pioggia è invocata come purificazione mentre i serpenti si avvolgono.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
        callbacks=[_cb(
            "Atlantic e High Water (2021)",
            "L'acqua che annegava diventa pioggia battesimale che lava il sale dalle ferite.",
            "Sleep Token Collective Wiki - Rain", _wiki("Rain"),
        )],
        community_theories=[_theory(
            "Due letture: un amore nuovo, o l'accettazione di sé, che guarisce dal trauma; oppure l'ultima tentazione dell'Eden, segnata dai serpenti, prima della traccia 11.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="11-take-me-back-to-eden",
        title="Take Me Back to Eden",
        release="Take Me Back to Eden",
        track_number=11,
        year=2023,
        genius_annotations_count=32,
        keywords=["Take Me Back to Eden", "Chokehold", "The Offering", "moth", "spit blood"],
        era_role=(
            "Title-track, circa otto minuti e venti secondi, 32 annotazioni Genius. "
            "Vessel ripercorre il viaggio dall'innocenza del giardino alla corruzione del patto, richiama Chokehold e The Offering, "
            "e arriva allo scontro più violento della trilogia."
        ),
        sigil="Sigillo completo incastonato nella luna",
        editorial_reading=[_edit(
            "Metal Hammer, Kerrang! e Boolin Tunes la trattano come l'opera magna: una suite in più movimenti che riassume la grammatica della band e lo scontro finale con Sleep.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "2023-05-15",
        )],
        object="Giardino, falena lunare alata, fuoco sacro, lama",
        color="Bianco lunare, oro alchemico, nero",
        references=[
            _ref(
                "Genesi 2-3",
                "L'Eden è lo stato di integrità prima di Sleep o prima del trauma. Il ritorno è negato: non si rientra nell'innocenza, si attraversa il dolore. L'Arcadia del 2025 sta oltre quella porta chiusa.",
                "Il ritornello implora di essere riportato nel giardino.",
                "Lore of Sleep Token", LORE_MAIN,
            ),
            _ref(
                "entomologia simbolica",
                "La falena lunare adulta vive pochi giorni e non si nutre: esiste per volare verso la luna e riprodursi. È la devozione autodistruttiva di Vessel.",
                "L'artwork ufficiale usa la falena alata e l'attrazione verso la fiamma.",
                "Sleep Token Collective Wiki - Take Me Back to Eden (song)", _wiki("Take Me Back to Eden"),
            ),
        ],
        callbacks=[
            _cb(
                "Chokehold (traccia 1, 2023)",
                "Nell'ultimo terzo torna l'incipit di Chokehold, l'incontro non accidentale, e chiude la parentesi aperta dal disco.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
            _cb(
                "The Offering (2019) e Fields of Elation (2016)",
                "Il sangue al risveglio e il sacrificio richiamano The Offering; i campi richiamano Fields of Elation. I versi non sono archiviati.",
                "Sleep Token Collective Wiki - Take Me Back to Eden (song)", _wiki("Take Me Back to Eden"),
            ),
        ],
        community_theories=[_theory(
            "Il breakdown finale è letto come lo scontro con il guardiano del giardino. Le porte restano chiuse, e la trasformazione prepara la decapitazione di Euclid.",
            "Lore of Sleep Token", LORE_MAIN,
        )],
    ),
    _song(
        slug="12-euclid",
        title="Euclid",
        release="Take Me Back to Eden",
        track_number=12,
        year=2023,
        genius_annotations_count=29,
        keywords=["Euclid", "The Night Does Not Belong to God", "When the Bough Breaks", "Blood Sport", "symmetry", "head"],
        era_role=(
            "Chiude l'album e la trilogia 2019-2023. Vessel accetta di dover essere qualcun altro, "
            "saluta il passato senza odio e riprende, in musica e in parole, The Night Does Not Belong to God: la notte ora appartiene a loro."
        ),
        sigil="Iscrizione runica THE NIGHT BELONGS TO YOU",
        editorial_reading=[_edit(
            "La critica la indica tra le chiusure di concept più nette del rock recente: gli accordi di pianoforte del 2019 trasformano tre album di tragedia in un addio luminoso.",
            "Louder - The story behind every Sleep Token song (Page 4)", LOUDER_P4, "2023-05-19",
        )],
        object="Testa mozzata con la vecchia maschera, rette parallele, rami autunnali",
        color="Bianco dorato dell'alba e rosso autunnale",
        references=[_ref(
            "geometria euclidea",
            "Euclide di Alessandria: nel quinto postulato due rette parallele restano simmetriche e non si incontrano. Vale per due amanti affiancati, e per la simmetria tra la traccia 1 di Sundowning e la traccia 12 di questo album.",
            "Il titolo e i versi sulla simmetria inversa descrivono una linea parallela su cui dare la vita.",
            "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
        )],
        callbacks=[
            _cb(
                "The Night Does Not Belong to God (Sundowning, traccia 1, 2019)",
                "La coda ripete il giro di pianoforte, i synth e il materiale della traccia 1 di Sundowning, compresi i bianchi degli occhi che diventano neri e il nome dimenticato. Il cerchio della trilogia si chiude.",
                "Boolin Tunes - The Lore of Sleep Token", BOOLIN, "editorial",
            ),
            _cb(
                "When the Bough Breaks (One EP, traccia 3, 2016)",
                "Torna l'immagine dell'attesa finché il ramo non si spezza, fino al primo EP.",
                "Sleep Token Collective Wiki - Euclid", _wiki("Euclid"),
            ),
            _cb(
                "Blood Sport (Sundowning, traccia 12, 2019) e Granite",
                "Il cielo che non accoglie e la stanza sottostante richiamano Blood Sport; le lamiere richiamano Granite.",
                "Sleep Token Collective Wiki - Euclid", _wiki("Euclid"),
            ),
        ],
        community_theories=[_theory(
            "La creatura che regge la testa con la maschera classica è letta come la morte del vecchio Vessel. Nei rituali successivi, da Wembley il 16 dicembre 2023 in poi, le maschere cambiano e preparano Even In Arcadia. I filmati restano fuori dall'archivio.",
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


def fetch_url(url: str, gaps_log: list[str], timeout: int = 25) -> str | None:
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
        with urllib.request.urlopen(req, timeout=timeout) as resp:
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
    base = title.lower().rstrip("?").strip()
    if not re.search(rf"\b{re.escape(base)}\b", window):
        return False
    if base in _SHORT_TITLES:
        return any(token in window for token in ("sleep", "vessel", "track", "song", "eden", "rune", "creature", "album"))
    return True


def latest_wayback(original_url: str, gaps_log: list[str]) -> str | None:
    query = (
        "https://web.archive.org/cdx/search/cdx?url="
        + urllib.parse.quote(original_url, safe="")
        + "&output=json&filter=statuscode:200&limit=20"
    )
    raw = fetch_url(query, gaps_log, timeout=45)
    if not raw:
        return None
    try:
        rows = json.loads(raw)
    except json.JSONDecodeError:
        gaps_log.append(f"Invalid JSON from Wayback CDX for {original_url}")
        return None
    last = next((row for row in reversed(rows[1:]) if len(row) >= 3 and str(row[1]).isdigit()), None)
    if not last:
        gaps_log.append(f"Nessuno snapshot Wayback per {original_url}")
        return None
    return f"https://web.archive.org/web/{last[1]}/{last[2]}"


def resolve_kerrang_snapshots(gaps_log: list[str]) -> list[dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    for query in WAYBACK_CDX_QUERIES:
        raw = fetch_url(query, gaps_log, timeout=45)
        time.sleep(REQUEST_DELAY_SEC)
        if not raw:
            continue
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError:
            gaps_log.append("Invalid JSON from Wayback CDX for Kerrang 2023.")
            continue
        for row in rows[1:]:
            if len(row) < 3 or not str(row[1]).isdigit():
                continue
            timestamp, original = row[1], row[2]
            blob = original.lower()
            if "sleep" not in blob and "eden" not in blob:
                continue
            found[original] = {
                "timestamp": timestamp,
                "original_url": original,
                "wayback_url": f"https://web.archive.org/web/{timestamp}/{original}",
                "source_class": "editorial",
            }
    if not found:
        gaps_log.append("Wayback CDX vuota per le query Kerrang 2023-2024 su sleep-token.")
    return list(found.values())


def fetch_reddit_threads(query: str, gaps_log: list[str]) -> list[dict[str, Any]]:
    encoded = urllib.parse.quote(query)
    raw = None
    for host in ("https://www.reddit.com", "https://old.reddit.com"):
        url = f"{host}/r/SleepToken/search.json?q={encoded}&restrict_sr=1&sort=top&t=all&limit=6"
        raw = fetch_url(url, gaps_log)
        if raw:
            break
        time.sleep(REQUEST_DELAY_SEC)
    if not raw:
        return []
    if not raw.lstrip().startswith(("{", "[")):
        gaps_log.append("Reddit ha restituito una pagina non JSON (blocco non aggirato).")
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
    reasons = {"sigil": _SIGIL_GAP, "depth": _DEPTH_GAP}
    for key, value in list(filled.items()):
        if value is None:
            filled[f"{key}_gap_reason"] = reasons.get(key, "Nessun elemento aggiuntivo canonizzato per questa voce.")
    return filled


def _load_closed_source(src: dict[str, str], gaps: list[str], fandom_cache: dict[str, str | None]) -> str | None:
    if src["id"] == "fandom_tmbte":
        page = FANDOM_API_PAGES[src["id"]]
        html = fetch_fandom_page(page, gaps)
        fandom_cache[page] = html
        return html
    if src["id"] == "fandom_runes":
        html = None
        used = ""
        for page in RUNE_PAGE_CANDIDATES:
            cached = fandom_cache.get(page)
            html = cached if cached else fetch_fandom_page(page, gaps)
            fandom_cache[page] = html
            if html:
                used = page
                src["url"] = (
                    "https://sleep-token-collective.fandom.com/wiki/"
                    + urllib.parse.quote(page.replace(" ", "_"), safe="()_")
                )
                break
            time.sleep(REQUEST_DELAY_SEC)
        if used == "Take Me Back To Eden (album)":
            gaps.append("Pagine Fandom Runes e Alphabet assenti: note runiche prese dalla pagina album.")
        return html
    html = fetch_url(src["url"], gaps)
    if src["id"] == "omniglot_alphabet" and not html:
        snapshot = latest_wayback("www.omniglot.com/conscripts/sleeptokenalphabet.htm", gaps)
        if snapshot:
            gaps.append(f"Omniglot live rifiutato: snapshot {snapshot}")
            html = fetch_url(snapshot, gaps, timeout=45)
            if html:
                src["url"] = snapshot
    if src["id"] == "lore_tmbte" and not html:
        gaps.append(f"Fallback lore URL: {LORE_TMBTE_FALLBACK}")
        html = fetch_url(LORE_TMBTE_FALLBACK, gaps)
        if html:
            src["url"] = LORE_TMBTE_FALLBACK
        else:
            for archived in ("loreofsleeptoken.com/tmbte/", "loreofsleeptoken.com/take-me-back-to-eden/"):
                snapshot = latest_wayback(archived, gaps)
                if not snapshot:
                    continue
                html = fetch_url(snapshot, gaps, timeout=45)
                if html:
                    src["url"] = snapshot
                    gaps.append(f"Sottopagina lore recuperata da Wayback: {snapshot}")
                    break
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
            if any(token in lower for token in ("eden", "euclid", "vessel", "sleep token", "chokehold", "summoning")):
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
                    key=lambda paragraph: 0 if any(
                        token in paragraph.lower() for token in ("character", "creature", "rune", "visual")
                    ) else 1,
                )
                for paragraph in ordered:
                    if kept >= 3:
                        break
                    lower = paragraph.lower()
                    if paragraph_matches(paragraph, title, keywords) or any(token in lower for token in _FANDOM_KEEP):
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

    omniglot_notes = [
        paraphrase_extract(paragraph)
        for paragraph in corpus.get("omniglot_alphabet", {}).get("paragraphs", [])[:5]
    ]
    rune_notes = [
        paraphrase_extract(paragraph)
        for paragraph in corpus.get("fandom_runes", {}).get("paragraphs", [])
        if any(token in paragraph.lower() for token in ("rune", "alphabet", "cipher", "glyph", "transliter"))
    ][:8]
    wiki_paragraphs = corpus.get("wiki_tmbte", {}).get("paragraphs", [])
    chronology_hits = [
        paraphrase_extract(paragraph)
        for paragraph in wiki_paragraphs
        if any(token in paragraph.lower() for token in ("spinefarm", "bown", "lever", "may", "2023", "kerrang", "hammer"))
    ][:6]
    producer = "Carl Bown" if any("bown" in item.lower() for item in chronology_hits) else None
    chapter = {
        "chapter_number": 3,
        "slug": "03-take-me-back-to-eden",
        "title": "Capitolo 3 — Take Me Back to Eden (2023), il cifrario runico, le 12 creature e la chiusura della trilogia",
        "why_before_chapter_4": (
            "Dopo il fondale di Missing Limbs, Chokehold riporta Vessel a terra sotto la luna. "
            "Il cifrario, le 12 creature e la catarsi di Euclid vanno letti prima del ciclo 2025: "
            "solo così si distingue la trilogia chiusa dall'Arcadia."
        ),
        "trilogy_culmination": {
            "elemental_progression": (
                "Aria, notte e tramonto in Sundowning (2019); acqua, abisso e pressione in TPWBYT (2021); "
                "terra, fuoco alchemico ed Eden in TMBTE (2023)."
            ),
            "vessel_arc_resolution": (
                "Dalla riemersione ancora prigioniera in Chokehold e The Summoning, alla disillusione di Granite, "
                "Aqua Regia e Ascensionism, allo scetticismo di The Apparition, allo specchio di DYWTYLM, "
                "fino al rifiuto del ritorno all'innocenza e alla morte simbolica del vecchio sé in Euclid."
            ),
            "alchemy_community_reading": {
                "stages": ["Nigredo", "Albedo", "Citrinitas", "Rubedo"],
                "assigned": {
                    "Vore": "Nigredo, putrefazione nella pancia del mostro",
                    "Rain": "Albedo / Ablutio, lavaggio con la pioggia",
                },
                "reading_class": "community",
                "note": "Citrinitas e Rubedo non hanno un'assegnazione traccia-per-traccia canonizzata in questo catalogo.",
            },
        },
        "public_chronology": {
            "label": "Spinefarm Records",
            "release_date": "2023-05-19",
            "singles_seed": SINGLES_SEED,
            "producer": producer,
            "producer_gap_reason": None if producer else "I paragrafi Wikipedia estratti non nominano Carl Bown.",
            "previous_cycle_producer": "George Lever",
            "source_class": "editorial",
            "source_url": WIKI,
            "live_extracts": chronology_hits,
            "awards_note": "Heavy Music Awards, Metal Hammer e Kerrang! vanno letti solo se compaiono nei live_extracts.",
        },
        "runic_cipher_documentation": {
            "system": RUNIC_CIPHER_SYSTEM,
            "omniglot_live_notes": omniglot_notes,
            "fandom_rune_notes": rune_notes,
            "bestiary_credit": {
                "designer": "Alex Tillbrook",
                "role": "Concept art delle 12 entità, attribuzione di community sotto la direzione creativa della band.",
                "reading_class": "community",
            },
        },
        "the_12_entities_bestiary": {str(number): row for number, row in TMBTE_CREATURES.items()},
        "wayback_kerrang_2023_snapshots": kerrang_snapshots,
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
