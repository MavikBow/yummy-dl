"""Main window: search → pick title → dub/player/quality → episodes → download queue."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt, QTimer, QUrl
from PySide6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence, QPalette, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
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
from .. import core, hls
from ..api import YummyClient
from ..extractors import EXTRACTORS, find_extractor
from ..models import Anime, Video
from . import theme
from .viewer import ClickableLabel, ImageViewer
from .workers import CANCELLED, DONE, FAILED, QUEUED, RUNNING, SKIPPED, DownloadManager, Job, run_bg

QUALITIES = [1080, 720, 480, 360]
POSTER_W, POSTER_H = 160, 224
AUTO = "Auto"


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

        self._build_menu()
        self._build_ui()
        self._refresh_ffmpeg_status()
        # Warm up TLS/HTTP after the first paint so the first search is quick.
        QTimer.singleShot(200, lambda: run_bg(self.api.warm, lambda _r: None, lambda _e: None))

    # --- layout -------------------------------------------------------------

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&Settings")
        act = QAction("API &token…", self)
        act.triggered.connect(self._set_token)
        menu.addAction(act)
        self.dark_act = QAction("&Dark theme", self, checkable=True)
        self.dark_act.setChecked(theme.resolve(self.cfg.theme))
        self.dark_act.toggled.connect(self._toggle_dark)
        menu.addAction(self.dark_act)
        menu.addSeparator()
        act = QAction("Open &config folder", self)
        act.triggered.connect(lambda: self._open(cfgmod.config_path().parent))
        menu.addAction(act)

    def _build_ui(self) -> None:
        # search bar
        self.search_edit = QLineEdit(placeholderText="Search anime, e.g. берсерк or Re:Zero")
        self.search_edit.returnPressed.connect(self._search)
        search_btn = QPushButton("Search")
        search_btn.clicked.connect(self._search)
        top = QHBoxLayout()
        top.addWidget(self.search_edit, 1)
        top.addWidget(search_btn)

        # results
        self.results = QListWidget()
        self.results.setIconSize(QSize(33, 47))
        self.results.currentItemChanged.connect(self._on_result_selected)

        # details
        self.title_lbl = QLabel("Search for a title to begin.")
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
        self.poster.setToolTip("Click to view full screen")
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
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        out_row = QHBoxLayout()
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(browse)

        form = QFormLayout()
        form.addRow("Dub:", self.dub_combo)
        form.addRow("Player:", self.player_combo)
        form.addRow("Max quality:", self.quality_combo)
        form.addRow("Save to:", out_row)

        self.episodes = QListWidget()
        self.episodes.itemChanged.connect(self._update_selection_label)
        all_btn = QPushButton("All")
        all_btn.clicked.connect(lambda: self._check_all(True))
        none_btn = QPushButton("None")
        none_btn.clicked.connect(lambda: self._check_all(False))
        self.sel_lbl = QLabel("")
        self.add_btn = QPushButton("Download selected")
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
        dl.addWidget(QLabel("Episodes:"))
        dl.addWidget(self.episodes, 1)
        dl.addLayout(ep_btns)

        upper = QSplitter(Qt.Horizontal)
        upper.addWidget(self.results)
        upper.addWidget(details)
        upper.setSizes([380, 720])

        # queue
        self.queue = QTableWidget(0, 5)
        self.queue.setHorizontalHeaderLabels(["Title", "Episode", "Dub", "Progress", "Status"])
        self.queue.verticalHeader().hide()
        self.queue.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.queue.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.queue.doubleClicked.connect(self._open_job)
        h = self.queue.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        for col in (1, 2):
            h.setSectionResizeMode(col, QHeaderView.ResizeToContents)
        h.resizeSection(3, 200)
        h.setSectionResizeMode(4, QHeaderView.Stretch)

        cancel_btn = QPushButton("Cancel selected")
        cancel_btn.clicked.connect(self._cancel_selected)
        clear_btn = QPushButton("Clear finished")
        clear_btn.clicked.connect(self._clear_finished)
        open_btn = QPushButton("Open folder")
        open_btn.clicked.connect(lambda: self._open(Path(self.out_edit.text())))
        qbtns = QHBoxLayout()
        qbtns.addWidget(QLabel("Downloads (double-click to open):"), 1)
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
            self.statusBar().addPermanentWidget(QLabel("ffmpeg not found: Kodik episodes save as .ts"))

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
        self.poster.setToolTip("Click to view full screen")
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
        self._status(f"Searching “{q}”…")
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
            self._status(f"{len(results)} result(s)" if results else "Nothing found", 5000)

        run_bg(lambda: self.api.search(q, limit=30), done, self._error)

    def _on_result_selected(self, item: QListWidgetItem | None, _prev=None) -> None:
        if item is None:
            return
        a: Anime = item.data(Qt.UserRole)
        self._req += 1
        req = self._req
        self.anime = None
        self.title_lbl.setText(a.title)
        self.sub_lbl.setText("Loading…")
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
            bits.append(f"{anime.episodes} ep.")
        others = ", ".join(anime.other_titles[:2])
        self.sub_lbl.setText(" · ".join(b for b in bits if b) + (f"\n{others}" if others else ""))
        self.dubs = [d for d in core.group_by_dub(videos) if d.supported]
        self.dub_combo.blockSignals(True)
        self.dub_combo.clear()
        for d in self.dubs:
            players = ", ".join(sorted(n for n, vids in d.by_player.items() if any(find_extractor(v) for v in vids)))
            self.dub_combo.addItem(f"{d.dub_name}  —  {len(d.supported_episodes)} ep. · {players}")
        self.dub_combo.blockSignals(False)
        if not self.dubs:
            self.sub_lbl.setText(self.sub_lbl.text() + "\nNo dubs on supported players (CVH, Kodik).")
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
            self.player_combo.addItem(AUTO)
            supported = {e.name for e in EXTRACTORS}
            for name in sorted(dub.by_player):
                if name in supported:
                    self.player_combo.addItem(name)
        self.player_combo.blockSignals(False)
        self._fill_episodes()

    def _player(self) -> str | None:
        p = self.player_combo.currentText()
        return None if p in ("", AUTO) else p

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
                item = QListWidgetItem(f"Episode {ep}   [{video.player_name}]" + ("   ✓ downloaded" if have else ""))
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
        self.sel_lbl.setText(f"{n} of {self.episodes.count()} selected")
        self.add_btn.setEnabled(n > 0)

    def _browse(self) -> None:
        d = QFileDialog.getExistingDirectory(self, "Download folder", str(self._out_dir()))
        if d:
            self.out_edit.setText(d)
            self._save_prefs()
            self._fill_episodes()

    def _set_token(self) -> None:
        tok, ok = QInputDialog.getText(
            self, "API token",
            "YummyAnime application token\n(create one at yummyani.me/dev/applications):",
            QLineEdit.Normal, self.cfg.token)
        if ok:
            self.cfg.token = tok.strip()
            cfgmod.save(self.cfg)
            self.api.close()
            self.api = YummyClient(token=self.cfg.effective_token)
            self._status("Token saved", 4000)

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
        self._status(f"Queued {len(wanted)} episode(s)", 4000)

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
        item = QTableWidgetItem(f"{status}: {detail}" if detail else status)
        item.setToolTip(detail)
        if status == FAILED:
            item.setForeground(Qt.red)
        self.queue.setItem(r, 4, item)
        if status in (DONE, SKIPPED) and job_id in self.jobs:
            self._mark_downloaded(self.jobs[job_id])

    def _mark_downloaded(self, job: Job) -> None:
        """Tick the finished episode in the list without disturbing the user's other checkboxes."""
        if not self.anime or job.anime.anime_id != self.anime.anime_id:
            return
        for i in range(self.episodes.count()):
            item = self.episodes.item(i)
            if item.data(Qt.UserRole) == job.video.number and job.video.player_name in item.text():
                if "✓" not in item.text():
                    self.episodes.blockSignals(True)
                    item.setText(item.text() + "   ✓ downloaded")
                    item.setCheckState(Qt.Unchecked)
                    self.episodes.blockSignals(False)
                    self._update_selection_label()

    def _cancel_selected(self) -> None:
        rows = {i.row() for i in self.queue.selectedIndexes()}
        for r in rows:
            job = self.jobs.get(self.queue.item(r, 0).data(Qt.UserRole))
            if job and job.status in (QUEUED, RUNNING):
                job.cancel.set()
                if job.status == QUEUED:
                    job.status = CANCELLED
                    self.queue.setItem(r, 4, QTableWidgetItem(CANCELLED))

    def _clear_finished(self) -> None:
        for r in reversed(range(self.queue.rowCount())):
            job = self.jobs.get(self.queue.item(r, 0).data(Qt.UserRole))
            if job and job.status in (DONE, SKIPPED, FAILED, CANCELLED):
                self.queue.removeRow(r)
                del self.jobs[job.id]

    def _open_job(self, index) -> None:
        job = self.jobs.get(self.queue.item(index.row(), 0).data(Qt.UserRole))
        if job and job.result:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(job.result.parent)))

    def closeEvent(self, event) -> None:
        active = [j for j in self.jobs.values() if j.status in (QUEUED, RUNNING)]
        if active:
            ans = QMessageBox.question(
                self, "yummy-dl",
                f"{len(active)} download(s) still running. Quit anyway?\n(Partial downloads resume next time.)")
            if ans != QMessageBox.Yes:
                event.ignore()
                return
        event.accept()
