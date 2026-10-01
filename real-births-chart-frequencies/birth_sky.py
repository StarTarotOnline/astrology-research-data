#!/usr/bin/env python3
"""How real birth times shape the birth chart: 95.7 million births in Brazil, Japan and the USA.

Source of the numbers on https://startarot.online/research/real-births-chart-frequencies (English)
and https://startarot.online/pt/research/mapa-astral-nascimentos-reais-brasil (Portuguese, Brazil).

Needs Python 3.10+, curl and unzip on PATH, and
    pip install numpy pandas pyarrow pyswisseph pyreaddbc dbfread timezonefinder
The raw data (several GB) are downloaded into $BIRTH_SKY_DATA (default: ./birth-sky-data next to
this script). Steps, in order:

    python3 birth_sky.py fetch           # all sources (resumable; Brazil's FTP is slow, ~3 MB/min/stream)
    python3 birth_sky.py compute         # per-country-year weighted counts -> $BIRTH_SKY_DATA/counts/
    python3 birth_sky.py export          # page JSON + dataset CSV (+ a copy of this script in the repo)

Sub-steps can be run alone: fetch-br|fetch-jp|fetch-us [years], compute-br|compute-us [years],
compute-jp, degrade [years], mars-model.

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/real-births-chart-frequencies.json   data both pages render
    frontend/static/research/real-births-chart-frequencies.csv     the open dataset (long format)
    frontend/static/research/birth_sky.py                           a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

What is counted
---------------
For every birth (Brazil) or weighted cell (Japan, USA) we take the UT instant and place, and compute
with Swiss Ephemeris (data files sepl_18/semo_18, downloaded) and closed formulas checked against
swe.houses_armc / swe.house_pos (``selftest``: 0 mismatches expected):
  - sect ("day chart"): geometric altitude of the Sun's centre > 0 — identical to the Sun in Placidus
    houses 7–12; alternatives: whole-sign houses 7–12, apparent sunrise (altitude > −0.833°);
  - for the Sun, Moon, Mercury, Venus, Mars, Jupiter, Saturn: tropical sign, Placidus house (by
    ecliptic longitude, as chart software does), whole-sign house, Gauquelin 36 sectors (true position
    with ecliptic latitude; sector 1 starts at rising, 10 at culmination);
  - Ascendant and MC signs; Lahiri sidereal signs of the Sun, Moon, Ascendant; Sun × Ascendant pairs;
  - "Sun, Mercury and Venus all in houses 7–12" (and by altitude).

Ladder of rungs (same places in every rung)
-------------------------------------------
  B1 period astronomy     every date of the year equal, time uniform over each local civil day
  B2 real dates           real births per date (season, weekday, holidays), time uniform per day
  B3 spontaneous profile  real births per date, spread by the local-clock hour profile of
                          spontaneous-onset births (Brazil: PARTO=1 & STTRABPART=2, meaningful from
                          2012; Japan: births at midwife homes + at home, pooled 2015–2024; USA:
                          DMETH_REC=1 & LD_INDL=N). "Spontaneous" is not "natural".
  B4 real                 real births at their recorded time
B1–B3 are integrated on a 5-minute grid (Brazil: 288 steps over the real length of each local day,
23/24/25 h; Japan: 12 steps per recorded hour; USA: 5-minute bins).

Sources and their limits
------------------------
Brazil — SINASC, Ministério da Saúde / DATASUS, national files DNBR{year}.dbc, 2006–2024 (files before
2006 carry no birth time). Every live birth with a valid HORANASC (99.6–99.95 %), at the seat of its
municipality of OCCURRENCE (IBGE coordinates via github.com/kelvins/municipios-brasileiros, MIT),
local clock time → UT with the IANA zone of that point (DST history from the tz database; times in
the spring-forward gap are shifted by +1 h, repeated times take the first occurrence; both counted).
OpenDataSUS publishes SINASC under CC BY-ND 3.0: we publish aggregates only, with attribution.
Japan — Vital Statistics (人口動態統計), e-Stat table 0003411915 "births by place, month, day and hour",
2015–2024, national only; spread over the 47 prefectures by 2023 births by prefecture (e-Stat file
000040207154) at the prefectural offices (GSI coordinates). JST, no DST. Government of Japan
Standard Terms of Use (compatible with CC BY 4.0).
USA — NCHS Natality public-use files 2016–2024 (U.S. government work): month, weekday and clock time
(DOB_TT) but NO day of month and NO place. Births of (month, weekday) are spread equally over the
matching dates; places are Census county births (co-est2024-alldata, public domain) at Gazetteer
2024 county points, 1° cells per IANA zone. The error of exactly this imputation is measured on
Brazil with the same information removed (``degrade``; 2018 has DST): published with the US numbers.
Nothing here describes people born outside these countries and years.
"""
from __future__ import annotations

import argparse
import base64
import calendar
import csv
import datetime as dt
import gzip
import html
import http.cookiejar
import io
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'real-births-chart-frequencies'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{SLUG}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{SLUG}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'birth_sky.py'
    # Compact facts for the backend (AI astrologer block, natal-chart hint) — GENERATED.
    FACTS_OUT = REPO_ROOT / 'backend' / 'app' / 'data' / 'birth_timing_facts.json'
    HOUSE_JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / 'house-frequency.json'
    RISING_JSON = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / 'rising-sign-by-latitude.json'
else:
    FACTS_OUT = None
    HOUSE_JSON_OUT = None
    RISING_JSON = None
    JSON_OUT = HERE / f'{SLUG}.json'
    CSV_OUT = HERE / f'{SLUG}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('BIRTH_SKY_DATA') or HERE / 'birth-sky-data')
COUNTS = DATA / 'counts'

BR_YEARS = list(range(2006, 2025))
JP_YEARS = list(range(2015, 2025))
US_YEARS = list(range(2016, 2025))
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius',
         'Capricorn', 'Aquarius', 'Pisces']
RUNGS = ['B1_period_astronomy', 'B2_real_dates', 'B3_spontaneous_profile', 'B4_real']
KEY_SECTORS = [0, 1, 2, 9, 10, 11]          # Gauquelin sectors 1–3 and 10–12
UA = 'Mozilla/5.0 (research script; startarot.online)'


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ downloads
def curl_resume(url: str, dest: Path, tries: int = 12) -> None:
    """Download with resume until the size matches Content-Length (curl handles http and ftp)."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    head = subprocess.run(['curl', '-sI', '-m', '60', url], capture_output=True, text=True).stdout
    m = re.search(r'content-length:\s*(\d+)', head, re.I)
    want = int(m.group(1)) if m else None
    for _ in range(tries):
        have = dest.stat().st_size if dest.exists() else 0
        if want is not None and have == want:
            return
        subprocess.run(['curl', '-s', '-m', '3600', '-C', '-', '-o', str(dest), url])
        if want is None and dest.exists():
            return
    if want is not None and (not dest.exists() or dest.stat().st_size != want):
        raise RuntimeError(f'download failed: {url}')


def curl_ranged(url: str, dest: Path, parts: int = 12) -> None:
    """Parallel ranged download (the CDC server throttles single streams)."""
    head = subprocess.run(['curl', '-sI', '-m', '60', url], capture_output=True, text=True).stdout
    size = int(re.search(r'content-length:\s*(\d+)', head, re.I).group(1))
    chunk = -(-size // parts)
    procs = []
    for i in range(parts):
        s, e = i * chunk, min(size, (i + 1) * chunk) - 1
        part = dest.with_suffix(dest.suffix + f'.part{i}')
        procs.append((part, s, e))
    def get(part, s, e):
        for _ in range(10):
            have = part.stat().st_size if part.exists() else 0
            if have == e - s + 1:
                return
            if have > e - s + 1:
                part.unlink(); have = 0
            with open(part, 'ab') as fh:
                subprocess.run(['curl', '-s', '-m', '1800', '-r', f'{s + have}-{e}', url], stdout=fh)
        raise RuntimeError(f'part failed: {part}')
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(parts) as ex:
        list(ex.map(lambda p: get(*p), procs))
    with open(dest, 'wb') as out:
        for part, _, _ in procs:
            out.write(part.read_bytes()); part.unlink()
    if dest.stat().st_size != size:
        raise RuntimeError(f'size mismatch {dest}')


def ensure_ephemeris() -> None:
    d = DATA / 'ephe'
    for f in ('sepl_18.se1', 'semo_18.se1'):
        if not (d / f).exists():
            curl_resume(f'https://raw.githubusercontent.com/aloistr/swisseph/master/ephe/{f}', d / f)


# ------------------------------------------------------------------ engine
_swe = None


def swe_mod():
    global _swe
    if _swe is None:
        import swisseph as swe
        ensure_ephemeris()
        swe.set_ephe_path(str(DATA / 'ephe'))
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        _swe = swe
    return _swe


D2R = np.pi / 180.0
BODY_NAMES = ['sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn']


def local_to_jd(dates, minutes, tz):
    """Local civil date + minutes after local midnight in IANA zone tz -> (jd_ut, n_gap, n_repeat)."""
    idx = pd.DatetimeIndex(pd.to_datetime(dates) + pd.to_timedelta(np.asarray(minutes, float), unit='m'))
    gap = idx.tz_localize(tz, nonexistent='NaT', ambiguous=np.ones(len(idx), bool)).isna()
    rep = idx.tz_localize(tz, nonexistent='shift_forward', ambiguous='NaT').isna()
    loc = idx.tz_localize(tz, nonexistent=pd.Timedelta('1h'), ambiguous=np.ones(len(idx), bool))
    ut = loc.tz_convert('UTC').tz_localize(None)
    return (ut - pd.Timestamp('1970-01-01')).total_seconds().values / 86400.0 + 2440587.5, int(gap.sum()), int(rep.sum())


def day_bounds_jd(dates, tz):
    d0 = pd.DatetimeIndex(pd.to_datetime(dates))
    to = lambda x: (x.tz_convert('UTC').tz_localize(None) - pd.Timestamp('1970-01-01')).total_seconds().values / 86400.0 + 2440587.5
    a = d0.tz_localize(tz, nonexistent='shift_forward', ambiguous=np.ones(len(d0), bool))
    b = (d0 + pd.Timedelta(days=1)).tz_localize(tz, nonexistent='shift_forward', ambiguous=np.ones(len(d0), bool))
    return to(a), to(b)


def _per_unique(jd, fn, width):
    u, inv = np.unique(jd, return_inverse=True)
    out = np.empty((len(u), width))
    for i, j in enumerate(u):
        out[i] = fn(float(j))
    return out[inv]


def _body(j, b):
    swe = swe_mod()
    x, fl = swe.calc_ut(j, b, swe.FLG_SWIEPH)
    if not fl & swe.FLG_SWIEPH:
        raise RuntimeError('Swiss Ephemeris data files not found')
    return x[0], x[1]


def diurnal_position(ra, dec, armc, f):
    """Continuous diurnal position in [0, 36): 0 rising, 9 culmination, 18 setting, 27 lower culmination."""
    H = (armc - ra + np.pi) % (2 * np.pi) - np.pi
    dsa = np.arccos(np.clip(-np.tan(f) * np.tan(dec), -1.0, 1.0)); nsa = np.pi - dsa
    above = np.abs(H) < dsa
    Hl = (H % (2 * np.pi)) - np.pi
    p = np.where(above, 9.0 * (H + dsa) / np.where(dsa > 0, dsa, 1), 27.0 + 9.0 * Hl / np.where(nsa > 0, nsa, 1))
    return p % 36.0, H


def ecl_to_eq(lon, lat, e):
    L = lon * D2R; B = lat * D2R
    ra = np.arctan2(np.sin(L) * np.cos(e) - np.tan(B) * np.sin(e), np.cos(L))
    dec = np.arcsin(np.sin(B) * np.cos(e) + np.cos(B) * np.sin(e) * np.sin(L))
    return ra, dec


def features(jd, lat, lon):
    swe = swe_mod()
    bodies = dict(zip(BODY_NAMES, [swe.SUN, swe.MOON, swe.MERCURY, swe.VENUS, swe.MARS, swe.JUPITER, swe.SATURN]))
    jd = np.asarray(jd, float); lat = np.asarray(lat, float); lon = np.asarray(lon, float)
    day = np.floor(jd + 0.5)
    eps = _per_unique(day, lambda j: [swe.calc_ut(j, swe.ECL_NUT)[0][0]], 1)[:, 0]
    ayan = _per_unique(day, lambda j: [swe.get_ayanamsa_ut(j)], 1)[:, 0]
    st = _per_unique(jd, lambda j: [swe.sidtime(j)], 1)[:, 0]
    armc_deg = (st * 15.0 + lon) % 360.0
    e = eps * D2R; a = armc_deg * D2R; f = lat * D2R
    asc = np.degrees(np.arctan2(np.cos(a), -(np.sin(a) * np.cos(e) + np.tan(f) * np.sin(e)))) % 360.0
    mc = np.degrees(np.arctan2(np.sin(a), np.cos(a) * np.cos(e))) % 360.0
    asc_sign = (asc // 30).astype(np.int64)
    F = {'asc_sign': asc_sign, 'mc_sign': (mc // 30).astype(np.int64),
         'asc_sign_sid': (((asc - ayan) % 360) // 30).astype(np.int64), '_armc': armc_deg, '_eps': eps, '_asc': asc}
    for name, b in bodies.items():
        ll = _per_unique(jd, lambda j, b=b: _body(j, b), 2)
        L, B = ll[:, 0], ll[:, 1]
        sign = (L // 30).astype(np.int64)
        ra0, dec0 = ecl_to_eq(L, np.zeros_like(L), e)
        p0, _ = diurnal_position(ra0, dec0, a, f)
        ra1, dec1 = ecl_to_eq(L, B, e)
        p1, H1 = diurnal_position(ra1, dec1, a, f)
        F[f'{name}_sign'] = sign
        F[f'{name}_house'] = (12 - np.floor(p0 / 3)).astype(np.int64)
        F[f'{name}_whole'] = ((sign - asc_sign) % 12 + 1).astype(np.int64)
        F[f'{name}_gq'] = (np.floor(p1) + 1).astype(np.int64)
        alt = np.degrees(np.arcsin(np.sin(f) * np.sin(dec1) + np.cos(f) * np.cos(dec1) * np.cos(H1)))
        F[f'{name}_above'] = alt > 0
        if name == 'sun':
            F['sun_alt'] = alt
            F['sun_sign_sid'] = (((L - ayan) % 360) // 30).astype(np.int64)
        if name == 'moon':
            F['moon_sign_sid'] = (((L - ayan) % 360) // 30).astype(np.int64)
        F[f'_{name}_lon'] = L; F[f'_{name}_lat'] = B
    return F


CAT = {**{f'{b}_{k}': n for b in BODY_NAMES for k, n in (('sign', 12), ('house', 12), ('whole', 12), ('gq', 36))},
       'asc_sign': 12, 'mc_sign': 12, 'asc_sign_sid': 12, 'sun_sign_sid': 12, 'moon_sign_sid': 12}
OFFSET = {k: (1 if k.endswith(('_house', '_whole', '_gq')) else 0) for k in CAT}
SCALARS = ['sect_day', 'sect_day_whole', 'sect_day_apparent', 'smv_all_above', 'smv_any_above',
           'smv_all_upper', 'smv_any_upper']


def accumulate(acc, F, w):
    w = np.asarray(w, float)
    acc['total'] = acc.get('total', 0.0) + float(w.sum())
    for k, n in CAT.items():
        acc[k] = acc.get(k, 0) + np.bincount(F[k] - OFFSET[k], weights=w, minlength=n)[:n]
    masks = {'sect_day': F['sun_alt'] > 0, 'sect_day_whole': F['sun_whole'] >= 7,
             'sect_day_apparent': F['sun_alt'] > -0.833,
             'smv_all_above': F['sun_above'] & F['mercury_above'] & F['venus_above'],
             'smv_any_above': F['sun_above'] | F['mercury_above'] | F['venus_above'],
             'smv_all_upper': (F['sun_house'] >= 7) & (F['mercury_house'] >= 7) & (F['venus_house'] >= 7),
             'smv_any_upper': (F['sun_house'] >= 7) | (F['mercury_house'] >= 7) | (F['venus_house'] >= 7)}
    for k, m in masks.items():
        acc[k] = acc.get(k, 0.0) + float(w[m].sum())
    acc['sun_asc'] = acc.get('sun_asc', 0) + np.bincount(F['sun_sign'] * 12 + F['asc_sign'], weights=w, minlength=144)
    return acc


def selftest(n=6000, seed=11):
    swe = swe_mod()
    rng = np.random.default_rng(seed)
    jd = swe.julday(2024, 1, 1, 0) + rng.random(n) * 366
    lat = rng.uniform(-50, 50, n); lon = rng.uniform(-180, 180, n)
    F = features(jd, lat, lon)
    bad = {'asc': 0, 'placidus': 0, 'gauquelin': 0}
    for i in range(n):
        armc, la, ep = float(F['_armc'][i]), float(lat[i]), float(F['_eps'][i])
        _, ascmc = swe.houses_armc(armc, la, ep, b'P')
        bad['asc'] += abs((ascmc[0] - F['_asc'][i] + 180) % 360 - 180) > 1e-6
        for name in ('sun', 'moon', 'mars', 'saturn'):
            L, B = float(F[f'_{name}_lon'][i]), float(F[f'_{name}_lat'][i])
            bad['placidus'] += int(swe.house_pos(armc, la, ep, (L, 0.0), b'P')) != F[f'{name}_house'][i]
            bad['gauquelin'] += int(swe.house_pos(armc, la, ep, (L, B), b'G')) != F[f'{name}_gq'][i]
    return {'charts': n, **{k: int(v) for k, v in bad.items()}}


def save_counts(name, obj):
    COUNTS.mkdir(parents=True, exist_ok=True)
    def conv(x):
        if isinstance(x, dict): return {k: conv(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)): return [conv(v) for v in x]
        if isinstance(x, np.ndarray): return [float(v) for v in x]
        if isinstance(x, (np.floating, np.integer)): return x.item()
        return x
    (COUNTS / f'{name}.json').write_text(json.dumps(conv(obj)))


def load_counts(name):
    obj = json.loads((COUNTS / f'{name}.json').read_text())
    def back(x):
        if isinstance(x, dict): return {k: back(v) for k, v in x.items()}
        if isinstance(x, list) and x and all(isinstance(v, (int, float)) for v in x): return np.array(x, float)
        return x
    return back(obj)


# ------------------------------------------------------------------ Brazil
BR_DIR = DATA / 'br'
BR_KEEP = ['DTNASC', 'HORANASC', 'CODMUNNASC', 'PARTO', 'STTRABPART', 'STCESPARTO']


def fetch_br(years):
    import pyreaddbc
    from dbfread import DBF
    BR_DIR.mkdir(parents=True, exist_ok=True)
    mun = BR_DIR / 'municipios.csv'
    if not mun.exists():
        curl_resume('https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv', mun)
    tzf = BR_DIR / 'municipios_tz.csv'
    if not tzf.exists():
        from timezonefinder import TimezoneFinder
        tf = TimezoneFinder(); m = pd.read_csv(mun)
        m['tz'] = [tf.timezone_at(lng=lo, lat=la) for la, lo in zip(m.latitude, m.longitude)]
        m['cod6'] = m.codigo_ibge.astype(str).str[:6]
        m[['cod6', 'codigo_ibge', 'nome', 'latitude', 'longitude', 'codigo_uf', 'tz']].to_csv(tzf, index=False)
    for y in years:
        pq = BR_DIR / f'sinasc_{y}.parquet'
        if pq.exists():
            continue
        dbc = BR_DIR / f'DNBR{y}.dbc'; dbf = BR_DIR / f'DNBR{y}.dbf'
        curl_resume(f'ftp://ftp.datasus.gov.br/dissemin/publicos/SINASC/1996_/Dados/DNRES/DNBR{y}.dbc', dbc)
        pyreaddbc.dbc2dbf(str(dbc), str(dbf))
        fields = [f.name for f in DBF(str(dbf), load=False).fields]
        keep = [k for k in BR_KEEP if k in fields]
        recs = [{k: r.get(k) for k in keep} for r in DBF(str(dbf), encoding='iso-8859-1', load=False, char_decode_errors='replace')]
        pd.DataFrame.from_records(recs, columns=keep).astype('string').to_parquet(pq)
        dbf.unlink(); dbc.unlink()
        (BR_DIR / f'sinasc_{y}.source.txt').write_text(f'DNBR{y}.dbc downloaded {dt.date.today()} from ftp.datasus.gov.br\n')
        log(f'BR {y}: {len(recs):,} records')


def compute_br(y, grid=288):
    raw = pd.read_parquet(BR_DIR / f'sinasc_{y}.parquet')
    if 'HORANASC' not in raw:
        raise SystemExit(f'BR {y}: no HORANASC in this file (public SINASC files carry birth time from 2006)')
    audit = {'year': y, 'n_records': len(raw)}
    h = raw.HORANASC.fillna('').str.strip()
    ok = h.str.fullmatch(r'([01]\d|2[0-3])[0-5]\d')
    audit['time_blank'] = int((h == '').sum()); audit['time_valid'] = int(ok.sum())
    mins = h[ok].str[2:].astype(int)
    audit['minute_00_pct'] = float((mins == 0).mean() * 100); audit['minute_x5_pct'] = float((mins % 5 == 0).mean() * 100)
    df = raw[ok].copy()
    mun = pd.read_csv(BR_DIR / 'municipios_tz.csv', dtype={'cod6': str})
    df = df.merge(mun[['cod6', 'latitude', 'longitude', 'tz']], left_on='CODMUNNASC', right_on='cod6', how='left')
    um = df.latitude.isna(); audit['unmatched_municipality'] = int(um.sum()); df = df[~um]
    df['date'] = pd.to_datetime(df.DTNASC, format='%d%m%Y', errors='coerce')
    audit['date_bad_or_other_year'] = int((df.date.isna() | (df.date.dt.year != y)).sum())
    df = df[df.date.notna() & (df.date.dt.year == y)].reset_index(drop=True)
    df['minute'] = df.HORANASC.str[:2].astype(int) * 60 + df.HORANASC.str[2:].astype(int)
    for c in ('PARTO', 'STTRABPART', 'STCESPARTO'):
        df[c] = df[c].fillna('').astype(str) if c in df else ''
    audit['n_used'] = len(df)
    jd = np.empty(len(df)); gap = rep = 0
    for tz, idx in df.groupby('tz').groups.items():
        r = df.index.get_indexer(idx)
        j, a, b = local_to_jd(df.date.values[r], df.minute.values[r], tz)
        jd[r] = j; gap += a; rep += b
    audit['nonexistent_local_times'] = gap; audit['repeated_local_times'] = rep
    F = features(jd, df.latitude.values, df.longitude.values)
    w = np.ones(len(df))
    out = {'audit': audit, 'rungs': {'B4_real': accumulate({}, F, w)}, 'groups': {}}
    groups = {'vaginal': df.PARTO.values == '1', 'caesarean': df.PARTO.values == '2',
              'caesarean_before_labour': df.STCESPARTO.values == '1',
              'spontaneous_vaginal': (df.PARTO.values == '1') & (df.STTRABPART.values == '2'),
              'induced': df.STTRABPART.values == '1'}
    for g, m in groups.items():
        if m.sum():
            out['groups'][g] = accumulate({}, {k: v[m] for k, v in F.items()}, w[m])
    audit['shares'] = {g: float(m.mean()) for g, m in groups.items()}
    audit['sttrabpart_filled'] = float(np.isin(df.STTRABPART.values, ['1', '2']).mean())
    uf = df.CODMUNNASC.str[:2].values
    st = pd.DataFrame({'uf': uf, 'day': F['sun_alt'] > 0, 'ces': groups['caesarean']}).groupby('uf').agg(
        n=('day', 'size'), day=('day', 'mean'), ces=('ces', 'mean'))
    out['by_state'] = [{'uf': k, 'n': int(r.n), 'day': float(r.day), 'ces': float(r.ces)} for k, r in st.iterrows()]
    hr = df.minute.values // 60
    out['hour_counts'] = {g: np.bincount(hr[m], minlength=24) for g, m in list(groups.items()) + [('all', np.ones(len(df), bool))]}
    ces = groups['caesarean']
    out['caesarean_daytime_share'] = float((F['sun_alt'][ces] > 0).mean()) if ces.sum() else None
    spont = groups['spontaneous_vaginal'] if groups['spontaneous_vaginal'].sum() > 10000 else groups['vaginal']
    out['spont_definition'] = 'PARTO=1 & STTRABPART=2' if spont is groups['spontaneous_vaginal'] else 'PARTO=1 (STTRABPART missing)'
    prof = np.bincount(hr[spont], minlength=24).astype(float); prof /= prof.mean()
    df['cl'] = df.latitude.round(); df['co'] = df.longitude.round()
    cells = df.groupby(['tz', 'cl', 'co']).agg(lat=('latitude', 'mean'), lon=('longitude', 'mean'), n=('date', 'size')).reset_index()
    cells['cid'] = np.arange(len(cells))
    df = df.merge(cells[['tz', 'cl', 'co', 'cid']], on=['tz', 'cl', 'co'])
    daycount = df.groupby(['cid', 'date']).size()
    dates = pd.date_range(f'{y}-01-01', f'{y}-12-31')
    steps = (np.arange(grid) + 0.5) / grid
    acc = {r: {} for r in RUNGS[:3]}
    N = len(df); ci = cells.set_index('cid')
    for month in range(1, 13):
        md = dates[dates.month == month]
        JD, LAT, LON, W1, W2, W3 = [], [], [], [], [], []
        for tz, g in cells.groupby('tz'):
            dd = np.repeat(md.values, len(g)); cid = np.tile(g.cid.values, len(md))
            a, b = day_bounds_jd(dd, tz)
            j = a[:, None] + (b - a)[:, None] * steps[None, :]
            ut = pd.to_datetime((j.ravel() - 2440587.5) * 86400, unit='s')
            local_hour = pd.DatetimeIndex(ut).tz_localize('UTC').tz_convert(tz).hour.values.reshape(j.shape)
            cnt = daycount.reindex(pd.MultiIndex.from_arrays([cid, pd.DatetimeIndex(dd)])).fillna(0).values
            pw = prof[local_hour]; pw = pw / pw.sum(1, keepdims=True)
            JD.append(j.ravel()); LAT.append(np.repeat(ci.lat.reindex(cid).values, grid)); LON.append(np.repeat(ci.lon.reindex(cid).values, grid))
            W1.append(np.repeat(ci.n.reindex(cid).values / len(dates) / grid, grid))
            W2.append(np.repeat(cnt / grid, grid)); W3.append((cnt[:, None] * pw).ravel())
        FG = features(np.concatenate(JD), np.concatenate(LAT), np.concatenate(LON))
        for r, W in zip(RUNGS[:3], (W1, W2, W3)):
            accumulate(acc[r], FG, np.concatenate(W))
    out['rungs'].update(acc)
    save_counts(f'BR_{y}', out)
    R = out['rungs']
    log(f"BR {y}: n={N:,} day charts " + ' '.join(f"{r[:2]} {R[r]['sect_day'] / R[r]['total'] * 100:.2f}" for r in RUNGS))


# ------------------------------------------------------------------ Japan
JP_DIR = DATA / 'jp'
ESTAT_SID = '0003411915'
# Prefectural offices (GSI, "都道府県の庁舎の経緯度", WGS84), prefecture codes 1–47.
JP_PREF = [(43.063968, 141.347899), (40.824623, 140.740593), (39.703531, 141.152667), (38.268839, 140.872103),
           (39.7186, 140.102334), (38.240437, 140.363634), (37.750299, 140.467521), (36.341813, 140.446793),
           (36.565725, 139.883565), (36.391208, 139.060156), (35.857428, 139.648933), (35.605058, 140.123308),
           (35.689521, 139.691704), (35.447753, 139.642514), (37.902418, 139.023221), (36.69529, 137.211338),
           (36.594682, 136.625573), (36.065219, 136.221642), (35.664158, 138.568449), (36.651289, 138.181224),
           (35.391227, 136.722291), (34.976978, 138.383054), (35.180188, 136.906565), (34.730283, 136.508591),
           (35.004531, 135.86859), (35.021004, 135.755608), (34.686297, 135.519661), (34.691279, 135.183025),
           (34.685333, 135.832744), (34.226034, 135.167506), (35.503869, 134.237672), (35.472297, 133.050499),
           (34.661772, 133.934675), (34.39656, 132.459622), (34.186121, 131.4705), (34.065761, 134.559303),
           (34.340149, 134.043444), (33.841624, 132.765681), (33.559706, 133.53108), (33.606785, 130.418314),
           (33.249367, 130.298822), (32.744839, 129.873756), (32.789828, 130.741667), (33.238194, 131.612591),
           (31.911096, 131.423855), (31.560148, 130.557981), (26.212401, 127.680932)]


def _estat_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); op.addheaders = [('User-Agent', UA)]
    op.open(f'https://www.e-stat.go.jp/dbview?sid={ESTAT_SID}').read()
    return op


def _estat_rows(op, year, month, place):
    """One view of the e-Stat table: rows = day (total + 1..31), cols = hour (total + 0..23).
    The dbview page posts its layout as gzip+base64 JSON; this replicates that request."""
    enc = lambda o: base64.b64encode(gzip.compress(json.dumps(o, ensure_ascii=False, separators=(',', ':')).encode())).decode()
    sid = ESTAT_SID
    matter = lambda mid, tbl, disp, **kw: {'matterId': mid, 'tableName': tbl, 'dispTableName': f'S9N8B_{sid}_{disp}', **kw}
    item = lambda code, name='': {'name': name, 'code': code, 'explanation': ''}
    tops = [matter(18, 'MH_HS9N8B_0000000001', 'HS', positionNum=1, allSelected=1, listData=[item('10040', '出生数')]),
            matter(6, 'MH_BU9N8B_0001059317', 'BUN04', positionNum=2, allSelected=1, listData=[item(place)]),
            matter(2, 'MH_TMY9N8B_0001006171', 'TIME', positionNum=3, allSelected=1, listData=[item(f'{year}000000')]),
            matter(5, 'MH_BU9N8B_0001059308', 'BUN03', positionNum=4, allSelected=0,
                   listData=[item('00100' if month == 0 else f'{100 + 10 * month:05d}')])]
    day = matter(4, 'MH_BU9N8B_0001059384', 'BUN02', positionNum=1, allSelected=1,
                 listData=[item('00100', '総数')] + [item(f'{100 + 10 * d:05d}', f'{d}日') for d in range(1, 32)])
    hour = matter(3, 'MH_BU9N8B_0001059348', 'BUN01', positionNum=1, allSelected=1,
                  listData=[item('00100', '総数')] + [item(f'{110 + 10 * h:05d}', f'{h}時') for h in range(24)])
    base = {'annotationFlg': 1, 'rowNoDataDispFlg': 0, 'colNoDataDispFlg': 0, 'commaType': 0, 'replaceSpChars': 0,
            'graphAxis': 'horizontal', 'graphBasis': 'head', 'graphSort': 'asc', 'graphTitle': '', 'graphType': 'barChart',
            'inputNumberOfCols': 100, 'inputNumberOfRows': 100, 'movementId': 0, 'leftMoveFlg': 0, 'rightMoveFlg': 0,
            'underMoveFlg': 0, 'upMoveFlg': 0, 'currentCols': '', 'currentRows': '', 'mode': 'table', 'layoutName': ''}
    data = dict(base, tops=enc(tops), apiTops=enc(tops), rows=enc([day]), cols=enc([hour]))
    req = urllib.request.Request(f'https://www.e-stat.go.jp/dbview/api_get_result?sid={sid}', data=urllib.parse.urlencode(data).encode(),
                                 headers={'X-Requested-With': 'XMLHttpRequest', 'Referer': f'https://www.e-stat.go.jp/dbview?sid={sid}',
                                          'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'})
    res = json.loads(op.open(req).read())
    if res.get('error'):
        raise RuntimeError(res.get('message'))
    rows = []
    for tr in re.findall(r'<tr>(.*?)</tr>', res['table'], re.S):
        cells = [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S)]
        if len(cells) >= 26:
            label = cells[-26]; vals = [int(v.replace(',', '')) if v not in ('-', '…', '') else 0 for v in cells[-25:]]
            rows.append((0 if '総数' in label else int(label.replace('日', '')), vals))
    return rows


def fetch_jp():
    JP_DIR.mkdir(parents=True, exist_ok=True)
    main = JP_DIR / 'jp_births_month_day_hour.csv'
    if not main.exists():
        op = _estat_opener(); out = []
        for y in JP_YEARS:
            for m in range(1, 13):
                for d, vals in _estat_rows(op, y, m, '000000'):
                    if d and not any(vals):
                        continue
                    out.append([y, m, d] + vals)
                time.sleep(0.7)
            log(f'JP {y} fetched')
        pd.DataFrame(out, columns=['year', 'month', 'day', 'total'] + [f'h{h:02d}' for h in range(24)]).to_csv(main, index=False)
    place = JP_DIR / 'jp_hour_by_place.csv'
    if not place.exists():
        op = _estat_opener(); out = []
        for y in JP_YEARS:
            for p in ('001100', '001200', '001400', '002100', '002200'):
                rows = [v for d, v in _estat_rows(op, y, 0, p) if d == 0]
                if rows:
                    out.append([y, p] + rows[0])
                time.sleep(0.5)
        pd.DataFrame(out, columns=['year', 'place', 'total'] + [f'h{h:02d}' for h in range(24)]).to_csv(place, index=False)
    pref = JP_DIR / 'pref_month_2023.csv'
    if not pref.exists():
        curl_resume('https://www.e-stat.go.jp/stat-search/file-download?statInfId=000040207154&fileKind=1', pref)


def compute_jp(sub=12):
    d = pd.read_csv(JP_DIR / 'jp_births_month_day_hour.csv'); d = d[d.day > 0]
    place = pd.read_csv(JP_DIR / 'jp_hour_by_place.csv', dtype={'place': str})
    raw = pd.read_csv(JP_DIR / 'pref_month_2023.csv', encoding='shift_jis', header=None, skiprows=7)
    w = raw[raw[0].astype(str).str.match(r'^\d\d ')][[0, 1]].copy()
    w['id'] = w[0].str[:2].astype(int); w['n'] = w[1].astype(float)
    w = w[w.id <= 47].sort_values('id')   # codes 50+ repeat designated cities
    assert list(w.id) == list(range(1, 48))
    share = (w.n / w.n.sum()).values
    plat = np.array([p[0] for p in JP_PREF]); plon = np.array([p[1] for p in JP_PREF])
    hc = [f'h{h:02d}' for h in range(24)]
    nat = place[place.place.isin(['001400', '002100'])][hc].sum().values.astype(float); natp = nat / nat.sum()
    steps = (np.arange(sub) + 0.5) / sub
    swe = swe_mod()
    for y in JP_YEARS:
        yy = d[d.year == y].sort_values(['month', 'day'])
        counts = yy[hc].values.astype(float)
        jd_day = np.array([swe.julday(int(a), int(b), int(c), 0.0) for a, b, c in zip(yy.year, yy.month, yy.day)])
        nd = len(jd_day)
        local_h = (np.arange(24)[:, None] + steps[None, :]).ravel()
        jd = (jd_day[:, None, None] + local_h[None, :, None] / 24 - 9 / 24) + np.zeros((1, 1, 47))
        F = features(jd.ravel(), np.broadcast_to(plat, jd.shape).ravel(), np.broadcast_to(plon, jd.shape).ravel())
        tot = counts.sum(); day_tot = counts.sum(1); hi = np.repeat(np.arange(24), sub)
        W = {'B1_period_astronomy': np.full((nd, 24 * sub), tot / nd / (24 * sub)),
             'B2_real_dates': np.repeat(day_tot[:, None] / (24 * sub), 24 * sub, 1),
             'B3_spontaneous_profile': day_tot[:, None] * natp[hi][None, :] / sub,
             'B4_real': counts[:, hi] / sub}
        yp = place[place.year == y]
        out = {'audit': {'year': y, 'n_hour_known': float(tot), 'n_table_total': float(yy.total.sum()),
                         'natural_births_pooled': float(nat.sum())},
               'rungs': {k: accumulate({}, F, (v[:, :, None] * share[None, None, :]).ravel()) for k, v in W.items()},
               'hour_counts': {'all': counts.sum(0), 'hospital': yp[yp.place == '001100'][hc].values.sum(0),
                               'clinic': yp[yp.place == '001200'][hc].values.sum(0),
                               'midwife_home_and_home': yp[yp.place.isin(['001400', '002100'])][hc].values.sum(0)}}
        save_counts(f'JP_{y}', out)
        R = out['rungs']
        log(f"JP {y}: " + ' '.join(f"{r[:2]} {R[r]['sect_day'] / R[r]['total'] * 100:.2f}" for r in RUNGS))


# ------------------------------------------------------------------ USA
US_DIR = DATA / 'us'
US_FILES = {2016: 'Nat2016us.zip', 2017: 'Nat2017US.zip', 2018: 'Nat2018us.zip', 2019: 'Nat2019us.zip',
            2020: 'Nat2020us.zip', 2021: 'nat2021us.zip', 2022: 'nat2022us.zip', 2023: 'Nat2023us.zip',
            2024: 'Nat2024us.zip'}


def fetch_us(years):
    US_DIR.mkdir(parents=True, exist_ok=True)
    for y in years:
        pq = US_DIR / f'us_{y}_counts.parquet'
        if pq.exists():
            continue
        z = US_DIR / f'Nat{y}us.zip'
        curl_ranged(f'https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/natality/{US_FILES[y]}', z)
        # Positions (1-based, 2016–2024 layout): DOB_YY 9-12, DOB_MM 13-14, DOB_TT 19-22, DOB_WK 23,
        # BFACIL 32, LD_INDL 383, DMETH_REC 408. The zips use Deflate64: read with unzip.
        cnt = {}
        p = subprocess.Popen(['unzip', '-p', str(z)], stdout=subprocess.PIPE)
        for line in io.TextIOWrapper(p.stdout, encoding='latin-1'):
            k = (line[8:12], line[12:14], line[22:23], line[18:22], line[31:32], line[407:408], line[382:383])
            cnt[k] = cnt.get(k, 0) + 1
        pd.DataFrame([k + (v,) for k, v in cnt.items()], columns=['year', 'month', 'weekday', 'hhmm', 'bfacil', 'dmeth', 'induced', 'n']).to_parquet(pq)
        z.unlink(); log(f'US {y}: {sum(cnt.values()):,} records')
    co = US_DIR / 'us_counties_births_tz.csv'
    if not co.exists():
        est = US_DIR / 'co-est2024-alldata.csv'; gz = US_DIR / 'gaz_counties.zip'
        curl_resume('https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/totals/co-est2024-alldata.csv', est)
        curl_resume('https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/2024_Gaz_counties_national.zip', gz)
        subprocess.run(['unzip', '-o', '-q', str(gz), '-d', str(US_DIR)], check=True)
        from timezonefinder import TimezoneFinder
        c = pd.read_csv(est, encoding='latin-1', dtype={'STATE': str, 'COUNTY': str}); c = c[c.SUMLEV == 50].copy()
        c['GEOID'] = c.STATE + c.COUNTY
        g = pd.read_csv(US_DIR / '2024_Gaz_counties_national.txt', sep='\t', dtype={'GEOID': str}); g.columns = [x.strip() for x in g.columns]
        m = c.merge(g[['GEOID', 'INTPTLAT', 'INTPTLONG']], on='GEOID')
        tf = TimezoneFinder(); m['tz'] = [tf.timezone_at(lng=lo, lat=la) for la, lo in zip(m.INTPTLAT, m.INTPTLONG)]
        m[['GEOID', 'STNAME', 'CTYNAME', 'INTPTLAT', 'INTPTLONG', 'tz'] + [f'BIRTHS{k}' for k in range(2020, 2025)]].to_csv(co, index=False)


def dates_by_month_weekday(year):
    out = {}
    for m in range(1, 13):
        for d in range(1, calendar.monthrange(year, m)[1] + 1):
            out.setdefault((m, dt.date(year, m, d).isoweekday() % 7 + 1), []).append(f'{year}-{m:02d}-{d:02d}')
    return out


def impute(counts, geo, year, bin_minutes, sub=1):
    """National counts by (month, weekday 1=Sunday, clock-time bin) spread over the matching dates and
    the places of `geo` (tz, lat, lon, share). Used for the USA and for the degradation test."""
    acc = {}; days = dates_by_month_weekday(year)
    offs = (np.arange(sub) + 0.5) / sub * bin_minutes
    for m in range(1, 13):
        JD, LAT, LON, W = [], [], [], []
        cm = counts[counts.month == m]
        for (mm, wd), dd in days.items():
            if mm != m:
                continue
            c = cm[cm.weekday == wd]
            if c.empty:
                continue
            mins = (c.bin.values[:, None] * bin_minutes + offs[None, :]).ravel()
            n = np.repeat(c.n.values / len(dd) / sub, sub)
            for tz, g in geo.groupby('tz'):
                for day in dd:
                    jd, _, _ = local_to_jd(np.repeat(day, len(mins)), mins, tz)
                    JD.append(np.repeat(jd, len(g))); LAT.append(np.tile(g.lat.values, len(jd)))
                    LON.append(np.tile(g.lon.values, len(jd))); W.append((n[:, None] * g.share.values[None, :]).ravel())
        if JD:
            accumulate(acc, features(np.concatenate(JD), np.concatenate(LAT), np.concatenate(LON)), np.concatenate(W))
    return acc


def compute_us(y, bin_minutes=5):
    nb = 1440 // bin_minutes
    c = pd.read_parquet(US_DIR / f'us_{y}_counts.parquet')
    audit = {'year': y, 'n_records': int(c.n.sum()), 'time_not_stated': int(c[c.hhmm == '9999'].n.sum())}
    c = c[c.hhmm != '9999'].copy()
    c['minute'] = c.hhmm.str[:2].astype(int) * 60 + c.hhmm.str[2:].astype(int)
    bad = c.minute >= 1440; audit['time_invalid'] = int(c[bad].n.sum()); c = c[~bad]
    c['month'] = c.month.astype(int); c['weekday'] = c.weekday.astype(int); c['bin'] = c.minute // bin_minutes
    mn = c.minute % 60
    audit['minute_00_pct'] = float(c[mn == 0].n.sum() / c.n.sum() * 100)
    audit['minute_x5_pct'] = float(c[mn % 5 == 0].n.sum() / c.n.sum() * 100)
    audit['n_used'] = int(c.n.sum())
    spont = (c.dmeth == '1') & (c.induced == 'N')
    audit['shares'] = {'caesarean': float(c[c.dmeth == '2'].n.sum() / c.n.sum()), 'induced': float(c[c.induced == 'Y'].n.sum() / c.n.sum()),
                       'spontaneous': float(c[spont].n.sum() / c.n.sum()), 'hospital': float(c[c.bfacil == '1'].n.sum() / c.n.sum())}
    real = c.groupby(['month', 'weekday', 'bin']).n.sum().reset_index()
    mw = c.groupby(['month', 'weekday']).n.sum().reset_index()
    prof = c[spont].groupby('bin').n.sum().reindex(range(nb), fill_value=0).values.astype(float); prof /= prof.sum()
    b2 = mw.merge(pd.DataFrame({'bin': range(nb)}), how='cross'); b2['n'] = b2.n / nb
    b3 = mw.merge(pd.DataFrame({'bin': range(nb), 'p': prof}), how='cross'); b3['n'] = b3.n * b3.p
    k = {}
    for (m, wd), dd in dates_by_month_weekday(y).items():
        k[(m, wd)] = len(dd)
    nd = sum(k.values()); tot = c.n.sum()
    b1 = pd.DataFrame([(m, wd, tot * v / nd) for (m, wd), v in k.items()], columns=['month', 'weekday', 'n'])
    b1 = b1.merge(pd.DataFrame({'bin': range(nb)}), how='cross'); b1['n'] = b1.n / nb
    co = pd.read_csv(US_DIR / 'us_counties_births_tz.csv', dtype={'GEOID': str})
    col = f'BIRTHS{min(max(y, 2021), 2024)}'
    co['w'] = co[col].clip(lower=0); co = co[co.w > 0]
    co['cl'] = co.INTPTLAT.round(); co['cn'] = co.INTPTLONG.round()
    geo = co.groupby(['tz', 'cl', 'cn']).apply(lambda d: pd.Series({'lat': np.average(d.INTPTLAT, weights=d.w), 'lon': np.average(d.INTPTLONG, weights=d.w), 'n': d.w.sum()}), include_groups=False).reset_index()
    geo['share'] = geo.n / geo.n.sum(); audit['geo_weights'] = f'Census county {col}'; audit['geo_cells'] = len(geo)
    hour = lambda mask: c[mask].groupby(c[mask].minute // 60).n.sum().reindex(range(24), fill_value=0).values
    out = {'audit': audit, 'rungs': {},
           'hour_counts': {'all': hour(np.ones(len(c), bool)), 'spontaneous_vaginal': hour(spont.values),
                           'caesarean': hour((c.dmeth == '2').values), 'induced': hour((c.induced == 'Y').values)}}
    for name, tab in (('B4_real', real), ('B1_period_astronomy', b1), ('B2_real_dates', b2), ('B3_spontaneous_profile', b3)):
        out['rungs'][name] = impute(tab[['month', 'weekday', 'bin', 'n']], geo, y, bin_minutes)
    save_counts(f'US_{y}', out)
    R = out['rungs']
    log(f"US {y}: " + ' '.join(f"{r[:2]} {R[r]['sect_day'] / R[r]['total'] * 100:.2f}" for r in RUNGS))


def degrade(y, bin_minutes=10):
    """Remove from Brazil exactly what the US file lacks (day of month, place, exact minute), impute
    US-style, and store it next to the full per-birth answer."""
    df = pd.read_parquet(BR_DIR / f'sinasc_{y}.parquet', columns=['DTNASC', 'HORANASC', 'CODMUNNASC'])
    h = df.HORANASC.fillna('').str.strip(); df = df[h.str.fullmatch(r'([01]\d|2[0-3])[0-5]\d')]
    mun = pd.read_csv(BR_DIR / 'municipios_tz.csv', dtype={'cod6': str})
    df = df.merge(mun[['cod6', 'latitude', 'longitude', 'tz']], left_on='CODMUNNASC', right_on='cod6')
    df['date'] = pd.to_datetime(df.DTNASC, format='%d%m%Y', errors='coerce'); df = df[df.date.dt.year == y]
    df['month'] = df.date.dt.month; df['weekday'] = (df.date.dt.dayofweek + 1) % 7 + 1
    df['bin'] = (df.HORANASC.str[:2].astype(int) * 60 + df.HORANASC.str[2:].astype(int)) // bin_minutes
    counts = df.groupby(['month', 'weekday', 'bin']).size().rename('n').reset_index()
    df['cl'] = df.latitude.round(); df['cn'] = df.longitude.round()
    geo = df.groupby(['tz', 'cl', 'cn']).agg(lat=('latitude', 'mean'), lon=('longitude', 'mean'), n=('date', 'size')).reset_index()
    geo['share'] = geo.n / geo.n.sum()
    imputed = impute(counts, geo, y, bin_minutes, sub=2)
    save_counts(f'DEGRADE_BR_{y}', {'imputed': imputed, 'full': load_counts(f'BR_{y}')['rungs']['B4_real']})
    log(f'degradation test BR {y} stored')


# ------------------------------------------------------------------ Mars mechanism
def mars_model():
    """Planet diurnal sector ≈ Sun's sector shifted by (RA_sun − RA_planet)/10°. Convolving the Sun's
    real and date-only sector distributions with the long-run offset distribution (1900–2099) predicts
    the pooled key-sector excess; the per-year version is checked against the full computation."""
    swe = swe_mod()
    def ra(j, b):
        return swe.calc_ut(j, b, swe.FLG_SWIEPH | swe.FLG_EQUATORIAL)[0][0]
    def offsets(y0, y1, b, step):
        js = np.arange(swe.julday(y0, 1, 1, 12), swe.julday(y1 + 1, 1, 1, 12), step)
        return np.array([((ra(j, swe.SUN) - ra(j, b) + 180) % 360 - 180) / 10.0 for j in js])
    def kernel(off):
        K = np.zeros(36); lo = np.floor(off).astype(int); fr = off - lo
        np.add.at(K, lo % 36, 1 - fr); np.add.at(K, (lo + 1) % 36, fr); return K / K.sum()
    def conv(s, K):
        return sum(K[d] * np.roll(s, d) for d in range(36))
    key = lambda v: float(v[KEY_SECTORS].sum())
    long_mars = offsets(1900, 2099, swe.MARS, 2.0)
    out = {'mars_within_60deg_of_sun_pct': float(np.mean(np.abs(long_mars) < 6) * 100),
           'uniform_within_60deg_pct': 100 / 3,
           'jupiter_within_60deg_pct': float(np.mean(np.abs(offsets(1900, 2099, swe.JUPITER, 2.0)) < 6) * 100),
           'saturn_within_60deg_pct': float(np.mean(np.abs(offsets(1900, 2099, swe.SATURN, 2.0)) < 6) * 100),
           'countries': {}}
    Kl = kernel(long_mars)
    for c, years in (('BR', BR_YEARS), ('JP', JP_YEARS), ('US', US_YEARS)):
        s2 = pooled_pct(c, years, 'sun_gq', 'B2_real_dates'); s4 = pooled_pct(c, years, 'sun_gq', 'B4_real')
        per_year = []
        for y in years:
            R = load_counts(f'{c}_{y}')['rungs']; Ky = kernel(offsets(y, y, swe.MARS, 1.0))
            p = lambda r, k: np.asarray(R[r][k]) / R[r]['total'] * 100
            per_year.append((key(conv(p('B4_real', 'sun_gq'), Ky)) - key(conv(p('B2_real_dates', 'sun_gq'), Ky)),
                             key(p('B4_real', 'mars_gq')) - key(p('B2_real_dates', 'mars_gq'))))
        per_year = np.array(per_year)
        out['countries'][c] = {'predicted_long_run_excess_pp': key(conv(s4, Kl)) - key(conv(s2, Kl)),
                               'per_year_corr_model_vs_computed': float(np.corrcoef(per_year[:, 0], per_year[:, 1])[0, 1])}
    (COUNTS / 'MARS_MODEL.json').write_text(json.dumps(out))
    log(json.dumps(out, indent=1))


# ------------------------------------------------------------------ export
def pooled_pct(c, years, feature, rung):
    acc = None; tot = 0.0
    for y in years:
        R = load_counts(f'{c}_{y}')['rungs'][rung]
        v = np.asarray(R[feature], float); acc = v if acc is None else acc + v; tot += R['total']
    return acc / tot * 100


def pct(R, k):
    return np.asarray(R[k], float) / R['total'] * 100


def r2(x, n=3):
    # Three decimals: shares are shown with one, and two-decimal storage double-rounds
    # (63.646 -> 63.65 -> '63.7' in Intl.NumberFormat).
    if isinstance(x, (list, np.ndarray)):
        return [round(float(v), n) for v in x]
    return round(float(x), n)


def export():
    years = {'BR': BR_YEARS, 'JP': JP_YEARS, 'US': US_YEARS}
    counts = {(c, y): load_counts(f'{c}_{y}') for c, ys in years.items() for y in ys}
    rows = []
    feats = list(CAT) + ['sun_asc']
    def emit(country, scope, year, rung, R):
        tot = R['total']
        for k in SCALARS:
            rows.append([country, scope, year, rung, k, 'yes', r2(R[k] / tot * 100, 4), r2(R[k], 1)])
        for k in feats:
            v = np.asarray(R[k], float)
            for i, x in enumerate(v):
                if k == 'sun_asc':
                    cat = f'{SIGNS[i // 12]}|{SIGNS[i % 12]}'
                elif k.endswith(('_sign', '_sign_sid')):
                    cat = SIGNS[i]
                else:
                    cat = str(i + 1)
                rows.append([country, scope, year, rung, k, cat, r2(x / tot * 100, 4), r2(x, 1)])
    for (c, y), obj in sorted(counts.items()):
        for r in RUNGS:
            emit(c, 'national', y, r, obj['rungs'][r])
        for g, v in obj['hour_counts'].items():
            v = np.asarray(v, float)
            if v.sum() > 0:
                for h, x in enumerate(v):
                    rows.append([c, 'national', y, 'B4_real', f'birth_hour_{g}', str(h), r2(x / v.sum() * 100, 4), r2(x, 1)])
        if c == 'BR':
            for s in obj['by_state']:
                rows.append([c, f"UF{s['uf']}", y, 'B4_real', 'sect_day', 'yes', r2(s['day'] * 100, 4), s['n']])
                rows.append([c, f"UF{s['uf']}", y, 'B4_real', 'caesarean_share', 'yes', r2(s['ces'] * 100, 4), s['n']])
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(CSV_OUT, 'w', newline='') as fh:
        w = csv.writer(fh)
        w.writerow(['country', 'scope', 'year', 'rung', 'feature', 'category', 'share_pct', 'weighted_births'])
        w.writerows(rows)

    # ---- page data
    series = []
    for (c, y), obj in sorted(counts.items()):
        R = obj['rungs']; a = obj['audit']
        top = int(np.argmax(pct(R['B4_real'], 'sun_house')))
        row = {'country': c, 'year': y, 'births': round(R['B4_real']['total']),
               'day': {r[:2]: r2(pct(R[r], 'sect_day')) for r in RUNGS},
               'day_whole_B4': r2(pct(R['B4_real'], 'sect_day_whole')),
               'smv_upper': {'B2': r2(pct(R['B2_real_dates'], 'smv_all_upper')), 'B4': r2(pct(R['B4_real'], 'smv_all_upper'))},
               'sun_house_B4': r2(pct(R['B4_real'], 'sun_house')), 'sun_house_B2': r2(pct(R['B2_real_dates'], 'sun_house')),
               'sun_top_house': top + 1,
               'sun_top_ratio': r2(pct(R['B4_real'], 'sun_house')[top] / pct(R['B2_real_dates'], 'sun_house')[top]),
               'mars_key': {r[:2]: r2(pct(R[r], 'mars_gq')[KEY_SECTORS].sum()) for r in RUNGS},
               'asc_max_diff_pp': r2(np.abs(pct(R['B4_real'], 'asc_sign') - pct(R['B2_real_dates'], 'asc_sign')).max(), 3),
               'moon_max_diff_pp': r2(np.abs(pct(R['B4_real'], 'moon_sign') - pct(R['B2_real_dates'], 'moon_sign')).max(), 3)}
        if c == 'BR':
            G = obj['groups']
            row.update(day_vaginal=r2(pct(G['vaginal'], 'sect_day')), day_caesarean=r2(pct(G['caesarean'], 'sect_day')))
            row.update(caesarean=r2(a['shares']['caesarean'] * 100), time_valid=r2(a['time_valid'] / a['n_records'] * 100),
                       minute_00=r2(a['minute_00_pct']), caesarean_daytime=r2(obj['caesarean_daytime_share'] * 100),
                       spont_defined=bool(a['sttrabpart_filled'] > 0.9), gap=a['nonexistent_local_times'], repeated=a['repeated_local_times'])
        if c == 'US':
            hc = obj['hour_counts']
            row['share_8_to_18'] = {g: r2(np.asarray(hc[g], float)[8:18].sum() / np.asarray(hc[g], float).sum() * 100)
                                    for g in ('all', 'spontaneous_vaginal', 'caesarean', 'induced')}
            row.update(caesarean=r2(a['shares']['caesarean'] * 100), induced=r2(a['shares']['induced'] * 100),
                       time_not_stated=a['time_not_stated'], minute_00=r2(a['minute_00_pct']))
        series.append(row)
    states = [{'year': y, 'uf': s['uf'], 'n': s['n'], 'day': r2(s['day'] * 100), 'ces': r2(s['ces'] * 100)}
              for (c, y), o in sorted(counts.items()) if c == 'BR' for s in o['by_state']]
    st = pd.DataFrame(states)
    pooled = {}
    for c, ys in years.items():
        P = {r: {k: pooled_pct(c, ys, k, r) for k in ('sun_house', 'mercury_house', 'venus_house', 'mars_house', 'jupiter_house',
                                                      'saturn_house', 'moon_house', 'asc_sign', 'moon_sign', 'sun_sign', 'sun_asc', 'mars_gq', 'sun_gq')}
             for r in ('B1_period_astronomy', 'B2_real_dates', 'B4_real')}
        per10k = P['B4_real']['sun_asc'] * 100
        pooled[c] = {
            'years': [ys[0], ys[-1]], 'births': round(sum(counts[(c, y)]['rungs']['B4_real']['total'] for y in ys)),
            'house_ratio': {b: r2(P['B4_real'][f'{b}_house'] / P['B2_real_dates'][f'{b}_house']) for b in ('sun', 'mercury', 'venus', 'moon', 'mars', 'jupiter', 'saturn')},
            'sun_house_B4': r2(P['B4_real']['sun_house']),
            'asc_sign': {'B4': r2(P['B4_real']['asc_sign']), 'B2': r2(P['B2_real_dates']['asc_sign']), 'B1': r2(P['B1_period_astronomy']['asc_sign'])},
            'moon_sign_B4': r2(P['B4_real']['moon_sign'], 3), 'sun_sign': {'B4': r2(P['B4_real']['sun_sign']), 'B1': r2(P['B1_period_astronomy']['sun_sign'])},
            'sun_asc_per10k': r2(per10k, 1), 'sun_asc_B2_per10k': r2(P['B2_real_dates']['sun_asc'] * 100, 1), 'sun_asc_ratio': r2(P['B4_real']['sun_asc'] / P['B2_real_dates']['sun_asc']),
            'mars_key': {'B4': r2(P['B4_real']['mars_gq'][KEY_SECTORS].sum()), 'B2': r2(P['B2_real_dates']['mars_gq'][KEY_SECTORS].sum())},
        }
    hours = {}
    for c, ys in years.items():
        H = {}
        for y in ys:
            for g, v in counts[(c, y)]['hour_counts'].items():
                H[g] = H.get(g, 0) + np.asarray(v, float)
        hours[c] = {g: r2(v / v.sum() * 100) for g, v in H.items() if v.sum() > 0}
    deg = {}
    for y in (2018, 2024):
        try:
            D = load_counts(f'DEGRADE_BR_{y}')
        except FileNotFoundError:
            continue
        f, i = D['full'], D['imputed']
        def err(k):
            a, b = pct(f, k), pct(i, k)
            return r2(np.abs(a - b).max(), 3)
        def rel(k):
            a, b = pct(f, k), pct(i, k)
            return r2(np.nanmax(np.abs(b / np.where(a > 0, a, np.nan) - 1)) * 100, 1)
        deg[str(y)] = {'sect_pp': r2(abs(pct(f, 'sect_day') - pct(i, 'sect_day')), 3), 'sun_house_pp': err('sun_house'),
                       'mars_house_pp': err('mars_house'), 'moon_sign_pp': err('moon_sign'), 'asc_sign_pp': err('asc_sign'),
                       'sun_asc_rel_pct': rel('sun_asc'), 'smv_upper_pp': r2(abs(pct(f, 'smv_all_upper') - pct(i, 'smv_all_upper')), 3)}
    # Brazil first vs last year: how much of the rise in day charts is the larger caesarean share
    # (composition) and how much is each delivery type moving into the day (shift-share, midpoint weights).
    b0, b1 = (next(r for r in series if r['country'] == 'BR' and r['year'] == y) for y in (BR_YEARS[0], BR_YEARS[-1]))
    c0, c1 = b0['caesarean'] / 100, b1['caesarean'] / 100
    comp = (c1 - c0) * ((b0['day_caesarean'] - b0['day_vaginal']) + (b1['day_caesarean'] - b1['day_vaginal'])) / 2
    within = ((c0 + c1) / 2) * (b1['day_caesarean'] - b0['day_caesarean']) + (1 - (c0 + c1) / 2) * (b1['day_vaginal'] - b0['day_vaginal'])
    cm = (c0 + c1) / 2
    within_c = cm * (b1['day_caesarean'] - b0['day_caesarean'])
    within_v = (1 - cm) * (b1['day_vaginal'] - b0['day_vaginal'])
    total = b1['day']['B4'] - b0['day']['B4']
    # The share depends on the weights: holding first-year or last-year day shares fixed instead.
    comp_first = (c1 - c0) * (b0['day_caesarean'] - b0['day_vaginal'])
    comp_last = (c1 - c0) * (b1['day_caesarean'] - b1['day_vaginal'])
    br_decomposition = {'from': BR_YEARS[0], 'to': BR_YEARS[-1], 'day_change_pp': r2(total),
                        'composition_pp': r2(comp), 'within_types_pp': r2(within),
                        'within_caesarean_pp': r2(within_c), 'within_vaginal_pp': r2(within_v),
                        'composition_share_pct': r2(comp / (comp + within) * 100, 1),
                        'composition_share_first_year_weights_pct': r2(comp_first / total * 100, 1),
                        'composition_share_last_year_weights_pct': r2(comp_last / total * 100, 1)}
    mars = json.loads((COUNTS / 'MARS_MODEL.json').read_text()) if (COUNTS / 'MARS_MODEL.json').exists() else None
    corr = float(st[['day', 'ces']].corr().iloc[0, 1])
    data = {
        'generated_by': 'scripts/research/birth_sky.py', 'signs': SIGNS, 'rungs': RUNGS,
        'selftest': selftest(2000),
        'totals': {c: {'years': [ys[0], ys[-1]], 'births': pooled[c]['births']} for c, ys in years.items()},
        'total_births': sum(pooled[c]['births'] for c in years),
        'series': series, 'br_decomposition': br_decomposition, 'br_states': {'points': len(st), 'corr_day_caesarean': r2(corr, 3), 'rows': states},
        'pooled': pooled, 'hour_profiles_pct': hours, 'degradation_test': deg, 'mars_model': mars,
        'csv_rows': len(rows),
    }
    # Pages «planet in house» (natal SEO leaves) read their OWN small file: kept out of the
    # study JSON so that neither the articles' lastmod nor their bundle moves with it.
    house_frequency = {
        c: {'years': [ys[0], ys[-1]],
            'bodies': {b: {'real': r2(pooled_pct(c, ys, f'{b}_house', 'B4_real')),
                           'even': r2(pooled_pct(c, ys, f'{b}_house', 'B2_real_dates'))}
                       for b in ('sun', 'moon', 'mercury', 'venus', 'mars', 'jupiter', 'saturn')}}
        for c, ys in years.items()}
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    if HOUSE_JSON_OUT is not None:
        HOUSE_JSON_OUT.write_text(json.dumps(house_frequency, ensure_ascii=False, separators=(',', ':')) + '\n')
    JSON_OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + '\n')
    if FACTS_OUT is not None:
        write_backend_facts(counts, years, pooled)
    if SCRIPT_COPY is not None:
        SCRIPT_COPY.write_bytes(Path(__file__).read_bytes())
    log(f'wrote {JSON_OUT} and {CSV_OUT} ({len(rows):,} rows)')


def write_backend_facts(counts, years, pooled):
    """Compact facts for backend/app/services/birth_timing.py (AI astrologer, natal hint).

    Per country-year: day-chart share (real, even times) and the Sun's house shares in both
    house systems the product offers (Placidus, whole sign); pooled Sun–Ascendant pairs per
    10,000; tropical rising-sign shares by integer latitude from the rising-sign study
    (astronomy: over a full year the hour of birth barely moves them — shown in this study).
    """
    per_year = {}
    for (c, y), obj in sorted(counts.items()):
        R = obj['rungs']
        per_year.setdefault(c, {})[str(y)] = {
            'day': r2(pct(R['B4_real'], 'sect_day')), 'day_even': r2(pct(R['B2_real_dates'], 'sect_day')),
            'sun_house': r2(pct(R['B4_real'], 'sun_house')), 'sun_house_even': r2(pct(R['B2_real_dates'], 'sun_house')),
            'sun_whole': r2(pct(R['B4_real'], 'sun_whole')), 'sun_whole_even': r2(pct(R['B2_real_dates'], 'sun_whole')),
        }
    rising = json.loads(RISING_JSON.read_text())
    facts = {
        'generated_by': 'scripts/research/birth_sky.py export',
        'research_path': '/research/' + SLUG,
        'coverage': {c: [ys[0], ys[-1]] for c, ys in years.items()},
        'per_year': per_year,
        'sun_asc_per10k': {c: {'real': pooled[c]['sun_asc_per10k'], 'even': pooled[c]['sun_asc_B2_per10k']} for c in years},
        'rising_by_latitude': {'latitudes': [row['latitude'] for row in rising['latitudes']],
                               'tropical': [row['tropical']['shares'] for row in rising['latitudes']]},
    }
    FACTS_OUT.parent.mkdir(parents=True, exist_ok=True)
    FACTS_OUT.write_text(json.dumps(facts, ensure_ascii=False, separators=(',', ':')) + '\n')
    log(f'wrote {FACTS_OUT} ({FACTS_OUT.stat().st_size:,} bytes)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=['fetch', 'fetch-br', 'fetch-jp', 'fetch-us', 'compute', 'compute-br', 'compute-jp',
                                     'compute-us', 'degrade', 'mars-model', 'export', 'selftest'])
    ap.add_argument('years', nargs='*', type=int)
    a = ap.parse_args()
    ys = lambda default: a.years or default
    if a.step in ('fetch', 'fetch-br'): fetch_br(ys(BR_YEARS))
    if a.step in ('fetch', 'fetch-jp'): fetch_jp()
    if a.step in ('fetch', 'fetch-us'): fetch_us(ys(US_YEARS))
    if a.step in ('compute', 'compute-br'):
        for y in ys(BR_YEARS): compute_br(y)
    if a.step in ('compute', 'compute-jp'): compute_jp()
    if a.step in ('compute', 'compute-us'):
        for y in ys(US_YEARS): compute_us(y)
    if a.step in ('compute', 'degrade'):
        for y in ys([2018, 2024]): degrade(y)
    if a.step in ('compute', 'mars-model'): mars_model()
    if a.step == 'export': export()
    if a.step == 'selftest': log(selftest())
    return 0


if __name__ == '__main__':
    sys.exit(main())
