#!/usr/bin/env python3
"""Which tarot card does the world search for? Meaning searches for the 78 cards in eight languages.

Study v2. Pre-registration written on 8 November 2026 BEFORE the v2 count (the v2 fetch follows in a later commit).

Why a v2. Study v1 (pre-registered in 3b89637cc, hypotheses kept below as HYPOTHESES_V1) ranked the cards by Google
Trends TOPICS. An independent critic and two term checks showed that ranking to be an artefact of how Google attaches
searches to entities: a bare "death", "world" or "star" goes to the ordinary word, so cards whose names are ordinary
words are under-counted and cards with rare names (High Priestess, Hierophant) are not. English search TERMS
"<card> tarot meaning" correlate -0.19 with the topic ranking and 0.94 with plain "<card> tarot". v1 is not published.
Topics stay valid for one card across countries or months, never for one card against another.

What had been seen by then (so these are not tests in English): English "<card> tarot meaning" for the 22 Major
Arcana, worldwide, 2025-11-01..2026-10-31 — The World first, then The Star and The Moon; Death 9th; The High
Priestess 13th; The Hierophant last; English "<card> tarot" gives nearly the same order. The v1 topic results by
country, suit and month; English Wikipedia views (The Fool first; the Major Arcana 72 % of views); the Spanish and
Italian Wikipedia figures were broken by article renames during the window (old titles' views lost).

Design v2
---------
* A card is searched with "<name> <tarot word> <meaning word>" in each language, where a name may have variants joined
  with Google's "+" (an OR of queries): the site's own card name (lib/i18n/<lang>/tarot/cards/list.ts) without its
  article, plus the common variants listed in NAMES_V2 (Papisa/Sacerdotisa, Bateleur/Magicien, Шут/Дурак, ...),
  fixed here before the count. Words of a term may appear in any order in a query (Google Trends term matching).
* Languages and their terms: en "tarot meaning"; es "tarot significado"; pt "tarot significado" + "tarô significado";
  de "tarot bedeutung"; fr "tarot signification"; it "tarocchi significato" + "tarot significato"; pl "tarot
  znaczenie"; ru "таро значение".
* All 22 Major Arcana in every language, chained in groups of four on The Fool; the 56 minor cards in English only,
  chained on the Knight of Swords, with a bridge query (The Fool, Knight of Swords, The Lovers, Death, Ace of Cups).
  Worldwide interest over time (weekly) for each comparison, and the compared breakdown by country.
* Countries: each country is read in its main language (COUNTRY_LANG below, fixed now); its leader is the Major
  Arcana card with the most meaning searches in that language, with the same whole-percent rounding bounds as v1.
* Wikipedia: views of each card article PLUS its redirects (old titles after a rename keep their views), monthly.

Hypotheses (v2)
---------------
"""

HYPOTHESES_V1 = {  # study v1, pre-registered in 3b89637cc, abandoned (see above); kept for the record
    'H1': 'Worldwide, the tarot card with the most Google interest is a Major Arcana card, and it is not Death.',
    'H2': 'The 22 Major Arcana take more than 70 % of the worldwide Google interest in all 78 cards.',
    'H3': 'Countries do not share one favourite: among countries with enough volume, at least 5 different cards '
          'are a national leader.',
    'H4': 'In Russia, Belarus, Kazakhstan and Ukraine The Lovers has more interest than The Fool.',
    'H5': 'In Spanish- and Portuguese-speaking countries with enough volume, The Magician is in the national '
          'top 3 of the Major Arcana in most of them.',
    'H6': 'Worldwide, Cups is the suit with the most interest and Pentacles (Coins) the suit with the least.',
    'H7': 'Death peaks in October: its interest relative to The Fool is highest in October of the 12 months.',
    'H8': 'The Lovers peaks around Valentine\'s Day: its interest relative to The Fool is highest in February of '
          'the 12 months.',
    'H9': 'Google and Wikipedia agree: the Spearman rank correlation between worldwide Google interest and '
          'English Wikipedia pageviews over the cards in both is at least 0.6.',
}
HYPOTHESES = {
    'H1': 'In at least 4 of the 7 languages other than English, the Major Arcana card with the most meaning searches '
          'is the World, the Star or the Moon.',
    'H2': 'Death is in the top half (top 11 of 22) of the Major Arcana by meaning searches in at least 6 of the 8 '
          'languages.',
    'H3': 'The High Priestess is outside the top 5 of the Major Arcana by meaning searches in at least 6 of the 8 '
          'languages.',
    'H4': 'In English, the 56 minor cards together get more meaning searches than the 22 Major Arcana.',
    'H5': 'In English, Cups is the suit with the most meaning searches per card and Pentacles the suit with the '
          'least.',
    'H6': 'In English, the single card with the most meaning searches of all 78 is a Major Arcana card.',
    'H7': 'Languages disagree: at least 3 different cards lead the Major Arcana across the 8 languages.',
    'H8': 'In English, meaning searches for the Lovers, relative to the Fool, are highest in February of the 12 '
          'months.',
    'H9': 'Searchers and readers want different cards: the Spearman correlation between English meaning searches and '
          'English Wikipedia views (redirects included) over the 78 cards is below 0.3.',
}
ADDED_AFTER_COUNT_V1: dict[str, str] = {  # study v1
    'A1': '[after count] Topic check: the 22 Major Arcana and the Ace of Wands come back from Trends typed "Tarot card"; '
          'the other 53 minor cards come back with the generic type "Topic", named exactly as the card (Coins for '
          'Pentacles). Their ids come from the card items in Wikidata, so validate accepts the exact name with either '
          'type, and the minor-arcana results carry this caveat.',
    'A2': '[after count] Eight of Cups and Queen of Wands have no Trends topic, so suits are compared by the mean '
          'interest per card (H6), not by the sum.',
    'A3': '[after count] Two of Wands: its topic (/g/11bc61vzm3, Wikidata P2671) collects almost no searches '
          '(0.03 against 20-120 for every other card) while its Wikipedia article has ordinary views; it is a '
          'topic Google does not attach searches to, so it is left out of every Trends ranking, sum and test.',
    'A4': '[after count] Rounding intervals: Google prints regional shares as whole percents, so each country index '
          'gets bounds from +-0.5 on every share it uses; a national leader is "clear" only when its lower bound '
          'beats the upper bound of every other card. H3 is printed both ways.',
    'A5': '[after count] Sampling check: the first majors query and the bridge are pulled a second time in a new '
          'session; the worldwide indices of their cards are compared with the first pull.',
    'A6': '[after count] Word check, raised by the independent critic: card names that are ordinary words (Death, '
          'the Devil, the World, Judgement) sit at the bottom of the topic ranking and distinctive names at the top. '
          'Search TERMS "<card> tarot" (English, worldwide, same window) are compared for 22 Major Arcana chained on '
          '"high priestess tarot", to see whether the topic ranking holds when every query names the deck.',
    'A7': '[after count] Second word check: "<card> tarot meaning" terms for the same 22 cards, chained on '
          '"high priestess tarot meaning" (bare "<card> tarot" also catches "world tarot day" and the like).',
}
UNRELIABLE_TOPICS = ['two-of-wands']  # A3
TERM_CARDS = [  # A6: English search terms, all ending in "tarot"
    ('the-high-priestess', 'high priestess tarot'), ('the-fool', 'fool tarot'), ('death', 'death tarot'),
    ('the-devil', 'devil tarot'), ('the-hanged-man', 'hanged man tarot'), ('the-tower', 'tower tarot'),
    ('the-lovers', 'lovers tarot'), ('the-world', 'world tarot'), ('judgement', 'judgement tarot'),
    ('the-magician', 'magician tarot'), ('the-hermit', 'hermit tarot'), ('the-empress', 'empress tarot'),
    ('the-emperor', 'emperor tarot'), ('the-hierophant', 'hierophant tarot'), ('the-chariot', 'chariot tarot'),
    ('strength', 'strength tarot'), ('wheel-of-fortune', 'wheel of fortune tarot'), ('justice', 'justice tarot'),
    ('temperance', 'temperance tarot'), ('the-star', 'star tarot'), ('the-moon', 'moon tarot'), ('the-sun', 'sun tarot'),
]

ADDED_AFTER_COUNT: dict[str, str] = {  # study v2
    'A1': '[during fetch, before compute] Google Trends rejects a term with more than three OR parts (HTTP 400), '
          'so Portuguese drops "tarô significado" and Italian drops "tarot significato": each keeps one meaning '
          'phrase ("tarot significado", "tarocchi significato") with every name variant. English and Spanish had been '
          'fetched as pre-registered.',
    'A2': '[after count] Worldwide totals of a language mix languages that spell card names the same way: Spanish and '
          'Portuguese share mago, sol, torre, mundo, carro, sacerdotisa, papisa, enamorados, hierofante, so the '
          'Spanish worldwide ranking was led by exactly those cards. Every language except English is therefore read '
          'inside its first country of COUNTRY_LANG (ES, BR, DE, FR, IT, PL, RU; fixed in the pre-registration), by '
          'Google\'s compared breakdown for that country over the whole year. The same queries restricted to the '
          'country as weekly series (fetch-v2-geo) proved too sparse to use: the anchor sums to 8-16 weekly points '
          'in Germany, France and Spain (8 to 100 points in-country, 1 to 3 non-zero weeks worldwide), and in Italy the sparse weeks put Death first while the full-year breakdown '
          'puts the Moon first; they are kept only as that evidence. A language whose first country has no breakdown '
          'has too few searches.',
    'A3': '[after count] A language with too few searches (A2) counts as not meeting H1, and H2, H3 and H7 are '
          'counted over the languages with enough searches. Ties (whole-percent shares make them common) never count '
          'for a hypothesis: H1 and H7 need a single leader, H2 takes Death\'s worst tied rank and H3 the High '
          'Priestess\'s best. The page prints every verdict under the pre-registered reading (worldwide weekly series '
          'per language) and under A2 side by side.',
    'A4': '[after count] Contamination check for the sky cards (related queries came back empty): the English terms '
          'again with Google\'s minus operator, "moon tarot meaning -full -new -sign -phase", "sun tarot meaning -sign", '
          '"star tarot meaning -sign", "world tarot meaning -day", each against "fool tarot meaning" and its own '
          'unfiltered term, worldwide, same window.',
}

# v2 search terms. Order = MAJORS. Each card: name variants (any matches); article dropped.
MEANING_WORDS = {
    'en': ['tarot meaning'],
    'es': ['tarot significado'],
    'pt': ['tarot significado'],  # A1: 'tarô significado' dropped
    'de': ['tarot bedeutung'],
    'fr': ['tarot signification'],
    'it': ['tarocchi significato'],  # A1: 'tarot significato' dropped
    'pl': ['tarot znaczenie'],
    'ru': ['таро значение'],
}
NAMES_V2 = {
    'en': [['fool'], ['magician'], ['high priestess'], ['empress'], ['emperor'], ['hierophant'], ['lovers'],
           ['chariot'], ['strength'], ['hermit'], ['wheel of fortune'], ['justice'], ['hanged man'], ['death'],
           ['temperance'], ['devil'], ['tower'], ['star'], ['moon'], ['sun'], ['judgement', 'judgment'], ['world']],
    'es': [['loco'], ['mago'], ['sacerdotisa', 'papisa'], ['emperatriz'], ['emperador'],
           ['hierofante', 'sumo sacerdote'], ['enamorados'], ['carro'], ['fuerza'], ['ermitaño'],
           ['rueda de la fortuna'], ['justicia'], ['colgado'], ['muerte'], ['templanza'], ['diablo'], ['torre'],
           ['estrella'], ['luna'], ['sol'], ['juicio'], ['mundo']],
    'pt': [['louco'], ['mago'], ['sacerdotisa', 'papisa'], ['imperatriz'], ['imperador'], ['hierofante', 'papa'],
           ['enamorados'], ['carro'], ['força'], ['eremita'], ['roda da fortuna'], ['justiça'], ['enforcado'],
           ['morte'], ['temperança'], ['diabo'], ['torre'], ['estrela'], ['lua'], ['sol'], ['julgamento'], ['mundo']],
    'de': [['narr'], ['magier'], ['hohepriesterin'], ['herrscherin'], ['herrscher'], ['hierophant', 'hohepriester'],
           ['liebenden'], ['wagen'], ['kraft'], ['eremit'], ['rad des schicksals'], ['gerechtigkeit'], ['gehängte'],
           ['tod'], ['mäßigkeit'], ['teufel'], ['turm'], ['stern'], ['mond'], ['sonne'], ['gericht'], ['welt']],
    'fr': [['fou', 'mat'], ['magicien', 'bateleur'], ['grande prêtresse', 'papesse'], ['impératrice'], ['empereur'],
           ['hiérophante', 'pape'], ['amoureux'], ['chariot'], ['force'], ['hermite'], ['roue de fortune'],
           ['justice'], ['pendu'], ['mort', 'arcane sans nom'], ['tempérance'], ['diable'], ['tour', 'maison dieu'],
           ['étoile'], ['lune'], ['soleil'], ['jugement'], ['monde']],
    'it': [['matto', 'folle'], ['mago', 'bagatto'], ['papessa', 'sacerdotessa'], ['imperatrice'], ['imperatore'],
           ['papa', 'ierofante'], ['amanti', 'innamorati'], ['carro'], ['forza'], ['eremita'],
           ['ruota della fortuna'], ['giustizia'], ['appeso'], ['morte'], ['temperanza'], ['diavolo'], ['torre'],
           ['stella'], ['luna'], ['sole'], ['giudizio'], ['mondo']],
    'pl': [['głupiec'], ['mag'], ['kapłanka'], ['cesarzowa'], ['cesarz'], ['arcykapłan'], ['kochankowie'],
           ['rydwan'], ['siła'], ['pustelnik'], ['koło fortuny'], ['sprawiedliwość'], ['wisielec'], ['śmierć'],
           ['umiarkowanie'], ['diabeł'], ['wieża'], ['gwiazda'], ['księżyc'], ['słońce'], ['sąd'], ['świat']],
    'ru': [['шут', 'дурак'], ['маг'], ['жрица'], ['императрица'], ['император'], ['иерофант', 'жрец'],
           ['влюблённые', 'влюбленные'], ['колесница'], ['сила'], ['отшельник'], ['колесо фортуны'],
           ['справедливость', 'правосудие'], ['повешенный'], ['смерть'], ['умеренность'], ['дьявол'], ['башня'],
           ['звезда'], ['луна'], ['солнце'], ['суд'], ['мир']],
}
# Each country is read in its main language (only countries where that language is the main one of web search).
COUNTRY_LANG = {
    'en': ['US', 'GB', 'CA', 'AU', 'NZ', 'IE', 'ZA', 'IN', 'PH', 'SG', 'NG'],
    'es': ['ES', 'MX', 'AR', 'CO', 'CL', 'PE', 'VE', 'EC', 'GT', 'CU', 'BO', 'DO', 'HN', 'PY', 'SV', 'NI', 'CR',
           'PA', 'UY', 'PR'],
    'pt': ['BR', 'PT', 'AO', 'MZ'],
    'de': ['DE', 'AT', 'CH'],
    'fr': ['FR', 'BE'],
    'it': ['IT'],
    'pl': ['PL'],
    'ru': ['RU', 'BY', 'KZ', 'UA'],
}

# ======================================================================================== the script
# Needs Python 3.10+ (standard library only) and network access. Raw responses go to $TAROT_SEARCH_DATA (default
# ~/startarot-data/tarot-card-search when ~/startarot-data exists, otherwise ./tarot-card-search-data next to this
# script). Steps of study v2, in order:
#     python3 tarot_card_search.py fetch-wiki            # Wikipedia language links (+ v1 pageviews, kept for the record)
#     python3 tarot_card_search.py fetch-wiki-redirects  # monthly views of each card article plus its redirects
#     python3 tarot_card_search.py fetch-v2              # Google Trends: meaning searches, 8 languages, 63 comparisons
#     python3 tarot_card_search.py fetch-trends          # v1 topic comparisons (only for the v1-vs-v2 comparison)
#     python3 tarot_card_search.py fetch-map             # Natural Earth country outlines
#     python3 tarot_card_search.py compute               # -> _work/computed.json
#     python3 tarot_card_search.py validate              # every card has searches, bridge consistency, coverage
#     python3 tarot_card_search.py export                # page JSON + CSV (+ a copy of this script); refuses if validate failed
# Run from the repo, export writes (GENERATED: regenerate, do not hand-edit):
#     frontend/src/lib/research/tarot-card-search.json
#     frontend/static/research/tarot-card-search.csv
#     frontend/static/research/tarot_card_search.py
# Google Trends is asked politely: one request every TRENDS_PAUSE seconds, a long pause on HTTP 429, every
# response stored raw, a rerun only fetches what is missing. Trends values are sampled by Google and may differ a
# little between pulls; the raw responses used for the page are kept with their fetch time.

import datetime as dt
import json
import math
import os
import shutil
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from http.cookiejar import CookieJar
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'tarot-card-search'
SLUG = 'which-tarot-card-does-the-world-search-for'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'tarot_card_search.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
_MAC_DATA = Path.home() / 'startarot-data' / 'tarot-card-search'
DATA = Path(os.environ.get('TAROT_SEARCH_DATA') or
            (_MAC_DATA if _MAC_DATA.parent.is_dir() else HERE / 'tarot-card-search-data'))
WORK = DATA / '_work'
WIKI_UA = 'StarTarotResearch/1.0 (https://startarot.online/research)'
BROWSER_UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36'
START, END = '2025-11-01', '2026-10-31'
MONTHS = [f'{y}-{m:02d}' for y, m in [(2025, 11), (2025, 12)] + [(2026, m) for m in range(1, 11)]]
TRENDS_PAUSE = 12
T0 = time.time()

MAJORS = [  # (number, name, site slug, English Wikipedia title)
    (0, 'The Fool', 'the-fool', 'The Fool (tarot card)'),
    (1, 'The Magician', 'the-magician', 'The Magician (tarot card)'),
    (2, 'The High Priestess', 'the-high-priestess', 'The High Priestess'),
    (3, 'The Empress', 'the-empress', 'The Empress (tarot card)'),
    (4, 'The Emperor', 'the-emperor', 'The Emperor (tarot card)'),
    (5, 'The Hierophant', 'the-hierophant', 'The Hierophant'),
    (6, 'The Lovers', 'the-lovers', 'The Lovers'),
    (7, 'The Chariot', 'the-chariot', 'The Chariot (tarot card)'),
    (8, 'Strength', 'strength', 'Strength (tarot card)'),
    (9, 'The Hermit', 'the-hermit', 'The Hermit (tarot card)'),
    (10, 'Wheel of Fortune', 'wheel-of-fortune', 'Wheel of Fortune (tarot card)'),
    (11, 'Justice', 'justice', 'Justice (tarot card)'),
    (12, 'The Hanged Man', 'the-hanged-man', 'The Hanged Man (tarot card)'),
    (13, 'Death', 'death', 'Death (tarot card)'),
    (14, 'Temperance', 'temperance', 'Temperance (tarot card)'),
    (15, 'The Devil', 'the-devil', 'The Devil (tarot card)'),
    (16, 'The Tower', 'the-tower', 'The Tower (tarot card)'),
    (17, 'The Star', 'the-star', 'The Star (tarot card)'),
    (18, 'The Moon', 'the-moon', 'The Moon (tarot card)'),
    (19, 'The Sun', 'the-sun', 'The Sun (tarot card)'),
    (20, 'Judgement', 'judgement', 'Judgement (tarot card)'),
    (21, 'The World', 'the-world', 'The World (tarot card)'),
]
RANKS = ['Ace', 'Two', 'Three', 'Four', 'Five', 'Six', 'Seven', 'Eight', 'Nine', 'Ten', 'Page', 'Knight', 'Queen', 'King']
SUITS = [('Wands', 'wands', 'Wands'), ('Cups', 'cups', 'Cups'), ('Swords', 'swords', 'Swords'),
         ('Pentacles', 'pentacles', 'Coins')]  # (name, slug part, English Wikipedia word)


def cards():
    out = [{'id': slug, 'name': name, 'arcana': 'major', 'number': n, 'suit': None, 'wiki_en': title}
           for n, name, slug, title in MAJORS]
    for suit, sslug, wword in SUITS:
        for i, rank in enumerate(RANKS):
            title = f'{rank} of {wword}'
            if title == 'Ace of Wands':
                title = 'Ace of Wands (tarot card)'
            out.append({'id': f'{rank.lower()}-of-{sslug}', 'name': f'{rank} of {suit}', 'arcana': 'minor',
                        'number': i + 1, 'suit': suit, 'wiki_en': title})
    return out


CARDS = cards()
BY_ID = {c['id']: c for c in CARDS}
ANCHOR_A = 'the-fool'
# H4/H5 country groups (ISO 3166-1 alpha-2, as Google Trends names them)
H4_COUNTRIES = ['RU', 'BY', 'KZ', 'UA']
H5_COUNTRIES = ['ES', 'MX', 'AR', 'CO', 'CL', 'PE', 'VE', 'EC', 'GT', 'CU', 'BO', 'DO', 'HN', 'PY', 'SV', 'NI', 'CR',
                'PA', 'UY', 'PR', 'BR', 'PT', 'AO', 'MZ']
# Wikipedia editions read for shares within a language (fixed before the count)
WIKI_LANGS = ['en', 'de', 'es', 'fr', 'it', 'pt', 'pl', 'ru', 'nl', 'cs', 'uk', 'tr', 'ja', 'sv', 'hu']
# the bridge query repeats three cards from the chains
BRIDGE_REPEAT = ['the-lovers', 'death', 'ace-of-cups']


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


def wget(url, ua=WIKI_UA, opener=None, tries=4):
    for k in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': ua})
            with (opener.open(req, timeout=60) if opener else urllib.request.urlopen(req, timeout=60)) as r:
                return r.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 and k < tries - 1:
                wait = 90 * (k + 1)
                log(f'HTTP 429, waiting {wait}s')
                time.sleep(wait)
                continue
            raise
        except urllib.error.URLError:
            if k < tries - 1:
                time.sleep(10)
                continue
            raise
    return None


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1))
    tmp.replace(path)


def load(path):
    return json.loads(path.read_text())


# ---------------------------------------------------------------------------------------- Wikipedia
def fetch_wiki():
    out = DATA / 'wiki'
    api = 'https://en.wikipedia.org/w/api.php?'
    links_path = out / 'langlinks.json'
    if not links_path.exists():
        links, qids = {}, {}
        titles = [c['wiki_en'] for c in CARDS]
        for i in range(0, len(titles), 20):
            q = urllib.parse.urlencode({'action': 'query', 'prop': 'langlinks|pageprops', 'ppprop': 'wikibase_item',
                                        'titles': '|'.join(titles[i:i + 20]), 'lllimit': 500, 'format': 'json'})
            d = json.loads(wget(api + q))
            for p in d['query']['pages'].values():
                links[p['title']] = {ll['lang']: ll['*'] for ll in p.get('langlinks', [])}
                qids[p['title']] = p.get('pageprops', {}).get('wikibase_item')
        missing = [t for t in titles if t not in links]
        if missing:
            sys.exit(f'English Wikipedia titles not found: {missing}')
        save(links_path, {'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                          'langlinks': links, 'wikidata': qids})
        log('langlinks: saved')
    meta = load(links_path)
    views_path = out / 'pageviews.json'
    views = load(views_path) if views_path.exists() else {}
    s, e = START.replace('-', '') + '00', END.replace('-', '') + '00'
    n = 0
    for c in CARDS:
        t_en = c['wiki_en']
        for lang in WIKI_LANGS:
            title = t_en if lang == 'en' else meta['langlinks'][t_en].get(lang)
            if not title:
                continue
            key = f'{lang}|{title}'
            if key in views:
                continue
            art = urllib.parse.quote(title.replace(' ', '_'), safe='')
            url = (f'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/'
                   f'user/{art}/monthly/{s}/{e}')
            body = wget(url)
            monthly = {}
            if body:
                for it in json.loads(body).get('items', []):
                    monthly[it['timestamp'][:4] + '-' + it['timestamp'][4:6]] = it['views']
            views[key] = {'card': c['id'], 'lang': lang, 'title': title, 'monthly': monthly}
            n += 1
            if n % 50 == 0:
                save(views_path, views)
            time.sleep(0.05)
    save(views_path, views)
    log(f'pageviews: {len(views)} articles ({n} new)')


def fetch_wiki_redirects():
    """v2: views of every card article PLUS its redirects (a renamed article keeps its old title's views)."""
    meta = load(DATA / 'wiki' / 'langlinks.json')
    out_path = DATA / 'wiki' / 'pageviews_v2.json'
    out = load(out_path) if out_path.exists() else {}
    s_, e_ = START.replace('-', '') + '00', END.replace('-', '') + '00'

    def views(lang, title):
        art = urllib.parse.quote(title.replace(' ', '_'), safe='')
        body = wget(f'https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/'
                    f'user/{art}/monthly/{s_}/{e_}')
        res = {}
        for it in (json.loads(body).get('items', []) if body else []):
            res[it['timestamp'][:4] + '-' + it['timestamp'][4:6]] = it['views']
        return res

    for c in CARDS:
        for lang in WIKI_LANGS:
            title = c['wiki_en'] if lang == 'en' else meta['langlinks'][c['wiki_en']].get(lang)
            if not title:
                continue
            key = f'{lang}|{title}'
            if key in out:
                continue
            q = urllib.parse.urlencode({'action': 'query', 'prop': 'redirects|pageprops', 'titles': title,
                                        'rdnamespace': 0, 'rdlimit': 500, 'redirects': 1, 'format': 'json'})
            d = json.loads(wget(f'https://{lang}.wikipedia.org/w/api.php?' + q))
            page = next(iter(d['query']['pages'].values()))
            canonical = page.get('title', title)
            reds = [r['title'] for r in page.get('redirects', [])]
            parts = {canonical: views(lang, canonical)}
            for r in reds:
                parts[r] = views(lang, r)
                time.sleep(0.03)
            monthly = {mo: sum(p.get(mo, 0) for p in parts.values()) for mo in MONTHS}
            out[key] = {'card': c['id'], 'lang': lang, 'title': canonical, 'redirects': len(reds),
                        'qid': page.get('pageprops', {}).get('wikibase_item'),
                        'months_with_views': sum(1 for mo in MONTHS if parts[canonical].get(mo)),
                        'monthly': monthly}
            save(out_path, out)
    log('pageviews with redirects:', len(out))


# ---------------------------------------------------------------------------------------- Google Trends
class Trends:
    def __init__(self):
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        wget('https://trends.google.com/trends/?geo=US', ua=BROWSER_UA, opener=self.opener)
        self.last = 0.0

    def get(self, path, params):
        wait = TRENDS_PAUSE - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        url = f'https://trends.google.com/trends/api/{path}?' + urllib.parse.urlencode(params)
        body = wget(url, ua=BROWSER_UA, opener=self.opener, tries=6)
        self.last = time.time()
        if body is None:
            raise RuntimeError(f'no body for {path}')
        return json.loads(body[body.index('{'):])

    def autocomplete(self, text):
        return self.get('autocomplete/' + urllib.parse.quote(text), {'hl': 'en-US', 'tz': 0})['default']['topics']

    def explore(self, mids):
        req = {'comparisonItem': [{'keyword': m, 'geo': '', 'time': f'{START} {END}'} for m in mids],
               'category': 0, 'property': ''}
        return self.get('explore', {'hl': 'en-US', 'tz': 0, 'req': json.dumps(req, separators=(',', ':'))})

    def widget(self, kind, w):
        return self.get(f'widgetdata/{kind}', {'hl': 'en-US', 'tz': 0, 'token': w['token'],
                                               'req': json.dumps(w['request'], separators=(',', ':'))})


def topic_ids(tr):
    path = DATA / 'trends' / 'topics.json'
    if path.exists():
        return load(path)
    meta = load(DATA / 'wiki' / 'langlinks.json')
    qids = [q for q in meta['wikidata'].values() if q]
    ents = {}
    for i in range(0, len(qids), 50):
        q = urllib.parse.urlencode({'action': 'wbgetentities', 'ids': '|'.join(qids[i:i + 50]), 'props': 'claims',
                                    'format': 'json'})
        ents.update(json.loads(wget('https://www.wikidata.org/w/api.php?' + q))['entities'])
    out = {}
    for c in CARDS:
        q = meta['wikidata'].get(c['wiki_en'])
        claims = ents.get(q, {}).get('claims', {})
        ids = [x['mainsnak']['datavalue']['value'] for p in ('P646', 'P2671') for x in claims.get(p, [])
               if 'datavalue' in x['mainsnak']]
        src = 'wikidata'
        if not ids:
            cand = [t for t in tr.autocomplete(c['name']) if t.get('type', '').lower() == 'tarot card'
                    and t['title'].lower() == c['name'].lower().replace('pentacles', 'pentacles')]
            ids = [cand[0]['mid']] if cand else []
            src = 'trends-autocomplete' if ids else None
        out[c['id']] = {'mid': ids[0] if ids else None, 'source': src, 'qid': q}
    save(path, out)
    return out


def queries(topics):
    """The fixed list of comparisons: anchor + up to four cards."""
    wiki = load(DATA / 'wiki' / 'pageviews.json')
    en = {v['card']: sum(v['monthly'].values()) for v in wiki.values() if v['lang'] == 'en'}
    minors = sorted((c['id'] for c in CARDS if c['arcana'] == 'minor' and topics[c['id']]['mid']),
                    key=lambda i: (en.get(i, 0), i))
    anchor_b = minors[(len(minors) - 1) // 2]  # median (lower middle for an even count)
    majors = [c['id'] for c in CARDS if c['arcana'] == 'major' and c['id'] != ANCHOR_A and topics[c['id']]['mid']]
    rest = [m for m in minors if m != anchor_b]
    qs = [{'id': f'major-{i // 4 + 1}', 'anchor': ANCHOR_A, 'cards': [ANCHOR_A] + majors[i:i + 4]}
          for i in range(0, len(majors), 4)]
    qs += [{'id': f'minor-{i // 4 + 1}', 'anchor': anchor_b, 'cards': [anchor_b] + rest[i:i + 4]}
           for i in range(0, len(rest), 4)]
    qs.append({'id': 'bridge', 'anchor': ANCHOR_A, 'cards': [ANCHOR_A, anchor_b] + BRIDGE_REPEAT})
    return anchor_b, qs


def fetch_trends():
    tr = Trends()
    topics = topic_ids(tr)
    log('topics:', sum(1 for v in topics.values() if v['mid']), 'of', len(topics))
    anchor_b, qs = queries(topics)
    save(DATA / 'trends' / 'plan.json', {'anchor_a': ANCHOR_A, 'anchor_b': anchor_b, 'queries': qs})
    for q in qs:
        path = DATA / 'trends' / f'{q["id"]}.json'
        if path.exists():
            continue
        mids = [topics[c]['mid'] for c in q['cards']]
        ex = tr.explore(mids)
        widgets = {w['id']: w for w in ex['widgets']}
        ts = tr.widget('multiline', widgets['TIMESERIES'])
        geo = tr.widget('comparedgeo', widgets['GEO_MAP'])
        save(path, {'query': q, 'mids': mids, 'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'widget_ids': sorted(widgets),
                    'topics': [{'id': c, 'mid': m, **k} for c, m, k in zip(q['cards'], mids, _keywords(ex, mids))],
                    'timeseries': ts['default'], 'geo': geo['default']})
        log(f'{q["id"]}: saved ({len(geo["default"].get("geoMapData", []))} regions)')


def _keywords(ex, mids):
    """Name and type Trends gives each topic (validate checks the type is 'Tarot card')."""
    found = {k['keyword']: {'name': k.get('name'), 'type': k.get('type')}
             for k in ex.get('keywords') or [] if isinstance(k, dict) and k.get('keyword') in mids}
    return [found.get(m, {}) for m in mids]


def fetch_types():
    """Name and type Google gives each topic id (a single-topic explore lists them at the top level)."""
    path = DATA / 'trends' / 'types.json'
    out = load(path) if path.exists() else {}
    topics = load(DATA / 'trends' / 'topics.json')
    tr = Trends()
    for cid, t in topics.items():
        mid = t['mid']
        if not mid or cid in out:
            continue
        ex = tr.explore([mid])
        k = next((k for k in ex.get('keywords') or [] if k.get('keyword') == mid), {})
        out[cid] = {'mid': mid, 'name': k.get('name'), 'type': k.get('type')}
        save(path, out)
    log('types:', sum(1 for v in out.values() if (v.get('type') or '').lower() == 'tarot card'), 'tarot cards of',
        len(out))


# ---------------------------------------------------------------------------------------- compute
def _month_of_week(ts):
    """A Trends week (Sunday start) belongs to the month of its Thursday."""
    d = dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).date() + dt.timedelta(days=4)
    return f'{d.year}-{d.month:02d}'


def _spearman(xs, ys):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den


def fetch_repeat():
    """A5: the first majors query and the bridge pulled again in a fresh session."""
    tr = Trends()
    plan = load(DATA / 'trends' / 'plan.json')
    topics = load(DATA / 'trends' / 'topics.json')
    for q in plan['queries']:
        if q['id'] not in ('major-1', 'bridge'):
            continue
        path = DATA / 'trends' / 'repeat' / f'{q["id"]}.json'
        if path.exists():
            continue
        ex = tr.explore([topics[c]['mid'] for c in q['cards']])
        widgets = {w['id']: w for w in ex['widgets']}
        ts = tr.widget('multiline', widgets['TIMESERIES'])
        save(path, {'query': q, 'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'timeseries': ts['default']})
        log(f'repeat {q["id"]}: saved')


def fetch_terms(suffix='', folder='terms'):
    """A6: '<card> tarot' search terms (A7: '<card> tarot meaning'), chained on the High Priestess."""
    tr = Trends()
    pairs = [(c, f'{t}{suffix}') for c, t in TERM_CARDS]
    anchor, rest = pairs[0], pairs[1:]
    for i in range(0, len(rest), 4):
        group = [anchor] + rest[i:i + 4]
        path = DATA / 'trends' / folder / f'terms-{i // 4 + 1}.json'
        if path.exists():
            continue
        ex = tr.explore([t for _, t in group])
        widgets = {w['id']: w for w in ex['widgets']}
        ts = tr.widget('multiline', widgets['TIMESERIES'])
        save(path, {'cards': [c for c, _ in group], 'terms': [t for _, t in group],
                    'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'timeseries': ts['default']})
        log(f'{folder} {i // 4 + 1}: saved')


# ---------------------------------------------------------------------------------------- v2: meaning searches
ANCHOR_MINOR = 'knight-of-swords'
BRIDGE_V2 = ['the-fool', 'knight-of-swords', 'the-lovers', 'death', 'ace-of-cups']


def term_for(lang, cid):
    """The Trends term of a card: every name variant x every meaning phrase, joined with ' + ' (an OR)."""
    c = BY_ID[cid]
    if c['arcana'] == 'major':
        names = NAMES_V2[lang][c['number']]
    else:
        names = [c['name'].lower()]
    return ' + '.join(f'{n} {w}' for n in names for w in MEANING_WORDS[lang])


def plan_v2():
    majors = [c['id'] for c in CARDS if c['arcana'] == 'major']
    minors = [c['id'] for c in CARDS if c['arcana'] == 'minor']
    qs = []
    for lang in MEANING_WORDS:
        rest = [c for c in majors if c != ANCHOR_A]
        qs += [{'id': f'{lang}-major-{i // 4 + 1}', 'lang': lang, 'anchor': ANCHOR_A,
                'cards': [ANCHOR_A] + rest[i:i + 4]} for i in range(0, len(rest), 4)]
    rest = [c for c in minors if c != ANCHOR_MINOR]
    qs += [{'id': f'en-minor-{i // 4 + 1}', 'lang': 'en', 'anchor': ANCHOR_MINOR,
            'cards': [ANCHOR_MINOR] + rest[i:i + 4]} for i in range(0, len(rest), 4)]
    qs.append({'id': 'en-bridge', 'lang': 'en', 'anchor': ANCHOR_A, 'cards': BRIDGE_V2})
    for q in qs:
        q['terms'] = [term_for(q['lang'], c) for c in q['cards']]
    return qs


def fetch_v2():
    tr = Trends()
    qs = plan_v2()
    save(DATA / 'v2' / 'plan.json', {'queries': qs})
    for q in qs:
        path = DATA / 'v2' / f'{q["id"]}.json'
        if path.exists():
            continue
        ex = tr.explore(q['terms'])
        widgets = {w['id']: w for w in ex['widgets']}
        ts = tr.widget('multiline', widgets['TIMESERIES'])
        geo = tr.widget('comparedgeo', widgets['GEO_MAP']) if 'GEO_MAP' in widgets else {'default': {}}
        save(path, {'query': q, 'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'timeseries': ts['default'], 'geo': geo['default']})
        log(f'{q["id"]}: saved')


def fetch_v2_geo():
    """A2: the non-English Major Arcana queries again, restricted to each language's first country."""
    tr = Trends()
    for q in load(DATA / 'v2' / 'plan.json')['queries']:
        if q['lang'] == 'en' or '-major-' not in q['id']:
            continue
        geo = COUNTRY_LANG[q['lang']][0]
        path = DATA / 'v2' / 'geo' / f'{q["id"]}.json'
        if path.exists():
            continue
        req = {'comparisonItem': [{'keyword': t, 'geo': geo, 'time': f'{START} {END}'} for t in q['terms']],
               'category': 0, 'property': ''}
        ex = tr.get('explore', {'hl': 'en-US', 'tz': 0, 'req': json.dumps(req, separators=(',', ':'))})
        widgets = {w['id']: w for w in ex['widgets']}
        ts = tr.widget('multiline', widgets['TIMESERIES'])
        save(path, {'query': {**q, 'geo': geo}, 'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'timeseries': ts['default']})
        log(f'{q["id"]} in {geo}: saved')


def fetch_related():
    """A4: related queries of the four sky-card terms (English, worldwide)."""
    tr = Trends()
    for cid in ('the-moon', 'the-sun', 'the-star', 'the-world', 'the-hermit'):
        path = DATA / 'v2' / 'related' / f'{cid}.json'
        if path.exists():
            continue
        term = term_for('en', cid)
        ex = tr.explore([term])
        w = next(w for w in ex['widgets'] if w['id'] == 'RELATED_QUERIES')
        rel = tr.widget('relatedsearches', w)
        save(path, {'card': cid, 'term': term, 'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'related': rel['default']})
        log(f'related {cid}: saved')


SKY_FILTERS = {'the-moon': ' -full -new -sign -phase', 'the-sun': ' -sign', 'the-star': ' -sign', 'the-world': ' -day'}


def fetch_filters():
    """A4: each sky term with and without the minus words, against the Fool."""
    tr = Trends()
    for cid, minus in SKY_FILTERS.items():
        path = DATA / 'v2' / 'filters' / f'{cid}.json'
        if path.exists():
            continue
        terms = [term_for('en', ANCHOR_A), term_for('en', cid), term_for('en', cid) + minus]
        ex = tr.explore(terms)
        w = next(w for w in ex['widgets'] if w['id'] == 'TIMESERIES')
        ts = tr.widget('multiline', w)
        save(path, {'card': cid, 'terms': terms, 'fetched': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                    'timeseries': ts['default']})
        log(f'filters {cid}: saved')


# ---------------------------------------------------------------------------------------- v2: compute
STUDY_LANGS = list(MEANING_WORDS)


def _bounds(x, a):
    """ratio x/a with both whole-percent shares off by up to 0.5"""
    return max(x - 0.5, 0) / (a + 0.5), (x + 0.5) / max(a - 0.5, 0.5)


def rank_bounds(idx):
    """Best and worst rank of every card when ties are kept as ties."""
    vals = list(idx.values())
    return ({c: 1 + sum(1 for x in vals if x > v) for c, v in idx.items()},
            {c: sum(1 for x in vals if x >= v) for c, v in idx.items()})


def lang_entry(idx, where):
    ranked = sorted(idx.items(), key=lambda kv: (-kv[1], kv[0]))
    best, worst = rank_bounds(idx)
    top = ranked[0][1]
    leaders = sorted(c for c, v in idx.items() if v == top)
    return {'status': 'ok', 'where': where, 'index': {c: round(v, 2) for c, v in ranked},
            'leader': leaders[0] if len(leaders) == 1 else None, 'leaders': leaders,
            'rank': {c: i + 1 for i, (c, _) in enumerate(ranked)}, 'rank_best': best, 'rank_worst': worst}


def verdicts(langs):
    """H1, H2, H3, H7 over a reading of the languages; ties never count for a hypothesis (A3)."""
    ok = [l for l in STUDY_LANGS if langs[l]['status'] == 'ok']
    non_en = [l for l in STUDY_LANGS if l != 'en']
    sky = {'the-world', 'the-star', 'the-moon'}
    h1 = [l for l in non_en if langs[l]['status'] == 'ok' and langs[l]['leader'] in sky]
    h2 = [l for l in ok if langs[l]['rank_worst']['death'] <= 11]
    h3 = [l for l in ok if langs[l]['rank_best']['the-high-priestess'] > 5]
    leaders = sorted({langs[l]['leader'] for l in ok if langs[l]['leader']})
    return {
        'H1': {'verdict': 'holds' if len(h1) >= 4 else 'does not hold', 'value': f'{len(h1)} of {len(non_en)}',
               'langs': h1},
        'H2': {'verdict': 'holds' if len(h2) >= 6 else 'does not hold', 'value': f'{len(h2)} of 8', 'langs': h2},
        'H3': {'verdict': 'holds' if len(h3) >= 6 else 'does not hold', 'value': f'{len(h3)} of 8', 'langs': h3},
        'H7': {'verdict': 'holds' if len(leaders) >= 3 else 'does not hold', 'value': len(leaders),
               'leaders': leaders},
    }


def v1_topic_majors():
    """The abandoned v1 topic index of the Major Arcana (for the 'why not topics' comparison)."""
    out = {ANCHOR_A: 100.0}
    for f in sorted((DATA / 'trends').glob('major-*.json')):
        r = load(f)
        rows = [w for w in r['timeseries']['timelineData'] if _month_of_week(w['time']) in MONTHS]
        sm = [sum(w['value'][i] for w in rows) for i in range(len(r['query']['cards']))]
        for i, c in enumerate(r['query']['cards'][1:], start=1):
            out[c] = 100.0 * sm[i] / sm[0]
    return out


def compute():
    plan = load(DATA / 'v2' / 'plan.json')['queries']
    raw = {q['id']: load(DATA / 'v2' / f'{q["id"]}.json') for q in plan}

    def week_rows(r):
        return [w for w in r['timeseries'].get('timelineData', []) if _month_of_week(w['time']) in MONTHS]

    def sums(r):
        rows = week_rows(r)
        return {c: sum(w['value'][i] for w in rows) for i, c in enumerate(r['query']['cards'])}

    # -- English worldwide Major Arcana
    en_majors = {ANCHOR_A: 100.0}
    for qid, r in raw.items():
        if qid.startswith('en-major-'):
            sm = sums(r)
            for c in r['query']['cards'][1:]:
                en_majors[c] = 100.0 * sm[c] / sm[ANCHOR_A]

    # -- English: all 78 cards via the bridge
    bridge = sums(raw['en-bridge'])
    b_over_a = bridge[ANCHOR_MINOR] / bridge[ANCHOR_A]
    en = dict(en_majors)
    for qid, r in raw.items():
        if qid.startswith('en-minor-'):
            sm = sums(r)
            for c in r['query']['cards'][1:]:
                en[c] = 100.0 * sm[c] / sm[ANCHOR_MINOR] * b_over_a
    en[ANCHOR_MINOR] = 100.0 * b_over_a
    consistency = []
    for c in BRIDGE_V2[2:]:
        direct = 100.0 * bridge[c] / bridge[ANCHOR_A]
        consistency.append({'card': c, 'direct': round(direct, 2), 'chained': round(en[c], 2),
                            'ratio': round(en[c] / direct, 3) if direct else None})
    en_ranked = sorted(en.items(), key=lambda kv: (-kv[1], kv[0]))
    en_rank = {c: i + 1 for i, (c, _) in enumerate(en_ranked)}
    total = sum(en.values())
    majors_share = 100 * sum(v for c, v in en.items() if BY_ID[c]['arcana'] == 'major') / total
    suits = []
    for suit, _, _ in SUITS:
        vals = [en[c['id']] for c in CARDS if c['suit'] == suit]
        suits.append({'suit': suit, 'cards': len(vals), 'mean': round(statistics.mean(vals), 2),
                      'sum': round(sum(vals), 2)})

    # -- countries: each in its main language, Major Arcana chained on The Fool
    countries = []
    for lang, isos in COUNTRY_LANG.items():
        qids = sorted(q for q in raw if q.startswith(f'{lang}-major-'))
        geos = {q: {g['geoCode']: g for g in raw[q]['geo'].get('geoMapData', [])} for q in qids}
        for iso in isos:
            rows = [geos[q].get(iso) for q in qids]
            if not all(row and row['hasData'][0] and row['value'][0] > 0 for row in rows):
                continue
            idx, lo, hi = {ANCHOR_A: 100.0}, {ANCHOR_A: 100.0}, {ANCHOR_A: 100.0}
            for q, row in zip(qids, rows):
                for i, c in enumerate(raw[q]['query']['cards'][1:], start=1):
                    if row['hasData'][i]:
                        idx[c] = 100.0 * row['value'][i] / row['value'][0]
                        lo[c], hi[c] = (100 * x for x in _bounds(row['value'][i], row['value'][0]))
            ranked = sorted(idx.items(), key=lambda kv: (-kv[1], kv[0]))
            lead = ranked[0][0]
            countries.append({'iso': iso, 'name': rows[0]['geoName'], 'lang': lang, 'leader': lead,
                              'runner_up': ranked[1][0], 'tie': ranked[0][1] == ranked[1][1],
                              'clear': all(lo[lead] > hi[c] for c in idx if c != lead),
                              'top3': [c for c, _ in ranked[:3]],
                              'death_rank': [c for c, _ in ranked].index('death') + 1,
                              'index': {c: round(v, 1) for c, v in ranked[:8]},
                              'full': {c: round(v, 2) for c, v in ranked}})
    countries.sort(key=lambda c: c['name'])

    # -- languages: English worldwide, the rest in their first country (A2)
    langs = {}
    for lang in STUDY_LANGS:
        if lang == 'en':
            langs[lang] = lang_entry(dict(en_majors), 'worldwide')
            continue
        where = COUNTRY_LANG[lang][0]
        row = next((x for x in countries if x['iso'] == where), None)
        langs[lang] = (lang_entry(dict(row['full']), where) if row else
                       {'status': 'too few searches', 'where': where, 'index': {}, 'leader': None, 'leaders': [],
                        'rank': {}, 'rank_best': {}, 'rank_worst': {}})
    ok_langs = [l for l in STUDY_LANGS if langs[l]['status'] == 'ok']

    # the pre-registered reading: every language from its worldwide weekly series
    langs_pre = {}
    for lang in STUDY_LANGS:
        src = [r for qid, r in raw.items() if qid.startswith(f'{lang}-major-')]
        if any(sums(r)[ANCHOR_A] == 0 for r in src):
            langs_pre[lang] = {'status': 'too few searches', 'where': 'worldwide', 'index': {}, 'leader': None,
                               'leaders': [], 'rank': {}, 'rank_best': {}, 'rank_worst': {}}
            continue
        idx = {ANCHOR_A: 100.0}
        for r in src:
            sm = sums(r)
            for c in r['query']['cards'][1:]:
                idx[c] = 100.0 * sm[c] / sm[ANCHOR_A]
        langs_pre[lang] = lang_entry(idx, 'worldwide')

    # -- seasons (English Major Arcana): November-March against April-October
    seasons = {}
    for name, months in (('nov_mar', MONTHS[:5]), ('apr_oct', MONTHS[5:])):
        idx = {ANCHOR_A: 100.0}
        for qid, r in raw.items():
            if qid.startswith('en-major-'):
                rows = [w for w in week_rows(r) if _month_of_week(w['time']) in months]
                a = sum(w['value'][0] for w in rows)
                for i, c in enumerate(r['query']['cards'][1:], start=1):
                    idx[c] = 100.0 * sum(w['value'][i] for w in rows) / a
        seasons[name] = [{'card': c, 'index': round(x, 1)} for c, x in
                         sorted(idx.items(), key=lambda kv: (-kv[1], kv[0]))[:5]]

    # -- months (English): the Lovers against the Fool
    monthly = {}
    for qid, r in raw.items():
        if not qid.startswith('en-major-'):
            continue
        rows = week_rows(r)
        for i, c in enumerate(r['query']['cards'][1:], start=1):
            per = {}
            for m in MONTHS:
                mr = [w for w in rows if _month_of_week(w['time']) == m]
                a = sum(w['value'][0] for w in mr)
                per[m] = round(sum(w['value'][i] for w in mr) / a, 4) if a else None
            monthly[c] = per

    # -- Wikipedia with redirects, study languages only
    wiki_raw = load(DATA / 'wiki' / 'pageviews_v2.json')
    wl = {}
    for v in wiki_raw.values():
        if v['lang'] in STUDY_LANGS:
            wl.setdefault(v['lang'], {})[v['card']] = sum(v['monthly'].get(m, 0) for m in MONTHS)
    wiki = []
    for lang in STUDY_LANGS:
        views = wl.get(lang, {})
        tot = sum(views.values())
        ranked = sorted(views.items(), key=lambda kv: (-kv[1], kv[0]))
        wiki.append({'lang': lang, 'articles': len(views), 'views': tot, 'leader': ranked[0][0],
                     'top5': [{'card': c, 'share': round(100 * n / tot, 2)} for c, n in ranked[:5]]})
    en_wiki = wl['en']
    both = [c for c in en if c in en_wiki]
    rho = _spearman([en[c] for c in both], [en_wiki[c] for c in both])

    # -- v1 topics against v2 meaning (English Major Arcana)
    v1 = v1_topic_majors()
    majors_ids = [c['id'] for c in CARDS if c['arcana'] == 'major']
    rho_v1 = _spearman([v1[c] for c in majors_ids], [en_majors[c] for c in majors_ids])

    # -- hypotheses
    v = verdicts(langs)
    v_pre = verdicts(langs_pre)
    v['H4'] = {'verdict': 'holds' if majors_share < 50 else 'does not hold', 'value': round(100 - majors_share, 1)}
    by_mean = sorted(suits, key=lambda x: -x['mean'])
    first, last = by_mean[0]['suit'] == 'Cups', by_mean[-1]['suit'] == 'Pentacles'
    v['H5'] = {'verdict': 'holds' if first and last else ('mixed' if first or last else 'does not hold'),
               'value': [x['suit'] for x in by_mean]}
    v['H6'] = {'verdict': 'holds' if BY_ID[en_ranked[0][0]]['arcana'] == 'major' else 'does not hold',
               'value': en_ranked[0][0]}
    per = {m: x for m, x in monthly['the-lovers'].items() if x is not None}
    peak = max(per, key=per.get)
    v['H8'] = {'verdict': 'holds' if peak == '2026-02' else 'does not hold', 'value': peak}
    v['H9'] = {'verdict': 'holds' if rho < 0.3 else 'does not hold', 'value': round(rho, 3), 'n': len(both)}

    sky_filters = {}
    for cid in SKY_FILTERS:
        f = DATA / 'v2' / 'filters' / f'{cid}.json'
        if f.exists():
            d = load(f)
            rows_ = [w for w in d['timeseries']['timelineData'] if _month_of_week(w['time']) in MONTHS]
            sm = [sum(w['value'][i] for w in rows_) for i in range(3)]
            sky_filters[cid] = {'term': d['terms'][2], 'raw': round(100 * sm[1] / sm[0], 1),
                                'filtered': round(100 * sm[2] / sm[0], 1), 'kept': round(100 * sm[2] / sm[1], 1)}

    cards_out = [{'id': c['id'], 'name': c['name'], 'arcana': c['arcana'], 'suit': c['suit'],
                  'en': round(en[c['id']], 2) if en.get(c['id']) is not None else None,
                  'en_rank': en_rank.get(c['id']), 'wiki_en': en_wiki.get(c['id']),
                  'v1_topic': round(v1[c['id']], 2) if c['id'] in v1 else None,
                  'leads_countries': sum(1 for x in countries if x['leader'] == c['id'])} for c in CARDS]
    out = {'window': [START, END], 'langs': langs, 'ok_langs': ok_langs,
           'terms': {l: {c['id']: term_for(l, c['id']) for c in CARDS if c['arcana'] == 'major'} for l in STUDY_LANGS},
           'b_over_a': round(b_over_a, 4), 'consistency': consistency, 'majors_share_en': round(majors_share, 1),
           'suits': suits, 'cards': cards_out, 'countries': countries, 'monthly': monthly, 'wiki': wiki,
           'sky_filters': sky_filters, 'spearman_wiki': round(rho, 3), 'spearman_v1': round(rho_v1, 3),
           'fetched': sorted({r['fetched'][:10] for r in raw.values()}),
           'hypotheses': {h: {'text': HYPOTHESES[h], **v[h]} for h in HYPOTHESES},
           'hypotheses_preregistered_reading': v_pre, 'langs_preregistered_reading': langs_pre, 'seasons': seasons,
           'hypotheses_v1': HYPOTHESES_V1, 'added_after_count': ADDED_AFTER_COUNT}
    save(WORK / 'computed.json', out)
    for l in STUDY_LANGS:
        d = langs[l]
        log(l, d['where'], d['status'], d['leader'], 'death', d['rank'].get('death'),
            'hp', d['rank'].get('the-high-priestess'), [c for c in list(d['index'])[:5]])
    log('countries', len(countries), 'en top', [(c, round(x)) for c, x in en_ranked[:5]], 'majors', round(majors_share, 1))
    for h in HYPOTHESES:
        log(h, v[h]['verdict'], v[h]['value'])
    return out


def validate():
    c = load(WORK / 'computed.json')
    checks = []

    def check(name, ok, detail=''):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})
        log(('OK  ' if ok else 'FAIL'), name, detail)

    for lang, d in c['langs'].items():
        if d['status'] != 'ok':
            check(f'{lang}: too few searches in {d["where"]}, left out', True)
            continue
        zero = [k for k, x in d['index'].items() if not x]
        check(f'{lang}: every Major Arcana card has meaning searches in {d["where"]}', not zero, f'zero: {zero}')
    check('English and at least 4 other languages have enough searches', 'en' in c['ok_langs'] and
          len(c['ok_langs']) >= 5, str(c['ok_langs']))
    for card, row in c['sky_filters'].items():
        check(f'sky card {card} keeps most of its searches without lunar/sign queries (A4)', row['kept'] >= 80,
              f'kept {row["kept"]} %')
    missing = [x['id'] for x in c['cards'] if x['en'] is None or x['en'] <= 0]
    check('English: all 78 cards have meaning searches', not missing, f'missing: {missing}')
    for row in c['consistency']:
        check(f'bridge consistency {row["card"]}', row['ratio'] and 0.85 <= row['ratio'] <= 1.15,
              f'chained/direct = {row["ratio"]}')
    check('at least 15 countries read in their language', len(c['countries']) >= 15, str(len(c['countries'])))
    check('every study language has Wikipedia articles for the 22 Major Arcana',
          all(w['articles'] >= 22 for w in c['wiki']), str([(w['lang'], w['articles']) for w in c['wiki']]))
    check('verdicts present', all('verdict' in h for h in c['hypotheses'].values()))
    ok = all(x['ok'] for x in checks)
    save(WORK / 'validated.json', {'ok': ok, 'checks': checks,
                                   'at': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')})
    log('validate:', 'passed' if ok else 'FAILED')
    if not ok:
        sys.exit(1)


def export():
    val = WORK / 'validated.json'
    if not val.exists() or not load(val)['ok']:
        sys.exit('validate has not passed: run validate first')
    c = load(WORK / 'computed.json')
    page = dict(c)
    page['countries'] = [{k: x for k, x in row.items() if k != 'full'} for row in c['countries']]
    page['map'] = svg_world(min_step=2.4)
    page['validated'] = load(val)
    page['sources'] = [
        {'name': 'Google Trends: search terms, interest over time and compared breakdown by region',
         'url': 'https://trends.google.com/trends/', 'licence': 'cite as Google Trends'},
        {'name': 'Wikimedia pageviews API (user agent, monthly), article plus its redirects',
         'url': 'https://wikitech.wikimedia.org/wiki/Analytics/AQS/Pageviews', 'licence': 'CC0'},
        {'name': 'Natural Earth 1:110m admin 0 countries, v5.1.2',
         'url': 'https://www.naturalearthdata.com/', 'licence': 'public domain'},
    ]
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(page, ensure_ascii=False, separators=(',', ':')) + '\n')
    rows = ['scope,area,card,card_name,arcana,suit,value,unit,term']
    for lang, d in c['langs'].items():
        for cid, val_ in d['index'].items():
            b = BY_ID[cid]
            rows.append(f'language,{lang}:{d["where"]},{cid},{b["name"]},{b["arcana"]},,{val_},meaning_searches_the_fool_100,'
                        f'"{c["terms"][lang][cid]}"')
    for x in c['cards']:
        if x['arcana'] == 'minor':
            rows.append(f'language,en,{x["id"]},{x["name"]},minor,{x["suit"]},{x["en"]},'
                        f'meaning_searches_the_fool_100,"{term_for("en", x["id"])}"')
    for country in c['countries']:
        for cid, val_ in country['full'].items():
            b = BY_ID[cid]
            rows.append(f'country,{country["iso"]},{cid},{b["name"]},{b["arcana"]},,{val_},'
                        f'meaning_searches_the_fool_100_in_{country["lang"]},')
    wiki = load(DATA / 'wiki' / 'pageviews_v2.json')
    for v in sorted(wiki.values(), key=lambda v: (v['lang'], v['card'])):
        if v['lang'] not in STUDY_LANGS:
            continue
        b = BY_ID[v['card']]
        rows.append(f'wikipedia,{v["lang"]},{v["card"]},{b["name"]},{b["arcana"]},{b["suit"] or ""},'
                    f'{sum(v["monthly"].get(m, 0) for m in MONTHS)},pageviews_with_redirects_{START}_{END},')
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    CSV_OUT.write_text('\n'.join(rows) + '\n')
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log('export:', JSON_OUT, f'{JSON_OUT.stat().st_size // 1024} KB;', CSV_OUT, len(rows) - 1, 'rows')


# ---------------------------------------------------------------------------------------- world map
NE_URL = ('https://raw.githubusercontent.com/nvkelso/natural-earth-vector/v5.1.2/geojson/'
          'ne_110m_admin_0_countries.geojson')


def fetch_map():
    path = DATA / 'map' / 'ne_110m_admin_0_countries.geojson'
    if path.exists():
        return
    body = wget(NE_URL)
    if not body:
        sys.exit('Natural Earth file not found')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    log('map: saved', len(body), 'bytes')


def equal_earth(lon, lat):
    """Equal Earth projection (Šavrič, Patterson, Jenny 2018), unit sphere."""
    a1, a2, a3, a4 = 1.340264, -0.081106, 0.000893, 0.003796
    m = math.sqrt(3) / 2
    lam, phi = math.radians(lon), math.radians(lat)
    th = math.asin(m * math.sin(phi))
    t2, t6 = th * th, th ** 6
    x = lam * math.cos(th) / (m * (a1 + 3 * a2 * t2 + t6 * (7 * a3 + 9 * a4 * t2)))
    y = th * (a1 + a2 * t2 + t6 * (a3 + a4 * t2))
    return x, y


def svg_world(width=1000.0, min_step=0.9):
    """Country outlines as SVG path strings keyed by ISO 3166-1 alpha-2 (Antarctica left out)."""
    geo = load(DATA / 'map' / 'ne_110m_admin_0_countries.geojson')
    xmax, _ = equal_earth(180, 0)
    _, ymax = equal_earth(0, 90)
    k = width / (2 * xmax)
    height = 2 * ymax * k
    out = {}
    for f in geo['features']:
        pr = f['properties']
        iso = pr.get('ISO_A2_EH') or pr.get('ISO_A2')
        if pr.get('CONTINENT') == 'Antarctica' or not iso or iso == '-99':
            continue
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        parts = []
        for poly in polys:
            for ring in poly:
                pts, last = [], None
                for lon, lat in ring:
                    x, y = equal_earth(lon, lat)
                    px, py = (x + xmax) * k, (ymax - y) * k
                    if last is None or abs(px - last[0]) + abs(py - last[1]) >= min_step:
                        pts.append((px, py))
                        last = (px, py)
                if len(pts) >= 4:  # tiny islands drop out at this scale
                    parts.append('M' + 'L'.join(f'{round(x)},{round(y)}' for x, y in pts) + 'Z')
        if parts:
            out[iso] = {'name': pr.get('NAME_EN') or pr.get('NAME'), 'd': ''.join(parts)}
    # Frame: the land, not the empty ocean. Hawaii alone would push the left edge 60 units out (the map looked
    # shifted right), so the frame is the extent of rings with at least 10 points, plus a small margin.
    xs, ys = [], []
    for c in out.values():
        for ring in c['d'].split('Z'):
            pts = [tuple(map(int, p.split(','))) for p in ring.lstrip('M').split('L') if p]
            if len(pts) >= 10:
                xs += [x for x, _ in pts]
                ys += [y for _, y in pts]
    pad = 6
    x0, y0 = max(min(xs) - pad, 0), max(min(ys) - pad, 0)
    x1, y1 = min(max(xs) + pad, round(width)), min(max(ys) + pad, round(height))
    return {'width': round(width), 'height': round(height, 1), 'viewBox': f'{x0} {y0} {x1 - x0} {y1 - y0}',
            'countries': out}


# ---------------------------------------------------------------------------------------- main
STEPS = {'fetch-wiki': lambda: fetch_wiki(), 'fetch-trends': lambda: fetch_trends(), 'fetch-map': lambda: fetch_map(), 'fetch-v2': lambda: fetch_v2(), 'fetch-v2-geo': lambda: fetch_v2_geo(), 'fetch-related': lambda: fetch_related(), 'fetch-filters': lambda: fetch_filters(), 'fetch-wiki-redirects': lambda: fetch_wiki_redirects(), 'fetch-types': lambda: fetch_types(), 'fetch-repeat': lambda: fetch_repeat(), 'fetch-terms': lambda: fetch_terms(), 'fetch-meaning': lambda: fetch_terms(' meaning', 'meaning'), 'compute': lambda: compute(), 'validate': lambda: validate(), 'export': lambda: export()}

if __name__ == '__main__':
    if len(sys.argv) != 2 or sys.argv[1] not in STEPS:
        sys.exit('usage: tarot_card_search.py ' + '|'.join(STEPS))
    STEPS[sys.argv[1]]()
