"""Stories from Wikisource, the free library of public-domain texts.

Everything here goes through MediaWiki's action API with `origin=*`
(anonymous CORS), so a web page may read the answer too: the same code
works on a device and in a browser (Emkay). Wikisource is the publisher;
this module only finds and reads its pages.

A collection is a Wikisource page that links to its stories: a book's
table of contents ("Hans Andersen's Fairy Tales"), or one section of an
author's page ("Forfatter:Hans Christian Andersen", "Eventyr og
historier"). Only `requests` and BeautifulSoup are used, so this module
can be tested and reused without OVOS.
"""
import re
import time
from urllib.parse import quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

TIMEOUT = 10
MAX_RETRY_WAIT = 5  # seconds
SOURCE_NAME = "Wikisource"

# a page this short holds no story of its own - a book split into
# chapters, whose chapters are its subpages
MIN_STORY_CHARS = 300

# what a book's table of contents links to besides its stories
FRONT_MATTER = re.compile(
    r"^(preface|introduction|contents|index|notes?|reminiscences.*|"
    r"vorrede|vorwort|einleitung|anmerkungen.*|register|inhalt.*|"
    r"préface.*|introduction.*|avertissement.*|notice.*|table.*|texte entier|"
    r"extrait d.*|éloge d.*|à madame.*|"
    r"prefazione|introduzione|indice|fonti.*|.*alla traduttrice|avvertenza.*|"
    r"al lector|prólogo|introducción|índice|"
    r"prefácio|introdução|índice|"
    r"forord|indledning|indhold)$",
    re.IGNORECASE)

LINE_BREAK = "\u2028"  # stands in for <br> while the text is collected

# where a picture was: "[imagen]", "[Illustration]"
PLACEHOLDER = re.compile(r"^\[[^\]]{0,30}\]$")

# what Wikisource puts around a text: headers, page numbers, notes,
# licence boxes, navigation
_DROP_TAGS = ["style", "script", "table", "sup", "figure", "img", "noscript",
              "h1", "h2", "h3", "h4", "h5", "h6"]
_DROP_CLASSES = ["ws-noexport", "noprint", "wst-header", "headertemplate",
                 "mw-editsection", "pagenum", "ws-pagenum", "PageNumber",
                 "reference", "references", "mw-references-wrap", "thumb",
                 "licenseContainer", "footer", "ws-summary"]
_DROP_IDS = ["headertemplate", "textdaten", "navigationHeader", "ws-data"]


class WikisourceError(Exception):
    """A page could not be fetched or holds no text."""


def _user_agent(package):
    try:
        from importlib.metadata import version
        ver = version(package)
    except Exception:
        ver = "unknown"
    return f"{package}/{ver} (+https://github.com/emkay-voice/{package})"


class Wikisource:
    """One reader per provider, so Wikisource can see who is asking (a
    browser sends its own User-Agent instead, which is fine)."""

    def __init__(self, package):
        self.headers = {"User-Agent": _user_agent(package)}

    # --- the API -------------------------------------------------------

    def _api(self, lang, **params):
        url = f"https://{lang}.wikisource.org/w/api.php"
        params.update(format="json", formatversion="2", origin="*")
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT, headers=self.headers)
            if r.status_code == 429:
                # Wikimedia asks busy clients to wait a moment: wait once
                # (a few seconds at most) and ask again
                time.sleep(min(float(r.headers.get("retry-after") or 1), MAX_RETRY_WAIT))
                r = requests.get(url, params=params, timeout=TIMEOUT, headers=self.headers)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError) as e:
            raise WikisourceError(f"{lang}.wikisource.org: {e}") from e
        if "error" in data:
            raise WikisourceError(f"{lang}.wikisource.org: {data['error'].get('info')}")
        return data

    def _parse(self, lang, page, prop, section=None):
        params = {"action": "parse", "page": page, "prop": prop, "redirects": 1,
                  "disablelimitreport": 1, "disableeditsection": 1}
        if section is not None:
            params["section"] = section
        return self._api(lang, **params)["parse"]

    def _section_index(self, lang, page, heading):
        for section in self._parse(lang, page, "sections")["sections"]:
            if section["line"].strip().lower() == heading.lower():
                return section["index"]
        raise WikisourceError(f"no section '{heading}' on {lang}:{page}")

    def links(self, lang, page, section=None):
        """The existing main-namespace pages `page` links to, in the
        order the API gives them (alphabetical)."""
        if section is not None and not str(section).isdigit():
            section = self._section_index(lang, page, section)
        parsed = self._parse(lang, page, "links", section)
        return [link["title"] for link in parsed["links"]
                if link["ns"] == 0 and link.get("exists")]

    # --- collections -----------------------------------------------------

    def collection(self, lang, sources, skip=()):
        """{spoken title: url} for the stories the `sources` link to.
        `sources` is a list of (page, section heading or None); the first
        source that has a title wins it. Front matter, the sources
        themselves, chapters of a story and anything in `skip` are left
        out."""
        pages = {page for page, _ in sources}
        skip = {s.lower() for s in skip}
        index = {}
        for page, section in sources:
            targets = [target for target in self.links(lang, page, section)
                       if target not in pages and target.lower() not in skip]
            for target in targets:
                parent = target.rsplit("/", 1)[0] if "/" in target else None
                if parent in targets:
                    continue  # a chapter, read as part of its story
                title = spoken_title(target)
                if not title or FRONT_MATTER.match(title) or title.lower() in skip:
                    continue
                index.setdefault(title, page_url(lang, target))
        return index

    # --- stories -----------------------------------------------------------

    def paragraphs(self, url):
        """The paragraphs of the story at a Wikisource page url. A page
        with (almost) no text of its own is a story split into chapters:
        its subpages are read in order instead."""
        lang, title = parse_url(url)
        parsed = self._parse(lang, title, "text|links")
        paragraphs = html_paragraphs(parsed["text"])
        if sum(map(len, paragraphs)) < MIN_STORY_CHARS:
            chapters = sorted((link["title"] for link in parsed["links"]
                               if link["ns"] == 0 and link.get("exists")
                               and link["title"].startswith(parsed["title"] + "/")),
                              key=_natural_key)
            for chapter in chapters:
                paragraphs += html_paragraphs(self._parse(lang, chapter, "text")["text"])
        # the title and headings above the text ("IL ROSPO.", "NOTTE
        # CDXLIII"), which the pipeline has announced already
        while paragraphs and (_letters(paragraphs[0]) == _letters(spoken_title(title))
                              or _is_heading(paragraphs[0])):
            paragraphs = paragraphs[1:]
        if not paragraphs:
            raise WikisourceError(f"no text at {url}")
        return paragraphs


def page_url(lang, title):
    return f"https://{lang}.wikisource.org/wiki/{quote(title.replace(' ', '_'))}"


def parse_url(url):
    """'https://da.wikisource.org/wiki/Den_grimme_%C3%86lling' ->
    ('da', 'Den grimme Ælling')."""
    parts = urlparse(url)
    return parts.netloc.split(".")[0], unquote(parts.path[len("/wiki/"):]).replace("_", " ")


def is_wikisource(url):
    return urlparse(url or "").netloc.endswith(".wikisource.org")


def spoken_title(page):
    """How a story is called aloud: no book in front of it, no edition or
    translator behind it. "Grimm's Household Tales, Volume 1/Cinderella"
    -> "Cinderella", "Aschenputtel (1857)" -> "Aschenputtel"."""
    title = page.rsplit("/", 1)[-1]
    title = re.sub(r"\s*\([^)]*\)\s*$", "", title)
    return " ".join(title.split())


def _letters(text):
    """Only the letters, in lower case: "IL BRUTTO ANITROCCOLO." and
    "Il brutto anitroccolo" are the same title."""
    return "".join(c for c in text.casefold() if c.isalpha())


def _is_heading(paragraph):
    """A short line in capitals only: a heading, not a sentence."""
    return len(paragraph) < 80 and any(c.isalpha() for c in paragraph) \
        and not any(c.islower() for c in paragraph)


def _natural_key(title):
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r"(\d+)", title)]


def _drop(root):
    # a decorated first letter drawn as a picture keeps its letter
    for img in root.find_all("img"):
        alt = (img.get("alt") or "").strip()
        if len(alt) == 1 and alt.isalpha():
            img.replace_with(alt)
    for tag in root.find_all(_DROP_TAGS):
        tag.decompose()
    for name in _DROP_CLASSES:
        for tag in root.find_all(class_=name):
            tag.decompose()
    for tag in root.find_all(id=_DROP_IDS):
        tag.decompose()
    for tag in root.find_all(style=re.compile(r"display\s*:\s*none")):
        tag.decompose()
    # a centred line on its own is a heading ("21.—CINDERELLA."), not text
    for tag in root.find_all(class_=["wst-center", "center"]):
        if len(tag.get_text(" ", strip=True)) < 80:
            tag.decompose()
    for tag in root.find_all("center"):
        if len(tag.get_text(" ", strip=True)) < 80:
            tag.decompose()


def html_paragraphs(html):
    """The paragraphs of a page's rendered text: each <p> is one, and a
    poem keeps one line per line with a paragraph per stanza."""
    soup = BeautifulSoup(html, "html.parser")
    root = soup.find(class_="mw-parser-output") or soup
    _drop(root)
    paragraphs = []
    for block in root.find_all(["p", "div"]):
        is_poem = "poem" in (block.get("class") or [])
        if block.name == "div" and not is_poem:
            continue
        if block.find_parent(class_="poem"):
            continue  # read as part of its poem
        for br in block.find_all("br"):
            br.replace_with(LINE_BREAK)
        if is_poem:
            for p in block.find_all("p"):
                p.insert_after(LINE_BREAK + LINE_BREAK)
                p.unwrap()
        lines = [" ".join(line.split()) for line in block.get_text().split(LINE_BREAK)]
        stanza = []
        for line in lines + [""]:
            if line:
                stanza.append(line)
            elif stanza:
                paragraph = "\n".join(stanza)
                if not PLACEHOLDER.match(paragraph):
                    paragraphs.append(paragraph)
                stanza = []
    return paragraphs
