"""Live smoke tests against the real API and Kodik. Run with: pytest -m live"""

import pytest

from yummy_dl import core
from yummy_dl.api import YummyClient
from yummy_dl.extractors import find_extractor

pytestmark = pytest.mark.live


def test_search_and_kodik_extract():
    import httpx

    with YummyClient() as api:
        assert any(a.url == "berserk" for a in api.search("берсерк"))
        anime = api.get_anime("berserk")
        videos = api.get_videos(anime.anime_id)
    dub = core.find_dub(core.group_by_dub(videos), "MC Entertainment")
    video = core.pick_videos(dub, ["1"])["1"]
    with httpx.Client(timeout=30, follow_redirects=True) as http:
        stream = find_extractor(video).extract(video, http)
    assert stream.qualities and all(u.startswith("https://") for u in stream.qualities.values())


def test_cvh_extract():
    import httpx

    with YummyClient() as api:
        videos = api.get_videos(api.get_anime("berserk").anime_id)
    dub = core.find_dub(core.group_by_dub(videos), "Юрий Сербин")
    video = core.pick_videos(dub, ["1"], player="cvh")["1"]
    assert video.player_name == "CVH"
    with httpx.Client(timeout=30, follow_redirects=True) as http:
        stream = find_extractor(video).extract(video, http)
    assert stream.kind == "file" and 720 in stream.qualities
