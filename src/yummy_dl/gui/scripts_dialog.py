"""Scripts → Manage scripts…: create and edit saved ffmpeg commands."""

from __future__ import annotations

import copy
import dataclasses

from PySide6.QtCore import Qt
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .. import hls
from .. import scripts as scriptmod
from ..i18n import _
from ..scripts import Script

def placeholder_help() -> str:
    return _(
    "Write the ffmpeg arguments; <code>ffmpeg</code> itself is optional. Placeholders:<br>"
    "<code>{input}</code> the episode file &nbsp; <code>{name}</code> its name without extension &nbsp; "
    "<code>{ext}</code> its extension &nbsp; <code>{episode}</code> episode number (01) &nbsp; "
    "<code>{outdir}</code> where to write the result<br>"
    "Placeholders need no quotes, but quote a path where <i>you</i> type a space: "
    "<code>\"{outdir}/{episode} {name}.mkv\"</code><br>"
    "Keep <code>{name}</code> in output names (optionally after <code>{episode}</code>) so the app still "
    "sees the episode as downloaded.<br>"
    "<b>After a successful run the original file is deleted</b>; if ffmpeg fails it is kept."
    )


class ScriptsDialog(QDialog):
    """Edits a copy of the scripts; `on_saved(scripts)` is called after Save."""

    def __init__(self, parent, scripts: list[Script], on_saved) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("Scripts"))
        self.resize(900, 560)
        self.scripts = [copy.copy(s) for s in scripts]
        self._on_saved = on_saved
        self._dirty = False
        self._loading = False

        # left: list
        self.list = QListWidget()
        self.list.currentRowChanged.connect(self._load_current)
        new_btn = QPushButton(_("New"))
        new_btn.clicked.connect(lambda: self._add(Script(name=self._unique(_("New script")),
                                                          command="-i {input} -c copy {outdir}/{name}.mkv")))
        examples = QToolButton(text=_("From example ▾"))
        examples.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(examples)
        for ex in scriptmod.EXAMPLES:
            act = menu.addAction(_(ex.name))
            act.setToolTip(_(ex.comment))
            act.triggered.connect(lambda _c=False, ex=ex: self._add(
                dataclasses.replace(ex, name=self._unique(_(ex.name)), comment=_(ex.comment))))
        examples.setMenu(menu)
        self.dup_btn = QPushButton(_("Duplicate"))
        self.dup_btn.clicked.connect(self._duplicate)
        self.del_btn = QPushButton(_("Delete"))
        self.del_btn.clicked.connect(self._delete)
        lbtns = QHBoxLayout()
        for b in (new_btn, examples, self.dup_btn, self.del_btn):
            lbtns.addWidget(b)
        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.list, 1)
        ll.addLayout(lbtns)

        # right: editor
        self.name_edit = QLineEdit()
        self.comment_edit = QLineEdit(placeholderText=_("Optional: what it's for"))
        self.command_edit = QPlainTextEdit()
        self.command_edit.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.command_edit.setPlaceholderText("-i {input} -c:v libx264 -c:a libmp3lame {outdir}/{name}.mkv")
        self.own_folder_cb = QCheckBox(_("Save the results in a folder named after the video "
                                         "(useful when cutting into parts)"))
        self.auto_cb = QCheckBox(_("Run automatically after each download (only one script can)"))
        self.problems = QLabel()
        self.problems.setWordWrap(True)
        self.problems.setStyleSheet("color: #d9534f")
        help_lbl = QLabel(placeholder_help())
        help_lbl.setWordWrap(True)
        help_lbl.setTextFormat(Qt.RichText)
        if not hls.find_ffmpeg():
            help_lbl.setText(help_lbl.text() + "<br><b style='color:#d9534f'>"
                             + _("ffmpeg was not found, so scripts can't run yet. On Windows: winget install ffmpeg.")
                             + "</b>")

        form = QFormLayout()
        form.addRow(_("Name:"), self.name_edit)
        form.addRow(_("Comment:"), self.comment_edit)
        self.editor = QWidget()
        el = QVBoxLayout(self.editor)
        el.setContentsMargins(0, 0, 0, 0)
        el.addLayout(form)
        el.addWidget(QLabel(_("ffmpeg command:")))
        el.addWidget(self.command_edit, 1)
        el.addWidget(self.problems)
        el.addWidget(self.own_folder_cb)
        el.addWidget(self.auto_cb)
        el.addWidget(help_lbl)

        for w in (self.name_edit, self.comment_edit):
            w.textChanged.connect(self._store)
        self.command_edit.textChanged.connect(self._store)
        self.own_folder_cb.toggled.connect(self._store)
        self.auto_cb.toggled.connect(self._store)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(left)
        split.addWidget(self.editor)
        split.setSizes([280, 620])

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Close)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(split, 1)
        lay.addWidget(buttons)

        for s in self.scripts:
            self.list.addItem(s.name)
        self.list.setCurrentRow(0 if self.scripts else -1)
        self._load_current(self.list.currentRow())

    # --- list -----------------------------------------------------------------------

    def _unique(self, base: str) -> str:
        names = {s.name for s in self.scripts}
        name, n = base, 2
        while name in names:
            name, n = f"{base} ({n})", n + 1
        return name

    def _add(self, script: Script) -> None:
        script.auto = False
        self.scripts.append(script)
        self.list.addItem(script.name)
        self.list.setCurrentRow(len(self.scripts) - 1)
        self._dirty = True
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _duplicate(self) -> None:
        cur = self._current()
        if cur:
            self._add(dataclasses.replace(cur, name=self._unique(cur.name)))

    def _delete(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        if QMessageBox.question(self, _("Scripts"), _("Delete '{name}'?", name=self.scripts[row].name)) != QMessageBox.Yes:
            return
        del self.scripts[row]
        self.list.takeItem(row)
        self._dirty = True
        self._load_current(self.list.currentRow())

    def _current(self) -> Script | None:
        row = self.list.currentRow()
        return self.scripts[row] if 0 <= row < len(self.scripts) else None

    # --- editor ---------------------------------------------------------------------

    def _load_current(self, _row: int = -1) -> None:
        s = self._current()
        self.editor.setEnabled(s is not None)
        self.dup_btn.setEnabled(s is not None)
        self.del_btn.setEnabled(s is not None)
        self._loading = True
        self.name_edit.setText(s.name if s else "")
        self.comment_edit.setText(s.comment if s else "")
        self.command_edit.setPlainText(s.command if s else "")
        self.own_folder_cb.setChecked(bool(s and s.own_folder))
        self.auto_cb.setChecked(bool(s and s.auto))
        self._loading = False
        self._show_problems()

    def _store(self, *_args) -> None:
        if self._loading:
            return
        s = self._current()
        if not s:
            return
        s.name = self.name_edit.text()
        s.comment = self.comment_edit.text()
        s.command = self.command_edit.toPlainText()
        s.own_folder = self.own_folder_cb.isChecked()
        if self.auto_cb.isChecked() and not s.auto:
            for other in self.scripts:  # only one auto script: a second would find its input deleted
                other.auto = False
        s.auto = self.auto_cb.isChecked()
        self.list.currentItem().setText(s.name or _("(no name)"))
        self._dirty = True
        self._show_problems()

    def _show_problems(self) -> None:
        s = self._current()
        problems = scriptmod.validate(s) if s else []
        self.problems.setText(" ".join(problems))
        self.problems.setVisible(bool(problems))

    # --- save / close ---------------------------------------------------------------

    def _save(self) -> None:
        names = [s.name.strip() for s in self.scripts]
        for i, s in enumerate(self.scripts):
            problems = scriptmod.validate(s)
            if not problems and names.count(s.name.strip()) > 1:
                problems = [_("Another script is also named '{name}'.", name=s.name)]
            if problems:
                self.list.setCurrentRow(i)
                QMessageBox.warning(self, _("Scripts"), f"'{s.name or _('(no name)')}': " + " ".join(problems))
                return
        for s in self.scripts:
            s.name = s.name.strip()
        try:
            scriptmod.save_scripts(self.scripts)
        except OSError as e:
            QMessageBox.warning(self, _("Scripts"), _("Couldn't save: {error}", error=e))
            return
        self._dirty = False
        self._on_saved(self.scripts)
        self.accept()

    def reject(self) -> None:
        if self._dirty:
            ans = QMessageBox.question(self, _("Scripts"), _("Discard your unsaved changes?"))
            if ans != QMessageBox.Yes:
                return
        super().reject()
