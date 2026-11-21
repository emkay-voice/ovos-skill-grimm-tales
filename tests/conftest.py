"""Shared pytest fixtures for the grimm-tales skill test suite."""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parents[1]
# loaded as the package it is installed as, so __init__.py's relative
# import of wikisource.py works without installing it
_spec = importlib.util.spec_from_file_location(
    "ovos_skill_grimm_tales", _ROOT / "__init__.py", submodule_search_locations=[str(_ROOT)])
_module = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _module
_spec.loader.exec_module(_module)

GrimmTales = _module.GrimmTales
StoryFetchError = _module.StoryFetchError
COMMON_READING_SEARCH_RESPONSE = _module.COMMON_READING_SEARCH_RESPONSE
COMMON_READING_FETCH_CONTENT_RESPONSE = _module.COMMON_READING_FETCH_CONTENT_RESPONSE
COMMON_READING_PONG = _module.COMMON_READING_PONG
skill_module = _module
WikisourceError = sys.modules["ovos_skill_grimm_tales.wikisource"].WikisourceError


class FakeWikisource:
    """Stands in for Wikisource: no test reaches the network. `stories`
    maps a page url to its paragraphs; a collection is `collections`[lang]."""
    def __init__(self, collections=None, stories=None):
        self.collections = collections or {}
        self.stories = stories or {}
        self.calls = []

    def collection(self, lang, sources, skip=()):
        self.calls.append(("collection", lang))
        if lang not in self.collections:
            raise WikisourceError(f"{lang}: unreachable")
        return dict(self.collections[lang])

    def paragraphs(self, url):
        self.calls.append(("paragraphs", url))
        if url not in self.stories:
            raise WikisourceError(f"no text at {url}")
        return list(self.stories[url])


class FakeFileSystem:
    def __init__(self, base):
        self.base = base
        self.path = str(base)

    def exists(self, name):
        return (self.base / name).exists()

    def open(self, name, mode="r"):
        return open(self.base / name, mode)


@pytest.fixture
def skill(tmp_path, monkeypatch):
    s = GrimmTales.__new__(GrimmTales)
    s.log = MagicMock()
    s.skill_id = "ovos-skill-grimm-tales.test"
    s.status = MagicMock()
    s._bus = MagicMock()
    s._settings = {}
    monkeypatch.setattr(GrimmTales, "lang", "en-us", raising=False)
    s.served = {"en"}
    s.file_system = FakeFileSystem(tmp_path)
    s.res_dir = str(Path(__file__).resolve().parents[1])  # repo root, holds locale/
    s._lang_resources = {}  # OVOSSkill.resources' internal per-language cache
    s._auto_register_entity_files = lambda *a, **k: None  # ovos-workshop >= 9.8 needs attributes __new__() bypasses
    s.index = {}
    s._story_text_cache = {}
    s.__dict__["_wikisource"] = FakeWikisource()
    # matches locale/en-us/collection.voc + collection_meta.json - most
    # tests don't exercise _load_collection_meta() itself, they just
    # need these pre-populated the way initialize() would leave them
    s._collection_aliases = ["grimm", "the brothers grimm", "brothers grimm", "grimm brothers"]
    s._author_name = "the Brothers Grimm"
    s._collection_name = "Grimm's Fairy Tales"
    return s
