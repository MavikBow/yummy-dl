import base64
import json
from pathlib import Path

import pytest

from yummy_dl import core, hls
from yummy_dl.extractors import kodik
from yummy_dl.extractors.base import ExtractError
from yummy_dl.models import Anime, Stream, Video
from yummy_dl.naming import episode_filename, episode_label, sanitize

FIX = Path(__file__).parent / "fixtures"


def load_videos() -> list[Video]:
    return [Video.from_api(v) for v in json.loads((FIX / "videos.json").read_text("utf-8"))["response"]]


# --- Kodik ---------------------------------------------------------------

def test_kodik_parse_page():
    params, vinfo = kodik.parse_page((FIX / "kodik_page.html").read_text("utf-8"))
    assert params["d"] == "ru.yummyani.me"
    assert vinfo == {"type": "video", "hash": "0b7467864b8e540b92abdfae09cb26d4", "id": "98535"}
    form = kodik.build_form(params, vinfo)
    assert form["ref"] == "https://ru.yummyani.me/"  # must be sent decoded
    assert form["id"] == "98535"


def test_kodik_parse_page_missing():
    with pytest.raises(ExtractError):
        kodik.parse_page("<html>removed</html>")


def test_kodik_decode_real_response():
    links = kodik.parse_links(json.loads((FIX / "kodik_ftor.json").read_text("utf-8")))
    assert set(links) == {360, 480, 720}
    for q, url in links.items():
        assert url.startswith("https://") and url.endswith(f"{q}.mp4:hls:manifest.m3u8")


@pytest.mark.parametrize("shift", [0, 5, 13, 25])
def test_kodik_decode_any_shift(shift):
    url = "//cdn.example.com/s/720.mp4:hls:manifest.m3u8"
    encoded = base64.b64encode(url.encode()).decode().rstrip("=")
    assert kodik.decode_src(kodik._shift(encoded, shift)) == "https:" + url


# --- models / selection ----------------------------------------------------

def test_stream_pick():
    s = Stream({360: "a", 480: "b", 720: "c"})
    assert s.pick(1080) == (720, "c")
    assert s.pick(500) == (480, "b")
    assert s.pick(240) == (360, "a")


def test_group_and_pick():
    videos = load_videos()
    assert all(v.iframe_url.startswith("https://") for v in videos)
    options = core.group_by_dub(videos)
    assert options[0].supported  # supported dubs sort first
    mc = core.find_dub(options, "mc entertainment")
    assert mc is not None and mc.dub_name == "MC Entertainment"
    picks = core.pick_videos(mc, ["1", "2"])
    assert set(picks) <= {"1", "2"}
    assert all(v.player_name == "Kodik" for v in picks.values())


@pytest.mark.parametrize(
    "spec,expected",
    [
        (None, ["1", "2", "3", "4", "5", "12.5"]),
        ("all", ["1", "2", "3", "4", "5", "12.5"]),
        ("2-4", ["2", "3", "4"]),
        ("1,5", ["1", "5"]),
        ("4-", ["4", "5", "12.5"]),
        ("12.5", ["12.5"]),
        ("01", ["1"]),
    ],
)
def test_parse_episodes(spec, expected):
    assert core.parse_episodes(spec, ["1", "2", "3", "4", "5", "12.5"]) == expected


def test_parse_episodes_errors():
    with pytest.raises(ValueError):
        core.parse_episodes("9", ["1", "2"])
    with pytest.raises(ValueError):
        core.parse_episodes("a-b", ["1"])


# --- naming ----------------------------------------------------------------

def test_sanitize_windows():
    assert sanitize('Re:Zero / "Start" <2>?') == "Re Zero Start 2"
    assert sanitize("CON") == "_CON"
    assert sanitize("name. ") == "name"
    assert sanitize("") == "_"


def test_episode_names():
    assert episode_label("1") == "E01"
    assert episode_label("12.5") == "E12.5"
    assert episode_filename("Берсерк: 1997", "3", "Сербин") == "Берсерк 1997 - E03 [Сербин].mp4"


def test_episode_path(tmp_path):
    a = Anime(1, "x", "Title?")
    v = load_videos()[0]
    p = core.episode_path(a, v, tmp_path)
    assert p.parent == tmp_path / "Title"


# --- HLS -------------------------------------------------------------------

MASTER = """#EXTM3U
#EXT-X-STREAM-INF:BANDWIDTH=800000,RESOLUTION=640x360,CODECS="avc1.4d401e,mp4a.40.2"
360/index.m3u8
#EXT-X-STREAM-INF:BANDWIDTH=2500000,RESOLUTION=1280x720
720/index.m3u8
"""

MEDIA = """#EXTM3U
#EXT-X-TARGETDURATION:6
#EXTINF:6.000,
./720.mp4:hls:seg-1-v1-a1.ts
#EXTINF:6.000,
https://other.cdn/seg2.ts
#EXT-X-ENDLIST
"""


def test_parse_master():
    variants, segs = hls.parse_playlist(MASTER, "https://h/a/master.m3u8")
    assert not segs
    assert [(v.height, v.bandwidth) for v in variants] == [(360, 800000), (720, 2500000)]
    assert variants[1].url == "https://h/a/720/index.m3u8"


def test_parse_media():
    variants, segs = hls.parse_playlist(MEDIA, "https://h/s/720.mp4:hls:manifest.m3u8")
    assert not variants
    assert segs == ["https://h/s/720.mp4:hls:seg-1-v1-a1.ts", "https://other.cdn/seg2.ts"]


def test_parse_encrypted_rejected():
    with pytest.raises(hls.HlsError):
        hls.parse_playlist('#EXTM3U\n#EXT-X-KEY:METHOD=AES-128,URI="k"\nseg.ts\n', "https://h/")


def test_download_resume(tmp_path, monkeypatch):
    import httpx

    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        if request.url.path.endswith(".m3u8"):
            body = "#EXTM3U\n" + "".join(f"#EXTINF:1,\nseg{i}.ts\n" for i in range(3))
            return httpx.Response(200, text=body)
        return httpx.Response(200, content=request.url.path.encode())

    monkeypatch.setattr(hls, "find_ffmpeg", lambda: None)
    dest = tmp_path / "out" / "ep.mp4"
    parts = dest.with_name(dest.name + ".parts")
    parts.mkdir(parents=True)
    (parts / "00000.ts").write_bytes(b"/cached")  # simulate an earlier partial run

    seen = []
    with httpx.Client(transport=httpx.MockTransport(handler)) as http:
        result = hls.download("https://h/p/index.m3u8", dest, http=http, workers=2,
                              progress=lambda d, t: seen.append((d, t)))
    assert result == dest.with_suffix(".ts")
    assert result.read_bytes() == b"/cached/p/seg1.ts/p/seg2.ts"
    assert "/p/seg0.ts" not in calls
    assert not parts.exists()
    assert seen[0] == (1, 3) and seen[-1] == (3, 3)
