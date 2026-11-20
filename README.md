# yummy-dl

Command-line downloader for Russian-dubbed anime from [YummyAnime](https://yummyani.me), built on the
official API ([swagger](https://api.yani.tv/swagger)). Runs on Windows and Linux.

> The YummyAnime API is **for personal use only**. Don't redistribute downloaded content.

## Install

**Windows:** download `yummy-dl-windows.zip` and unzip it anywhere. Then:

- double-click **`yummy-dl-gui.exe`** for the desktop app, or
- double-click `yummy-dl.exe` for guided terminal mode, or run it from a terminal with the commands below.

ffmpeg is included in the zip.

**From source** (Windows/Linux, Python 3.11+):

```bash
pip install -e .          # or: uv pip install -e .
```

**ffmpeg** (recommended) turns Kodik downloads into `.mp4`. Without it, those are saved as `.ts`, which most
players handle fine. CVH downloads are already MP4.

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

1. Search for a title and pick it from the list.
2. Choose the dub, the player (Auto prefers CVH), the max quality, and the folder.
3. Tick episodes. Ones you already downloaded are marked ✓ and left unticked.
4. Click **Download selected**. The queue shows progress per episode. Cancel keeps partial files, so
   re-adding the episode resumes it. Double-click a finished row to open its folder.

The API token is under **Settings → API token…**. From source, the app needs `pip install -e '.[gui]'`.

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
| Aksor, Alloha | maybe later | |

When a dub is on several players, CVH is used by default. Use `--player kodik` to override.

`info` greys out dubs and players that aren't supported yet.

## Development

```bash
uv venv && uv pip install -e '.[dev]'
pytest              # offline unit tests
pytest -m live      # hits the real API/players
```

### Building the Windows exe

On Windows (Python 3.11+ on PATH):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1                # dist\yummy-dl.exe
powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1 -BundleFfmpeg  # + dist\yummy-dl-windows.zip
```

CI (`.github/workflows/build.yml`) builds the zip for `v*` tags or a manual run, once the repo is on GitHub.
Linux users can just `pip install .`. A PyInstaller binary can be built the same way with `pyinstaller --onefile`.
