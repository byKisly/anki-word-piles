"""Run with Anki's Python: integration_check.py --collection /path/collection.anki2

Close Anki first. All operations use a temporary copy, never the original.
Set QT_QPA_PLATFORM=offscreen for an invisible Qt smoke test.
"""
import argparse
import pathlib
import shutil
import sqlite3
import sys
import tempfile
import types


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--collection', type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = pathlib.Path(__file__).resolve().parents[1]
    source = root if (root / 'core.py').exists() else root / 'word_piles'
    pkg = types.ModuleType('word_piles_check')
    pkg.__path__ = [str(source)]
    sys.modules[pkg.__name__] = pkg
    from anki.collection import Collection
    from anki.lang import set_lang
    from aqt.qt import QApplication
    from word_piles_check.service import read_snapshot, make_rows
    from word_piles_check import ui
    set_lang('en')
    app = QApplication([])

    class Manager:
        def getConfig(self, package):
            return {'threshold': 10, 'fields': {}}

    with tempfile.TemporaryDirectory(prefix='word-piles-check-') as directory:
        path = pathlib.Path(directory) / 'collection.anki2'
        # Copy bytes, including WAL if present, before opening any SQLite handle.
        shutil.copyfile(args.collection, path)
        wal = pathlib.Path(str(args.collection) + '-wal')
        if wal.exists():
            shutil.copyfile(wal, str(path) + '-wal')
        col = Collection(str(path))
        try:
            before = col.db.all('select id,cid,ease,type from revlog order by id')
            snap = read_snapshot(col, {'threshold': 10})
            ui.mw = types.SimpleNamespace(addonManager=Manager(), col=col)
            ui.tooltip = lambda *a, **kw: None
            dialog = ui.WordPilesDialog(None, pkg.__name__)
            dialog.loaded(snap)
            rows = make_rows(snap, snap.today, False)
            assert dialog.tables[0].rowCount() == len(rows)
            assert dialog.tables[1].rowCount() == len(make_rows(snap, snap.today, True))
            if rows:
                dialog.tables[0].selectRow(0)
                assert len(dialog.selected_rows()) == 1
                dialog.copy_rows('ai')
                assert rows[0]['word'] in app.clipboard().text()
                dialog.search.setText(rows[0]['word'])
                assert dialog.tables[0].rowCount() > 0
            settings = ui.SettingsDialog(dialog, snap.models, {'threshold': 10})
            assert settings.result_config()['threshold'] == 10
            dialog.show()
            app.processEvents()
            dialog.close()
            assert col.db.all('select id,cid,ease,type from revlog order by id') == before
            print('PASS: collection read, two tables, clipboard, search, settings, unchanged review log')
        finally:
            col.close()


if __name__ == '__main__':
    main()
