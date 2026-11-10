from __future__ import annotations

import copy

from aqt import mw
from aqt.operations import QueryOp
from aqt.qt import (
    QAbstractItemView, QApplication, QComboBox, QDialog, QDialogButtonBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QScrollArea, QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget,
    QVBoxLayout, QWidget, Qt, QShortcut, QKeySequence, QTimer,
)
from aqt.utils import showWarning, tooltip

from .core import export_text
from .service import guess_fields, make_rows, read_snapshot


class SettingsDialog(QDialog):
    def __init__(self, parent, models, config):
        super().__init__(parent)
        self.setWindowTitle("Настройки стопок")
        self.resize(630, 480)
        self.config = copy.deepcopy(config)
        root = QVBoxLayout(self)
        info = QLabel("Настройки меняют только анализ списка. История ответов и интервалы Anki сохраняются.")
        info.setWordWrap(True)
        root.addWidget(info)
        form = QFormLayout()
        self.threshold = QSpinBox()
        self.threshold.setRange(1, 1000)
        self.threshold.setValue(int(config.get("threshold", 10)))
        form.addRow("Ответов «Снова» за день для входа:", self.threshold)
        root.addLayout(form)
        label = QLabel("Поля карточек: выбери, где слово и где перевод. Обратные карточки одной записи объединяются.")
        label.setWordWrap(True)
        root.addWidget(label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        fields_form = QFormLayout(container)
        self.mappings = []
        for model in sorted(models, key=lambda m: m["name"]):
            names = [f["name"] for f in model["flds"]]
            if not names:
                continue
            word_idx, meaning_idx = guess_fields(names)
            configured = config.get("fields", {}).get(model["name"], {})
            word = QComboBox()
            word.addItems(names)
            word.setCurrentText(configured.get("word", names[word_idx]))
            meaning = QComboBox()
            meaning.addItem("Без перевода", "")
            for name in names:
                meaning.addItem(name, name)
            meaning_name = configured.get("meaning", names[meaning_idx] if meaning_idx >= 0 else "")
            index = meaning.findData(meaning_name)
            meaning.setCurrentIndex(max(0, index))
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.addWidget(word)
            layout.addWidget(QLabel("→"))
            layout.addWidget(meaning)
            fields_form.addRow(model["name"], row)
            self.mappings.append((model["name"], word, meaning))
        scroll.setWidget(container)
        root.addWidget(scroll)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def result_config(self):
        self.config["threshold"] = self.threshold.value()
        self.config["fields"] = {name: {"word": word.currentText(), "meaning": meaning.currentData()}
                                 for name, word, meaning in self.mappings}
        return self.config


class WordPilesDialog(QDialog):
    def __init__(self, parent, package):
        super().__init__(parent)
        self.package = package
        self.snapshot = None
        self.busy = False
        self.rows = [[], []]
        self.tables = []
        self.setWindowTitle("Стопки слов · 0.1")
        self.resize(1050, 650)
        root = QVBoxLayout(self)
        title = QLabel("<h2>Стопки слов</h2>")
        root.addWidget(title)
        self.explanation = QLabel("Загружаю историю ответов…")
        self.explanation.setWordWrap(True)
        root.addWidget(self.explanation)
        filters = QHBoxLayout()
        filters.addWidget(QLabel("День:"))
        self.day = QComboBox()
        self.day.setMinimumWidth(165)
        self.day.currentIndexChanged.connect(self.render)
        filters.addWidget(self.day)
        filters.addWidget(QLabel("Колода:"))
        self.deck = QComboBox()
        self.deck.setMinimumWidth(220)
        self.deck.currentIndexChanged.connect(self.render)
        filters.addWidget(self.deck, 1)
        self.refresh = QPushButton("Обновить")
        self.refresh.clicked.connect(self.reload)
        filters.addWidget(self.refresh)
        self.settings_button = QPushButton("Настройки")
        self.settings_button.clicked.connect(self.settings)
        filters.addWidget(self.settings_button)
        root.addLayout(filters)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Поиск по слову или переводу…")
        self.search.textChanged.connect(self.render)
        root.addWidget(self.search)
        self.tabs = QTabWidget()
        root.addWidget(self.tabs, 1)
        for name in ("Слова за день", "Трудные сейчас"):
            page = QWidget()
            layout = QVBoxLayout(page)
            table = QTableWidget(0, 6)
            table.setHorizontalHeaderLabels(["Слово", "Перевод", "Снова", "Трудно", "Хорошо / Легко", "Направления"])
            table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
            table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
            table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
            table.setAlternatingRowColors(True)
            table.setWordWrap(False)
            table.verticalHeader().setVisible(False)
            header = table.horizontalHeader()
            for i in range(6):
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            table.setColumnWidth(0, 155)
            table.setColumnWidth(1, 230)
            for i in (2, 3):
                table.setColumnWidth(i, 65)
            table.setColumnWidth(4, 120)
            header.setStretchLastSection(True)
            table.doubleClicked.connect(self.open_source)
            layout.addWidget(table)
            self.tables.append(table)
            self.tabs.addTab(page, name)
        self.tabs.currentChanged.connect(self.update_status)
        self.status = QLabel()
        self.status.setWordWrap(True)
        root.addWidget(self.status)
        actions = QHBoxLayout()
        for label, mode in (("Копировать слова", "words"), ("С переводами", "meaning"), ("Для нейронки", "ai")):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, m=mode: self.copy_rows(m))
            actions.addWidget(button)
        actions.addStretch()
        source = QPushButton("Открыть в Anki")
        source.clicked.connect(self.open_source)
        actions.addWidget(source)
        close = QPushButton("Закрыть")
        close.clicked.connect(self.close)
        actions.addWidget(close)
        root.addLayout(actions)
        hint = QLabel("Копируются выделенные строки; если ничего не выделено — весь показанный список. "
                      "⌘/Ctrl+C — с переводами · ⌘/Ctrl+Shift+C — для нейронки · двойной щелчок — карточки в Anki")
        hint.setWordWrap(True)
        root.addWidget(hint)
        self.shortcuts = []
        for key, mode in (("Ctrl+C", "meaning"), ("Ctrl+Shift+C", "ai")):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(lambda m=mode: self.copy_rows(m))
            self.shortcuts.append(shortcut)
        self.day_timer = QTimer(self)
        self.day_timer.setInterval(60_000)
        self.day_timer.timeout.connect(self.check_day)
        self.day_timer.start()

    def check_day(self):
        if self.isVisible() and self.snapshot is not None:
            import time
            from .core import study_day
            if study_day(int(time.time() * 1000), self.snapshot.rollover) != self.snapshot.today:
                self.reload()

    def get_config(self):
        return mw.addonManager.getConfig(self.package) or {"threshold": 10, "fields": {}}

    def reload(self):
        if self.busy or mw.col is None:
            return
        self.busy = True
        self.refresh.setEnabled(False)
        self.settings_button.setEnabled(False)
        config = copy.deepcopy(self.get_config())
        QueryOp(parent=self, op=lambda col: read_snapshot(col, config), success=self.loaded).failure(self.failed).run_in_background()

    def failed(self, error):
        self.busy = False
        self.refresh.setEnabled(True)
        self.settings_button.setEnabled(True)
        showWarning("Не удалось прочитать историю ответов:\n" + str(error), parent=self)

    def loaded(self, snapshot):
        self.busy = False
        self.refresh.setEnabled(True)
        self.settings_button.setEnabled(True)
        old_day = self.day.currentData()
        if self.snapshot is not None and old_day == self.snapshot.today:
            old_day = snapshot.today
        self.snapshot = snapshot
        old_deck = self.deck.currentData()
        self.day.blockSignals(True)
        self.deck.blockSignals(True)
        self.day.clear()
        for day in snapshot.days:
            self.day.addItem(day + (" · сегодня" if day == snapshot.today else ""), day)
        idx = self.day.findData(old_day)
        self.day.setCurrentIndex(max(0, idx))
        self.deck.clear()
        self.deck.addItem("Все колоды", 0)
        for did, name in sorted(snapshot.decks, key=lambda d: d[1]):
            self.deck.addItem(name, did)
        self.deck.setCurrentIndex(max(0, self.deck.findData(old_deck)))
        self.day.blockSignals(False)
        self.deck.blockSignals(False)
        threshold = self.get_config().get("threshold", 10)
        self.explanation.setText(
            f"Учебный день начинается в {snapshot.rollover:02}:00. "
            f"Вход в трудные: {threshold} ответов «Снова» за один день. "
            "Выход: следующий день со словом, без единого «Снова». "
            "Оба направления одной записи считаются вместе.")
        self.render()

    def render(self, *_):
        if self.snapshot is None:
            return
        day = self.day.currentData() or self.snapshot.today
        deck_id = self.deck.currentData() or 0
        needle = self.search.text().strip().casefold()
        for index, table in enumerate(self.tables):
            rows = make_rows(self.snapshot, day, bool(index), deck_id)
            if needle:
                rows = [r for r in rows if needle in (r["word"] + " " + r["meaning"]).casefold()]
            self.rows[index] = rows
            table.setRowCount(0)
            table.setRowCount(len(rows))
            for row_idx, row in enumerate(rows):
                again, hard, good, easy = row["ratings"]
                values = (row["word"], row["meaning"], str(again), str(hard), f"{good} / {easy}", row["directions"])
                for col_idx, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(row["detail"])
                    if col_idx in (2, 3, 4):
                        item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    table.setItem(row_idx, col_idx, item)
            self.tabs.setTabText(index, ("Слова за день" if index == 0 else "Трудные сейчас") + f" · {len(rows)}")
        self.update_status()

    def update_status(self, *_):
        index = self.tabs.currentIndex()
        text = ("Все оценённые сегодня слова: новые и повторяемые." if index == 0 else
                "Текущий список за всю историю. Счётчики — за последний день, когда слово встречалось. "
                "Выбор даты меняет только вкладку «Слова за день».")
        if self.snapshot and self.day.currentData() != self.snapshot.today and index == 0:
            text = "Все оценённые слова за выбранный учебный день: новые и повторяемые."
        if not self.rows[index] and self.snapshot:
            text += (" Порог пока не достигнут ни одним словом в выбранной колоде." if index else
                     " За этот день слов нет или они скрыты фильтрами.")
        if self.snapshot and self.snapshot.skipped:
            text += f" Пропущено записей без текста слова: {self.snapshot.skipped}. Проверь поля в настройках."
        self.status.setText(text)

    def selected_rows(self):
        index = self.tabs.currentIndex()
        selected = sorted({i.row() for i in self.tables[index].selectionModel().selectedRows()})
        return [self.rows[index][i] for i in selected] if selected else self.rows[index]

    def copy_rows(self, mode):
        if self.busy:
            tooltip("Дождись загрузки истории", parent=self)
            return
        rows = self.selected_rows()
        if not rows:
            tooltip("Список пуст", parent=self)
            return
        text = export_text(rows, mode, self.day.currentData() or "", self.tabs.currentIndex() == 1)
        QApplication.clipboard().setText(text)
        tooltip(f"Скопировано слов: {len(rows)}", parent=self)

    def open_source(self, *_):
        index = self.tabs.currentIndex()
        selected = sorted({i.row() for i in self.tables[index].selectionModel().selectedRows()})
        if not selected:
            tooltip("Выдели слово в таблице", parent=self)
            return
        nids = [str(self.rows[index][i]["nid"]) for i in selected]
        from aqt import dialogs
        browser = dialogs.open("Browser", mw)
        browser.form.searchEdit.lineEdit().setText("nid:" + ",".join(nids))
        browser.onSearchActivated()

    def settings(self):
        if self.snapshot is None or self.busy:
            return
        dialog = SettingsDialog(self, self.snapshot.models, self.get_config())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            mw.addonManager.writeConfig(self.package, dialog.result_config())
            self.reload()
