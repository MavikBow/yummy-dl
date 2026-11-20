<p align="center"><img src="src/yummy_dl/gui/assets/logo.png" width="128" alt="yummy-dl logo"></p>

# yummy-dl

Downloader for Russian-dubbed anime from [YummyAnime](https://yummyani.me), with a desktop app and a
command-line tool. It's built on the official API ([swagger](https://api.yani.tv/swagger)) and runs on Windows
and Linux.

> The YummyAnime API is **for personal use only**. Don't redistribute downloaded content.

## Install

**Windows:** download `yummy-dl-windows.zip` and unzip it anywhere. It contains a `yummy-dl` folder:

- double-click **`yummy-dl-gui.exe`** for the desktop app, or
- double-click `yummy-dl.exe` for guided terminal mode, or run it from a terminal with the commands below.

Keep the `_internal` folder next to `yummy-dl-gui.exe`, since the app loads its libraries from there. ffmpeg is
included.

**From source** (Windows/Linux, Python 3.11+):

```bash
git clone <this repo> && cd yummy
python -m venv .venv
# activate it: .venv\Scripts\activate (Windows) or source .venv/bin/activate (Linux)

pip install -e '.[gui]'   # desktop app + CLI (in Windows cmd.exe write ".[gui]" with double quotes)
pip install -e .          # CLI only, no Qt
```

Then run `yummy-dl-gui` for the desktop app, or `yummy-dl --help` for the CLI. To build standalone executables
instead, see [Building](#building).

On Linux the desktop app needs Qt's system libraries. Most desktop installs already have them; otherwise, on
Debian/Ubuntu run `sudo apt install libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libegl1`.

**ffmpeg** (recommended) turns Kodik downloads into `.mp4`. Without it, those are saved as `.ts`, which most
players handle fine. Aksor downloads need it to merge video and audio. CVH downloads are already MP4.

- Windows: `winget install ffmpeg` (or put `ffmpeg.exe` next to `yummy-dl.exe`)
- Linux: `sudo apt install ffmpeg` / `sudo pacman -S ffmpeg`
- Or point to it explicitly: `YUMMY_FFMPEG=C:\path\to\ffmpeg.exe`

## Getting an API token

The API currently answers without a token, but its docs say one is required, so set it up:

1. Register or log in at <https://yummyani.me>.
2. Open <https://yummyani.me/dev/applications> and create a new application (a name and description are enough).
3. Copy the application's **public token**.
4. Save it: `yummy-dl config set-token <TOKEN>`. Alternatively, set the env var `YUMMY_APP_TOKEN`.

The token is sent as the `X-Application` header.

## Desktop app

`yummy-dl-gui` (or `yummy-dl gui`) opens a window:

1. Search for a title and pick it from the list. Posters show next to the results and in the details panel. Click the poster to view it full screen.
2. Choose the dub, the player (Auto prefers CVH), the max quality, and the folder.
3. Tick episodes. Ones you already downloaded are marked ✓ and left unticked.
4. Click **Download selected**. The queue shows progress per episode. Cancel keeps partial files, so
   re-adding the episode resumes it. Double-click a finished row to open its folder.

**Settings → Dark theme** switches the look and is remembered; until you set it, the app follows the system. The API token is under **Settings → API token…**.

## Usage

```bash
yummy-dl search "берсерк"                 # find titles
yummy-dl info berserk                     # dubs, episodes, players for a title (id/alias/text)
yummy-dl download berserk                 # interactive: pick dub + episodes
yummy-dl interactive                      # guided loop (also what double-clicking the .exe does)
yummy-dl download berserk -d "MC Entertainment" -e 1-5,8 -q 720 -o D:\Anime
yummy-dl config show                      # settings, config path, ffmpeg status
yummy-dl config set --output-dir D:\Anime --quality 1080
```

- Files go to `<out>/<Title>/<Title> - E01 [Dub].mp4`. The default output folder is `Downloads/yummy-dl`.
- Interrupted downloads resume: rerun the same command. Episodes that already finished are skipped.

## Supported players

Each video on YummyAnime is an embedded third-party player, and each one needs its own extractor.

| Player | Status | Notes |
|---|---|---|
| CVH (cdnvideohub) | ✅ | Direct MP4 up to 1080p, parallel chunked download; no ffmpeg needed |
| Kodik | ✅ | HLS up to 720p; ffmpeg needed for .mp4 |
| Aksor | ✅ | DASH (separate video/audio tracks), up to 1080p+; **ffmpeg required** to merge them |
| Alloha | ❌ | Not supported: its player is protected by an anti-bot challenge (obfuscated proof-of-work + captcha) |

In a sample of the 30 most popular titles, CVH/Kodik/Aksor cover about 94% of dubs. About 5% are only on Alloha.

When a dub is on several players, the order of preference is CVH, then Kodik, then Aksor. Use `--player kodik` or
`--player aksor` to override.

`info` greys out dubs that are only on unsupported players and says why.

## Development

```bash
uv venv && uv pip install -e '.[dev]'
pytest              # offline unit tests
pytest -m live      # hits the real API/players
```

## Building

The build uses PyInstaller and produces two programs:

| Program | What it is | How it's built |
|---|---|---|
| `yummy-dl-gui` | Desktop app (PySide6/Qt), opens without a console window | One-folder build from `packaging/yummy-dl-gui.spec`: the exe plus an `_internal/` folder that must stay next to it |
| `yummy-dl` | Command-line tool | Single file, no Qt inside |

The GUI is a one-folder build on purpose. A single-file Qt exe unpacks about 100 MB to a temp folder on every
launch, and antivirus rescans it each time, which made startup take 10+ seconds. Now it opens in about 1 second.

### Windows, step by step

You only need Python. The build script installs everything else (PySide6, PyInstaller, ...) into its own
virtualenv, so it doesn't touch your system Python.

**1. Install Python 3.11 or newer.**
Download it from <https://www.python.org/downloads/>. On the installer's first screen, tick
**"Add python.exe to PATH"**. The Microsoft Store version of Python also works.

Open **PowerShell** (Start menu → type `powershell`) and check:

```powershell
python --version        # should print Python 3.11 or newer
```

**2. (Optional) Install ffmpeg** so it gets bundled into the release. Kodik downloads need it to produce `.mp4`, and
Aksor downloads need it at all:

```powershell
winget install ffmpeg
```

Close and reopen PowerShell afterwards so `ffmpeg` is on PATH.

**3. Put the project on a Windows drive**, for example `C:\src\yummy`. Pick whichever applies:

- with Git: `git clone <repo-url> C:\src\yummy`
- the repo lives in WSL: run this inside WSL: `git clone ~/path/to/yummy /mnt/c/src/yummy`
- no Git: copy the project folder to `C:\src\yummy`

Building straight from a `\\wsl.localhost\...` path is untested, and much slower. Use a Windows drive.

**4. Build.** In PowerShell:

```powershell
cd C:\src\yummy
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -BundleFfmpeg
```

Leave out `-BundleFfmpeg` if you skipped step 2. The first build takes about 4–5 minutes, because it downloads
PySide6 and PyInstaller. Later builds reuse `.venv-win` and are faster. It's done when it prints
`Built ...\dist\yummy-dl and dist\yummy-dl-windows.zip`.

**5. Run it.** Open `dist\yummy-dl\` and double-click **`yummy-dl-gui.exe`**. To share it or move it to another PC,
use `dist\yummy-dl-windows.zip`.

The script creates its own virtualenv (`.venv-win`), installs dependencies, builds both programs and checks that
the CLI runs. The result:

```
dist\yummy-dl\
  yummy-dl-gui.exe      <- the desktop app (double-click this)
  _internal\           <- its libraries; keep next to the exe
  yummy-dl.exe          <- the CLI
  ffmpeg.exe            <- with -BundleFfmpeg
  README.md
dist\yummy-dl-windows.zip  <- the same folder zipped, ready to share
```

To build **only the GUI** (from an environment with `pip install ".[gui]" pyinstaller`):

```powershell
pyinstaller --noconfirm packaging\yummy-dl-gui.spec   # -> dist\yummy-dl\yummy-dl-gui.exe
```

**If something goes wrong:**

| Message / symptom | Fix |
|---|---|
| `python is not recognized…`, or typing `python` opens the Microsoft Store | Python isn't on PATH. Re-run the installer, choose *Modify*, and tick *Add Python to environment variables*. Or pass the full path: `... build_windows.ps1 -Python C:\path\to\python.exe` |
| `running scripts is disabled on this system` | You ran `.\scripts\build_windows.ps1` directly. Use the `powershell -ExecutionPolicy Bypass -File ...` command from step 4 |
| `ffmpeg.exe not on PATH; pass -FfmpegPath` | Reopen PowerShell after `winget install ffmpeg`, or pass `-FfmpegPath C:\path\to\ffmpeg.exe`, or drop `-BundleFfmpeg` |
| Antivirus deletes or blocks the built exe | PyInstaller apps sometimes trigger false positives. Allow the file, or add an exclusion for the `dist` folder |
| Explorer still shows an old icon after a rebuild | That's Windows' icon cache. Run `ie4uinit.exe -show`, or unzip the release into a new folder |
| Weird errors after updating the code | Do a clean build: delete `.venv-win`, `build` and `dist`, then run step 4 again |

### Linux

```bash
python -m venv .venv && source .venv/bin/activate
pip install '.[gui]' pyinstaller
pyinstaller --noconfirm packaging/yummy-dl-gui.spec              # -> dist/yummy-dl/yummy-dl-gui
pyinstaller --noconfirm --onefile --name yummy-dl src/yummy_dl/__main__.py   # optional CLI binary
```

The Linux GUI build needs the Qt system libraries listed under [Install](#install), on both the build machine and
the machine that runs it. On Linux it's usually simpler to skip building and just `pip install -e '.[gui]'`.

### CI

`.github/workflows/build.yml` builds the Windows zip for `v*` tags or a manual run, once the repo is on GitHub.
