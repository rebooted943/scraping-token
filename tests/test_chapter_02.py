"""Catalogo del Capitolo 2: batimetria, filtri, nessun testo cantato."""

from __future__ import annotations

import json

import collect_chapter_02 as chapter


def test_twelve_tracks_descend() -> None:
    assert len(chapter.SONGS_CATALOG) == 12
    assert len(chapter.TPWBYT_BATHYMETRY) == 12
    fathoms = [chapter.TPWBYT_BATHYMETRY[n]["fathoms"] for n in range(1, 13)]
    assert fathoms == sorted(fathoms)
    assert fathoms[0] == 500
    assert fathoms[-1] == 5973
    for row in chapter.TPWBYT_BATHYMETRY.values():
        assert row["reading_class"] == "community"
        assert row["fathoms_status"].startswith("unverified")
        assert abs(row["meters"] - round(row["fathoms"] * chapter.FATHOM_METERS)) == 0
    assert chapter.TPWBYT_BATHYMETRY[2]["booklet_specimen"].startswith("Brittle star")
    assert chapter.TPWBYT_BATHYMETRY[7]["booklet_specimen"].startswith("Anglerfish")
    assert chapter.FANDOM_API_PAGES["Fall for Me"] == "Fall For Me"


def test_alkaline_repair_does_not_store_lyrics() -> None:
    alkaline = next(song for song in chapter.SONGS_CATALOG if song["title"] == "Alkaline")
    note = alkaline["local_archive_repair_note"]
    assert "22 caratteri" in note
    blob = json.dumps(chapter.SONGS_CATALOG, ensure_ascii=False)
    assert "[verse" not in blob.lower()
    assert "[chorus" not in blob.lower()
    assert not chapter.IDENTITY_REGEX.search(blob)


def test_blocked_domains_and_quote_gap() -> None:
    assert "genius.com" in chapter.BLOCKED_DOMAINS
    assert "youtube.com" in chapter.BLOCKED_DOMAINS
    fall = next(song for song in chapter.SONGS_CATALOG if song["title"] == "Fall for Me")
    assert fall["in_character_quotes"][0]["source_class"] == "canon"
    assert "Parafrasi" in fall["in_character_quotes"][0]["quote"]
    assert chapter.is_forbidden_content("His real name is printed here")
    assert chapter.paraphrase_extract('He said "a long quoted line of verse here" calmly.') == (
        "He said [riferimento testuale] calmly."
    )
