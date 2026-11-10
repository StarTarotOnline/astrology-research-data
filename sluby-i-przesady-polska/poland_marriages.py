#!/usr/bin/env python3
"""Polish wedding superstitions against the marriage registers of GUS (2002–2025, every day).

Source of the numbers on https://startarot.online/pl/research/sluby-i-przesady-polska

Needs Python 3.10+ and
    pip install numpy pandas xlrd openpyxl
The raw files (about 5 MB) go to $PL_MARRIAGES_DATA (default: ./poland-marriages-data next to this
script). Steps, in order:

    python3 poland_marriages.py fetch      # GUS Baza Demografia, Statistics Lithuania, CZSO, Eurostat
    python3 poland_marriages.py compute    # days, Saturdays, months, hypotheses, controls
    python3 poland_marriages.py validate   # sums against Eurostat and between GUS tables
    python3 poland_marriages.py export     # page JSON + dataset CSV (+ a copy of this script)

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/poland-marriages.json   data the page renders
    frontend/static/research/poland-marriages.csv     the open dataset (Poland by day, 2002–2025)
    frontend/static/research/poland_marriages.py      a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

Sources
-------
* GUS, Baza Demografia (demografia.stat.gov.pl), table 30 "Małżeństwa według dnia i miesiąca zawarcia
  związku małżeńskiego" (all, civil, religious with civil effect), 2002–2025, and table 14 (month ×
  voivodeship, by voivodeship of residence; urban and rural). Marriages where at least one spouse lived
  in Poland. Every church wedding with civil effect (since the 1998 concordat law) counts on the day of
  the ceremony.
* Eurostat demo_nind (MARRIAGE): annual totals of Poland from 1960, for the leap-year test and as a check.
* Statistics Lithuania, indicator S3R845 (marriages by month, 2001–) and CZSO, Demografická příručka 2024
  table 4.11 plus open data OBY01CRQM (marriages by month, 1950–): the controls. Lithuania is Catholic with
  the same climate and holidays and no "R" rule (July is "liepa"); in Czech every summer month has an r
  (červen, červenec, srpen).

Hypotheses, fixed before the daily data were opened
---------------------------------------------------
Written down and committed (28.10.2026) after only the national monthly totals of a few years had been
seen — the July dip and the May slump among them, which is why both are tested against controls, not
taken as found. The page prints every hypothesis with its result.

H1  "Ślub majowy, grób gotowy": weddings per Saturday in May are lower than the mean per Saturday of
    June and September, in every year; and the May ratio of Poland is lower than that of Czechia
    (monthly counts per Saturday in both).
H2  July, the summer month without an "r": weddings per Saturday in July are lower than the mean of June
    and August in every year; among civil weddings too; and Poland's July ratio is lower than that of
    Lithuania and of Czechia.
H3  The rule over the whole year: no prediction — the page shows for each pair of neighbouring months
    whether the month with an "r" has more weddings per Saturday, and says where another reason (Lent,
    Advent, All Saints, the summer) is the likelier one.
H4  Friday the 13th: fewer weddings than on the other Fridays of the same month.
H5  "Beautiful dates" (day = month = last two digits of the year, 02.02.02 … 12.12.12, and 20.02.2020,
    22.02.2022): more weddings than on the same weekday in the same month.
H6  A leap year: fewer weddings than the centred 2×4 moving average of the neighbouring years
    (Eurostat, 1960–2024; 2020–2021 left out).
H7  Ostatki: more weddings on the last Saturday before Ash Wednesday than on the other Saturdays of
    January and February outside Lent.
H8  Lent and Advent: weddings per Saturday fall in both; among religious weddings more than among civil.

Added after the count, not pre-registered (the page says so)
------------------------------------------------------------
* The 13th on every weekday and four placebo days (6th, 12th, 14th, 20th): an independent check found
  Saturday the 13th as empty as Friday the 13th — the number is avoided, not the Friday.
* Steps at month boundaries: consecutive Saturdays a week apart, inside a month against across the 1st.
* H6 drops 2019–2022, not only 2020–2021 as written: the centred 2×4 average of 2019 and 2022 reaches
  into the pandemic years.
* Voivodeships: the religious share of weddings against the May and July ratios (an ecological
  correlation over 16 regions — it says nothing about who keeps the superstition).
* A negative control for the steps (`steps_control`): the same step on the boundaries where the letter
  does not change. Jump on the 1st over the week-to-week change inside the earlier month; July's two
  boundaries against the two largest such steps without a letter change (April→May left out: the
  1 and 3 May holidays, the first communions and the end of Lent all fall on it).
* Trends (`trends`): the July ratio in the same three periods as the 13th (2002–2009, 2010–2017,
  2018–2025, pandemic years out).
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'poland-marriages'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'poland_marriages.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('PL_MARRIAGES_DATA', HERE / 'poland-marriages-data'))
RAW = DATA / 'raw'

FIRST_YEAR, LAST_YEAR = 2002, 2025
BD = 'https://demografia.stat.gov.pl/bazademografia/Downloader.aspx?file=pl_mal_{y}_00_{t}.zip&sys=mal'
LT_URL = 'https://osp-rs.stat.gov.lt/ords/ipospp/ospp/rest_json/data/S3R845_M3010102_1'
CZ_URL = ('https://csu.gov.cz/docs/107508/c35988fd-861d-516e-f59d-f7a97ab27969/130055250411.xlsx'
          '?version=1.0')
CZ_OPEN = 'https://data.csu.gov.cz/opendata/sady/OBY01CRQM/distribuce/csv'
EUROSTAT = ('https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_nind'
            '?format=JSON&lang=EN&geo=PL&geo=LT&geo=CZ&indic_de=MARRIAGE')


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def curl(url: str, dest: Path, tries: int = 6) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    for attempt in range(tries):
        r = subprocess.run(['curl', '-sSfL', '--retry', '3', '-A', 'Mozilla/5.0 startarot-research',
                            '-o', str(tmp), url])
        if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 0:
            tmp.rename(dest)
            log(f'  {dest.relative_to(RAW)}: {dest.stat().st_size} bytes')
            return
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f'download failed: {url}')


def fetch():
    """Every file once; manifest.json records the SHA-256 of what was fetched (GUS republishes the
    yearly tables when it revises them, so a pinned hash would only record the day of the download)."""
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        for t in ('30', '14'):
            curl(BD.format(y=y, t=t), RAW / 'gus' / f'pl_mal_{y}_00_{t}.zip')
    curl(LT_URL, RAW / 'lt' / 'S3R845_M3010102_1.json')
    curl(CZ_URL, RAW / 'cz' / '130055250411.xlsx')
    curl(CZ_OPEN, RAW / 'cz' / 'OBY01CRQM.csv')
    curl(EUROSTAT, RAW / 'eurostat' / 'demo_nind.json')
    manifest = {str(p.relative_to(RAW)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in sorted(RAW.rglob('*')) if p.is_file() and not p.name.endswith('.part')}
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=1))


# ------------------------------------------------------------------ readers
MONTHS_PL = ['styczeń', 'luty', 'marzec', 'kwiecień', 'maj', 'czerwiec', 'lipiec', 'sierpień', 'wrzesień',
             'październik', 'listopad', 'grudzień']
# Months whose Polish name has an "r": marzec, czerwiec, sierpień, wrzesień, październik, grudzień.
R_MONTHS = [m for m, name in enumerate(MONTHS_PL, start=1) if 'r' in name]


def _norm(v) -> str:
    import unicodedata
    return unicodedata.normalize('NFC', str(v)).strip()


def _num(v):
    t = _norm(v).replace(' ', '').replace('\xa0', '')
    if t in ('-', '–'):
        return 0
    if t in ('', 'nan'):
        return None
    return int(round(float(t)))


def _excel(zip_path: Path):
    """The one .xls(x) inside a GUS zip, as a pandas ExcelFile."""
    import pandas as pd
    with zipfile.ZipFile(zip_path) as z:
        name = next(n for n in z.namelist() if n.lower().endswith(('.xls', '.xlsx')))
        data = z.read(name)
    import io
    return pd.ExcelFile(io.BytesIO(data))


def _month_columns(df):
    for r in range(4, 14):
        row = [_norm(v).lower() for v in df.iloc[r]]
        if 'styczeń' in row:
            return r, {m + 1: row.index(MONTHS_PL[m]) for m in range(12)}
    raise ValueError('month header not found')


def read_daily():
    """Table 30: marriages per calendar day, all / civil / religious, 2002–2025."""
    import pandas as pd
    rows = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        x = _excel(RAW / 'gus' / f'pl_mal_{y}_00_30.zip')
        for sheet in x.sheet_names:
            kind = {'ogółem': 'total', 'cywilne': 'civil', 'wyznaniowe': 'religious'}[_norm(sheet).lower()]
            df = x.parse(sheet, header=None)
            assert int(float(_norm(df.iat[1, 1]))) == y, (y, sheet)
            hr, mc = _month_columns(df)
            for r in range(hr + 1, len(df)):
                lab = _norm(df.iat[r, 0])
                if not lab.replace('.0', '').isdigit():
                    continue
                d = int(float(lab))
                for m in range(1, 13):
                    v = _num(df.iat[r, mc[m]])
                    try:
                        day = date(y, m, d)
                    except ValueError:
                        assert not v, (y, m, d, v)
                        continue
                    rows.append((day, kind, v or 0))
    t = pd.DataFrame(rows, columns=['date', 'kind', 'n']).pivot_table(index='date', columns='kind', values='n',
                                                                         aggfunc='sum').fillna(0).astype(int)
    t.index = pd.to_datetime(t.index)
    return t[['total', 'civil', 'religious']]


def read_voivodeships(section: str = 'all'):
    """Table 14, part II (voivodeship of residence before the wedding): year, month, voivodeship,
    marriages — all of them, or ('religious') the block "w tym małżeństwa wyznaniowe" below."""
    rows = []
    for y in range(FIRST_YEAR, LAST_YEAR + 1):
        x = _excel(RAW / 'gus' / f'pl_mal_{y}_00_14.zip')
        sheet = next(s for s in x.sheet_names if 'II' in s and 'ogółem' in _norm(s).lower())
        df = x.parse(sheet, header=None)
        hr, mc = _month_columns(df)
        inside = section == 'all'
        for r in range(hr + 1, len(df)):
            row = ' '.join(_norm(v) for v in df.iloc[r] if _norm(v) != 'nan').lower()
            if 'wyznaniow' in row:
                if section == 'all':
                    break
                inside = True
                continue
            if not inside:
                continue
            lab = _norm(df.iat[r, 0])
            if lab == 'nan' or lab.upper() == 'POLSKA' or 'granic' in lab.lower() or '=' in lab:
                continue
            vals = [_num(df.iat[r, mc[m]]) for m in range(1, 13)]
            if any(v is None for v in vals):
                continue
            rows += [(y, m, lab.strip().capitalize(), vals[m - 1]) for m in range(1, 13)]
    return rows


def read_lithuania():
    d = json.loads((RAW / 'lt' / 'S3R845_M3010102_1.json').read_text())
    vals = d['structure']['dimensions']['observation'][1]['values']
    out = {}
    for k, o in d['dataSets'][0]['observations'].items():
        per = vals[int(k.split(':')[2])]['id']
        out[(int(per[:4]), int(per[5:]))] = int(o[0])
    return out


def read_czechia():
    import pandas as pd
    t = pd.read_excel(RAW / 'cz' / '130055250411.xlsx', header=None)
    out = {}
    for i in range(5, len(t)):
        try:
            y = int(float(t.iat[i, 0]))
        except (TypeError, ValueError):
            continue
        mv = [int(t.iat[i, c]) for c in range(2, 14)]
        assert sum(mv) == int(t.iat[i, 1]), y
        for m in range(12):
            out[(y, m + 1)] = mv[m]
    return out


def read_eurostat():
    import itertools
    d = json.loads((RAW / 'eurostat' / 'demo_nind.json').read_text())
    dims = d['id']
    cats = [sorted(d['dimension'][k]['category']['index'].items(), key=lambda x: x[1]) for k in dims]
    out = {}
    for idx, combo in enumerate(itertools.product(*cats)):
        v = d['value'].get(str(idx))
        rec = dict(zip(dims, [c[0] for c in combo]))
        if v is not None and rec.get('indic_de') == 'MARRIAGE':
            out[(rec['geo'], int(rec['time']))] = int(v)
    return out


# ------------------------------------------------------------------ calendar
def easter(y: int) -> date:
    """Gregorian Easter Sunday (anonymous Gregorian computus)."""
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(y, month, day)


def holidays(y: int) -> set:
    """Public holidays of Poland (the ones that fall on a fixed day or follow Easter)."""
    e = easter(y)
    days = {date(y, 1, 1), date(y, 5, 1), date(y, 5, 3), date(y, 8, 15), date(y, 11, 1), date(y, 11, 11),
            date(y, 12, 25), date(y, 12, 26), e, e + timedelta(1), e + timedelta(49), e + timedelta(60)}
    if y >= 2011:
        days.add(date(y, 1, 6))
    if y >= 2025:
        days.add(date(y, 12, 24))
    return days


def lent(y: int) -> tuple[date, date]:
    """Ash Wednesday to Holy Saturday."""
    e = easter(y)
    return e - timedelta(46), e - timedelta(1)


def advent(y: int) -> tuple[date, date]:
    """First Sunday of Advent to 24 December."""
    xmas = date(y, 12, 25)
    first = xmas - timedelta(days=(xmas.weekday() + 1) % 7 or 7) - timedelta(weeks=3)
    return first, date(y, 12, 24)


def saturdays(y: int, m: int) -> int:
    d = date(y, m, 1)
    n = 0
    while d.month == m:
        n += d.weekday() == 5
        d += timedelta(1)
    return n


def beautiful_dates() -> list[date]:
    out = [date(2000 + k, k, k) for k in range(2, 13)]
    return out + [date(2020, 2, 20), date(2022, 2, 22)]


# ------------------------------------------------------------------ compute
PERMUTATIONS = 10000


def compute():
    import numpy as np
    import pandas as pd
    rng = np.random.default_rng(20261028)
    daily = read_daily()
    res = {'first_year': FIRST_YEAR, 'last_year': LAST_YEAR, 'r_months': R_MONTHS, 'months_pl': MONTHS_PL}
    res['total'] = int(daily.total.sum())
    res['by_year'] = {int(y): {k: int(v) for k, v in g.sum().items()} for y, g in daily.groupby(daily.index.year)}
    wd = daily.groupby(daily.index.weekday).total.sum()
    res['weekday_share'] = [float(wd.get(i, 0) / daily.total.sum()) for i in range(7)]
    sat = daily[daily.index.weekday == 5]

    # weddings per Saturday, by year and month and kind
    def per_saturday(kind):
        g = sat.groupby([sat.index.year, sat.index.month])[kind].agg(['sum', 'count'])
        return {(int(y), int(m)): float(r['sum'] / r['count']) for (y, m), r in g.iterrows()}
    ps = {k: per_saturday(k) for k in ('total', 'civil', 'religious')}
    res['per_saturday'] = {k: [[round(v[(y, m)], 2) for m in range(1, 13)] for y in range(FIRST_YEAR, LAST_YEAR + 1)]
                           for k, v in ps.items()}
    # the same for the controls, from monthly counts (every wedding in the month over its Saturdays):
    # Poland computed this way too, so the three are measured alike
    lt, cz = read_lithuania(), read_czechia()
    month_pl = daily.groupby([daily.index.year, daily.index.month]).total.sum()
    approx = {'PL': {(int(y), int(m)): float(v) / saturdays(y, m) for (y, m), v in month_pl.items()},
              'LT': {k: v / saturdays(*k) for k, v in lt.items()},
              'CZ': {k: v / saturdays(*k) for k, v in cz.items()}}
    ctrl_years = range(FIRST_YEAR, 2025)   # Czech 2025 is preliminary; the comparison stops at 2024

    def ratio_series(table, m, refs, years):
        out = {}
        for y in years:
            if all((y, k) in table for k in [m] + refs):
                out[y] = table[(y, m)] / np.mean([table[(y, k)] for k in refs])
        return out

    def summary(series, exclude=(2020, 2021)):
        vals = np.array([v for y, v in series.items() if y not in exclude])
        logs = np.log(vals)
        return {'mean_ratio': float(np.exp(logs.mean())), 'min': float(vals.min()), 'max': float(vals.max()),
                'below_one': int((vals < 1).sum()), 'years': int(len(vals)),
                'by_year': {int(y): round(float(v), 4) for y, v in series.items()}}
    years = range(FIRST_YEAR, LAST_YEAR + 1)
    h = {}
    # H1 May against June and September; H2 July against June and August
    for key, m, refs in (('may', 5, [6, 9]), ('july', 7, [6, 8])):
        block = {kind: summary(ratio_series(ps[kind], m, refs, years)) for kind in ('total', 'civil', 'religious')}
        block['controls'] = {c: summary(ratio_series(approx[c], m, refs, ctrl_years)) for c in ('PL', 'LT', 'CZ')}
        h[key] = block
    # H3 the rule over the year: neighbouring months, one with an "r" and one without
    pairs = []
    for m in range(1, 13):
        n = m % 12 + 1
        if (m in R_MONTHS) != (n in R_MONTHS):
            rm, other = (m, n) if m in R_MONTHS else (n, m)
            wins = sum(1 for y in years if ps['total'][(y, rm)] > ps['total'][(y, other)])
            pairs.append({'months': [m, n], 'r_month': rm, 'r_wins': wins, 'years': len(years),
                          'ratio': float(np.exp(np.mean([math.log(ps['total'][(y, rm)] / ps['total'][(y, other)])
                                                         for y in years])))})
    h['pairs'] = pairs
    # H4 Friday the 13th against the other Fridays of the same month (holidays left out)
    def same_weekday(day, kind='total', clean=False):
        """The other days of the month on the same weekday, without public holidays; ``clean`` also
        leaves out Lent and the ostatki Saturday (for single dates near Ash Wednesday)."""
        hol = holidays(day.year)
        a, b = lent(day.year)
        ost_day = a - timedelta(days=4)
        d0 = date(day.year, day.month, 1)
        others = [d0 + timedelta(i) for i in range(31)]
        others = [d for d in others if d.month == day.month and d.weekday() == day.weekday() and d != day
                  and d not in hol and not (clean and (a <= d <= b or d == ost_day))]
        return [int(daily.at[pd.Timestamp(d), kind]) for d in others]
    f13 = []
    for y in years:
        for m in range(1, 13):
            d = date(y, m, 13)
            if d.weekday() == 4 and d not in holidays(y):
                ref = same_weekday(d)
                f13.append({'date': d.isoformat(), 'n': int(daily.at[pd.Timestamp(d), 'total']),
                            'ref_mean': float(np.mean(ref))})
    obs, exp = sum(x['n'] for x in f13), sum(x['ref_mean'] for x in f13)
    # null: a random other Friday of the month stands in for the 13th
    null = []
    fr = {}
    for x in f13:
        d = date.fromisoformat(x['date'])
        fr[x['date']] = same_weekday(d)
    for _ in range(PERMUTATIONS):
        tot = 0.0
        for x in f13:
            ref = fr[x['date']]
            k = int(rng.integers(len(ref)))
            pick = ref[k]
            rest = [r for i, r in enumerate(ref) if i != k] + [x['n']]
            tot += pick / np.mean(rest)
        null.append(tot / len(f13))
    real = float(np.mean([x['n'] / x['ref_mean'] for x in f13]))
    h['friday13'] = {'dates': f13, 'ratio': obs / exp, 'mean_ratio': real,
                     'below': int(sum(x['n'] < x['ref_mean'] for x in f13)),
                     'p_lower': float(np.mean(np.array(null) <= real))}
    # H5 beautiful dates against the same weekday of the month
    bd = []
    for d in beautiful_dates():
        if FIRST_YEAR <= d.year <= LAST_YEAR:
            # without Lent and ostatki where the month has such days left; else every same weekday
            ref = same_weekday(d, clean=True)
            ref_clean = bool(ref)
            ref = ref or same_weekday(d)
            a, b = lent(d.year)
            bd.append({'date': d.isoformat(), 'weekday': d.weekday(), 'holiday': d in holidays(d.year),
                       'lent': a <= d <= b, 'ostatki_week': a - timedelta(days=7) <= d < a, 'ref_clean': ref_clean,
                       'n': int(daily.at[pd.Timestamp(d), 'total']), 'ref_mean': float(np.mean(ref)),
                       'ref_max': int(max(ref))})
    h['beautiful'] = bd
    # The 13th on any weekday, against the other days of the month with that weekday (holidays out):
    # Friday was the hypothesis, the other weekdays say whether it is Friday or the number.
    thirteenth = {}
    for wd in range(7):
        rows = []
        for y in years:
            for m in range(1, 13):
                d = date(y, m, 13)
                if d.weekday() == wd and d not in holidays(y):
                    ref = same_weekday(d)
                    if ref and np.mean(ref) > 0:
                        rows.append((y, int(daily.at[pd.Timestamp(d), 'total']), float(np.mean(ref))))
        if rows:
            thirteenth[wd] = {'n': len(rows), 'ratio': sum(r[1] for r in rows) / sum(r[2] for r in rows),
                              'below': sum(r[1] < r[2] for r in rows)}
    # placebo days: the 12th and the 14th on Fridays and Saturdays
    placebo = {}
    for dd in (6, 12, 14, 20):
        o = e = 0.0
        for y in years:
            for m in range(1, 13):
                d = date(y, m, dd)
                if d.weekday() in (4, 5) and d not in holidays(y):
                    ref = same_weekday(d)
                    o += daily.at[pd.Timestamp(d), 'total']
                    e += float(np.mean(ref))
        placebo[dd] = o / e
    periods = {}
    for p0, p1 in ((2002, 2009), (2010, 2017), (2018, 2025)):
        o = e = 0.0
        for y in range(p0, p1 + 1):
            for m in range(1, 13):
                d = date(y, m, 13)
                if d.weekday() in (4, 5) and d not in holidays(y):
                    o += daily.at[pd.Timestamp(d), 'total']
                    e += float(np.mean(same_weekday(d)))
        periods[f'{p0}-{p1}'] = o / e
    h['thirteenth'] = {'by_weekday': thirteenth, 'placebo_fri_sat': placebo, 'fri_sat_by_period': periods}
    # Steps at month boundaries: consecutive Saturdays one week apart, inside a month against across the
    # boundary. Holidays, seasons and summer change smoothly; a jump on the 1st belongs to the month.
    steps_in, steps_across = {}, {}
    sat_days = [d.date() for d in sat.index if d.year not in (2020, 2021)]
    sat_set = set(sat_days)
    for d in sat_days:
        nxt = d + timedelta(7)
        if nxt not in sat_set or d in holidays(d.year) or nxt in holidays(nxt.year):
            continue
        a_, b_ = daily.at[pd.Timestamp(d), 'total'], daily.at[pd.Timestamp(nxt), 'total']
        if a_ <= 0 or b_ <= 0:
            continue
        lr = math.log(b_ / a_)
        if nxt.month == d.month:
            steps_in.setdefault(d.month, []).append(lr)
        else:
            steps_across.setdefault(d.month, []).append(lr)
    h['steps'] = {'within': {m: float(math.exp(np.mean(v))) for m, v in sorted(steps_in.items())},
                  'across': {m: float(math.exp(np.mean(v))) for m, v in sorted(steps_across.items())},
                  'n_across': {m: len(v) for m, v in sorted(steps_across.items())}}
    # Added after the count (not pre-registered): the negative control for the steps. A boundary steps
    # for many reasons (holidays, school year, harvest); only the excess over the July boundaries of
    # what boundaries WITHOUT a letter change do can be laid at the letter's door.
    st_in, st_across = h['steps']['within'], h['steps']['across']
    excess = {m: st_across[m] / st_in[m] for m in st_across if m in st_in}
    letter_change = [m for m in excess if (m in R_MONTHS) != ((m % 12 + 1) in R_MONTHS)]
    quiet = sorted((m for m in excess if m not in letter_change and m != 4),
                   key=lambda m: -abs(math.log(excess[m])))[:2]
    size = {m: abs(math.log(v)) for m, v in excess.items()}
    h['steps_control'] = {'excess': excess, 'letter_change': letter_change, 'quiet_largest': quiet,
                          'july_vs_quiet': float(np.mean([size[6], size[7]]) / np.mean([size[m] for m in quiet]))}
    # Added after the count: is the July dip fading? The same periods as the 13th, pandemic years out.
    jy = h['july']['total']['by_year']
    h['trends'] = {'july_by_period': {
        f'{p0}-{p1}': float(np.exp(np.mean([math.log(jy[y]) for y in range(p0, p1 + 1) if y not in (2020, 2021)])))
        for p0, p1 in ((2002, 2009), (2010, 2017), (2018, 2025))}}
    # H6 leap years, Eurostat annual totals, centred 2×4 moving average
    eu = read_eurostat()
    leap = {}
    for geo in ('PL', 'LT', 'CZ'):
        ys = sorted(y for g, y in eu if g == geo)
        s = pd.Series({y: eu[(geo, y)] for y in ys}, dtype=float)
        ma = s.rolling(4, center=True).mean().rolling(2).mean().shift(-1)
        dev = np.log(s / ma).dropna()
        dev = dev[~dev.index.isin([2019, 2020, 2021, 2022])]
        is_leap = np.array([y % 4 == 0 for y in dev.index])
        real = float(dev[is_leap].mean() - dev[~is_leap].mean())
        # null: the leap phase moved to one of the other three years of the cycle
        phases = [float(dev[np.array([(y - k) % 4 == 0 for y in dev.index])].mean()
                        - dev[~np.array([(y - k) % 4 == 0 for y in dev.index])].mean()) for k in range(4)]
        se = float(math.sqrt(dev[is_leap].var(ddof=1) / is_leap.sum() + dev[~is_leap].var(ddof=1) / (~is_leap).sum()))
        leap[geo] = {'effect_pct': 100 * (math.exp(real) - 1), 'years': [int(dev.index.min()), int(dev.index.max())],
                     'ci95_pct': [100 * (math.exp(real - 1.96 * se) - 1), 100 * (math.exp(real + 1.96 * se) - 1)],
                     'dropped': [2019, 2020, 2021, 2022],
                     'leap_years': int(is_leap.sum()), 'below_trend': int((dev[is_leap] < 0).sum()),
                     'phases_pct': [100 * (math.exp(p) - 1) for p in phases],
                     'by_year': {int(y): round(float(100 * (math.exp(v) - 1)), 2) for y, v in dev.items()}}
    h['leap'] = leap
    # H7 ostatki: the last Saturday before Ash Wednesday against the other Saturdays of Jan–Feb before Lent
    ost = []
    for y in years:
        ash = lent(y)[0]
        last = ash - timedelta(days=4)
        hol = holidays(y)
        ref = [d for d in (date(y, 1, 1) + timedelta(i) for i in range(70))
               if d.weekday() == 5 and d < last and d not in hol and d.month <= 2]
        if not ref:
            continue
        ost.append({'year': y, 'date': last.isoformat(), 'n': int(daily.at[pd.Timestamp(last), 'total']),
                    'ref_mean': float(np.mean([daily.at[pd.Timestamp(d), 'total'] for d in ref]))})
    h['ostatki'] = {'rows': ost, 'ratio': float(np.exp(np.mean([math.log(x['n'] / x['ref_mean']) for x in ost]))),
                    'above': int(sum(x['n'] > x['ref_mean'] for x in ost))}
    # H8 Lent and Advent: Saturdays inside against Saturdays of the same months outside, by kind
    def season(kind, inside):
        ins, out = [], []
        for d, row in sat.iterrows():
            dd = d.date()
            if dd in holidays(dd.year):
                continue
            if inside(dd) is None:
                continue
            (ins if inside(dd) else out).append(row[kind])
        return float(np.mean(ins) / np.mean(out)), len(ins), len(out)
    def in_lent(d):
        a, b = lent(d.year)
        if d.month not in (2, 3, 4):
            return None
        return a <= d <= b
    def in_advent(d):
        a, b = advent(d.year)
        if d.month not in (11, 12):
            return None
        return a <= d <= b
    h['seasons'] = {name: {kind: dict(zip(('ratio', 'inside', 'outside'), season(kind, fn)))
                           for kind in ('total', 'civil', 'religious')}
                    for name, fn in (('lent', in_lent), ('advent', in_advent))}
    # Easter shift: April weddings per Saturday in years with an early Easter against a late one
    h['easter'] = [{'year': y, 'easter': easter(y).isoformat(), 'april': round(ps['total'][(y, 4)], 2),
                    'march': round(ps['total'][(y, 3)], 2)} for y in years]
    # Every 13th and every Friday, for the reader's date checker: none needed — the page reads by_day
    res['hypotheses'] = h
    # voivodeships: May and July ratios (monthly counts over Saturdays), all years together
    vv = read_voivodeships()
    rel = {}
    for y, m, v, n in read_voivodeships('religious'):
        rel[v] = rel.get(v, 0) + n
    by = {}
    for y, m, v, n in vv:
        by.setdefault(v, {})[(y, m)] = n / saturdays(y, m)
    reg = []
    for v, tab in sorted(by.items()):
        ys = [y for y in years if y not in (2020, 2021)]
        def pooled(m, refs):
            return float(np.exp(np.mean([math.log(tab[(y, m)] / np.mean([tab[(y, k)] for k in refs])) for y in ys])))
        total_v = int(round(sum(n * saturdays(y, m) for (y, m), n in tab.items())))
        reg.append({'name': v, 'may': pooled(5, [6, 9]), 'july': pooled(7, [6, 8]),
                    'marriages': total_v, 'religious_share': rel.get(v, 0) / total_v})
    res['voivodeships'] = reg
    rs = np.array([r['religious_share'] for r in reg])
    res['voivodeship_corr'] = {k: float(np.corrcoef(rs, [r[k] for r in reg])[0, 1]) for k in ('may', 'july')}
    # the year of weddings, day by day: mean per calendar day over all years (for the page's strip)
    md = daily.groupby([daily.index.month, daily.index.day]).total.mean()
    res['calendar_mean'] = [[round(float(md.get((m, d), 0)), 1) for d in range(1, 32)] for m in range(1, 13)]
    res['lithuania_years'] = [min(y for y, _ in lt), max(y for y, _ in lt)]
    res['czechia_years'] = [min(y for y, _ in cz), max(y for y, _ in cz)]
    res['eurostat_pl'] = {int(y): eu[('PL', y)] for (g, y) in eu if g == 'PL'}
    daily.to_csv(DATA / 'daily.csv')
    (DATA / 'computed.json').write_text(json.dumps(res, ensure_ascii=False, default=float))
    log('computed.json written')


# ------------------------------------------------------------------ validate
def validate() -> bool:
    import pandas as pd
    r = json.loads((DATA / 'computed.json').read_text())
    daily = pd.read_csv(DATA / 'daily.csv', index_col=0, parse_dates=True)
    problems, notes = [], []
    if (daily.civil + daily.religious != daily.total).any():
        problems.append('civil + religious differs from the total on some days')
    eu = read_eurostat()
    for y, g in daily.groupby(daily.index.year):
        if ('PL', y) in eu and int(g.total.sum()) != eu[('PL', y)]:
            problems.append(f'{y}: GUS days sum to {int(g.total.sum())}, Eurostat has {eu[("PL", y)]}')
        if ('PL', y) not in eu:
            notes.append(f'{y}: no Eurostat total yet (GUS {int(g.total.sum())})')
    # the voivodeship table (residence) adds up to the national table, month by month
    vv = read_voivodeships()
    tab = {}
    for y, m, _, n in vv:
        tab[(y, m)] = tab.get((y, m), 0) + n
    month = daily.groupby([daily.index.year, daily.index.month]).total.sum()
    off = [(y, m) for (y, m), n in month.items() if abs(tab.get((y, m), 0) - n) > 0.01 * n]
    if off:
        problems.append(f'voivodeships do not add up in {len(off)} months, e.g. {off[:3]}')
    if len(r['voivodeships']) != 16:
        problems.append(f"{len(r['voivodeships'])} voivodeships instead of 16")
    # the calendar arithmetic
    if easter(2024) != date(2024, 3, 31) or easter(2025) != date(2025, 4, 20) or lent(2025)[0] != date(2025, 3, 5):
        problems.append('Easter or Ash Wednesday wrong')
    if advent(2025)[0] != date(2025, 11, 30) or advent(2024)[0] != date(2024, 12, 1):
        problems.append('Advent wrong')
    if R_MONTHS != [3, 6, 8, 9, 10, 12]:
        problems.append(f'months with an r: {R_MONTHS}')
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
    import pandas as pd
    val = json.loads((DATA / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed — run validate and resolve its problems first')
    r = json.loads((DATA / 'computed.json').read_text())
    r['generated_by'] = 'scripts/research/poland_marriages.py'
    JSON_OUT.write_text(json.dumps(_round(r), ensure_ascii=False, separators=(',', ':')) + '\n')
    daily = pd.read_csv(DATA / 'daily.csv', index_col=0, parse_dates=True)
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['date', 'weekday', 'marriages', 'civil', 'religious', 'public_holiday', 'lent', 'advent'])
        for d, row in daily.iterrows():
            dd = d.date()
            a, b = lent(dd.year)
            c, e = advent(dd.year)
            w.writerow([dd.isoformat(), dd.strftime('%A'), int(row.total), int(row.civil), int(row.religious),
                        int(dd in holidays(dd.year)), int(a <= dd <= b), int(c <= dd <= e)])
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')


if __name__ == '__main__':
    steps = {'fetch': fetch, 'compute': compute, 'validate': validate, 'export': export}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    ok = steps[sys.argv[1]]()
    sys.exit(1 if ok is False else 0)
