"""Read existing collection data using Anki's collection API. Never write it."""
from __future__ import annotations

import time
import re
from dataclasses import dataclass

from anki.utils import strip_html_media

from .core import analyze, study_day


WORD_NAMES = ("word", "expression", "term", "vocabulary", "english", "английский", "слово", "front")
MEANING_NAMES = ("translation", "meaning", "russian", "перевод", "русский", "back", "definition")


def guess_fields(names: list[str]) -> tuple[int, int]:
    lowered = [n.casefold().strip() for n in names]
    def find(candidates, fallback):
        return next((lowered.index(c) for c in candidates if c in lowered), fallback)
    word = find(WORD_NAMES, 0)
    meaning = find(MEANING_NAMES, 1 if len(names) > 1 else -1)
    if meaning == word:
        meaning = next((i for i in range(len(names)) if i != word), -1)
    return word, meaning


def clean(text: str) -> str:
    text = re.sub(r"\[sound:[^\]]*\]", "", text, flags=re.IGNORECASE)
    return " ".join(strip_html_media(text).split())


@dataclass
class Snapshot:
    histories: dict
    notes: dict
    days: list[str]
    today: str
    rollover: int
    models: list[dict]
    decks: list[tuple[int, str]]
    skipped: int


def read_snapshot(col, config: dict) -> Snapshot:
    now_ms = int(time.time() * 1000)
    rollover = col.get_preferences().scheduling.rollover
    today = study_day(now_ms, rollover)
    events = col.db.all(
        "select r.id, r.cid, c.nid, r.ease, r.type from revlog r "
        "join cards c on c.id=r.cid where r.ease between 1 and 4 "
        "and r.type between 0 and 3 and r.id<=? order by r.id", now_ms)
    histories = analyze(events, rollover, int(config.get("threshold", 10)), now_ms)
    models = list(col.models.all())
    model_map = {m["id"]: m for m in models}
    mappings = config.get("fields", {})
    decks = [(int(d.id), d.name) for d in col.decks.all_names_and_ids()]
    card_meta = {}
    note_decks: dict[int, set[int]] = {}
    for cid, nid, did, odid, ordinal in col.db.all("select id,nid,did,odid,ord from cards"):
        card_meta[cid] = ordinal
        note_decks.setdefault(nid, set()).add(odid or did)
    notes = {}
    skipped = 0
    for nid, mid, flds in col.db.all("select id,mid,flds from notes"):
        if nid not in histories:
            continue
        model = model_map.get(mid)
        if model is None:
            skipped += 1
            continue
        names = [f["name"] for f in model["flds"]]
        word_idx, meaning_idx = guess_fields(names)
        mapping = mappings.get(model["name"], {})
        if mapping.get("word") in names:
            word_idx = names.index(mapping["word"])
        if mapping.get("meaning") in names:
            meaning_idx = names.index(mapping["meaning"])
        if mapping.get("meaning") == "":
            meaning_idx = -1
        fields = flds.split("\x1f")
        word = clean(fields[word_idx]) if word_idx < len(fields) else ""
        meaning = clean(fields[meaning_idx]) if 0 <= meaning_idx < len(fields) else ""
        if not word:
            skipped += 1
            continue
        templates = {t["ord"]: t["name"] for t in model["tmpls"]}
        directions = {cid: templates.get(card_meta.get(cid), "Карточка")
                      for stats in histories[nid].days.values() for cid in stats.directions}
        notes[nid] = dict(word=word, meaning=meaning, decks=note_decks.get(nid, set()),
                          directions=directions)
    days = sorted({today} | {d for h in histories.values() for d in h.days}, reverse=True)
    return Snapshot(histories, notes, days, today, rollover, models, decks, skipped)


def make_rows(snapshot: Snapshot, day: str, difficult: bool, deck_id: int = 0) -> list[dict]:
    deck_names = dict(snapshot.decks)
    scope = deck_names.get(deck_id, "")
    rows = []
    for nid, history in snapshot.histories.items():
        note = snapshot.notes.get(nid)
        if note is None or (difficult and not history.active):
            continue
        if not difficult and day not in history.days:
            continue
        if deck_id and not any(d == deck_id or deck_names.get(d, "").startswith(scope + "::")
                               for d in note["decks"]):
            continue
        stats_day = history.last_day if difficult else day
        stats = history.days[stats_day]
        parts = []
        for cid, ratings in sorted(stats.directions.items()):
            name = note["directions"].get(cid, "Карточка")
            parts.append(f"{name}: 1={ratings[0]}, 2={ratings[1]}, 3={ratings[2]}, 4={ratings[3]}")
        directions = "; ".join(parts)
        detail = f"День: {stats_day}; {directions}"
        if difficult:
            detail += f"; в трудных с {history.entered}"
        rows.append(dict(nid=nid, word=note["word"], meaning=note["meaning"],
                         ratings=stats.ratings, directions=directions, detail=detail,
                         day=stats_day, entered=history.entered))
    return sorted(rows, key=lambda r: (-r["ratings"][0], r["word"].casefold(), r["nid"]))
