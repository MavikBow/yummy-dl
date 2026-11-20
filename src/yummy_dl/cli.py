"""Command-line interface: `yummy-dl search | info | download | config`."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import httpx
import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TaskProgressColumn, TextColumn, TimeRemainingColumn
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from . import config as cfgmod
from . import core, direct, hls
from .api import ApiError, YummyClient
from .extractors import ExtractError, is_supported
from .models import Anime

app = typer.Typer(help="Download Russian-dubbed anime from YummyAnime. Personal use only.",
                  no_args_is_help=True, add_completion=False)
config_app = typer.Typer(help="Manage settings (API token, defaults).", no_args_is_help=True)
app.add_typer(config_app, name="config")
console = Console()


def _client() -> YummyClient:
    return YummyClient(token=cfgmod.load().effective_token)


def _fail(msg: str) -> None:
    console.print(f"[red]Error:[/red] {msg}")
    raise typer.Exit(1)


def _resolve_anime(api: YummyClient, query: str) -> Anime:
    """Accept an id, an alias (anime_url), or free text (search and let the user choose)."""
    try:
        return api.get_anime(query)
    except ApiError:
        pass
    results = api.search(query, limit=10)
    if not results:
        _fail(f"nothing found for {query!r}")
    if len(results) == 1:
        return api.get_anime(results[0].anime_id)
    _print_search(results)
    choice = IntPrompt.ask("Pick a title #", choices=[str(i) for i in range(1, len(results) + 1)])
    return api.get_anime(results[choice - 1].anime_id)


def _print_search(results: list[Anime]) -> None:
    t = Table(show_lines=False)
    for col in ("#", "ID", "Alias", "Title", "Year", "Type", "Status"):
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
    for col in ("#", "Dub", "Episodes", "Players"):
        t.add_column(col)
    for i, o in enumerate(options, 1):
        players = ", ".join(
            name if any(is_supported(v) for v in vids) else f"[dim]{name}[/dim]"
            for name, vids in sorted(o.by_player.items())
        )
        style = None if o.supported else "dim"
        t.add_row(str(i), o.dub_name, _ep_range(o.supported_episodes or o.episodes), players, style=style)
    console.print(t)
    console.print("[dim]Greyed out = player not supported yet.[/dim]")


@app.command()
def search(query: str, limit: Annotated[int, typer.Option("--limit", "-n")] = 10) -> None:
    """Search titles by name."""
    with _client() as api:
        try:
            results = api.search(query, limit=limit)
        except ApiError as e:
            _fail(str(e))
    if not results:
        console.print("Nothing found.")
        return
    _print_search(results)


@app.command()
def info(anime: Annotated[str, typer.Argument(help="ID, alias, or search text")]) -> None:
    """Show available dubs and episodes for a title."""
    with _client() as api:
        try:
            a = _resolve_anime(api, anime)
            videos = api.get_videos(a.anime_id)
        except ApiError as e:
            _fail(str(e))
    console.print(f"[bold]{a.title}[/bold] ({a.year}, {a.type}) — id {a.anime_id}, alias [cyan]{a.url}[/cyan]")
    if not videos:
        console.print("No videos.")
        return
    _print_dubs(core.group_by_dub(videos))


@app.command()
def download(
    anime: Annotated[str, typer.Argument(help="ID, alias, or search text")],
    dub: Annotated[Optional[str], typer.Option("--dub", "-d", help="Dub name, e.g. 'AniLibria'")] = None,
    episodes: Annotated[Optional[str], typer.Option("--episodes", "-e", help="e.g. 1-5,8 or all")] = None,
    quality: Annotated[Optional[int], typer.Option("--quality", "-q", help="Max height: 360/480/720/1080")] = None,
    out: Annotated[Optional[Path], typer.Option("--out", "-o", help="Output directory")] = None,
    player: Annotated[Optional[str], typer.Option("--player", "-p", help="Preferred player, e.g. kodik")] = None,
    workers: Annotated[Optional[int], typer.Option("--workers", "-w", help="Parallel segment downloads")] = None,
) -> None:
    """Download episodes. Missing options are asked interactively."""
    cfg = cfgmod.load()
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
        _fail("no dubs with a supported player for this title")

    console.print(f"[bold]{a.title}[/bold] ({a.year}, {a.type})")
    if dub:
        chosen = core.find_dub(options, dub)
        if chosen is None:
            _print_dubs(options)
            _fail(f"dub {dub!r} not found")
        if not chosen.supported:
            _fail(f"dub {chosen.dub_name!r} is only on unsupported players")
    else:
        _print_dubs(supported)
        n = IntPrompt.ask("Pick a dub #", choices=[str(i) for i in range(1, len(supported) + 1)])
        chosen = supported[n - 1]

    available = chosen.supported_episodes
    if episodes is None:
        episodes = Prompt.ask(f"Episodes ({_ep_range(available)}), e.g. 1-3,5", default="all")
    try:
        wanted = core.parse_episodes(episodes, available)
    except ValueError as e:
        _fail(str(e))
    picks = core.pick_videos(chosen, wanted, player)
    if not picks:
        _fail("nothing to download")

    console.print(f"Dub [cyan]{chosen.dub_name}[/cyan], {len(picks)} episode(s), up to {quality}p → {out_dir}")
    if not hls.find_ffmpeg():
        console.print("[yellow]ffmpeg not found: Kodik episodes will be saved as .ts instead of .mp4.[/yellow]")

    failed: list[str] = []
    with httpx.Client(timeout=60, follow_redirects=True) as http, Progress(
        TextColumn("[bold]{task.description}"), BarColumn(), TaskProgressColumn(),
        TimeRemainingColumn(), console=console,
    ) as progress:
        for ep, video in picks.items():
            target = core.episode_path(a, video, out_dir)
            if done := core.existing_download(target):
                progress.console.print(f"[dim]skip (exists): {done.name}[/dim]")
                continue
            task = progress.add_task(f"Ep {ep} [{video.player_name}]", total=None)

            def update(done: int, total: int, task=task) -> None:
                progress.update(task, completed=done, total=total)

            try:
                path, q = core.download_episode(a, video, out_dir, quality=quality, workers=workers,
                                                progress=update, http=http)
                progress.update(task, description=f"Ep {ep} ✓ {q}p")
                progress.console.print(f"[green]saved[/green] {path}")
            except (ExtractError, hls.HlsError, direct.DirectError, httpx.HTTPError, OSError) as e:
                failed.append(ep)
                progress.update(task, description=f"Ep {ep} ✗")
                progress.console.print(f"[red]episode {ep} failed:[/red] {e}")
    if failed:
        console.print(f"[red]{len(failed)} failed:[/red] {', '.join(failed)} — rerun to resume.")
        raise typer.Exit(1)


@config_app.command("set-token")
def set_token(token: str) -> None:
    """Save your YummyAnime application token (from yummyani.me/dev/applications)."""
    cfg = cfgmod.load()
    cfg.token = token.strip()
    console.print(f"Saved to {cfgmod.save(cfg)}")


@config_app.command("set")
def set_option(
    output_dir: Annotated[Optional[Path], typer.Option(help="Default download folder")] = None,
    quality: Annotated[Optional[int], typer.Option(help="Default max quality")] = None,
    workers: Annotated[Optional[int], typer.Option(help="Parallel segment downloads")] = None,
) -> None:
    """Change default options."""
    cfg = cfgmod.load()
    if output_dir is not None:
        cfg.output_dir = str(output_dir.expanduser().resolve())
    if quality is not None:
        cfg.quality = quality
    if workers is not None:
        cfg.workers = workers
    console.print(f"Saved to {cfgmod.save(cfg)}")


@config_app.command("show")
def show() -> None:
    """Print current settings."""
    cfg = cfgmod.load()
    tok = cfg.effective_token
    console.print(f"config file : {cfgmod.config_path()}")
    console.print(f"token       : {(tok[:4] + '…' + tok[-4:]) if tok and len(tok) > 10 else (tok or '[dim]not set[/dim]')}")
    console.print(f"output_dir  : {cfg.effective_output_dir}")
    console.print(f"quality     : {cfg.quality}")
    console.print(f"workers     : {cfg.workers}")
    console.print(f"ffmpeg      : {hls.find_ffmpeg() or '[yellow]not found[/yellow]'}")


if __name__ == "__main__":
    app()
