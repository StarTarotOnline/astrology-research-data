#!/usr/bin/env python3
"""On which weekday were ships launched, and were ships launched on a Friday lost more often?

The sailors' rule "never launch a ship on a Friday" is old and well documented as folklore. This script
counts it in the calendar: every ship in Wikidata with a launch date known to the day, 1800-2025, and
the weekday of that date. It then asks the question every reader asks next - did the Friday ships sink
more often? - with two independent definitions of a loss.

Sources (all free):
  * Wikidata, through the QLever SPARQL endpoint https://qlever.dev/api/wikidata (CC0):
    launch (P793 = Q596643 ship launching, qualifier P585), keel laying (Q14592615) and commissioning
    (Q14475832) dates; operators (P137 with P580/P582); ship classes (P31 and the P279* closure);
    loss events on P793 (sinking, shipwrecking, destruction, missing in action, grounding, capsizing...)
    with their cause qualifiers, P31 = shipwreck, P770 cause of destruction; and two controls that have
    nothing to do with ships: dates of official opening (P1619) and dates of birth of humans (P569).
  * English Wikipedia's chronological "List of shipwrecks in <month> <year>" pages (CC BY-SA), read through
    the MediaWiki API: the ship named in each row (its ship cell). That is the second, independent loss record.

Only ship LOSSES are counted. The script never reads casualty data (P1120 and the like), and the page
never names victims.

Steps (raw data goes to $SHIP_LAUNCH_DATA, default ~/startarot-data/ship-launch-days, about 100 MB):
    python3 ship_launch_days.py fetch      # QLever + Wikipedia API (about half an hour, polite pauses)
    python3 ship_launch_days.py compute    # -> $SHIP_LAUNCH_DATA/computed.json
    python3 ship_launch_days.py validate   # sanity checks + the registered hypotheses -> validation.json
    python3 ship_launch_days.py export     # JSON for the page + CSV + a copy of this script (only if valid)

Method in one paragraph. A weekday's "launch ratio" is its number of launches divided by the mean of
Monday-Thursday in the same years (the 95 % interval treats both as Poisson counts). The 13th of the month
is compared with the mean of days 2-12 and 14-28 the same way. Losses: one row per ship; a ship counts as
lost (Wikidata) if a loss event is not followed by any sign of later service, deliberate sinkings
(scuttling, targets, weapons tests) are kept apart and never count as bad luck; or (Wikipedia) if a row of a
shipwreck list from the ship's launch month on names it in its ship cell (see ADDED_AFTER_COUNT A1). Friday ships are compared with
ships launched on other days of the same launch year (the same quarter during 1914-18 and 1939-45), the
same operator group and the same broad type: Mantel-Haenszel odds ratio with the Robins-Breslow-Greenland
interval, and a permutation test that shuffles the weekday inside those strata. The crude comparison is
reported too, because it misleads in an instructive way: Friday launches became common only after 1946,
when far fewer ships were lost, so a raw count makes Friday ships look luckier than they were.

Exploration before registration (16.11.2026, an earlier pull of the same sources): 20,483 ships with a
day-precision launch date; in 1860-1899 Friday had 6.5 % of launches and Saturday 26.6 %; the 13th was not
avoided before 1900 and was avoided in 1900-1945; two independent loss counts found no Friday excess once
ships were compared within year, navy and type, while the crude count made Friday ships look luckier.
The hypotheses below were therefore written AFTER that exploration, and are marked [seen in exploration]
where the number was already known. What the registration fixes is the definitions, thresholds and
comparisons, before the final count on a fresh pull; the page says so.
"""

import csv
import datetime as dt
import gzip
import hashlib
import http.client
import json
import math
import os
import random
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'ship-launch-days'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'ship_launch_days.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('SHIP_LAUNCH_DATA', Path.home() / 'startarot-data' / 'ship-launch-days'))
UA = 'ship-launch-days/1.0 (open research script; python urllib)'
QLEVER = 'https://qlever.dev/api/wikidata'
WP_API = 'https://en.wikipedia.org/w/api.php'

# ---------------------------------------------------------------------------------------------------------
# Registered hypotheses. Their text is not edited after registration (the data test compares it with the
# registered copy); anything decided after the count goes to ADDED_AFTER_COUNT.
HYPOTHESES = {
    'H1': '[seen in exploration] In 1860-1899 Friday launches are below half of the Monday-Thursday mean: '
          'ratio < 0.50 and the upper end of its 95 % interval < 0.60.',
    'H2': '[seen in exploration] The Friday dip in launches is deeper than the Friday dip in official '
          'openings (P1619) of the same years 1860-1899: launch ratio / opening ratio < 0.75.',
    'H3': '[seen in exploration] Wikidata dates carry no weekday artefact: Friday births of humans in '
          '1860-1899 (day precision) are within 0.97-1.03 of the Monday-Thursday mean.',
    'H4': '[seen in exploration] The avoidance faded: in 1946-1959 the Friday launch ratio is >= 0.80.',
    'H5': '[seen in exploration] The 13th of the month: launches on the 13th are within 0.80-1.25 of the '
          'mean of days 2-12 and 14-28 in 1800-1899, and below 0.70 (upper 95 % end < 0.75) in 1900-1945.',
    'H6': '[seen in exploration] Ships launched on a Friday were not lost more often: Friday vs '
          'Monday-Thursday, any non-deliberate loss, Mantel-Haenszel odds ratio over launch year (quarter in '
          '1914-18 and 1939-45) x operator group x type is <= 1.00 with the upper 95 % end < 1.25, in BOTH '
          'sources (Wikidata loss records; Wikipedia shipwreck lists).',
    'H7': '[seen in exploration] Friday vs Saturday, the favourite launch day, same strata and outcome: odds '
          'ratio within 0.80-1.25 in both sources.',
    'H8': 'Keel laying, the other start of a ship, was avoided on Fridays too: keel-laying Friday ratio in '
          '1860-1899 < 0.80 (the 1800-1945 figure, 0.62, was seen in exploration; 1860-1899 was not).',
    'H9': 'Commissioning, a paperwork date set by navies, was avoided less than launching: in 1860-1899 the '
          'commissioning Friday ratio exceeds the launch Friday ratio by at least 0.20.',
    'H10': 'The Royal Navy alone shows it: Royal Navy launches 1860-1899 have a Friday ratio < 0.60.',
}
HYPOTHESES_SHA256 = '402abddb'  # first 8 hex of sha256(json.dumps(HYPOTHESES, sort_keys=True)); set at registration
ADDED_AFTER_COUNT = {
    'A1': '[after count] The Wikipedia source first counted every link on a shipwreck-list page. That also '
          'catches ships named in the description of someone else\'s loss (the submarine that fired, the ship '
          'that rescued the crew): 45 % of Monday-Thursday ships came out as "listed". The source now counts only '
          'the ship cell of each row ({{shipwreck list item|ship=...}} or the first table cell), as the '
          'exploration did. The registered hypotheses are unchanged.',
}

# ---------------------------------------------------------------------------------------------------------
GREGORIAN = 'Q1985727'
LAUNCH, KEEL, COMMISSION, DECOM = 'Q596643', 'Q14592615', 'Q14475832', 'Q7497952'
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
PERIODS = [(1800, 1839), (1840, 1859), (1860, 1879), (1880, 1899), (1900, 1913), (1914, 1918), (1919, 1938),
           (1939, 1945), (1946, 1959), (1960, 1979), (1980, 1999), (2000, 2025)]
DECADES = [(y, y + 9) for y in range(1800, 2030, 10)]
WW = [(dt.date(1914, 7, 28), dt.date(1918, 11, 11)), (dt.date(1939, 9, 1), dt.date(1945, 9, 2))]
SEED = 20261116
NPERM = 2000

# Loss vocabulary (labels checked 16.11.2026). Terminal events end a ship; incidents do only when no sign of
# later service follows; deliberate sinkings are kept apart.
TERMINAL = {
    'Q30880545': 'sinking', 'Q906512': 'shipwrecking', 'Q17781833': 'destruction', 'Q2344557': 'missing in action',
    'Q1708441': 'ship loss', 'Q20888800': 'loss', 'Q852190': 'shipwreck', 'Q112613829': 'wreck',
    'Q3030513': 'disappearance', 'Q67155205': 'ship abandonment',
    'Q41767780': 'SS Athenia sinking', 'Q5551560': 'sinking of the RMS Lusitania',
    'Q112913932': 'sinking of the French submarine Surcouf', 'Q138567686': 'sinking of IRIS Dena',
    'Q460731': 'sinking of the Rainbow Warrior', 'Q47345655': 'Sanchi oil tanker collision',
    'Q4394421': 'sinking of the Rigel', 'Q3656148': 'Deepwater Horizon explosion',
    'Q98138630': 'MV Wakashio disaster', 'Q111767806': 'Eastland disaster',
}
INCIDENT = {
    'Q14920473': 'grounding', 'Q1522772': 'capsizing', 'Q179057': 'explosion', 'Q50295027': 'torpedo attack',
    'Q168983': 'conflagration', 'Q2192508': 'ship collision', 'Q238053': 'collision', 'Q352070': 'collision',
    'Q3196': 'fire', 'Q83858': 'ramming', 'Q111034471': 'missile strike', 'Q2235325': 'maritime accident',
    'Q16529727': 'nautical accident', 'Q171558': 'accident',
}
SCUTTLE = {'Q1786766': 'scuttling', 'Q699527': 'scuttling of the German fleet at Scapa Flow'}
LOSS_EVENTS = {**TERMINAL, **INCIDENT, **SCUTTLE}
# Events after a loss that do not show the ship survived (wreck found, salvage, scrapping, paperwork).
POST_LOSS = {'Q111177852', 'Q38131096', 'Q12772819', DECOM, 'Q49642078', 'Q336332', 'Q9393330', 'Q7497950',
             'Q820382', 'Q107281362', 'Q107281304', 'Q56651571', 'Q29933838', 'Q217901', 'Q1668049'}
# Causes that make a sinking deliberate (scuttling, target ship, weapons tests, Regenbogen, Deadlight...).
DELIBERATE_CAUSE = {'Q1786766', 'Q566859', 'Q660865', 'Q199028', 'Q569545', 'Q210112', 'Q451967', 'Q80594',
                    'Q357104', 'Q699527', 'Q1650581', 'Q794050'}
NOT_A_LOSS_CAUSE = {'Q336332', 'Q49642078'}  # ship breaking, striking: scrapped, not lost
CAUSE_QUALIFIERS = ('P1478', 'P828', 'P770', 'P1542', 'P1534')

# Broad ship types from the P31 / P279* closure; first match wins.
TYPE_ROOTS = {
    'submarine': {'Q2811'},
    'battleship_cruiser': {'Q182531', 'Q104843', 'Q214190'},
    'destroyer_escort': {'Q174736', 'Q1499623', 'Q161705', 'Q170013', 'Q324233', 'Q3057965', 'Q744967'},
    'other_warship': {'Q2031121', 'Q177597'},
    'merchant_passenger': {'Q848944', 'Q105999', 'Q2055880', 'Q697196', 'Q14970', 'Q25653', 'Q39804',
                           'Q15276', 'Q17210'},
}
WARSHIP_TYPES = {'submarine', 'battleship_cruiser', 'destroyer_escort', 'other_warship'}
IGNORE_CLASSES = {'Q852190', 'Q906512', 'Q575727', 'Q130326199'}
NAVY_MIN_SHIPS = 50

PREFIXES = """PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX ps: <http://www.wikidata.org/prop/statement/>
PREFIX pq: <http://www.wikidata.org/prop/qualifier/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX pqv: <http://www.wikidata.org/prop/qualifier/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <http://schema.org/>
"""
COHORT = '{ SELECT DISTINCT ?ship WHERE { ?ship p:P793 ?s0 . ?s0 ps:P793 wd:Q596643 . } }'


def event_dates_query(event):
    return f"""SELECT ?ship ?t ?prec ?cal WHERE {{
  ?ship p:P793 ?st . ?st ps:P793 wd:{event} . ?st pqv:P585 ?v .
  ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec ; wikibase:timeCalendarModel ?cal . }}"""


QUERIES = {
    'launch': event_dates_query(LAUNCH),
    'keel': event_dates_query(KEEL),
    'commission': event_dates_query(COMMISSION),
    'events': f"""SELECT ?ship ?sid ?ev ?t ?prec ?t2 ?prec2 WHERE {{ {COHORT}
  ?ship p:P793 ?st . ?st ps:P793 ?ev .
  OPTIONAL {{ ?st pqv:P585 ?v . ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec . }}
  OPTIONAL {{ ?st pqv:P580 ?v2 . ?v2 wikibase:timeValue ?t2 ; wikibase:timePrecision ?prec2 . }}
  BIND(STRAFTER(STR(?st), "statement/") AS ?sid) }}""",
    'event_quals': f"""SELECT ?ship ?st ?q ?val WHERE {{ {COHORT}
  VALUES ?q {{ pq:P1478 pq:P828 pq:P770 pq:P1542 pq:P1534 pq:P710 }}
  ?ship p:P793 ?st . ?st ?q ?val . }}""",
    'p31': f"""SELECT ?ship ?c ?t ?prec WHERE {{ {COHORT}
  ?ship p:P31 ?st . ?st ps:P31 ?c .
  OPTIONAL {{ ?st pqv:P580 ?v . ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec . }} }}""",
    'classmap': f"""SELECT ?c ?root WHERE {{
  {{ SELECT DISTINCT ?c WHERE {{ ?ship p:P793 ?s0 . ?s0 ps:P793 wd:Q596643 . ?ship wdt:P31 ?c . }} }}
  VALUES ?root {{ {' '.join('wd:' + r for roots in TYPE_ROOTS.values() for r in sorted(roots))} }}
  ?c wdt:P279* ?root . }}""",
    'operators': f"""SELECT ?ship ?op ?t1 ?t2 WHERE {{ {COHORT}
  ?ship p:P137 ?st . ?st ps:P137 ?op .
  OPTIONAL {{ ?st pq:P580 ?t1 }} OPTIONAL {{ ?st pq:P582 ?t2 }} }}""",
    'opmap': """SELECT ?op ?l ?navy ?mil WHERE {
  { SELECT DISTINCT ?op WHERE { ?ship p:P793 ?s0 . ?s0 ps:P793 wd:Q596643 . ?ship wdt:P137 ?op . } }
  OPTIONAL { ?op rdfs:label ?l FILTER(LANG(?l) = "en") }
  OPTIONAL { ?op wdt:P31/wdt:P279* wd:Q4508 . BIND(1 AS ?navy) }
  OPTIONAL { ?op wdt:P31/wdt:P279* ?m . VALUES ?m { wd:Q781132 wd:Q772547 wd:Q176799 } BIND(1 AS ?mil) } }""",
    'end': f"""SELECT ?ship ?p ?t ?prec WHERE {{ {COHORT}
  {{ ?ship p:P730 ?st . ?st psv:P730 ?v . BIND("P730" AS ?p) }} UNION
  {{ ?ship p:P576 ?st . ?st psv:P576 ?v . BIND("P576" AS ?p) }}
  ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec . }}""",
    'p770': f"""SELECT ?ship ?val WHERE {{ {COHORT} ?ship wdt:P770 ?val . }}""",
    'names': f"""SELECT ?ship ?label ?links ?title WHERE {{ {COHORT}
  OPTIONAL {{ ?ship rdfs:label ?label FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?ship wikibase:sitelinks ?links }}
  OPTIONAL {{ ?article schema:about ?ship ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?title . }} }}""",
    'openings': """SELECT ?x ?t ?cal WHERE {
  ?x p:P1619 ?st . ?st psv:P1619 ?v .
  ?v wikibase:timeValue ?t ; wikibase:timePrecision 11 ; wikibase:timeCalendarModel ?cal .
  FILTER(YEAR(?t) >= 1800 && YEAR(?t) <= 1945) }""",
    'births': """SELECT ?t WHERE {
  ?h wdt:P31 wd:Q5 ; p:P569 ?st . ?st psv:P569 ?v .
  ?v wikibase:timeValue ?t ; wikibase:timePrecision 11 ; wikibase:timeCalendarModel wd:Q1985727 .
  FILTER(YEAR(?t) >= 1860 && YEAR(?t) <= 1899) }""",
}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------------- HTTP
def http_post(url, data, accept, timeout=600, tries=7, pause=1.0):
    body = urllib.parse.urlencode(data).encode()
    delay = 5.0
    for i in range(tries):
        req = urllib.request.Request(url, data=body, method='POST', headers={
            'User-Agent': UA, 'Accept': accept, 'Accept-Encoding': 'gzip',
            'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
            time.sleep(pause)
            return raw
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and i < tries - 1:
                ra = e.headers.get('Retry-After')
                time.sleep(float(ra) if ra and ra.isdigit() else delay)
                delay *= 2
                continue
            raise RuntimeError(f'HTTP {e.code} from {url}: {e.read()[:300]!r}') from e
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.IncompleteRead) as e:
            if i < tries - 1:
                log(f'network error {e}, retry in {delay:.0f}s')
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError('unreachable')


def wp(params):
    p = {**params, 'format': 'json', 'formatversion': '2', 'maxlag': '5'}
    for _ in range(10):
        d = json.loads(http_post(WP_API, p, 'application/json', timeout=120, pause=0.5))
        if d.get('error', {}).get('code') == 'maxlag':
            time.sleep(6)
            continue
        if 'error' in d:
            raise RuntimeError(f'Wikipedia API error: {d["error"]}')
        return d
    raise RuntimeError('Wikipedia API: maxlag did not clear')


# --------------------------------------------------------------------------------------------- fetch
def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    for name, query in QUERIES.items():
        out = DATA / f'{name}.tsv.gz'
        if out.exists():
            log(f'{name}: have {out}')
            continue
        log(f'{name}: querying QLever')
        raw = http_post(QLEVER, {'query': PREFIXES + query}, 'text/tab-separated-values', pause=2.0)
        with gzip.open(out, 'wb') as fh:
            fh.write(raw)
        log(f'{name}: {raw.count(b"\n") - 1} rows')
    fetch_causes()
    fetch_shipwreck_lists()
    manifest = {}
    for f in sorted(DATA.glob('*.gz')):
        manifest[f.name] = hashlib.sha256(f.read_bytes()).hexdigest()
    manifest['fetched_on'] = dt.date.today().isoformat()
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    log('fetch done')


def fetch_causes():
    """Kinds of every cause value seen on loss events: is it a ship, an aircraft unit, a battle, a military unit?"""
    out = DATA / 'causekinds.tsv.gz'
    if out.exists():
        return
    vals = set()
    for r in read_tsv('event_quals'):
        vals.add(qid(r[3]))
    for r in read_tsv('p770'):
        vals.add(qid(r[1]))
    vals = sorted(v for v in vals if re.fullmatch(r'Q\d+', v))
    lines = [b'?v\t?ship\t?air\t?battle\t?mil']
    for i in range(0, len(vals), 200):
        chunk = ' '.join('wd:' + v for v in vals[i:i + 200])
        q = f"""SELECT ?v ?ship ?air ?battle ?mil WHERE {{ VALUES ?v {{ {chunk} }}
  OPTIONAL {{ ?v wdt:P31/wdt:P279* wd:Q11446 . BIND(1 AS ?ship) }}
  OPTIONAL {{ ?v wdt:P31/wdt:P279* wd:Q11436 . BIND(1 AS ?air) }}
  OPTIONAL {{ ?v wdt:P31/wdt:P279* wd:Q178561 . BIND(1 AS ?battle) }}
  OPTIONAL {{ ?v wdt:P31/wdt:P279* wd:Q645883 . BIND(1 AS ?mil) }} }}"""
        raw = http_post(QLEVER, {'query': PREFIXES + q}, 'text/tab-separated-values', pause=2.0)
        lines.extend(raw.split(b'\n')[1:])
    with gzip.open(out, 'wb') as fh:
        fh.write(b'\n'.join(x for x in lines if x.strip()) + b'\n')


MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October',
          'November', 'December']


def list_page_date(title):
    m = re.fullmatch(r'List of shipwrecks in (' + '|'.join(MONTHS) + r') (\d{4})', title)
    if m:
        return int(m.group(2)), MONTHS.index(m.group(1)) + 1
    m = re.fullmatch(r'List of shipwrecks in (\d{4})', title)
    if m:
        return int(m.group(1)), None
    return None


def fetch_shipwreck_lists():
    """The wikitext of every chronological shipwreck list, and the redirects into the cohort's articles."""
    pages_f, redir_f = DATA / 'wp_pages.json.gz', DATA / 'wp_redirects.json.gz'
    if not pages_f.exists():
        titles, cont = [], {}
        while True:
            d = wp({'action': 'query', 'list': 'allpages', 'apprefix': 'List of shipwrecks', 'apnamespace': '0',
                    'apfilterredir': 'nonredirects', 'aplimit': 'max', **cont})
            titles += [p['title'] for p in d['query']['allpages']]
            if 'continue' not in d:
                break
            cont = d['continue']
        pages = {t: list_page_date(t) for t in titles}
        pages = {t: v for t, v in pages.items() if v and v[0] >= 1800}
        with gzip.open(pages_f, 'wt') as fh:
            json.dump(pages, fh)
        log(f'shipwreck lists: {len(pages)} dated pages of {len(titles)}')
    pages = json.load(gzip.open(pages_f, 'rt'))
    # The wikitext of every list page: only the row's SHIP cell says which ship was lost. A page's links
    # also point at ships that sank, rescued or towed the lost ones, so "any link on the page" is no loss record.
    text_f = DATA / 'wp_wikitext.json.gz'
    texts = json.load(gzip.open(text_f, 'rt')) if text_f.exists() else {}
    todo = [t for t in sorted(pages) if t not in texts]
    for i in range(0, len(todo), 10):
        chunk = todo[i:i + 10]
        d = wp({'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
                'titles': '|'.join(chunk)})
        for p in d['query'].get('pages', []):
            if p.get('revisions'):
                texts[p['title']] = p['revisions'][0]['slots']['main']['content']
        if (i // 10) % 10 == 0 or i + 10 >= len(todo):
            log(f'wikitext: {len(texts)}/{len(pages)} pages')
            with gzip.open(text_f, 'wt') as fh:
                json.dump(texts, fh)
    # Redirects INTO the cohort's English articles (a list often links a ship through a redirect such as
    # "HMS Hood (51)"): asking only for those is a few hundred requests instead of resolving every linked title.
    redir = json.load(gzip.open(redir_f, 'rt')) if redir_f.exists() else {}
    done = set(redir.get('__articles__', []))
    articles = sorted({lit(r[3]) for r in read_tsv('names') if len(r) > 3 and lit(r[3])} - done)
    for i in range(0, len(articles), 50):
        chunk = articles[i:i + 50]
        cont = {}
        while True:
            d = wp({'action': 'query', 'titles': '|'.join(chunk), 'prop': 'redirects', 'rdlimit': 'max',
                    'rdnamespace': '0', **cont})
            for p in d['query'].get('pages', []):
                for x in p.get('redirects', []):
                    redir[x['title']] = p['title']
            if 'continue' not in d:
                break
            cont = d['continue']
        done.update(chunk)
        if (i // 50) % 40 == 0 or i + 50 >= len(articles):
            redir['__articles__'] = sorted(done)
            log(f'redirects: {len(done)} articles checked, {len(redir) - 1} redirects')
            with gzip.open(redir_f, 'wt') as fh:
                json.dump(redir, fh)


# --------------------------------------------------------------------------------------------- reading
def read_tsv(name):
    with gzip.open(DATA / f'{name}.tsv.gz', 'rt', encoding='utf-8') as fh:
        rows = [line.rstrip('\n').split('\t') for line in fh]
    return rows[1:]


def qid(x):
    x = x.strip().strip('<>')
    return x.rsplit('/', 1)[-1] if 'wikidata.org' in x else x


def lit(x):
    """A TSV literal without quotes and type/language tags."""
    x = x.strip()
    m = re.match(r'^"(.*)"(?:\^\^<[^>]+>|@[\w-]+)?$', x, flags=re.S)
    return m.group(1) if m else x


def pdate(t, prec='11'):
    """(date, precision) for precision 9-11, else (None, None). Year -> 1 July, month -> the 15th."""
    t = lit(t or '')
    if not t or t.startswith('-'):
        return None, None
    try:
        prec = int(lit(prec)) if prec else 11
        y, m, d = int(t[0:4]), int(t[5:7]), int(t[8:10])
    except ValueError:
        return None, None
    try:
        if prec == 9:
            return dt.date(y, 7, 1), 9
        if prec == 10:
            return dt.date(y, max(m, 1), 15), 10
        if prec >= 11:
            return dt.date(y, m, d), 11
    except ValueError:
        pass
    return None, None


def day_dates(name, lo=1800, hi=2025):
    """ship -> its single Gregorian day-precision date for one event type; ships with conflicting dates dropped."""
    seen, julian = defaultdict(set), 0
    for r in read_tsv(name):
        if len(r) < 4 or lit(r[2]) != '11':
            continue
        if qid(r[3]) != GREGORIAN:
            julian += 1
            continue
        d, _ = pdate(r[1])
        if d and lo <= d.year <= hi:
            seen[qid(r[0])].add(d)
    one = {s: next(iter(v)) for s, v in seen.items() if len(v) == 1}
    return one, len(seen) - len(one), julian


# --------------------------------------------------------------------------------------------- statistics
def ratio_ci(k, base_sum, base_days=4):
    """k / (base_sum / base_days) with a 95 % interval treating both counts as Poisson."""
    if k == 0 or base_sum == 0:
        return {'ratio': None, 'lo': None, 'hi': None}
    r = k / (base_sum / base_days)
    se = math.sqrt(1 / k + 1 / base_sum)
    return {'ratio': round(r, 3), 'lo': round(r * math.exp(-1.96 * se), 3), 'hi': round(r * math.exp(1.96 * se), 3)}


def weekday_block(dates):
    c = Counter(d.weekday() for d in dates)
    counts = [c[i] for i in range(7)]
    mon_thu = sum(counts[:4])
    n = sum(counts)
    return {'n': n, 'counts': counts,
            'share_pct': [round(100 * x / n, 1) if n else None for x in counts],
            'friday': ratio_ci(counts[4], mon_thu), 'saturday': ratio_ci(counts[5], mon_thu),
            'monday_vs_tue_thu': ratio_ci(counts[0], sum(counts[1:4]), 3)}


def thirteenth_block(dates):
    c = Counter(d.day for d in dates)
    base_days = list(range(2, 13)) + list(range(14, 29))
    base = sum(c[x] for x in base_days)
    return {'n': len(dates), 'on_13th': c[13], **ratio_ci(c[13], base, len(base_days))}


def by_period(dates, periods, fn):
    return [{'from': a, 'to': b, **fn([d for d in dates if a <= d.year <= b])} for a, b in periods]


def mantel_haenszel(rows):
    """rows: (stratum, exposed 0/1, outcome 0/1). Odds ratio, 95 % RBG interval, observed and expected events."""
    tab = defaultdict(lambda: [0, 0, 0, 0])  # a: exp&out, b: exp&~out, c: ~exp&out, d: ~exp&~out
    for s, e, o in rows:
        tab[s][(0 if o else 1) if e else (2 if o else 3)] += 1
    R = S = PR = PSQR = QS = 0.0
    obs = exp_ = 0.0
    informative = 0
    for a, b, c, d in tab.values():
        n = a + b + c + d
        if n < 2:
            continue
        r_, s_ = a * d / n, b * c / n
        p_, q_ = (a + d) / n, (b + c) / n
        R += r_
        S += s_
        PR += p_ * r_
        PSQR += p_ * s_ + q_ * r_
        QS += q_ * s_
        obs += a
        exp_ += (a + b) * (a + c) / n
        if (a + b) and (c + d) and (a + c) and (b + d):
            informative += 1
    if R == 0 or S == 0:
        return {'or': None, 'lo': None, 'hi': None, 'observed': obs, 'expected': round(exp_, 1),
                'strata': informative}
    orr = R / S
    se = math.sqrt(PR / (2 * R * R) + PSQR / (2 * R * S) + QS / (2 * S * S))
    return {'or': round(orr, 3), 'lo': round(orr * math.exp(-1.96 * se), 3), 'hi': round(orr * math.exp(1.96 * se), 3),
            'observed': int(obs), 'expected': round(exp_, 1), 'strata': informative}


def permutation_p(rows, seed=SEED, nperm=NPERM):
    """Two-sided p for sum(observed - expected) with the exposure shuffled inside strata."""
    by = defaultdict(list)
    for s, e, o in rows:
        by[s].append((e, o))
    # Strata where nothing can move (no exposed, all exposed, no events, all events) add a constant: skip them.
    blocks = []
    for v in by.values():
        k, out = sum(e for e, _ in v), [o for _, o in v]
        if 0 < k < len(v) and 0 < sum(out) < len(v):
            blocks.append((k, out, sum(e * o for e, o in v)))
    expected = sum(k * sum(out) / len(out) for k, out, _ in blocks)
    observed = sum(a for _, _, a in blocks)
    t_obs = abs(observed - expected)
    rng = random.Random(seed)
    hits = 0
    for _ in range(nperm):
        tot = 0
        for k, out, _ in blocks:
            tot += sum(rng.sample(out, k))
        if abs(tot - expected) >= t_obs - 1e-9:
            hits += 1
    return round((hits + 1) / (nperm + 1), 4)


def crude(rows):
    a = sum(1 for _, e, o in rows if e and o)
    n1 = sum(1 for _, e, _ in rows if e)
    c = sum(1 for _, e, o in rows if not e and o)
    n0 = sum(1 for _, e, _ in rows if not e)
    b, d = n1 - a, n0 - c
    out = {'exposed_lost': a, 'exposed_n': n1, 'other_lost': c, 'other_n': n0,
           'exposed_pct': round(100 * a / n1, 2) if n1 else None, 'other_pct': round(100 * c / n0, 2) if n0 else None}
    if min(a, b, c, d) > 0:
        orr = a * d / (b * c)
        se = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
        out.update({'or': round(orr, 3), 'lo': round(orr * math.exp(-1.96 * se), 3),
                    'hi': round(orr * math.exp(1.96 * se), 3)})
    return out


# --------------------------------------------------------------------------------------------- compute
def build_ships():
    launch, conflicts, julian = day_dates('launch')
    log(f'launches: {len(launch)} ships (conflicting dates dropped: {conflicts}; Julian statements: {julian})')

    roots = defaultdict(set)
    for r in read_tsv('classmap'):
        roots[qid(r[0])].add(qid(r[1]))
    p31 = defaultdict(set)
    p31_wreck_date = {}
    for r in read_tsv('p31'):
        s, c = qid(r[0]), qid(r[1])
        if s in launch:
            p31[s].add(c)
            if c in ('Q852190', 'Q906512') and len(r) > 2 and r[2]:
                d, p = pdate(r[2], r[3] if len(r) > 3 else '')
                if d:
                    p31_wreck_date[s] = (d, p)

    def ship_type(s, year):
        rs = set()
        for c in p31[s] - IGNORE_CLASSES:
            rs |= roots.get(c, set())
        for name, rootset in TYPE_ROOTS.items():
            if rs & rootset:
                if name == 'destroyer_escort' and year < 1880 and 'Q324233' not in rs:
                    return 'other_warship'  # sailing-era frigates and corvettes
                return name
        return 'other'

    opinfo = {}
    for r in read_tsv('opmap'):
        e = opinfo.setdefault(qid(r[0]), {'label': lit(r[1]) if len(r) > 1 else '', 'mil': False})
        if any(len(r) > i and r[i].strip() for i in (2, 3)):
            e['mil'] = True
    opst = defaultdict(list)
    for r in read_tsv('operators'):
        s = qid(r[0])
        if s in launch:
            t1 = pdate(r[2])[0] if len(r) > 2 and r[2] else None
            t2 = pdate(r[3])[0] if len(r) > 3 and r[3] else None
            opst[s].append((qid(r[1]), t1, t2))

    def operator_at_launch(s):
        L = launch[s]
        cands = opst.get(s, [])
        ok = [c for c in cands if (c[1] is None or c[1] <= L + dt.timedelta(days=400)) and (c[2] is None or c[2] >= L)]
        pool = sorted(ok or cands, key=lambda c: (c[1] is None, c[1] or dt.date(9999, 1, 1), c[0]))
        return pool[0][0] if pool else None

    op_at = {s: operator_at_launch(s) for s in launch}
    opcount = Counter(v for v in op_at.values() if v)

    def op_group(s, typ):
        o = op_at[s]
        if o is None:
            return 'unknown_navy' if typ in WARSHIP_TYPES else 'civil'
        if opinfo.get(o, {}).get('mil'):
            return opinfo[o]['label'] or o if opcount[o] >= NAVY_MIN_SHIPS else 'other_navy'
        return 'civil'

    causekind = defaultdict(set)
    for r in read_tsv('causekinds'):
        for i, name in zip(range(1, 5), ('ship', 'air', 'battle', 'mil')):
            if len(r) > i and r[i].strip():
                causekind[qid(r[0])].add(name)

    events = defaultdict(list)
    for r in read_tsv('events'):
        s = qid(r[0])
        if s not in launch or len(r) < 3:
            continue
        d, p = pdate(r[3] if len(r) > 3 else '', r[4] if len(r) > 4 else '')
        if d is None and len(r) > 5:
            d, p = pdate(r[5], r[6] if len(r) > 6 else '')
        events[s].append((lit(r[1]), qid(r[2]), d, p))
    quals = defaultdict(lambda: defaultdict(set))
    for r in read_tsv('event_quals'):
        if len(r) >= 4:
            quals[r[1].strip('<>').rsplit('/', 1)[-1]][qid(r[2]).replace('pq:', '')].add(qid(r[3]))
    enddate = {}
    for r in read_tsv('end'):
        s = qid(r[0])
        d, p = pdate(r[2], r[3])
        if s in launch and d and (s not in enddate or d < enddate[s][0]):
            enddate[s] = (d, p)
    p770 = defaultdict(set)
    for r in read_tsv('p770'):
        if qid(r[0]) in launch:
            p770[qid(r[0])].add(qid(r[1]))

    def cause_kinds(causes):
        k = set()
        for c in causes:
            if c in NOT_A_LOSS_CAUSE:
                k.add('notloss')
            elif c in DELIBERATE_CAUSE:
                k.add('deliberate')
        return k

    def later(a, ap, b, bp, days):
        if a is None or b is None:
            return False
        if (ap or 11) < 11 or (bp or 11) < 11:
            return b.year > a.year + days // 365
        return (b - a).days > days

    ships = {}
    for s, L in launch.items():
        typ = ship_type(s, L.year)
        evs = events.get(s, [])
        cands = []
        for sid, ev, d, p in evs:
            if ev not in LOSS_EVENTS:
                continue
            causes = set()
            for qp in CAUSE_QUALIFIERS:
                causes |= quals[sid].get(qp, set())
            for v in quals[sid].get('P710', set()):
                if causekind.get(v, set()):
                    causes.add(v)
            if ev == 'Q17781833' and 'notloss' in cause_kinds(causes):
                continue  # "destruction" by ship breaking = scrapped
            if d is not None and d < L:
                continue
            cands.append((ev, d, p, causes))
        alive = [(d, p) for _, ev, d, p in evs if ev != LAUNCH and d is not None and ev not in POST_LOSS]
        decoms = [(d, p) for _, ev, d, p in evs if ev == DECOM and d is not None]
        final = []
        for ev, d, p, causes in cands:
            superseded = d is not None and (any(later(d, p, d2, p2, 30) for d2, p2 in alive) or
                                            any(later(d, p, d2, p2, 4 * 365) for d2, p2 in decoms))
            if not superseded:
                final.append((ev, d, p, causes))
        lost, deliberate, loss_d = False, False, None
        if final:
            dated = [x for x in final if x[1] is not None]
            loss_d = min(x[1] for x in dated) if dated else None
            evtypes = {x[0] for x in final}
            causes = set().union(*(x[3] for x in final)) | p770.get(s, set())
            deliberate = bool(evtypes & set(SCUTTLE)) or 'deliberate' in cause_kinds(causes)
            lost = not deliberate
        elif p31[s] & {'Q852190', 'Q906512'}:
            lost = True
            loss_d = p31_wreck_date.get(s, enddate.get(s, (None, None)))[0]
        elif p770.get(s) and not cause_kinds(p770[s]) & {'notloss'}:
            deliberate = 'deliberate' in cause_kinds(p770[s])
            lost = not deliberate
            loss_d = enddate.get(s, (None, None))[0]
        if lost and loss_d is not None and loss_d < L:
            loss_d = None
        # A navy ship sunk more than 30 days after its last decommissioning: a target, reef or tow, not luck at sea.
        last_decom = max((d for d, _ in decoms), default=None)
        if lost and loss_d and last_decom and typ in WARSHIP_TYPES and (loss_d - last_decom).days > 30:
            lost, deliberate = False, True
        ships[s] = {'launch': L, 'type': typ, 'op_group': op_group(s, typ), 'op': op_at[s],
                    'lost_wd': lost, 'deliberate_wd': deliberate, 'loss_date_wd': loss_d,
                    # Any loss-type record at all, even one followed by more service (sunk and raised):
                    # such ships never appear in the birthday calculator.
                    'any_loss_record': bool(cands) or bool(p31[s] & {'Q852190', 'Q906512'}) or bool(p770.get(s)),
                    'war_loss_wd': bool(lost and loss_d and any(a <= loss_d <= b for a, b in WW))}
    return ships, {'conflicting_dates': conflicts, 'julian_statements': julian}, opinfo


def match_braces(t, i):
    """t[i:i+2] == '{{': the index just after the matching '}}'."""
    depth, j, n = 0, i, len(t)
    while j < n:
        if t.startswith('{{', j):
            depth, j = depth + 1, j + 2
        elif t.startswith('}}', j):
            depth, j = depth - 1, j + 2
            if depth == 0:
                return j
        else:
            j += 1
    return n


def split_top(text, sep='|'):
    """Split on `sep` outside {{...}} and [[...]]."""
    parts, cur, braces, brackets, i = [], [], 0, 0, 0
    while i < len(text):
        two = text[i:i + 2]
        if two in ('{{', '[['):
            braces += two == '{{'
            brackets += two == '[['
            cur.append(two)
            i += 2
            continue
        if two == '}}' and braces or two == ']]' and brackets:
            braces -= two == '}}'
            brackets -= two == ']]'
            cur.append(two)
            i += 2
            continue
        if text.startswith(sep, i) and not braces and not brackets:
            parts.append(''.join(cur))
            cur = []
            i += len(sep)
            continue
        cur.append(text[i])
        i += 1
    parts.append(''.join(cur))
    return parts


def ship_cells(text):
    """The ship cell of every row: {{shipwreck list item|ship=...}} (or its first positional argument) and the
    first cell of plain table rows."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    cells, i = [], 0
    blanked = list(text)
    while True:
        j = text.find('{{', i)
        if j < 0:
            break
        k = match_braces(text, j)
        inner = text[j + 2:k - 2]
        if inner.lower().lstrip().startswith('shipwreck list item'):
            pos, kv = [], {}
            for part in split_top(inner)[1:]:
                head = part.split('{{')[0].split('[[')[0]
                if '=' in head:
                    key, val = part.split('=', 1)
                    kv[key.strip().lower()] = val
                else:
                    pos.append(part)
            cells.append(kv.get('ship', pos[0] if pos else ''))
            for x in range(j, k):
                if blanked[x] != '\n':
                    blanked[x] = ' '
            i = k
        else:
            i = j + 2
    plain = ''.join(blanked)
    for row in re.split(r'\n\|-[^\n]*', plain)[1:]:
        lines = [x for x in row.split('\n') if x.strip()]
        if not lines or not lines[0].startswith(('|', '!')) or lines[0].startswith(('|}', '|+')):
            continue
        first = split_top(lines[0][1:], '||')[0]
        top = split_top(first)
        if len(top) == 2 and re.match(r'^\s*(style|class|align|rowspan|colspan|scope|data-sort-value)\s*=', top[0]):
            first = top[1]
        cells.append(first)
    return cells


def cell_targets(cell):
    """Article titles a ship cell links to: [[Target|label]] and the ship-name templates of WikiProject Ships
    ({{ship|HMS|Hood|51}}, {{HMS|Hood|51}}, {{SS|Titanic}} ... -> "HMS Hood (51)", "SS Titanic")."""
    out = []
    for m in re.finditer(r'\[\[([^\[\]|#]+)(?:#[^\[\]|]*)?(?:\|[^\[\]]*)?\]\]', cell):
        out.append(m.group(1))
    for m in re.finditer(r'\{\{([^{}]+)\}\}', cell):
        parts = [x.strip() for x in m.group(1).split('|')]
        name, args = parts[0], [x for x in parts[1:] if '=' not in x]
        if name.lower() == 'ship' and len(args) >= 2:
            prefix, args = args[0], args[1:]
        elif re.fullmatch(r'[A-Z][A-Za-z]{1,6}', name) and args:
            prefix = name
        else:
            continue
        title = f'{prefix} {args[0]}'
        if len(args) > 1 and args[1]:
            title += f' ({args[1]})'
        out.append(title)
    norm = []
    for t in out:
        t = t.replace('_', ' ').strip()
        if t:
            norm.append(t[0].upper() + t[1:])
    return norm


def attach_wikipedia(ships):
    """Mark ships named in the ship cell of a shipwreck-list row, on a page dated from their launch month on."""
    names = {}
    for r in read_tsv('names'):
        s = qid(r[0])
        if s in ships:
            names[s] = {'label': lit(r[1]) if len(r) > 1 else '', 'links': int(lit(r[2]) or 0) if len(r) > 2 and lit(r[2]).isdigit() else 0,
                        'title': lit(r[3]) if len(r) > 3 else ''}
    title_to_ship = {v['title']: s for s, v in names.items() if v['title']}
    pages = json.load(gzip.open(DATA / 'wp_pages.json.gz', 'rt'))
    texts = json.load(gzip.open(DATA / 'wp_wikitext.json.gz', 'rt'))
    redir = json.load(gzip.open(DATA / 'wp_redirects.json.gz', 'rt'))
    redir.pop('__articles__', None)
    first = {}
    for page, text in texts.items():
        if page not in pages:
            continue
        y, m = pages[page]
        targets = {t for cell in ship_cells(text) for t in cell_targets(cell)}
        for t in targets:
            s = title_to_ship.get(redir.get(t, t))
            if s is None:
                continue
            key = (y, m or 1)
            if s not in first or key < first[s]:
                first[s] = key
    with_article = 0
    for s, v in ships.items():
        v['name'] = names.get(s, {}).get('label') or s
        v['sitelinks'] = names.get(s, {}).get('links', 0)
        v['enwiki'] = bool(names.get(s, {}).get('title'))
        with_article += v['enwiki']
        L = v['launch']
        hit = first.get(s)
        v['listed_wp'] = bool(hit and hit >= (L.year, L.month))
        v['listed_wp_date'] = f'{hit[0]:04d}-{hit[1]:02d}' if v['listed_wp'] else ''
        v['war_listed_wp'] = bool(v['listed_wp'] and any(
            (a.year, a.month) <= hit <= (b.year, b.month) for a, b in WW))
    return {'list_pages': len(pages), 'ships_with_enwiki_article': with_article,
            'ships_listed': sum(v['listed_wp'] for v in ships.values())}


def stratum(v):
    L = v['launch']
    when = f'{L.year}Q{(L.month - 1) // 3 + 1}' if (1914 <= L.year <= 1918 or 1939 <= L.year <= 1945) else str(L.year)
    return f'{when}|{v["op_group"]}|{v["type"]}'


def loss_tests(ships):
    out = {}
    sources = {'wikidata': lambda v: v['lost_wd'], 'wikipedia_lists': lambda v: v['listed_wp']}
    for src, outcome in sources.items():
        pool = [v for v in ships.values() if not (src == 'wikidata' and v['deliberate_wd'])]
        if src == 'wikipedia_lists':
            pool = [v for v in pool if v['enwiki']]  # only ships that can appear in the lists at all
        res = {}
        for name, ref in (('friday_vs_mon_thu', set(range(4))), ('friday_vs_saturday', {5}),
                          ('friday_vs_all_other_days', {0, 1, 2, 3, 5, 6})):
            rows = [(stratum(v), 1 if v['launch'].weekday() == 4 else 0, 1 if outcome(v) else 0)
                    for v in pool if v['launch'].weekday() == 4 or v['launch'].weekday() in ref]
            res[name] = {'crude': crude(rows), 'stratified': mantel_haenszel(rows)}
            if name != 'friday_vs_all_other_days':
                res[name]['permutation_p'] = permutation_p(rows)
        # Each weekday against all the others: the control for "is Friday special at all".
        res['each_day_vs_rest'] = []
        for wd in range(7):
            rows = [(stratum(v), 1 if v['launch'].weekday() == wd else 0, 1 if outcome(v) else 0) for v in pool]
            res['each_day_vs_rest'].append({'day': WEEKDAYS[wd], **mantel_haenszel(rows)})
        # War-time and peace-time losses separately (Wikidata loss date / list page date inside 1914-18, 1939-45).
        # A ship lost in the other part, or lost on an unknown date, leaves that comparison.
        def war_flag(v, src=src):
            if src == 'wikidata':
                return None if v['loss_date_wd'] is None else v['war_loss_wd']
            return v['war_listed_wp']
        for part, want in (('war', True), ('outside_world_wars', False)):
            rows = [(stratum(v), 1 if v['launch'].weekday() == 4 else 0, 1 if outcome(v) else 0)
                    for v in pool if v['launch'].weekday() in (0, 1, 2, 3, 4)
                    and (not outcome(v) or war_flag(v) is want)]
            res[f'friday_vs_mon_thu_{part}'] = {'crude': crude(rows), 'stratified': mantel_haenszel(rows)}
        out[src] = res
    # How often the two records agree, and whether a ship's chance of being "seen" by one source depends on Friday.
    both = [v for v in ships.values() if v['enwiki'] and not v['deliberate_wd']]
    out['agreement'] = {
        'ships': len(both),
        'lost_in_both': sum(1 for v in both if v['lost_wd'] and v['listed_wp']),
        'wikidata_only': sum(1 for v in both if v['lost_wd'] and not v['listed_wp']),
        'lists_only': sum(1 for v in both if v['listed_wp'] and not v['lost_wd']),
    }
    return out


def compute():
    ships, launch_meta, opinfo = build_ships()
    wp_meta = attach_wikipedia(ships)
    dates = [v['launch'] for v in ships.values()]

    def dates_where(pred):
        return [v['launch'] for v in ships.values() if pred(v)]

    keel, _, _ = day_dates('keel')
    commission, _, _ = day_dates('commission')
    openings = []
    for r in read_tsv('openings'):
        if len(r) >= 3 and qid(r[2]) == GREGORIAN:
            d, _ = pdate(r[1])
            if d:
                openings.append(d)
    births = [d for d in (pdate(r[0])[0] for r in read_tsv('births')) if d]

    r = {
        'cohort': {'ships': len(ships), 'first_year': min(dates).year, 'last_year': max(dates).year, **launch_meta,
                   **wp_meta},
        'launch_by_period': by_period(dates, PERIODS, weekday_block),
        'launch_by_decade': by_period(dates, DECADES, weekday_block),
        'thirteenth_by_period': by_period(dates, [(1800, 1899), (1900, 1945), (1946, 1969), (1970, 1999), (2000, 2025)],
                                          thirteenth_block),
        'thirteenth_by_decade': by_period(dates, DECADES, thirteenth_block),
        'headline_1860_1899': weekday_block([d for d in dates if 1860 <= d.year <= 1899]),
        'controls_1860_1899': {
            'keel_laying': weekday_block([d for d in keel.values() if 1860 <= d.year <= 1899]),
            'commissioning': weekday_block([d for d in commission.values() if 1860 <= d.year <= 1899]),
            'official_openings': weekday_block([d for d in openings if 1860 <= d.year <= 1899]),
            'births': weekday_block(births),
        },
        'commission_by_period': by_period(list(commission.values()), PERIODS, weekday_block),
        'controls_1800_1945': {
            'keel_laying': weekday_block([d for d in keel.values() if d.year <= 1945]),
            'commissioning': weekday_block([d for d in commission.values() if d.year <= 1945]),
            'launches': weekday_block([d for d in dates if d.year <= 1945]),
        },
        'friday_13th': {
            'launches_1800_1945': sum(1 for d in dates if d.year <= 1945 and d.day == 13 and d.weekday() == 4),
            'expected_1800_1945': round(sum(1 for d in dates if d.year <= 1945) / 365.25 * 12 / 7, 1),
        },
    }
    # Navies (operator at launch), 1800-1945 and 1860-1899.
    navies = Counter(v['op_group'] for v in ships.values() if v['launch'].year <= 1945)
    r['navies_1800_1945'] = sorted(
        [{'navy': g, **weekday_block(dates_where(lambda v, g=g: v['op_group'] == g and v['launch'].year <= 1945))}
         for g, n in navies.items() if n >= 300 and g not in ('other_navy', 'unknown_navy')],
        key=lambda x: -x['n'])
    r['royal_navy_1860_1899'] = weekday_block(dates_where(
        lambda v: v['op_group'] == 'Royal Navy' and 1860 <= v['launch'].year <= 1899))
    r['civil_1800_1945'] = weekday_block(dates_where(lambda v: v['op_group'] == 'civil' and v['launch'].year <= 1945))
    r['types_1800_1945'] = Counter(v['type'] for v in ships.values() if v['launch'].year <= 1945)
    r['losses'] = loss_tests(ships)

    # Calculator: for each day and month, the best-known ship launched on it with no loss record at all.
    best = {}
    for s, v in ships.items():
        if (v['lost_wd'] or v['deliberate_wd'] or v['listed_wp'] or v['any_loss_record'] or not v['name']
                or v['name'] == s):
            continue
        key = v['launch'].strftime('%m-%d')
        cand = (v['sitelinks'], -v['launch'].year, s)
        if key not in best or cand > best[key][0]:
            best[key] = (cand, {'name': v['name'], 'year': v['launch'].year, 'weekday': v['launch'].weekday(),
                                'qid': s})
    r['birthday_ships'] = {k: best[k][1] for k in sorted(best)}

    (DATA / 'computed.json').write_text(json.dumps(r, indent=1, default=str))
    with gzip.open(DATA / 'ships.csv.gz', 'wt', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['qid', 'launch_date', 'weekday', 'type', 'operator_group', 'lost_wikidata', 'deliberate_wikidata',
                    'loss_date_wikidata', 'in_wikipedia_shipwreck_list', 'first_list_month', 'has_enwiki_article'])
        for s in sorted(ships, key=lambda x: (ships[x]['launch'], x)):
            v = ships[s]
            w.writerow([s, v['launch'].isoformat(), WEEKDAYS[v['launch'].weekday()], v['type'], v['op_group'],
                        int(v['lost_wd']), int(v['deliberate_wd']),
                        v['loss_date_wd'].isoformat() if v['loss_date_wd'] else '', int(v['listed_wp']),
                        v['listed_wp_date'], int(v['enwiki'])])
    log(f'computed: {len(ships)} ships -> {DATA / "computed.json"}')


# --------------------------------------------------------------------------------------------- validate
def hypotheses_sha():
    return hashlib.sha256(json.dumps(HYPOTHESES, sort_keys=True).encode()).hexdigest()[:8]


def validate():
    r = json.loads((DATA / 'computed.json').read_text())
    checks = []

    def check(name, ok, detail=''):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})

    n = r['cohort']['ships']
    check('cohort size', 17000 <= n <= 30000, f'{n} ships')
    h = r['headline_1860_1899']
    check('1860-1899 sample', h['n'] >= 1200, f'{h["n"]} launches')
    b = r['controls_1860_1899']['births']
    check('births sample', b['n'] >= 300000, f'{b["n"]} births')
    check('Wikipedia lists read', r['cohort']['list_pages'] >= 1000, f'{r["cohort"]["list_pages"]} pages')
    check('ships found in the lists', r['cohort']['ships_listed'] >= 2000, f'{r["cohort"]["ships_listed"]}')
    check('hypotheses unchanged since registration', hypotheses_sha() == HYPOTHESES_SHA256, hypotheses_sha())

    L, C = r['losses'], r['controls_1860_1899']
    t13 = {(x['from'], x['to']): x for x in r['thirteenth_by_period']}
    per = {(x['from'], x['to']): x for x in r['launch_by_period']}
    f46 = per[(1946, 1959)]['friday']['ratio']
    hyp = {
        'H1': h['friday']['ratio'] < 0.50 and h['friday']['hi'] < 0.60,
        'H2': h['friday']['ratio'] / C['official_openings']['friday']['ratio'] < 0.75,
        'H3': 0.97 <= b['friday']['ratio'] <= 1.03,
        'H4': f46 >= 0.80,
        'H5': 0.80 <= t13[(1800, 1899)]['ratio'] <= 1.25 and t13[(1900, 1945)]['ratio'] < 0.70
              and t13[(1900, 1945)]['hi'] < 0.75,
        'H6': all(L[s]['friday_vs_mon_thu']['stratified']['or'] <= 1.00
                  and L[s]['friday_vs_mon_thu']['stratified']['hi'] < 1.25 for s in ('wikidata', 'wikipedia_lists')),
        'H7': all(0.80 <= L[s]['friday_vs_saturday']['stratified']['or'] <= 1.25
                  for s in ('wikidata', 'wikipedia_lists')),
        'H8': C['keel_laying']['friday']['ratio'] < 0.80,
        'H9': C['commissioning']['friday']['ratio'] - h['friday']['ratio'] >= 0.20,
        'H10': r['royal_navy_1860_1899']['friday']['ratio'] < 0.60,
    }
    out = {'ok': all(c['ok'] for c in checks), 'checks': checks, 'hypotheses': {
        k: {'text': HYPOTHESES[k], 'held': bool(v)} for k, v in hyp.items()}, 'hypotheses_sha': hypotheses_sha()}
    (DATA / 'validation.json').write_text(json.dumps(out, indent=1))
    for c in checks:
        log(('ok  ' if c['ok'] else 'FAIL') + f' {c["check"]}: {c["detail"]}')
    for k, v in out['hypotheses'].items():
        log(f'{k}: {"held" if v["held"] else "did not hold"}')
    return out['ok']


# --------------------------------------------------------------------------------------------- export
def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if not val['ok']:
        log('validation failed - nothing exported')
        return False
    r = json.loads((DATA / 'computed.json').read_text())
    manifest = json.loads((DATA / 'manifest.json').read_text())
    page = {
        'generated_from': {'fetched_on': manifest.get('fetched_on'), 'script': 'ship_launch_days.py'},
        'weekdays': WEEKDAYS,
        **{k: r[k] for k in ('cohort', 'launch_by_period', 'launch_by_decade', 'commission_by_period', 'thirteenth_by_period',
                             'thirteenth_by_decade', 'headline_1860_1899', 'controls_1860_1899', 'controls_1800_1945',
                             'friday_13th', 'navies_1800_1945', 'royal_navy_1860_1899', 'civil_1800_1945', 'losses',
                             'birthday_ships')},
        'hypotheses': val['hypotheses'],
        'added_after_count': ADDED_AFTER_COUNT,
        'validation': {'ok': val['ok'], 'checks': val['checks']},
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(page, separators=(',', ':'), ensure_ascii=False) + '\n')
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(DATA / 'ships.csv.gz', 'rt') as src, CSV_OUT.open('w') as dst:
        shutil.copyfileobj(src, dst)
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')
    return True


if __name__ == '__main__':
    steps = {'fetch': fetch, 'compute': compute, 'validate': validate, 'export': export}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    sys.exit(1 if steps[sys.argv[1]]() is False else 0)
