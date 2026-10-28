"""Catalogo del Capitolo 3: cifrario runico, 12 creature, nessun testo cantato."""

from __future__ import annotations

import json

import collect_chapter_03 as chapter


def test_twelve_tracks_and_creatures() -> None:
    assert len(chapter.SONGS_CATALOG) == 12
    assert len(chapter.TMBTE_CREATURES) == 12
    titles = [song["title"] for song in chapter.SONGS_CATALOG]
    assert titles[0] == "Chokehold"
    assert titles[-1] == "Euclid"
    assert [song["genius_annotations_count"] for song in chapter.SONGS_CATALOG] == [
        7, 13, 13, 14, 13, 27, 13, 7, 18, 17, 32, 29,
    ]
    for number, row in chapter.TMBTE_CREATURES.items():
        assert row["reading_class"] == "community"
        assert row["track"] == chapter.SONGS_CATALOG[number - 1]["title"]
        assert chapter.SONGS_CATALOG[number - 1]["symbols"]["rune"] == row["decoded_rune"]
    assert "testa mozzata" in chapter.TMBTE_CREATURES[12]["entity_description"]
    assert chapter.FANDOM_API_PAGES["Take Me Back to Eden"] == "Take Me Back To Eden (song)"
    assert chapter.FANDOM_API_PAGES["fandom_tmbte"] == "Take Me Back To Eden (album)"
    assert "%3F" in chapter.FANDOM_SONG_URLS["Are You Really Okay?"]


def test_cipher_depth_and_quote_gap() -> None:
    phrases = [item["decoded_english"] for item in chapter.RUNIC_CIPHER_SYSTEM["key_decoded_phrases"]]
    assert phrases == [
        "TAKE ME BACK TO EDEN",
        "THE NIGHT BELONGS TO YOU",
        "I AM HUNTING SOMETHING AND IN TURN THAT SAME THING IS HUNTING ME",
    ]
    assert "Unicode" in chapter.RUNIC_CIPHER_SYSTEM["structural_features"]["unicode_gap"]
    chokehold = chapter.SONGS_CATALOG[0]
    assert chokehold["symbols"]["depth"].startswith("Riemersione")
    assert chapter.SONGS_CATALOG[1]["symbols"]["depth"] is None
    assert "2023" in chapter._QUOTE_GAP
    assert "interviste" in chapter._QUOTE_GAP
    euclid = chapter.SONGS_CATALOG[-1]
    targets = " ".join(item["target_song"] for item in euclid["callbacks"])
    assert "The Night Does Not Belong to God" in targets
    assert "When the Bough Breaks" in targets


def test_blocked_domains_and_no_lyrics() -> None:
    assert "genius.com" in chapter.BLOCKED_DOMAINS
    assert "youtube.com" in chapter.BLOCKED_DOMAINS
    blob = json.dumps(chapter.SONGS_CATALOG, ensure_ascii=False)
    assert "[verse" not in blob.lower()
    assert "[chorus" not in blob.lower()
    assert "wish i could disappear" not in blob.lower()
    assert not chapter.IDENTITY_REGEX.search(blob)
    assert chapter.is_forbidden_content("His real name is printed here")
    assert chapter.paraphrase_extract('He said "a long quoted line of verse here" calmly.') == (
        "He said [riferimento testuale] calmly."
    )
    assert chapter.paragraph_matches("Rain falls on the garden in this Sleep Token song.", "Rain", [])
    assert not chapter.paragraph_matches("The rain in Spain stays mainly in the plain.", "Rain", [])
