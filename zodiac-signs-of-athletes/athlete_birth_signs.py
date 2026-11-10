#!/usr/bin/env python3
"""The zodiac signs of professional athletes, and the youth-sport cutoff dates that set them.

Source of the numbers on https://startarot.online/research/zodiac-signs-of-athletes

Needs Python 3.10+ and
    pip install numpy pandas pyreadr
The raw files (about 300 MB) go to $ATHLETE_SIGNS_DATA (default: ./athlete-signs-data next to this
script). Steps, in order:

    python3 athlete_birth_signs.py fetch      # Wikidata (QLever), Lahman, official births by month
    python3 athlete_birth_signs.py compute    # people, baselines, signs, cutoffs, tests
    python3 athlete_birth_signs.py validate   # dates, coverage, Lahman against Wikidata, baselines
    python3 athlete_birth_signs.py export     # page JSON + dataset CSV (+ a copy of this script)

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/athlete-birth-signs.json   data the page renders
    frontend/static/research/athlete-birth-signs.csv     the open dataset (observed and expected
                                                         counts by group, cohort and month/sign)
    frontend/static/research/athlete_birth_signs.py      a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself. Individual people are not
published: the dataset holds counts only.

Pre-registration
----------------
A first look (28.10.2026) covered men's football in Germany, the Netherlands, the UK, Japan, France,
Brazil, Belgium, Italy, Spain and Russia, baseball in the USA and Japan and ice hockey in Canada and
Russia, without a baseline. Every other cell was unopened when ``PREDICTIONS`` below was written and
committed (28.10.2026, before ``compute`` existed); the page prints every prediction with its result,
the misses too. A cutoff date comes from a federation rule or a published relative-age study
(``CUTOFF_SOURCES``); "unknown" cells get no prediction.

* Directional: the cell's quarter right after the cutoff (the oldest children of a cohort) is born
  more often than its quarter right before the cutoff (the youngest), against the official
  baseline: ratio > 1 with a one-sided z > 1.645.
* Sign: the most over-represented sign is one of the three signs whose days lie mostly in the three
  months after the cutoff.
* Weaker: a cell named "weaker than X" has a quarter ratio closer to 1 than X.
* Flat: famous people outside sport (politicians, writers, actors, painters, musicians,
  researchers) show no cutoff: their ratio for a 1 January and a 1 September cutoff stays within
  0.95–1.05. This is also the test of the baseline itself.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import zipfile
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'athlete-birth-signs'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'athlete_birth_signs.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('ATHLETE_SIGNS_DATA', HERE / 'athlete-signs-data'))
RAW = DATA / 'raw'
QLEVER = 'https://qlever.dev/api/wikidata'


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ groups
# Wikidata occupations (P106). A person with several occupations counts in each of them.
SPORTS = {
    'football': ('Q937857', 'Association football'),
    'basketball': ('Q3665646', 'Basketball'),
    'ice_hockey': ('Q11774891', 'Ice hockey'),
    'baseball': ('Q10871364', 'Baseball'),
    'american_football': ('Q19204627', 'American football'),
    'cricket': ('Q12299841', 'Cricket'),
    'rugby_union': ('Q14089670', 'Rugby union'),
    'rugby_league': ('Q14373094', 'Rugby league'),
    'australian_rules': ('Q13414980', 'Australian rules football'),
    'handball': ('Q12840545', 'Handball'),
    'volleyball': ('Q15117302', 'Volleyball'),
    'tennis': ('Q10833314', 'Tennis'),
    'athletics': ('Q11513337', 'Athletics'),
    'swimming': ('Q10843402', 'Swimming'),
    'cycling': ('Q2309784', 'Cycling'),
    'field_hockey': ('Q10843263', 'Field hockey'),
    'boxing': ('Q11338576', 'Boxing'),
    'badminton': ('Q13141064', 'Badminton'),
    'rowing': ('Q13382576', 'Rowing'),
    'chess': ('Q10873124', 'Chess'),
    'golf': ('Q11303721', 'Golf'),
    'jockey': ('Q846750', 'Horse racing (jockeys)'),
    'snooker': ('Q17165321', 'Snooker'),
    'darts': ('Q18574233', 'Darts'),
    'formula_one': ('Q10841764', 'Formula One'),
}
# Famous people who are not athletes: the second baseline (anyone with a sports occupation above is
# dropped from it). Same source, same date errors, same coverage by country and era as the athletes.
OTHERS = {
    'politician': ('Q82955', 'Politicians'),
    'writer': ('Q36180', 'Writers'),
    'actor': ('Q33999', 'Actors'),
    'painter': ('Q1028181', 'Painters'),
    'musician': ('Q639669', 'Musicians'),
    'researcher': ('Q1650915', 'Researchers'),
}
GROUPS = {**SPORTS, **OTHERS}
# Constituent countries of the UK: their football and rugby have their own youth systems.
UK_PARTS = {'Q21': 'GB-ENG', 'Q22': 'GB-SCT', 'Q25': 'GB-WLS', 'Q26': 'GB-NIR'}
# Historical states -> the ISO code of the successor whose births series covers the place
# (birthplace country is used first; these only matter when it is missing).
HISTORICAL = {'Q713750': 'DE', 'Q16957': 'DE', 'Q15180': 'SU', 'Q83286': 'YU', 'Q33946': 'CS'}

PREFIX = '''PREFIX wd: <http://www.wikidata.org/entity/>
PREFIX wdt: <http://www.wikidata.org/prop/direct/>
PREFIX p: <http://www.wikidata.org/prop/>
PREFIX psv: <http://www.wikidata.org/prop/statement/value/>
PREFIX wikibase: <http://wikiba.se/ontology#>
'''
Q_PEOPLE = PREFIX + '''SELECT ?h ?t ?prec ?sex ?links WHERE {
 ?h wdt:P106 wd:%s . ?h wdt:P31 wd:Q5 .
 ?h p:P569 ?st . ?st psv:P569 ?v . ?v wikibase:timeValue ?t ; wikibase:timePrecision ?prec .
 OPTIONAL { ?h wdt:P21 ?sex } OPTIONAL { ?h wikibase:sitelinks ?links }
}'''
Q_ATTR = {
    # country for sport
    'cfs': PREFIX + 'SELECT ?h ?c WHERE { ?h wdt:P106 wd:%s . ?h wdt:P31 wd:Q5 . ?h wdt:P1532 ?c . }',
    # country of the place of birth
    'bpc': PREFIX + 'SELECT ?h ?c WHERE { ?h wdt:P106 wd:%s . ?h wdt:P31 wd:Q5 . ?h wdt:P19 ?b . ?b wdt:P17 ?c . }',
    # constituent country of the UK the place of birth lies in
    'ukp': PREFIX + '''SELECT ?h ?c WHERE { ?h wdt:P106 wd:%s . ?h wdt:P31 wd:Q5 . ?h wdt:P19 ?b .
 ?b wdt:P131+ ?c . VALUES ?c { wd:Q21 wd:Q22 wd:Q25 wd:Q26 } }''',
    # citizenship
    'cit': PREFIX + 'SELECT ?h ?c WHERE { ?h wdt:P106 wd:%s . ?h wdt:P31 wd:Q5 . ?h wdt:P27 ?c . }',
}
Q_ISO = PREFIX + 'SELECT ?c ?iso WHERE { ?c wdt:P297 ?iso . }'


def qlever(query: str, dest: Path, tries: int = 6) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    body = urllib.parse.urlencode({'query': query}).encode()
    for attempt in range(tries):
        try:
            req = urllib.request.Request(QLEVER, data=body,
                                         headers={'Accept': 'text/tab-separated-values',
                                                  'User-Agent': 'startarot-research/1.0'})
            with urllib.request.urlopen(req, timeout=600) as r:
                data = r.read()
            if not data.startswith(b'?'):
                raise RuntimeError(f'unexpected answer: {data[:200]!r}')
            tmp = dest.with_suffix('.part')
            tmp.write_bytes(data)
            tmp.rename(dest)
            log(f'  {dest.name}: {data.count(b"\n") - 1} rows')
            return
        except Exception as e:  # noqa: BLE001 — network: retry
            log(f'  {dest.name}: {e}; retry {attempt + 1}')
            time.sleep(10 * (attempt + 1))
    raise SystemExit(f'QLever failed for {dest.name}')


def curl(url: str, dest: Path, tries: int = 6) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + '.part')
    for attempt in range(tries):
        r = subprocess.run(['curl', '-sSfL', '--retry', '3', '-A', 'startarot-research/1.0',
                            '-o', str(tmp), url])
        if r.returncode == 0 and tmp.stat().st_size > 0:
            tmp.rename(dest)
            log(f'  {dest.name}: {dest.stat().st_size} bytes')
            return
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f'download failed: {url}')


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    wd = RAW / 'wikidata'
    wd.mkdir(exist_ok=True)
    qlever(Q_ISO, wd / 'iso.tsv')
    for key, (qid, _) in GROUPS.items():
        log(key)
        qlever(Q_PEOPLE % qid, wd / f'{key}.people.tsv')
        for attr, q in Q_ATTR.items():
            qlever(q % qid, wd / f'{key}.{attr}.tsv')
    # Official births by month (the first baseline): Eurostat from 1960, HFD STFF from 2000.
    curl('https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/demo_fmonth?format=TSV&compressed=true',
         RAW / 'demo_fmonth.tsv.gz')
    curl('https://www.humanfertility.org/File/GetDocumentFree/STFF/stff.csv', RAW / 'stff.csv')
    # Daily births where they exist (summed to months): USA 1969–1988 and 1994–2014, France 1968–.
    gh = 'https://raw.githubusercontent.com/'
    curl(gh + 'avehtari/casestudies/master/Birthdays/data/births_usa_1969.csv', RAW / 'births_usa_1969.csv')
    curl(gh + 'fivethirtyeight/data/master/births/US_births_1994-2003_CDC_NCHS.csv', RAW / 'us_1994_2003.csv')
    curl(gh + 'fivethirtyeight/data/master/births/US_births_2000-2014_SSA.csv', RAW / 'us_2000_2014.csv')
    curl('https://www.insee.fr/fr/statistiques/fichier/8582123/T79jnais.csv', RAW / 'fr_T79jnais.csv')
    # Lahman Baseball Database (SABR, CC BY-SA 3.0): every major-league player, the check of
    # Wikidata's coverage. Read from the R package's copy (pyreadr) — SABR serves it via Box.
    curl(gh + 'cdalzell/Lahman/master/data/People.RData', RAW / 'People.RData')


# ------------------------------------------------------------------ pre-registered predictions
# (group, countries, first birth year, last birth year, cutoff month) — the cutoff is the 1st of the
# month (Japan's 2 April counts as April: 1 April babies are dropped with every 1st, see load_people).
JAN, APR, AUG, SEP, MAR = 1, 4, 8, 9, 3
CUTOFF_SOURCES = {
    'fifa_jan': 'Helsen et al. 2005, J Sports Sci 23:629 (ten European countries); Musch & Hay 1999',
    'school_sep': 'FA / ECB / RFU age groups follow the school year from 1 September; Kelly et al. 2021',
    'bcci_sep': 'BCCI Age Verification Programme rules 2025-26 (cutoff 1 September)',
    'ca_sep': 'Cricket Australia age groups, PeerJ 2019 7:e6867',
    'iihf_jan': 'Barnsley et al. 1985 (Canada); IIHF age categories by calendar year',
    'rugby_jan': 'U20 World Championship RAE study (UiTM, 2019): calendar-year cohorts',
    'au_football': 'van den Honert 2012, J Sports Sci; Musch & Hay 1999: 1 Jan -> 1 Aug (1988) -> 1 Jan (1995)',
    'mlb_intl': 'MLB Rule 3(a)(1)(B): an international amateur must be 17 by 1 September of the first season',
    'kr_school': 'Korean school year from 1 March until the 2002 birth cohort (Hangyo 2006)',
    'us_soccer': 'Smith et al. 2021, Front Sports Act Living 3:635195: 1 Aug until the 2016 reform',
}
# '*jan': every calendar-year football country of P1 plus the explored ones that switched to
# 1 January by the 1990 cohort; '*all': every country with a person in both groups.
JAN_FOOTBALL = ['DE', 'NL', 'BE', 'FR', 'IT', 'ES', 'BR', 'RU']
PREDICTIONS = [
    # id, kind, group, countries, years, cutoff month, source key, note
    ('P1', 'directional+sign', 'football', ['PT', 'AR', 'MX', 'PL', 'SE', 'NO', 'DK', 'CZ', 'HR', 'RS', 'AT',
                                            'CH', 'TR', 'GR', 'IE', 'UA', 'RO', 'HU', 'SK', 'SI', 'FI', 'CO',
                                            'UY', 'CL'], (1987, 2007), JAN, 'fifa_jan',
     'calendar-year youth football; each country is its own prediction'),
    ('P2', 'directional+sign', 'cricket', ['GB-ENG', 'IN', 'AU'], (1960, 2007), SEP, 'bcci_sep',
     'cricket age groups from 1 September'),
    ('P3', 'directional+sign', 'rugby_union', ['GB-ENG', 'GB-WLS', 'GB-SCT', 'IE'], (1960, 2007), SEP,
     'school_sep', 'rugby in the four home unions follows the school year'),
    ('P4', 'directional+sign', 'rugby_union', ['NZ', 'ZA', 'AU', 'FR', 'AR', 'IT'], (1975, 2007), JAN,
     'rugby_jan', 'calendar-year rugby'),
    ('P5', 'directional+sign', 'ice_hockey', ['SE', 'FI', 'CZ', 'SK', 'CH', 'DE', 'LV', 'NO', 'AT'],
     (1960, 2007), JAN, 'iihf_jan', 'calendar-year hockey'),
    ('P6', 'directional+sign', 'rugby_league', ['GB-ENG'], (1960, 2007), SEP, 'school_sep',
     'English rugby league, school year'),
    ('P7', 'switch', 'football', ['AU'], None, None, 'au_football',
     'Australia: cohorts 1981–1987 grew up under 1 August, 1990–2007 under 1 January. The Aug–Oct over '
     'May–Jul ratio is larger in 1981–1987 than in 1990–2007, and the Jan–Mar over Oct–Dec ratio is '
     'larger in 1990–2007 than in 1981–1987'),
    ('P8', 'directional', 'baseball', ['DO', 'VE'], (1960, 2005), SEP, 'mlb_intl',
     'international signings: 1 September eligibility (low confidence)'),
    ('P9', 'directional', 'football', ['US'], (1975, 2004), AUG, 'us_soccer',
     'US youth soccer used 1 August before 2016'),
    ('P10', 'directional', 'football', ['KR'], (1960, 2001), MAR, 'kr_school',
     'Korean school grade from 1 March (diluted by late school entry; low confidence)'),
    ('P11', 'weaker', 'football_women', ['*jan'], (1990, 2007), JAN, 'fifa_jan',
     "women's football in calendar-year countries is weaker than men's"),
    ('P12', 'weaker', 'rowing', ['*jan'], (1990, 2007), JAN, 'fifa_jan',
     'rowing (late entry, no small-child age groups) is weaker than football in the same countries'),
    ('P13', 'weaker', 'darts+snooker+jockey+golf', ['*all'], (1950, 2007), JAN, 'fifa_jan',
     'darts, snooker, jockeys and golf together are weaker than football in the same countries'),
    ('P14', 'flat', 'others', ['*all'], (1950, 2007), None, None,
     'politicians, writers, actors, painters, musicians, researchers: 1 Jan and 1 Sep ratios within 0.95–1.05'),
]


# ------------------------------------------------------------------ people
FIRST_YEAR, LAST_YEAR = 1950, 2007   # birth cohorts analysed (official baselines start in 1960)
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius',
         'Capricorn', 'Aquarius', 'Pisces']
# Conventional newspaper dates (first day of each sign); the Sun's ingress moves by a day between
# years, so the day on either side of a boundary is a cusp day and is counted where the table puts it.
SIGN_START = [(3, 21), (4, 20), (5, 21), (6, 21), (7, 23), (8, 23), (9, 23), (10, 23), (11, 22),
              (12, 22), (1, 20), (2, 19)]
DIM = [31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def sign_of(month: int, day: int) -> int:
    """Index into SIGNS of a calendar day."""
    # the last sign starting on or before the day; before 20 January it is still Capricorn
    found = 9
    for i in sorted(range(12), key=lambda i: SIGN_START[i]):
        if SIGN_START[i] <= (month, day):
            found = i
    return found


SIGN_OF = [[sign_of(m + 1, d + 1) if d < DIM[m] else -1 for d in range(31)] for m in range(12)]


def qid(cell: str) -> str:
    return cell.rsplit('/', 1)[-1].rstrip('>')


def read_tsv(path: Path) -> list[list[str]]:
    with path.open(encoding='utf-8') as f:
        next(f)
        return [line.rstrip('\n').split('\t') for line in f]


def iso_map() -> dict[str, str]:
    m = {qid(r[0]): r[1].strip('"') for r in read_tsv(RAW / 'wikidata' / 'iso.tsv')}
    m.update(HISTORICAL)
    return m


def load_people() -> tuple[dict, dict]:
    """qid -> person; plus a data-quality tally. A person: date (y, m, d), sex, sitelinks, groups,
    country code and where it came from. Only day-precision dates (Wikidata precision 11) are used:
    a year-only date is stored as 1 January and a month-only one as the 1st, exactly where a cutoff
    effect would show. A person with two different day-precision dates is dropped."""
    iso = iso_map()
    people: dict[str, dict] = {}
    tally = {'rows': 0, 'not_day_precision': 0, 'conflicting_dates': 0, 'out_of_range': 0}
    for key in GROUPS:
        base = RAW / 'wikidata'
        for r in read_tsv(base / f'{key}.people.tsv'):
            tally['rows'] += 1
            h = qid(r[0])
            t, prec = r[1].strip('"'), r[2].strip('"')
            p = people.setdefault(h, {'dates': set(), 'imprecise': False, 'groups': set(), 'sex': '',
                                      'links': 0, 'cfs': set(), 'bpc': set(), 'ukp': set(), 'cit': set()})
            p['groups'].add(key)
            if prec.split('^')[0] != '11':
                p['imprecise'] = True
            else:
                ymd = t.split('T')[0].split('^')[0]
                neg = ymd.startswith('-')
                y, m, d = ymd.lstrip('-').split('-')
                if not neg:
                    p['dates'].add((int(y), int(m), int(d)))
            if len(r) > 3 and r[3]:
                p['sex'] = {'Q6581097': 'm', 'Q6581072': 'f'}.get(qid(r[3]), p['sex'] or 'o')
            if len(r) > 4 and r[4]:
                p['links'] = max(p['links'], int(r[4].split('^')[0].strip('"')))
        for attr in Q_ATTR:
            for r in read_tsv(base / f'{key}.{attr}.tsv'):
                h = qid(r[0])
                if h in people and len(r) > 1:
                    people[h][attr].add(qid(r[1]))
    out = {}
    for h, p in people.items():
        if not p['dates']:
            tally['not_day_precision'] += 1
            continue
        if len(p['dates']) > 1:
            tally['conflicting_dates'] += 1
            continue
        y, m, d = next(iter(p['dates']))
        if not (FIRST_YEAR <= y <= LAST_YEAR) or not (1 <= m <= 12 and 1 <= d <= DIM[m - 1]):
            tally['out_of_range'] += 1
            continue
        code, how = assign_country(p, iso)
        out[h] = {'y': y, 'm': m, 'd': d, 'sex': p['sex'], 'links': p['links'], 'groups': p['groups'],
                  'country': code, 'country_from': how}
    tally['people'] = len(out)
    return out, tally


def assign_country(p: dict, iso: dict) -> tuple[str | None, str]:
    """Where the person grew up in sport, as well as Wikidata can tell: 'country for sport' if it
    names one country; else the country of the place of birth (with the UK split into its four
    football nations); else a single citizenship."""
    def codes(qids):
        out = set()
        for q in qids:
            if q in UK_PARTS:
                out.add(UK_PARTS[q])
            elif q in iso:
                out.add(iso[q])
        return out
    cfs = codes(p['cfs'])
    if len(cfs) == 1:
        c = next(iter(cfs))
        if c == 'GB' and len(p['ukp']) == 1:
            c = UK_PARTS[next(iter(p['ukp']))]
        return c, 'country for sport'
    bpc = codes(p['bpc'])
    if len(p['ukp']) == 1 and (not bpc or bpc <= {'GB', 'IE'}):
        return UK_PARTS[next(iter(p['ukp']))], 'place of birth'
    if len(bpc) == 1:
        return next(iter(bpc)), 'place of birth'
    cit = codes(p['cit'])
    if len(cit) == 1:
        return next(iter(cit)), 'citizenship'
    return None, 'unknown'


# ------------------------------------------------------------------ official baseline
# ISO 3166 -> entity of the births tables (Eurostat's codes; UK nations use the UK series)
def entity_of(code: str | None) -> str | None:
    if code is None:
        return None
    if code.startswith('GB'):
        return 'UK'
    return {'GR': 'EL'}.get(code, code)


# Series counted by month of REGISTRATION (offices closed at weekends) or with untraceable gaps are
# not a baseline of births: the screen of the 710-million-births study (rarest-zodiac-sign).
EUROSTAT_NOT_USED = {'UA', 'AZ', 'MD', 'XK'}
STFF_ENTITY = {'AUT': 'AT', 'BEL': 'BE', 'BGR': 'BG', 'CHE': 'CH', 'CZE': 'CZ', 'DNK': 'DK', 'ESP': 'ES',
               'EST': 'EE', 'FIN': 'FI', 'GRC': 'EL', 'HRV': 'HR', 'HUN': 'HU', 'IRL': 'IE', 'ISL': 'IS',
               'ITA': 'IT', 'LTU': 'LT', 'LUX': 'LU', 'LVA': 'LV', 'NLD': 'NL', 'NOR': 'NO', 'PRT': 'PT',
               'ROU': 'RO', 'SRB': 'RS', 'SVN': 'SI', 'SWE': 'SE', 'DEUTNP': 'DE', 'AUS': 'AU', 'CAN': 'CA',
               'CHL': 'CL', 'ISR': 'IL', 'JPN': 'JP', 'KOR': 'KR', 'NZL': 'NZ', 'SGP': 'SG', 'USA': 'US',
               'RUS': 'RU', 'GBR_NP': 'UK', 'SVK': 'SK', 'POL': 'PL'}
# last year STFF metadata (23.02.2026) calls final and by date of occurrence
STFF_FINAL = {'AUT': 2024, 'BEL': 2024, 'BGR': 2024, 'CHE': 2024, 'CZE': 2024, 'DNK': 2024, 'ESP': 2023,
              'EST': 2024, 'FIN': 2024, 'GRC': 2023, 'HRV': 2024, 'HUN': 2024, 'IRL': 2023, 'ISL': 2024,
              'ITA': 2023, 'LTU': 2023, 'LUX': 2024, 'LVA': 2024, 'NLD': 2023, 'NOR': 2024, 'PRT': 2024,
              'ROU': 2023, 'SRB': 2024, 'SVN': 2024, 'SWE': 2024, 'DEUTNP': 2024, 'AUS': 2023, 'CAN': 2023,
              'CHL': 2022, 'ISR': 2023, 'JPN': 2024, 'KOR': 2023, 'NZL': 2024, 'SGP': 2024, 'USA': 2024,
              'RUS': 2020, 'GBR_NP': 2022, 'SVK': 2015, 'POL': 2022}
STFF_FIRST = {'GBR_NP': 2006}
MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
             'October', 'November', 'December']
MAX_UNKNOWN_MONTH = 0.02
# A country-year whose smallest month, per day, is under this share of its yearly mean per day is a
# broken series (a month reported late, e.g. Eurostat Poland 1995 with December at 0.65) and is dropped:
# real birth seasons stay within about ±15%. Added after the critic's review of 28.10.2026.
MIN_MONTH_SHARE = 0.8
# A cohort year without its own baseline borrows the nearest year of the same country within this.
MAX_BASELINE_GAP = 10


def official_baseline() -> tuple[dict, dict]:
    """(entity, year) -> 12 monthly birth counts, and (entity, year) -> source. Priority: daily
    series > HFD STFF > Eurostat."""
    import numpy as np
    import pandas as pd
    base, src = {}, {}
    t = pd.read_csv(RAW / 'demo_fmonth.tsv.gz', sep='\t', dtype=str)
    key = t.columns[0]
    parts = t[key].str.split(',', expand=True)
    parts.columns = ['freq', 'unit', 'month', 'geo']
    t = pd.concat([parts, t.drop(columns=key)], axis=1).melt(
        id_vars=['freq', 'unit', 'month', 'geo'], var_name='year', value_name='v')
    t['year'] = t.year.str.strip().astype(int)
    t['flag'] = t.v.str.extract(r'([a-z]+)\s*$')[0].fillna('')
    t['v'] = pd.to_numeric(t.v.str.replace(r'[^0-9.]', '', regex=True), errors='coerce')
    t = t[t.v.notna()]
    # Germany with the GDR, metropolitan France: 'DE' is without the GDR, 'FR' with overseas from 1994
    t = t[~t.geo.isin(['DE', 'FR'])]
    t.loc[t.geo == 'DE_TOT', 'geo'] = 'DE'
    t.loc[t.geo == 'FX', 'geo'] = 'FR'
    t = t[(t.geo.str.len() == 2) & ~t.geo.isin(EUROSTAT_NOT_USED)]
    last = t.groupby('geo').year.transform('max')
    t = t[~(t.flag.str.contains('p') & (t.year >= last - 1))]
    for (geo, year), g in t.groupby(['geo', 'year']):
        m = {r.month: r.v for r in g.itertuples()}
        months = [m.get(f'M{i:02d}') for i in range(1, 13)]
        if any(v is None for v in months):
            continue
        known = sum(months)
        if m.get('UNK', 0) > MAX_UNKNOWN_MONTH * (known + m.get('UNK', 0)) or known <= 0:
            continue
        base[(geo, year)] = np.array(months, dtype=float)
        src[(geo, year)] = 'Eurostat'
    s = pd.read_csv(RAW / 'stff.csv', na_values='.')
    for code, ent in STFF_ENTITY.items():
        for r in s[(s.CountryCode == code) & s.Year.between(STFF_FIRST.get(code, 2000), STFF_FINAL[code])].itertuples():
            months = [getattr(r, m) for m in MONTHS_EN]
            if any(pd.isna(v) for v in months):
                continue
            base[(ent, int(r.Year))] = np.array(months, dtype=float)
            src[(ent, int(r.Year))] = 'HFD STFF'
    for ent, series in daily_series().items():
        frame = series.groupby([series.index.year, series.index.month]).sum()
        for year in sorted({y for y, _ in frame.index}):
            months = [frame.get((year, m)) for m in range(1, 13)]
            if any(v is None or v != v for v in months):
                continue
            base[(ent, int(year))] = np.array(months, dtype=float)
            src[(ent, int(year))] = 'daily'
    for k in list(base):
        per_day = base[k] / np.array(DIM, dtype=float)
        if per_day.min() < MIN_MONTH_SHARE * per_day.mean():
            del base[k], src[k]
    return base, src


def daily_series() -> dict:
    import pandas as pd
    out = {}
    a = pd.read_csv(RAW / 'births_usa_1969.csv')
    a = a[a.year <= 1988]
    a = pd.Series(a.births.values, index=pd.to_datetime(dict(year=a.year, month=a.month, day=a.day)))
    b = pd.read_csv(RAW / 'us_1994_2003.csv')
    b = b[b.year < 2000]
    c = pd.read_csv(RAW / 'us_2000_2014.csv')
    bc = pd.concat([b, c])
    bc = pd.Series(bc.births.values, index=pd.to_datetime(dict(year=bc.year, month=bc.month, day=bc.date_of_month)))
    out['US'] = pd.concat([a, bc]).sort_index()
    f = pd.read_csv(RAW / 'fr_T79jnais.csv', sep=';', dtype=str)
    f = f[(f.CHAMP2 == 'FM') & (f.JOUR != 'MM') & (f.NBNAIS != 'so')]
    year_col = [c for c in f.columns if c.startswith('ANNEE')][0]
    idx = pd.to_datetime(f[year_col] + '-' + f.MOIS + '-' + f.JOUR, errors='coerce')
    keep = idx.notna().values
    out['FR'] = pd.Series(f.NBNAIS.astype(int).values[keep], index=idx[keep]).sort_index()
    return out


# ------------------------------------------------------------------ cells
def leap(y: int) -> bool:
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


def day_mask():
    """12×31: valid calendar days other than the 1st of a month (29 February counts)."""
    import numpy as np
    m = np.zeros((12, 31), dtype=bool)
    for mo in range(12):
        m[mo, 1:DIM[mo]] = True
    return m


# Countries mostly south of the equator: their fallback is the southern official season.
SOUTH = {'AR', 'AU', 'NZ', 'ZA', 'BR', 'UY', 'CL', 'PE', 'BO', 'PY', 'ZW', 'ZM', 'MZ', 'MG', 'NA', 'BW', 'LS',
         'SZ', 'AO', 'MW', 'FJ', 'PG', 'TZ', 'RW', 'BI', 'MU', 'SB', 'VU', 'WS', 'TO'}
SOUTH_SERIES = ('AU', 'NZ', 'CL')
MIN_OTHERS = 2000         # famous non-athletes of a country within ±10 birth years for their own season


class Baselines:
    """Expected births per calendar day for a country and birth year. ``mode``: 'main' (official
    births; else the nearest official year; else famous non-athletes of the same country; else the
    official season of the hemisphere), 'flat' (every day alike) or 'others' (famous non-athletes
    only, wherever there are enough) — the last two are the robustness runs."""

    def __init__(self, people: dict, mode: str = 'main'):
        import numpy as np
        self.np = np
        self.mode = mode
        self.official, self.source = official_baseline()
        self.years_of = {}
        for (ent, y) in self.official:
            self.years_of.setdefault(ent, []).append(y)
        # second baseline: famous people outside sport, per entity and birth year
        self.others = {}
        for p in people.values():
            if p['groups'] & set(SPORTS) or not p['groups'] & set(OTHERS):
                continue
            ent = entity_of(p['country'])
            if ent is None:
                continue
            arr = self.others.setdefault(ent, np.zeros((LAST_YEAR - FIRST_YEAR + 1, 12, 31)))
            arr[p['y'] - FIRST_YEAR, p['m'] - 1, p['d'] - 1] += 1
        # hemisphere seasons: the births-per-day profile of every official series with EQUAL weight
        # (summing counts would make the north the USA and Japan); the north year by year
        self.north, south = {}, np.zeros(12)
        for (ent, y), months in self.official.items():
            per_day = months / np.array([DIM[m] if m != 1 else (29 if leap(y) else 28) for m in range(12)])
            share = per_day / per_day.sum()
            if ent in SOUTH_SERIES:
                south += share
            elif ent not in SOUTH:
                self.north[y] = self.north.get(y, 0) + share
        self.south = south / south.sum()
        self.cache = {}

    def _fill(self, per_day_by_month, year):
        np = self.np
        mat = np.zeros((12, 31))
        for mo in range(12):
            n = DIM[mo] if mo != 1 else (29 if leap(year) else 28)
            mat[mo, :n] = per_day_by_month[mo]
        return mat

    def _monthly(self, months, year):
        days = [DIM[mo] if mo != 1 else (29 if leap(year) else 28) for mo in range(12)]
        return [months[mo] / days[mo] for mo in range(12)]

    def _others(self, ent, year):
        o = self.others.get(ent)
        if o is None:
            return None
        lo, hi = max(year - 10, FIRST_YEAR), min(year + 10, LAST_YEAR)
        block = o[lo - FIRST_YEAR:hi - FIRST_YEAR + 1].sum(axis=0)
        if block[:, 1:].sum() < MIN_OTHERS:
            return None
        # the 1sts of the others are as unreliable as the athletes': per month the mean of days 2..
        return [block[mo, 1:DIM[mo] if mo != 1 else 28].mean() for mo in range(12)]

    def year_matrix(self, ent: str, year: int):
        """12×31 share of a year's births per calendar day (uniform within a month), and how it
        was found: 'official', 'nearest year', 'others', 'hemisphere', 'flat'."""
        np = self.np
        key = (ent, year)
        if key in self.cache:
            return self.cache[key]
        per_day, how = None, None
        if self.mode == 'flat':
            per_day, how = [1.0] * 12, 'flat'
        elif self.mode == 'others':
            per_day = self._others(ent, year)
            how = 'others' if per_day is not None else None
        else:
            if (ent, year) in self.official:
                per_day, how = self._monthly(self.official[(ent, year)], year), 'official'
            elif ent in self.years_of:
                near = min(self.years_of[ent], key=lambda y: (abs(y - year), y))
                if abs(near - year) <= MAX_BASELINE_GAP:
                    per_day, how = self._monthly(self.official[(ent, near)], near), 'nearest year'
            if per_day is None:
                per_day = self._others(ent, year)
                how = 'others' if per_day is not None else None
            if per_day is None:
                if ent in SOUTH:
                    per_day, how = list(self.south), 'hemisphere'
                else:
                    y = min(self.north, key=lambda k: (abs(k - year), k))
                    per_day, how = list(self.north[y] / self.north[y].sum()), 'hemisphere'
        if per_day is None:
            per_day, how = [1.0] * 12, 'flat'
        mat = self._fill(per_day, year)
        mat = mat / mat.sum()
        self.cache[key] = (mat, how)
        return mat, how


def cell(people_list, bl: Baselines) -> dict:
    """Observed and expected counts (12×31, 1sts masked) for a list of people, and the share of
    expected weight by baseline kind."""
    import numpy as np
    obs = np.zeros((12, 31))
    exp = np.zeros((12, 31))
    kinds = {}
    by_year = {}
    for p in people_list:
        obs[p['m'] - 1, p['d'] - 1] += 1
        ent = entity_of(p['country'])
        by_year[(ent, p['y'])] = by_year.get((ent, p['y']), 0) + 1
    for (ent, y), n in by_year.items():
        mat, how = bl.year_matrix(ent, y)
        exp += n * mat
        kinds[how] = kinds.get(how, 0) + n
    mask = day_mask()
    o = np.where(mask, obs, 0)
    e = np.where(mask, exp, 0)
    if e.sum() > 0:
        e = e * o.sum() / e.sum()
    total = sum(kinds.values()) or 1
    return {'obs': o, 'exp': e, 'n': int(len(people_list)), 'n_used': int(o.sum()),
            'baseline': {k: round(v / total, 4) for k, v in sorted(kinds.items())}}


def month_ratio(c):
    o, e = c['obs'].sum(axis=1), c['exp'].sum(axis=1)
    return o, e


def sign_counts(c):
    import numpy as np
    o, e = np.zeros(12), np.zeros(12)
    for mo in range(12):
        for d in range(DIM[mo]):
            s = SIGN_OF[mo][d]
            o[s] += c['obs'][mo, d]
            e[s] += c['exp'][mo, d]
    return o, e


def quarter_ratio(c, cutoff: int) -> dict:
    """Oldest quarter (the three months from the cutoff) against the youngest (the three before),
    each observed over expected; z of the log ratio with Poisson errors."""
    o, e = month_ratio(c)
    old = [(cutoff - 1 + k) % 12 for k in range(3)]
    young = [(cutoff - 1 + k) % 12 for k in range(9, 12)]
    oo, eo, oy, ey = o[old].sum(), e[old].sum(), o[young].sum(), e[young].sum()
    if min(oo, oy) == 0 or min(eo, ey) == 0:
        return {'ratio': None, 'z': None, 'lo': None, 'hi': None}
    lr = math.log((oo / eo) / (oy / ey))
    se = math.sqrt(1 / oo + 1 / oy)
    return {'ratio': math.exp(lr), 'z': lr / se, 'lo': math.exp(lr - 1.96 * se), 'hi': math.exp(lr + 1.96 * se)}


def top_signs_after(cutoff: int) -> list[int]:
    """The three signs whose days lie mostly in the three months from the cutoff."""
    months = {(cutoff - 1 + k) % 12 for k in range(3)}
    share = []
    for s in range(12):
        days = [(mo, d) for mo in range(12) for d in range(DIM[mo]) if SIGN_OF[mo][d] == s and not (mo == 1 and d == 28)]
        share.append((sum(1 for mo, _ in days if mo in months) / len(days), s))
    return [s for sh, s in sorted(share, reverse=True)[:3]]


# ------------------------------------------------------------------ compute
MIN_CELL = 300            # people in a sport × country cell before it gets its own wheel
EXPLORED = {('football', c) for c in ['DE', 'NL', 'GB-ENG', 'GB-SCT', 'GB-WLS', 'GB-NIR', 'JP', 'FR', 'BR',
                                      'BE', 'IT', 'ES', 'RU']} | {('baseball', 'US'), ('baseball', 'JP'),
                                                                   ('ice_hockey', 'CA'), ('ice_hockey', 'RU')}
# Documented cutoffs (sport, country, first year, last year, cutoff month, source key) — the cells of
# the "collapse" figure. The explored cells are here too; the predictions are scored separately.
DOCUMENTED = (
    [('football', c, 1990, 2007, JAN, 'fifa_jan') for c in JAN_FOOTBALL + PREDICTIONS[0][3]]
    + [('football', c, 1960, 1979, AUG, 'de_be_switch') for c in ['DE', 'BE']]
    + [('football', 'GB-ENG', 1960, 2007, SEP, 'school_sep'), ('football', 'JP', 1960, 2007, APR, 'jp_school'),
       ('baseball', 'JP', 1960, 2007, APR, 'jp_school'), ('baseball', 'US', 1950, 1993, AUG, 'little_league'),
       ('baseball', 'US', 1994, 2007, 5, 'little_league'), ('football', 'AU', 1981, 1987, AUG, 'au_football'),
       ('football', 'AU', 1990, 2007, JAN, 'au_football'), ('football', 'US', 1975, 2004, AUG, 'us_soccer')]
    + [('ice_hockey', c, 1960, 2007, JAN, 'iihf_jan') for c in ['CA', 'RU'] + PREDICTIONS[4][3]]
    + [('cricket', c, 1960, 2007, SEP, 'bcci_sep') for c in PREDICTIONS[1][3]]
    + [('rugby_union', c, 1960, 2007, SEP, 'school_sep') for c in PREDICTIONS[2][3]]
    + [('rugby_union', c, 1975, 2007, JAN, 'rugby_jan') for c in PREDICTIONS[3][3]]
    + [('rugby_league', 'GB-ENG', 1960, 2007, SEP, 'school_sep')]
)
CUTOFF_SOURCES.update({
    'de_be_switch': 'Germany and Belgium: 1 August until 1997 (Helsen et al. 2000; Ostapczuk & Musch 2013)',
    'jp_school': 'Japanese school year from 2 April (J-League RAE studies, IJSSC 2022)',
    'little_league': 'Little League: 31 July until 2006, then 30 April (littleleague.org; Slate 2008)',
})
EXPERIMENT_BINS = 3       # birth years per point of the natural-experiment series
FAKE_DRAWS = 10000        # random wrong cutoffs per documented cell
MIN_ERA_CELL = 200        # people in a sport × country × era cell of the lookup
LOOKUP_ERAS = {'all': (FIRST_YEAR, LAST_YEAR), 'before1985': (FIRST_YEAR, 1984), 'from1985': (1985, LAST_YEAR)}
# Cells printed in full on the page: name, sport, country, birth years
ERAS = [('de_early', 'football', 'DE', 1956, 1979), ('de_late', 'football', 'DE', 1990, 2007),
        ('nl_early', 'football', 'NL', 1956, 1979), ('nl_late', 'football', 'NL', 1990, 2007),
        ('be_early', 'football', 'BE', 1956, 1979), ('be_late', 'football', 'BE', 1990, 2007),
        ('eng', 'football', 'GB-ENG', 1956, 2007), ('jp', 'football', 'JP', 1956, 2007),
        ('jp_baseball', 'baseball', 'JP', 1956, 2007), ('us_baseball_early', 'baseball', 'US', 1950, 1993),
        ('us_baseball_late', 'baseball', 'US', 1994, 2007), ('ca_hockey', 'ice_hockey', 'CA', 1950, 2007),
        ('in_cricket', 'cricket', 'IN', 1950, 2007), ('eng_cricket', 'cricket', 'GB-ENG', 1950, 2007),
        ('jan_football', 'football', None, 1990, 2007)]


_MEMBERS: dict = {}


def members(people: dict, group: str) -> list:
    """Men of a sport ('football_women': women footballers); 'others': famous non-athletes."""
    key = (id(people), group)
    if key not in _MEMBERS:
        _MEMBERS[key] = _members(people, group)
    return _MEMBERS[key]


def _members(people: dict, group: str) -> list:
    if group == 'football_women':
        return [p for p in people.values() if 'football' in p['groups'] and p['sex'] == 'f']
    if group == 'others':
        return [p for p in people.values() if p['groups'] & set(OTHERS) and not p['groups'] & set(SPORTS)]
    if group in OTHERS:
        return [p for p in people.values() if group in p['groups'] and not p['groups'] & set(SPORTS)]
    keys = group.split('+')
    return [p for p in people.values() if p['groups'] & set(keys) and p['sex'] == 'm']


def pick(lst, countries=None, years=None, links=None):
    out = []
    for p in lst:
        if countries is not None and p['country'] not in countries:
            continue
        if years is not None and not (years[0] <= p['y'] <= years[1]):
            continue
        if links is not None and not (links[0] <= p['links'] < links[1]):
            continue
        out.append(p)
    return out


def summary(c, cutoffs=(JAN, APR, AUG, SEP)) -> dict:
    mo, me = month_ratio(c)
    so, se = sign_counts(c)
    sr = [float(o / e) if e > 0 else None for o, e in zip(so, se)]
    valid = [i for i in range(12) if sr[i] is not None]
    return {'n': c['n'], 'n_used': c['n_used'], 'baseline': c['baseline'],
            'month_obs': [int(x) for x in mo], 'month_exp': [round(float(x), 2) for x in me],
            'sign_obs': [int(x) for x in so], 'sign_exp': [round(float(x), 2) for x in se],
            'sign_ratio': [round(x, 4) if x is not None else None for x in sr],
            'top_sign': max(valid, key=lambda i: sr[i]) if valid else None,
            'bottom_sign': min(valid, key=lambda i: sr[i]) if valid else None,
            'quarters': {str(k): {kk: (round(v, 4) if v is not None else None) for kk, v in quarter_ratio(c, k).items()}
                         for k in cutoffs}}


def lahman_people() -> list:
    import pyreadr
    t = list(pyreadr.read_r(str(RAW / 'People.RData')).values())[0]
    t = t[(t.birthCountry == 'USA') & t.birthYear.between(FIRST_YEAR, LAST_YEAR) & t.birthMonth.notna() & t.birthDay.notna()]
    return [{'y': int(r.birthYear), 'm': int(r.birthMonth), 'd': int(r.birthDay), 'country': 'US', 'links': 0,
             'sex': 'm', 'groups': {'baseball'}} for r in t.itertuples()]


def score_predictions(people, bl) -> list:
    out = []
    men_football = members(people, 'football')
    for pid, kind, group, countries, years, cutoff, src, note in PREDICTIONS:
        if kind in ('directional+sign', 'directional'):
            lst = members(people, group)
            for ctry in countries:
                c = cell(pick(lst, {ctry}, years), bl)
                q = quarter_ratio(c, cutoff)
                so, se = sign_counts(c)
                top = int(max(range(12), key=lambda i: so[i] / se[i] if se[i] else -1)) if c['n_used'] else None
                hit_dir = q['z'] is not None and q['z'] > 1.645
                row = {'id': pid, 'kind': kind, 'group': group, 'country': ctry, 'years': list(years),
                       'cutoff': cutoff, 'n': c['n_used'], 'ratio': q['ratio'], 'lo': q['lo'], 'hi': q['hi'],
                       'z': q['z'], 'hit_direction': bool(hit_dir), 'top_sign': top, 'note': note, 'source': src}
                if kind == 'directional+sign':
                    row['predicted_signs'] = top_signs_after(cutoff)
                    row['hit_sign'] = top in row['predicted_signs'] if top is not None else False
                out.append(row)
        elif kind == 'switch':
            lst = members(people, group)
            a = cell(pick(lst, set(countries), (1981, 1987)), bl)
            b = cell(pick(lst, set(countries), (1990, 2007)), bl)
            qa_aug, qb_aug = quarter_ratio(a, AUG), quarter_ratio(b, AUG)
            qa_jan, qb_jan = quarter_ratio(a, JAN), quarter_ratio(b, JAN)
            hit = all(x['ratio'] is not None for x in (qa_aug, qb_aug, qa_jan, qb_jan)) and \
                qa_aug['ratio'] > qb_aug['ratio'] and qb_jan['ratio'] > qa_jan['ratio']
            out.append({'id': pid, 'kind': kind, 'group': group, 'country': countries[0], 'note': note,
                        'source': src, 'n_early': a['n_used'], 'n_late': b['n_used'],
                        'aug_early': qa_aug, 'aug_late': qb_aug, 'jan_early': qa_jan, 'jan_late': qb_jan,
                        'hit': bool(hit)})
        elif kind == 'weaker':
            ctry = set(JAN_FOOTBALL + PREDICTIONS[0][3]) if countries == ['*jan'] else None
            lst = pick(members(people, group), ctry, years)
            if ctry is None:
                ctry = {p['country'] for p in lst}
            ref = cell(pick(men_football, ctry, years), bl)
            c = cell(lst, bl)
            q, qr = quarter_ratio(c, cutoff), quarter_ratio(ref, cutoff)
            hit = q['ratio'] is not None and qr['ratio'] is not None and abs(math.log(q['ratio'])) < abs(math.log(qr['ratio']))
            out.append({'id': pid, 'kind': kind, 'group': group, 'note': note, 'source': src, 'n': c['n_used'],
                        'ratio': q['ratio'], 'lo': q['lo'], 'hi': q['hi'], 'ref_n': ref['n_used'],
                        'ref_ratio': qr['ratio'], 'hit': bool(hit)})
        elif kind == 'flat':
            rows = []
            for g in OTHERS:
                c = cell(pick(members(people, g), None, years), bl)
                rows.append({'group': g, 'n': c['n_used'], 'jan': quarter_ratio(c, JAN), 'sep': quarter_ratio(c, SEP)})
            hit = all(0.95 <= r[k]['ratio'] <= 1.05 for r in rows for k in ('jan', 'sep'))
            out.append({'id': pid, 'kind': kind, 'group': group, 'note': note, 'rows': rows, 'hit': bool(hit)})
    return out


def compute():
    import numpy as np
    people, tally = load_people()
    log('people', tally)
    # Wikidata's 1sts: day 1 of each month against the mean of days 2–28, before any masking
    first = []
    for mo in range(12):
        days = np.zeros(31)
        for p in people.values():
            if p['m'] == mo + 1:
                days[p['d'] - 1] += 1
        first.append(round(float(days[0] / days[1:28].mean()), 3))
    tally['first_of_month_ratio'] = first
    bl = Baselines(people)
    res = {'tally': tally, 'groups': {k: v[1] for k, v in GROUPS.items()}, 'signs': SIGNS,
           'sign_start': SIGN_START, 'first_year': FIRST_YEAR, 'last_year': LAST_YEAR}
    # country source tally
    src = {}
    for p in people.values():
        src[p['country_from']] = src.get(p['country_from'], 0) + 1
    res['country_from'] = src
    # sports pooled and sport × country cells
    res['sports'], res['cells'] = {}, {}
    for key in list(SPORTS) + ['football_women']:
        lst = members(people, key)
        c = cell([p for p in lst if p['country']], bl)
        res['sports'][key] = summary(c)
        by = {}
        for p in lst:
            if p['country']:
                by.setdefault(p['country'], []).append(p)
        for ctry, ps in by.items():
            if len(ps) >= MIN_CELL:
                res['cells'].setdefault(key, {})[ctry] = summary(cell(ps, bl))
        log(key, len(lst), 'cells', len(res['cells'].get(key, {})))
    for key in OTHERS:
        res['sports'][key] = summary(cell([p for p in members(people, key) if p['country']], bl))
    # natural experiments: quarter ratios by birth-year bin
    exps = {}
    lah = lahman_people()
    series_def = [('football', 'DE'), ('football', 'NL'), ('football', 'BE'), ('football', 'AU'),
                  ('baseball', 'US'), ('lahman', 'US'), ('football', 'GB-ENG'), ('football', 'JP')]
    for group, ctry in series_def:
        lst = lah if group == 'lahman' else pick(members(people, group), {ctry})
        pts = []
        for y0 in range(1956, LAST_YEAR + 1, EXPERIMENT_BINS):
            y1 = min(y0 + EXPERIMENT_BINS - 1, LAST_YEAR)
            c = cell(pick(lst, None, (y0, y1)), bl)
            if c['n_used'] < 60:
                continue
            pts.append({'years': [y0, y1], 'n': c['n_used'],
                        **{f'q{k}': quarter_ratio(c, k) for k in (JAN, APR, 5, AUG, SEP)},
                        'month_obs': [int(x) for x in month_ratio(c)[0]],
                        'month_exp': [round(float(x), 2) for x in month_ratio(c)[1]]})
        exps[f'{group}:{ctry}'] = pts
    res['experiments'] = exps
    # Lahman against Wikidata, same cohorts
    wd_us = pick(members(people, 'baseball'), {'US'})
    lv = {}
    for name, yrs in [('1950-1993', (1950, 1993)), ('1994-2005', (1994, 2005))]:
        a, b = cell(pick(lah, None, yrs), bl), cell(pick(wd_us, None, yrs), bl)
        ra = month_ratio(a)[0] / month_ratio(a)[1]
        rb = month_ratio(b)[0] / month_ratio(b)[1]
        lv[name] = {'lahman': summary(a, (AUG, 5)), 'wikidata': summary(b, (AUG, 5)),
                    'month_corr': round(float(np.corrcoef(ra, rb)[0, 1]), 4)}
    res['lahman'] = lv
    # collapse: month ratio by months since the cutoff, every documented cell
    col = []
    pooled_o, pooled_e = np.zeros(12), np.zeros(12)
    for sport, ctry, y0, y1, cut, srckey in DOCUMENTED:
        c = cell(pick(members(people, sport), {ctry}, (y0, y1)), bl)
        if c['n_used'] < 200:
            continue
        o, e = month_ratio(c)
        idx = [(cut - 1 + k) % 12 for k in range(12)]
        ro, re_ = o[idx], e[idx]
        pooled_o += ro
        pooled_e += re_
        col.append({'sport': sport, 'country': ctry, 'years': [y0, y1], 'cutoff': cut, 'source': srckey,
                    'explored': (sport, ctry) in EXPLORED, 'n': c['n_used'],
                    'by_month_since': [round(float(a / b), 4) if b else None for a, b in zip(ro, re_)],
                    'by_calendar_month': [round(float(a / b), 4) if b else None for a, b in zip(o, e)]})
    res['collapse'] = {'cells': col, 'pooled': [round(float(a / b), 4) for a, b in zip(pooled_o, pooled_e)],
                       'pooled_obs': [int(x) for x in pooled_o], 'pooled_exp': [round(float(x), 1) for x in pooled_e]}
    # fake cutoffs: every documented cell gets a wrong cutoff month at random; how often does the
    # pooled oldest-over-youngest quarter ratio reach the real one?
    rng = np.random.default_rng(20261028)
    obs_cal = []
    for sport, ctry, y0, y1, cut, srckey in DOCUMENTED:
        c = cell(pick(members(people, sport), {ctry}, (y0, y1)), bl)
        if c['n_used'] < 200:
            continue
        o, e = month_ratio(c)
        obs_cal.append((o, e, cut, (sport, ctry) in EXPLORED))

    def pooled_q(cells, cuts):
        oo = oy = eo = ey = 0.0
        for (o, e, *_), k in zip(cells, cuts):
            old = [(k - 1 + j) % 12 for j in range(3)]
            young = [(k - 1 + j) % 12 for j in range(9, 12)]
            oo += o[old].sum(); eo += e[old].sum(); oy += o[young].sum(); ey += e[young].sum()
        return (oo / eo) / (oy / ey)

    def fake_test(cells):
        real = pooled_q(cells, [c for _, _, c, _ in cells])
        fakes = []
        for _ in range(FAKE_DRAWS):
            cuts = [(true - 1 + int(rng.integers(1, 12))) % 12 + 1 for _, _, true, _ in cells]
            fakes.append(pooled_q(cells, cuts))
        fakes = np.array(fakes)
        return {'real': real, 'draws': FAKE_DRAWS, 'max_fake': float(fakes.max()),
                'p95_fake': float(np.quantile(fakes, 0.95)), 'median_fake': float(np.median(fakes)),
                'share_at_least_real': float((fakes >= real).mean()), 'cells': len(cells),
                'min_players': 200}
    # All documented cells, and — because most of them use 1 January, and a Jan–Mar excess common
    # to all athletes for any other reason would also beat random dates — the other cutoffs alone.
    res['fake_cutoffs'] = fake_test(obs_cal)
    res['fake_cutoffs']['jan_cells'] = sum(1 for _, _, c, _ in obs_cal if c == JAN)
    res['fake_cutoffs_other'] = fake_test([x for x in obs_cal if x[2] != JAN])
    # The same, without the cells of the first look (their cutoffs were chosen with the data seen):
    # only groups whose cutoff was predicted blind. Added after the critic's review of 28.10.2026.
    blind = [x for x in obs_cal if x[2] != JAN and not x[3]]
    res['fake_cutoffs_blind'] = fake_test(blind)
    # eras of the headline countries: full sign and month tables
    res['eras'] = {}
    for name, sport, ctry, y0, y1 in ERAS:
        res['eras'][name] = {'sport': sport, 'country': ctry, 'years': [y0, y1],
                             **summary(cell(pick(members(people, sport),
                                                 set(JAN_FOOTBALL + PREDICTIONS[0][3]) if ctry is None else {ctry},
                                                 (y0, y1)), bl), (JAN, APR, 5, AUG, SEP))}
    lah_early = cell(pick(lah, None, (1950, 1993)), bl)
    lah_late = cell(pick(lah, None, (1994, 2005)), bl)
    res['eras']['lahman_early'] = {'sport': 'baseball', 'country': 'US', 'years': [1950, 1993],
                                   **summary(lah_early, (JAN, APR, 5, AUG, SEP))}
    res['eras']['lahman_late'] = {'sport': 'baseball', 'country': 'US', 'years': [1994, 2005],
                                  **summary(lah_late, (JAN, APR, 5, AUG, SEP))}
    # the lookup: sport × country × era
    look = {}
    for key in list(SPORTS) + ['football_women']:
        lst = [p for p in members(people, key) if p['country']]
        by = {}
        for p in lst:
            by.setdefault(p['country'], []).append(p)
        for ctry, ps in by.items():
            for era, (y0, y1) in LOOKUP_ERAS.items():
                sel = pick(ps, None, (y0, y1))
                if len(sel) < (MIN_CELL if era == 'all' else MIN_ERA_CELL):
                    continue
                c = cell(sel, bl)
                so, se = sign_counts(c)
                mo, me = month_ratio(c)
                look.setdefault(key, {}).setdefault(ctry, {})[era] = {
                    'n': c['n_used'], 'sign_obs': [int(x) for x in so], 'sign_exp': [round(float(x), 2) for x in se],
                    'month_obs': [int(x) for x in mo], 'month_exp': [round(float(x), 2) for x in me],
                    'baseline': c['baseline']}
    res['lookup'] = look
    # fame: football, calendar-year countries, 1990–2007, by Wikipedia editions (sitelinks)
    fb = pick(members(people, 'football'), set(JAN_FOOTBALL + PREDICTIONS[0][3]), (1990, 2007))
    links = sorted(p['links'] for p in fb)
    edges = [links[int(len(links) * q)] for q in (0, 0.5, 0.8, 0.95, 0.99)] + [10 ** 9]
    fame = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        if lo == hi:
            continue
        c = cell(pick(fb, None, None, (lo, hi)), bl)
        fame.append({'links': [lo, hi], 'n': c['n_used'], 'q': quarter_ratio(c, JAN)})
    res['fame'] = fame
    res['predictions'] = score_predictions(people, bl)
    # the non-athletes against official births only (the main baseline borrows from them elsewhere)
    po = []
    for g in OTHERS:
        lst = [p for p in members(people, g) if p['country']
               and bl.year_matrix(entity_of(p['country']), p['y'])[1] in ('official', 'nearest year')]
        c = cell(lst, bl)
        po.append({'group': g, 'n': c['n_used'], **{str(k): quarter_ratio(c, k) for k in (JAN, APR, AUG, SEP)}})
    res['placebo_official'] = po
    # where the expected counts of the headline cells come from
    # the same predictions against the two other baselines: every day alike, famous non-athletes
    res['robustness'] = {}
    for mode in ('flat', 'others'):
        res['robustness'][mode] = score_predictions(people, Baselines(people, mode))
    res['cutoff_sources'] = CUTOFF_SOURCES
    # overall baseline mix
    allc = cell([p for p in people.values() if p['country'] and p['groups'] & set(SPORTS)], bl)
    res['baseline_mix'] = allc['baseline']
    res['n_athletes'] = sum(1 for p in people.values() if p['groups'] & set(SPORTS))
    res['n_athletes_country'] = allc['n']
    res['n_others'] = sum(1 for p in people.values() if p['groups'] & set(OTHERS) and not p['groups'] & set(SPORTS))

    def clean(x):
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, (np.floating, float)):
            return None if x != x else round(float(x), 5)
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, set):
            return sorted(x)
        return x
    (DATA / 'computed.json').write_text(json.dumps(clean(res), ensure_ascii=False))
    log('computed.json written')


# ------------------------------------------------------------------ validate
def validate() -> bool:
    """Checks that do not depend on what the page wants to say. Writes validation.json; export
    refuses to run while it lists problems."""
    r = json.loads((DATA / 'computed.json').read_text())
    problems, notes = [], []
    # the sign table: every day of a leap year has exactly one sign, 29–32 days each
    days = [sum(1 for mo in range(12) for d in range(DIM[mo]) if SIGN_OF[mo][d] == s) for s in range(12)]
    if sum(days) != 366 or not all(29 <= d <= 32 for d in days):
        problems.append(f'sign table: days per sign {days}')
    if [SIGN_OF[m - 1][d - 1] for m, d in [(3, 20), (3, 21), (1, 19), (1, 20), (12, 21), (12, 22)]] != [11, 0, 9, 10, 8, 9]:
        problems.append('sign boundaries moved')
    t = r['tally']
    if t['people'] < 1_000_000:
        problems.append(f"only {t['people']} people with a day-precision date in {FIRST_YEAR}–{LAST_YEAR}")
    # the 1st of January is where imprecise dates gather; it must stand out (else the masking
    # rationale is gone) and the other 1sts must not stand out much more than ordinary days
    f = t['first_of_month_ratio']
    if f[0] < 1.5:
        notes.append(f'1 January is only {f[0]}× an ordinary January day')
    if max(f[1:]) > 1.5:
        problems.append(f'a 1st other than 1 January stands out: {f}')
    # observed and expected totals agree in every cell (expected is scaled to the used days)
    for key, v in r['sports'].items():
        if abs(sum(v['sign_obs']) - sum(v['sign_exp'])) > 0.01 * max(1, sum(v['sign_obs'])):
            problems.append(f'{key}: observed and expected totals differ')
    # Lahman (every major leaguer) against Wikidata: same month pattern before 1994
    corr = r['lahman']['1950-1993']['month_corr']
    if corr < 0.8:
        problems.append(f'Lahman and Wikidata disagree on US baseball months (r = {corr})')
    # Wikidata covers most major leaguers born in the USA
    nl, nw = r['lahman']['1950-1993']['lahman']['n_used'], r['lahman']['1950-1993']['wikidata']['n_used']
    if nw < 0.8 * nl:
        problems.append(f'Wikidata has {nw} US baseball players vs {nl} major leaguers in Lahman')
    # baselines: the robustness runs exist and agree on the prediction tally within two cells
    def hits(preds):
        return sum(p.get('hit_direction', False) for p in preds if p['kind'].startswith('directional'))
    main = hits(r['predictions'])
    for mode, preds in r['robustness'].items():
        if abs(hits(preds) - main) > 2:
            notes.append(f'baseline {mode}: {hits(preds)} directional hits vs {main}')
    # every prediction of the pre-registration is scored
    ids = {p['id'] for p in r['predictions']}
    if ids != {p[0] for p in PREDICTIONS}:
        problems.append(f'unscored predictions: {sorted({p[0] for p in PREDICTIONS} - ids)}')
    out = {'problems': problems, 'notes': notes}
    (DATA / 'validation.json').write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for x in problems:
        log('PROBLEM', x)
    for x in notes:
        log('note', x)
    log('validation', 'failed' if problems else 'passed')
    return not problems


# ------------------------------------------------------------------ export
def _round(x, digits=4):
    if isinstance(x, dict):
        return {k: _round(v, digits) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, digits) for v in x]
    if isinstance(x, float):
        return round(x, digits)
    return x


def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed — run validate and resolve its problems first')
    r = json.loads((DATA / 'computed.json').read_text())
    keep_q = lambda q: {k: q[k] for k in ('ratio', 'lo', 'hi', 'z')}  # noqa: E731
    slim = lambda v: {k: v[k] for k in ('n_used', 'sign_obs', 'sign_exp', 'sign_ratio', 'top_sign',  # noqa: E731
                                        'bottom_sign', 'month_obs', 'month_exp', 'quarters', 'baseline')}
    out = {
        'generated_by': 'scripts/research/athlete_birth_signs.py',
        'signs': SIGNS, 'sign_start': SIGN_START, 'first_year': FIRST_YEAR, 'last_year': LAST_YEAR,
        'groups': r['groups'] | {'football_women': 'Women’s football', 'football': 'Association football'},
        'sports_keys': list(SPORTS), 'others_keys': list(OTHERS),
        'tally': r['tally'], 'country_from': r['country_from'], 'baseline_mix': r['baseline_mix'],
        'n_athletes': r['n_athletes'], 'n_athletes_country': r['n_athletes_country'], 'n_others': r['n_others'],
        'sports': {k: slim(v) for k, v in r['sports'].items()},
        'eras': {k: {'sport': v['sport'], 'country': v['country'], 'years': v['years'], **slim(v)}
                 for k, v in r['eras'].items()},
        'experiments': {k: [{'years': p['years'], 'n': p['n'],
                             **{f'q{c}': keep_q(p[f'q{c}']) for c in (JAN, APR, 5, AUG, SEP)}} for p in pts]
                        for k, pts in r['experiments'].items()},
        'lahman': {k: {'month_corr': v['month_corr'], 'lahman_n': v['lahman']['n_used'],
                       'wikidata_n': v['wikidata']['n_used'],
                       'lahman_q': v['lahman']['quarters'], 'wikidata_q': v['wikidata']['quarters']}
                   for k, v in r['lahman'].items()},
        'collapse': r['collapse'], 'fake_cutoffs': r['fake_cutoffs'],
        'fake_cutoffs_other': r['fake_cutoffs_other'], 'fake_cutoffs_blind': r['fake_cutoffs_blind'],
        'placebo_official': r['placebo_official'],
        'fame': r['fame'],
        'predictions': r['predictions'],
        'robustness': {mode: [{k: p.get(k) for k in ('id', 'country', 'group', 'ratio', 'hit_direction', 'hit_sign', 'hit')}
                              for p in preds] for mode, preds in r['robustness'].items()},
        'cutoff_sources': r['cutoff_sources'],
        'lookup': {sport: {c: {era: {'n': v['n'], 'sign_obs': v['sign_obs'], 'sign_exp': v['sign_exp']}
                               for era, v in eras.items()} for c, eras in cells.items()}
                   for sport, cells in r['lookup'].items()},
    }
    JSON_OUT.write_text(json.dumps(_round(out), ensure_ascii=False, separators=(',', ':')) + '\n')
    # dataset: observed and expected counts by sign and by month (no individual people)
    rows = []
    for sport, cells in r['lookup'].items():
        for ctry, eras in cells.items():
            for era, v in eras.items():
                y0, y1 = LOOKUP_ERAS[era]
                for unit, obs, exp in (('sign', v['sign_obs'], v['sign_exp']), ('month', v['month_obs'], v['month_exp'])):
                    labels = SIGNS if unit == 'sign' else MONTHS_EN
                    for lab, o, e in zip(labels, obs, exp):
                        rows.append([sport, ctry, f'{y0}-{y1}', unit, lab, o, f'{e:.2f}',
                                     f'{o / e:.4f}' if e else '', v['baseline'].get('official', 0) + v['baseline'].get('nearest year', 0)])
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['group', 'country', 'birth_years', 'unit', 'label', 'observed', 'expected', 'ratio',
                    'official_baseline_share'])
        w.writerows(rows)
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    steps = {'fetch': fetch, 'compute': compute, 'validate': validate, 'export': export}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    ok = steps[sys.argv[1]]()
    sys.exit(1 if ok is False else 0)
