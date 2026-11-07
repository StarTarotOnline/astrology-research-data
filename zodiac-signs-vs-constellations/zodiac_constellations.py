#!/usr/bin/env python3
"""Zodiac signs against the constellations: where the Sun really was for 309 million births.

Source of the numbers on https://startarot.online/research/zodiac-signs-vs-constellations

Needs Python 3.10+ and
    pip install numpy pandas pyarrow pyswisseph astropy openpyxl
and the daily birth series of zodiac_sign_frequency.py (startarot.online/research/rarest-zodiac-sign):
put that script next to this one and run its fetch step first (fetch-france, fetch-ew, fetch-us,
fetch-br, fetch-jp are enough); $ZODIAC_DATA must point at the same folder for both scripts.
Intermediate files go to $CONSTELLATION_DATA (default: ./zodiac-constellation-data next to this
script). Steps, in order:

    python3 zodiac_constellations.py compute    # sky tables + births by sign x constellation
    python3 zodiac_constellations.py validate   # internal checks and sensitivity of every date we print
    python3 zodiac_constellations.py export     # page JSON + dataset CSV (+ a copy of this script in the repo)

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/zodiac-constellations.json     data the page renders
    frontend/static/research/zodiac-constellations.csv       the open dataset (long format)
    frontend/static/research/zodiac_constellations.py        a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

Three ways to name the Sun's place at a birth
---------------------------------------------
TROPICAL SIGN — the sign of Western astrology: the ecliptic cut into twelve 30° arcs counted from the
March equinox (true equinox of date). It follows the seasons, not the stars.
SIDEREAL SIGN — twelve 30° arcs fixed to the stars (Lahiri ayanamsa), the sign of Indian astrology.
CONSTELLATION — the IAU constellation that contains the Sun's position: the 88 regions of
Delporte (1930), whose edges are arcs of right ascension and declination of the equinox B1875.0
(Roman 1987, CDS catalogue VI/42, as shipped with astropy). Along the ecliptic the Sun crosses
thirteen of them: the twelve zodiac constellations and Ophiuchus. It does not touch Cetus in the
years counted here (``validate`` checks this every run).

The Sun's position is Swiss Ephemeris (built-in Moshier ephemeris), apparent (light time and
aberration included), referred to the MEAN equator and equinox of date and then precessed to B1875
by astropy (IAU 2006 precession); nutation is left out because the boundaries are drawn on a mean
frame. ``validate`` repeats every printed date with nutation included, with the geometric instead
of the apparent position, and with a second precession route (IAU 1976 angles by hand), and prints how far each
date moves.

The minutes of a last window depend on that convention, and the page prints both. The boundaries
are catalogue lines drawn on the mean places of the stars, which aberration does not shift; the
apparent Sun (aberration about -20.5" along the ecliptic) therefore enters every constellation about
eight minutes later than the geometric Sun measured against the same lines, and each last window is
that much longer by the geometric Sun (Capricorn's: 12 minutes apparent, 21 geometric; the years do
not move). ``validate`` keeps the geometric windows and counts the births inside both windows of
every sign whose last overlap falls inside the birth data; ``export`` prints them next to the
apparent ones (``last_true[].geometric``, ``last_window_births``). The apparent Sun stays the model
of every other number: it is the Sun of astrology and of the almanacs.

What is counted
---------------
1. The sky, 1900–2100: the instants the Sun enters each tropical sign, sidereal sign and
   constellation (to about a second; the boundaries themselves are exact lines, the error is the
   ephemeris and the model, see ``validate``).
2. The sky over the centuries, 2001 BC to AD 2990 (the limit of the Moshier ephemeris) (astronomical years, so year 0 = 1 BC): the
   share of the year in which the tropical sign and the constellation agree, and for each sign the
   last moment at which a person could be born with the Sun both in the tropical sign and in the
   constellation of the same name. The edges move along the ecliptic by precession (about 1.4° a
   century), so every such overlap shrinks at the END of the tropical sign and then closes for
   good; the page prints when. The constellation boundaries are a 1930 convention: for the
   distant past they answer "where would today's official boundaries put the Sun", not what any
   ancient astronomer drew. Far in the past and after about 2500 the uncertainty of ΔT (the
   Earth's clock) moves the instant by hours, never by a year.
3. Births: the daily series of zodiac_sign_frequency.py — metropolitan France 1968–2024 (INSEE),
   England and Wales 1995–2024 (ONS), the USA 1969–1988 and 1994–2014 (NCHS/CDC/SSA), Brazil
   1997–2024 (SINASC), Japan 2015–2024 (e-Stat): every birth of each local civil day is split by
   the share of that day the Sun spent in each (tropical sign, sidereal sign, constellation)
   combination, time uniform over the day (the clock zone per country is that of
   zodiac_sign_frequency.py). Brazil records the clock hour from 2006, and there the day is split
   by those hours. ``validate`` measures the error of the uniform-time assumption on Brazil's
   recorded hours: small for shares, but tens of percent for the births of one short window (the
   page gives those as "about"). Licences and limits of each source are in that script.

Nothing here says which zodiac is "right": the signs of astrology were never the constellations
(Ptolemy, 2nd century, defined them from the equinox). The page describes how far apart the two
are, for real people, and since when.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import os
import shutil
import sys
import warnings
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore', module='erfa')
warnings.filterwarnings('ignore', category=UserWarning, module='astropy')

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'zodiac-signs-vs-constellations'
FILE_STEM = 'zodiac-constellations'
SCRIPT_COPY = None
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'zodiac_constellations.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
DATA = Path(os.environ.get('CONSTELLATION_DATA') or HERE / 'zodiac-constellation-data')

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius',
         'Capricorn', 'Aquarius', 'Pisces']
# IAU abbreviation -> name used on the page; the order is the order along the ecliptic
CONSTELLATIONS = {'Ari': 'Aries', 'Tau': 'Taurus', 'Gem': 'Gemini', 'Cnc': 'Cancer', 'Leo': 'Leo',
                  'Vir': 'Virgo', 'Lib': 'Libra', 'Sco': 'Scorpius', 'Oph': 'Ophiuchus',
                  'Sgr': 'Sagittarius', 'Cap': 'Capricornus', 'Aqr': 'Aquarius', 'Psc': 'Pisces'}
CON_CODES = list(CONSTELLATIONS)
# the constellation that carries each sign's name
SIGN_CON = ['Ari', 'Tau', 'Gem', 'Cnc', 'Leo', 'Vir', 'Lib', 'Sco', 'Sgr', 'Cap', 'Aqr', 'Psc']
SKY_YEARS = (1900, 2100)
CENTURY_YEARS = (-2000, 2990)
CENTURY_STEP = 10
LAST_TRUE_RANGE = (-2900, 2999)

J1970 = 2440587.5
MINUTE = 1 / 1440


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ------------------------------------------------------------------ births (zodiac_sign_frequency.py)
_ZSF = None


def zsf():
    """The sibling script that fetches and reads the daily birth series."""
    global _ZSF
    if _ZSF is None:
        path = HERE / 'zodiac_sign_frequency.py'
        if not path.exists():
            sys.exit('zodiac_sign_frequency.py must sit next to this script (see the docstring)')
        spec = importlib.util.spec_from_file_location('zodiac_sign_frequency', path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules['zodiac_sign_frequency'] = mod
        spec.loader.exec_module(mod)
        _ZSF = mod
    return _ZSF


# ------------------------------------------------------------------ astronomy
_SWE = None


def swe():
    global _SWE
    if _SWE is None:
        import swisseph
        swisseph.set_sid_mode(swisseph.SIDM_LAHIRI)
        _SWE = swisseph
    return _SWE


# variants for the sensitivity test: (nutation included, apparent position, astropy frame route)
MODEL = {'nutation': False, 'apparent': True}


def sun_equatorial(jd_ut: np.ndarray, nutation: bool | None = None, apparent: bool | None = None):
    s = swe()
    nutation = MODEL['nutation'] if nutation is None else nutation
    apparent = MODEL['apparent'] if apparent is None else apparent
    flag = s.FLG_MOSEPH | s.FLG_EQUATORIAL
    if not nutation:
        flag |= s.FLG_NONUT
    if not apparent:
        flag |= s.FLG_TRUEPOS | s.FLG_NOABERR
    out = np.empty((len(jd_ut), 2))
    for i, j in enumerate(jd_ut):
        out[i] = s.calc_ut(float(j), s.SUN, flag)[0][:2]
    return out


def constellation(jd_ut, nutation: bool | None = None, apparent: bool | None = None) -> np.ndarray:
    """IAU constellation (abbreviation) holding the Sun at each instant (UT Julian days)."""
    import astropy.units as u
    from astropy.coordinates import PrecessedGeocentric, SkyCoord, get_constellation
    from astropy.time import Time

    jd_ut = np.atleast_1d(np.asarray(jd_ut, dtype=float))
    out = np.empty(len(jd_ut), dtype='<U3')
    s = swe()
    for a in range(0, len(jd_ut), 200_000):
        j = jd_ut[a:a + 200_000]
        rd = sun_equatorial(j, nutation, apparent)
        tt = Time(j + np.array([s.deltat(float(x)) for x in j]), format='jd', scale='tt')
        c = SkyCoord(rd[:, 0] * u.deg, rd[:, 1] * u.deg, frame=PrecessedGeocentric(equinox=tt, obstime=tt))
        out[a:a + 200_000] = np.asarray(get_constellation(c, short_name=True))
    return out


def tropical_lon(jd_ut: np.ndarray, sidereal: bool = False) -> np.ndarray:
    s = swe()
    flag = s.FLG_MOSEPH | (s.FLG_SIDEREAL if sidereal else 0)
    return np.array([s.calc_ut(float(j), s.SUN, flag)[0][0] for j in jd_ut])


def sign_ingresses(jd0: float, jd1: float, sidereal: bool) -> pd.DataFrame:
    s = swe()
    flag = s.FLG_MOSEPH | (s.FLG_SIDEREAL if sidereal else 0)
    k = int(s.calc_ut(jd0, s.SUN, flag)[0][0] // 30)
    rows, jd = [], jd0
    while True:
        k = (k + 1) % 12
        jd = s.solcross_ut(30.0 * k, jd, flag)
        if jd > jd1:
            break
        rows.append((jd, SIGNS[k]))
        jd += 1
    return pd.DataFrame(rows, columns=['jd', 'enters'])


def refine(lo: np.ndarray, hi: np.ndarray, before: np.ndarray, seconds: float = 1.0) -> np.ndarray:
    """Bisect each [lo, hi] until it is ``seconds`` wide: the instant the Sun leaves ``before``."""
    lo, hi = lo.copy(), hi.copy()
    while (hi - lo).max() * 86400 > seconds:
        mid = (lo + hi) / 2
        same = constellation(mid) == before
        lo = np.where(same, mid, lo)
        hi = np.where(same, hi, mid)
    return hi


def constellation_ingresses(jd0: float, jd1: float, step_hours: float = 2.0) -> pd.DataFrame:
    grid = np.arange(jd0, jd1, step_hours / 24)
    con = constellation(grid)
    ch = np.where(con[1:] != con[:-1])[0]
    jd = refine(grid[ch], grid[ch + 1], con[ch])
    df = pd.DataFrame({'jd': jd, 'leaves': con[ch], 'enters': con[ch + 1]})
    # no constellation is crossed in under two hours, so the grid cannot step over one
    if not (np.diff(df.jd) > 2 * step_hours / 24).all():
        raise RuntimeError('two constellation changes inside one grid step')
    return df


def year_jd(year: int) -> float:
    """0h UT on 1 January (proleptic Gregorian) of an astronomical year."""
    return swe().julday(year, 1, 1, 0.0, swe().GREG_CAL)


def utc_iso(jd: float) -> str:
    y, m, d, h = swe().revjul(jd, swe().GREG_CAL)
    hh = int(h)
    mm = int(round((h - hh) * 60))
    if mm == 60:
        hh, mm = hh + 1, 0
    return f'{y:05d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}Z' if y < 0 else f'{y:04d}-{m:02d}-{d:02d}T{hh:02d}:{mm:02d}Z'


# ------------------------------------------------------------------ compute: the sky
def compute_sky():
    jd0, jd1 = year_jd(SKY_YEARS[0] - 1) + 300, year_jd(SKY_YEARS[1] + 2) + 30
    log('constellation ingresses', SKY_YEARS)
    con = constellation_ingresses(jd0, jd1)
    seen = set(con.leaves) | set(con.enters)
    if seen != set(CON_CODES):
        raise RuntimeError(f'the Sun crossed {sorted(seen)} instead of the 13 ecliptic constellations')
    trop = sign_ingresses(jd0, jd1, False)
    sid = sign_ingresses(jd0, jd1, True)
    con[['jd', 'enters']].to_csv(DATA / 'ingress_constellation.csv', index=False)
    trop.to_csv(DATA / 'ingress_tropical.csv', index=False)
    sid.to_csv(DATA / 'ingress_sidereal.csv', index=False)


def centuries_curve(step_days: float = 0.1) -> pd.DataFrame:
    """Share of the tropical year in which the tropical sign and the constellation agree."""
    rows = []
    for year in range(CENTURY_YEARS[0], CENTURY_YEARS[1] + 1, CENTURY_STEP):
        jd = year_jd(year) + np.arange(0, 365.2422, step_days)
        k = (tropical_lon(jd) // 30).astype(int) % 12
        con = constellation(jd)
        trop_con = np.array(SIGN_CON)[k]
        rows.append({'year': year, 'agree': float((trop_con == con).mean()),
                     'ophiuchus_days': float((con == 'Oph').sum() * step_days),
                     'scorpius_days': float((con == 'Sco').sum() * step_days)})
        if year % 500 == 0:
            log('  centuries', year, round(rows[-1]['agree'], 3))
    return pd.DataFrame(rows)


def tropical_end(year: int, k: int) -> float:
    """Instant the Sun leaves tropical sign ``k`` in (or nearest) the given year."""
    s = swe()
    target = 30.0 * ((k + 1) % 12)
    jd = year_jd(year) + ((target - 280.0) % 360) / 0.9856  # 1 Jan ≈ 280°
    return s.solcross_ut(target, jd - 40, s.FLG_MOSEPH)


def last_true(k: int, **model) -> dict:
    """Last year in which tropical sign k overlaps its namesake constellation, and that overlap."""
    years = np.arange(*LAST_TRUE_RANGE)
    ends = np.array([tropical_end(int(y), k) for y in years])
    inside = constellation(ends - MINUTE, **model) == SIGN_CON[k]
    if not inside.any():
        return {'sign': SIGNS[k], 'last_year': None}
    i = int(np.where(inside)[0].max())
    if i == len(years) - 1:
        return {'sign': SIGNS[k], 'last_year': None, 'beyond': int(years[-1])}
    end = ends[i]
    # the overlap that year: from the Sun's entry into the constellation to the end of the sign
    lo, hi = np.array([end - 40.0]), np.array([end - MINUTE])
    grid = np.arange(lo[0], hi[0], 1 / 24)
    con = constellation(grid, **model)
    j = np.where(con != SIGN_CON[k])[0]
    entry = end - MINUTE
    if len(j):
        a = grid[j.max()]
        lo2 = np.array([a])
        hi2 = np.array([a + 1 / 24])
        # bisect for the entry instant (first moment inside)
        while (hi2 - lo2)[0] * 86400 > 1:
            mid = (lo2 + hi2) / 2
            ins = constellation(mid, **model) == SIGN_CON[k]
            hi2 = np.where(ins, mid, hi2)
            lo2 = np.where(ins, lo2, mid)
        entry = hi2[0]
    first_out = int(years[i + 1])
    return {'sign': SIGNS[k], 'constellation': CONSTELLATIONS[SIGN_CON[k]], 'last_year': int(years[i]),
            'first_year_without': first_out, 'overlap_from_utc': utc_iso(entry), 'overlap_to_utc': utc_iso(end),
            'overlap_minutes': round((end - entry) * 1440, 1), '_entry_jd': float(entry), '_end_jd': float(end)}


def public_row(r: dict) -> dict:
    """A last_true row without the working instants."""
    return {k: v for k, v in r.items() if not k.startswith('_')}


def compute_centuries():
    log('centuries curve', CENTURY_YEARS)
    centuries_curve().to_csv(DATA / 'centuries.csv', index=False)
    log('last overlaps')
    out = []
    for k in range(12):
        r = public_row(last_true(k))
        log('  ', r)
        out.append(r)
    (DATA / 'last_true.json').write_text(json.dumps(out, indent=1))


# ------------------------------------------------------------------ compute: births
def day_bounds_jd(dates: pd.DatetimeIndex, tz: str) -> tuple[np.ndarray, np.ndarray]:
    z = ZoneInfo(tz)
    days = list(dates) + [dates[-1] + pd.Timedelta(days=1)]
    jd = np.array([J1970 + dt.datetime(d.year, d.month, d.day, tzinfo=z).timestamp() / 86400 for d in days])
    return jd[:-1], jd[1:]


def load_ingresses():
    con = pd.read_csv(DATA / 'ingress_constellation.csv')
    trop = pd.read_csv(DATA / 'ingress_tropical.csv')
    sid = pd.read_csv(DATA / 'ingress_sidereal.csv')
    return trop, sid, con


def state_at(jd: np.ndarray, ing: pd.DataFrame) -> np.ndarray:
    i = np.searchsorted(ing.jd.values, jd, side='right') - 1
    if (i < 0).any():
        raise RuntimeError('instant before the first tabulated ingress')
    return ing.enters.values[i]


def day_combinations(dates: pd.DatetimeIndex, tz: str, hour_weights: np.ndarray | None = None):
    """For each local civil day: list of ((tropical, sidereal, constellation), share of the day's births)."""
    trop, sid, con = load_ingresses()
    start, end = day_bounds_jd(dates, tz)
    events = np.sort(np.concatenate([trop.jd.values, sid.jd.values, con.jd.values]))
    out = []
    for i in range(len(dates)):
        a, b = start[i], end[i]
        cuts = events[(events > a) & (events < b)]
        edges = np.concatenate([[a], cuts, [b]])
        mids = (edges[:-1] + edges[1:]) / 2
        frac = np.diff(edges) / (b - a)
        if hour_weights is not None and hour_weights[i].sum() > 0:
            w = hour_weights[i] / hour_weights[i].sum()
            cum = np.concatenate([[0], np.cumsum(w)])
            x = (edges - a) / (b - a) * 24
            h = np.minimum(x.astype(int), 23)
            c = cum[h] + w[h] * (x - h)
            c[-1] = 1.0
            frac = np.diff(c)
        keys = list(zip(state_at(mids, trop), state_at(mids, sid), state_at(mids, con)))
        out.append(list(zip(keys, frac)))
    return out


_DAILY = {}


def daily(z, key: str) -> pd.Series:
    if key not in _DAILY:
        _DAILY[key] = z.read_daily(key)
    return _DAILY[key]


def window_births(z, jd_from: float, jd_to: float) -> dict[str, float]:
    """Births of every daily series inside one UT window, by country: the same split as
    ``compute_births`` (time uniform over the local day, Brazil from 2006 by its recorded hours),
    for one window alone — the births of a last overlap under a given convention."""
    out = {}
    for key in z.DAILY:
        tz = z.DAILY_TZ[key]
        zone = ZoneInfo(tz)
        s = daily(z, key)
        first = dt.datetime.fromtimestamp((jd_from - J1970) * 86400, zone).date()
        last = dt.datetime.fromtimestamp((jd_to - J1970) * 86400, zone).date()
        days = pd.date_range(first, last)
        days = days[days.isin(s.index)]
        if not len(days):
            continue
        hours = None
        if key == 'BR':
            hp = z.br_hour_profile()
            hp = hp[hp.hour >= 0]
            hours = (hp.pivot_table(index='date', columns='hour', values='n', aggfunc='sum')
                     .reindex(index=days, columns=range(24)).fillna(0).values)
        start, end = day_bounds_jd(days, tz)
        n = 0.0
        for i, d in enumerate(days):
            a, b = start[i], end[i]
            lo, hi = max(a, jd_from), min(b, jd_to)
            if hi <= lo:
                continue
            if hours is not None and hours[i].sum() > 0:
                w = hours[i] / hours[i].sum()
                cum = np.concatenate([[0], np.cumsum(w)])

                def before(x):
                    x = (x - a) / (b - a) * 24
                    h = min(int(x), 23)
                    return cum[h] + w[h] * (x - h)

                frac = before(hi) - before(lo)
            else:
                frac = (hi - lo) / (b - a)
            n += float(s[d]) * frac
        country = SERIES_COUNTRY[key]
        out[country] = out.get(country, 0.0) + n
    return out


def compute_births():
    z = zsf()
    rows = []
    for key in z.DAILY:
        s = daily(z, key)
        log('births', key, len(s), int(s.sum()))
        hours = None
        if key == 'BR':
            # Brazil records the clock hour from 2006: the day is split by those hours, not uniformly
            # (the last overlap of Capricorn fell at 11:00 in Brasília, the peak of planned caesareans)
            hp = z.br_hour_profile()
            hp = hp[hp.hour >= 0]
            hours = (hp.pivot_table(index='date', columns='hour', values='n', aggfunc='sum')
                     .reindex(index=s.index, columns=range(24)).fillna(0).values)
        combos = day_combinations(s.index, z.DAILY_TZ[key], hours)
        acc = {}
        for d, n, parts in zip(s.index, s.values, combos):
            for (t, sd, c), f in parts:
                k = (d.year, t, sd, c)
                acc[k] = acc.get(k, 0.0) + n * f
        for (y, t, sd, c), v in acc.items():
            rows.append((key, y, t, sd, c, v))
    df = pd.DataFrame(rows, columns=['series', 'year', 'tropical', 'sidereal', 'constellation', 'births'])
    df.to_parquet(DATA / 'births.parquet', index=False)
    log('births total', int(df.births.sum()))


def compute():
    DATA.mkdir(parents=True, exist_ok=True)
    compute_sky()
    compute_births()
    compute_centuries()


# ------------------------------------------------------------------ validate
def validate():
    z = zsf()
    checks = {}
    trop, sid, con = load_ingresses()
    # 1. the sky: 13 constellations in fixed order, every year 1900–2100
    seq = list(con.enters)
    order = CON_CODES
    bad = [i for i in range(1, len(seq)) if order.index(seq[i]) != (order.index(seq[i - 1]) + 1) % 13]
    checks['constellation_order_breaks'] = len(bad)
    years = pd.Series([swe().revjul(j)[0] for j in con.jd])
    per_year = years[(years >= SKY_YEARS[0]) & (years <= SKY_YEARS[1])].value_counts()
    checks['constellation_ingresses_per_year'] = sorted(set(per_year.values.tolist()))
    # Cetus: the closest the Sun gets is checked by moving its declination toward Cetus' edge
    # (the ecliptic constellation sequence above already proves Cetus is never entered)
    # 2. the births table reproduces the tropical shares of zodiac_sign_frequency.py's daily rows
    b = pd.read_parquet(DATA / 'births.parquet')
    counts = pd.read_parquet(z.DATA / 'counts.parquet')
    daily_rows = counts[(counts.method == 'daily') & (counts.zodiac == 'tropical')]
    mine = b.assign(source=b.series.map(z.DAILY_SOURCE)).groupby(['source', 'year', 'tropical']).births.sum()
    theirs = daily_rows.groupby(['source', 'year', 'sign']).births.sum()
    theirs.index = theirs.index.set_names(['source', 'year', 'tropical'])
    joined = pd.concat([mine.rename('mine'), theirs.rename('theirs')], axis=1).dropna()
    rel = (joined.mine / joined.theirs - 1).abs()
    # Brazil is split by recorded hours here and uniformly there: report it apart, check the rest
    br = rel.index.get_level_values('source') == z.DAILY_SOURCE['BR']
    checks['tropical_vs_rarest_sign_max_rel'] = float(rel[~br].max())
    checks['tropical_vs_rarest_sign_rows'] = int((~br).sum())
    checks['brazil_hours_vs_uniform_max_rel'] = round(float(rel[br].max()), 4)
    # 3. uniform time within the day vs Brazil's recorded hours (2006–2024)
    hp = z.br_hour_profile()
    hp = hp[hp.hour >= 0]
    wide = hp.pivot_table(index='date', columns='hour', values='n', aggfunc='sum').reindex(columns=range(24)).fillna(0)
    dates = pd.DatetimeIndex(wide.index)
    with_hours = day_combinations(dates, z.DAILY_TZ['BR'], wide.values)
    uniform = day_combinations(dates, z.DAILY_TZ['BR'])
    tot = wide.values.sum(axis=1)

    def shares(parts_list):
        acc = {}
        for n, parts in zip(tot, parts_list):
            for (t, sd, c), f in parts:
                acc[c] = acc.get(c, 0.0) + n * f
        s = pd.Series(acc)
        return s / s.sum() * 100

    diff = (shares(with_hours) - shares(uniform)).abs()
    checks['within_day_max_pp_constellation'] = round(float(diff.max()), 4)
    # 4. sensitivity of the printed dates of the last overlaps
    base = {r['sign']: r for r in json.loads((DATA / 'last_true.json').read_text())}
    sens, geometric = {}, {}
    for name, model in (('nutation', {'nutation': True}), ('geometric', {'apparent': False})):
        moved = {}
        for k in range(12):
            r = last_true(k, **model)
            if base[SIGNS[k]]['last_year'] is not None and r['last_year'] is not None:
                moved[SIGNS[k]] = r['last_year'] - base[SIGNS[k]]['last_year']
            if name == 'geometric':
                geometric[SIGNS[k]] = r
        sens[name] = moved
        log('  sensitivity', name, moved)
    checks['last_year_shift'] = sens
    checks['last_year_max_abs_shift'] = max(abs(v) for m in sens.values() for v in m.values())
    # the page prints the length of every last window under both conventions: the geometric
    # Sun, against the same catalogue lines, enters a constellation about eight minutes earlier
    checks['geometric_windows'] = {s: {k: v for k, v in public_row(r).items() if k.startswith(('last_year', 'overlap'))}
                                   for s, r in geometric.items()}
    # 4b. births inside the last windows that fall within the birth data, counted straight from the
    #     daily series under both conventions: the apparent count must reproduce births.parquet
    #     (the page prints it), and the geometric count is what the page prints next to it
    b['true'] = b.tropical.map(dict(zip(SIGNS, SIGN_CON))) == b.constellation
    b['country'] = b.series.map(SERIES_COUNTRY)
    year0, year1 = int(b.year.min()), int(b.year.max())
    closing_windows, worst = {}, 0.0
    for k in range(12):
        y = base[SIGNS[k]]['last_year']
        if y is None or not year0 <= y <= year1:
            continue
        app = last_true(k)
        counted = window_births(z, app['_entry_jd'], app['_end_jd'])
        stored = b[(b.tropical == SIGNS[k]) & b.true & (b.year == y)].groupby('country').births.sum()
        for c in set(counted) | set(stored.index):
            worst = max(worst, abs(counted.get(c, 0.0) - float(stored.get(c, 0.0))))
        geo = geometric[SIGNS[k]]
        geo_counted = window_births(z, geo['_entry_jd'], geo['_end_jd']) if geo['last_year'] is not None else {}
        closing_windows[SIGNS[k]] = {
            'apparent': {'year': y, 'births': {c: round(v, 1) for c, v in sorted(counted.items())}},
            'geometric': {'year': geo['last_year'], 'births': {c: round(v, 1) for c, v in sorted(geo_counted.items())}},
        }
        log('  last window births', SIGNS[k], closing_windows[SIGNS[k]])
    checks['closing_windows'] = closing_windows
    checks['closing_window_vs_births_max_abs'] = round(worst, 3)
    # 5. a second route to the boundaries: precess with the IAU 1976 angles by hand instead of
    #    astropy's IAU 2006 transform and compare the constellation at 20,000 random instants near a boundary
    rng = np.random.default_rng(1)
    pick = rng.choice(len(con), size=min(400, len(con)), replace=False)
    near = np.concatenate([con.jd.values[pick] - 30 / 86400, con.jd.values[pick] + 30 / 86400])
    a = constellation(near)
    b2 = constellation_iau1976(near)
    checks['iau1976_route_disagreements_at_30s'] = int((a != b2).sum())
    ok = (checks['constellation_order_breaks'] == 0 and checks['constellation_ingresses_per_year'] in ([13], [13, 14])
          and checks.get('tropical_vs_rarest_sign_max_rel', 0) < 0.002
          and checks['within_day_max_pp_constellation'] < 0.05 and checks['last_year_max_abs_shift'] <= 1
          and checks['iau1976_route_disagreements_at_30s'] == 0 and checks['closing_window_vs_births_max_abs'] < 1
          and len(checks['closing_windows']) > 0)
    checks['ok'] = bool(ok)
    (DATA / 'validation.json').write_text(json.dumps(checks, indent=1))
    log(json.dumps(checks, indent=1))
    if not ok:
        sys.exit('validate: FAILED (see validation.json)')


def constellation_iau1976(jd_ut) -> np.ndarray:
    """Same lookup with a second precession route: the IAU 1976 angles (Lieske 1977) applied by hand
    from the mean equator of date straight to B1875, then astropy's boundary table only."""
    import astropy.units as u
    from astropy.coordinates import PrecessedGeocentric, SkyCoord, get_constellation
    from astropy.time import Time

    jd_ut = np.atleast_1d(np.asarray(jd_ut, dtype=float))
    rd = np.radians(sun_equatorial(jd_ut))
    s = swe()
    jd0 = jd_ut + np.array([s.deltat(float(x)) for x in jd_ut])
    b1875 = Time('B1875', scale='tt')
    T = (jd0 - 2451545.0) / 36525
    t = (b1875.jd - jd0) / 36525
    asec = np.pi / 180 / 3600
    zeta = ((2306.2181 + 1.39656 * T - 0.000139 * T**2) * t + (0.30188 - 0.000344 * T) * t**2 + 0.017998 * t**3) * asec
    z = ((2306.2181 + 1.39656 * T - 0.000139 * T**2) * t + (1.09468 + 0.000066 * T) * t**2 + 0.018203 * t**3) * asec
    th = ((2004.3109 - 0.85330 * T - 0.000217 * T**2) * t - (0.42665 + 0.000217 * T) * t**2 - 0.041833 * t**3) * asec
    ra, dec = rd[:, 0], rd[:, 1]
    A = np.cos(dec) * np.sin(ra + zeta)
    B = np.cos(th) * np.cos(dec) * np.cos(ra + zeta) - np.sin(th) * np.sin(dec)
    C = np.sin(th) * np.cos(dec) * np.cos(ra + zeta) + np.cos(th) * np.sin(dec)
    ra2 = (np.arctan2(A, B) + z) % (2 * np.pi)
    dec2 = np.arcsin(C)
    c = SkyCoord(ra2 * u.rad, dec2 * u.rad, frame=PrecessedGeocentric(equinox=b1875, obstime=b1875))
    return np.asarray(get_constellation(c, short_name=True))


# ------------------------------------------------------------------ export
SERIES_COUNTRY = {'FR': 'France', 'UK_EW': 'England and Wales', 'US_1969': 'USA', 'US': 'USA', 'BR': 'Brazil',
                  'JP': 'Japan'}
SERIES_SOURCE = {'FR': 'INSEE', 'UK_EW': 'ONS', 'US_1969': 'NCHS (BigQuery natality)',
                 'US': 'CDC/NCHS, SSA (FiveThirtyEight)', 'BR': 'SINASC', 'JP': 'e-Stat'}


def r3(x: float) -> float:
    return round(float(x), 3)


def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if not val.get('ok'):
        sys.exit('export: run validate first (it must pass)')
    b = pd.read_parquet(DATA / 'births.parquet')
    b['country'] = b.series.map(SERIES_COUNTRY)
    total = float(b.births.sum())

    def share(g):
        return (g / g.sum() * 100)

    con_share = share(b.groupby('constellation').births.sum()).reindex(CON_CODES)
    trop_share = share(b.groupby('tropical').births.sum()).reindex(SIGNS)
    sid_share = share(b.groupby('sidereal').births.sum()).reindex(SIGNS)
    by_country = {}
    for c, g in b.groupby('country'):
        by_country[c] = {'births': int(round(g.births.sum())),
                         'years': [int(g.year.min()), int(g.year.max())],
                         'constellation': [r3(v) for v in share(g.groupby('constellation').births.sum()).reindex(CON_CODES)]}
    # where each tropical sign goes
    m = b.groupby(['tropical', 'constellation']).births.sum().unstack(fill_value=0).reindex(index=SIGNS, columns=CON_CODES,
                                                                                         fill_value=0)
    flows = []
    for t in SIGNS:
        row = m.loc[t]
        for c in CON_CODES:
            if row[c] > 0:
                flows.append({'tropical': t, 'constellation': c, 'share_of_sign': r3(row[c] / row.sum() * 100),
                              'share_of_all': r3(row[c] / total * 100)})
    same_trop = float(b[b.tropical.map(dict(zip(SIGNS, SIGN_CON))) == b.constellation].births.sum() / total * 100)
    same_sid = float(b[b.sidereal.map(dict(zip(SIGNS, SIGN_CON))) == b.constellation].births.sum() / total * 100)
    same_both = float(b[(b.sidereal == b.tropical)].births.sum() / total * 100)
    # true signs by year (pooled over the countries that have the year)
    b['true'] = b.tropical.map(dict(zip(SIGNS, SIGN_CON))) == b.constellation
    yr = b.groupby('year').births.sum()
    true_by_year = b[b.true].groupby(['year', 'tropical']).births.sum().unstack(fill_value=0).reindex(columns=SIGNS,
                                                                                                    fill_value=0)
    true_rows = []
    for y in yr.index:
        row = true_by_year.loc[y] if y in true_by_year.index else pd.Series(0, index=SIGNS)
        true_rows.append({'year': int(y), 'births': int(round(yr[y])), 'true_share': r3(row.sum() / yr[y] * 100),
                          'true_births': {s: int(round(row[s])) for s in SIGNS if row[s] >= 0.5}})
    # "true" births of the sign whose overlap closed inside the data: per series and year
    last = json.loads((DATA / 'last_true.json').read_text())
    # the year moves by one under other conventions for some signs: print the range, not one year;
    # the minutes of the window depend on the convention always: print both (see the docstring)
    for r in last:
        shifts = [m.get(r['sign'], 0) for m in val['last_year_shift'].values()]
        r['year_range'] = [r['last_year'] + min(0, *shifts), r['last_year'] + max(0, *shifts)]
        r['geometric'] = val['geometric_windows'][r['sign']]
    window_births_rows = [{'sign': s, **w} for s, w in val['closing_windows'].items()]
    for row in window_births_rows:
        for conv in ('apparent', 'geometric'):
            row[conv]['births'] = {c: int(round(v)) for c, v in row[conv]['births'].items()}
    closing = []
    for r in last:
        y = r.get('last_year')
        if y is None:
            continue
        g = b[(b.tropical == r['sign']) & b.true & (b.year >= y - 30) & (b.year <= y)]
        if len(g):
            per = g.groupby(['country', 'year']).births.sum().reset_index()
            closing.append({'sign': r['sign'], 'rows': [{'country': c, 'year': int(yy), 'births': int(round(v))}
                                                        for c, yy, v in per.itertuples(index=False)]})
    # three names at once: tropical / sidereal / constellation
    triple = b.groupby(['tropical', 'sidereal', 'constellation']).births.sum()
    triple = (triple / total * 100).sort_values(ascending=False)
    triples = [{'tropical': t, 'sidereal': sd, 'constellation': c, 'share': round(float(v), 4)}
               for (t, sd, c), v in triple.items() if v >= 0.0005]
    # the sky for the calculator: ingress instants 1900–2100, minutes since 1900-01-01 00:00 UT
    trop, sid, con = load_ingresses()
    base = year_jd(1900)

    def table(ing, names):
        ing = ing[(ing.jd >= year_jd(SKY_YEARS[0]) - 40) & (ing.jd < year_jd(SKY_YEARS[1] + 1) + 40)]
        t = [int(round((j - base) * 1440)) for j in ing.jd]
        # first value absolute, then differences (minutes): a third of the size in the page bundle
        return {'t0': t[0], 'dt': np.diff(t).tolist(), 'k': [names.index(x) for x in ing.enters]}

    sky = {'epoch': '1900-01-01T00:00Z', 'tropical': table(trop, SIGNS), 'sidereal': table(sid, SIGNS),
           'constellation': table(con, CON_CODES)}
    # constellation days in a sample year and the entry dates of 2026 (for the page's table)
    def entries(year):
        g = con[(con.jd >= year_jd(year)) & (con.jd < year_jd(year + 1))]
        return [{'constellation': c, 'utc': utc_iso(j)} for j, c in zip(g.jd, g.enters)]
    span = con.copy()
    span['days'] = span.jd.shift(-1) - span.jd
    span['year'] = [swe().revjul(j)[0] for j in span.jd]
    days = span[(span.year >= 2000) & (span.year <= 2049)].groupby('enters').days.mean().reindex(CON_CODES)
    cent = pd.read_csv(DATA / 'centuries.csv')
    best = cent.loc[cent.agree.idxmax()]
    data = {
        'slug': SLUG,
        'births_total': int(round(total)),
        'countries': len(by_country),
        'series': [{'series': s, 'country': SERIES_COUNTRY[s], 'source': SERIES_SOURCE[s],
                    'years': [int(g.year.min()), int(g.year.max())], 'births': int(round(g.births.sum()))}
                   for s, g in b.groupby('series')],
        'constellations': [{'code': c, 'name': CONSTELLATIONS[c], 'share': r3(con_share[c]),
                            'days_2000_2049': round(float(days[c]), 2)} for c in CON_CODES],
        'tropical': [{'sign': s, 'share': r3(trop_share[s])} for s in SIGNS],
        'sidereal': [{'sign': s, 'share': r3(sid_share[s])} for s in SIGNS],
        'by_country': by_country,
        'flows': flows,
        'same': {'tropical_equals_constellation': r3(same_trop), 'sidereal_equals_constellation': r3(same_sid),
                 'tropical_equals_sidereal': r3(same_both)},
        'true_by_year': true_rows,
        'closing': closing,
        'last_true': last,
        'last_window_births': window_births_rows,
        'centuries': {'step': CENTURY_STEP, 'years': cent.year.tolist(), 'agree': [r3(v * 100) for v in cent.agree],
                      'ophiuchus_days': [round(float(v), 1) for v in cent.ophiuchus_days],
                      'best_year': int(best.year), 'best_agree': r3(best.agree * 100)},
        'entries_2026': entries(2026),
        'triples': triples,
        'sky': sky,
        'validation': {k: v for k, v in val.items() if k not in ('ok', 'geometric_windows', 'closing_windows')},
    }
    JSON_OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    csv = b.groupby(['country', 'series', 'year', 'tropical', 'sidereal', 'constellation']).births.sum().reset_index()
    csv['constellation'] = csv.constellation.map(CONSTELLATIONS)
    csv['births_estimated'] = csv.births.round(1)
    csv['source'] = csv.series.map(SERIES_SOURCE)
    csv[['country', 'year', 'tropical', 'sidereal', 'constellation', 'births_estimated', 'source']].to_csv(
        CSV_OUT, index=False, lineterminator='\n')
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=['compute', 'compute-sky', 'compute-births', 'compute-centuries', 'validate',
                                     'export'])
    a = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    if a.step == 'compute':
        compute()
    if a.step == 'compute-sky':
        compute_sky()
    if a.step == 'compute-births':
        compute_births()
    if a.step == 'compute-centuries':
        compute_centuries()
    if a.step == 'validate':
        validate()
    if a.step == 'export':
        export()
    return 0


if __name__ == '__main__':
    sys.exit(main())
