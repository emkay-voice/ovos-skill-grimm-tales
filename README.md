# <img src='story-512.png' card_color='#40DBB0' width='50' height='50' style='vertical-align:bottom'/> Grimm Tales (provider)

A *provider* skill for [ovos-common-reading-pipeline-plugin](https://github.com/andlo/ovos-common-reading-pipeline-plugin),
delivering the Brothers Grimm's fairy tales.

_"He who is too well off is always longing for something new."_
— from "The Mouse, the Bird, and the Sausage," Brothers Grimm

It is part of [Emkay](https://github.com/emkay-voice/emkay), OpenVoiceOS in
the browser, and works on any [OpenVoiceOS](https://openvoiceos.org).

[![Build](https://github.com/emkay-voice/ovos-skill-grimm-tales/actions/workflows/publish.yml/badge.svg)](https://github.com/emkay-voice/ovos-skill-grimm-tales/actions/workflows/publish.yml)
[![PyPI version](https://img.shields.io/pypi/v/ovos-skill-grimm-tales.svg)](https://pypi.org/project/ovos-skill-grimm-tales/)

> **This skill has no standalone voice interface.** It registers no
> intents and never speaks. It only answers
> [ovos.common_reading.* bus messages](https://github.com/andlo/ovos-common-reading-pipeline-plugin#the-ovoscommon_reading-bus-protocol),
> so you also need **ovos-common-reading-pipeline-plugin** installed and
> added to your pipeline config for it to be useful at all.

## Install
```bash
pip install ovos-skill-grimm-tales ovos-common-reading-pipeline-plugin
```

## Where the stories come from

This provider publishes nothing itself: it finds the stories where they
are already published, and every story says where it came from. The
`source` of each search answer is the site the text is read from, and
the pipeline says it after the last sentence ("And that's the end. It
came from Wikisource.").

- **[grimmstories.com](https://www.grimmstories.com/)** – on a device
  (any OpenVoiceOS), as it always was: 8 languages here, EN, DA, DE, ES,
  FR, IT, NL, PT. The site offers 20 languages in all; the other 12 (FI,
  HU, VI, TR, PL, RO, RU, UK, EL, ZH, JA, KO) aren't included yet since
  they fall outside [OVOS's actively-tracked language set](https://openvoiceos.github.io/lang-support-tracker/).
- **[Wikisource](https://wikisource.org)** – the free library of
  public-domain texts. A browser may not read grimmstories.com (the site
  doesn't allow other web pages to read it), but it may read Wikisource,
  so in a browser – [Emkay](https://github.com/emkay-voice/emkay) – the
  stories come from Wikisource. On a device Wikisource is the fallback
  when the site can't be reached.

| Language | Wikisource edition | Stories |
|---|---|---|
| German | The Grimms' own last edition, [Kinder- und Haus-Märchen 1857](https://de.wikisource.org/wiki/Kinder-_und_Haus-M%C3%A4rchen_Band_1_(1857)), both volumes | about 210 |
| English | [Grimm's Household Tales](https://en.wikisource.org/wiki/Grimm%27s_Household_Tales) (Margaret Hunt, 1884), both volumes | about 210 |
| French | [Contes choisis des frères Grimm](https://fr.wikisource.org/wiki/Contes_choisis_des_fr%C3%A8res_Grimm) | about 40 |
| Spanish | [Cuentos escogidos de los Hermanos Grimm](https://es.wikisource.org/wiki/Cuentos_escogidos_de_los_Hermanos_Grimm) | about 45 |

Danish, Italian, Dutch and Portuguese have no Grimm collection on
Wikisource yet that can be read aloud as it is (the Portuguese *Contos
de Grimm* is still being translated there), so a browser has no Grimm in
those languages. A story added to one of the
pages above is found the next time the index is built (once a week).
The texts on Wikisource are in the public domain; see each page for its
edition and translator.

## Languages

**This provider does not translate.** It loads only for the languages
the installation is configured for - the device's own `lang` plus
`secondary_langs` in `mycroft.conf` - that it has stories in (above). If
none of them is one of those, it **never loads at all**: `initialize()`
builds no index, registers no bus events, and logs a clear message
rather than silently serving English (or any other) content.

For each configured, supported language it builds its own story index,
and each search is answered from the index of the language it was made
in: the pipeline plugin's `lang` field, else the language of the session
the search came from, else the device's own. A single device builds one
index, as before. A HiveMind hub serving users in several languages lists
them in `secondary_langs`:

```json
{
  "lang": "en-US",
  "secondary_langs": ["da-DK", "de-DE"]
}
```

A search in a language the installation doesn't serve gets no answer at
all. A search with no title ("tell me a story") gets a random story at
0.9, and titles match regardless of case.

**Author/collection name and collection_hint aliases are also
per-language**, not hardcoded English - "the Brothers Grimm" only makes
sense to announce on an English device; a Danish device hears "Brødrene
Grimm" instead, and a Danish user saying "brødrene grimm" as a
collection_hint matches correctly (not just by luck, the way it would
have if we'd only shipped English aliases). See
`locale/<lang>/collection.voc` (aliases) and
`locale/<lang>/collection_meta.json` (author/collection name), loaded
via OVOS's own resource file resolution rather than Python constants -
see [ovos-common-reading-pipeline-plugin#26](https://github.com/andlo/ovos-common-reading-pipeline-plugin/issues/26)
for the full reasoning. This also means every supported language has
its own `locale/<lang>/skill.json`, so the Skills Store can see this
provider genuinely supports 8 languages, not just English.

## Collection hints

Responds to `collection_hint` values in the *device's own language* -
e.g. "grimm"/"the brothers grimm" on English, "grimm"/"brødrene grimm"
on Danish, "grimm"/"die gebrüder grimm" on German - matched fuzzily
against that language's own alias list (see `locale/<lang>/collection.voc`).

## Content type

Identifies as `content_type: "story"` or `"tale"`. A search with a
`content_type` hint for anything else (e.g. "article", "poem") gets no
response from this provider.

## Credits

Stories from [grimmstories.com](https://www.grimmstories.com/) and
[Wikisource](https://wikisource.org) and its volunteers, who transcribe
and proofread the public-domain editions. Scraping/caching logic ported
from [ovos-skill-fairytales](https://github.com/andlo/ovos-skill-fairytales)
and [ovos-skill-andersen-tales](https://github.com/emkay-voice/ovos-skill-andersen-tales).

## Category
**Entertainment**

## Tags
#stories #fairytales #grimm #provider #wikisource
