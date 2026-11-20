import json
import shutil
import subprocess
from pathlib import Path

import pytest

from yummy_dl import core, scripts
from yummy_dl.scripts import EXAMPLES, Script, ScriptError

FFMPEG = shutil.which("ffmpeg")
needs_ffmpeg = pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")


def example(name_part: str) -> Script:
    return next(s for s in EXAMPLES if name_part in s.name)


def test_build_args_keeps_paths_whole():
    src = Path("/videos/Монолог фармацевта/Монолог фармацевта - E01 [MC Entertainment].mp4")
    s = Script("x", "ffmpeg -i {input}\n -c copy -f segment -segment_time 600 {outdir}/{name}_%02d.{ext}")
    args = scripts.build_args(s, src, Path("/out dir"))
    assert args[0] == "-i" and args[1] == str(src)
    assert args[-1] == "/out dir/Монолог фармацевта - E01 [MC Entertainment]_%02d.mp4"
    assert "ffmpeg" not in args


def test_build_args_quoted_filter_and_braces():
    s = Script("x", "-i {input} -vf \"drawtext=text='{name}':x=10\" {outdir}/{name}.mkv")
    args = scripts.build_args(s, Path("/a/ep 1.mp4"), Path("/o"))
    assert args[2:4] == ["-vf", "drawtext=text='ep 1':x=10"]


def test_validate():
    assert scripts.validate(EXAMPLES[0]) == []
    assert len(scripts.validate(Script("", "-c copy out.mkv"))) == 3
    assert any("parse" in p for p in scripts.validate(Script("x", "-i {input} \"{outdir}/a.mkv")))


def test_storage_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(scripts.cfgmod, "config_path", lambda: tmp_path / "config.toml")
    assert scripts.load_scripts() == []
    saved = [Script("Сжать", "-i {input} {outdir}/{name}.mkv", comment="коммент", auto=True)]
    scripts.save_scripts(saved)
    assert "Сжать" in (tmp_path / "scripts.json").read_text(encoding="utf-8")
    assert scripts.load_scripts() == saved
    data = json.loads((tmp_path / "scripts.json").read_text(encoding="utf-8"))
    data[0]["future_field"] = 1  # unknown keys from newer versions are ignored
    (tmp_path / "scripts.json").write_text(json.dumps(data), encoding="utf-8")
    assert scripts.load_scripts()[0].name == "Сжать"
    assert scripts.auto_script(saved) is saved[0]
    assert scripts.find_script(saved, "сжать") is saved[0]
    with pytest.raises(ScriptError):
        scripts.find_script(saved, "nope")


def test_collect_inputs(tmp_path):
    (tmp_path / "Show").mkdir()
    (tmp_path / "Show" / "a.mp4").write_bytes(b"x")
    (tmp_path / "Show" / "b.mkv").write_bytes(b"x")
    (tmp_path / "Show" / "notes.txt").write_bytes(b"x")
    (tmp_path / "Show" / "c.mp4").write_bytes(b"x")
    (tmp_path / "Show" / "c.mp4.parts").mkdir()  # unfinished download
    (tmp_path / "Show" / ".yummy-tmp-a").mkdir()
    (tmp_path / "Show" / ".yummy-tmp-a" / "a.mkv").write_bytes(b"x")
    (tmp_path / "top.ts").write_bytes(b"x")
    got = scripts.collect_inputs([tmp_path])
    assert [p.name for p in got] == ["a.mp4", "b.mkv", "top.ts"]
    assert scripts.collect_inputs([tmp_path / "Show" / "notes.txt"]) == [tmp_path / "Show" / "notes.txt"]


def test_existing_download_finds_converted(tmp_path):
    folder = tmp_path / "Show"
    folder.mkdir()
    target = folder / "Show - E01 [Dub].mp4"
    assert core.existing_download(target) is None
    (folder / "Show - E010 [Dub].mkv").write_bytes(b"x")  # different episode
    (folder / "Show - E01 [Dub].mkv.part").write_bytes(b"x")  # not a video extension
    assert core.existing_download(target) is None
    (folder / "Show - E01 [Dub]_00.mkv").write_bytes(b"x")
    assert core.existing_download(target) == folder / "Show - E01 [Dub]_00.mkv"
    (folder / "Show - E01 [Dub].mp4.parts").mkdir()  # unfinished download wins
    assert core.existing_download(target) is None


def test_existing_download_finds_parts_folder(tmp_path):
    target = tmp_path / "Show - E02 [Dub].mp4"
    (tmp_path / "Show - E02 [Dub]").mkdir()
    assert core.existing_download(target) is None  # empty folder doesn't count
    (tmp_path / "Show - E02 [Dub]" / "Show - E02 [Dub]_00.mkv").write_bytes(b"x")
    assert core.existing_download(target) == tmp_path / "Show - E02 [Dub]"


def make_clip(path: Path, seconds: int = 3) -> None:
    subprocess.run([FFMPEG, "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=size=320x240:rate=10:duration={seconds}",
                    "-f", "lavfi", "-i", f"sine=duration={seconds}", "-c:v", "libx264", "-g", "10", "-c:a", "aac",
                    "-shortest", str(path)], check=True)


@needs_ffmpeg
def test_run_remux_replaces_original(tmp_path, monkeypatch):
    monkeypatch.setenv("YUMMY_FFMPEG", FFMPEG)
    src = tmp_path / "Шоу - E01 [Дуб].mp4"
    make_clip(src)
    seen = []
    out = scripts.run_script(example("Remux"), src, progress=lambda d, t: seen.append((d, t)))
    assert out == [tmp_path / "Шоу - E01 [Дуб].mkv"]
    assert out[0].stat().st_size > 0 and not src.exists()
    assert [p.name for p in tmp_path.iterdir()] == [out[0].name]  # work dir removed
    assert seen and seen[-1][0] == seen[-1][1]


@needs_ffmpeg
def test_run_same_name_output(tmp_path, monkeypatch):
    monkeypatch.setenv("YUMMY_FFMPEG", FFMPEG)
    src = tmp_path / "ep.mp4"
    make_clip(src)
    out = scripts.run_script(Script("same", "-i {input} -c copy {outdir}/{name}.{ext}"), src)
    assert out == [src] and src.stat().st_size > 0


@needs_ffmpeg
def test_run_segments_into_own_folder(tmp_path, monkeypatch):
    monkeypatch.setenv("YUMMY_FFMPEG", FFMPEG)
    src = tmp_path / "long video.mp4"
    make_clip(src, seconds=6)
    s = Script("cut", "-i {input} -c copy -f segment -segment_time 2 -reset_timestamps 1 {outdir}/{name}_%02d.mkv",
               own_folder=True)
    out = scripts.run_script(s, src)
    assert out == [tmp_path / "long video"]
    parts = sorted(p.name for p in out[0].iterdir())
    assert len(parts) >= 2 and parts[0] == "long video_00.mkv"
    assert not src.exists()


@needs_ffmpeg
def test_failure_keeps_original(tmp_path, monkeypatch):
    monkeypatch.setenv("YUMMY_FFMPEG", FFMPEG)
    src = tmp_path / "ep.mp4"
    make_clip(src)
    with pytest.raises(ScriptError, match="ffmpeg exited"):
        scripts.run_script(Script("bad", "-i {input} -c:v no_such_codec {outdir}/{name}.mkv"), src)
    assert src.exists() and [p.name for p in tmp_path.iterdir()] == ["ep.mp4"]


@needs_ffmpeg
def test_cancel_keeps_original(tmp_path, monkeypatch):
    monkeypatch.setenv("YUMMY_FFMPEG", FFMPEG)
    src = tmp_path / "ep.mp4"
    make_clip(src, seconds=5)

    def cancel(_d, _t):
        raise core.Cancelled()

    with pytest.raises(core.Cancelled):
        scripts.run_script(example("720p"), src, progress=cancel)
    assert src.exists() and [p.name for p in tmp_path.iterdir()] == ["ep.mp4"]
