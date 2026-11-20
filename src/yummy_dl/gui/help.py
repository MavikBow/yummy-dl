"""Help dialog: quick start, guided API-token setup, and command-line reference."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFontDatabase, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..i18n import _
from .. import config as cfgmod
from .. import hls

APPS_URL = "https://yummyani.me/dev/applications"
SITE_URL = "https://yummyani.me"
SWAGGER_URL = "https://api.yani.tv/swagger"

TAB_START, TAB_TOKEN, TAB_CLI, TAB_ABOUT = range(4)


def cli_command() -> str:
    """How the user should invoke the CLI from a terminal."""
    if getattr(sys, "frozen", False):
        return "yummy-dl.exe" if sys.platform == "win32" else "./yummy-dl"
    return "yummy-dl"


def cli_dir() -> Path | None:
    """Folder holding the bundled CLI exe (release build only)."""
    if not getattr(sys, "frozen", False):
        return None
    folder = Path(sys.executable).resolve().parent
    name = "yummy-dl.exe" if sys.platform == "win32" else "yummy-dl"
    return folder if (folder / name).exists() else None


def cli_reference(cmd: str) -> str:
    def c(text: str) -> str:
        return "# " + text

    return "\n".join([
        c(_("Find a title")),
        f'{cmd} search "берсерк"',
        "",
        c(_("Show dubs, episodes and players for a title (id, alias or text)")),
        f"{cmd} info berserk",
        "",
        c(_("Download: asks which dub and episodes if you leave them out")),
        f"{cmd} download berserk",
        "",
        c(_("Download non-interactively")),
        f'{cmd} download berserk -d "MC Entertainment" -e 1-5,8 -q 720 -o D:\\Anime',
        "",
        c("  -d / --dub        " + _("part of the dub name")),
        c("  -e / --episodes   " + _("e.g. 1-5,8  (default: all)")),
        c("  -q / --quality    " + _("max height: 1080, 720, 480, 360")),
        c("  -o / --out        " + _("download folder")),
        c("  -p / --player     cvh | kodik | aksor  " + _("(default: auto)")),
        c("  -w / --workers    " + _("parallel connections")),
        "",
        c(_("Guided mode (what double-clicking {cmd} does)", cmd=cmd)),
        f"{cmd} interactive",
        "",
        c(_("Settings")),
        f"{cmd} config set-token <TOKEN>",
        f"{cmd} config set --output-dir D:\\Anime --quality 1080",
        f"{cmd} config set --language ru          " + c(_("auto, en or ru")),
        f"{cmd} config show",
        "",
        c(_("Scripts (saved ffmpeg commands; create them in Scripts -> Manage scripts...)")),
        f"{cmd} scripts list",
        f'{cmd} scripts run "BBK 720p" D:\\Anime\\Berserk     ' + c(_("a folder or files; originals are replaced")),
        f'{cmd} download berserk -e 1-3 --script "BBK 720p"   ' + c(_("convert each new episode")),
        f"{cmd} download berserk --no-script                 " + c(_("skip the auto-run script")),
        "",
        c(_("Open this desktop app")),
        f"{cmd} gui",
        "",
        c(_("Built-in help for any command")),
        f"{cmd} --help",
        f"{cmd} download --help",
        "",
    ])


def _label(html: str) -> QLabel:
    lbl = QLabel(html)
    lbl.setWordWrap(True)
    lbl.setTextFormat(Qt.RichText)
    lbl.setOpenExternalLinks(True)
    lbl.setTextInteractionFlags(Qt.TextBrowserInteraction)
    lbl.setAlignment(Qt.AlignTop | Qt.AlignLeft)
    return lbl


class HelpDialog(QDialog):
    """`on_token_saved(token)` is called after the user saves a token."""

    def __init__(self, parent, cfg: cfgmod.Config, on_token_saved, tab: int = TAB_START) -> None:
        super().__init__(parent)
        self.setWindowTitle(_("yummy-dl help"))
        self.resize(680, 560)
        self.cfg = cfg
        self._on_token_saved = on_token_saved

        self.tabs = QTabWidget()
        self.tabs.addTab(self._start_tab(), _("Quick start"))
        self.tabs.addTab(self._token_tab(), _("API token"))
        self.tabs.addTab(self._cli_tab(), _("Command line"))
        self.tabs.addTab(self._about_tab(), _("About"))
        self.tabs.setCurrentIndex(tab)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(self.tabs)
        lay.addWidget(buttons)

    # --- tabs -----------------------------------------------------------------

    def _start_tab(self) -> QWidget:
        ffmpeg = hls.find_ffmpeg()
        ffmpeg_line = (
            _("✓ ffmpeg found, so every player works.")
            if ffmpeg else
            _("⚠ ffmpeg not found. Kodik episodes will be saved as <code>.ts</code>, and Aksor needs it. "
              "On Windows run <code>winget install ffmpeg</code> or put <code>ffmpeg.exe</code> next to the app.")
        )
        html = _("""
<h3>Downloading an episode</h3>
<ol>
<li><b>Search</b> for a title (Russian or English name) and press Enter.</li>
<li><b>Pick it</b> from the list on the left. Click the poster to see it full screen.</li>
<li>Choose the <b>dub</b>, the <b>player</b> (Auto picks the best one), the max <b>quality</b>
    and the <b>folder</b>.</li>
<li><b>Tick episodes</b>. Ones you already have are marked ✓.</li>
<li>Click <b>Download selected</b>. Progress shows in the queue at the bottom.</li>
</ol>
<h3>Good to know</h3>
<ul>
<li>Cancelling keeps partial files. Adding the episode again resumes it.</li>
<li>Double-click a finished row in the queue to open its folder.</li>
<li>Files are saved as <code>&lt;folder&gt;/&lt;Title&gt;/&lt;Title&gt; - E01 [Dub].mp4</code>.</li>
<li>Dubs only available on the Alloha player can't be downloaded (it uses anti-bot protection).</li>
<li>{ffmpeg_line}</li>
</ul>
<h3>Scripts</h3>
<p><b>Scripts → Manage scripts…</b> saves ffmpeg commands with a name and a comment, e.g. to convert
episodes for a TV or cut a long video into 10-minute parts. Run one from <b>Scripts → &lt;name&gt;</b> on files
or a folder, by right-clicking a finished download, or tick <i>Run automatically after each download</i>.
The converted file replaces the original.</p>
<p>Set up your <a href="#token">API token</a> once. It takes a minute.</p>
""", ffmpeg_line=ffmpeg_line)
        lbl = _label(html)
        lbl.setOpenExternalLinks(False)
        lbl.linkActivated.connect(lambda _l: self.tabs.setCurrentIndex(TAB_TOKEN))
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(lbl)
        lay.addStretch()
        return w

    def _token_tab(self) -> QWidget:
        steps = _label(_("""
<p>YummyAnime asks every app to identify itself with a free <b>application token</b>.
Downloads work without one today, but the API docs say it's required, so it's worth setting up.</p>
<ol>
<li>Log in (or register) at <a href="{site}">yummyani.me</a>.</li>
<li>Open <a href="{apps}">yummyani.me/dev/applications</a> and create an application.
    Any name and description will do.</li>
<li>Copy the application's <b>public token</b>.</li>
<li>Paste it below and click <b>Save token</b>.</li>
</ol>
""", site=SITE_URL, apps=APPS_URL))
        open_btn = QPushButton(_("1. Open the applications page"))
        open_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(APPS_URL)))

        self.token_edit = QLineEdit(self.cfg.token)
        self.token_edit.setPlaceholderText(_("Paste your public token here"))
        self.token_edit.setClearButtonEnabled(True)
        paste_btn = QPushButton(_("Paste"))
        paste_btn.clicked.connect(self._paste_token)
        save_btn = QPushButton(_("Save token"))
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save_token)
        self.token_edit.returnPressed.connect(self._save_token)

        row = QHBoxLayout()
        row.addWidget(self.token_edit, 1)
        row.addWidget(paste_btn)
        row.addWidget(save_btn)

        self.token_status = QLabel()
        self.token_status.setWordWrap(True)
        self._refresh_token_status()

        note = _label(
            "<p style='color:gray'>"
            + _("The token is stored in <code>{path}</code> and sent as the <code>X-Application</code> header. "
                "The command-line tool uses the same setting. Instead of saving it here you can set the "
                "<code>{env}</code> environment variable, which takes priority.",
                path=cfgmod.config_path(), env=cfgmod.ENV_TOKEN)
            + "</p>")

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(steps)
        lay.addWidget(open_btn, 0, Qt.AlignLeft)
        lay.addSpacing(8)
        lay.addLayout(row)
        lay.addWidget(self.token_status)
        lay.addSpacing(8)
        lay.addWidget(note)
        lay.addStretch()
        return w

    def _cli_tab(self) -> QWidget:
        cmd = cli_command()
        folder = cli_dir()
        if folder:
            where = _("The command-line tool is <code>{cmd}</code>, in the same folder as this app: "
                      "<code>{folder}</code>. Open a terminal there and run the commands below.",
                      cmd=cmd, folder=folder)
        elif getattr(sys, "frozen", False):
            where = _("The command-line tool <code>{cmd}</code> is shipped in the release zip, "
                      "next to <code>yummy-dl-gui.exe</code>.", cmd=cmd)
        else:
            where = _("Run these in a terminal where yummy-dl is installed (your virtualenv).")
        intro = _label(f"<p>{where}</p><p>"
                       + _("Double-clicking it without arguments starts a guided mode that asks "
                           "what to download step by step.") + "</p>")

        text = QPlainTextEdit(cli_reference(cmd))
        text.setReadOnly(True)
        text.setLineWrapMode(QPlainTextEdit.NoWrap)
        text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))

        copy_btn = QPushButton(_("Copy all"))
        copy_btn.clicked.connect(lambda: self._copy(text.toPlainText(), copy_btn))
        row = QHBoxLayout()
        row.addWidget(copy_btn)
        if folder and sys.platform == "win32":
            term_btn = QPushButton(_("Open terminal here"))
            term_btn.setToolTip(_("Opens a Command Prompt in {folder}", folder=folder))
            term_btn.clicked.connect(lambda: self._open_terminal(folder))
            row.addWidget(term_btn)
        row.addStretch()

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(intro)
        lay.addWidget(text, 1)
        lay.addLayout(row)
        return w

    def _about_tab(self) -> QWidget:
        from . import asset

        logo = QLabel()
        pix = QPixmap(asset("logo.png"))
        if not pix.isNull():
            logo.setPixmap(pix.scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        info = _label(f"<h2>yummy-dl {__version__}</h2>" + _("""
<p>Downloader for Russian-dubbed anime from <a href="{site}">YummyAnime</a>,
built on the official API (<a href="{docs}">docs</a>).</p>
<p>Supported players: CVH, Kodik, Aksor.</p>
<p>The YummyAnime API is <b>for personal use only</b>. Don't redistribute downloaded content.</p>
<p style='color:gray'>Settings file: <code>{path}</code></p>
""", site=SITE_URL, docs=SWAGGER_URL, path=cfgmod.config_path()))
        w = QWidget()
        lay = QHBoxLayout(w)
        lay.addWidget(logo, 0, Qt.AlignTop)
        lay.addWidget(info, 1)
        return w

    # --- actions ----------------------------------------------------------------

    def _refresh_token_status(self) -> None:
        if os.environ.get(cfgmod.ENV_TOKEN):
            msg = _("✓ Using the token from the {env} environment variable (it overrides the saved one).",
                    env=cfgmod.ENV_TOKEN)
        elif self.cfg.token:
            msg = _("✓ A token is saved.")
        else:
            msg = _("No token saved yet.")
        self.token_status.setText(msg)

    def _paste_token(self) -> None:
        self.token_edit.setText(QGuiApplication.clipboard().text().strip())
        self.token_edit.setFocus()

    def _save_token(self) -> None:
        tok = self.token_edit.text().strip()
        if any(c.isspace() for c in tok):
            self.token_status.setText(_("⚠ That doesn't look like a token (it contains spaces). Copy just the token."))
            return
        self._on_token_saved(tok)
        self.token_edit.setText(tok)
        self._refresh_token_status()
        if tok:
            self.token_status.setText(self.token_status.text() + " " + _("Saved, you're all set."))
        else:
            self.token_status.setText(_("Token removed."))

    def _copy(self, text: str, btn: QPushButton) -> None:
        QGuiApplication.clipboard().setText(text)
        btn.setText(_("Copied ✓"))

    @staticmethod
    def _open_terminal(folder: Path) -> None:
        subprocess.Popen(
            ["cmd.exe", "/K", "yummy-dl.exe --help"],
            cwd=str(folder),
            creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
        )
