# Word Piles for Anki

Two automatically collected vocabulary lists: **words reviewed during an Anki study day** and **words that keep causing trouble**. Copy either list, translations, or a practice prompt into your preferred AI assistant.

[Русская инструкция](README.ru.md)

## Install

Download `Word_Piles_0.1.0.ankiaddon` from `dist/` (or a release when available).
In desktop Anki, select **Tools → Add-ons → Install from file**, choose the file, then restart Anki.

Open **Tools → Стопки слов…**, or **Cmd+Shift+J** on macOS / **Ctrl+Shift+J** on Windows and Linux.
The interface is currently in Russian. This is a desktop add-on; it does not run on AnkiMobile or AnkiDroid.

## How it works

- **Words for the day:** all notes with an actual graded answer during the selected study day, including learning and relearning.
- **Difficult now:** a note enters after **10 Again answers in a single study day**, summed across its card directions. The threshold is configurable.
- A difficult note leaves on a later study day when it receives at least one passing answer and **no Again answers that day**. If an Again occurs later that day, it returns.
- An unreviewed note retains its previous status. Passing answers on the entry day do not clear it.
- Hard counts as a passing answer. Only Again counts as a failure.
- Sibling cards from one note are combined. Separate notes are not merged by identical text.

Lists are reconstructed from Anki's review log, so previous reviews work immediately and undo is respected after refreshing. This is a practice queue, not a claim of permanent mastery.
Study days use the current Anki rollover hour and the computer's local time zone. Changing those settings or the threshold recalculates the historical lists.

## Copy and practice

Choose a tab, optionally select rows, then use **Копировать слова** (words), **С переводами** (with translations), or **Для нейронки** (AI practice prompt).
Without a selection, all visible rows are copied. Search and deck filters apply.
Cmd/Ctrl+C copies translations; Cmd/Ctrl+Shift+C copies the practice prompt. Double-click a row to open its source in Anki.

Configure word and translation fields in **Настройки**. Common fields such as Word/Translation and Front/Back are detected automatically.

## Privacy and compatibility

All processing is local. No API keys or network requests are used. Copying writes to the clipboard; pasting into another service is your choice.
The add-on does not change notes, cards, tags, scheduling, or review history. It saves only its configuration.
No collection data is included in this repository or the installation package.

**Early version 0.1.0.** Tested on macOS with Anki **25.09.4**, its bundled Python 3.13 and Qt 6. Live installation and opening both lists were verified; logic and Qt clipboard/table checks were run on a collection copy. Windows/Linux and prolonged everyday use have not yet been verified.

## Development

No third-party dependencies are required for the pure rule tests:

```sh
python3 -m unittest discover -s tests -v
python3 build.py
```

The integration check needs Anki's Python environment and PyQt6. Close Anki first; the script copies the provided collection to a temporary directory and operates only on that copy:

```sh
QT_QPA_PLATFORM=offscreen /path/to/anki/python tests/integration_check.py --collection /path/to/collection.anki2
```

Code was created with OpenAI Codex assistance. Issues and reproducible examples are welcome. Do not attach your full collection or private vocabulary data to a public issue.

Licensed under MIT.
