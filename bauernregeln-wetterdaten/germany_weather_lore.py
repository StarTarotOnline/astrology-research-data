#!/usr/bin/env python3
"""German weather lore (Bauernregeln) against the daily station records of the Deutscher Wetterdienst.

Source of the numbers on https://startarot.online/de/research/bauernregeln-wetterdaten

Needs Python 3.10+ and
    pip install numpy pandas pyswisseph
The raw files (about 400 MB) go to $WEATHER_LORE_DATA (default: ./weather-lore-data next to this
script). Steps, in order:

    python3 germany_weather_lore.py fetch      # DWD station archives + regional averages (resumable)
    python3 germany_weather_lore.py compute    # anomalies, rules, baselines -> $WEATHER_LORE_DATA
    python3 germany_weather_lore.py validate   # physical ranges, cross-checks, calendar arithmetic
    python3 germany_weather_lore.py export     # page JSON + dataset CSV (+ a copy of this script in the repo)

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/germany-weather-lore.json   data the page renders
    frontend/static/research/germany-weather-lore.csv     the open dataset (one row per station and measure)
    frontend/static/research/germany_weather_lore.py      a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

Sources (Deutscher Wetterdienst, opendata.dwd.de, licence CC BY 4.0)
---------------------------------------------------------------------
* Daily climate records of the German station network (CDC, observations_germany/climate/daily/kl/
  historical): mean, maximum and minimum air temperature, minimum 5 cm above ground, precipitation,
  sunshine and snow depth. One archive per station, from November 1759 (Leipzig-Holzhausen) to the end
  of the last full year; the analysis starts with 1760. ``fetch`` writes the SHA-256 of every file to manifest.json: DWD republishes the archives
  once a year with a new end date in the name, so a pin would only record which year was fetched.
* Monthly regional averages (CDC, regional_averages_DE): the mean temperature of Germany from 1881, used
  only to check the station network (``validate``).

The rules, fixed before the full computation
--------------------------------------------
Each rule is written down here with its variants before any network result was seen; the page prints
every variant, including those that fail. A first look at three stations (Hohenpeißenberg, Potsdam,
Dresden) came before this list and is the only result that did.

Singularities — "is there such a spell at all" (``SINGULARITIES``): the mean anomaly of daily mean
temperature over the window, against a smooth annual curve (below), and the contrast of the window with
the ten days on each side of it. Every rule is computed for the Gregorian date and for the date it had
when the saying arose, ten days later (the saints' days predate the calendar reform: 1583 in the Catholic,
1700 in the Protestant lands).
    Eisheilige 11–15 May (cold), Schafskälte 4–20 June (cold), Hundstage 23 July – 23 August (warm),
    Altweibersommer 15–30 September (warm), Weihnachtstauwetter 24–29 December (warm).
Two practical numbers go with them: the chance of an air frost (minimum below 0 °C at 2 m) or a ground
frost (below 0 °C at 5 cm) after 15 May, the "kalte Sophie" gardeners plant after; and the chance of a
white Christmas by DWD's definition, snow cover of at least 1 cm on the mornings of 24, 25 and 26 December.

Forecasting rules — "does the day tell what follows" (``RULES``): the weather of a key day (or window)
against the weather of the period the saying names.
    Siebenschläfer: the weather of 27 June for seven weeks; as a day and as the window 27 June – 10 July
        DWD reads it as (then for 11 July – 15 August), each for wet days, sunshine and temperature;
    Medardus: rain on 8 June, rain for forty days;
    Lichtmess: a bright 2 February, a long winter (a cold 3 February – 31 March);
    Petri Stuhlfeier: frost on 22 February, frost for forty days after;
    Mariä Geburt: as the weather of 8 September, so the four weeks after;
    a bright January, a hot summer (June–August);
    grüne Weihnachten, weiße Ostern: no white Christmas, snow on Easter Sunday.

Mondwechsel bringt Wetterwechsel (``moon_rule``): a weather change on the CET day of a principal phase
(new moon, first quarter, full moon, last quarter; Swiss Ephemeris), against all days. A change is a jump
of the 3-day mean temperature anomaly across the day among the station's top fifth, or a switch between
a mostly dry and a mostly wet three days (at most one and at least two wet days of three, either way).

Method
------
* Anomalies (``era_anomaly``): each station's daily temperature minus a smooth annual curve — four
  harmonics and a linear trend, fitted separately in each of ``ERAS`` (a station needs
  ``MIN_ERA_YEARS`` years in an era). Four harmonics bend over months, so a spell of days cannot hide in
  the curve, and the era trend keeps a warming century from passing for a warm window. A station move
  shifts all days of the year alike and leaves the shape of the year — what the rules are about — alone.
* The network (``network``): stations are averaged within cells of 0.5° latitude × 0.75° longitude
  (about 55 km), the cells with equal weight, so that dense networks in some states do not outvote the
  rest. The same cell weights (one over the stations of a cell) average station results.
* Singularities: the network's mean anomaly of the window per era, with a bootstrap over years; its
  rank among all windows of the same length in the era's mean year (a cold spell should be among the
  coldest windows of its season, not merely below a curve).
* Forecasting rules, per station over ``PREDICTIVE_PERIOD``: the key window and the target window are
  aggregated per year (share of wet days ≥ 1 mm, mean sunshine, mean temperature anomaly, share of frost
  days). Each yearly series is detrended — a trend common to both windows, warming or brightening, would
  otherwise pass for a forecast — and split at its median (years on the median drop out); a key day that
  is itself yes/no (rain, frost) is used as it is. Skill is the phi coefficient of the two splits, signed
  so that the saying's direction is positive, and the hit rate (50 % = a coin).
* Three baselines for every forecasting rule: (1) the coin, 50 %, by construction of the split;
  (2) persistence — the same weather over the 14 days (or the key window's length, if longer) before
  the key day; (3) every day of the year as the key day (``lostag_curve``): key and target windows
  shifted together by −182…+182 days. A real Lostag is a peak in that curve, not a point above zero.
  The saying's day is ranked against all other key days and against its own season (4–30 days away:
  ``LOCAL_RANK``), since persistence itself varies with the season — winter and early spring forecast
  better than midsummer whatever the day. The curve's noise is its spread around a 15-day running
  mean (wrapping round the year); with a day-to-day noise of about 0.05 the curve's highest point among
  365 is no Lostag, so only the smoothed peak is reported. Key days without a forecast (frost in July)
  are left out of the ranks, not counted as worse. Each rule is also counted in the two halves of the
  period (``HALVES``): a day that is special only in one half is not a Lostag.
* Hit rates are read against their own coin (``hit_rate_if_independent``): 50 % for a median split,
  far less for rare events — white Easter follows in about one year of twelve. Next to it the share of
  years with the target after the key and after its absence, which is what the saying promises.
* Station moves (``station_moves``): a move inside the period shifts key and target windows of a year
  alike, so each rule is also counted on the stations that never moved (``phi_unmoved``).
* Comparisons of periods (late frost, white Christmas) are also made on the stations with numbers in
  both (``common_change``): the network of 1951–2000 is larger than that of the last thirty years.
* Hundstage claim the hottest time of the year, which the anomaly test cannot see by construction (the
  smooth curve is that hot time): ``hottest_window`` finds the warmest window of their length in the
  plain mean temperature of 1991–2020.
* Significance by randomisation, not by standard errors: years of the key window permuted
  (``PERMUTATIONS``) — one permutation for all stations at once, so that the network's spatial
  correlation stays in the null — and a bootstrap over years for intervals. The moon's null moves each
  phase instant by its own random span inside its quarter (``PHASE_SHIFT``): a day of the same season
  that is no phase day.
* Multiple testing (``multiple_testing``): one Benjamini–Hochberg family over every hypothesis on the
  page — forecasting rules, the moon, planet years and each singularity per calendar and era (its p-value
  is its rank share: the chance that a window at a random place of the year is as extreme). The page
  calls a rule confirmed only at q ≤ 0.05; persistence and the other baselines are not hypotheses.
* Planet years of the Hundertjähriger Kalender (``planet_of_year``): the cycle Saturn, Jupiter, Mars,
  Sonne, Venus, Merkur, Mond, each year from 21 March (1896 and 2022 are years of Jupiter). Network
  temperature anomaly and share of wet days per planet year, tested by permuting the years among the
  planets. The almanac's month-by-month text is not encoded yet.

Data quality: values outside physical bounds (``BOUNDS``) are set missing and counted; ``validate``
stops ``export`` when they are more than a trace, when the network loses its year-to-year agreement with
DWD's own average for Germany, or when the calendar arithmetic (Easter, planet years) is off.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import warnings
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'bauernregeln-wetterdaten'
FILE_STEM = 'germany-weather-lore'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'germany_weather_lore.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('WEATHER_LORE_DATA') or HERE / 'weather-lore-data')
RAW = DATA / 'raw'
UA = 'Mozilla/5.0 (research script; startarot.online)'
CDC = 'https://opendata.dwd.de/climate_environment/CDC/'
KL_DIR = CDC + 'observations_germany/climate/daily/kl/historical/'
STATION_LIST = 'KL_Tageswerte_Beschreibung_Stationen.txt'
REGIONAL_DIR = CDC + 'regional_averages_DE/monthly/air_temperature_mean/'

FIRST_YEAR, LAST_YEAR = 1760, 2025
ERAS = [(1760, 1880), (1881, 1950), (1951, 2000), (2001, 2025)]
MIN_ERA_YEARS = 20          # years with ≥ 300 days of mean temperature for an era fit
RECENT = (1996, 2025)       # the last thirty years: the practical numbers (frost, white Christmas)
PREDICTIVE_PERIOD = (1951, 2025)
MIN_RULE_YEARS = 30         # station-years a station needs for a forecasting rule
CELL = (0.5, 0.75)          # network cell, degrees latitude × longitude
OLD_STYLE_DAYS = 10         # Julian → Gregorian in the 16th–17th centuries
FLANK_DAYS = 10
PERMUTATIONS = 2000
BOOTSTRAPS = 1000
SEED = 20261023

COLUMNS = ['TMK', 'TXK', 'TNK', 'TGK', 'RSK', 'SDK', 'SHK_TAG']
BOUNDS = {'TMK': (-40, 40), 'TXK': (-35, 45), 'TNK': (-45, 35), 'TGK': (-50, 35), 'RSK': (0, 350),
          'SDK': (0, 17), 'SHK_TAG': (0, 800)}
WET_MM = 1.0
SOPHIE = (5, 15)

# name: (start month, day), (end month, day), expected sign of the anomaly
SINGULARITIES = {
    'eisheilige': ((5, 11), (5, 15), -1),
    'schafskaelte': ((6, 4), (6, 20), -1),
    'hundstage': ((7, 23), (8, 23), +1),
    'altweibersommer': ((9, 15), (9, 30), +1),
    'weihnachtstauwetter': ((12, 24), (12, 29), +1),
}

# name: key day (month, day), key days, days from the key window's end to the target, target days,
# predictor variable, target variable, sign (+1: the target follows the key, −1: the opposite)
RULES = {
    'siebenschlaefer_day_wet': ((6, 27), 1, 0, 49, 'wet', 'wet', +1),
    'siebenschlaefer_day_sun': ((6, 27), 1, 0, 49, 'sun', 'sun', +1),
    'siebenschlaefer_day_warm': ((6, 27), 1, 0, 49, 'warm', 'warm', +1),
    'siebenschlaefer_window_wet': ((6, 27), 14, 0, 36, 'wet', 'wet', +1),
    'siebenschlaefer_window_sun': ((6, 27), 14, 0, 36, 'sun', 'sun', +1),
    'siebenschlaefer_window_warm': ((6, 27), 14, 0, 36, 'warm', 'warm', +1),
    'medardus_wet': ((6, 8), 1, 0, 40, 'wet', 'wet', +1),
    'lichtmess_bright_cold': ((2, 2), 1, 0, 57, 'sun', 'warm', -1),
    'petri_stuhlfeier_frost': ((2, 22), 1, 0, 40, 'frost', 'frost', +1),
    'mariae_geburt_wet': ((9, 8), 1, 0, 28, 'wet', 'wet', +1),
    # 1–31 January → June–August; in leap years the target starts on 31 May
    'januar_bright_summer_hot': ((1, 1), 31, 120, 92, 'sun', 'warm', +1),
}
CHRISTMAS_EASTER = 'gruene_weihnachten_weisse_ostern'
OFFSETS = np.arange(-182, 183)
CURVE_SMOOTH = 15           # days of the running mean the curve's noise is measured against
LOCAL_RANK = (4, 30)        # key days this far (in days) from the saying's own make its season
PERSISTENCE_DAYS = 14
HALVES = [(1951, 1987), (1988, 2025)]
MIN_HALF_YEARS = 15
# a station counts as moved when its position shifts by more than this within PREDICTIVE_PERIOD
MOVE_DEG, MOVE_HEIGHT_M = 0.02, 20
HOTTEST_PERIOD = (1991, 2020)   # the WMO normal period: where the warmest weeks of the year lie

# Mondwechsel bringt Wetterwechsel: the four principal phases, a change judged over three days on each side
PHASES = ['new_moon', 'first_quarter', 'full_moon', 'last_quarter']
CHANGE_DAYS = 3
TEMP_CHANGE_QUANTILE = 0.8  # a temperature change: the station's top fifth of 3-day jumps
PHASE_SHIFT = (1.5, 5.88)   # null: each phase instant moved by its own random span inside its quarter
# (CET date, phase) of well-documented phases, eclipses among them; 2025-01-07 is 23:56 UTC on the 6th
KNOWN_PHASES = [('1999-08-11', 'new_moon'), ('2000-01-21', 'full_moon'), ('2015-03-20', 'new_moon'),
                ('2024-01-25', 'full_moon'), ('2024-04-08', 'new_moon'), ('2025-01-07', 'first_quarter')]

PLANETS = ['Saturn', 'Jupiter', 'Mars', 'Sonne', 'Venus', 'Merkur', 'Mond']


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ downloads
def curl(url: str, dest: Path, tries: int = 6) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + '.part')
    for _ in range(tries):
        r = subprocess.run(['curl', '-sSL', '-f', '-A', UA, '-m', '600', '-C', '-', '-o', str(tmp), url])
        if r.returncode == 0:
            tmp.rename(dest)
            return
        time.sleep(5)
    raise RuntimeError(f'download failed: {url}')


def listing(url: str, pattern: str) -> list[str]:
    r = subprocess.run(['curl', '-sSL', '-f', '-A', UA, '-m', '120', url], capture_output=True, text=True, check=True)
    return sorted(set(re.findall(pattern, r.stdout)))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def fetch():
    kl = RAW / 'kl'
    names = listing(KL_DIR, r'tageswerte_KL_\d{5}_\d{8}_\d{8}_hist\.zip')
    if not names:
        raise RuntimeError(f'no station archives listed at {KL_DIR}')
    curl(KL_DIR + STATION_LIST, kl / STATION_LIST)
    # DWD republishes an archive with a new end date in its name: the older file is dropped
    current = set(names)
    for old in kl.glob('tageswerte_KL_*_hist.zip'):
        if old.name not in current:
            old.unlink()
            log(f'dropped {old.name} (republished)')
    with cf.ThreadPoolExecutor(6) as ex:
        list(ex.map(lambda n: curl(KL_DIR + n, kl / n), names))
    log(f'station archives: {len(names)}')
    for n in listing(REGIONAL_DIR, r'regional_averages_tm_\d{2}\.txt'):
        curl(REGIONAL_DIR + n, RAW / 'regional' / n)
    manifest = {str(p.relative_to(RAW)): {'bytes': p.stat().st_size, 'sha256': sha256(p)}
                for p in sorted(RAW.rglob('*')) if p.is_file() and not p.name.endswith('.part')}
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n')
    log(f'manifest: {len(manifest)} files, {sum(v["bytes"] for v in manifest.values()) // 2**20} MB')


# ------------------------------------------------------------------ reading
def read_station_list() -> pd.DataFrame:
    rows = []
    for line in (RAW / 'kl' / STATION_LIST).read_text(encoding='latin-1').splitlines()[2:]:
        t = line.split()
        if len(t) < 9 or not t[0].isdigit():
            continue
        rows.append({'station': int(t[0]), 'height_m': float(t[3]), 'lat': float(t[4]), 'lon': float(t[5]),
                     'name': ' '.join(t[6:-2]), 'state': t[-2]})
    return pd.DataFrame(rows).drop_duplicates('station').set_index('station')


def read_station(path: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    """Daily values on a continuous calendar; values outside ``BOUNDS`` set missing and counted."""
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.startswith('produkt_klima_tag_'))
        with z.open(name) as f:
            df = pd.read_csv(f, sep=';', skipinitialspace=True, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    date = pd.to_datetime(df.MESS_DATUM.str.strip(), format='%Y%m%d')
    out = pd.DataFrame({c: pd.to_numeric(df[c].str.strip(), errors='coerce') if c in df else np.nan for c in COLUMNS})
    out = out.mask(out == -999)
    out.index = date
    dups = int(out.index.duplicated().sum())
    out = out[~out.index.duplicated()].sort_index()
    out = out[(out.index.year >= FIRST_YEAR) & (out.index.year <= LAST_YEAR)]
    out = out.reindex(pd.date_range(out.index[0], out.index[-1], freq='D'))
    bad = {}
    for c, (lo, hi) in BOUNDS.items():
        m = (out[c] < lo) | (out[c] > hi)
        bad[c] = int(m.sum())
        out.loc[m, c] = np.nan
    bad['duplicate_dates'] = dups
    order = (out.TNK <= out.TMK + 0.5) & (out.TMK <= out.TXK + 0.5)
    known = out[['TNK', 'TMK', 'TXK']].notna().all(axis=1)
    bad['tn_tm_tx_order'] = int((known & ~order).sum())
    bad['tn_tm_tx_known'] = int(known.sum())
    return out, bad


def station_moves(path: Path) -> int:
    """Moves within ``PREDICTIVE_PERIOD`` by the archive's position history (Metadaten_Geographie): a
    shift of more than ``MOVE_DEG`` in latitude or longitude or ``MOVE_HEIGHT_M`` in height between
    consecutive records. −1 when the archive has no history."""
    with zipfile.ZipFile(path) as z:
        name = next((n for n in z.namelist() if n.startswith('Metadaten_Geographie')), None)
        if name is None:
            return -1
        with z.open(name) as f:
            g = pd.read_csv(f, sep=';', encoding='latin-1', skipinitialspace=True, dtype=str)
    g.columns = [c.strip() for c in g.columns]
    g = g.assign(h=pd.to_numeric(g.Stationshoehe, errors='coerce'), lat=pd.to_numeric(g['Geogr.Breite'], errors='coerce'),
                 lon=pd.to_numeric(g['Geogr.Laenge'], errors='coerce'),
                 von=pd.to_numeric(g.von_datum.str.strip(), errors='coerce'),
                 bis=pd.to_numeric(g.bis_datum.fillna('').str.strip().replace('', '99999999'), errors='coerce'))
    g = g.sort_values('von').reset_index(drop=True)
    moves = 0
    for i in range(1, len(g)):
        a, b = g.iloc[i - 1], g.iloc[i]
        if not (PREDICTIVE_PERIOD[0] * 10000 < b.von <= PREDICTIVE_PERIOD[1] * 10000 + 1231):
            continue
        if (abs(b.lat - a.lat) > MOVE_DEG or abs(b.lon - a.lon) > MOVE_DEG or abs(b.h - a.h) > MOVE_HEIGHT_M):
            moves += 1
    return moves


def read_regional() -> pd.DataFrame:
    parts = []
    for p in sorted((RAW / 'regional').glob('regional_averages_tm_*.txt')):
        d = pd.read_csv(p, sep=';', skiprows=1, skipinitialspace=True)
        d.columns = [c.strip() for c in d.columns]
        parts.append(d[['Jahr', 'Monat', 'Deutschland']].rename(columns={'Jahr': 'year', 'Monat': 'month', 'Deutschland': 'tm'}))
    return pd.concat(parts).astype({'year': int, 'month': int, 'tm': float}).sort_values(['year', 'month'])


# ------------------------------------------------------------------ calendar
def gregorian_easter(y: int) -> dt.date:
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    return dt.date(y, month, (h + l_ - 7 * m + 114) % 31 + 1)


def planet_of_year(y: int) -> str:
    """Ruling planet of the year beginning on 21 March of ``y`` (1896 and 2022: Jupiter)."""
    return PLANETS[(PLANETS.index('Jupiter') + y - 2022) % 7]


def window_dates(y: int, start: tuple[int, int], end: tuple[int, int], shift: int = 0) -> tuple[dt.date, int]:
    a = dt.date(y, *start) + dt.timedelta(days=shift)
    b = dt.date(y, *end) + dt.timedelta(days=shift)
    return a, (b - a).days + 1


def doy365(idx: pd.DatetimeIndex) -> np.ndarray:
    """Day of a 365-day year (1…365); 29 February → 0."""
    d = idx.dayofyear.values - (idx.is_leap_year & (idx.month > 2)).astype(int)
    return np.where((idx.month == 2) & (idx.day == 29), 0, d)


# ------------------------------------------------------------------ building blocks
def era_anomaly(s: pd.Series) -> pd.Series:
    out = pd.Series(np.nan, index=s.index)
    for a, b in ERAS:
        m = (s.index.year >= a) & (s.index.year <= b)
        x = s[m]
        if not len(x):
            continue
        per_year = x.notna().groupby(x.index.year).sum()
        if (per_year >= 300).sum() < MIN_ERA_YEARS:
            continue
        idx = x.index
        frac = (idx.dayofyear.values - 1) / np.where(idx.is_leap_year, 366, 365)
        w = 2 * np.pi * frac
        cols = [np.ones(len(x)), (idx.year.values + frac - (a + b) / 2) / 100]
        for k in range(1, 5):
            cols += [np.sin(k * w), np.cos(k * w)]
        X = np.column_stack(cols)
        v = x.values
        ok = ~np.isnan(v)
        beta = np.linalg.lstsq(X[ok], v[ok], rcond=None)[0]
        out[m] = v - X @ beta
    return out


def window_means(v: np.ndarray, starts, length: int, min_frac: float = 0.9) -> np.ndarray:
    """Mean of ``v`` over [start, start + length) for every start (any shape); NaN where outside the
    series or with fewer than ``min_frac`` of the days known."""
    valid = ~np.isnan(v)
    cs = np.concatenate([[0.0], np.cumsum(np.where(valid, v, 0.0))])
    cn = np.concatenate([[0], np.cumsum(valid)])
    s = np.asarray(starts)
    e = s + length
    ok = (s >= 0) & (e <= len(v))
    s2, e2 = np.clip(s, 0, len(v)), np.clip(e, 0, len(v))
    n = cn[e2] - cn[s2]
    with np.errstate(invalid='ignore', divide='ignore'):
        return np.where(ok & (n >= max(1, int(np.ceil(min_frac * length)))), (cs[e2] - cs[s2]) / n, np.nan)


def detrend(x: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Remove a least-squares line along the last axis (NaN-aware)."""
    m = ~np.isnan(x)
    tt = np.where(m, t, 0.0)
    xx = np.where(m, x, 0.0)
    n = m.sum(-1, keepdims=True)
    with np.errstate(invalid='ignore', divide='ignore'):
        mt, mx = tt.sum(-1, keepdims=True) / n, xx.sum(-1, keepdims=True) / n
        cov = (np.where(m, (t - mt) * (x - mx), 0.0)).sum(-1, keepdims=True)
        var = (np.where(m, (t - mt) ** 2, 0.0)).sum(-1, keepdims=True)
        slope = np.where(var > 0, cov / var, 0.0)
    return x - mx - slope * (t - mt)


def median_split(x: np.ndarray, t: np.ndarray) -> np.ndarray:
    """1 above the median of the detrended series, 0 below, NaN on it or missing (along the last axis)."""
    d = detrend(x, t)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', RuntimeWarning)   # rows with no known year
        med = np.nanmedian(d, axis=-1, keepdims=True)
    return np.where(np.isnan(d) | (d == med), np.nan, (d > med).astype(float))


def phi(P: np.ndarray, T: np.ndarray, min_n: int = 1) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """phi coefficient, hit rate and pair count of two 0/1 arrays along the last axis."""
    m = ~np.isnan(P) & ~np.isnan(T)
    n = m.sum(-1)
    p, q = np.where(m, P, 0.0), np.where(m, T, 0.0)
    with np.errstate(invalid='ignore', divide='ignore'):
        mp, mq, mpq = p.sum(-1) / n, q.sum(-1) / n, (p * q).sum(-1) / n
        den = np.sqrt(mp * (1 - mp) * mq * (1 - mq))
        r = np.where((n >= min_n) & (den > 0), (mpq - mp * mq) / den, np.nan)
        hit = np.where(n >= min_n, (np.where(m, P == T, False)).sum(-1) / n, np.nan)
    return r, hit, n


def cell_of(lat: float, lon: float) -> str:
    return f'{int(np.floor(lat / CELL[0]))}:{int(np.floor(lon / CELL[1]))}'


def cell_weights(stations: list[int], cells: dict[int, str]) -> np.ndarray:
    c = pd.Series([cells[s] for s in stations])
    return (1.0 / c.map(c.value_counts())).values


def wmean(x: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Weighted mean over the first axis (stations), NaN-aware."""
    m = ~np.isnan(x)
    ww = np.where(m, w.reshape((-1,) + (1,) * (x.ndim - 1)), 0.0)
    s = ww.sum(0)
    return np.where(s > 0, (np.where(m, x, 0.0) * ww).sum(0) / np.where(s > 0, s, 1.0), np.nan)


def boot_ci(x: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    x = x[~np.isnan(x)]
    if len(x) < 5:
        return float('nan'), float('nan')
    b = x[rng.integers(0, len(x), (BOOTSTRAPS, len(x)))].mean(1)
    return float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))


def r_(x, nd: int = 3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


# ------------------------------------------------------------------ per station
def daily_variables(df: pd.DataFrame, anom: pd.Series) -> dict[str, np.ndarray]:
    return {
        'wet': np.where(df.RSK.isna(), np.nan, (df.RSK >= WET_MM).astype(float)),
        'sun': df.SDK.values.astype(float),
        'warm': anom.values,
        'frost': np.where(df.TNK.isna(), np.nan, (df.TNK < 0).astype(float)),
    }


def station_rules(df: pd.DataFrame, var: dict[str, np.ndarray]) -> dict[str, dict]:
    """Per forecasting rule: key/target/persistence splits for ``PREDICTIVE_PERIOD`` and the phi curve
    over ``OFFSETS``."""
    d0 = df.index[0].date()
    years = np.arange(PREDICTIVE_PERIOD[0], PREDICTIVE_PERIOD[1] + 1)
    t = years.astype(float)
    out = {}
    for name, ((km, kd), kdays, gap, tdays, pv, tv, sign) in RULES.items():
        anchor = np.array([(dt.date(y, km, kd) - d0).days for y in years])
        starts = anchor[None, :] + OFFSETS[:, None]                     # (offsets, years)
        key = window_means(var[pv], starts, kdays)
        target = window_means(var[tv], starts + kdays + gap, tdays)
        binary_key = kdays == 1 and pv in ('wet', 'frost')
        P = key if binary_key else median_split(key, t)
        T = median_split(target, t)
        curve, _, n = phi(P, T, MIN_RULE_YEARS)
        pdays = max(PERSISTENCE_DAYS, kdays)
        pers = median_split(window_means(var[pv], anchor - pdays, pdays), t)
        i0 = int(np.where(OFFSETS == 0)[0][0])
        # the same splits, counted in each half of the period: does the day stay special?
        halves = {f'{a}-{b}': sign * phi(P[:, (years >= a) & (years <= b)], T[:, (years >= a) & (years <= b)],
                                         MIN_HALF_YEARS)[0] for a, b in HALVES}
        out[name] = {'P': P[i0], 'T': T[i0], 'Pp': pers, 'curve': sign * curve, 'halves': halves, 'n': int(n[i0])}
    # grüne Weihnachten, weiße Ostern: white Christmas of y against snow on Easter Sunday of y + 1
    snow = df.SHK_TAG
    P, T = np.full(len(years), np.nan), np.full(len(years), np.nan)
    for j, y in enumerate(years[:-1]):
        xmas = snow.reindex(pd.date_range(f'{y}-12-24', f'{y}-12-26'))
        if xmas.notna().all():
            P[j] = float((xmas >= 1).all())
        e = snow.get(pd.Timestamp(gregorian_easter(int(y) + 1)), np.nan)
        if e == e:
            T[j] = float(e >= 1)
    out[CHRISTMAS_EASTER] = {'P': P, 'T': T, 'Pp': np.full(len(years), np.nan), 'curve': None, 'halves': None,
                             'n': int((~np.isnan(P) & ~np.isnan(T)).sum())}
    return out


def station_changes(df: pd.DataFrame, anom: pd.Series, wet: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Weather changes on each day of ``PREDICTIVE_PERIOD`` (1/0, NaN unknown or outside it): a jump of the
    3-day mean temperature anomaly across the day among the station's top fifth, and a switch between a
    mostly dry and a mostly wet three days (≤ 1 and ≥ 2 wet days of 3, either way)."""
    idx = np.arange(len(df))
    period = (df.index.year >= PREDICTIVE_PERIOD[0]) & (df.index.year <= PREDICTIVE_PERIOD[1])
    jump = np.abs(window_means(anom.values, idx + 1, CHANGE_DAYS, 1.0) - window_means(anom.values, idx - CHANGE_DAYS, CHANGE_DAYS, 1.0))
    known = period & np.isfinite(jump)
    chg_t = np.full(len(df), np.nan)
    if known.sum() >= 3650:
        chg_t[known] = (jump[known] >= np.quantile(jump[known], TEMP_CHANGE_QUANTILE)).astype(float)
    before = np.rint(window_means(wet, idx - CHANGE_DAYS, CHANGE_DAYS, 1.0) * CHANGE_DAYS)
    after = np.rint(window_means(wet, idx + 1, CHANGE_DAYS, 1.0) * CHANGE_DAYS)
    known = period & np.isfinite(before) & np.isfinite(after)
    switch = ((before <= 1) & (after >= 2)) | ((before >= 2) & (after <= 1))
    chg_r = np.where(known, switch.astype(float), np.nan)
    return chg_t, chg_r


def moon_phases(y0: int, y1: int) -> pd.DataFrame:
    """Instants of the four principal phases, y0–y1 (Swiss Ephemeris, Moshier), with the civil date in
    CET (UTC+1, the date a German almanac prints; summer time is left out)."""
    import swisseph as swe

    def quarter(jd: float) -> int:
        e = swe.calc_ut(jd, swe.MOON, swe.FLG_MOSEPH)[0][0] - swe.calc_ut(jd, swe.SUN, swe.FLG_MOSEPH)[0][0]
        return int((e % 360) // 90)

    jd, end = swe.julday(y0, 1, 1, 0.0) - 2, swe.julday(y1 + 1, 1, 1, 0.0) + 2
    q_prev, rows = quarter(jd), []
    while jd < end:
        nxt = jd + 0.25
        q = quarter(nxt)
        if q != q_prev:
            a, b = jd, nxt
            for _ in range(30):   # 6 h / 2^30: far below a second
                mid = (a + b) / 2
                a, b = (mid, b) if quarter(mid) == q_prev else (a, mid)
            y, m, d, _ = swe.revjul(b + 1 / 24)
            rows.append({'jd_ut': b, 'phase': PHASES[q], 'date': dt.date(y, m, d).isoformat()})
            q_prev = q
        jd = nxt
    ph = pd.DataFrame(rows)
    return ph[(ph.date >= f'{y0}-01-01') & (ph.date <= f'{y1}-12-31')].reset_index(drop=True)


def moon_rule(net: pd.DataFrame, ph: pd.DataFrame, rng) -> dict:
    """Share of the network with a weather change on the day of a phase change against all days; null:
    each phase instant moved by its own random span inside its quarter (``PHASE_SHIFT``). One span for all
    of them would leave only the handful of whole-day shifts the span covers as distinct null sets, and a
    p-value far below what those few sets can support."""
    import swisseph as swe
    sub = net[(net.index.year >= PREDICTIVE_PERIOD[0]) & (net.index.year <= PREDICTIVE_PERIOD[1])]
    d0 = sub.index[0]
    t = ph.jd_ut.values + 1 / 24 - swe.julday(d0.year, d0.month, d0.day, 0.0)   # days since d0, CET
    out = {'phase_changes': len(ph)}
    for key in ('chg_t', 'chg_r'):
        c = sub[key].values
        base = float(np.nanmean(c))

        def rate(tt):
            i = np.floor(tt).astype(int)
            return float(np.nanmean(c[i[(i >= 0) & (i < len(c))]]))

        obs = rate(t)
        null = np.array([rate(t + rng.uniform(*PHASE_SHIFT, len(t))) for _ in range(PERMUTATIONS)])
        out[key] = {'all_days': r_(base, 4), 'phase_days': r_(obs, 4), 'difference': r_(obs - base, 4),
                    'null_interval': [r_(np.percentile(null, 2.5), 4), r_(np.percentile(null, 97.5), 4)],
                    'p_value': r_((1 + (null >= obs).sum()) / (1 + PERMUTATIONS), 4),
                    'by_phase': {p: r_(rate(t[ph.phase.values == p]), 4) for p in PHASES}}
    return out


def benjamini_hochberg(p: dict[str, float]) -> dict[str, float]:
    keys = [k for k, v in p.items() if v is not None and np.isfinite(v)]
    ps = np.array([p[k] for k in keys])
    q, prev = np.empty(len(ps)), 1.0
    for rank, i in reversed(list(enumerate(np.argsort(ps), 1))):
        prev = min(prev, ps[i] * len(ps) / rank)
        q[i] = prev
    return dict(zip(keys, q.tolist()))


def multiple_testing(est: dict) -> dict:
    """One Benjamini–Hochberg family over every hypothesis the page tests: the forecasting rules, the
    moon, the planet years and each singularity per calendar and era (its rank share is the p-value of
    "a window at a random place in the year"). Baselines (persistence) are not hypotheses and stay out.
    Writes ``q_value`` next to each p-value."""
    p, at = {}, {}
    for k, r in est['rules'].items():
        p[f'rule/{k}'], at[f'rule/{k}'] = r['p_value'], (r, 'q_value')
    for k in ('chg_t', 'chg_r'):
        p[f'moon/{k}'], at[f'moon/{k}'] = est['moon'][k]['p_value'], (est['moon'][k], 'q_value')
    for k in ('tmk', 'wet'):
        p[f'planets/{k}'], at[f'planets/{k}'] = est['planet_years'][f'{k}_p_value'], (est['planet_years'], f'{k}_q_value')
    for k, by in est['singularities'].items():
        for era, r in by.items():
            p[f'singularity/{k}/{era}'], at[f'singularity/{k}/{era}'] = r['rank_share'], (r, 'q_value')
    q = benjamini_hochberg(p)
    for k, v in q.items():
        target, field = at[k]
        target[field] = r_(v, 4)
    return {'method': 'Benjamini–Hochberg', 'tests': len(q),
            'discoveries_q_0_05': sorted(k for k, v in q.items() if v <= 0.05)}


def singularity_years(v: np.ndarray, d0: dt.date, years: np.ndarray) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Per singularity and calendar: the window's mean anomaly in each year and its contrast with the
    ``FLANK_DAYS`` on each side."""
    out = {}
    for name, (start, end, _) in SINGULARITIES.items():
        for cal, shift in (('gregorian', 0), ('old_style', OLD_STYLE_DAYS)):
            n = window_dates(2001, start, end, shift)[1]
            i = np.array([(window_dates(int(y), start, end, shift)[0] - d0).days for y in years])
            w = window_means(v, i, n)
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                flank = np.nanmean([window_means(v, i - FLANK_DAYS, FLANK_DAYS), window_means(v, i + n, FLANK_DAYS)], axis=0)
            out[f'{name}/{cal}'] = (w, w - flank)
    return out


def station_singularities(sid: int, anom: pd.Series) -> list[dict]:
    years = np.arange(anom.index[0].year, anom.index[-1].year + 1)
    rows = []
    for key, (w, c) in singularity_years(anom.values, anom.index[0].date(), years).items():
        name, cal = key.split('/')
        for y, a, b in zip(years, w, c):
            if np.isfinite(a):
                rows.append({'station': sid, 'year': int(y), 'rule': name, 'calendar': cal,
                             'anomaly': round(float(a), 3), 'contrast': round(float(b), 3) if np.isfinite(b) else np.nan})
    return rows


def station_frost_christmas(sid: int, df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    frost, xmas = [], []
    for y, g in df.groupby(df.index.year):
        spring = g[(g.index.month >= 3) & (g.index.month <= 6)]
        row = {'station': sid, 'year': y}
        for col, key in (('TNK', 'last_air_frost_doy'), ('TGK', 'last_ground_frost_doy')):
            if len(spring) >= 120 and spring[col].notna().mean() >= 0.95:
                f = g[(g.index.month <= 7) & (g[col] < 0)]
                row[key] = int(f.index[-1].dayofyear) if len(f) else 0
        if len(row) > 2:
            frost.append(row)
        d = g.SHK_TAG.reindex(pd.date_range(f'{y}-12-24', f'{y}-12-26'))
        if d.notna().all():
            xmas.append({'station': sid, 'year': y, 'white': int((d >= 1).all())})
    return frost, xmas


# ------------------------------------------------------------------ compute
def compute():
    rng = np.random.default_rng(SEED)
    meta = read_station_list()
    zips = sorted((RAW / 'kl').glob('tageswerte_KL_*_hist.zip'))
    if not zips:
        raise SystemExit('no station archives — run fetch first')
    days = pd.date_range(f'{FIRST_YEAR}-01-01', f'{LAST_YEAR}-12-31', freq='D')
    nd = len(days)
    cell_sum = {k: {} for k in ('tmk', 'tnk', 'wet', 'chg_t', 'chg_r', 'tmk_abs')}
    cell_cnt = {k: {} for k in cell_sum}
    stations, quality, sing_rows, frost_rows, xmas_rows = [], [], [], [], []
    rules: dict[str, dict[int, dict]] = {k: {} for k in [*RULES, CHRISTMAS_EASTER]}
    for k, z in enumerate(zips):
        sid = int(z.name.split('_')[2])
        if sid not in meta.index:
            log(f'{z.name}: not in the station list, skipped')
            continue
        df, bad = read_station(z)
        m = meta.loc[sid]
        cell = cell_of(m.lat, m.lon)
        tmk_a, tnk_a = era_anomaly(df.TMK), era_anomaly(df.TNK)
        quality.append({'station': sid, **bad})
        stations.append({'station': sid, 'name': m['name'], 'state': m.state, 'lat': m.lat, 'lon': m.lon,
                         'height_m': m.height_m, 'cell': cell, 'first': df.index[0].date().isoformat(),
                         'last': df.index[-1].date().isoformat(), 'days_tmk': int(df.TMK.notna().sum()),
                         'moves': station_moves(z),
                         'years_tmk': int((df.TMK.notna().groupby(df.index.year).sum() >= 300).sum()),
                         'years_rsk': int((df.RSK.notna().groupby(df.index.year).sum() >= 300).sum())})
        i0 = (df.index[0] - days[0]).days
        var = daily_variables(df, tmk_a)
        chg_t, chg_r = station_changes(df, tmk_a, var['wet'])
        # tmk_abs: the plain mean temperature, only for where the warmest weeks of the year lie
        for key, arr in (('tmk', tmk_a.values), ('tnk', tnk_a.values), ('wet', var['wet']), ('chg_t', chg_t),
                         ('chg_r', chg_r), ('tmk_abs', df.TMK.values.astype(float))):
            if cell not in cell_sum[key]:
                cell_sum[key][cell] = np.zeros(nd, np.float32)
                cell_cnt[key][cell] = np.zeros(nd, np.float32)
            ok = ~np.isnan(arr)
            cell_sum[key][cell][i0:i0 + len(arr)] += np.where(ok, arr, 0).astype(np.float32)
            cell_cnt[key][cell][i0:i0 + len(arr)] += ok
        sing_rows += station_singularities(sid, tmk_a)
        f, x = station_frost_christmas(sid, df)
        frost_rows += f
        xmas_rows += x
        if df.index[-1].year >= PREDICTIVE_PERIOD[0] + MIN_RULE_YEARS - 1:
            for name, res in station_rules(df, var).items():
                if res['n'] >= MIN_RULE_YEARS:
                    rules[name][sid] = res
        if k % 100 == 0:
            log(f'{k}/{len(zips)} stations')

    st = pd.DataFrame(stations).set_index('station')
    st.to_csv(DATA / 'stations.csv')
    pd.DataFrame(quality).to_csv(DATA / 'quality.csv', index=False)
    sing = pd.DataFrame(sing_rows)
    sing.to_csv(DATA / 'singularity_years.csv.gz', index=False)
    frost = pd.DataFrame(frost_rows)
    frost.to_csv(DATA / 'frost_years.csv.gz', index=False)
    xmas = pd.DataFrame(xmas_rows)
    xmas.to_csv(DATA / 'christmas_years.csv.gz', index=False)

    # network: cells with equal weight
    net = pd.DataFrame(index=days)
    for key in cell_sum:
        with np.errstate(invalid='ignore', divide='ignore'), warnings.catch_warnings():
            warnings.simplefilter('ignore', RuntimeWarning)   # days before the first station
            means = np.vstack([cell_sum[key][c] / cell_cnt[key][c] for c in cell_sum[key]])
            net[key] = np.nanmean(np.where(np.isfinite(means), means, np.nan), axis=0)
        net[f'cells_{key}'] = np.isfinite(means).sum(0)
    net.index.name = 'date'
    net.round(4).to_csv(DATA / 'network_daily.csv.gz')

    cells = st.cell.to_dict()
    est = {'stations': len(st), 'station_days_tmk': int(st.days_tmk.sum()),
           'profiles': era_profiles(net),
           'singularities': network_singularities(net, rng),
           'frost_after_sophie': share_by_period(frost, st, cells, 'last_air_frost_doy'),
           'ground_frost_after_sophie': share_by_period(frost, st, cells, 'last_ground_frost_doy'),
           'white_christmas': white_christmas(xmas, cells),
           # the same comparison on the stations with numbers in both periods: the network changed
           'frost_after_sophie_common': common_change(frost, cells, 'last_air_frost_doy'),
           'white_christmas_common': common_change(xmas, cells, 'white'),
           'hottest_window': hottest_window(net),
           'rules': network_rules(rules, cells, set(st.index[st.moves != 0]), rng),
           'planet_years': planet_years(net, rng)}
    ph = moon_phases(*PREDICTIVE_PERIOD)
    ph.to_csv(DATA / 'moon_phases.csv', index=False)
    est['moon'] = moon_rule(net, ph, rng)
    est['multiple_testing'] = multiple_testing(est)
    curves = {name: {str(s): r['curve'] for s, r in by.items()} for name, by in rules.items() if name in RULES}
    np.savez_compressed(DATA / 'lostag_curves.npz', **{f'{n}__{s}': c for n, by in curves.items() for s, c in by.items()})
    rule_years = []
    years = np.arange(PREDICTIVE_PERIOD[0], PREDICTIVE_PERIOD[1] + 1)
    for name, by in rules.items():
        for s, r in by.items():
            for j, y in enumerate(years):
                if not (np.isnan(r['P'][j]) and np.isnan(r['T'][j])):
                    rule_years.append((name, s, int(y), r['P'][j], r['T'][j], r['Pp'][j]))
    pd.DataFrame(rule_years, columns=['rule', 'station', 'year', 'key', 'target', 'persistence']).to_csv(
        DATA / 'rule_years.csv.gz', index=False)
    (DATA / 'estimates.json').write_text(json.dumps(est, ensure_ascii=False, indent=1) + '\n')
    log(json.dumps({k: est[k] for k in ('stations', 'singularities', 'rules')}, ensure_ascii=False)[:4000])


def era_of(y: int) -> str | None:
    for a, b in ERAS:
        if a <= y <= b:
            return f'{a}-{b}'
    return None


def network_singularities(net: pd.DataFrame, rng) -> dict:
    """Per singularity, calendar and era: the network's mean anomaly and contrast with bootstrap
    intervals, and the window's rank among all windows of its length in the era's mean year."""
    years = np.arange(FIRST_YEAR, LAST_YEAR + 1)
    per_year = singularity_years(net.tmk.values, net.index[0].date(), years)
    profiles = era_profiles(net, rounded=False)
    cells = net.cells_tmk.groupby(net.index.year).min()
    out = {}
    for key, (w, c) in per_year.items():
        name, cal = key.split('/')
        start, end, sign = SINGULARITIES[name]
        shift = OLD_STYLE_DAYS if cal == 'old_style' else 0
        s0, n = window_dates(2001, start, end, shift)
        k0 = s0.timetuple().tm_yday - 1
        res = {}
        for a, b in ERAS:
            m = (years >= a) & (years <= b)
            prof = np.array(profiles[f'{a}-{b}'], dtype=float)
            allw = window_means(np.concatenate([prof, prof[:n]]), np.arange(365), n, min_frac=1.0)
            rank = float(np.nanmean(sign * allw >= sign * allw[k0])) if np.isfinite(allw[k0]) else np.nan
            res[f'{a}-{b}'] = {
                'years': int(np.isfinite(w[m]).sum()), 'min_cells': int(cells[(cells.index >= a) & (cells.index <= b)].min()),
                'anomaly': r_(np.nanmean(w[m])), 'anomaly_ci': [r_(x) for x in boot_ci(w[m], rng)],
                'contrast': r_(np.nanmean(c[m])), 'contrast_ci': [r_(x) for x in boot_ci(c[m], rng)],
                # share of all same-length windows of the era's mean year at least as cold (warm) as this one
                'rank_share': r_(rank)}
        out[key] = res
    return out


def era_profiles(net: pd.DataFrame, rounded: bool = True) -> dict[str, list]:
    """The network's mean temperature anomaly per day of a 365-day year, per era. Ranks are taken on
    the unrounded profile: rounding to 0.01 °C first makes ties of windows that differ."""
    d365 = doy365(net.index)
    out = {}
    for a, b in ERAS:
        m = (net.index.year >= a) & (net.index.year <= b) & (d365 > 0)
        prof = pd.Series(net.tmk.values[m]).groupby(d365[m]).mean().reindex(range(1, 366))
        out[f'{a}-{b}'] = [r_(x, 2) for x in prof.values] if rounded else prof.values
    return out


def hottest_window(net: pd.DataFrame) -> dict:
    """Where the warmest weeks of the year lie (``HOTTEST_PERIOD``, plain mean temperature of the
    network): the Hundstage claim to be the hottest time of the year, a claim the anomaly test cannot see."""
    start, end, _ = SINGULARITIES['hundstage']
    days = window_dates(2001, start, end)[1]
    d365 = doy365(net.index)
    m = (net.index.year >= HOTTEST_PERIOD[0]) & (net.index.year <= HOTTEST_PERIOD[1]) & (d365 > 0)
    prof = pd.Series(net.tmk_abs.values[m]).groupby(d365[m]).mean().reindex(range(1, 366)).values
    allw = window_means(np.concatenate([prof, prof[:days]]), np.arange(365), days, min_frac=1.0)
    k = int(np.nanargmax(allw))
    a, b = dt.date(2001, 1, 1) + dt.timedelta(days=k), dt.date(2001, 1, 1) + dt.timedelta(days=k + days - 1)
    h0 = dt.date(2001, *start).timetuple().tm_yday - 1
    return {'period': f'{HOTTEST_PERIOD[0]}-{HOTTEST_PERIOD[1]}', 'days': days, 'start': [a.month, a.day],
            'end': [b.month, b.day], 'overlap_days': max(0, days - abs(k - h0)),
            'hundstage_mean_c': r_(float(allw[h0]), 2), 'warmest_mean_c': r_(float(allw[k]), 2)}


def after_sophie(frost: pd.DataFrame, col: str) -> pd.DataFrame:
    """Years with ``col`` (the last frost's day of the year) after 15 May, leap years counted."""
    sophie = dt.date(2001, *SOPHIE).timetuple().tm_yday   # 135; leap years: 136 = 15 May too
    f = frost.dropna(subset=[col]).copy()
    leap = f.year.map(lambda y: int(y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)))
    f['after'] = (f[col] > sophie + leap).astype(float)
    return f


def common_change(df: pd.DataFrame, cells: dict, col: str) -> dict:
    """1951–2000 against ``RECENT`` on the stations with at least 20 years in both: the network of
    the second half of the century is larger, and its mountain and coastal shares differ."""
    d = after_sophie(df, col) if col.endswith('_doy') else df.assign(after=df[col].astype(float))
    old = d[(d.year >= 1951) & (d.year <= 2000)].groupby('station').after.agg(['mean', 'size'])
    new = d[(d.year >= RECENT[0]) & (d.year <= RECENT[1])].groupby('station').after.agg(['mean', 'size'])
    both = old[old['size'] >= 20].join(new[new['size'] >= 20], lsuffix='_old', rsuffix='_new', how='inner')
    w = cell_weights(list(both.index), cells)
    return {'stations': len(both), 'from_period': '1951-2000', 'to_period': f'{RECENT[0]}-{RECENT[1]}',
            'from': r_(float(np.average(both.mean_old, weights=w))),
            'to': r_(float(np.average(both.mean_new, weights=w)))}


def periods() -> list[tuple[int, int]]:
    return [*ERAS, RECENT]


def share_by_period(frost: pd.DataFrame, st: pd.DataFrame, cells: dict, col: str) -> dict:
    """Chance of a frost after 15 May: per station in each period, then the cell-weighted network."""
    f = after_sophie(frost, col)
    out = {}
    for a, b in periods():
        g = f[(f.year >= a) & (f.year <= b)].groupby('station').after.agg(['mean', 'size'])
        g = g[g['size'] >= min(20, (b - a + 1) // 2)]
        if not len(g):
            continue
        w = cell_weights(list(g.index), cells)
        out[f'{a}-{b}'] = {'stations': len(g), 'share': r_(np.average(g['mean'], weights=w)),
                           'by_station': {int(s): r_(v) for s, v in g['mean'].items()}}
    return out


def white_christmas(xmas: pd.DataFrame, cells: dict) -> dict:
    out = share_by_period_simple(xmas, cells, 'white')
    yearly = {}
    for y, g in xmas.groupby('year'):
        if len(g) >= 10:
            yearly[int(y)] = r_(np.average(g.white, weights=cell_weights(list(g.station), cells)))
    out['by_year'] = yearly
    return out


def share_by_period_simple(df: pd.DataFrame, cells: dict, col: str) -> dict:
    out = {}
    for a, b in periods():
        g = df[(df.year >= a) & (df.year <= b)].groupby('station')[col].agg(['mean', 'size'])
        g = g[g['size'] >= min(20, (b - a + 1) // 2)]
        if len(g):
            out[f'{a}-{b}'] = {'stations': len(g), 'share': r_(np.average(g['mean'], weights=cell_weights(list(g.index), cells))),
                               'by_station': {int(s): r_(v) for s, v in g['mean'].items()}}
    return out


def network_rules(rules: dict, cells: dict, moved: set[int], rng) -> dict:
    out = {}
    for name, by in rules.items():
        if not by:
            continue
        sign = RULES[name][6] if name in RULES else -1
        sids = list(by)
        w = cell_weights(sids, cells)
        P = np.vstack([by[s]['P'] for s in sids])
        T = np.vstack([by[s]['T'] for s in sids])
        Pp = np.vstack([by[s]['Pp'] for s in sids])

        def stat(PP, TT):
            # eligibility is MIN_RULE_YEARS on the real years; a permutation may move a station's
            # key years onto years without a target, and it stays in with fewer pairs
            r, hit, n = phi(PP, TT, 10)
            return float(wmean(sign * r, w)), float(wmean(hit if sign > 0 else 1 - hit, w))

        obs, hit = stat(P, T)
        Y = P.shape[1]
        null = np.array([stat(P[:, rng.permutation(Y)], T)[0] for _ in range(PERMUTATIONS)])
        boot = np.array([stat(P[:, b], T[:, b])[0] for b in rng.integers(0, Y, (BOOTSTRAPS, Y))])
        m = ~np.isnan(P) & ~np.isnan(T)
        with np.errstate(invalid='ignore', divide='ignore'):
            n = m.sum(1)
            pk = np.where(m, P, 0).sum(1) / n            # share of years with the key "yes"
            pt = np.where(m, T, 0).sum(1) / n            # share of years with the target "yes"
            agree = pk * pt + (1 - pk) * (1 - pt)         # agreement if key and target were independent
            # target "yes" after the key "yes" and after "no": what a reader of the saying expects to see
            t_yes = np.where(m & (P == 1), T, 0).sum(1) / np.where(m & (P == 1), 1, 0).sum(1)
            t_no = np.where(m & (P == 0), T, 0).sum(1) / np.where(m & (P == 0), 1, 0).sum(1)
        unmoved = np.array([s not in moved for s in sids])
        res = {'stations': len(sids), 'phi': r_(obs), 'hit_rate': r_(hit),
               # the coin a hit rate is read against: 50 % for median splits, far less for rare events
               'hit_rate_if_independent': r_(float(wmean(agree if sign > 0 else 1 - agree, w))),
               'target_after_key': r_(float(wmean(t_yes, w))), 'target_after_no_key': r_(float(wmean(t_no, w))),
               'phi_ci': [r_(np.nanpercentile(boot, 2.5)), r_(np.nanpercentile(boot, 97.5))],
               'p_value': r_((1 + (null >= obs).sum()) / (1 + PERMUTATIONS), 4),
               # a move within the period shifts key and target windows of a year alike and could fake a
               # forecast for temperature and frost: the same rule on stations that never moved
               'stations_unmoved': int(unmoved.sum()),
               'phi_unmoved': r_(float(wmean(sign * phi(P[unmoved], T[unmoved], 10)[0], cell_weights(
                   [s for s, u in zip(sids, unmoved) if u], cells)))) if unmoved.sum() >= 30 else None}
        if np.isfinite(Pp).any():
            pobs, phit = stat(Pp, T)
            pnull = np.array([stat(Pp[:, rng.permutation(Y)], T)[0] for _ in range(PERMUTATIONS)])
            res |= {'persistence_phi': r_(pobs), 'persistence_hit_rate': r_(phit),
                    'persistence_p_value': r_((1 + (pnull >= pobs).sum()) / (1 + PERMUTATIONS), 4)}
        if name == CHRISTMAS_EASTER:
            # white Easters are rare: the hit rate alone flatters or damns the saying by the base rate,
            # so the page compares the chance of a white Easter after a green and after a white Christmas
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', RuntimeWarning)
                after = {k: np.nanmean(np.where(P == v, T, np.nan), axis=1) for k, v in (('green', 0), ('white', 1))}
            res |= {f'white_easter_after_{k}_christmas': r_(float(wmean(v, w))) for k, v in after.items()}
        if by[sids[0]]['curve'] is not None:
            C = np.vstack([by[s]['curve'] for s in sids])
            # a key day counts where most of the network has a forecast: frost in July has no variance
            # and no phi, and a curve over the few mountain stations would compare a different network
            cover = np.isfinite(C).sum(0)
            defined = cover >= 0.8 * len(sids)
            curve = np.where(defined, wmean(C, w), np.nan)
            i0 = int(np.where(OFFSETS == 0)[0][0])
            # the 365 offsets are 365 consecutive key days: the running mean wraps round the year
            h = CURVE_SMOOTH // 2
            ring = pd.Series(np.concatenate([curve[-h:], curve, curve[:h]]))
            smooth = ring.rolling(CURVE_SMOOTH, center=True, min_periods=h).mean().values[h:-h]

            def rank(sel, c=curve):   # share of those key days whose forecast is at least as good
                sel = sel & np.isfinite(c)   # a day without a forecast is not "worse"
                return r_(float(np.mean(c[sel] >= c[i0])))

            far = np.abs(OFFSETS)
            local = (far >= LOCAL_RANK[0]) & (far <= LOCAL_RANK[1])
            halves = {}
            for period in by[sids[0]]['halves']:
                Ch = np.vstack([by[s]['halves'][period] for s in sids])
                # coverage against the stations that report in this half: many closed before 1988
                cov = np.isfinite(Ch).sum(0)
                ch = np.where(cov >= 0.8 * cov.max(), wmean(Ch, w), np.nan)
                halves[period] = {'phi': r_(float(ch[i0])), 'curve_local_rank_share': rank(local, ch)}
            res['halves'] = halves

            res |= {'curve': [r_(x) for x in curve],
                    'curve_defined_days': int(defined.sum()), 'curve_key_day_defined': bool(defined[i0]),
                    'curve_stations_min': int(cover[defined].min()) if defined.any() else 0,
                    'curve_rank_share': rank(OFFSETS != 0),
                    'curve_local_rank_share': rank(local),
                    # day-to-day noise: the spread around the running mean
                    'curve_noise': r_(float(np.nanstd(curve - smooth))),
                    'curve_smoothed_peak_offset': int(OFFSETS[int(np.nanargmax(smooth))])}
        out[name] = res
    return out


def planet_years(net: pd.DataFrame, rng) -> dict:
    rows = []
    for y in range(1881, LAST_YEAR):
        g = net.loc[f'{y}-03-21':f'{y + 1}-03-20']
        if len(g) >= 365 and g.tmk.notna().mean() >= 0.9:
            rows.append({'year': y, 'planet': planet_of_year(y), 'tmk': g.tmk.mean(), 'wet': g.wet.mean()})
    d = pd.DataFrame(rows)
    out = {'years': [int(d.year.min()), int(d.year.max())], 'by_planet': {}}
    for col in ('tmk', 'wet'):
        x = (d[col] - d[col].mean()).values
        lab = d.planet.values

        def f_stat(labels):
            means = pd.Series(x).groupby(labels).mean()
            return float((means ** 2).mean())

        obs = f_stat(lab)
        null = np.array([f_stat(rng.permutation(lab)) for _ in range(PERMUTATIONS)])
        out[f'{col}_p_value'] = r_((1 + (null >= obs).sum()) / (1 + PERMUTATIONS), 4)
        for p in PLANETS:
            v = x[lab == p]
            out['by_planet'].setdefault(p, {})[col] = {'mean': r_(v.mean(), 4), 'ci': [r_(c, 4) for c in boot_ci(v, rng)],
                                                      'years': int(len(v))}
    return out


# ------------------------------------------------------------------ validate
def validate():
    """Checks; any failure stops ``export``. Results -> $WEATHER_LORE_DATA/validation.json."""
    problems, checks = [], {}
    q = pd.read_csv(DATA / 'quality.csv')
    st = pd.read_csv(DATA / 'stations.csv')
    net = pd.read_csv(DATA / 'network_daily.csv.gz', parse_dates=['date']).set_index('date')
    est = json.loads((DATA / 'estimates.json').read_text())

    # 1. values outside physical bounds and the order Tmin ≤ Tmean ≤ Tmax: a trace, not a pattern
    total_days = int((pd.to_datetime(st['last']) - pd.to_datetime(st['first'])).dt.days.sum())
    for c in BOUNDS:
        checks[f'out_of_bounds_{c}'] = int(q[c].sum())
        if q[c].sum() > 1e-4 * total_days:
            problems.append(f'{c}: {int(q[c].sum())} values out of bounds')
    share = q.tn_tm_tx_order.sum() / max(1, q.tn_tm_tx_known.sum())
    checks['tn_tm_tx_order_share'] = round(float(share), 6)
    if share > 1e-3:
        problems.append(f'Tmin ≤ Tmean ≤ Tmax broken on {share:.3%} of days')
    checks['duplicate_dates'] = int(q.duplicate_dates.sum())

    # 2. the network follows DWD's own average for Germany year to year (first differences per month,
    #    within an era: the anomaly removes each era's trend and level)
    reg = read_regional()
    mon = net.tmk.groupby([net.index.year, net.index.month]).mean()
    mon.index.names = ['year', 'month']
    j = reg.set_index(['year', 'month']).tm.to_frame().join(mon.rename('net'), how='inner').reset_index()
    j['era'] = j.year.map(era_of)
    j = j.sort_values(['month', 'year'])
    g = j.groupby(['month', 'era'])
    dd = pd.DataFrame({'dwd': g.tm.diff(), 'net': g.net.diff()}).dropna()
    corr = float(dd.dwd.corr(dd.net))
    checks['network_vs_dwd_germany_diff_corr'] = round(corr, 4)
    if corr < 0.95:
        problems.append(f'network vs DWD Germany: year-to-year correlation {corr:.3f} < 0.95')

    # 3. the network has stations every year of the analysis
    cells = net.cells_tmk.groupby(net.index.year).min()
    thin = [int(y) for y, c in cells.items() if y >= 1881 and c < 5]
    checks['years_from_1881_under_5_cells'] = thin
    problems += [f'{y}: under 5 network cells' for y in thin]
    checks['min_cells_by_era'] = {f'{a}-{b}': int(cells[(cells.index >= a) & (cells.index <= b)].min()) for a, b in ERAS}

    # 4. calendar arithmetic
    easter = {2019: dt.date(2019, 4, 21), 2024: dt.date(2024, 3, 31), 2025: dt.date(2025, 4, 20),
              2026: dt.date(2026, 4, 5), 1900: dt.date(1900, 4, 15), 1954: dt.date(1954, 4, 18)}
    bad = [y for y, d in easter.items() if gregorian_easter(y) != d]
    checks['easter_errors'] = bad
    problems += [f'Easter {y}: computed {gregorian_easter(y)}' for y in bad]
    anchors = {1896: 'Jupiter', 2022: 'Jupiter', 2026: 'Merkur'}
    bad = [y for y, p in anchors.items() if planet_of_year(y) != p]
    checks['planet_year_errors'] = bad
    problems += [f'planet year {y}: {planet_of_year(y)}, expected {anchors[y]}' for y in bad]

    ph = pd.read_csv(DATA / 'moon_phases.csv')
    have = set(zip(ph.date, ph.phase))
    bad = [f'{d} {p}' for d, p in KNOWN_PHASES if dt.date.fromisoformat(d).year <= PREDICTIVE_PERIOD[1] and (d, p) not in have]
    checks['moon_known_phase_errors'] = bad
    problems += [f'moon: no {b} among the computed phases' for b in bad]
    per_year = ph.groupby(ph.date.str[:4]).size()
    checks['moon_phases_per_year'] = [int(per_year.min()), int(per_year.max())]
    if per_year.min() < 48 or per_year.max() > 51:
        problems.append(f'moon: {per_year.min()}…{per_year.max()} phases a year')

    # 5. every forecasting rule rests on a network, not on a handful of stations; its Lostag curve
    #    covers the saying's own day and a season of other days to rank it against
    for name, r in est['rules'].items():
        checks[f'stations_{name}'] = r['stations']
        if r['stations'] < 100:
            problems.append(f'{name}: only {r["stations"]} stations')
        if 'curve' in r and (not r['curve_key_day_defined'] or r['curve_defined_days'] < 60):
            problems.append(f'{name}: the Lostag curve covers {r["curve_defined_days"]} days'
                            + ('' if r['curve_key_day_defined'] else ', not the key day'))

    # 6. the q-values are q-values
    pairs = [(r['p_value'], r['q_value']) for r in est['rules'].values()]
    pairs += [(est['moon'][k]['p_value'], est['moon'][k]['q_value']) for k in ('chg_t', 'chg_r')]
    pairs += [(r['rank_share'], r['q_value']) for by in est['singularities'].values() for r in by.values()]
    bad = [p_ for p_, q_ in pairs if q_ is None or q_ < p_ - 1e-9 or q_ > 1]
    checks['multiple_testing_tests'] = est['multiple_testing']['tests']
    problems += [f'q-value below its p-value or missing (p = {p_})' for p_ in bad]

    (DATA / 'validation.json').write_text(json.dumps({'checks': checks, 'problems': problems}, ensure_ascii=False, indent=1))
    for k, v in checks.items():
        log(f'{k}: {v}')
    for p in problems:
        log('  PROBLEM', p)
    log('validation ' + ('passed' if not problems else f'FAILED: {len(problems)} problems'))
    return not problems


# ------------------------------------------------------------------ export
def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed — run validate and resolve its problems first')
    est = json.loads((DATA / 'estimates.json').read_text())
    st = pd.read_csv(DATA / 'stations.csv').set_index('station')
    manifest = (DATA / 'manifest.json').read_bytes()
    by_station = {}   # (station, measure, period) -> value

    def put(measure: str, block: dict):
        for period, r in block.items():
            if isinstance(r, dict) and 'by_station' in r:
                for s, v in r['by_station'].items():
                    by_station[(int(s), measure, period)] = v

    put('p_air_frost_after_15_may', est['frost_after_sophie'])
    put('p_ground_frost_after_15_may', est['ground_frost_after_sophie'])
    put('p_white_christmas', est['white_christmas'])

    def strip(block: dict) -> dict:
        return {k: ({kk: vv for kk, vv in v.items() if kk != 'by_station'} if isinstance(v, dict) else v)
                for k, v in block.items()}

    # «Ihre Station»: the practical numbers of the last thirty years, per station
    recent = f'{RECENT[0]}-{RECENT[1]}'
    measures = ['p_air_frost_after_15_may', 'p_ground_frost_after_15_may', 'p_white_christmas']
    keep = sorted({s for s, _, p in by_station if p == recent})
    out = {
        'generated_by': 'scripts/research/germany_weather_lore.py',
        'source': 'Deutscher Wetterdienst, CDC Open Data (CC BY 4.0)',
        'dwd_manifest_sha256': hashlib.sha256(manifest).hexdigest(),
        'first_year': FIRST_YEAR, 'last_year': LAST_YEAR, 'eras': [f'{a}-{b}' for a, b in ERAS],
        'recent': f'{RECENT[0]}-{RECENT[1]}', 'predictive_period': f'{PREDICTIVE_PERIOD[0]}-{PREDICTIVE_PERIOD[1]}',
        'stations_total': est['stations'], 'station_days_tmk': est['station_days_tmk'],
        'profiles': est['profiles'],
        'singularities': est['singularities'],
        'frost_after_sophie': strip(est['frost_after_sophie']),
        'ground_frost_after_sophie': strip(est['ground_frost_after_sophie']),
        'white_christmas': strip(est['white_christmas']),
        'rules': est['rules'], 'offsets': [int(OFFSETS[0]), int(OFFSETS[-1])],
        'planet_years': est['planet_years'],
        'moon': est['moon'], 'multiple_testing': est['multiple_testing'],
        'frost_after_sophie_common': est['frost_after_sophie_common'],
        'white_christmas_common': est['white_christmas_common'],
        'hottest_window': est['hottest_window'],
        'permutations': PERMUTATIONS, 'min_rule_years': MIN_RULE_YEARS, 'persistence_days': PERSISTENCE_DAYS,
        'halves': [f'{a}-{b}' for a, b in HALVES], 'local_rank_days': list(LOCAL_RANK),
        'rule_defs': {k: {'key': list(v[0]), 'key_days': v[1], 'gap_days': v[2], 'target_days': v[3],
                          'predictor': v[4], 'target': v[5], 'sign': v[6]} for k, v in RULES.items()},
        'singularity_defs': {k: {'start': list(a), 'end': list(b), 'sign': s} for k, (a, b, s) in SINGULARITIES.items()},
        'old_style_days': OLD_STYLE_DAYS,
        # station, name, state, height, then per measure of ``station_columns`` its share 1996–2025
        # (null: too few years) — the stations with at least one of them
        'station_columns': measures,
        'stations': [[int(s), st.at[s, 'name'], st.at[s, 'state'], int(st.at[s, 'height_m'])]
                     + [by_station.get((s, m, recent)) for m in measures] for s in keep],
        'validation': val['checks'],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    ds = pd.DataFrame([(s, st.at[s, 'name'], st.at[s, 'state'], st.at[s, 'lat'], st.at[s, 'lon'], st.at[s, 'height_m'],
                        m, p, v) for (s, m, p), v in sorted(by_station.items())],
                      columns=['station_id', 'station', 'state', 'lat', 'lon', 'height_m', 'measure', 'period', 'value'])
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    ds.to_csv(CSV_OUT, index=False, lineterminator='\n')
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
