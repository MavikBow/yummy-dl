"""Background work for the GUI: one-off API calls and the sequential download queue."""

from __future__ import annotations

import itertools
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from .. import core
from .. import scripts as scriptmod
from ..i18n import N_, _
from ..models import Anime, Video


class _Signals(QObject):
    done = Signal(object)
    failed = Signal(str)


class _Call(QRunnable):
    def __init__(self, fn: Callable[[], object]):
        super().__init__()
        self.fn = fn
        self.signals = _Signals()

    def run(self) -> None:
        try:
            try:
                result = self.fn()
            except Exception as e:  # surfaced in the UI, never crash the worker pool
                self.signals.failed.emit(str(e) or type(e).__name__)
            else:
                self.signals.done.emit(result)
        except RuntimeError:
            pass  # the app/window closed while this was running; nobody is listening anymore


_alive: set[_Call] = set()


def run_bg(fn: Callable[[], object], on_done: Callable[[object], None], on_fail: Callable[[str], None]) -> None:
    """Run `fn` on the Qt thread pool; callbacks are delivered on the GUI thread."""
    call = _Call(fn)
    call.setAutoDelete(False)
    _alive.add(call)

    def finish() -> None:
        _alive.discard(call)

    call.signals.done.connect(on_done)
    call.signals.failed.connect(on_fail)
    call.signals.done.connect(finish)
    call.signals.failed.connect(finish)
    QThreadPool.globalInstance().start(call)


# --- download queue ------------------------------------------------------------

# Status codes double as English display text; the window shows them through _().
QUEUED, RUNNING, DONE, SKIPPED = N_("Queued"), N_("Downloading"), N_("Done"), N_("Exists")
FAILED, CANCELLED, CONVERTING = N_("Failed"), N_("Cancelled"), N_("Running script")
ACTIVE = (QUEUED, RUNNING, CONVERTING)
FINISHED = (DONE, SKIPPED, FAILED, CANCELLED)

_ids = itertools.count(1)


@dataclass
class Job:
    anime: Anime
    video: Video
    out_dir: Path
    quality: int
    workers: int
    id: int = field(default_factory=lambda: next(_ids))
    status: str = QUEUED
    result: Path | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


class DownloadManager(QObject):
    """Runs jobs one at a time on a daemon thread (each job already downloads in parallel)."""

    progress = Signal(int, int, int)  # job id, done, total
    status = Signal(int, str, str)  # job id, status, detail

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue[Job] = queue.Queue()
        self._thread = threading.Thread(target=self._loop, name="downloads", daemon=True)
        self._thread.start()

    def add(self, job: Job) -> None:
        self._queue.put(job)
        self.status.emit(job.id, QUEUED, "")

    def _loop(self) -> None:
        job = self._queue.get()  # build the HTTP client only once there is work (keeps startup fast)
        with httpx.Client(timeout=60, follow_redirects=True) as http:
            while True:
                if not job.cancel.is_set():
                    self._run(job, http)
                job = self._queue.get()

    def _run(self, job: Job, http: httpx.Client) -> None:
        target = core.episode_path(job.anime, job.video, job.out_dir)
        if existing := core.existing_download(target):
            job.status, job.result = SKIPPED, existing
            self.status.emit(job.id, SKIPPED, str(existing))
            return
        job.status = RUNNING
        self.status.emit(job.id, RUNNING, "")
        last = 0.0

        def on_progress(done: int, total: int) -> None:
            nonlocal last
            if job.cancel.is_set():
                raise core.Cancelled()
            now = time.monotonic()
            if now - last >= 0.15 or done >= total:
                last = now
                self.progress.emit(job.id, done, total)

        try:
            path, q = core.download_episode(job.anime, job.video, job.out_dir, quality=job.quality,
                                            workers=job.workers, progress=on_progress, http=http)
        except core.Cancelled:
            job.status = CANCELLED
            self.status.emit(job.id, CANCELLED, _("partial download kept, re-add to resume"))
        except Exception as e:  # anything else must not kill the queue thread
            job.status = FAILED
            self.status.emit(job.id, FAILED, str(e) or type(e).__name__)
        else:
            job.status, job.result = DONE, path
            self.status.emit(job.id, DONE, f"{q}p · {path}")


# --- user scripts ------------------------------------------------------------------


@dataclass
class ScriptJob:
    script: scriptmod.Script
    input: Path
    id: int = field(default_factory=lambda: next(_ids))
    status: str = QUEUED
    result: Path | None = None
    cancel: threading.Event = field(default_factory=threading.Event)


class ScriptManager(QObject):
    """Runs user scripts one at a time on its own thread, so a long encode never blocks downloads."""

    progress = Signal(int, int, int)  # job id, done ms, total ms
    status = Signal(int, str, str)  # job id, status, detail

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue[ScriptJob] = queue.Queue()
        self._thread: threading.Thread | None = None

    def add(self, job: ScriptJob) -> None:
        if self._thread is None:  # started lazily: most sessions never run a script
            self._thread = threading.Thread(target=self._loop, name="scripts", daemon=True)
            self._thread.start()
        self._queue.put(job)
        self.status.emit(job.id, QUEUED, "")

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            if not job.cancel.is_set():
                self._run(job)

    def _run(self, job: ScriptJob) -> None:
        job.status = CONVERTING
        self.status.emit(job.id, CONVERTING, "")
        last = 0.0

        def on_progress(done: int, total: int) -> None:
            nonlocal last
            if job.cancel.is_set():
                raise core.Cancelled()
            now = time.monotonic()
            if now - last >= 0.3 or done >= total:
                last = now
                self.progress.emit(job.id, done, total)

        try:
            out = scriptmod.run_script(job.script, job.input, progress=on_progress)
        except core.Cancelled:
            job.status = CANCELLED
            self.status.emit(job.id, CANCELLED, _("original kept"))
        except Exception as e:  # never kill the thread
            job.status = FAILED
            self.status.emit(job.id, FAILED, f"{e or type(e).__name__} " + _("(original kept)"))
        else:
            job.status, job.result = DONE, out[0]
            more = " " + _("(+{n} more)", n=len(out) - 1) if len(out) > 1 else ""
            self.status.emit(job.id, DONE, f"{out[0].name}{more}")
