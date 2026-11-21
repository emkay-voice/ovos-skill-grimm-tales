"""Stories from Wikisource: in a browser (Emkay), where grimmstories.com
can't be read, and on a device when the site can't be reached - and the
source each story names."""
import json
import time
from unittest.mock import MagicMock

from conftest import FakeWikisource, StoryFetchError, skill_module

WS_URL = "https://en.wikisource.org/wiki/Grimm%27s_Household_Tales%2C_Volume_1/Cinderella"


def make_message(data=None):
    m = MagicMock()
    m.data = data or {}
    m.context = {}
    m.reply = MagicMock(side_effect=lambda mtype, d: MagicMock(msg_type=mtype, data=d))
    return m


def site_down(lang=None):
    raise StoryFetchError("site down")


def test_device_tries_the_site_first_then_wikisource(monkeypatch):
    monkeypatch.setattr(skill_module, "IN_BROWSER", False)
    assert skill_module.GrimmTales._sources("de") == ["site", "wikisource"]
    assert skill_module.GrimmTales._sources("da") == ["site"]  # no Danish Grimm on Wikisource


def test_browser_only_uses_wikisource(monkeypatch):
    monkeypatch.setattr(skill_module, "IN_BROWSER", True)
    assert skill_module.GrimmTales._sources("de") == ["wikisource"]
    assert skill_module.GrimmTales._sources("da") == []


def test_index_falls_back_to_wikisource_when_the_site_is_unreachable(skill):
    skill.update_index = site_down
    skill.__dict__["_wikisource"] = FakeWikisource({"en": {"Cinderella": WS_URL}})

    skill.refresh_index()

    assert skill.index == {"Cinderella": WS_URL}
    cached = json.loads((skill.file_system.base / "index_wikisource_en.json").read_text())
    assert cached["index"] == {"Cinderella": WS_URL}


def test_browser_never_asks_the_site(skill, monkeypatch):
    monkeypatch.setattr(skill_module, "IN_BROWSER", True)
    skill.update_index = lambda lang=None: (_ for _ in ()).throw(AssertionError("a browser may not read the site"))
    skill.__dict__["_wikisource"] = FakeWikisource({"en": {"Cinderella": WS_URL}})

    skill.refresh_index()

    assert skill.index == {"Cinderella": WS_URL}


def test_fresh_wikisource_cache_is_used_without_asking(skill, monkeypatch):
    monkeypatch.setattr(skill_module, "IN_BROWSER", True)
    (skill.file_system.base / "index_wikisource_en.json").write_text(
        json.dumps({"timestamp": time.time(), "index": {"Cached": WS_URL}}))

    skill.refresh_index()

    assert skill.index == {"Cached": WS_URL}
    assert skill.wikisource.calls == []


def test_search_names_wikisource_as_the_source(skill):
    skill.index = {"Cinderella": WS_URL}

    skill.handle_search(make_message({"phrase": "cinderella"}))

    assert skill.bus.emit.call_args[0][0].data["source"] == "Wikisource"


def test_search_names_the_site_for_its_own_stories(skill):
    skill.index = {"Cinderella": "https://www.grimmstories.com/en/grimm_fairy-tales/cinderella"}

    skill.handle_search(make_message({"phrase": "cinderella"}))

    assert skill.bus.emit.call_args[0][0].data["source"] == "grimmstories.com"


def test_fetch_reads_the_story_from_wikisource(skill):
    skill.index = {"Cinderella": WS_URL}
    skill.__dict__["_wikisource"] = FakeWikisource(stories={WS_URL: ["It was so beautiful.", "The end."]})

    skill.handle_fetch_content(make_message({"content_id": "Cinderella"}))

    data = skill.bus.emit.call_args[0][0].data
    assert data["paragraphs"] == ["It was so beautiful.", "The end."]


def test_fetch_answers_empty_when_wikisource_fails(skill):
    skill.index = {"Cinderella": WS_URL}

    skill.handle_fetch_content(make_message({"content_id": "Cinderella"}))

    assert skill.bus.emit.call_args[0][0].data["paragraphs"] == []
