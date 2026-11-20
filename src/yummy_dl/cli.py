"""Command-line interface: `yummy-dl search | info | download | config | scripts`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from . import config as cfgmod
from . import core, dash, direct, hls, i18n
from . import scripts as scriptmod
from .api import ApiError, YummyClient
from .extractors import ExtractError, is_supported
from .i18n import _, ngettext
from .models import Anime


def _init_language() -> None:
    """Runs at import: Typer evaluates help texts when the commands below are declared."""
    try:
        setting = cfgmod.load().language
    except (OSError, ValueError):
        setting = ""
    i18n.set_language(i18n.resolve(setting))
    try:  # section titles of the rich --help output
        from typer import rich_utils

        rich_utils.ARGUMENTS_PANEL_TITLE = _("Arguments")
        rich_utils.OPTIONS_PANEL_TITLE = _("Options")
        rich_utils.COMMANDS_PANEL_TITLE = _("Commands")
        rich_utils.REQUIRED_LONG_STRING = _("[required]")
    except (ImportError, AttributeError):
        pass


_init_language()

app = typer.Typer(help=_("Download Russian-dubbed anime from YummyAnime. Personal use only."),
                  no_args_is_help=True, add_completion=False)
config_app = typer.Typer(help=_("Manage settings (API token, defaults, language)."), no_args_is_help=True)
app.add_typer(config_app, name="config")
scripts_app = typer.Typer(help=_("Run saved ffmpeg scripts on downloaded episodes (edit them in the GUI)."),
                          no_args_is_help=True)
app.add_typer(scripts_app, name="scripts")
console = Console()


def _client() -> YummyClient:
    return YummyClient(token=cfgmod.load().effective_token)


def _fail(msg: str) -> None:
    console.print(f"[red]{_('Error:')}[/red] {msg}")
    raise typer.Exit(1)


def _resolve_anime(api: YummyClient, query: str) -> Anime:
    """Accept an id, an alias (anime_url), or free text (search and let the user choose)."""
    try:
        return api.get_anime(query)
    except ApiError:
        pass
    results = api.search(query, limit=10)
    if not results:
        _fail(_("nothing found for '{query}'", query=query))
    if len(results) == 1:
        return api.get_anime(results[0].anime_id)
    _print_search(results)
    choice = IntPrompt.ask(_("Pick a title #"), choices=[str(i) for i in range(1, len(results) + 1)])
    return api.get_anime(results[choice - 1].anime_id)


def _print_search(results: list[Anime]) -> None:
    t = Table(show_lines=False)
    for col in ("#", "ID", _("Alias"), _("Title"), _("Year"), _("Type"), _("Status")):
        t.add_column(col)
    for i, a in enumerate(results, 1):
        t.add_row(str(i), str(a.anime_id), a.url, a.title, str(a.year or ""), a.type, a.status)
    console.print(t)


def _ep_range(eps: list[str]) -> str:
    if not eps:
        return "-"
    return eps[0] if len(eps) == 1 else f"{eps[0]}–{eps[-1]} ({len(eps)})"


def _print_dubs(options: list[core.DubOption]) -> None:
    t = Table()
    for col in ("#", _("Dub"), _("Episodes"), _("Players")):
        t.add_column(col)
    for i, o in enumerate(options, 1):
        players = ", ".join(
            name if any(is_supported(v) for v in vids) else f"[dim]{name}[/dim]"
            for name, vids in sorted(o.by_player.items())
        )
        style = None if o.supported else "dim"
        t.add_row(str(i), o.dub_name, _ep_range(o.supported_episodes or o.episodes), players, style=style)
    console.print(t)
    if note := core.unsupported_note(options):
        console.print("[dim]" + _("Greyed out: {note}.", note=note) + "[/dim]")


@app.command(help=_("Search titles by name."))
def search(query: str, limit: Annotated[int, typer.Option("--limit", "-n", help=_("How many results"))] = 10) -> None:
    with _client() as api:
        try:
            results = api.search(query, limit=limit)
        except ApiError as e:
            _fail(str(e))
    if not results:
        console.print(_("Nothing found."))
        return
    _print_search(results)


@app.command(help=_("Show available dubs and episodes for a title."))
def info(anime: Annotated[str, typer.Argument(help=_("ID, alias, or search text"))]) -> None:
    with _client() as api:
        try:
            a = _resolve_anime(api, anime)
            videos = api.get_videos(a.anime_id)
        except ApiError as e:
            _fail(str(e))
    console.print(f"[bold]{a.title}[/bold] ({a.year}, {a.type}) — id {a.anime_id}, "
                  + _("alias") + f" [cyan]{a.url}[/cyan]")
    if not videos:
        console.print(_("No videos."))
        return
    _print_dubs(core.group_by_dub(videos))


@app.command(help=_("Download episodes. Missing options are asked interactively."))
def download(
    anime: Annotated[str, typer.Argument(help=_("ID, alias, or search text"))],
    dub: Annotated[Optional[str], typer.Option("--dub", "-d", help=_("Dub name, e.g. 'AniLibria'"))] = None,
    episodes: Annotated[Optional[str], typer.Option("--episodes", "-e", help=_("e.g. 1-5,8 or all"))] = None,
    quality: Annotated[Optional[int], typer.Option("--quality", "-q", help=_("Max height: 360/480/720/1080"))] = None,
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help=_("Output directory"))] = None,
    player: Annotated[Optional[str], typer.Option("--player", "-p", help=_("Preferred player, e.g. kodik"))] = None,
    workers: Annotated[Optional[int], typer.Option("--workers", "-w", help=_("Parallel segment downloads"))] = None,
    script: Annotated[Optional[str], typer.Option(
        "--script", "-s", help=_("Run this saved script on each new episode (default: the auto-run script)"))] = None,
    no_script: Annotated[bool, typer.Option("--no-script", help=_("Don't run the auto-run script"))] = False,
) -> None:
    cfg = cfgmod.load()
    post = None if no_script else _pick_script(script)
    out_dir = out or cfg.effective_output_dir
    quality = quality or cfg.quality
    workers = workers or cfg.workers

    with _client() as api:
        try:
            a = _resolve_anime(api, anime)
            videos = api.get_videos(a.anime_id)
        except ApiError as e:
            _fail(str(e))
    options = core.group_by_dub(videos)
    supported = [o for o in options if o.supported]
    if not supported:
        _fail(_("no dubs with a supported player for this title"))

    console.print(f"[bold]{a.title}[/bold] ({a.year}, {a.type})")
    if dub:
        chosen = core.find_dub(options, dub)
        if chosen is None:
            _print_dubs(options)
            _fail(_("dub '{dub}' not found", dub=dub))
        if not chosen.supported:
            _fail(_("dub '{dub}' is only on unsupported players", dub=chosen.dub_name))
    else:
        _print_dubs(supported)
        n = IntPrompt.ask(_("Pick a dub #"), choices=[str(i) for i in range(1, len(supported) + 1)])
        chosen = supported[n - 1]

    available = chosen.supported_episodes
    if episodes is None:
        episodes = Prompt.ask(_("Episodes ({range}), e.g. 1-3,5", range=_ep_range(available)), default="all")
    try:
        wanted = core.parse_episodes(episodes, available)
    except ValueError as e:
        _fail(str(e))
    picks = core.pick_videos(chosen, wanted, player)
    if not picks:
        _fail(_("nothing to download"))

    console.print(_("Dub [cyan]{dub}[/cyan]", dub=chosen.dub_name) + ", "
                  + ngettext("{n} episode", "{n} episodes", len(picks))
                  + ", " + _("up to {quality}p", quality=quality) + f" → {out_dir}")
    if not hls.find_ffmpeg():
        console.print("[yellow]" + _("ffmpeg not found: Kodik episodes will be saved as .ts, Aksor episodes will fail.")
                      + "[/yellow]")
    if post:
        console.print(_("After each episode: script [cyan]{name}[/cyan] (the original is replaced)", name=post.name))

    failed: list[str] = []
    with httpx.Client(timeout=60, follow_redirects=True) as http, Progress(
        TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
        TimeRemainingColumn(), console=console,
    ) as progress:
        for ep, video in picks.items():
            target = core.episode_path(a, video, out_dir)
            if done := core.existing_download(target):
                progress.console.print("[dim]" + _("skip (exists): {name}", name=done.name) + "[/dim]")
                continue
            ep_label = _("Ep {ep}", ep=ep)
            task = progress.add_task(f"{ep_label} [{video.player_name}]", total=None)

            def update(done: int, total: int, task=task) -> None:
                progress.update(task, completed=done, total=total)

            try:
                path, q = core.download_episode(a, video, out_dir, quality=quality, workers=workers,
                                                progress=update, http=http)
                progress.update(task, description=f"{ep_label} ✓ {q}p")
                progress.console.print(f"[green]{_('saved')}[/green] {path}")
            except (ExtractError, hls.HlsError, dash.DashError, direct.DirectError, httpx.HTTPError, OSError) as e:
                failed.append(ep)
                progress.update(task, description=f"{ep_label} ✗")
                progress.console.print("[red]" + _("episode {ep} failed:", ep=ep) + f"[/red] {e}")
                continue
            if post and not _run_one(post, path, progress):
                failed.append(f"{ep} ({_('script')})")
    if failed:
        console.print("[red]" + ngettext("{n} failed:", "{n} failed:", len(failed)) + "[/red] "
                      + ", ".join(failed) + " — " + _("rerun to resume."))
        raise typer.Exit(1)


def _pick_script(name: str | None) -> scriptmod.Script | None:
    try:
        saved = scriptmod.load_scripts()
        return scriptmod.find_script(saved, name) if name else scriptmod.auto_script(saved)
    except scriptmod.ScriptError as e:
        _fail(str(e))


def _run_one(script: scriptmod.Script, src: Path, progress: Progress) -> bool:
    task = progress.add_task(f"⚙ {src.name}", total=None)

    def update(done: int, total: int) -> None:
        progress.update(task, completed=done, total=total)

    try:
        out = scriptmod.run_script(script, src, progress=update)
    except (scriptmod.ScriptError, OSError) as e:
        progress.update(task, description=f"⚙ {src.name} ✗")
        progress.console.print("[red]" + _("script failed") + "[/red] "
                               + _("on {name} (original kept):", name=src.name) + f" {e}")
        return False
    progress.update(task, description=f"⚙ {src.name} ✓")
    for p in out:
        progress.console.print(f"[green]{_('converted')}[/green] {p}")
    return True


@scripts_app.command("list", help=_("Show saved scripts."))
def scripts_list() -> None:
    try:
        saved = scriptmod.load_scripts()
    except scriptmod.ScriptError as e:
        _fail(str(e))
    if not saved:
        console.print(_("No scripts yet. Create them in the desktop app (Scripts → Manage scripts…) or in {path}",
                        path=scriptmod.scripts_path()))
        return
    t = Table(_("Name"), _("Comment"), _("Auto"), _("Command"))
    for sc in saved:
        t.add_row(sc.name, sc.comment, _("yes") if sc.auto else "", " ".join(sc.command.split()))
    console.print(t)
    console.print(f"[dim]{scriptmod.scripts_path()}[/dim]")


@scripts_app.command("run", help=_("Run a saved script on files or folders. Originals are deleted after a successful run."))
def scripts_run(
    name: Annotated[str, typer.Argument(help=_("Script name (or a unique part of it)"))],
    paths: Annotated[list[Path], typer.Argument(help=_("Video files and/or folders of episodes"))],
    yes: Annotated[bool, typer.Option("--yes", "-y", help=_("Don't ask for confirmation"))] = False,
) -> None:
    script = _pick_script(name)
    if not hls.find_ffmpeg():
        _fail(_("ffmpeg not found (Windows: winget install ffmpeg)"))
    inputs = scriptmod.collect_inputs(p.expanduser() for p in paths)
    if not inputs:
        _fail(_("no video files found"))
    console.print(_("Script [cyan]{name}[/cyan]", name=script.name) + " — "
                  + ngettext("{n} file:", "{n} files:", len(inputs)))
    for p in inputs:
        console.print(f"  {p}")
    if not yes and not Confirm.ask(_("Originals are deleted after each successful run. Continue?"), default=True):
        raise typer.Exit(1)
    failed = 0
    with Progress(TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
                  TimeRemainingColumn(), console=console) as progress:
        for src in inputs:
            failed += not _run_one(script, src, progress)
    if failed:
        console.print("[red]" + ngettext("{n} failed", "{n} failed", failed) + "[/red]")
        raise typer.Exit(1)


@config_app.command("set-token", help=_("Save your YummyAnime application token (from yummyani.me/dev/applications)."))
def set_token(token: str) -> None:
    cfg = cfgmod.load()
    cfg.token = token.strip()
    console.print(_("Saved to {path}", path=cfgmod.save(cfg)))


@config_app.command("set", help=_("Change default options."))
def set_option(
    output_dir: Annotated[Optional[Path], typer.Option(help=_("Default download folder"))] = None,
    quality: Annotated[Optional[int], typer.Option(help=_("Default max quality"))] = None,
    workers: Annotated[Optional[int], typer.Option(help=_("Parallel segment downloads"))] = None,
    language: Annotated[Optional[str], typer.Option(help=_("Interface language: auto, en or ru"))] = None,
) -> None:
    cfg = cfgmod.load()
    if language is not None:
        code = language.strip().lower()
        if code not in ("auto", "", *i18n.LANGUAGES):
            _fail(_("unknown language '{lang}' (use auto, en or ru)", lang=language))
        cfg.language = "" if code in ("auto", "") else code
    if output_dir is not None:
        cfg.output_dir = str(output_dir.expanduser().resolve())
    if quality is not None:
        cfg.quality = quality
    if workers is not None:
        cfg.workers = workers
    console.print(_("Saved to {path}", path=cfgmod.save(cfg)))


@config_app.command("show", help=_("Print current settings."))
def show() -> None:
    cfg = cfgmod.load()
    tok = cfg.effective_token
    not_set = "[dim]" + _("not set") + "[/dim]"
    lang = i18n.LANGUAGES.get(cfg.language) or _("system ({lang})", lang=i18n.LANGUAGES[i18n.system_language()])
    console.print(f"config file : {cfgmod.config_path()}")
    console.print(f"token       : {(tok[:4] + '…' + tok[-4:]) if tok and len(tok) > 10 else (tok or not_set)}")
    console.print(f"output_dir  : {cfg.effective_output_dir}")
    console.print(f"quality     : {cfg.quality}")
    console.print(f"workers     : {cfg.workers}")
    console.print(f"language    : {lang}")
    console.print(f"ffmpeg      : {hls.find_ffmpeg() or '[yellow]' + _('not found') + '[/yellow]'}")


@app.command(help=_("Open the desktop window (needs: pip install 'yummy-dl[gui]').").replace("[", "\\["))
def gui() -> None:
    from .gui import main as gui_main

    raise typer.Exit(gui_main())


@app.command(help=_("Guided mode: search, pick a dub and episodes, download. Loops until you leave it empty."))
def interactive() -> None:
    console.print("[bold]yummy-dl[/bold] — " + _("downloads go to {path}", path=cfgmod.load().effective_output_dir))
    console.print("[dim]" + _("Change it with: yummy-dl config set --output-dir <folder>") + "[/dim]")
    while True:
        query = Prompt.ask("\n" + _("Title to search (empty to quit)"), default="", show_default=False).strip()
        if not query:
            return
        try:
            download(anime=query)
        except typer.Exit:
            pass  # error already printed; ask again


def _windows_utf8() -> None:
    """Cyrillic titles crash on cp1252 consoles/pipes: switch the console and std streams to UTF-8."""
    import sys

    if sys.platform != "win32":
        return
    try:
        import ctypes

        ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        ctypes.windll.kernel32.SetConsoleCP(65001)
    except (AttributeError, OSError):
        pass
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main() -> None:
    """Entry point. A bare double-click on the Windows .exe starts guided mode and waits before closing."""
    import sys

    _windows_utf8()
    if len(sys.argv) == 1 and getattr(sys, "frozen", False):
        try:
            interactive()
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            try:
                input("\n" + _("Press Enter to close..."))
            except (KeyboardInterrupt, EOFError):
                pass
        return
    app()


if __name__ == "__main__":
    main()
