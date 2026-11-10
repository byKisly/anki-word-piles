"""Pure, read-only analysis of Anki review events. No Anki/Qt imports."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Iterable


def study_day(timestamp_ms: int, rollover: int) -> str:
    # Subtract from local wall time, not the epoch: this also handles DST days.
    local = datetime.fromtimestamp(timestamp_ms / 1000)
    return (local - timedelta(hours=rollover)).date().isoformat()


@dataclass
class DayStats:
    ratings: list[int] = field(default_factory=lambda: [0, 0, 0, 0])
    directions: dict[int, list[int]] = field(default_factory=dict)
    last_id: int = 0

    @property
    def again(self) -> int:
        return self.ratings[0]

    def add(self, cid: int, rating: int, event_id: int) -> None:
        self.ratings[rating - 1] += 1
        self.directions.setdefault(cid, [0, 0, 0, 0])[rating - 1] += 1
        self.last_id = max(self.last_id, event_id)


@dataclass
class WordHistory:
    days: dict[str, DayStats] = field(default_factory=dict)
    active: bool = False
    entered: str | None = None
    last_day: str = ""


def analyze(events: Iterable[tuple[int, int, int, int, int]], rollover: int,
            threshold: int = 10, now_ms: int | None = None) -> dict[int, WordHistory]:
    """Events: (revlog id/ms, card id, note id, ease 1..4, review type).

    Types 0..3 are actual answers; manual/reschedule entries aren't answers.
    Rebuilding from the surviving journal naturally handles undo and sync.
    """
    if threshold < 1:
        raise ValueError("threshold must be positive")
    histories: dict[int, WordHistory] = {}
    for event_id, cid, nid, rating, kind in events:
        if rating not in (1, 2, 3, 4) or kind not in (0, 1, 2, 3):
            continue
        if now_ms is not None and event_id > now_ms:
            continue
        day = study_day(event_id, rollover)
        history = histories.setdefault(nid, WordHistory())
        history.days.setdefault(day, DayStats()).add(cid, rating, event_id)
    for history in histories.values():
        for day, stats in sorted(history.days.items()):
            history.last_day = day
            if history.active:
                # A day with at least one answer and zero Again clears it.
                # Same-day successes never erase that day's failures.
                if stats.again == 0:
                    history.active = False
                    history.entered = None
            elif stats.again >= threshold:
                history.active = True
                history.entered = day
    return histories


def export_text(rows: list[dict], mode: str, day: str = "", difficult: bool = False) -> str:
    lines = []
    for row in rows:
        word = " ".join(row["word"].split())
        meaning = " ".join(row["meaning"].split())
        if mode == "words":
            lines.append(word)
        else:
            line = word + (" — " + meaning if meaning else "")
            if mode == "ai":
                line += " | " + row["detail"]
            lines.append(line)
    if mode != "ai":
        return "\n".join(lines)
    scope = "Мои текущие трудные слова" if difficult else f"Слова, которые я повторял за учебный день {day}"
    return (
        scope + ".\n"
        "Помоги закрепить эти английские слова. Значения из карточек приведены ниже. "
        "Если перевод неоднозначен, уточни нужный смысл. Давай задания по одному: "
        "перевод в обе стороны и короткие предложения с пропусками. "
        "Не показывай ответ до моей попытки. Проверяй смысл и написание, объясняй ошибки "
        "кратко и возвращай ошибочные слова позже. Учитывай слабое направление, "
        "если оно видно из статистики. Не считай слово усвоенным после одной удачной попытки.\n"
        "Оценки Anki: 1 = забыл, 2 = вспомнил с трудом, 3/4 = успешный ответ.\n\n"
        + "\n".join(lines)
    )
