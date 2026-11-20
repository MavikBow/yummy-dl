"""Main window: search → pick title → dub/player/quality → episodes → download queue."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QIcon, QKeySequence, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import config as cfgmod
from .. import core, hls, i18n
from .. import scripts as scriptmod
from ..api import YummyClient
from ..extractors import EXTRACTORS, find_extractor
from ..i18n import _, ngettext
from ..models import Anime, Video
from . import help as helpdlg
from . import theme
from .viewer import ClickableLabel, ImageViewer
from .scripts_dialog import ScriptsDialog
from .workers import (
    ACTIVE,
    CANCELLED,
    DONE,
    FAILED,
    FINISHED,
    QUEUED,
    SKIPPED,
    DownloadManager,
    Job,
    ScriptJob,
    ScriptManager,
    run_bg,
)

QUALITIES = [1080, 720, 480, 360]
POSTER_W, POSTER_H = 160, 224


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("yummy-dl")
        self.resize(1100, 760)
        self.cfg = cfgmod.load()
        self.api = YummyClient(token=self.cfg.effective_token)
        self.anime: Anime | None = None
        self.dubs: list[core.DubOption] = []
        self.jobs: dict[int, Job] = {}
        self._req = 0  # guards against stale background responses
        self._images: dict[str, bytes] = {}  # poster URL -> bytes
        self._poster_anime: Anime | None = None  # whose poster is currently shown

        self.manager = DownloadManager()
        self.manager.progress.connect(self._on_progress)
        self.manager.status.connect(self._on_status)
        self.script_mgr = ScriptManager()
        self.script_mgr.progress.connect(self._on_progress)
        self.script_mgr.status.connect(self._on_status)
        self._scripts_error = ""
        try:
            self.scripts = scriptmod.load_scripts()
        except scriptmod.ScriptError as e:
            self.scripts, self._scripts_error = [], str(e)
        self._confirm_delete = True  # ask before a manual run deletes originals

        self._build_menu()
        self._build_ui()
        self._refresh_ffmpeg_status()
        # Warm up TLS/HTTP after the first paint so the first search is quick.
        QTimer.singleShot(200, lambda: run_bg(self.api.warm, lambda _r: None, lambda _e: None))

    # --- layout -------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu(_("&Settings"))
        act = QAction(_("API &token…"), self)
        act.triggered.connect(self._set_token)
        menu.addAction(act)
        self.dark_act = QAction(_("&Dark theme"), self, checkable=True)
        self.dark_act.setChecked(theme.resolve(self.cfg.theme))
        self.dark_act.toggled.connect(self._toggle_dark)
        menu.addAction(self.dark_act)
        lang_menu = menu.addMenu(_("&Language"))
        group = QActionGroup(self)
        system = i18n.LANGUAGES[i18n.system_language()]
        for code, label in [("", _("System default ({lang})", lang=system)), *i18n.LANGUAGES.items()]:
            act = QAction(label, self, checkable=True)
            act.setChecked(self.cfg.language == code)
            act.triggered.connect(lambda _c=False, code=code: self._set_language(code))
            group.addAction(act)
            lang_menu.addAction(act)
        menu.addSeparator()
        act = QAction(_("Open &config folder"), self)
        act.triggered.connect(lambda: self._open(cfgmod.config_path().parent))
        menu.addAction(act)

        self.scripts_menu = self.menuBar().addMenu(_("S&cripts"))
        self._rebuild_scripts_menu()

        help_menu = self.menuBar().addMenu(_("&Help"))
        for text, tab, key in (
            (_("&Quick start"), helpdlg.TAB_START, QKeySequence.HelpContents),
            (_("Set up API &token…"), helpdlg.TAB_TOKEN, None),
            (_("&Command-line usage"), helpdlg.TAB_CLI, None),
            (_("&About yummy-dl"), helpdlg.TAB_ABOUT, None),
        ):
            act = QAction(text, self)
            if key is not None:
                act.setShortcut(key)
            act.triggered.connect(lambda _c=False, t=tab: self._show_help(t))
            help_menu.addAction(act)

    def _build_ui(self) -> None:
        # search bar
        self.search_edit = QLineEdit(placeholderText=_("Search anime, e.g. берсерк or Re:Zero"))
        self.search_edit.returnPressed.connect(self._search)
        search_btn = QPushButton(_("Search"))
        search_btn.clicked.connect(self._search)
        top = QHBoxLayout()
        top.addWidget(self.search_edit, 1)
        top.addWidget(search_btn)

        # results
        self.results = QListWidget()
        self.results.setIconSize(QSize(33, 47))
        self.results.currentItemChanged.connect(self._on_result_selected)

        # details
        self.title_lbl = QLabel(_("Search for a title to begin."))
        self.title_lbl.setWordWrap(True)
        f = self.title_lbl.font()
        f.setPointSize(f.pointSize() + 3)
        f.setBold(True)
        self.title_lbl.setFont(f)
        self.sub_lbl = QLabel("")
        self.sub_lbl.setWordWrap(True)
        self.sub_lbl.setForegroundRole(QPalette.PlaceholderText)
        self.poster = ClickableLabel()
        self.poster.setFixedSize(POSTER_W, POSTER_H)
        self.poster.setCursor(Qt.PointingHandCursor)
        self.poster.setToolTip(_("Click to view full screen"))
        self.poster.clicked.connect(self._open_poster)
        self.poster.setAlignment(Qt.AlignCenter)
        self._show_logo()

        self.dub_combo = QComboBox()
        self.dub_combo.currentIndexChanged.connect(self._on_dub_changed)
        self.player_combo = QComboBox()
        self.player_combo.currentIndexChanged.connect(self._fill_episodes)
        self.quality_combo = QComboBox()
        for q in QUALITIES:
            self.quality_combo.addItem(f"{q}p", q)
        idx = self.quality_combo.findData(self.cfg.quality)
        self.quality_combo.setCurrentIndex(idx if idx >= 0 else 1)
        self.quality_combo.currentIndexChanged.connect(self._save_prefs)

        self.out_edit = QLineEdit(str(self.cfg.effective_output_dir))
        self.out_edit.editingFinished.connect(self._save_prefs)
        browse = QPushButton(_("Browse…"))
        browse.clicked.connect(self._browse)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(browse)

        form = QFormLayout()
        form.addRow(_("Dub:"), self.dub_combo)
        form.addRow(_("Player:"), self.player_combo)
        form.addRow(_("Max quality:"), self.quality_combo)
        form.addRow(_("Save to:"), out_row)

        self.episodes = QListWidget()
        self.episodes.itemChanged.connect(self._update_selection_label)
        all_btn = QPushButton(_("All"))
        all_btn.clicked.connect(lambda: self._check_all(True))
        none_btn = QPushButton(_("None"))
        none_btn.clicked.connect(lambda: self._check_all(False))
        self.sel_lbl = QLabel("")
        self.add_btn = QPushButton(_("Download selected"))
        self.add_btn.setDefault(True)
        self.add_btn.clicked.connect(self._enqueue)
        ep_btns = QHBoxLayout()
        ep_btns.addWidget(all_btn)
        ep_btns.addWidget(none_btn)
        ep_btns.addWidget(self.sel_lbl, 1)
        ep_btns.addWidget(self.add_btn)

        details = QWidget()
        dl = QVBoxLayout(details)
        info = QVBoxLayout()
        info.addWidget(self.title_lbl)
        info.addWidget(self.sub_lbl)
        info.addLayout(form)
        info.addStretch(1)
        header = QHBoxLayout()
        header.addWidget(self.poster, 0, Qt.AlignTop)
        header.addLayout(info, 1)
        dl.addLayout(header)
        dl.addWidget(QLabel(_("Episodes:")))
        dl.addWidget(self.episodes, 1)
        dl.addLayout(ep_btns)

        upper = QSplitter(Qt.Horizontal)
        upper.addWidget(self.results)
        upper.addWidget(details)
        upper.setSizes([380, 720])

        # queue
        self.queue = QTableWidget(0, 5)
        self.queue.setHorizontalHeaderLabels([_("Title"), _("Episode"), _("Dub"), _("Progress"), _("Status")])
        self.queue.verticalHeader().hide()
        self.queue.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue.doubleClicked.connect(self._open_job)
        self.queue.setContextMenuPolicy(Qt.CustomContextMenu)
        self.queue.customContextMenuRequested.connect(self._queue_menu)
        h = self.queue.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        h.resizeSection(3, 200)
        h.setSectionResizeMode(4, QHeaderView.Stretch)

        cancel_btn = QPushButton(_("Cancel selected"))
        cancel_btn.clicked.connect(self._cancel_selected)
        clear_btn = QPushButton(_("Clear finished"))
        clear_btn.clicked.connect(self._clear_finished)
        open_btn = QPushButton(_("Open folder"))
        open_btn.clicked.connect(lambda: self._open(Path(self.out_edit.text())))
        qbtns = QHBoxLayout()
        qbtns.addWidget(QLabel(_("Queue (double-click to open, right-click to run a script):")), 1)
        qbtns.addWidget(cancel_btn)
        qbtns.addWidget(clear_btn)
        qbtns.addWidget(open_btn)
        lower = QWidget()
        ll = QVBoxLayout(lower)
        ll.setContentsMargins(0, 0, 0, 0)
        ll.addLayout(qbtns)
        ll.addWidget(self.queue)

        main = QSplitter(Qt.Vertical)
        main.addWidget(upper)
        main.addWidget(lower)
        main.setSizes([480, 280])

        root = QWidget()
        rl = QVBoxLayout(root)
        rl.addLayout(top)
        rl.addWidget(main, 1)
        self.setCentralWidget(root)
        self._set_details_enabled(False)

        self.addAction(QAction(self, shortcut=QKeySequence("Ctrl+F"), triggered=self.search_edit.setFocus))

    # --- helpers ------------------------------------------------------------

    def _set_details_enabled(self, on: bool) -> None:
        for w in (self.dub_combo, self.player_combo, self.episodes, self.add_btn):
            w.setEnabled(on)

    def _status(self, text: str, ms: int = 0) -> None:
        self.statusBar().showMessage(text, ms)

    def _error(self, text: str) -> None:
        self._status("")
        QMessageBox.warning(self, "yummy-dl", text)

    def _open(self, path: Path) -> None:
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def _refresh_ffmpeg_status(self) -> None:
        if not hls.find_ffmpeg():
            self.statusBar().addPermanentWidget(QLabel(_("ffmpeg not found: Kodik saves as .ts, Aksor won't work")))

    def _out_dir(self) -> Path:
        return Path(self.out_edit.text().strip() or self.cfg.effective_output_dir).expanduser()

    def _save_prefs(self) -> None:
        self.cfg.quality = self.quality_combo.currentData()
        self.cfg.output_dir = str(self._out_dir())
        cfgmod.save(self.cfg)

    # --- theme & images -----------------------------------------------------

    def _toggle_dark(self, dark: bool) -> None:
        theme.apply(QApplication.instance(), dark)
        self.cfg.theme = "dark" if dark else "light"
        cfgmod.save(self.cfg)

    @staticmethod
    def _pixmap(data: bytes) -> QPixmap:
        pm = QPixmap()
        pm.loadFromData(data)
        return pm

    def _load_image(self, url: str, on_loaded, on_failed=None) -> None:
        """Fetch an image in the background (cached). Failures are ignored unless `on_failed` is given."""
        if url in self._images:
            on_loaded(self._images[url])
            return

        def done(data: bytes) -> None:
            self._images[url] = data
            on_loaded(data)

        run_bg(lambda: self.api.get_image(url), done, on_failed or (lambda _err: None))

    def _show_logo(self) -> None:
        """App logo in the poster slot: before a title is picked, or when a title has no poster."""
        from . import asset

        self._poster_anime = None  # not clickable
        pm = QPixmap(asset("logo.png"))
        self.poster.setPixmap(pm.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.poster.setCursor(Qt.ArrowCursor)
        self.poster.setToolTip("")
        self.poster.show()

    def _show_poster(self, anime: Anime, req: int) -> None:
        url = anime.poster("big", "medium", "fullsize")
        if not url:
            self._show_logo()
            return
        self._poster_anime = anime
        self.poster.clear()
        self.poster.setCursor(Qt.PointingHandCursor)
        self.poster.setToolTip(_("Click to view full screen"))
        self.poster.show()

        def show(data: bytes) -> None:
            if req != self._req:
                return  # user already picked another title
            pm = self._pixmap(data)
            if pm.isNull():
                self._show_logo()
                return
            self.poster.setPixmap(pm.scaled(POSTER_W, POSTER_H, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        self._load_image(url, show)

    def _open_poster(self) -> None:
        anime = self._poster_anime
        if anime is None or self.poster.pixmap() is None:
            return
        small = anime.poster("big", "medium")
        start = self._pixmap(self._images[small]) if small in self._images else self.poster.pixmap()
        viewer = ImageViewer(start, anime.title, self)
        full = anime.poster("fullsize", "mega", "huge")
        if full and full != small:
            viewer.loading = full not in self._images

            def upgrade(data: bytes | None) -> None:
                try:
                    viewer.set_pixmap(self._pixmap(data) if data else QPixmap())
                except RuntimeError:  # viewer already closed and deleted
                    pass

            self._load_image(full, upgrade, lambda _err: upgrade(None))
        viewer.show_on(self)

    # --- search & title -----------------------------------------------------

    def _search(self) -> None:
        q = self.search_edit.text().strip()
        if not q:
            return
        self._req += 1
        req = self._req
        self._status(_("Searching “{query}”…", query=q))
        self.results.clear()

        def done(results: list[Anime]) -> None:
            if req != self._req:
                return
            for a in results:
                item = QListWidgetItem(f"{a.title}\n{a.year or ''} · {a.type} · {a.status}")
                item.setData(Qt.UserRole, a)
                item.setSizeHint(QSize(0, 54))
                self.results.addItem(item)
                if url := a.poster("small", "medium"):
                    self._load_image(url, lambda data, it=item: it.setIcon(QIcon(self._pixmap(data))))
            self._status(ngettext("{n} result", "{n} results", len(results)) if results else _("Nothing found"), 5000)

        run_bg(lambda: self.api.search(q, limit=30), done, self._error)

    def _on_result_selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        if item is None:
            return
        a: Anime = item.data(Qt.UserRole)
        self._req += 1
        req = self._req
        self.anime = None
        self.title_lbl.setText(a.title)
        self.sub_lbl.setText(_("Loading…"))
        self._show_poster(a, req)
        self.dub_combo.clear()
        self.episodes.clear()
        self._set_details_enabled(False)

        def load():
            return self.api.get_anime(a.anime_id), self.api.get_videos(a.anime_id)

        def done(result) -> None:
            if req != self._req:
                return
            anime, videos = result
            self._show_anime(anime, videos)

        run_bg(load, done, self._error)

    def _show_anime(self, anime: Anime, videos: list[Video]) -> None:
        self.anime = anime
        bits = [str(anime.year or ""), anime.type, anime.status]
        if anime.episodes:
            bits.append(_("{n} ep.", n=anime.episodes))
        others = ", ".join(anime.other_titles[:2])
        self.sub_lbl.setText(" · ".join(b for b in bits if b) + (f"\n{others}" if others else ""))
        options = core.group_by_dub(videos)
        if note := core.unsupported_note(options):
            self.sub_lbl.setText(f"{self.sub_lbl.text()}\n{note}")
        self.dubs = [d for d in options if d.supported]
        self.dub_combo.blockSignals(True)
        self.dub_combo.clear()
        for d in self.dubs:
            players = ", ".join(sorted(n for n, vids in d.by_player.items() if any(find_extractor(v) for v in vids)))
            self.dub_combo.addItem(f"{d.dub_name}  —  " + _("{n} ep.", n=len(d.supported_episodes)) + f" · {players}")
        self.dub_combo.blockSignals(False)
        if not self.dubs:
            self.sub_lbl.setText(self.sub_lbl.text() + "\n" + _("No downloadable dubs (supported: CVH, Kodik, Aksor)."))
            return
        self._set_details_enabled(True)
        self._on_dub_changed()

    def _current_dub(self) -> core.DubOption | None:
        i = self.dub_combo.currentIndex()
        return self.dubs[i] if 0 <= i < len(self.dubs) else None

    def _on_dub_changed(self) -> None:
        dub = self._current_dub()
        self.player_combo.blockSignals(True)
        self.player_combo.clear()
        if dub:
            self.player_combo.addItem(_("Auto"), None)
            supported = {e.name for e in EXTRACTORS}
            for name in sorted(dub.by_player):
                if name in supported:
                    self.player_combo.addItem(name, name)
        self.player_combo.blockSignals(False)
        self._fill_episodes()

    def _player(self) -> str | None:
        return self.player_combo.currentData()

    def _picks(self) -> dict[str, Video]:
        dub = self._current_dub()
        if not dub:
            return {}
        player = self._player()
        eps = dub.supported_episodes
        if player:
            eps = [e for e in eps if any(v.number == e for v in dub.by_player.get(player, []))]
        return core.pick_videos(dub, eps, player)

    def _fill_episodes(self) -> None:
        self.episodes.blockSignals(True)
        self.episodes.clear()
        if self.anime:
            out = self._out_dir()
            for ep, video in self._picks().items():
                have = core.existing_download(core.episode_path(self.anime, video, out))
                item = QListWidgetItem(_("Episode {ep}", ep=ep) + f"   [{video.player_name}]"
                                       + ("   " + _("✓ downloaded") if have else ""))
                item.setData(Qt.UserRole, ep)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked if have else Qt.Checked)
                self.episodes.addItem(item)
        self.episodes.blockSignals(False)
        self._update_selection_label()

    def _checked(self) -> list[str]:
        return [self.episodes.item(i).data(Qt.UserRole) for i in range(self.episodes.count())
                if self.episodes.item(i).checkState() == Qt.Checked]

    def _check_all(self, on: bool) -> None:
        self.episodes.blockSignals(True)
        for i in range(self.episodes.count()):
            self.episodes.item(i).setCheckState(Qt.Checked if on else Qt.Unchecked)
        self.episodes.blockSignals(False)
        self._update_selection_label()

    def _update_selection_label(self, *_args) -> None:
        n = len(self._checked())
        self.sel_lbl.setText(_("{n} of {total} selected", n=n, total=self.episodes.count()))
        self.add_btn.setEnabled(n > 0)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, _("Download folder"), str(self._out_dir()))
        if d:
            self.out_edit.setText(d)
            self._save_prefs()
            self._fill_episodes()

    def _set_language(self, code: str) -> None:
        if code == self.cfg.language:
            return
        self.cfg.language = code
        cfgmod.save(self.cfg)
        new = i18n.resolve(code)
        if new == i18n.current():
            return  # e.g. "System default" while the system language is already in use
        # Ask in the language being switched to, so the user can read the question either way.
        old = i18n.current()
        i18n.set_language(new)
        question = _("Restart yummy-dl now to switch the language?")
        active = [j for j in self.jobs.values() if j.status in ACTIVE]
        if active:
            question += "\n\n" + ngettext(
                "{n} job is still running and will be stopped (downloads resume when re-added).",
                "{n} jobs are still running and will be stopped (downloads resume when re-added).", len(active))
        later = _("The new language will be used the next time you start the app.")
        restart = QMessageBox.question(self, "yummy-dl", question) == QMessageBox.Yes
        if not restart:
            QMessageBox.information(self, "yummy-dl", later)
        i18n.set_language(old)  # the running window keeps one language until the restart
        if restart:
            self._restart()

    def _restart(self) -> None:
        if getattr(sys, "frozen", False):
            program, args = sys.executable, sys.argv[1:]
        else:
            program, args = sys.executable, ["-m", "yummy_dl.gui", *sys.argv[1:]]
        if not QProcess.startDetached(program, args):
            self._error(_("Couldn't restart automatically. Please start yummy-dl again."))
            return
        self._restarting = True
        self.close()

    def _set_token(self) -> None:
        self._show_help(helpdlg.TAB_TOKEN)

    def _show_help(self, tab: int = helpdlg.TAB_START) -> None:
        helpdlg.HelpDialog(self, self.cfg, self._save_token, tab).exec()

    def _save_token(self, tok: str) -> None:
        self.cfg.token = tok
        cfgmod.save(self.cfg)
        self.api.close()
        self.api = YummyClient(token=self.cfg.effective_token)
        self._status(_("Token saved") if tok else _("Token removed"), 4000)

    # --- queue --------------------------------------------------------------

    def _enqueue(self) -> None:
        if not self.anime:
            return
        picks = self._picks()
        wanted = self._checked()
        dub = self._current_dub()
        self._save_prefs()
        for ep in wanted:
            job = Job(self.anime, picks[ep], self._out_dir(), self.quality_combo.currentData(), self.cfg.workers)
            self.jobs[job.id] = job
            row = self.queue.rowCount()
            self.queue.insertRow(row)
            title = QTableWidgetItem(self.anime.title)
            title.setData(Qt.UserRole, job.id)
            self.queue.setItem(row, 0, title)
            self.queue.setItem(row, 1, QTableWidgetItem(ep))
            self.queue.setItem(row, 2, QTableWidgetItem(f"{dub.dub_name} [{job.video.player_name}]"))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            self.queue.setCellWidget(row, 3, bar)
            self.queue.setItem(row, 4, QTableWidgetItem(QUEUED))
            self.manager.add(job)
        self._status(ngettext("Queued {n} episode", "Queued {n} episodes", len(wanted)), 4000)

    def _row(self, job_id: int) -> int:
        for r in range(self.queue.rowCount()):
            item = self.queue.item(r, 0)
            if item and item.data(Qt.UserRole) == job_id:
                return r
        return -1

    def _on_progress(self, job_id: int, done: int, total: int) -> None:
        r = self._row(job_id)
        if r >= 0 and total:
            self.queue.cellWidget(r, 3).setValue(int(done * 100 / total))

    def _on_status(self, job_id: int, status: str, detail: str) -> None:
        r = self._row(job_id)
        if r < 0:
            return
        bar: QProgressBar = self.queue.cellWidget(r, 3)
        if status in (DONE, SKIPPED):
            bar.setValue(100)
        item = QTableWidgetItem(f"{_(status)}: {detail}" if detail else _(status))
        item.setToolTip(detail)
        if status == FAILED:
            item.setForeground(Qt.red)
        self.queue.setItem(r, 4, item)
        job = self.jobs.get(job_id)
        if status in (DONE, SKIPPED) and job:
            self._mark_downloaded(job)
        if status == DONE and isinstance(job, Job) and job.result:
            if auto := scriptmod.auto_script(self.scripts):
                self._run_script(auto, [job.result], confirm=False)

    def _mark_downloaded(self, job: Job) -> None:
        """Tick the finished episode in the list without disturbing the user's other checkboxes."""
        if not isinstance(job, Job) or not self.anime or job.anime.anime_id != self.anime.anime_id:
            return
        for i in range(self.episodes.count()):
            item = self.episodes.item(i)
            if item.data(Qt.UserRole) == job.video.number and job.video.player_name in item.text():
                if "✓" not in item.text():
                    self.episodes.blockSignals(True)
                    item.setText(item.text() + "   " + _("✓ downloaded"))
                    item.setCheckState(Qt.Unchecked)
                    self.episodes.blockSignals(False)
                    self._update_selection_label()

    def _cancel_selected(self) -> None:
        rows = {i.row() for i in self.queue.selectedIndexes()}
        for r in rows:
            job = self.jobs.get(self.queue.item(r, 0).data(Qt.UserRole))
            if job and job.status in ACTIVE:
                job.cancel.set()
                if job.status == QUEUED:
                    job.status = CANCELLED
                    self.queue.setItem(r, 4, QTableWidgetItem(_(CANCELLED)))

    def _clear_finished(self) -> None:
        for r in reversed(range(self.queue.rowCount())):
            job = self.jobs.get(self.queue.item(r, 0).data(Qt.UserRole))
            if job and job.status in FINISHED:
                self.queue.removeRow(r)
                del self.jobs[job.id]

    def _open_job(self, index) -> None:
        job = self.jobs.get(self.queue.item(index.row(), 0).data(Qt.UserRole))
        if job and job.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(job.result.parent)))

    # --- scripts ------------------------------------------------------------

    def _rebuild_scripts_menu(self) -> None:
        menu = self.scripts_menu
        menu.clear()
        menu.setToolTipsVisible(True)
        act = menu.addAction(_("&Manage scripts…"))
        act.triggered.connect(self._manage_scripts)
        if not self.scripts:
            menu.addSeparator()
            hint = menu.addAction(_("No scripts yet: add one in Manage scripts…"))
            hint.setEnabled(False)
            return
        menu.addSeparator()
        for script in self.scripts:
            sub = menu.addMenu(script.name + ("   " + _("(auto)") if script.auto else ""))
            sub.menuAction().setToolTip(script.comment)
            sub.menuAction().setStatusTip(script.comment)
            a = sub.addAction(_("Run on &files…"))
            a.triggered.connect(lambda _c=False, s=script: self._run_on_files(s))
            a = sub.addAction(_("Run on a f&older…"))
            a.triggered.connect(lambda _c=False, s=script: self._run_on_folder(s))

    def _manage_scripts(self) -> None:
        if self._scripts_error:
            self._error(f"{self._scripts_error}\n" + _("It will be overwritten when you save."))
            self._scripts_error = ""

        def saved(scripts: list[scriptmod.Script]) -> None:
            self.scripts = scripts
            self._rebuild_scripts_menu()
            self._status(_("Scripts saved"), 4000)

        ScriptsDialog(self, self.scripts, saved).exec()

    def _run_on_files(self, script: scriptmod.Script) -> None:
        exts = " ".join(f"*{e}" for e in sorted(core.VIDEO_EXTS))
        files, _filter = QFileDialog.getOpenFileNames(
            self, _("Run '{name}' on…", name=script.name), str(self._out_dir()),
            _("Videos ({exts});;All files (*)", exts=exts))
        if files:
            self._run_script(script, [Path(f) for f in files])

    def _run_on_folder(self, script: scriptmod.Script) -> None:
        d = QFileDialog.getExistingDirectory(self, _("Run '{name}' on every video in…", name=script.name),
                                             str(self._out_dir()))
        if d:
            self._run_script(script, [Path(d)])

    def _run_script(self, script: scriptmod.Script, paths: list[Path], confirm: bool = True) -> None:
        if not hls.find_ffmpeg():
            self._error(_("Scripts need ffmpeg, and it wasn't found.\n"
                          "Windows: run  winget install ffmpeg  or put ffmpeg.exe next to yummy-dl-gui.exe."))
            return
        busy = {j.input for j in self.jobs.values() if isinstance(j, ScriptJob) and j.status in ACTIVE}
        inputs = [p for p in scriptmod.collect_inputs(paths) if p not in busy]
        if not inputs:
            self._error(_("No video files found there (or they're already queued)."))
            return
        if confirm and self._confirm_delete:
            box = QMessageBox(QMessageBox.Question, _("Run script"),
                              ngettext("Run '{name}' on {n} file?", "Run '{name}' on {n} files?", len(inputs),
                                       name=script.name) + "\n\n"
                              + _("Each original is deleted after its conversion succeeds. "
                                  "If ffmpeg fails, the original is kept."),
                              QMessageBox.Yes | QMessageBox.Cancel, self)
            box.setCheckBox(QCheckBox(_("Don't ask again until I restart the app")))
            if box.exec() != QMessageBox.Yes:
                return
            self._confirm_delete = not box.checkBox().isChecked()
        for src in inputs:
            job = ScriptJob(script, src)
            self.jobs[job.id] = job
            row = self.queue.rowCount()
            self.queue.insertRow(row)
            title = QTableWidgetItem(f"⚙ {script.name}")
            title.setData(Qt.UserRole, job.id)
            title.setToolTip(script.comment)
            self.queue.setItem(row, 0, title)
            name = QTableWidgetItem(src.name)
            name.setToolTip(str(src))
            self.queue.setItem(row, 1, name)
            self.queue.setItem(row, 2, QTableWidgetItem(""))
            bar = QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(0)
            self.queue.setCellWidget(row, 3, bar)
            self.queue.setItem(row, 4, QTableWidgetItem(QUEUED))
            self.script_mgr.add(job)
        self._status(ngettext("Queued '{name}' on {n} file", "Queued '{name}' on {n} files", len(inputs),
                              name=script.name), 4000)

    def _queue_menu(self, pos) -> None:
        item = self.queue.itemAt(pos)
        if not item:
            return
        rows = sorted({i.row() for i in self.queue.selectedIndexes()} | {item.row()})
        files = []
        for r in rows:
            job = self.jobs.get(self.queue.item(r, 0).data(Qt.UserRole))
            if job and job.status in (DONE, SKIPPED) and job.result and job.result.is_file():
                files.append(job.result)
        menu = QMenu(self)
        sub = menu.addMenu(_("Run script"))
        sub.setEnabled(bool(files and self.scripts))
        for script in self.scripts:
            a = sub.addAction(script.name)
            a.triggered.connect(lambda _c=False, s=script: self._run_script(s, files))
        menu.addAction(_("Open folder"), lambda: self._open_job(self.queue.indexFromItem(item)))
        menu.exec(self.queue.viewport().mapToGlobal(pos))

    def closeEvent(self, event) -> None:
        active = [j for j in self.jobs.values() if j.status in ACTIVE]
        if active and not getattr(self, "_restarting", False):
            ans = QMessageBox.question(
                self, "yummy-dl",
                ngettext("{n} job still running. Quit anyway?", "{n} jobs still running. Quit anyway?", len(active))
                + "\n" + _("(Partial downloads resume next time; unfinished scripts keep the original file.)"))
            if ans != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()
