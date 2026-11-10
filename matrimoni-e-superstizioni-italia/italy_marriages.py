#!/usr/bin/env python3
"""Marriages in Italy by month, rite and province: leap years, Lent, May, November and retrograde Venus and Mars.

Source of the numbers on https://startarot.online/it/research/matrimoni-e-superstizioni-italia

Needs Python 3.10+ and
    pip install numpy pandas
plus ``curl``. The raw tables (about 25 MB) go to $IT_MARRIAGES_DATA (default: ./italy-marriages-data next
to this script). Steps, in order:

    python3 italy_marriages.py fetch      # ISTAT and Eurostat tables
    python3 italy_marriages.py compute    # tables + calendar + estimates -> $IT_MARRIAGES_DATA
    python3 italy_marriages.py validate   # months against years, rites against totals, provinces against regions
    python3 italy_marriages.py export     # page JSON + dataset CSV (+ a copy of this script in the repo)

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/italy-marriages.json      data the page renders
    frontend/static/research/italy-marriages.csv        the open dataset (long format)
    frontend/static/research/italy_marriages.py         a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

What is counted
---------------
Marriages CELEBRATED in Italy (religious "concordatario" marriages and civil ones), by the month and the
province where they were celebrated, as the civil registrars report them to ISTAT on form D.3. Civil
unions (from June 2016) are not marriages and are not counted.

Sources
-------
* ISTAT, I.Stat / esploradati, dataflow 24_186_DF_DCIS_MATRDEMO_7 "Matrimoni — rito, mese di celebrazione":
  marriages by month (and year) × rite (all / religious / civil) × territory (Italy, the five parts, 21
  regions and autonomous provinces, the provinces), 2004–2024. Territory names: codelist CL_ITTER107.
* Eurostat, demo_nind (indicator MARRIAGE, Italy): marriages by year, 1960–2024. The national series is
  Eurostat's for 1960–2003 and ISTAT's from 2004: the two agree to the unit in every year but 2012, where
  Eurostat prints 208,947 and ISTAT (the table and its 2012 report) 207,138 (``KNOWN_DIFFERENCES``).
* ISTAT reports "Matrimoni, unioni civili, separazioni e divorzi" for 2023 and 2024: the shares by day of the
  week (printed figures only — no series is published; see ``WEEKDAY_REPORTS``).
* retrograde-periods.csv of https://startarot.online/research/retrograde-planets-1900-2100 (Venus and Mars
  stations, computed with the Swiss Ephemeris).
The date of each marriage is collected (form D.3) but not published: no microdata file of marriages exists
among ISTAT's public, standard or research files (checked 23 October 2026). Days of the week, the 17th and
"beautiful" dates therefore cannot be measured here.

Method
------
* Leap years: each year against its centred 2×4-year moving average (``cycle_ratios``), nationally on the
  1960–2024 series (1962–2017) and by province on ISTAT's (2006–2017: leap years 2008, 2012, 2016). Years whose
  five-year window touches 2020 are left out.
* Months (``monthly_models``), 2004–2024 without 2020 and 2021 (COVID-19: receptions were banned until 15 June
  2021), for religious and civil marriages separately: log marriages per day on year and month effects, each
  month's own linear drift, the number of Fridays, Saturdays, Sundays and public holidays, the share of the
  month in Lent (Ash Wednesday to Holy Saturday) and the shares with Venus and with Mars retrograde.
  Significance by randomisation: Easter dates swapped between years, the retrograde calendars shifted round
  the span. Civil marriages are the control: the Church's calendar should not move them.
* Months against their neighbours (``neighbour_test``): log(per-day rate of a month) − the mean of its two
  neighbours, averaged over the years, religious minus civil — where the Church side leaves a gap the season
  does not explain (May for the folk saying and Ovid's "mense malas Maio nubere", November for the month of
  the dead). May is judged on the years when April holds no Lent (``may_clean``); November also against the
  year's average day (``november_vs_average``), since the January–February base itself emptied over the
  period.
* Provinces whose borders changed in 2004–2024 are merged into stable units (``MERGES``); Sardinia, whose
  provinces were redrawn twice and whose four 2005–2016 provinces are missing from the table (2006–2016), is
  one unit.

Raw files are checked against the SHA-256 of their CONTENT (``content_digest``: the parsed rows, sorted),
pinned in ``CONTENT_SHA256``: the services restamp their files on every release, so a byte hash would
change with nothing changed. A different content digest stops ``fetch``: ISTAT or Eurostat revised the
numbers — look at what changed, then update the pin.
"""
from __future__ import annotations

import argparse
import calendar as cal_mod
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'matrimoni-e-superstizioni-italia'
FILE_STEM = 'italy-marriages'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'italy_marriages.py'
    RETRO_CSV = REPO_ROOT / 'frontend' / 'static' / 'research' / 'retrograde-periods.csv'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
    RETRO_CSV = HERE / 'retrograde-periods.csv'
RETRO_URL = 'https://startarot.online/research/retrograde-periods.csv'
DATA = Path(os.environ.get('IT_MARRIAGES_DATA') or HERE / 'italy-marriages-data')
RAW = DATA / 'raw'
UA = 'Mozilla/5.0 (research script; startarot.online)'

ISTAT_SDMX = 'https://esploradati.istat.it/SDMXWS/rest/'
SOURCES = {
    'istat_month_rite': (ISTAT_SDMX + 'data/IT1,24_186_DF_DCIS_MATRDEMO_7,1.0/all',
                         'application/vnd.sdmx.data+csv;version=1.0.0', 'istat_month_rite.csv'),
    'istat_territories': (ISTAT_SDMX + 'codelist/IT1/CL_ITTER107/latest', 'application/xml',
                          'istat_cl_itter107.xml'),
    'eurostat_annual': ('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_nind'
                        '?geo=IT&indic_de=MARRIAGE&format=JSON&lang=EN', 'application/json',
                        'eurostat_demo_nind_it.json'),
}
# SHA-256 of each source's parsed content (see the docstring); ``fetch`` prints the digest of an unpinned one.
CONTENT_SHA256: dict[str, str] = {
    'istat_month_rite': 'e623ad1535ef7fa5df92bb71e4b6f0c210bb2e5e6e19ebd92cf69a2b242cf048',
    'istat_territories': '3ba6e73f681c5fc40f611641401f4816f37d1215752546220dbe2b230e131a18',
    'eurostat_annual': '44cb8cdfd5dcce9fcb3564383652880d98b8810363c10a531a3cd94f1d2a9b2a',
}

FIRST_YEAR_ISTAT, LAST_YEAR_ISTAT = 2004, 2024
FIRST_YEAR_EU, LAST_YEAR_EU = 1960, 2024
SHOCK_YEARS = {2020}
# COVID-19: 2020 lost two thirds of its religious weddings, and receptions stayed banned until 15 June 2021.
EXCLUDED_YEARS = {2020: 'COVID-19: lockdown from March, ceremonies limited for the rest of the year',
                  2021: 'COVID-19: wedding receptions banned until 15 June 2021, a backlog after'}
MONTHS = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEPT', 'OCT', 'NOV', 'DEC']
RITES = {'ALL': 'all', 'REL': 'religious', 'CIVIL': 'civil'}
# The three parts the page compares: North (North-West + North-East), Centre, South with the islands.
MACRO = {'ITCD': 'Nord', 'ITE': 'Centro', 'ITFG': 'Mezzogiorno'}
# Provinces whose borders changed in 2004–2024, merged into units with one border throughout:
# Monza e della Brianza left Milano, Fermo left Ascoli Piceno, Barletta-Andria-Trani took comuni from Bari
# and Foggia (all three in the table from 2010); seven comuni of the Valmarecchia left Pesaro e Urbino for
# Rimini in 2009 (Pesaro −18 % in 2010 against −6 % for Italy). Sardinia is one unit (see the docstring).
MERGES = {
    'ITC45+IT108': ('Milano e Monza-Brianza', ['ITC45', 'IT108']),
    'ITE34+IT109': ('Ascoli Piceno e Fermo', ['ITE34', 'IT109']),
    'ITF41+ITF42+IT110': ('Bari, Foggia e Barletta-Andria-Trani', ['ITF41', 'ITF42', 'IT110']),
    'ITE31+ITD59': ('Pesaro e Urbino e Rimini', ['ITE31', 'ITD59']),
}
SARDINIA = 'ITG2'
# Years where Eurostat and ISTAT print different national totals; ISTAT, the source, is used.
KNOWN_DIFFERENCES = {2012: 'Eurostat 208,947; ISTAT 207,138 (table and the report "Il matrimonio in Italia, anno 2012")'}
# Day-of-week shares in ISTAT's reports (no series is published). Saturday and Tuesday are printed in the
# text (per cent of the marriages of each rite; "all_saturday" counts marriages and civil unions together, as
# the reports do). The other days are only drawn, in Figure 6: Friday is read off the 2024 chart (about 14 %
# of religious and 15 % of civil marriages, ±1 point) — the second day after Saturday in church, about level
# with Thursday at the town hall. The 2023
# report also ranks the dates: Saturday 17 June 2023, at the June peak, came only tenth.
WEEKDAY_REPORTS = {
    2023: {'url': 'https://www.istat.it/wp-content/uploads/2024/11/REPORT_MATRIMONI-UNIONI-SEPARAZIONI_dati-2023_22novembre2024.pdf',
           'all_saturday': 46.2, 'religious_saturday': 53.1, 'religious_tuesday': 3.5, 'civil_tuesday': 6.1,
           'june_17_rank': 10},
    2024: {'url': 'https://www.istat.it/wp-content/uploads/2026/01/MATRIMONI-UNIONI-SEPARAZIONI-DIVORZI_anno-2024.pdf',
           'all_saturday': 46.2, 'religious_saturday': 54.8, 'religious_tuesday': 3.3, 'civil_tuesday': 6.3,
           'religious_friday_from_chart': 14, 'civil_friday_from_chart': 15, 'friday_rank_from_chart': 2},
}


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ downloads
def curl(url: str, accept: str, dest: Path, tries: int = 6) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + '.part')
    for i in range(tries):
        r = subprocess.run(['curl', '-sSL', '-f', '-A', UA, '-H', f'Accept: {accept}', '-m', '600', '-o', str(tmp), url])
        if r.returncode == 0 and tmp.stat().st_size > 0:
            tmp.rename(dest)
            return
        time.sleep(15 * (i + 1))  # the ISTAT service limits requests per minute
    raise RuntimeError(f'download failed: {url}')


def content_rows(key: str) -> list[tuple]:
    """The rows a source contributes, as sorted tuples of strings (the base of ``content_digest``)."""
    p = RAW / SOURCES[key][2]
    if key == 'istat_month_rite':
        t = pd.read_csv(p, dtype=str)
        cols = ['REF_AREA', 'MARRIAGE_RITE', 'MONTH_CELEBRATION', 'TIME_PERIOD', 'OBS_VALUE']
        return sorted(map(tuple, t[cols].fillna('').values.tolist()))
    if key == 'istat_territories':
        return sorted((c, n or '', par or '') for c, (n, par) in territories().items())
    if key == 'eurostat_annual':
        return sorted((str(y), str(v)) for y, v in eurostat_series().items())
    raise KeyError(key)


def content_digest(key: str) -> str:
    h = hashlib.sha256()
    for row in content_rows(key):
        h.update(('\t'.join(row) + '\n').encode())
    return h.hexdigest()


def fetch():
    digests = {}
    for key, (url, accept, name) in SOURCES.items():
        log(f'{key}: {url}')
        curl(url, accept, RAW / name)
        d = content_digest(key)
        if CONTENT_SHA256.get(key) and CONTENT_SHA256[key] != d:
            raise RuntimeError(f'{name}: content SHA-256 {d} differs from the pinned {CONTENT_SHA256[key]} — the '
                               f'source revised its numbers; inspect them, then update CONTENT_SHA256["{key}"]')
        digests[key] = d
    if not RETRO_CSV.exists():
        curl(RETRO_URL, 'text/csv', DATA / 'retrograde-periods.csv')
    missing = [k for k in SOURCES if not CONTENT_SHA256.get(k)]
    if missing:
        log('unpinned sources — paste into CONTENT_SHA256:')
        for k in missing:
            log(f"    '{k}': '{digests[k]}',")


# ------------------------------------------------------------------ reading
def territories() -> dict[str, tuple[str | None, str | None]]:
    """Territory code -> (Italian name, parent code), from the SDMX codelist."""
    s = (RAW / SOURCES['istat_territories'][2]).read_text(encoding='utf-8')
    out = {}
    for c in re.finditer(r'<structure:Code id="([^"]+)"[^>]*>(.*?)</structure:Code>', s, re.S):
        name = re.search(r'<common:Name xml:lang="it">([^<]+)', c.group(2))
        parent = re.search(r'<structure:Parent>\s*<Ref id="([^"]+)"', c.group(2))
        out[c.group(1)] = (name.group(1).strip() if name else None, parent.group(1) if parent else None)
    return out


def eurostat_series() -> dict[int, int]:
    d = json.loads((RAW / SOURCES['eurostat_annual'][2]).read_text())
    index = d['dimension']['time']['category']['index']
    year_of = {i: int(y) for y, i in index.items()}
    return {year_of[int(i)]: int(round(v)) for i, v in d['value'].items()}


def national_annual(eu: pd.Series, istat: pd.DataFrame) -> pd.DataFrame:
    """year, marriages, source: Eurostat before ISTAT's first year, ISTAT from it."""
    it = istat[(istat.area == 'IT') & (istat.rite == 'ALL') & (istat.month == 0)].set_index('year').marriages
    rows = [{'year': int(y), 'marriages': int(v), 'source': 'Eurostat demo_nind'} for y, v in eu.items() if y < FIRST_YEAR_ISTAT]
    rows += [{'year': int(y), 'marriages': int(v), 'source': 'ISTAT 24_186_DF_DCIS_MATRDEMO_7'} for y, v in it.items()]
    return pd.DataFrame(rows).sort_values('year').reset_index(drop=True)


def read_istat() -> pd.DataFrame:
    """Long table: area, rite, year, month (1–12, 0 = the year), marriages."""
    t = pd.read_csv(RAW / SOURCES['istat_month_rite'][2], dtype={'REF_AREA': str, 'TIME_PERIOD': int})
    t = t[t.DATA_TYPE == 'MARRG_FROM2017'] if 'DATA_TYPE' in t else t
    month = {m: i + 1 for i, m in enumerate(MONTHS)} | {'YEAR': 0}
    out = pd.DataFrame({'area': t.REF_AREA, 'rite': t.MARRIAGE_RITE, 'year': t.TIME_PERIOD,
                        'month': t.MONTH_CELEBRATION.map(month), 'marriages': t.OBS_VALUE.astype(int)})
    if out.month.isna().any():
        raise RuntimeError(f'unknown month labels: {sorted(t.MONTH_CELEBRATION[out.month.isna()].unique())}')
    out['month'] = out.month.astype(int)
    return out.sort_values(['area', 'rite', 'year', 'month']).reset_index(drop=True)


def area_levels(names: dict, areas: set[str]) -> dict[str, list[str]]:
    """The codes of each level present in the table: regions (incl. the autonomous provinces of Bolzano and
    Trento, without the Trentino-Alto Adige total), provinces (NUTS-3 and the IT1xx codes of new ones)."""
    parts = {'ITC', 'ITD', 'ITE', 'ITF', 'ITG'}
    regions = sorted(a for a in areas if names.get(a, (None, None))[1] in parts and a != 'ITDA')
    provinces = sorted(a for a in areas if (len(a) == 5 and a[:4] in regions) or a.startswith('IT1'))
    return {'regions': regions, 'provinces': provinces}


def region_of(code: str, names: dict) -> str:
    return code[:4] if not code.startswith('IT1') else names[code][1]


def stable_units(istat: pd.DataFrame, names: dict, levels: dict) -> tuple[pd.DataFrame, dict]:
    """Marriages by stable unit (``MERGES``, Sardinia whole), every month and year, every rite."""
    merged = {p: u for u, (_, ps) in MERGES.items() for p in ps}
    rows = []
    unit_meta = {}
    for p in levels['provinces']:
        reg = region_of(p, names)
        if reg == SARDINIA:
            continue
        u = merged.get(p, p)
        unit_meta[u] = {'name': MERGES[u][0] if u in MERGES else names[p][0], 'region': reg}
        rows.append(istat[istat.area == p].assign(unit=u))
    rows.append(istat[istat.area == SARDINIA].assign(unit=SARDINIA))
    unit_meta[SARDINIA] = {'name': names[SARDINIA][0], 'region': SARDINIA}
    u = pd.concat(rows).groupby(['unit', 'rite', 'year', 'month'], as_index=False).marriages.sum()
    return u, unit_meta


# ------------------------------------------------------------------ calendar
def easter(y: int) -> dt.date:
    """Western Easter (Gregorian computus, Meeus/Jones/Butcher)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return dt.date(y, month, day + 1)


def public_holidays(y: int) -> set[dt.date]:
    """National public holidays (law 260/1949 as amended; 2 June again from 2001), with Easter Monday.
    Patron saints' days are local and left out."""
    md = [(1, 1), (1, 6), (4, 25), (5, 1), (8, 15), (11, 1), (12, 8), (12, 25), (12, 26)] + [(6, 2)] * (y >= 2001)
    return {dt.date(y, m, d) for m, d in md} | {easter(y) + dt.timedelta(days=1)}


def lent_days(e: dt.date) -> set[dt.date]:
    """Ash Wednesday (Easter − 46) to Holy Saturday."""
    return {e + dt.timedelta(days=i) for i in range(-46, 0)}


def retro_days(planet: str) -> set[dt.date]:
    p = RETRO_CSV if RETRO_CSV.exists() else DATA / 'retrograde-periods.csv'
    t = pd.read_csv(p)
    t = t[t.planet == planet]
    days = set()
    for _, r in t.iterrows():
        a = dt.date.fromisoformat(r.station_retrograde_utc[:10])
        b = dt.date.fromisoformat(r.station_direct_utc[:10])
        days |= {a + dt.timedelta(days=i) for i in range((b - a).days + 1)}
    return days


# Years the page's date checker accepts; the retrograde periods are exported for them.
CHECKER_YEARS = (2026, 2035)


def retrograde_upcoming() -> list[dict]:
    """Venus and Mars retrograde periods (station to station, UTC dates) that touch CHECKER_YEARS."""
    p = RETRO_CSV if RETRO_CSV.exists() else DATA / 'retrograde-periods.csv'
    t = pd.read_csv(p)
    lo, hi = f'{CHECKER_YEARS[0]}-01-01', f'{CHECKER_YEARS[1]}-12-31'
    rows = []
    for _, r in t[t.planet.isin(['Venus', 'Mars'])].iterrows():
        a, b = r.station_retrograde_utc[:10], r.station_direct_utc[:10]
        if b >= lo and a <= hi:
            rows.append({'planet': r.planet, 'from': a, 'to': b})
    return sorted(rows, key=lambda x: x['from'])


def month_days(y: int, m: int) -> list[dt.date]:
    return [dt.date(y, m, d) for d in range(1, cal_mod.monthrange(y, m)[1] + 1)]


def calendar(years: range) -> pd.DataFrame:
    """Per year and month: days, Fridays, Saturdays, Sundays, public holidays, days of Lent, days with Venus
    and with Mars retrograde."""
    venus, mars = retro_days('Venus'), retro_days('Mars')
    rows = []
    for y in years:
        hol, lent = public_holidays(y), lent_days(easter(y))
        for m in range(1, 13):
            days = month_days(y, m)
            rows.append({'year': y, 'month': m, 'days': len(days),
                         'fridays': sum(d.weekday() == 4 for d in days),
                         'saturdays': sum(d.weekday() == 5 for d in days),
                         'sundays': sum(d.weekday() == 6 for d in days),
                         'holidays': sum(d in hol for d in days),
                         'lent_days': sum(d in lent for d in days),
                         'venus_retro_days': sum(d in venus for d in days),
                         'mars_retro_days': sum(d in mars for d in days)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ estimates
MA_WEIGHTS = (0.125, 0.25, 0.25, 0.25, 0.125)  # centred 2×4 moving average: one weight per leap phase


def cycle_ratios(s: pd.Series) -> pd.DataFrame:
    """log(marriages in a year / their centred 2×4-year moving average), with the year's place in the leap
    cycle (phase 0 = leap year). The 2×4 average gives every phase of the cycle the same weight, so it keeps
    the trend and drops the cycle; the mean log ratio by phase is the cycle itself. Years whose five-year
    window touches SHOCK_YEARS are left out."""
    rows = []
    for y in s.index:
        win = range(y - 2, y + 3)
        if all(w in s.index for w in win) and not (set(win) & SHOCK_YEARS):
            ma = sum(w_ * s[w] for w_, w in zip(MA_WEIGHTS, win))
            rows.append({'year': int(y), 'phase': int(y % 4), 'log_ratio': float(np.log(s[y] / ma))})
    return pd.DataFrame(rows, columns=['year', 'phase', 'log_ratio'])


MODEL_YEARS = [y for y in range(FIRST_YEAR_ISTAT, LAST_YEAR_ISTAT + 1) if y not in EXCLUDED_YEARS]
MODEL_TERMS = ['fridays', 'saturdays', 'sundays', 'holidays', 'lent_share', 'venus_share', 'mars_share']
PERMUTATIONS = 2000
SEED = 20261023


def model_frame(monthly: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    """``monthly``: year, month, marriages (one rite of one area)."""
    d = monthly[monthly.year.isin(MODEL_YEARS) & (monthly.month > 0)].merge(cal, on=['year', 'month'])
    d = d.sort_values(['year', 'month']).reset_index(drop=True)
    d['lent_share'] = d.lent_days / d.days
    d['venus_share'] = d.venus_retro_days / d.days
    d['mars_share'] = d.mars_retro_days / d.days
    d['y'] = np.log(d.marriages.clip(lower=0.5) / d.days)
    return d


def design(d: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Year effects, month effects, a linear drift of each month's effect (the season moved as religious
    weddings fell from two thirds to two fifths of the total), and the calendar terms. January is the base."""
    t = (d.year - 2014).astype(float)
    month = pd.get_dummies(d.month, prefix='m').astype(float).iloc[:, 1:]
    X = pd.concat([pd.get_dummies(d.year, prefix='y').astype(float), month,
                   month.mul(t, axis=0).add_suffix('_drift'), d[MODEL_TERMS].astype(float)], axis=1)
    return X.values, list(X.columns)


def fit(d: pd.DataFrame) -> tuple[dict[str, float], np.ndarray, dict[str, float]]:
    X, names = design(d)
    b, *_ = np.linalg.lstsq(X, d.y.values, rcond=None)
    res = d.y.values - X @ b
    dof = len(d) - np.linalg.matrix_rank(X)
    cov = (res @ res / dof) * np.linalg.pinv(X.T @ X)
    return dict(zip(names, b)), res, dict(zip(names, np.sqrt(np.diag(cov))))


def lent_shares(y: int, e: dt.date) -> np.ndarray:
    lent = lent_days(e)
    return np.array([sum(x in lent for x in month_days(y, m)) / cal_mod.monthrange(y, m)[1] for m in range(1, 13)])


def permutation_draws(d: pd.DataFrame, rng: np.random.Generator) -> dict[str, np.ndarray]:
    """The model's lent, Venus and Mars coefficients under PERMUTATIONS randomisations each:
    * Lent: every model year gets the Easter (day of the year) of another model year;
    * Venus, Mars: the day-by-day retrograde calendar shifted round 2004–2024 by a random offset of 60 days or
      more (a multiple of the synodic period nearly reproduces the real calendar; such draws belong to the
      null distribution all the same)."""
    years = MODEL_YEARS
    doy = {y: (easter(y) - dt.date(y, 1, 1)).days for y in years}
    shares = {(y, s): lent_shares(y, dt.date(y, 1, 1) + dt.timedelta(days=doy[s])) for y in years for s in years}
    rows = list(zip(d.year, d.month - 1))
    out = {'lent_share': [], 'venus_share': [], 'mars_share': []}
    for _ in range(PERMUTATIONS):
        src = dict(zip(years, rng.permutation(years)))
        dp = d.copy()
        dp['lent_share'] = [shares[(y, src[y])][m] for y, m in rows]
        out['lent_share'].append(fit(dp)[0]['lent_share'])
    start, end = dt.date(FIRST_YEAR_ISTAT, 1, 1), dt.date(LAST_YEAR_ISTAT, 12, 31)
    span = (end - start).days + 1
    all_days = [start + dt.timedelta(days=i) for i in range(span)]
    month_of_day = np.array([(x.year - start.year) * 12 + x.month - 1 for x in all_days])
    days_in = np.bincount(month_of_day)
    row_month = ((d.year - start.year) * 12 + d.month - 1).values
    for planet, term in (('Venus', 'venus_share'), ('Mars', 'mars_share')):
        retro = retro_days(planet)
        v = np.array([x in retro for x in all_days], dtype=float)
        for _ in range(PERMUTATIONS):
            k = int(rng.integers(60, span - 60))
            share = np.bincount(month_of_day, weights=np.roll(v, k), minlength=len(days_in)) / days_in
            dp = d.copy()
            dp[term] = share[row_month]
            out[term].append(fit(dp)[0][term])
    return {k: np.array(v) for k, v in out.items()}


def summary(obs: float, ols_se: float, perm: np.ndarray) -> dict:
    """Coefficient per whole month (a month spent entirely in Lent, with Venus retrograde, …), its
    randomisation p-value, and the smallest effect the data can show (80 % power, two-sided 5 %: about
    2.8 × the spread of the permuted coefficients)."""
    mde = 2.8 * float(perm.std())
    edges = np.linspace(-4 * perm.std(), 4 * perm.std(), 33)
    counts, _ = np.histogram(np.clip(perm, edges[0], edges[-1]), bins=edges)
    return {'coef': round(float(obs), 4), 'pct': round(100 * float(np.exp(obs) - 1), 1),
            'perm_hist': {'edges': [round(float(e), 5) for e in edges], 'counts': counts.tolist()},
            'ols_se': round(float(ols_se), 4), 'perm_sd': round(float(perm.std()), 4),
            'p_value': round(float((np.sum(np.abs(perm) >= abs(obs)) + 1) / (len(perm) + 1)), 4),
            'mde_log': round(mde, 4), 'mde_pct_up': round(100 * (np.exp(mde) - 1), 1),
            'mde_pct_down': round(100 * (np.exp(-mde) - 1), 1),
            # 95 % interval of the effect from the spread of the randomised coefficients
            'ci95_pct': [round(100 * (float(np.exp(obs - 1.96 * perm.std())) - 1), 1),
                         round(100 * (float(np.exp(obs + 1.96 * perm.std())) - 1), 1)]}


def monthly_models(istat: pd.DataFrame, cal: pd.DataFrame) -> dict:
    """The calendar terms of the monthly model for religious and for civil marriages (Italy as a whole), each
    with a randomisation test instead of the textbook standard error (months of one year share a level and
    neighbouring months share weather, so the OLS error is too optimistic)."""
    rng = np.random.default_rng(SEED)
    out = {'years': MODEL_YEARS, 'excluded_years': EXCLUDED_YEARS, 'permutations': PERMUTATIONS}
    for rite in ('REL', 'CIVIL'):
        d = model_frame(istat[(istat.area == 'IT') & (istat.rite == rite)], cal)
        b, res, se = fit(d)
        perm = permutation_draws(d, rng)
        out[RITES[rite]] = {
            'months': int(len(d)), 'residual_sd': round(float(res.std(ddof=0)), 4),
            **{k: summary(b[k], se[k], perm[k]) for k in ('lent_share', 'venus_share', 'mars_share')},
            'other_terms': {k: {'coef': round(float(b[k]), 4), 'pct': round(100 * float(np.exp(b[k]) - 1), 1),
                                'ols_se': round(float(se[k]), 4)} for k in ('fridays', 'saturdays', 'sundays', 'holidays')},
        }
    return out


def regional_lent(istat: pd.DataFrame, cal: pd.DataFrame, regions: list[str]) -> dict[str, dict]:
    """The Lent coefficient of each region's own monthly model, religious and civil (OLS only: the national
    model carries the randomisation test; here the regions are compared with each other)."""
    out = {}
    for code in regions:
        row = {}
        for rite in ('REL', 'CIVIL'):
            d = model_frame(istat[(istat.area == code) & (istat.rite == rite)], cal)
            b, _, se = fit(d)
            row[RITES[rite]] = {'coef': round(float(b['lent_share']), 4), 'ols_se': round(float(se['lent_share']), 4)}
        out[code] = row
    return out


def per_day(istat: pd.DataFrame, area: str, rite: str) -> pd.DataFrame:
    """year × month table of marriages per day, as a share of the year's daily rate (1 = an average day)."""
    t = istat[(istat.area == area) & (istat.rite == rite) & istat.year.isin(MODEL_YEARS)]
    m = t[t.month > 0].pivot(index='year', columns='month', values='marriages')
    days = pd.DataFrame({mo: [cal_mod.monthrange(y, mo)[1] for y in m.index] for mo in range(1, 13)}, index=m.index)
    year = t[t.month == 0].set_index('year').marriages
    ydays = pd.Series([366 if cal_mod.isleap(y) else 365 for y in m.index], index=m.index)
    return (m / days).div(year / ydays, axis=0)


def season_profiles(istat: pd.DataFrame) -> dict:
    """Mean per-day index of each month (1 = the year's average day), by area and rite."""
    out = {}
    for area in ['IT', *MACRO]:
        out[area] = {RITES[r]: [round(float(v), 3) for v in per_day(istat, area, r).mean().values] for r in ('REL', 'CIVIL')}
    return out


def neighbour_test(istat: pd.DataFrame, area: str = 'IT') -> list[dict]:
    """For each month: log(its per-day rate) − the mean log rate of the two neighbouring months, per year,
    religious and civil; then religious minus civil. A month the Church side avoids beyond what the season
    does to all weddings shows a negative difference. The neighbours of January and December wrap within the
    year. Mean ± its standard error over the model years."""
    lr = {r: np.log(per_day(istat, area, r).clip(lower=1e-6)) for r in ('REL', 'CIVIL')}
    out = []
    for m in range(1, 13):
        prev, nxt = (m - 2) % 12 + 1, m % 12 + 1
        c = {r: lr[r][m] - (lr[r][prev] + lr[r][nxt]) / 2 for r in lr}
        diff = c['REL'] - c['CIVIL']
        n = len(diff)
        out.append({'month': m,
                    'religious': round(float(c['REL'].mean()), 4), 'civil': round(float(c['CIVIL'].mean()), 4),
                    'difference': round(float(diff.mean()), 4),
                    'difference_se': round(float(diff.std(ddof=1) / np.sqrt(n)), 4),
                    'years_below_zero': int((diff < 0).sum()), 'years': int(n)})
    return out


def may_clean(istat: pd.DataFrame) -> dict:
    """May against its neighbours (religious minus civil, as in ``neighbour_test``) only in the model years
    when no day of April is in Lent: in the other years Lent empties April, the neighbour mean drops and May
    looks higher than it is (the all-years difference correlates with April's Lent days, r ≈ 0.8)."""
    years = [y for y in MODEL_YEARS if not any(d in lent_days(easter(y)) for d in month_days(y, 4))]
    lr = {r: np.log(per_day(istat, 'IT', r).loc[years]) for r in ('REL', 'CIVIL')}
    c = {r: lr[r][5] - (lr[r][4] + lr[r][6]) / 2 for r in lr}
    diff = c['REL'] - c['CIVIL']
    return {'years': years, 'difference': round(float(diff.mean()), 4),
            'difference_se': round(float(diff.std(ddof=1) / np.sqrt(len(diff))), 4),
            'pct': round(100 * (float(np.exp(diff.mean())) - 1), 1)}


def november_vs_average(istat: pd.DataFrame) -> dict:
    """November's per-day rate against the year's average day, religious divided by civil, per year: the
    November gap without January–February as the base. January–February church weddings fell much faster
    than the rest of the year (3.3 % of the year in 2004, 0.75 % in 2024), so the gap against them shrinks
    while November itself stays as empty as it was."""
    p = {r: per_day(istat, 'IT', r) for r in ('REL', 'CIVIL')}
    ratio = p['REL'][11] / p['CIVIL'][11]
    jf = (p['REL'][1] + p['REL'][2]) / 2
    return {'by_year': {int(y): round(float(v), 4) for y, v in ratio.items()},
            'religious_november_index': {int(y): round(float(v), 4) for y, v in p['REL'][11].items()},
            'religious_jan_feb_index': {int(y): round(float(v), 4) for y, v in jf.items()}}


def november_gap(istat: pd.DataFrame, areas: list[str]) -> dict:
    """Religious weddings per day in November against January–February, divided by the same ratio for civil
    weddings: the November gap of the Church side, with winter weather and the year's level taken out by
    the civil control. Per year for Italy; for each area on the model years pooled (a small region can have
    a November without a single church wedding, and a yearly log ratio would be infinite)."""
    def gap(area):
        p = {r: per_day(istat, area, r) for r in ('REL', 'CIVIL')}
        g = {r: np.log(p[r][11] / ((p[r][1] + p[r][2]) / 2)) for r in p}
        return g['REL'] - g['CIVIL']

    def pooled(area):
        t = istat[(istat.area == area) & istat.year.isin(MODEL_YEARS)]
        days = {m: sum(cal_mod.monthrange(y, m)[1] for y in MODEL_YEARS) for m in (1, 2, 11)}
        g = {}
        for r in ('REL', 'CIVIL'):
            n = t[t.rite == r].groupby('month').marriages.sum()
            g[r] = np.log((n[11] / days[11]) / ((n[1] + n[2]) / (days[1] + days[2])))
        return float(g['REL'] - g['CIVIL'])
    it = gap('IT')
    return {'italy_by_year': {int(y): round(float(v), 4) for y, v in it.items()},
            'italy_mean_log': round(float(it.mean()), 4),
            'italy_pct': round(100 * float(np.exp(it.mean()) - 1), 1),
            'italy_years_below_zero': int((it < 0).sum()),
            'by_area': {a: round(pooled(a), 4) for a in areas}}


def easter_april(istat: pd.DataFrame) -> list[dict]:
    """Share of the year's religious and civil weddings celebrated in March and April, with the date of
    Easter: the raw picture behind the Lent term."""
    rows = []
    for y in MODEL_YEARS:
        e = easter(y)
        r = {}
        for rite in ('REL', 'CIVIL'):
            t = istat[(istat.area == 'IT') & (istat.rite == rite) & (istat.year == y)].set_index('month').marriages
            r[RITES[rite]] = {'march_pct': round(100 * float(t[3] / t[0]), 3), 'april_pct': round(100 * float(t[4] / t[0]), 3)}
        rows.append({'year': y, 'easter': e.isoformat(), 'easter_doy': (e - dt.date(y, 1, 1)).days,
                     'lent_days_april': int(sum(d in lent_days(e) for d in month_days(y, 4))), **r})
    return rows


def slope_test(x: np.ndarray, y: np.ndarray, rng: np.random.Generator) -> dict:
    """Least-squares slope of y on x over units (equal weight), tested by shuffling x between units."""
    b = float(np.polyfit(x, y, 1)[0])
    perm = np.array([np.polyfit(rng.permutation(x), y, 1)[0] for _ in range(PERMUTATIONS)])
    return {'slope': round(b, 6), 'correlation': round(float(np.corrcoef(x, y)[0, 1]), 3),
            'p_value': round(float((np.sum(np.abs(perm) >= abs(b)) + 1) / (len(perm) + 1)), 4)}


def compute():
    names = territories()
    istat = read_istat()
    levels = area_levels(names, set(istat.area))
    units, unit_meta = stable_units(istat, names, levels)
    eu = pd.Series(eurostat_series()).sort_index()
    eu = eu[(eu.index >= FIRST_YEAR_EU) & (eu.index <= LAST_YEAR_EU)]
    cal = calendar(range(FIRST_YEAR_ISTAT, LAST_YEAR_ISTAT + 1))
    istat.to_csv(DATA / 'istat_month_rite_long.csv', index=False)
    units.to_csv(DATA / 'stable_units.csv', index=False)
    eu.rename('marriages').rename_axis('year').to_csv(DATA / 'eurostat_annual.csv')
    nat = national_annual(eu, istat)
    nat.to_csv(DATA / 'national_annual.csv', index=False)
    cal.to_csv(DATA / 'calendar.csv', index=False)
    (DATA / 'territories.json').write_text(json.dumps({'names': names, 'levels': levels, 'units': unit_meta},
                                                      ensure_ascii=False, indent=1))
    rng = np.random.default_rng(SEED + 1)

    # leap years: national (Eurostat 1960–2024; ISTAT by rite 2004–2024) and by stable unit
    nr = cycle_ratios(nat.set_index('year').marriages)
    by_rite = {}
    for rite in RITES:
        s = istat[(istat.area == 'IT') & (istat.rite == rite) & (istat.month == 0)].set_index('year').marriages
        by_rite[RITES[rite]] = cycle_ratios(s)
    unit_rows = []
    for u, meta in unit_meta.items():
        g = units[units.unit == u]
        allr = g[(g.rite == 'ALL') & (g.month == 0)].set_index('year').marriages
        rel = g[(g.rite == 'REL') & (g.month == 0)].set_index('year').marriages
        cr = cycle_ratios(allr)
        base = [y for y in range(FIRST_YEAR_ISTAT, 2020)]
        unit_rows.append({'code': u, 'name': meta['name'], 'region': meta['region'],
                          'religious_share_pct': round(100 * float(rel[base].sum() / allr[base].sum()), 1),
                          'leap_log': float(cr[cr.phase == 0].log_ratio.mean()),
                          'pre_leap_log': float(cr[cr.phase == 3].log_ratio.mean()),
                          'leap_years': int((cr.phase == 0).sum()),
                          'leap_below_zero': bool(cr[cr.phase == 0].log_ratio.mean() < 0),
                          'marriages_2024': int(allr[LAST_YEAR_ISTAT])})
    ut = pd.DataFrame(unit_rows).sort_values('code').reset_index(drop=True)
    ut.to_csv(DATA / 'unit_summary.csv', index=False)
    leap_slope = slope_test(ut.religious_share_pct.to_numpy(float), ut.leap_log.to_numpy(float), rng)

    # months
    models = monthly_models(istat, cal)
    reg_lent = regional_lent(istat, cal, levels['regions'])
    reg_rows = []
    for code in levels['regions']:
        t = istat[(istat.area == code) & (istat.month == 0) & istat.year.between(FIRST_YEAR_ISTAT, 2019)]
        share = t[t.rite == 'REL'].marriages.sum() / t[t.rite == 'ALL'].marriages.sum()
        reg_rows.append({'code': code, 'name': names[code][0], 'religious_share_pct': round(100 * float(share), 1),
                         'lent_religious_coef': reg_lent[code]['religious']['coef'],
                         'lent_religious_se': reg_lent[code]['religious']['ols_se'],
                         'lent_civil_coef': reg_lent[code]['civil']['coef']})
    rt = pd.DataFrame(reg_rows)
    nov = november_gap(istat, ['IT', *MACRO, *levels['regions']])
    rt['november_gap_log'] = rt.code.map(nov['by_area'])
    nov_rel = istat[(istat.rite == 'REL') & (istat.month == 11) & istat.year.isin(MODEL_YEARS)]
    rt['november_religious_marriages'] = rt.code.map(nov_rel.groupby('area').marriages.sum()).astype(int)
    rt.to_csv(DATA / 'region_summary.csv', index=False)
    lent_slope = slope_test(rt.religious_share_pct.to_numpy(float), rt.lent_religious_coef.to_numpy(float), rng)
    nov_slope = slope_test(rt.religious_share_pct.to_numpy(float), rt.november_gap_log.to_numpy(float), rng)

    pct = lambda v: round(100 * (float(np.exp(v)) - 1), 1)  # noqa: E731
    est = {
        'national_leap': {int(p): {'mean_log_ratio': round(float(g.log_ratio.mean()), 4),
                                   'years': [int(y) for y in g.year], 'below_zero': int((g.log_ratio < 0).sum())}
                          for p, g in nr.groupby('phase')},
        'national_cycle': [[int(r.year), int(r.phase), round(float(r.log_ratio), 4)] for r in nr.itertuples()],
        'istat_leap_by_rite': {k: {int(p): round(float(g.log_ratio.mean()), 4) for p, g in v.groupby('phase')}
                               for k, v in by_rite.items()},
        'istat_cycle_by_rite': {k: [[int(r.year), int(r.phase), round(float(r.log_ratio), 4)] for r in v.itertuples()]
                                for k, v in by_rite.items()},
        'unit_leap': {'units': int(len(ut)), 'median_leap_pct': pct(ut.leap_log.median()),
                      'median_pre_leap_pct': pct(ut.pre_leap_log.median()),
                      'share_below_zero': round(float((ut.leap_log < 0).mean()), 3),
                      'by_religious_share': leap_slope},
        'monthly_model': models,
        'regional_lent': {'by_religious_share': lent_slope},
        'season_profiles': season_profiles(istat),
        'neighbour_test': neighbour_test(istat),
        'may_clean': may_clean(istat),
        'november_vs_average': november_vs_average(istat),
        'november_gap': {**{k: v for k, v in nov.items() if k != 'by_area'},
                         'macro': {MACRO[a]: pct(nov['by_area'][a]) for a in MACRO},
                         'by_religious_share': nov_slope},
        'easter_april': easter_april(istat),
        'weekday_reports': WEEKDAY_REPORTS,
    }
    (DATA / 'estimates.json').write_text(json.dumps(est, ensure_ascii=False, indent=1))

    log(f'ISTAT {istat.year.min()}–{istat.year.max()}, {istat.area.nunique()} areas; units {len(ut)}; '
        f'national {nat.year.min()}–{nat.year.max()}, {nat.marriages.sum():,} marriages')
    for p, v in est['national_leap'].items():
        log(f'  national, phase {p}{" (leap)" if p == 0 else ""}: {pct(v["mean_log_ratio"]):+.1f} % '
            f'({len(v["years"])} years, {v["below_zero"]} below the average)')
    for k, v in est['istat_leap_by_rite'].items():
        log(f'  ISTAT {k:9s} by phase: ' + ', '.join(f'{p}: {pct(x):+.1f} %' for p, x in v.items()))
    u = est['unit_leap']
    log(f'  units: leap median {u["median_leap_pct"]:+.1f} %, year before {u["median_pre_leap_pct"]:+.1f} %, below zero in '
        f'{100 * u["share_below_zero"]:.0f} % of {u["units"]}; slope on religious share {leap_slope}')
    for rite in ('religious', 'civil'):
        m = models[rite]
        log(f'  monthly model, {rite}: {m["months"]} months, residual sd {m["residual_sd"]}')
        for k in ('lent_share', 'venus_share', 'mars_share'):
            log(f'    {k:12s} {m[k]["pct"]:+6.1f} % (p = {m[k]["p_value"]}, visible from '
                f'{m[k]["mde_pct_up"]:+.1f} / {m[k]["mde_pct_down"]:+.1f} %)')
        for k, t in m['other_terms'].items():
            log(f'    {k:12s} {t["pct"]:+6.1f} % per day of the kind (OLS se {t["ols_se"]})')
    log(f'  regional Lent vs religious share: {lent_slope}')
    for row in est['neighbour_test']:
        log(f'  neighbours, month {row["month"]:2d}: religious {row["religious"]:+.3f}, civil {row["civil"]:+.3f}, '
            f'difference {row["difference"]:+.3f} ± {row["difference_se"]:.3f} ({row["years_below_zero"]}/{row["years"]} below)')
    log(f'  November gap: Italy {est["november_gap"]["italy_pct"]:+.1f} %, {est["november_gap"]["macro"]}, '
        f'slope on religious share {nov_slope}')


# ------------------------------------------------------------------ validation
def validate():
    """Cross-checks; any failure stops ``export``. Results -> $IT_MARRIAGES_DATA/validation.json."""
    istat = pd.read_csv(DATA / 'istat_month_rite_long.csv', dtype={'area': str})
    eu = pd.read_csv(DATA / 'eurostat_annual.csv').set_index('year').marriages
    terr = json.loads((DATA / 'territories.json').read_text())
    names, levels = terr['names'], terr['levels']
    units = pd.read_csv(DATA / 'stable_units.csv', dtype={'unit': str})
    problems, checks = [], {}

    # 1. twelve months add up to the year, for every area and rite
    m = istat[istat.month > 0].groupby(['area', 'rite', 'year']).agg(total=('marriages', 'sum'), n=('month', 'size'))
    y = istat[istat.month == 0].set_index(['area', 'rite', 'year']).marriages
    j = m.join(y.rename('year_total'), how='outer')
    bad = j[(j.n != 12) | (j.total != j.year_total)]
    checks['months_vs_year_mismatches'] = int(len(bad))
    problems += [f'{a} {r} {yr}: {row.n} months sum to {row.total}, year {row.year_total}' for (a, r, yr), row in bad.head(20).iterrows()]

    # 2. religious + civil = all
    p = istat.pivot_table(index=['area', 'year', 'month'], columns='rite', values='marriages')
    bad = p[(p.REL + p.CIVIL) != p.ALL]
    checks['rites_vs_all_mismatches'] = int(len(bad))
    problems += [f'{a} {yr}-{mo:02d}: religious + civil {r.REL + r.CIVIL}, all {r.ALL}' for (a, yr, mo), r in bad.head(20).iterrows()]

    # 3. regions add up to Italy; provinces to their region (Sardinia's 2005–2016 provinces are missing)
    tot = istat[(istat.rite == 'ALL')].set_index(['area', 'year', 'month']).marriages
    reg = istat[istat.area.isin(levels['regions']) & (istat.rite == 'ALL')].groupby(['year', 'month']).marriages.sum()
    it = tot.loc['IT']
    checks['regions_vs_italy_mismatches'] = int((reg != it.reindex(reg.index)).sum())
    problems += [f'regions sum to {reg[k]}, Italy {it[k]} in {k}' for k in reg.index[reg != it.reindex(reg.index)][:20]]
    prov = istat[istat.area.isin(levels['provinces']) & (istat.rite == 'ALL')].copy()
    prov['region'] = [a[:4] if not a.startswith('IT1') else names[a][1] for a in prov.area]
    ps = prov.groupby(['region', 'year', 'month']).marriages.sum()
    rs = tot.reindex(ps.index)
    off = ps[ps != rs]
    sardinia_gap = [k for k in off.index if k[0] == 'ITG2' and 2005 <= k[1] <= 2016]
    checks['provinces_vs_region_mismatches'] = int(len(off) - len(sardinia_gap))
    checks['sardinia_years_with_missing_provinces'] = sorted({int(k[1]) for k in sardinia_gap})
    problems += [f'provinces of {k[0]} sum to {off[k]}, region {rs[k]} in {k[1]}-{k[2]:02d}'
                 for k in off.index if k not in sardinia_gap][:20]

    # 4. stable units add up to Italy
    us = units[units.rite == 'ALL'].groupby(['year', 'month']).marriages.sum()
    checks['units_vs_italy_mismatches'] = int((us != it.reindex(us.index)).sum())
    problems += [f'units sum to {us[k]}, Italy {it[k]} in {k}' for k in us.index[us != it.reindex(us.index)][:20]]

    # 5. every year of both series is there; ISTAT and Eurostat agree on the national total
    miss_eu = sorted(set(range(FIRST_YEAR_EU, LAST_YEAR_EU + 1)) - set(eu.index))
    miss_it = sorted(set(range(FIRST_YEAR_ISTAT, LAST_YEAR_ISTAT + 1)) - set(it.index.get_level_values(0)))
    checks['eurostat_missing_years'], checks['istat_missing_years'] = miss_eu, miss_it
    problems += [f'Eurostat: no {y_}' for y_ in miss_eu] + [f'ISTAT: no {y_}' for y_ in miss_it]
    both = sorted(set(eu.index) & set(it.index.get_level_values(0)))
    rel = {int(y_): float(abs(eu[y_] - it[(y_, 0)]) / it[(y_, 0)]) for y_ in both}
    checks['istat_vs_eurostat_max_rel'] = round(max(rel.values()), 5)
    differ = {y_: r for y_, r in rel.items() if eu[y_] != it[(y_, 0)]}
    checks['istat_vs_eurostat_years_differing'] = sorted(differ)
    problems += [f'{y_}: Eurostat {eu[y_]}, ISTAT {it[(y_, 0)]}' for y_ in differ if y_ not in KNOWN_DIFFERENCES]

    # 6. every unit has every year
    n = units[(units.rite == 'ALL') & (units.month == 0)].groupby('unit').year.nunique()
    short = n[n != LAST_YEAR_ISTAT - FIRST_YEAR_ISTAT + 1]
    checks['units'] = int(len(n))
    checks['units_with_missing_years'] = short.index.tolist()
    problems += [f'unit {u}: {k} years' for u, k in short.items()]

    (DATA / 'validation.json').write_text(json.dumps({'checks': checks, 'problems': problems}, ensure_ascii=False, indent=1))
    for k, v in checks.items():
        log(f'{k}: {v}')
    for p_ in problems:
        log('  PROBLEM', p_)
    log('validation ' + ('passed' if not problems else f'FAILED: {len(problems)} problems'))
    return not problems


# ------------------------------------------------------------------ export
def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed — run validate and resolve its problems first')
    istat = pd.read_csv(DATA / 'istat_month_rite_long.csv', dtype={'area': str})
    nat = pd.read_csv(DATA / 'national_annual.csv')
    eu_all = pd.read_csv(DATA / 'eurostat_annual.csv').set_index('year').marriages
    terr = json.loads((DATA / 'territories.json').read_text())
    names, levels = terr['names'], terr['levels']
    est = json.loads((DATA / 'estimates.json').read_text())
    ut = pd.read_csv(DATA / 'unit_summary.csv', dtype={'code': str})
    rt = pd.read_csv(DATA / 'region_summary.csv', dtype={'code': str})
    cal = pd.read_csv(DATA / 'calendar.csv')
    it = istat[istat.area == 'IT']
    nat_month = {RITES[r]: it[(it.rite == r) & (it.month > 0)][['year', 'month', 'marriages']].astype(int).values.tolist()
                 for r in ('REL', 'CIVIL')}
    nat_year = {RITES[r]: it[(it.rite == r) & (it.month == 0)][['year', 'marriages']].astype(int).values.tolist()
                for r in RITES}
    pct = lambda v: round(100 * (float(np.exp(v)) - 1), 1)  # noqa: E731
    out = {
        'generated_by': 'scripts/research/italy_marriages.py',
        'first_year': FIRST_YEAR_EU, 'last_year': LAST_YEAR_EU,
        'first_year_monthly': FIRST_YEAR_ISTAT, 'last_year_monthly': LAST_YEAR_ISTAT,
        'checker_years': list(CHECKER_YEARS),
        'total_marriages': int(nat[(nat.year >= FIRST_YEAR_EU) & (nat.year <= LAST_YEAR_EU)].marriages.sum()),
        'total_marriages_monthly': int(it[(it.rite == 'ALL') & (it.month == 0)].marriages.sum()),
        'national_annual': nat[['year', 'marriages']].astype(int).values.tolist(),
        # Venus and Mars retrograde periods for the page's date checker («Controlla la tua data»)
        'retrograde_upcoming': retrograde_upcoming(),
        # years where Eurostat prints another national total than ISTAT (ISTAT is used)
        'eurostat_differences': [{'year': int(y), 'eurostat': int(eu_all[y]), 'istat': int(n)}
                                 for y, n in nat.set_index('year').marriages.items()
                                 if y >= FIRST_YEAR_ISTAT and y in eu_all and eu_all[y] != n],
        'national_monthly': nat_month,
        'national_annual_by_rite': nat_year,
        'easter': {int(y): easter(int(y)).isoformat() for y in range(FIRST_YEAR_ISTAT, LAST_YEAR_ISTAT + 1)},
        'calendar_columns': ['year', 'month', 'days', 'lent_days', 'fridays', 'saturdays', 'sundays', 'holidays',
                             'venus_retro_days', 'mars_retro_days'],
        'calendar': cal[['year', 'month', 'days', 'lent_days', 'fridays', 'saturdays', 'sundays', 'holidays',
                         'venus_retro_days', 'mars_retro_days']].astype(int).values.tolist(),
        'macro_areas': MACRO,
        'regions': [{'code': r.code, 'name': r.name, 'religious_share_pct': float(r.religious_share_pct),
                     'lent_religious_pct': pct(r.lent_religious_coef), 'lent_civil_pct': pct(r.lent_civil_coef),
                     'november_gap_pct': pct(r.november_gap_log),
                     'november_religious_marriages': int(r.november_religious_marriages)}
                    for r in rt.sort_values('code').itertuples()],
        'units': [{'code': r.code, 'name': r.name, 'region': r.region, 'religious_share_pct': float(r.religious_share_pct),
                   'leap_pct': pct(r.leap_log), 'pre_leap_pct': pct(r.pre_leap_log), 'leap_years': int(r.leap_years),
                   'leap_below_zero': bool(r.leap_below_zero),
                   'marriages_2024': int(r.marriages_2024)} for r in ut.itertuples()],
        'estimates': est,
        'validation': val['checks'],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')

    # dataset: ISTAT's own rows (Italy, regions, provinces as published; religious and civil, months and
    # year) and the national series of all marriages (Eurostat to 2003, ISTAT from 2004)
    keep = ['IT', *levels['regions'], *levels['provinces']]
    level = {'IT': 'country'} | {a: 'region' for a in levels['regions']} | {a: 'province' for a in levels['provinces']}
    ds = istat[istat.area.isin(keep) & istat.rite.isin(['REL', 'CIVIL'])].copy()
    ds = ds.assign(level=ds.area.map(level), name=ds.area.map(lambda a: names[a][0]),
                   period=ds.month.map(lambda m: 'Y' if m == 0 else f'M{m:02d}'),
                   rite=ds.rite.map(RITES), source='ISTAT 24_186_DF_DCIS_MATRDEMO_7').rename(columns={'area': 'code'})
    e = nat.assign(level='country', code='IT', name='Italia', period='Y', rite='all')
    ds = pd.concat([e, ds], ignore_index=True).sort_values(['level', 'code', 'rite', 'year', 'period'])
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    ds[['level', 'code', 'name', 'year', 'period', 'rite', 'marriages', 'source']].to_csv(CSV_OUT, index=False, lineterminator='\n')
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=['fetch', 'compute', 'validate', 'export'])
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    if a.step == 'fetch':
        fetch()
    if a.step == 'compute':
        compute()
    if a.step == 'validate':
        return 0 if validate() else 1
    if a.step == 'export':
        export()
    return 0


if __name__ == '__main__':
    sys.exit(main())
