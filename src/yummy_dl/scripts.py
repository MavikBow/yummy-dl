"""User scripts: saved ffmpeg command templates run on downloaded episodes.

A script's command is the ffmpeg argument list with placeholders:
    {input}   full path of the episode file
    {name}    its file name without extension
    {ext}     its extension, without the dot
    {episode} the episode number from a yummy-dl file name ('01', '12.5'); empty for other files
    {outdir}  folder the outputs must be written to

The command is split into arguments first and placeholders are filled in afterwards, so paths with
spaces or Cyrillic letters never need quoting. On success the outputs replace the original file
(the original is deleted); on failure or cancel the original is left untouched.
"""

from __future__ import annotations

import json
import re
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from . import config as cfgmod
from . import hls
from .core import VIDEO_EXTS
from .naming import episode_number

TMP_PREFIX = ".yummy-tmp-"
PLACEHOLDERS = ("{input}", "{name}", "{ext}", "{episode}", "{outdir}")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class ScriptError(Exception):
    pass


@dataclass
class Script:
    name: str
    command: str
    comment: str = ""
    auto: bool = False  # run automatically after each download
    own_folder: bool = False  # put outputs into a folder named after the video


EXAMPLES: list[Script] = [
    Script(
        name="x264/MP3 MKV 720p",
        comment="Re-encode to H.264 + MP3 192k, scaled to 720p. Plays on simple hardware players.",
        command="-i {input} -c:v libx264 -c:a libmp3lame -b:a 192k -vf scale=-2:720\n{outdir}/{name}.mkv",
    ),
    Script(
        name="x264/MP3 MKV 720p, 10-min parts",
        comment="Same conversion, cut into 10-minute pieces inside a folder named after the video.",
        command=("-i {input} -c:v libx264 -c:a libmp3lame -b:a 192k -vf scale=-2:720\n"
                 "-f segment -segment_time 600 -reset_timestamps 1\n{outdir}/{name}_%02d.mkv"),
        own_folder=True,
    ),
    Script(
        name="Remux to MKV (no re-encode)",
        comment="Change the container to MKV without touching video or audio. Takes seconds.",
        command="-i {input} -map 0 -c copy {outdir}/{name}.mkv",
    ),
]


# --- storage ------------------------------------------------------------------------


def scripts_path() -> Path:
    return cfgmod.config_path().parent / "scripts.json"


def load_scripts() -> list[Script]:
    path = scripts_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ScriptError(f"can't read {path}: {e}") from e
    known = {f.name for f in fields(Script)}
    return [Script(**{k: v for k, v in item.items() if k in known}) for item in data if isinstance(item, dict)]


def save_scripts(scripts: list[Script]) -> Path:
    path = scripts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([asdict(s) for s in scripts], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def find_script(scripts: list[Script], name: str) -> Script:
    for s in scripts:
        if s.name == name:
            return s
    low = name.casefold()
    hits = [s for s in scripts if low in s.name.casefold()]
    if len(hits) == 1:
        return hits[0]
    if hits:
        raise ScriptError(f"{name!r} matches several scripts: " + ", ".join(repr(s.name) for s in hits))
    names = ", ".join(repr(s.name) for s in scripts) or "none saved"
    raise ScriptError(f"no script named {name!r} (have: {names})")


def auto_script(scripts: list[Script]) -> Script | None:
    return next((s for s in scripts if s.auto), None)


# --- templates ----------------------------------------------------------------------


def split_command(command: str) -> list[str]:
    try:
        args = shlex.split(command.replace("\r", " ").replace("\n", " "), posix=True)
    except ValueError as e:  # unbalanced quotes
        raise ScriptError(f"can't parse the command: {e}") from e
    if args and Path(args[0]).stem.lower() == "ffmpeg":
        args = args[1:]
    return args


def validate(script: Script) -> list[str]:
    """Problems with a script, as human-readable messages (empty = fine)."""
    problems = []
    if not script.name.strip():
        problems.append("Give the script a name.")
    try:
        args = split_command(script.command)
    except ScriptError as e:
        return [*problems, str(e)]
    joined = " ".join(args)
    if "{input}" not in joined:
        problems.append("The command must read {input}, e.g. -i {input}.")
    if "{outdir}" not in joined:
        problems.append("The command must write into {outdir}, e.g. {outdir}/{name}.mkv.")
    for prev, arg in zip(args, args[1:]):
        if "{outdir}" in prev and not arg.startswith("-") and any(p in arg for p in PLACEHOLDERS):
            problems.append(f'The output path has a space in it, so it was split in two. Wrap it in quotes: '
                            f'"{prev} {arg}".')
            break
    return problems


def build_args(script: Script, src: Path, outdir: Path) -> list[str]:
    episode = episode_number(src.stem)
    values = {"{input}": str(src), "{name}": src.stem, "{ext}": src.suffix.lstrip("."), "{episode}": episode,
              "{outdir}": str(outdir)}
    out = []
    for arg in split_command(script.command):
        if not episode:  # "{episode}. {name}" -> "{name}" for files without an episode number
            arg = re.sub(r"\{episode\}[ ._-]*", "", arg)
        for key, value in values.items():
            arg = arg.replace(key, value)
        out.append(arg)
    return out


# --- inputs ---------------------------------------------------------------------------


def _is_video(p: Path) -> bool:
    return (p.is_file() and p.suffix.lower() in VIDEO_EXTS and ".muxing" not in p.name
            and not p.with_name(p.name + ".parts").exists())


def collect_inputs(paths: Iterable[Path]) -> list[Path]:
    """Files are taken as given; a folder means the videos in it and in its direct subfolders."""
    out: list[Path] = []
    for p in paths:
        if p.is_dir():
            for child in sorted(p.iterdir()):
                if child.name.startswith(TMP_PREFIX) or child.name.endswith(".parts"):
                    continue
                if child.is_dir():
                    out.extend(c for c in sorted(child.iterdir()) if _is_video(c))
                elif _is_video(child):
                    out.append(child)
        elif p.is_file():
            out.append(p)
    seen: set[Path] = set()
    return [p for p in out if not (p in seen or seen.add(p))]


# --- running --------------------------------------------------------------------------

_DURATION = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


def probe_duration_ms(ffmpeg: str, src: Path) -> int:
    proc = subprocess.run([ffmpeg, "-hide_banner", "-nostdin", "-i", str(src)], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", creationflags=_NO_WINDOW)
    m = _DURATION.search(proc.stderr)
    if not m:
        return 0
    h, mi, s = m.groups()
    return int((int(h) * 3600 + int(mi) * 60 + float(s)) * 1000)


def _replace(src: Path, dest: Path) -> None:
    if dest.is_dir():
        shutil.rmtree(dest)
    elif dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))


def run_script(script: Script, src: Path, *, progress: hls.ProgressFn | None = None) -> list[Path]:
    """Run `script` on `src`. Returns the produced paths (files, or the folder with own_folder).

    `progress(done_ms, total_ms)` may raise an exception (core.Cancelled) to stop; ffmpeg is then killed and the
    original is kept.
    """
    ffmpeg = hls.find_ffmpeg()
    if not ffmpeg:
        raise ScriptError("ffmpeg not found. Install it (Windows: winget install ffmpeg) or put ffmpeg.exe next to the app.")
    if not src.is_file():
        raise ScriptError(f"file not found: {src}")
    problems = validate(script)
    if problems:
        raise ScriptError(" ".join(problems))

    folder = src.parent
    work = folder / f"{TMP_PREFIX}{src.stem}"
    if work.exists():
        shutil.rmtree(work)
    outdir = work / src.stem if script.own_folder else work
    outdir.mkdir(parents=True)
    total = probe_duration_ms(ffmpeg, src)
    args = [ffmpeg, "-hide_banner", "-nostdin", "-y", "-progress", "pipe:1", "-nostats",
            *build_args(script, src, outdir)]

    try:
        with tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=err, stdin=subprocess.DEVNULL,
                                    creationflags=_NO_WINDOW)
            try:
                assert proc.stdout is not None
                for raw in proc.stdout:
                    key, _, value = raw.decode("ascii", "replace").strip().partition("=")
                    if key == "out_time_us" and value.isdigit() and progress:
                        progress(min(int(value) // 1000, total or 1), total or 1)
                proc.wait()
            except BaseException:  # Cancelled or anything else: stop ffmpeg
                proc.kill()
                proc.wait()
                raise
            if proc.returncode:
                err.seek(0)
                tail = err.read().decode("utf-8", "replace").strip().splitlines()[-4:]
                raise ScriptError(f"ffmpeg exited with code {proc.returncode}: " + " | ".join(tail))

        produced = list(work.iterdir())
        if script.own_folder and not any(outdir.iterdir()):
            produced = []
        if not produced:
            raise ScriptError("the script finished but wrote nothing into {outdir}")
        if progress:
            progress(total or 1, total or 1)

        src.unlink()  # first: an output may have the same name as the original
        results = []
        for p in produced:
            dest = folder / p.name
            _replace(p, dest)
            results.append(dest)
        return results
    finally:  # on failure/cancel the original was never touched; only the work dir goes
        shutil.rmtree(work, ignore_errors=True)

