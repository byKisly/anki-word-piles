"""Word Piles 0.1.0 — desktop Anki add-on."""
from aqt import mw
from aqt.qt import QAction, QKeySequence

from .ui import WordPilesDialog

_dialog = None


def open_piles():
    global _dialog
    if mw is None or mw.col is None:
        return
    if _dialog is None:
        _dialog = WordPilesDialog(mw, __name__)
    _dialog.show()
    _dialog.raise_()
    _dialog.activateWindow()
    _dialog.reload()


if mw is not None:
    action = QAction("Стопки слов…", mw)
    action.setShortcut(QKeySequence("Ctrl+Shift+J"))
    action.triggered.connect(open_piles)
    mw.form.menuTools.addAction(action)
    # Keep the action alive, and close the window before switching profiles.
    from aqt import gui_hooks

    def close_piles():
        global _dialog
        if _dialog is not None:
            _dialog.close()
            _dialog.deleteLater()
            _dialog = None

    gui_hooks.profile_will_close.append(close_piles)

    def update_piles(*_):
        if _dialog is not None and _dialog.isVisible():
            _dialog.reload()

    gui_hooks.operation_did_execute.append(update_piles)
