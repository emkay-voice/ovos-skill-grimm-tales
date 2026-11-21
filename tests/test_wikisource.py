"""wikisource.py on its own: titles, the text of a page, and which links
of a collection are stories. No network: the API is stood in for."""
import sys

import pytest

import conftest  # noqa: F401 - loads the package

ws = sys.modules["ovos_skill_grimm_tales.wikisource"]


def test_spoken_title_drops_book_and_edition():
    assert ws.spoken_title("Grimm's Household Tales, Volume 1/Cinderella") == "Cinderella"
    assert ws.spoken_title("Aschenputtel (1857)") == "Aschenputtel"
    assert ws.spoken_title("Algo (Andresen, Roca y Roca tr.)") == "Algo"
    assert ws.spoken_title("Den grimme Ælling") == "Den grimme Ælling"


def test_page_url_round_trips():
    url = ws.page_url("da", "Den grimme Ælling")
    assert url == "https://da.wikisource.org/wiki/Den_grimme_%C3%86lling"
    assert ws.parse_url(url) == ("da", "Den grimme Ælling")
    assert ws.is_wikisource(url)
    assert not ws.is_wikisource("https://www.andersenstories.com/da/x")


HTML = """<div class="mw-parser-output">
<div class="wst-header ws-noexport">Den grimme Ælling, af H.C. Andersen</div>
<div class="wst-center"><p>21.—THE UGLY DUCKLING.</p></div>
<p>It was so   beautiful
out in the country.<sup class="reference">[1]</sup></p>
<p><span class="PageNumber">[120]</span> The duck sat on her nest.</p>
<div class="poem"><p>Line one<br>Line two<br><br>Line three</p></div>
<table><tr><td>licence</td></tr></table>
<span style="display:none">hidden</span>
</div>"""


def test_html_paragraphs_keep_only_the_text():
    assert ws.html_paragraphs(HTML) == [
        "It was so beautiful out in the country.",
        "The duck sat on her nest.",
        "Line one\nLine two",
        "Line three",
    ]


class FakeAPI(ws.Wikisource):
    def __init__(self, pages):
        super().__init__("test")
        self.pages = pages

    def _parse(self, lang, page, prop, section=None):
        found = self.pages[page]
        if prop == "sections":
            return {"sections": [{"index": "1", "line": "Eventyr og historier"}]}
        return {"title": page, "text": found.get("text", ""),
                "links": [{"ns": 0, "exists": True, "title": t} for t in found.get("links", [])]}


def test_collection_keeps_stories_and_leaves_out_the_rest():
    api = FakeAPI({"Book": {"links": [
        "Book/The Ugly Duckling", "Book/Preface", "Book/The Snow Queen",
        "Book/The Snow Queen/1", "Book 2", "Hans Christian Andersen"]},
        "Book 2": {"links": ["The Ugly Duckling (Tegner)", "The Fir Tree"]}})

    index = api.collection("en", [("Book", None), ("Book 2", None)], skip={"Hans Christian Andersen"})

    assert list(index) == ["The Ugly Duckling", "The Snow Queen", "The Fir Tree"]
    assert index["The Ugly Duckling"] == ws.page_url("en", "Book/The Ugly Duckling")


def test_collection_from_a_section_of_an_author_page():
    api = FakeAPI({"Forfatter:H": {"links": ["Den grimme Ælling"]}})
    assert list(api.collection("da", [("Forfatter:H", "Eventyr og historier")])) == ["Den grimme Ælling"]


def test_a_story_in_chapters_is_read_chapter_by_chapter():
    long = "<p>" + "Snow. " * 60 + "</p>"
    api = FakeAPI({
        "The Snow Queen": {"links": ["The Snow Queen/2", "The Snow Queen/1", "The Snow Queen/10"]},
        "The Snow Queen/1": {"text": "<p>First.</p>" + long},
        "The Snow Queen/2": {"text": "<p>Second.</p>"},
        "The Snow Queen/10": {"text": "<p>Tenth.</p>"},
    })
    paragraphs = api.paragraphs(ws.page_url("en", "The Snow Queen"))
    assert paragraphs[0] == "First."
    assert paragraphs[-2:] == ["Second.", "Tenth."]


def test_a_page_without_text_is_an_error():
    api = FakeAPI({"Empty": {}})
    with pytest.raises(ws.WikisourceError):
        api.paragraphs(ws.page_url("en", "Empty"))


def test_the_title_at_the_top_of_a_page_is_not_read_twice():
    api = FakeAPI({"Quaranta novelle/Il rospo": {
        "text": "<p>IL ROSPO.</p><p>" + "Giù, in fondo, abitava una famiglia di rospi. " * 8 + "</p>"}})
    paragraphs = api.paragraphs(ws.page_url("it", "Quaranta novelle/Il rospo"))
    assert paragraphs[0].startswith("Giù, in fondo")


def test_where_a_picture_was_is_not_read():
    assert ws.html_paragraphs("<p>[imagen]</p><p>Erase una viuda.</p>") == ["Erase una viuda."]


def test_a_link_back_to_the_whole_work_does_not_hide_its_tales():
    """Galland's Table générale links to the work itself and to its tales,
    which are subpages of the work: skipping the work keeps the tales."""
    api = FakeAPI({"Nuits/Table générale": {"links": ["Nuits", "Nuits/Attaf", "Nuits/Attaf/1"]}})
    index = api.collection("fr", [("Nuits/Table générale", None)], skip={"Nuits"})
    assert list(index) == ["Attaf"]


def test_headings_above_the_text_are_not_read():
    api = FakeAPI({"Nights/Hicar": {
        "text": "<p>NOTTE CDXLIII</p><p>STORIA DEL SAGGIO HICAR.</p><p>" + "Sire, Sencharib, re. " * 20 + "</p>"}})
    assert api.paragraphs(ws.page_url("it", "Nights/Hicar"))[0].startswith("Sire, Sencharib")


def test_a_decorated_first_letter_keeps_its_letter():
    html = '<p><span class="dropinitial"><img alt="P" src="x.png"></span>RINCE HOUSSAIN would not.</p>'
    assert ws.html_paragraphs(html) == ["PRINCE HOUSSAIN would not."]
