#!/usr/bin/env python3
"""When does the Sun really come back to where it was when you were born? Solar returns against birthdays.

Source of the numbers on https://startarot.online/research/solar-return-before-birthday

A solar return is the instant the Sun gets back to the ecliptic longitude it had at birth (tropical
zodiac, apparent position, Swiss Ephemeris). The page compares the local calendar date of that instant
with the birthday. From 1901 to 2099 every fourth year is a leap year with no exception (2000 was a leap
year), so the calendar runs on a 365.25-day year while the tropical year is about 11 minutes shorter:
the return drifts earlier against the clock year after year, with a four-year leap saw on top, until
2100 skips its leap day.

Hypotheses: HYPOTHESES below were committed BEFORE the full count (ccc676479); the code that follows
came in a later commit and does not edit them (validate checks their SHA-256). A pilot on a 10 % sample
of Brazilian births and a uniform-time model for one time zone ran during topic selection (2026-11-04)
and was seen before these lines were written: the hypotheses are fixed before the full count, not
before any look at the data. Anything thought of after the count goes to ADDED_AFTER_COUNT, marked.

How to run
----------
Needs Python 3.10+ with ``pip install numpy pandas pyarrow pyswisseph`` (tested: Python 3.13, numpy 2.5,
pandas 3.0, pyswisseph 2.10) and curl. The raw birth files are the ones birth_sky.py downloads (that
script lies next to this one, on the site too: /research/birth_sky.py) in $BIRTH_SKY_DATA (default
~/startarot-data/birth-sky when it exists, else ./birth-sky-data); this script's own raw and
intermediate files go to $COSMIC_BIRTHDAY_DATA (default ~/startarot-data/cosmic-birthday when it
exists, else ./cosmic-birthday-data). Steps, in order:

    python3 cosmic_birthday.py fetch      # UN WPP 2024 single ages (67 MB gz, filtered to 2027/2028), VSOP87D
                                          # Earth; births via birth_sky.py fetch-* if their files are missing
    python3 cosmic_birthday.py compute    # everything -> $COSMIC_BIRTHDAY_DATA/_work/*.json (~12 min on an M-series Mac)
    python3 cosmic_birthday.py validate   # named checks -> _work/validation.json
    python3 cosmic_birthday.py export     # page JSON + long CSV (+ a copy of this script); refuses unless
                                          # validate passed
Parts of compute run alone: compute-br | compute-jp | compute-us | compute-model | compute-misc (the
model needs the spontaneous profile from compute-br). Heavy steps run one at a time in one process; Brazil
is read year by year (peak RSS 1.0 GB). Measured: Brazil 4.5 min, Japan 0.5 min, USA 5 min, model 1.3 min, rest < 1 min.

Run from the repo, export writes (GENERATED: regenerate, do not hand-edit):
    frontend/src/lib/research/solar-return-before-birthday.json   data the page renders
    frontend/static/research/solar-return-before-birthday.csv     the open dataset (long format)
    frontend/static/research/cosmic_birthday.py                   a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

Method
------
Sun: apparent geocentric tropical longitude from Swiss Ephemeris (files sepl_18/semo_18, flag
SEFLG_SWIEPH). The site's return charts use JPL DE440 through libephemeris (kerykeion's
PlanetaryReturnFactory; solar_return_moment in backend/app/services/lifecycle_email_content.py goes through
the same backend); it agrees with Swiss Ephemeris to 0.2 arcsec (checked 2026-11-04 at 40 dates 1900-2100). Sidereal: the same call with SEFLG_SIDEREAL, ayanamsa SE_SIDM_LAHIRI. Both are
tabulated every 6 hours UT from 1899-12-01 to 2111-02-01 with the daily motion, unwrapped into a
monotone cumulative longitude, and read with cubic Hermite interpolation; the return is the inverse of
that curve (Newton inside the bracketing 6-hour step). validate compares 3000 random returns with
direct root finding on swe.calc_ut (limit 2 s of time; measured max 0.017 s).
Birth instant T0 (UT) in zone Z; natal longitude L0 = longitude at T0. Return in year Y: the instant
T_Y with longitude L0 (mod 360) nearest to Y-MM-DD 12:00 UT, MM-DD the local birthday (29 February ->
1 March anchor; these births are reported apart and left out of every share). Outcome in year Y: local
date of T_Y in zone Z (tz database rules of year Y) minus the birthday date in year Y: -2, -1, 0, +1,
+2. Clock shift: local clock time of T_Y minus local clock time of birth on the birthday date, minutes,
unwrapped across midnight (shift < -(minutes after midnight at birth) <=> day before). The UT shift is
the same without the change of UTC offset between birth and return (no DST effect).
Populations:
  * Real births at their recorded times (birth_sky.py's readers and rules): Brazil SINASC 2006-2024,
    recorded minute, IANA zone of the municipality of occurrence, local time -> UT with the tz database
    (DST until 2019; nonexistent times +1 h, repeated times first occurrence); Japan 2015-2024, births
    by date and hour, spread uniformly within the hour (minute centres), JST; USA 2016-2024, DOB_TT
    minute, month and weekday only: each (month, weekday, minute) count is spread equally over the
    matching dates, and over IANA zones by Census county births (co-est2024, year clamped to
    2021-2024) -- zones with identical UTC-offset history over the years used are merged (CHOICE: the
    per-county zone weights of birth_sky.py, aggregated to zones; no place is used beyond the zone).
  * Model: every calendar day of birth years 1901-2027 equally, birth time uniform over the local day,
    zone-free (no DST; the local clock is UT + a constant, which leaves the outcome unchanged to
    0.1 min). Within each hour the outcome is integrated exactly (the shift varies by < 0.01 min within
    an hour). Second time profile: the local-hour profile of spontaneous-onset births in Brazil
    (SINASC PARTO=1 & STTRABPART=2, all years pooled, = birth_sky.py rung B3), uniform within the hour.
  * Age-weighted: UN World Population Prospects 2024, Medium variant, population by single age on
    1 July 2027 and 2028 (thousands). Age a on 1 July of Y -> birth years Y-1-a and Y-a, half each;
    100+ -> the four birth years Y-103..Y-100 equally; people born in Y itself have no return in Y and
    are left out (the model therefore runs to birth year 2027). Countries = LocTypeName "Country/Area";
    aggregates = "World", "Geographic region" and "Subregion".
Moving: the same return instant read in a zone shifted by -12..+12 h from the birth zone (the birthday
stays the calendar date).

Sources and licences
--------------------
SINASC (Ministerio da Saude / DATASUS), CC BY-ND 3.0: aggregates only, with attribution. Japan Vital
Statistics (e-Stat table 0003411915), Government of Japan Standard Terms of Use (CC BY 4.0 compatible).
NCHS Natality public-use files 2016-2024 and Census county estimates: U.S. government works. UN DESA
Population Division, World Population Prospects 2024, CC BY 3.0 IGO. Swiss Ephemeris (Astrodienst),
AGPL / professional licence. VSOP87D (Bretagnon & Francou 1988, CDS VI/81) for the browser
calculator's truncated series. Our derived numbers: CC BY 4.0.

Limits
------
* Return instants after 2025 rest on Swiss Ephemeris' extrapolated Delta T (68.8 s in 2028, 93 s in
  2100); an error of a minute in Delta T moves the shares by about 0.07 percentage points.
* Birth times are recorded clock times (Brazil and the USA round to 5 and 0 minutes often); Japan and
  the US day of month are imputed; the model has no seasonality of births and no DST.
* The tz database is assumed to hold for return years (no future DST change); Brazil's zones have no
  DST from 2019, US zones keep theirs.
"""
from __future__ import annotations

# Fixed before the full count (commit of 2026-11-04). The page prints the outcome of each, misses too.
HYPOTHESES = {
    'H1': 'For births from 1901 to 2025 and return years up to 2099, the solar return moves earlier against '
          'the birth clock time by 11.2 +- 0.5 minutes per year on average over four-year cycles.',
    'H2': 'Among Brazilian births of 2006-2024 at their recorded minute, the share of solar returns on the day '
          'before the birthday is higher in 2028 than in each of 2026, 2027, 2029 and 2030.',
    'H3': 'Of the world population aged 18 and over in 2028 (UN WPP age structure, birth times uniform over '
          'the day), more than half have their 2028 solar return on the day before their birthday.',
    'H4': 'Of people born 1940-1959 (birth times uniform over the day), at least 5 % have their 2028 solar '
          'return two calendar days before their birthday.',
    'H5': 'In 2028, among Brazilian births of 2006-2024, the day-before share for births at 00:00-05:59 local '
          'time is at least three times the share for births at 18:00-23:59.',
    'H6': 'The 2028 day-before share for the whole population (UN WPP age structure, uniform birth times) is '
          'at least 10 percentage points higher in Japan than in Nigeria.',
    'H7': 'In the sidereal zodiac (Lahiri) the return moves LATER against the birth clock time, by 9 +- 2 '
          'minutes per year on average.',
    'H8': 'For people born 1950-2010 (birth times uniform), the solar return falls on the calendar birthday '
          'in at most 65 % of the birthdays from age 1 to age 80.',
}

# Thought of after the count: kept apart, each text starts with "[after count]".
ADDED_AFTER_COUNT: dict[str, str] = {
    'A1': '[after count] Leap-year series: with the 2028 world age structure held fixed (ages fixed, birth years shifted), '
          'the share of adults with the return on the day before their birthday is printed for every return year 2024-2036; '
          'it comes back in every leap year (2024, 2028, 2032, 2036), so 2028 is the next leap year, not a unique peak.',
    'A2': '[after count] Cohort growth: for fixed groups (born 2006-2024 and born 1960-1979; uniform dates and times) the '
          'day-before share is printed for the leap years 2028-2048, with the first leap year in which it exceeds 50 % for '
          'the 2006-2024 group.',
    'A3': '[after count] January-February against March-December birthdays: in a leap year the day-before share is high '
          'only for birthdays after 29 February; January-February birthdays peak the following year (model and Brazil).',
    'A4': '[after count] Moving: the same return instant read in a zone shifted -12..+12 h from the birth zone (birthday = the '
          'same calendar date), for Brazil, Japan and US real births and for world adults, 2027 and 2028.',
}
# Independent methodological recount (separate code: astropy/ERFA, own tz and WPP handling), read after this script's
# count: ~/startarot-data/cosmic-birthday/method/REPORT.md. Its H6 convention gives the WHOLE age-0 group (1 July 2028)
# the outcome of July-December 2027 births, i.e. infants born January-July 2028, who have no return in 2028, are counted
# as if they had one; this script leaves them out. Reproduced here with the recount's convention: 58.18 / 48.33.
# The page also prints results of the recount that this script does not compute. They are recorded below as the recount
# reported them, and the page credits the recount wherever it prints one: H1_min_per_year, the mean four-year drift
# (h1_h7.py); zone_history_at_birth (tzhist.py), each country's historical tz rules at birth (DST, war and double summer
# time, Soviet decree time, zone changes; main zones weighted) instead of a fixed offset, returns read with 2028 rules:
# change of the 2028 adult shares, percentage points (the countries not covered count as 0); cohort_2006_2024_br_hours
# (cohort.py), the fixed group born 2006-2024 with uniform dates and Brazil's 6-hour profile of all births (14.29 /
# 32.20 / 29.96 / 23.55 %) instead of uniform times: % with the return on the day before (2040 and 2044 not computed).
INDEPENDENT_RECOUNT = {'date': '2026-11-04', 'H6_pp': 9.85, 'H6_japan': 58.18, 'H6_nigeria': 48.33,
                       'H6_pp_profiles': [9.1, 11.7], 'H3_world_adults': 57.28, 'H2_brazil_2028': 39.00,
                       'H1_min_per_year': 11.23,
                       'zone_history_at_birth': {'countries': 35, 'adults_share': 0.804, 'world_day_before_pp': 0.04,
                                                 'largest': {'country': 'Kazakhstan', 'day_before_pp': 2.61,
                                                             'two_days_pp': 1.07}},
                       'cohort_2006_2024_br_hours': {2028: 38.80, 2032: 41.31, 2036: 43.56, 2048: 51.45}}
HYPOTHESES_SHA256 = '18aece17d16e09488c3efce89f27e580ee291e8c9786257ae6a0fca10fb54eb0'  # json.dumps(sort_keys)

import csv  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import os  # noqa: E402
import resource  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'solar-return-before-birthday'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{SLUG}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{SLUG}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'cosmic_birthday.py'
    BIRTH_SKY_JSON = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / 'real-births-chart-frequencies.json'
else:
    JSON_OUT = HERE / f'{SLUG}.json'
    CSV_OUT = HERE / f'{SLUG}.csv'
    SCRIPT_COPY = None
    BIRTH_SKY_JSON = HERE / 'real-births-chart-frequencies.json'
_MAC = Path.home() / 'startarot-data'
DATA = Path(os.environ.get('COSMIC_BIRTHDAY_DATA') or (_MAC / 'cosmic-birthday' if _MAC.is_dir() else HERE / 'cosmic-birthday-data'))
WORK = DATA / '_work'
if not os.environ.get('BIRTH_SKY_DATA') and (_MAC / 'birth-sky').is_dir():
    os.environ['BIRTH_SKY_DATA'] = str(_MAC / 'birth-sky')
sys.path.insert(0, str(HERE))
import birth_sky as bs  # noqa: E402  (readers of the raw birth files, ephemeris download)

T_START = time.time()
EPOCH_JD = 2440587.5                       # JD of 1970-01-01 00:00 UT; times below are UT days since then
STEP = 0.25                                # table step, days
TAB_FROM, TAB_TO = (1899, 12, 1), (2111, 2, 1)
RET_YEARS = list(range(2024, 2033)) + list(range(2097, 2103))
MODEL_YEARS = list(range(1901, 2036))      # model birth years (H1 needs 1901-, WPP ages 0-1 up to return year 2036 need -2035)
SERIES_YEARS = list(range(2024, 2037))     # world series with the 2028 age structure held fixed (after count)
COHORT_GROUPS = {'born 2006-2024': (2006, 2024), 'born 1960-1979': (1960, 1979)}   # cohort growth (after count)
OUT_MODEL_YEARS = list(range(1925, 2026))
CAT_LO, NCAT = -3, 7                       # categories -3..+3 (index = cat + 3; -3/+3 also hold anything beyond)
MOVE = list(range(-12, 13))
SID_YEARS = list(range(2026, 2031))
AREA_TYPES = ['World', 'Geographic region', 'Subregion', 'Country/Area']   # WPP LocTypeName kept
WPP_URL = ('https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/'
           'WPP2024_PopulationBySingleAgeSex_Medium_2024-2100.csv.gz')
VSOP_URLS = ['https://cdsarc.cds.unistra.fr/ftp/VI/81/VSOP87D.ear',
             'https://raw.githubusercontent.com/ctdk/vsop87/master/VSOP87D.ear']
VSOP_MIN_AMPLITUDE = 1e-7                  # radians (L) / au (R): terms kept for the browser calculator
# Births per country-year as birth_sky.py counted them (frontend/src/lib/research/real-births-chart-frequencies.json).
BIRTH_SKY_TOTALS = {
    'BR': {2006: 2935653, 2007: 2880699, 2008: 2927891, 2009: 2875150, 2010: 2856072, 2011: 2905534, 2012: 2899769,
           2013: 2898431, 2014: 2972442, 2015: 3011083, 2016: 2852578, 2017: 2919493, 2018: 2941919, 2019: 2846628,
           2020: 2727783, 2021: 2675125, 2022: 2560214, 2023: 2536204, 2024: 2388174},
    'JP': {2015: 1005721, 2016: 976895, 2017: 945645, 2018: 918177, 2019: 864997, 2020: 840684, 2021: 811455,
           2022: 770589, 2023: 727138, 2024: 686020},
    'US': {2016: 3955420, 2017: 3863987, 2018: 3801218, 2019: 3757251, 2020: 3619491, 2021: 3669596, 2022: 3675635,
           2023: 3604652, 2024: 3637770},
}
# birth_sky.py's published profile of spontaneous-onset births in Brazil (% per local hour, 2006-2024 pooled).
BIRTH_SKY_SPONT_PCT = [3.821, 3.899, 3.981, 4.157, 4.285, 4.405, 4.446, 4.718, 5.134, 5.037, 4.903, 4.679, 4.283, 4.114,
                       4.121, 4.01, 3.907, 3.784, 3.597, 3.546, 3.736, 3.743, 3.796, 3.897]


def log(*a):
    print(f'[{time.time() - T_START:7.1f}s]', *a, flush=True)


def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 1024 / 1024 if sys.platform == 'darwin' else r / 1024


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for b in iter(lambda: fh.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def save_json(name, obj):
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / name).write_text(json.dumps(obj, default=_np_default, separators=(',', ':')))


def load_json(name):
    return json.loads((WORK / name).read_text())


def _np_default(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    raise TypeError(type(o))


# ------------------------------------------------------------------ calendar (proleptic Gregorian, vectorised)
def days_from_civil(y, m, d):
    """Days since 1970-01-01 of the civil date (y, m, d) (H. Hinnant's algorithm)."""
    y = np.asarray(y, np.int64)
    m = np.asarray(m, np.int64)
    d = np.asarray(d, np.int64)
    y = y - (m <= 2)
    era = np.floor_divide(y, 400)
    yoe = y - era * 400
    doy = (153 * ((m + 9) % 12) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_from_days(z):
    z = np.asarray(z, np.int64) + 719468
    era = np.floor_divide(z, 146097)
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = np.where(mp < 10, mp + 3, mp - 9)
    return yoe + era * 400 + (m <= 2), m, d


def is_leap(y):
    return (y % 4 == 0 and y % 100 != 0) or y % 400 == 0


def anchor_day(Y, M, D):
    """Day of the anniversary in year Y (29 February -> 1 March)."""
    feb29 = (np.asarray(M) == 2) & (np.asarray(D) == 29)
    return days_from_civil(Y, np.where(feb29, 3, M), np.where(feb29, 1, D))


def local_days(ut_days, tz):
    """UT days since epoch -> local wall-clock days since epoch in IANA zone tz (tz database rules)."""
    ns = np.rint(np.asarray(ut_days, float) * 86400e9).astype('int64')
    idx = pd.DatetimeIndex(ns.view('datetime64[ns]')).tz_localize('UTC').tz_convert(tz).tz_localize(None)
    loc = idx.as_unit('ns').asi8
    return (loc - ns) / 86400e9 + np.asarray(ut_days, float)


# ------------------------------------------------------------------ the Sun
def swe():
    return bs.swe_mod()   # ephemeris path = $BIRTH_SKY_DATA/ephe (sepl_18, semo_18), sidereal mode Lahiri


def swe_lon(jd_ut, sidereal=False):
    s = swe()
    fl = s.FLG_SWIEPH | s.FLG_SPEED | (s.FLG_SIDEREAL if sidereal else 0)
    r, ret = s.calc_ut(jd_ut, s.SUN, fl)
    if not ret & s.FLG_SWIEPH:
        raise RuntimeError('Swiss Ephemeris fell back from the sepl files')
    return r[0], r[3]


class SunTable:
    """Apparent Sun longitude every 6 h UT, unwrapped (monotone), cubic Hermite with the daily motion."""

    def __init__(self, sidereal=False):
        self.sidereal = sidereal
        s = swe()
        j0 = s.julday(*TAB_FROM, 0.0)
        j1 = s.julday(*TAB_TO, 0.0)
        n = int(round((j1 - j0) / STEP)) + 1
        cache = WORK / f'sun_table_{"sid" if sidereal else "trop"}.npz'
        if cache.exists():
            z = np.load(cache)
            lon, v = z['lon'], z['v']
        else:
            lon = np.empty(n)
            v = np.empty(n)
            for i in range(n):
                lon[i], v[i] = swe_lon(j0 + i * STEP, sidereal)
            WORK.mkdir(parents=True, exist_ok=True)
            np.savez(cache, lon=lon, v=v)
        d = np.diff(lon)
        d[d < -180] += 360
        self.L = lon[0] + np.concatenate([[0.0], np.cumsum(d)])
        self.v = v * STEP                   # degrees per step
        self.t0 = j0 - EPOCH_JD
        self.n = n
        self.min_speed = float(v.min())

    def _parts(self, i):
        return self.L[i], self.L[i + 1], self.v[i], self.v[i + 1]

    def lon(self, t):
        """Cumulative longitude (degrees) at UT days t."""
        x = (np.asarray(t, float) - self.t0) / STEP
        i = np.floor(x).astype(np.int64)
        u = x - i
        p0, p1, m0, m1 = self._parts(i)
        u2 = u * u
        u3 = u2 * u
        return (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (3 * u2 - 2 * u3) * p1 + (u3 - u2) * m1

    def inverse(self, target):
        target = np.asarray(target, float)
        i = np.searchsorted(self.L, target, 'right') - 1
        p0, p1, m0, m1 = self._parts(i)
        u = (target - p0) / (p1 - p0)
        for _ in range(4):
            u2 = u * u
            u3 = u2 * u
            f = (2 * u3 - 3 * u2 + 1) * p0 + (u3 - 2 * u2 + u) * m0 + (3 * u2 - 2 * u3) * p1 + (u3 - u2) * m1 - target
            fp = (6 * u2 - 6 * u) * p0 + (3 * u2 - 4 * u + 1) * m0 + (6 * u - 6 * u2) * p1 + (3 * u2 - 2 * u) * m1
            u = u - f / fp
        return self.t0 + (i + u) * STEP


def returns(tab, L0, anchor):
    """Return instants (UT days) with cumulative longitude L0 + 360 k nearest to `anchor` (UT days)."""
    k = np.rint((tab.lon(anchor) - L0) / 360.0)
    return tab.inverse(L0 + 360.0 * k)


def direct_return(lon0, anchor_jd, sidereal=False):
    """Root finding on swe.calc_ut itself (no table): Newton from the anchor, then two secant polish steps."""
    t = anchor_jd
    for _ in range(12):
        lam, v = swe_lon(t, sidereal)
        step = (((lam - lon0) + 180) % 360 - 180) / v
        t -= step
        if abs(step) < 1e-9:
            break
    return t


# ------------------------------------------------------------------ real births: one accumulator per country
def new_acc(cohorts):
    ny = len(RET_YEARS)
    return dict(cohorts=list(cohorts), cat=np.zeros((ny, NCAT)), hour=np.zeros((ny, 24, NCAT)), month=np.zeros((ny, 12, NCAT)),
                cohort=np.zeros((ny, len(cohorts), NCAT)), dst=np.zeros((ny, 2, NCAT)), cat_birth_offset=np.zeros((ny, NCAT)),
                cat_ut=np.zeros((ny, NCAT)), shift_local=np.zeros(ny), shift_ut=np.zeros(ny), w=np.zeros(ny),
                moving=np.zeros((2, len(MOVE), NCAT)), feb29={}, feb29_births=0.0, births=0.0, max_dev_days=0.0,
                n_records=0, n_unique_ut=0)


def _bincat(acc_arr, cat, w):
    acc_arr += np.bincount(np.clip(cat, CAT_LO, CAT_LO + NCAT - 1) - CAT_LO, weights=w, minlength=NCAT)


def accumulate_real(acc, tab, bday, m0, ut0, off_birth, tz, w, dst=None):
    """Births with local birth date `bday` (days), local clock minute m0, UT instant ut0 (days), UTC offset at
    birth (minutes) in IANA zone `tz` (one zone per call), weight w. Fills acc for every year of RET_YEARS."""
    y0, M, D = civil_from_days(bday)
    feb29 = (M == 2) & (D == 29)
    acc['births'] += float(w.sum())
    acc['feb29_births'] += float(w[feb29].sum())
    acc['n_records'] += len(w)
    ci = y0 - acc['cohorts'][0]
    # one root per distinct UT instant and anniversary: births share instants
    key = np.round(ut0 * 1440).astype(np.int64)
    uk, inv = np.unique(key, return_inverse=True)
    acc['n_unique_ut'] += len(uk)
    L0u = tab.lon(uk / 1440.0)
    L0 = L0u[inv]
    for iy, Y in enumerate(RET_YEARS):
        ok = y0 < Y
        if not ok.any():
            continue
        bdY = anchor_day(Y, M, D)
        T = returns(tab, L0, bdY + 0.5)
        acc['max_dev_days'] = max(acc['max_dev_days'], float(np.abs(T - bdY - 0.5)[ok].max()))
        loc = local_days(T, tz)
        rel = loc - bdY                              # days after local midnight starting the birthday
        cat = np.floor(rel).astype(np.int64)
        # 29 February births: the local date of the return, kept apart
        f = ok & feb29
        if f.any():
            _, mm, dd = civil_from_days(np.floor(loc[f]).astype(np.int64))
            for lab, ww in pd.Series(w[f]).groupby([f'{a:02d}-{b:02d}' for a, b in zip(mm, dd)]).sum().items():
                acc['feb29'][f'{Y}:{lab}'] = acc['feb29'].get(f'{Y}:{lab}', 0.0) + float(ww)
        g = ok & ~feb29
        if not g.any():
            continue
        wg, cg, relg = w[g], cat[g], rel[g]
        acc['w'][iy] += wg.sum()
        _bincat(acc['cat'][iy], cg, wg)
        acc['shift_local'][iy] += float((wg * (relg * 1440 - m0[g])).sum())
        shift_ut = (T[g] - ut0[g]) * 1440 - (bdY[g] - bday[g]) * 1440
        acc['shift_ut'][iy] += float((wg * shift_ut).sum())
        _bincat(acc['cat_ut'][iy], np.floor((m0[g] + shift_ut) / 1440).astype(np.int64), wg)
        _bincat(acc['cat_birth_offset'][iy], np.floor(T[g] + off_birth[g] / 1440.0 - bdY[g]).astype(np.int64), wg)
        idx = np.clip(cg, CAT_LO, CAT_LO + NCAT - 1) - CAT_LO
        h = (m0[g] // 60).astype(np.int64)
        np.add.at(acc['hour'][iy], (h, idx), wg)
        np.add.at(acc['month'][iy], (M[g] - 1, idx), wg)
        np.add.at(acc['cohort'][iy], (ci[g], idx), wg)
        if dst is not None:
            np.add.at(acc['dst'][iy], (dst[g].astype(np.int64), idx), wg)
        if Y in (2027, 2028):
            for im, dh in enumerate(MOVE):
                _bincat(acc['moving'][Y - 2027, im], np.floor(relg + dh / 24.0).astype(np.int64), wg)


def finish_acc(acc):
    out = {k: (v.tolist() if isinstance(v, np.ndarray) else v) for k, v in acc.items()}
    return out


def offsets_minutes(ut_days, tz):
    return np.rint((local_days(ut_days, tz) - ut_days) * 1440)


# ------------------------------------------------------------------ Brazil
def compute_br(tab):
    import pyarrow.parquet as papq
    acc = new_acc(bs.BR_YEARS)
    audits, spont_hours, all_hours = {}, np.zeros(24), np.zeros(24)
    for y in bs.BR_YEARS:
        pq = bs.BR_DIR / f'sinasc_{y}.parquet'
        have = set(papq.read_schema(pq).names)
        cols = [k for k in ('DTNASC', 'HORANASC', 'CODMUNNASC', 'PARTO', 'STTRABPART') if k in have]
        raw = pd.read_parquet(pq, columns=cols)
        for k in ('PARTO', 'STTRABPART'):          # STTRABPART only from 2010 (as in birth_sky.py: spontaneous = PARTO=1 & STTRABPART=2)
            if k not in raw:
                raw[k] = pd.Series([''] * len(raw), dtype='string')
        a = {'n_records': len(raw)}
        h = raw.HORANASC.fillna('').str.strip()
        okt = h.str.fullmatch(r'([01]\d|2[0-3])[0-5]\d').fillna(False).astype(bool)
        a['time_blank'] = int((h == '').sum())
        a['time_valid'] = int(okt.sum())
        a['time_invalid'] = a['n_records'] - a['time_blank'] - a['time_valid']
        df = raw[okt.values].copy()
        del raw
        mun = pd.read_csv(bs.BR_DIR / 'municipios_tz.csv', dtype={'cod6': str})
        df = df.merge(mun[['cod6', 'tz']], left_on='CODMUNNASC', right_on='cod6', how='left')
        um = df.tz.isna()
        a['unmatched_municipality'] = int(um.sum())
        df = df[~um]
        date = pd.to_datetime(df.DTNASC, format='%d%m%Y', errors='coerce')
        bad = date.isna() | (date.dt.year != y)
        a['date_bad_or_other_year'] = int(bad.sum())
        df = df[~bad.values]
        date = date[~bad.values]
        minute = (df.HORANASC.str[:2].astype(int) * 60 + df.HORANASC.str[2:].astype(int)).values
        spont = ((df.PARTO.fillna('') == '1') & (df.STTRABPART.fillna('') == '2')).to_numpy(dtype=bool)
        spont_hours += np.bincount(minute[spont] // 60, minlength=24)
        all_hours += np.bincount(minute // 60, minlength=24)
        a['n_used'] = len(df)
        a['spontaneous'] = int(spont.sum())
        g = pd.DataFrame({'tz': df.tz.values, 'day': ((date.values.astype('datetime64[D]').astype(np.int64))), 'm': minute})
        del df, date
        g = g.groupby(['tz', 'day', 'm'], sort=False).size().rename('n').reset_index()
        a['unique_cells'] = len(g)
        a['nonexistent_local_times'] = a['repeated_local_times'] = 0
        a['dst_births'] = 0
        for tz, part in g.groupby('tz', sort=False):
            day = part.day.values
            m0 = part.m.values.astype(float)
            dates = day.astype('datetime64[D]')
            jd, gap, rep = bs.local_to_jd(dates, m0, tz)
            a['nonexistent_local_times'] += gap
            a['repeated_local_times'] += rep
            ut0 = np.rint((jd - EPOCH_JD) * 1440) / 1440
            off = np.rint((day + m0 / 1440 - ut0) * 1440)
            jul = offsets_minutes(np.array([float(days_from_civil(y, 7, 1)) + 0.5]), tz)[0]
            dst = off > jul
            w = part.n.values.astype(float)
            a['dst_births'] += int(w[dst].sum())
            accumulate_real(acc, tab, day, m0, ut0, off, tz, w, dst)
        audits[y] = a
        log(f'BR {y}: {a["n_used"]:,} births, {a["unique_cells"]:,} cells, DST {a["dst_births"]:,}; RSS {rss_mb():.0f} MB')
    out = finish_acc(acc)
    out['audit'] = audits
    out['spont_hours'] = spont_hours.tolist()
    out['all_hours'] = all_hours.tolist()
    save_json('br.json', out)


# ------------------------------------------------------------------ Japan
def compute_jp(tab):
    d = pd.read_csv(bs.JP_DIR / 'jp_births_month_day_hour.csv')
    d = d[d.day > 0]
    hc = [f'h{h:02d}' for h in range(24)]
    acc = new_acc(bs.JP_YEARS)
    audits = {}
    for y in bs.JP_YEARS:
        yy = d[d.year == y]
        cnt = yy[hc].values.astype(float)                     # days x 24
        day = days_from_civil(yy.year.values, yy.month.values, yy.day.values)
        # uniform within the hour: 60 minute centres
        mins = (np.arange(24)[:, None] * 60 + np.arange(60)[None, :] + 0.5).ravel()          # 1440
        D = np.repeat(day, 1440)
        M0 = np.tile(mins, len(day))
        W = np.repeat(cnt / 60.0, 60, axis=1).ravel()
        keep = W > 0
        D, M0, W = D[keep], M0[keep], W[keep]
        ut0 = D + (M0 - 540) / 1440.0
        accumulate_real(acc, tab, D, M0, ut0, np.full(len(D), 540.0), 'Asia/Tokyo', W)
        audits[y] = {'n_hour_known': float(cnt.sum()), 'n_table_total': float(yy.total.sum())}
        log(f'JP {y}: {cnt.sum():,.0f} births')
    out = finish_acc(acc)
    out['audit'] = audits
    save_json('jp.json', out)


# ------------------------------------------------------------------ USA
def us_zone_classes():
    """County births per IANA zone (birth_sky's county file), zones merged when their UTC offsets agree at every
    hour of the years used (birth years 2016-2024, return years). Returns {year_column: DataFrame(tz, share)}."""
    co = pd.read_csv(bs.US_DIR / 'us_counties_births_tz.csv', dtype={'GEOID': str})
    probe_years = list(range(2015, 2034)) + list(range(2096, 2104))
    probe = np.concatenate([np.arange(days_from_civil(y, 1, 1), days_from_civil(y + 1, 1, 1), 1 / 24.0) for y in probe_years])
    sig = {}
    for tz in sorted(co.tz.unique()):
        sig[tz] = hashlib.sha1(offsets_minutes(probe, tz).astype(np.int32).tobytes()).hexdigest()
    rep = {}
    for tz in sorted(co.tz.unique(), key=lambda z: -co[co.tz == z].shape[0]):
        rep.setdefault(sig[tz], tz)
    co['cls'] = co.tz.map(lambda z: rep[sig[z]])
    return co, {z: rep[sig[z]] for z in sig}


def compute_us(tab):
    co, zone_map = us_zone_classes()
    acc = new_acc(bs.US_YEARS)
    audits = {}
    for y in bs.US_YEARS:
        c = pd.read_parquet(bs.US_DIR / f'us_{y}_counts.parquet', columns=['month', 'weekday', 'hhmm', 'n'])
        a = {'n_records': int(c.n.sum()), 'time_not_stated': int(c[c.hhmm == '9999'].n.sum())}
        c = c[c.hhmm != '9999'].copy()
        c['minute'] = c.hhmm.str[:2].astype(int) * 60 + c.hhmm.str[2:].astype(int)
        bad = c.minute >= 1440
        a['time_invalid'] = int(c[bad].n.sum())
        c = c[~bad]
        a['n_used'] = int(c.n.sum())
        c['month'] = c.month.astype(int)
        c['weekday'] = c.weekday.astype(int)
        c = c.groupby(['month', 'weekday', 'minute']).n.sum().reset_index()
        days = bs.dates_by_month_weekday(y)
        rows = []
        for (m, wd), dd in days.items():
            part = c[(c.month == m) & (c.weekday == wd)]
            if part.empty:
                continue
            dn = np.array([np.datetime64(x, 'D').astype(np.int64) for x in dd])
            rows.append(pd.DataFrame({'day': np.repeat(dn, len(part)), 'm': np.tile(part.minute.values, len(dn)),
                                      'n': np.tile(part.n.values / len(dn), len(dn))}))
        R = pd.concat(rows, ignore_index=True)
        col = f'BIRTHS{min(max(y, 2021), 2024)}'
        wz = co.assign(w=co[col].clip(lower=0)).groupby('cls').w.sum()
        wz = wz[wz > 0] / wz[wz > 0].sum()
        a['geo_weights'] = f'Census county {col}'
        a['zones'] = {k: round(float(v), 6) for k, v in wz.items()}
        for tz, share in wz.items():
            jd, gap, rep = bs.local_to_jd(R.day.values.astype('datetime64[D]'), R.m.values.astype(float), tz)
            ut0 = np.rint((jd - EPOCH_JD) * 1440) / 1440
            off = np.rint((R.day.values + R.m.values / 1440 - ut0) * 1440)
            accumulate_real(acc, tab, R.day.values, R.m.values.astype(float), ut0, off, tz, R.n.values * share)
        audits[y] = a
        log(f'US {y}: {a["n_used"]:,} births over {len(wz)} zone classes; RSS {rss_mb():.0f} MB')
    out = finish_acc(acc)
    out['audit'] = audits
    out['zone_map'] = zone_map
    save_json('us.json', out)


# ------------------------------------------------------------------ model population
def cell_fractions(s, h):
    """Fraction of the local-hour cell [60h, 60h+60) whose outcome is each category -3..+3, given the local clock
    shift s (minutes) at the cell (the outcome of minute m is floor((m + s) / 1440)). Returns (..., 7)."""
    ks = np.arange(CAT_LO + 1, CAT_LO + NCAT)                      # boundaries k = -2..3: P(cat < k)
    F = np.clip((1440.0 * ks - s[..., None] - 60.0 * h[..., None]) / 60.0, 0, 1)
    out = np.empty(s.shape + (NCAT,))
    out[..., 0] = F[..., 0]
    out[..., 1:-1] = np.diff(F, axis=-1)
    out[..., -1] = 1 - F[..., -1]
    return out


def compute_model(tab, sid):
    br = load_json('br.json')
    prof = np.asarray(br['spont_hours'], float)
    prof /= prof.sum()
    H = np.arange(24)
    hc = (H + 0.5) / 24.0
    years_all = list(range(MODEL_YEARS[0] + 1, 2111))
    ny = len(years_all)
    # outputs
    sh_u = np.full((len(MODEL_YEARS), ny, NCAT), np.nan)     # shares by birth year x return year (uniform time)
    sh_s = np.full_like(sh_u, np.nan)                         # spontaneous profile
    sd_u = np.full_like(sh_u, np.nan)                         # sidereal, uniform
    sd_s = np.full_like(sh_u, np.nan)
    by_month = np.full((len(MODEL_YEARS), len(RET_YEARS), 12, NCAT), np.nan)
    move = np.full((len(MODEL_YEARS), 2, 2, len(MOVE), NCAT), np.nan)   # [by, 2027/2028, uniform/spont, shift, cat]
    mean_shift = np.full((len(MODEL_YEARS), ny), np.nan)
    h1 = {'trop': [0.0, 0.0], 'sid': [0.0, 0.0]}             # sum of 4-year slopes, count
    h1_doy = {'trop': np.zeros((365, 2)), 'sid': np.zeros((365, 2))}
    reset = []                                                # s(2101) - s(2097), births after 1 March
    reset_before = []
    life_hist = {k: np.zeros((len(MODEL_YEARS), 81)) for k in ('u', 's')}   # people by number of on-day birthdays (ages 1-80)
    life_age = np.full((len(MODEL_YEARS), 80, NCAT), np.nan)                 # outcome by age 1-80, uniform
    feb29 = {}
    sub = (np.arange(12) + 0.5) * 5.0                         # 5-minute grid inside the hour (lifetime per person)
    w5_u = np.full((24, 12), 1 / 288.0)
    w5_s = np.repeat(prof[:, None] / 12.0, 12, axis=1)
    for ib, y0 in enumerate(MODEL_YEARS):
        days = np.arange(days_from_civil(y0, 1, 1), days_from_civil(y0 + 1, 1, 1))
        _, M, D = civil_from_days(days)
        f29 = (M == 2) & (D == 29)
        idx = np.arange(len(days))
        doy = np.where(idx > np.argmax(f29), idx - 1, idx) if f29.any() else idx   # 0..364 without 29 February
        T0 = days[:, None] + hc[None, :]
        L0t = tab.lon(T0)
        L0s = sid.lon(T0)
        s_by_year = {}
        ssid_by_year = {}
        onday = np.zeros((len(days), 24, 12), np.int16)
        for iy, Y in enumerate(years_all):
            if Y <= y0:
                continue
            bdY = anchor_day(Y, M, D).astype(float)
            for kind, tb, L0 in (('trop', tab, L0t), ('sid', sid, L0s)):
                need = kind == 'trop' or Y <= 2099 or Y in SID_YEARS
                if not need:
                    continue
                T = returns(tb, L0, (bdY + 0.5)[:, None])
                s = (T - bdY[:, None] - hc[None, :]) * 1440.0          # local clock shift (zone-free: UT = local)
                if kind == 'trop':
                    if np.abs(T - bdY[:, None] - 0.5).max() > 3:
                        raise RuntimeError(f'return beyond 3 days: {y0} -> {Y}')
                    s_by_year[Y] = s.mean(1)
                else:
                    ssid_by_year[Y] = s.mean(1)
                fr = cell_fractions(s[~f29], np.broadcast_to(H, s[~f29].shape))
                u = fr.mean((0, 1))
                sp = (fr.mean(0) * prof[:, None]).sum(0)
                if kind == 'trop':
                    sh_u[ib, iy], sh_s[ib, iy] = u, sp
                    if Y in RET_YEARS:
                        frm = fr.mean(1)
                        for m in range(12):
                            by_month[ib, RET_YEARS.index(Y), m] = frm[M[~f29] == m + 1].mean(0)
                    if Y in (2027, 2028):
                        for im, dh in enumerate(MOVE):
                            fm = cell_fractions(s[~f29] + 60.0 * dh, np.broadcast_to(H, s[~f29].shape))
                            move[ib, Y - 2027, 0, im] = fm.mean((0, 1))
                            move[ib, Y - 2027, 1, im] = (fm.mean(0) * prof[:, None]).sum(0)
                    a = Y - y0
                    if 1 <= a <= 80:
                        life_age[ib, a - 1] = u
                        cat5 = np.floor((60.0 * H[None, :, None] + sub[None, None, :] + s[:, :, None]) / 1440.0)
                        onday += (cat5 == 0)
                    if f29.any():
                        _, mm, dd = civil_from_days(np.floor(T[f29]).astype(np.int64))
                        for lab in zip(mm.ravel(), dd.ravel()):
                            k = f'{Y}:{lab[0]:02d}-{lab[1]:02d}'
                            feb29[k] = feb29.get(k, 0) + 1
                else:
                    sd_u[ib, iy], sd_s[ib, iy] = u, sp
        # H1 / H7: mean shift per year over four-year cycles, return years up to 2099
        for kind, sb in (('trop', s_by_year), ('sid', ssid_by_year)):
            ys = [Y for Y in sb if Y + 4 in sb and Y + 4 <= 2099]
            if ys and y0 <= 2025:                                                       # H1/H7: births 1901-2025
                dif = np.stack([(sb[Y + 4] - sb[Y]) / 4.0 for Y in ys])[:, ~f29]       # (nY, days)
                h1[kind][0] += float(dif.sum())
                h1[kind][1] += dif.size
                np.add.at(h1_doy[kind], (doy[~f29], 0), dif.sum(0))
                np.add.at(h1_doy[kind], (doy[~f29], 1), len(ys))
        for Y, v in s_by_year.items():
            mean_shift[ib, years_all.index(Y)] = v[~f29].mean()
        if 2097 in s_by_year and 2101 in s_by_year:
            jump = (s_by_year[2101] - s_by_year[2097])[~f29]
            after = (M[~f29] >= 3)
            reset.append([float(jump[after].min()), float(jump[after].max()), float(jump[after].mean())])
            reset_before.append([float(jump[~after].min()), float(jump[~after].max()), float(jump[~after].mean())])
        if y0 + 80 <= 2110:
            nd = onday[~f29]
            for k, w5 in (('u', w5_u), ('s', w5_s)):
                life_hist[k][ib] = np.bincount(nd.reshape(len(nd), -1).ravel(), weights=np.tile(w5.ravel(), len(nd)) / len(nd), minlength=81)[:81]
        if y0 % 10 == 0:
            log(f'model {y0}: 2028 day-before {sh_u[ib, years_all.index(2028), 2]:.4f}; RSS {rss_mb():.0f} MB')
    np.savez(WORK / 'model.npz', sh_u=sh_u, sh_s=sh_s, sd_u=sd_u, sd_s=sd_s, by_month=by_month, move=move,
             mean_shift=mean_shift, life_u=life_hist['u'], life_s=life_hist['s'], life_age=life_age,
             years_all=np.array(years_all), birth_years=np.array(MODEL_YEARS),
             h1_doy_trop=h1_doy['trop'], h1_doy_sid=h1_doy['sid'], profile=prof)
    save_json('model.json', {'h1': h1, 'reset_after_march': reset, 'reset_jan_feb': reset_before, 'feb29': feb29,
                             'profile': prof.tolist()})
    log('model done')


# ------------------------------------------------------------------ fetch
def _curl(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    r = subprocess.run(['curl', '-sSL', '--fail', '--connect-timeout', '30', '-m', '1800', '-o', str(tmp), url])
    if r.returncode or not tmp.exists() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        return False
    tmp.rename(dest)
    return True


def _last_modified(url):
    h = subprocess.run(['curl', '-sIL', '-m', '60', url], capture_output=True, text=True).stdout
    lm = [ln.split(':', 1)[1].strip() for ln in h.splitlines() if ln.lower().startswith('last-modified:')]
    return lm[-1] if lm else None


def _manifest():
    p = DATA / 'manifest.json'
    return json.loads(p.read_text()) if p.exists() else {}


def _write_manifest(man):
    (DATA / 'manifest.json').write_text(json.dumps(man, indent=1, ensure_ascii=False))


WPP_DIR = DATA / 'wpp'
WPP_GZ = WPP_DIR / WPP_URL.rsplit('/', 1)[1]
WPP_FILTERED = WPP_DIR / 'wpp2024_single_age_medium_2027_2028.csv'
VSOP_FILE = DATA / 'vsop' / 'VSOP87D.ear'


def fetch_wpp():
    man = _manifest()
    if not WPP_GZ.exists():
        log('downloading', WPP_URL)
        if not _curl(WPP_URL, WPP_GZ):
            raise SystemExit('WPP download failed')
        man[str(WPP_GZ.relative_to(DATA))] = {'url': WPP_URL, 'bytes': WPP_GZ.stat().st_size, 'sha256': sha256(WPP_GZ),
                                              'downloaded': time.strftime('%Y-%m-%d'), 'last_modified': _last_modified(WPP_URL)}
    if not WPP_FILTERED.exists():
        cols = ['LocID', 'ISO3_code', 'LocTypeName', 'Location', 'Variant', 'Time', 'AgeGrp', 'AgeGrpStart', 'PopTotal']
        parts = []
        for ch in pd.read_csv(WPP_GZ, usecols=cols, chunksize=500_000, low_memory=False):
            parts.append(ch[ch.Time.isin([2027, 2028]) & (ch.Variant == 'Medium')])
        f = pd.concat(parts).drop(columns='Variant')
        f.to_csv(WPP_FILTERED, index=False)
        man[str(WPP_FILTERED.relative_to(DATA))] = {'from': str(WPP_GZ.relative_to(DATA)), 'rows': len(f), 'bytes': WPP_FILTERED.stat().st_size,
                                                    'sha256': sha256(WPP_FILTERED), 'filter': 'Time in (2027, 2028), Variant = Medium'}
        log(f'WPP filtered: {len(f):,} rows')
    if WPP_GZ.exists() and WPP_GZ.stat().st_size > 500e6:
        WPP_GZ.unlink()          # keep only the filtered file (its SHA-256 and the raw one's are in the manifest)
    _write_manifest(man)


def fetch_vsop():
    man = _manifest()
    if not VSOP_FILE.exists():
        for url in VSOP_URLS:
            log('downloading', url)
            if _curl(url, VSOP_FILE):
                man[str(VSOP_FILE.relative_to(DATA))] = {'url': url, 'bytes': VSOP_FILE.stat().st_size, 'sha256': sha256(VSOP_FILE),
                                                         'downloaded': time.strftime('%Y-%m-%d')}
                break
        else:
            raise SystemExit('VSOP87D download failed')
    key = str(VSOP_FILE.relative_to(DATA))
    if key not in man:   # present before this script fetched it: record what is there; validate checks the content
        man[key] = {'url': 'found in place (CDS VI/81 file, same size as the GitHub mirror)', 'bytes': VSOP_FILE.stat().st_size,
                    'sha256': sha256(VSOP_FILE)}
    _write_manifest(man)


def fetch():
    bs.ensure_ephemeris()
    miss_br = [y for y in bs.BR_YEARS if not (bs.BR_DIR / f'sinasc_{y}.parquet').exists()]
    if miss_br or not (bs.BR_DIR / 'municipios_tz.csv').exists():
        bs.fetch_br(miss_br)
    if not (bs.JP_DIR / 'jp_births_month_day_hour.csv').exists():
        bs.fetch_jp()
    miss_us = [y for y in bs.US_YEARS if not (bs.US_DIR / f'us_{y}_counts.parquet').exists()]
    if miss_us or not (bs.US_DIR / 'us_counties_births_tz.csv').exists():
        bs.fetch_us(miss_us)
    fetch_wpp()
    fetch_vsop()
    man = _manifest()
    inputs = [bs.BR_DIR / f'sinasc_{y}.parquet' for y in bs.BR_YEARS] + [bs.BR_DIR / 'municipios_tz.csv',
              bs.JP_DIR / 'jp_births_month_day_hour.csv', bs.US_DIR / 'us_counties_births_tz.csv'] + \
             [bs.US_DIR / f'us_{y}_counts.parquet' for y in bs.US_YEARS] + [bs.DATA / 'ephe' / 'sepl_18.se1', bs.DATA / 'ephe' / 'semo_18.se1']
    man['birth_sky_inputs'] = {str(p.relative_to(bs.DATA)): {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in inputs}
    _write_manifest(man)
    log('fetch done')


# ------------------------------------------------------------------ VSOP87D (browser calculator)
def read_vsop(min_amp=VSOP_MIN_AMPLITUDE):
    """VSOP87D Earth: {'L': [[[A, B, C], ...] per power of tau], 'R': ...}, terms with |A| >= min_amp."""
    out = {1: {}, 3: {}}
    var = power = None
    total = {}
    for line in VSOP_FILE.read_text().splitlines():
        if 'VSOP87' in line and 'VARIABLE' in line:
            var = int(line.split('VARIABLE')[1].split()[0])
            power = int(line.split('*T**')[1].split()[0])
            continue
        if var not in out or not line.strip():
            continue
        a, b, c = (float(x) for x in line.split()[-3:])
        total[(var, power)] = total.get((var, power), 0) + 1
        if abs(a) >= min_amp:
            out[var].setdefault(power, []).append([a, b, c])
    ser = {k: [out[v].get(p, []) for p in range(max(out[v]) + 1)] for k, v in (('L', 1), ('R', 3))}
    return ser, {f'{"LBR"[v - 1]}{p}': n for (v, p), n in sorted(total.items()) if v in out}


def _vsop_series(blocks, tau):
    s, pw = 0.0, 1.0
    for blk in blocks:
        a = np.array(blk) if blk else np.zeros((0, 3))
        s += (a[:, 0] * np.cos(a[:, 1] + a[:, 2] * tau)).sum() * pw if len(a) else 0.0
        pw *= tau
    return s


def vsop_apparent(jd_tt, ser):
    """Apparent geocentric longitude at TT jd_tt from the truncated VSOP87D series (+ FK5 correction -0.09033",
    aberration -20.4898"/R), with swisseph's own nutation in longitude (true minus FLG_NONUT): checks the series alone."""
    tau = (jd_tt - 2451545.0) / 365250.0
    L = _vsop_series(ser['L'], tau)
    R = _vsop_series(ser['R'], tau)
    s = swe()
    true = s.calc(jd_tt, s.SUN, s.FLG_SWIEPH)[0][0]
    nonut = s.calc(jd_tt, s.SUN, s.FLG_SWIEPH | s.FLG_NONUT)[0][0]
    dpsi = ((true - nonut + 180) % 360) - 180                         # nutation in longitude, degrees (exact, from swisseph)
    lon = np.degrees(L) + 180.0 + (-0.09033 - 20.4898 / R) / 3600.0 + dpsi
    return lon % 360.0


# ------------------------------------------------------------------ WPP weighting, examples, calculator, checks
def age_weights(pop, Y, adults):
    """pop: array of 101 (ages 0..99, 100+). -> {birth year: weight} for people with a return in Y."""
    w = {}
    for a in range(101):
        if adults and a < 18:
            continue
        if a < 100:
            for b in (Y - 1 - a, Y - a):
                if b < Y:
                    w[b] = w.get(b, 0.0) + pop[a] / 2
        else:
            for b in range(Y - 103, Y - 99):
                w[b] = w.get(b, 0.0) + pop[a] / 4
    return w


def weighted(table, years_all, birth_years, w, Y=None):
    """Population-weighted shares: table [birth year, return year, ...] (Y given) or [birth year, ...] (Y None)."""
    tab = table[:, list(years_all).index(Y)] if Y is not None else table
    tot = sum(w.values())
    by = list(birth_years)
    return sum(x / tot * tab[by.index(b)] for b, x in w.items())


MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def window_shares(bm, by, pop, Y, adults):
    """Sensitivity to the age -> birth year mapping: age a on 1 July of Y = born July-December of Y-1-a or January-June
    of Y-a (half each; 100+ = four whole birth years Y-103..Y-100). bm: model shares [birth year, birth month, cat] in Y."""
    acc, tot = np.zeros(NCAT), 0.0
    for a in range(18 if adults else 0, 101):
        parts = [(Y - 1 - a, range(6, 12)), (Y - a, range(0, 6))] if a < 100 else [(b, range(12)) for b in range(Y - 103, Y - 99)]
        for b, months in parts:
            if b >= Y:
                continue
            part = sum(bm[by.index(b), mo] * MONTH_DAYS[mo] for mo in months) / sum(MONTH_DAYS[mo] for mo in months)
            acc += pop[a] / len(parts) * part
            tot += pop[a] / len(parts)
    return acc / tot


def compute_wpp():
    m = np.load(WORK / 'model.npz')
    by, ya = list(m['birth_years']), list(m['years_all'])
    f = pd.read_csv(WPP_FILTERED, keep_default_na=False, na_values=[''])
    f['age'] = f.AgeGrpStart.astype(int)
    keep = f.LocTypeName.isin(AREA_TYPES)
    f = f[keep]
    out = []
    for (loc, iso, typ, name), g in f.groupby(['LocID', 'ISO3_code', 'LocTypeName', 'Location'], dropna=False):
        row = {'loc_id': int(loc), 'iso3': iso if isinstance(iso, str) else None, 'type': typ, 'name': name}
        for Y in (2027, 2028):
            pop = g[g.Time == Y].sort_values('age').PopTotal.values * 1000.0
            assert len(pop) == 101, (name, Y, len(pop))
            row[f'pop_{Y}'] = float(pop.sum())
            row[f'pop18_{Y}'] = float(pop[18:].sum())
            c = np.cumsum(pop)
            row[f'median_age_{Y}'] = float(np.searchsorted(c, c[-1] / 2) + 0.5)
            for grp, adults in (('all', False), ('adults', True)):
                w = age_weights(pop, Y, adults)
                row[f'{Y}_{grp}_u'] = weighted(m['sh_u'], ya, by, w, Y).tolist()
                row[f'{Y}_{grp}_s'] = weighted(m['sh_s'], ya, by, w, Y).tolist()
            if typ == 'World':
                wa = age_weights(pop, Y, True)
                row[f'move_{Y}'] = {p: weighted(m['move'][:, Y - 2027, ip], ya, by, wa).tolist() for ip, p in enumerate('us')}
            for grp, adults in (('all', False), ('adults', True)):
                row[f'{Y}_{grp}_u_window'] = window_shares(m['by_month'][:, RET_YEARS.index(Y)], by, pop, Y, adults).tolist()
        if typ == 'World':
            p28 = g[g.Time == 2028].sort_values('age').PopTotal.values * 1000.0
            wa = age_weights(p28, 2028, True)
            row['series'] = {Y: {grp: {'u': weighted(m['sh_u'], ya, by, age_weights(p28, Y, adults), Y).tolist(),
                                       's': weighted(m['sh_s'], ya, by, age_weights(p28, Y, adults), Y).tolist()}
                                 for grp, adults in (('all', False), ('adults', True))} for Y in SERIES_YEARS}
            row['sidereal'] = {}          # the same people (adults of 2028) in every year 2026-2030
            for Y in SID_YEARS:
                row['sidereal'][Y] = {'u': weighted(m['sd_u'], ya, by, wa, Y).tolist(), 's': weighted(m['sd_s'], ya, by, wa, Y).tolist(),
                                      'trop_u': weighted(m['sh_u'], ya, by, wa, Y).tolist(), 'trop_s': weighted(m['sh_s'], ya, by, wa, Y).tolist()}
        out.append(row)
    save_json('wpp.json', out)
    w = next(r for r in out if r['type'] == 'World')
    log(f"WPP: {len(out)} areas; World 2028 {w['pop_2028'] / 1e9:.3f} bn, adults day-before {w['2028_adults_u'][2]:.4f}")


def compute_misc(tab, sid):
    s = swe()
    rng = np.random.default_rng(20261104)
    out = {'swe_version': s.version}
    # 1. interpolation against direct root finding on swe.calc_ut
    for kind, tb, n in (('trop', tab, 3000), ('sid', sid, 1000)):
        t0 = rng.uniform(days_from_civil(1901, 1, 2), days_from_civil(2026, 1, 1), n)
        Y = np.array([rng.integers(int(civil_from_days(int(t))[0]) + 1, 2110) for t in t0])
        y_, M, D = civil_from_days(np.floor(t0).astype(np.int64))
        anchor = anchor_day(Y, M, D) + 0.5
        T = returns(tb, tb.lon(t0), anchor)
        err = []
        for i in range(n):
            lon0 = swe_lon(t0[i] + EPOCH_JD, kind == 'sid')[0]
            Td = direct_return(lon0, anchor[i] + EPOCH_JD, kind == 'sid') - EPOCH_JD
            err.append(abs(Td - T[i]) * 86400)
        out[f'interp_{kind}'] = {'n': n, 'max_err_s': float(max(err)), 'mean_err_s': float(np.mean(err)),
                                 'max_dev_days': float(np.abs(T - anchor).max())}
        log(f'interpolation {kind}: max {max(err):.4f} s over {n}')
    # 2. the analytic hour-cell model against an exact per-minute grid
    m = np.load(WORK / 'model.npz') if (WORK / 'model.npz').exists() else None
    grid = []
    for y0, Y in ((1960, 2028), (1999, 2027), (1950, 2101)):
        days = np.arange(days_from_civil(y0, 1, 1), days_from_civil(y0 + 1, 1, 1))
        _, M, D = civil_from_days(days)
        days = days[~((M == 2) & (D == 29))]
        _, M, D = civil_from_days(days)
        mins = np.arange(1440) + 0.5
        T0 = (days[:, None] + mins[None, :] / 1440.0)
        bdY = anchor_day(Y, M, D).astype(float)
        T = returns(tab, tab.lon(T0), (bdY + 0.5)[:, None])
        cat = np.floor(T - bdY[:, None]).astype(np.int64)
        exact = np.bincount(np.clip(cat.ravel(), -3, 3) + 3, minlength=7) / cat.size
        row = {'birth_year': y0, 'Y': Y, 'grid': exact.tolist()}
        if m is not None:
            row['model'] = m['sh_u'][list(m['birth_years']).index(y0), list(m['years_all']).index(Y)].tolist()
        grid.append(row)
    out['grid_check'] = grid
    # 3. example people (zone without DST: Etc/GMT-3 = UTC+3 all year), born 15 June at 12:00 local
    ex = []
    for y0 in (1990, 1955):
        b = days_from_civil(y0, 6, 15)
        t0 = b + 0.5 - 3 / 24.0
        lon0 = swe_lon(t0 + EPOCH_JD)[0]
        rows = []
        for Y in range(y0 + 1, 2111):
            bdY = int(days_from_civil(Y, 6, 15))
            T = direct_return(lon0, bdY + 0.5 + EPOCH_JD) - EPOCH_JD
            Tt = float(returns(tab, tab.lon(np.array([t0])), np.array([bdY + 0.5]))[0])
            loc = T + 3 / 24.0
            rows.append([Y, round((loc - bdY - 0.5) * 1440, 2), int(np.floor(loc - bdY)), round(abs(T - Tt) * 86400, 4),
                         int(round(T * 86400))])
        ex.append({'birth_local': f'{y0}-06-15 12:00', 'zone': 'Etc/GMT-3 (UTC+3, no DST)', 'natal_longitude': round(lon0, 6),
                   'fields': ['year', 'clock_shift_min', 'outcome_days', 'table_vs_direct_s', 'return_unix_s'], 'rows': rows})
    out['examples'] = ex
    # 4. calculator test cases: births uniform in UT over 1925-2025, exact returns 2026-2030 (direct root finding)
    lo, hi = days_from_civil(1925, 1, 1) * 86400, days_from_civil(2026, 1, 1) * 86400
    cases = []
    for t in rng.integers(lo, hi, 400):
        t0 = int(t) / 86400.0
        lon0 = swe_lon(t0 + EPOCH_JD)[0]
        _, M, D = civil_from_days(int(np.floor(t0)))
        r = [int(t), round(lon0, 6)]
        for Y in range(2026, 2031):
            a = float(anchor_day(Y, M, D)) + 0.5
            T = direct_return(lon0, a + EPOCH_JD) - EPOCH_JD
            if abs(T - a) > 3:
                raise RuntimeError('calculator case beyond 3 days')
            r.append(int(round(T * 86400)))
        cases.append(r)
    out['calculator'] = cases
    # 5. VSOP87D truncated series vs swisseph (TT), for the browser
    if VSOP_FILE.exists():
        ser, total = read_vsop()
        jt = rng.uniform(s.julday(1900, 1, 1, 0), s.julday(2110, 12, 31, 0), 600)
        d = []
        for j in jt:
            a = vsop_apparent(j, ser)
            b = s.calc(j, s.SUN, s.FLG_SWIEPH)[0][0]
            d.append(abs(((a - b + 180) % 360) - 180) * 3600)
        out['vsop'] = {'kept': {k: sum(map(len, ser[k])) for k in ('L', 'R')},
                       'total_terms': total, 'max_err_arcsec': float(max(d)), 'mean_err_arcsec': float(np.mean(d))}
        log(f'VSOP87D truncated: max {max(d):.3f}" ({out["vsop"]["kept"]})')
    # 6. tables
    out['min_speed'] = {'trop': tab.min_speed, 'sid': sid.min_speed}
    br_off = {}
    for tz in pd.read_csv(bs.BR_DIR / 'municipios_tz.csv').tz.dropna().unique():
        probe = np.concatenate([np.arange(days_from_civil(y, 1, 1), days_from_civil(y + 1, 1, 1), 1 / 24.0) for y in RET_YEARS])
        br_off[tz] = sorted(set(offsets_minutes(probe, tz).astype(int).tolist()))
    out['br_return_offsets'] = br_off
    save_json('misc.json', out)


def compute_all():
    WORK.mkdir(parents=True, exist_ok=True)
    tab, sid = SunTable(False), SunTable(True)
    log(f'tables ready ({tab.n} steps)')
    compute_br(tab)
    compute_jp(tab)
    compute_us(tab)
    compute_model(tab, sid)
    compute_wpp()
    compute_misc(tab, sid)
    log(f'compute done, peak RSS {rss_mb():.0f} MB')



# ------------------------------------------------------------------ validate and hypotheses
CATS5 = [-2, -1, 0, 1, 2]


def _shares(row, w=None):
    """7-category counts (or shares) -> list of 5 shares for -2..+2 (-3 folded into -2, +3 into +2)."""
    a = np.asarray(row, float)
    t = a.sum() if w is None else w
    a = a / t if t else a * 0
    return [a[0] + a[1], a[2], a[3], a[4], a[5] + a[6]]


def _load_all():
    m = np.load(WORK / 'model.npz')
    return dict(br=load_json('br.json'), jp=load_json('jp.json'), us=load_json('us.json'), mj=load_json('model.json'), m=m,
                ya=list(m['years_all']), by=list(m['birth_years']), wpp=load_json('wpp.json'), misc=load_json('misc.json'))


def real_shares(c, Y, key='cat'):
    i = RET_YEARS.index(Y)
    return _shares(c[key][i], c['w'][i])


def model_mean(d, y_from, y_to, Y, table='sh_u'):
    """Equal weight per birth year (and per calendar day inside it)."""
    rows = [d['m'][table][d['by'].index(b), d['ya'].index(Y)] for b in range(y_from, y_to + 1)]
    return np.mean(rows, 0)


def model_vs_real(d, c, Y):
    """Model shares with the cohort mix of a real population (births per birth year), against the real shares."""
    i = RET_YEARS.index(Y)
    coh = np.asarray(c['cohort'][i]).sum(1)
    out = {}
    for prof, tab in (('uniform', 'sh_u'), ('spontaneous', 'sh_s')):
        mod = sum(coh[j] / coh.sum() * d['m'][tab][d['by'].index(b), d['ya'].index(Y)] for j, b in enumerate(c['cohorts']) if coh[j] > 0)
        out[prof] = _shares(mod)
    out['real'] = real_shares(c, Y)
    return out


def hypotheses_results(d):
    mj, wpp = d['mj'], d['wpp']
    br = d['br']
    res = []

    def add(hid, verdict, detail, numbers):
        res.append(dict(id=hid, text=HYPOTHESES[hid], verdict=verdict, detail=detail, numbers=numbers))
    # H1
    h1 = -mj['h1']['trop'][0] / mj['h1']['trop'][1]
    doy = d['m']['h1_doy_trop']
    per_day = -doy[:, 0] / doy[:, 1]
    inside = float(((per_day >= 10.7) & (per_day <= 11.7)).mean())
    add('H1', 'holds' if 10.7 <= h1 <= 11.7 else 'does not hold',
        f'mean {h1:.2f} min/yr earlier over {int(mj["h1"]["trop"][1]):,} (birth day x hour x four-year step) cells, births 1901-2025, '
        f'return years to 2099; by calendar day of birth {per_day.min():.2f}-{per_day.max():.2f} min/yr ({100 * inside:.0f} % of '
        f'birthdays inside 11.2 +- 0.5: the average holds, not every birthday)',
        dict(mean_min_per_year=h1, by_birthday_min=float(per_day.min()), by_birthday_max=float(per_day.max()), birthdays_inside=inside))
    # H2
    db = {Y: real_shares(br, Y)[1] for Y in range(2026, 2031)}
    ok = all(db[2028] > db[Y] for Y in (2026, 2027, 2029, 2030))
    add('H2', 'holds' if ok else 'does not hold',
        'Brazil day-before share ' + ', '.join(f'{Y} {100 * v:.2f} %' for Y, v in db.items()), dict(day_before=db))
    # H3
    world = next(r for r in wpp if r['type'] == 'World')
    v3 = _shares(world['2028_adults_u'])
    s3 = _shares(world['2028_adults_s'])
    w3 = _shares(world['2028_adults_u_window'])
    add('H3', 'holds' if v3[1] > 0.5 else 'does not hold',
        f'World 18+ 2028 (uniform times): day before {100 * v3[1]:.2f} %, two days before {100 * v3[0]:.2f} %, on the day '
        f'{100 * v3[2]:.2f} %, day after {100 * v3[3]:.2f} %; spontaneous profile {100 * s3[1]:.2f} %; ages mapped by July '
        f'windows {100 * w3[1]:.2f} %', dict(shares=v3, spontaneous=s3, july_window=w3))
    # H4
    v4 = _shares(model_mean(d, 1940, 1959, 2028))
    add('H4', 'holds' if v4[0] >= 0.05 else 'does not hold',
        f'born 1940-1959, 2028: two days before {100 * v4[0]:.2f} %, day before {100 * v4[1]:.2f} %', dict(shares=v4))
    # H5
    hr = np.asarray(br['hour'][RET_YEARS.index(2028)])
    early = hr[0:6].sum(0)
    late = hr[18:24].sum(0)
    e, la = early[2] / early.sum(), late[2] / late.sum()
    add('H5', 'holds' if e >= 3 * la else 'does not hold',
        f'Brazil 2028 day-before share: births 00:00-05:59 {100 * e:.2f} %, 18:00-23:59 {100 * la:.2f} %, ratio {e / la:.2f}',
        dict(early=e, late=la, ratio=e / la))
    # H6
    jp = next(r for r in wpp if r['iso3'] == 'JPN')
    ng = next(r for r in wpp if r['iso3'] == 'NGA')
    a, b = _shares(jp['2028_all_u'])[1], _shares(ng['2028_all_u'])[1]
    sa, sb = _shares(jp['2028_all_s'])[1], _shares(ng['2028_all_s'])[1]
    wa, wb = _shares(jp['2028_all_u_window'])[1], _shares(ng['2028_all_u_window'])[1]
    rc = INDEPENDENT_RECOUNT
    # H6 fixes the time profile (uniform): the verdict reads the two uniform age mappings only. Other profiles and
    # the recount's convention (it counts infants with no 2028 return) are printed, not voted.
    conv = [100 * (a - b), 100 * (wa - wb)]
    lo6, hi6 = min(conv), max(conv)
    v6 = 'holds' if lo6 >= 10 else 'does not hold' if hi6 < 10 else 'mixed'
    add('H6', v6,
        f'2028 day-before, whole population, uniform times: Japan {100 * a:.2f} %, Nigeria {100 * b:.2f} %, difference '
        f'{100 * (a - b):.2f} pp (spontaneous profile {100 * (sa - sb):.2f} pp, ages mapped by July windows {100 * (wa - wb):.2f} pp); '
        f'independent recount {rc["date"]}: {rc["H6_pp"]:.2f} pp (Japan {rc["H6_japan"]:.2f} %, Nigeria {rc["H6_nigeria"]:.2f} %; '
        f'it gives infants born in 2028, who have no 2028 return, the outcome of July-December 2027 births) and '
        f'{rc["H6_pp_profiles"][0]}-{rc["H6_pp_profiles"][1]} pp across time-of-day profiles; with uniform times, as the '
        f'prediction says, the margin over 10 pp is {lo6 - 10:.2f}-{hi6 - 10:.2f} pp',
        dict(japan=a, nigeria=b, diff_pp=100 * (a - b), diff_pp_spontaneous=100 * (sa - sb), diff_pp_july_window=100 * (wa - wb),
             recount_pp=rc['H6_pp'], range_pp=[lo6, hi6]))
    # H7
    h7 = mj['h1']['sid'][0] / mj['h1']['sid'][1]
    doy = d['m']['h1_doy_sid']
    per_day = doy[:, 0] / doy[:, 1]
    add('H7', 'holds' if 7 <= h7 <= 11 else 'does not hold',
        f'Lahiri sidereal return: mean {h7:+.2f} min/yr (later) over births 1901-2025 and return years to 2099; by calendar '
        f'day of birth {per_day.min():+.2f}..{per_day.max():+.2f}', dict(mean_min_per_year=h7))
    # H8
    lu = d['m']['life_u']
    i0, i1 = d['by'].index(1950), d['by'].index(2010)
    hist = lu[i0:i1 + 1].mean(0)
    v8 = float((hist * np.arange(81)).sum() / 80)
    by_year = [(float((lu[i] * np.arange(81)).sum() / 80)) for i in range(i0, i1 + 1)]
    add('H8', 'holds' if v8 <= 0.65 else 'does not hold',
        f'born 1950-2010, ages 1-80, uniform times: {100 * v8:.2f} % of birthdays have the return on the day '
        f'(by birth year {100 * min(by_year):.1f}-{100 * max(by_year):.1f} %)', dict(on_day=v8))
    return res


def validate() -> bool:
    d = _load_all()
    br, jp, us, mj, m, misc, wpp = d['br'], d['jp'], d['us'], d['mj'], d['m'], d['misc'], d['wpp']
    checks, problems = [], []

    def check(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))
        print(('OK   ' if ok else 'FAIL ') + name + ': ' + detail)
        if not ok:
            problems.append(name)
    hs = hashlib.sha256(json.dumps(HYPOTHESES, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    check('hypotheses unchanged since ccc676479', hs == HYPOTHESES_SHA256, hs[:16])
    check('Sun tables monotone', misc['min_speed']['trop'] > 0.9 and misc['min_speed']['sid'] > 0.9,
          f"min daily motion tropical {misc['min_speed']['trop']:.4f} deg, sidereal {misc['min_speed']['sid']:.4f} deg (swisseph {misc['swe_version']})")
    for k, nm in (('trop', 'tropical'), ('sid', 'sidereal')):
        x = misc[f'interp_{k}']
        check(f'interpolation vs direct root finding ({nm})', x['max_err_s'] < 2 and x['n'] >= (2000 if k == 'trop' else 500),
              f"{x['n']} random returns 1902-2110: max {x['max_err_s']:.4f} s, mean {x['mean_err_s']:.4f} s")
    dev = max(br['max_dev_days'], jp['max_dev_days'], us['max_dev_days'], misc['interp_trop']['max_dev_days'])
    check('tropical returns within 3 days of the anniversary noon', dev < 3,
          f"max {dev:.3f} days (real births, random cases; the model raises beyond 3); sidereal for comparison: up to "
          f"{misc['interp_sid']['max_dev_days']:.2f} days from the tropical anniversary by 2110")
    for nm, c in (('Brazil', br), ('Japan', jp), ('USA', us)):
        cat, w = np.asarray(c['cat']), np.asarray(c['w'])
        rel = np.abs(cat.sum(1) - w).max() / w.max()
        sub = max(np.abs(np.asarray(c[k]).sum(tuple(range(1, np.asarray(c[k]).ndim))) - w).max() / w.max() for k in ('hour', 'month', 'cohort'))
        check(f'{nm}: shares sum to 1', rel < 1e-9 and sub < 1e-9, f'max relative gap {rel:.1e} (breakdowns {sub:.1e})')
        beyond = (cat[:, 0].sum() + cat[:, 6].sum()) / w.sum()
        check(f'{nm}: no outcome beyond +-2 days', beyond == 0, f'share {beyond:.2e}')
    by_, ya_ = np.asarray(d['by']), np.asarray(d['ya'])
    printed = (by_ >= OUT_MODEL_YEARS[0])[:, None] & (ya_ <= 2032)[None, :]
    for t in ('sh_u', 'sh_s', 'sd_u', 'sd_s'):
        a = m[t]
        ok = np.isfinite(a).all(-1)
        gap = np.abs(a[ok].sum(-1) - 1).max()
        b3 = max(a[ok & printed][:, 0].max(), a[ok & printed][:, 6].max())
        far = (ok & ((a[..., 0] > 0) | (a[..., 6] > 0)))
        fy = by_[far.any(1)]
        check(f'model {t}: shares sum to 1; nothing beyond +-2 for births 1925+ up to 2032', gap < 1e-9 and b3 == 0,
              f'{ok.sum():,} (birth year, year) rows, max gap {gap:.1e}; beyond +-2 in printed rows {b3:.1e}; '
              f'elsewhere in {far.sum()} rows' + (f' (births {fy.min()}-{fy.max()})' if len(fy) else ''))
    wgap = max(abs(sum(r[f'{Y}_{g}_{p}']) - 1) for r in wpp for Y in (2027, 2028) for g in ('all', 'adults') for p in 'us')
    check('WPP: shares sum to 1', wgap < 1e-9, f'{len(wpp)} areas, max gap {wgap:.1e}')
    # counts against birth_sky.py
    for nm, c, key in (('Brazil', br, 'n_used'), ('Japan', jp, 'n_hour_known'), ('USA', us, 'n_used')):
        cc = {'Brazil': 'BR', 'Japan': 'JP', 'USA': 'US'}[nm]
        got = {int(y): int(round(a[key])) for y, a in c['audit'].items()}
        diff = {y: got[y] - BIRTH_SKY_TOTALS[cc][y] for y in got if got[y] != BIRTH_SKY_TOTALS[cc][y]}
        check(f'{nm}: births per year = birth_sky.py', not diff and set(got) == set(BIRTH_SKY_TOTALS[cc]),
              f'{sum(got.values()):,} births {min(got)}-{max(got)}' + (f'; differences {diff}' if diff else ''))
        check(f'{nm}: weights conserved', abs(c['births'] - sum(got.values())) < 1e-3 * len(got),
              f"accumulated {c['births']:,.3f} vs {sum(got.values()):,}; 29 February births {c['feb29_births']:,.1f} (left out of shares)")
        i25 = RET_YEARS.index(2025)
        check(f'{nm}: every birth in the 2025 share except 29 February', abs(c['w'][i25] - (c['births'] - c['feb29_births'])) < 1e-3 * len(got),
              f"{c['w'][i25]:,.1f} = {c['births']:,.1f} - {c['feb29_births']:,.1f}")
    bad = {y: a for y, a in br['audit'].items()
           if a['n_records'] != a['n_used'] + a['time_blank'] + a['time_invalid'] + a['unmatched_municipality'] + a['date_bad_or_other_year']}
    tot = {k: sum(a[k] for a in br['audit'].values()) for k in ('n_records', 'n_used', 'time_blank', 'time_invalid', 'unmatched_municipality', 'date_bad_or_other_year')}
    check('Brazil: record accounting', not bad, ', '.join(f'{k} {v:,}' for k, v in tot.items()))
    late = sum(br['audit'][str(y)]['dst_births'] for y in range(2020, 2025))
    early = sum(br['audit'][str(y)]['dst_births'] for y in range(2006, 2019))
    check('Brazil: DST births only before the 2019 abolition', late == 0 and early > 0, f'2006-2018 {early:,}, 2020-2024 {late}')
    offs = misc['br_return_offsets']
    check('Brazil zones: one UTC offset in every return year', all(len(v) == 1 for v in offs.values()),
          ', '.join(f'{k.split("/")[1]} {v}' for k, v in sorted(offs.items())))
    zs = [sum(a['zones'].values()) for a in us['audit'].values()]
    check('USA: zone weights sum to 1', max(abs(z - 1) for z in zs) < 1e-4,
          f"{len(us['audit']['2024']['zones'])} zone classes (merged from {len(us['zone_map'])} IANA zones by identical offsets)")
    sp = np.asarray(br['spont_hours'], float)
    sp = 100 * sp / sp.sum()
    ref = BIRTH_SKY_SPONT_PCT
    if BIRTH_SKY_JSON.exists():
        ref = json.loads(BIRTH_SKY_JSON.read_text())['hour_profiles_pct']['BR']['spontaneous_vaginal']
    check('spontaneous profile = birth_sky.py rung B3', np.abs(sp - np.asarray(ref)).max() < 0.0015,
          f'max difference {np.abs(sp - np.asarray(ref)).max():.4f} pp; {sum(a["spontaneous"] for a in br["audit"].values()):,} births')
    # WPP
    world = next(r for r in wpp if r['type'] == 'World')
    countries = [r for r in wpp if r['type'] == 'Country/Area']
    check('WPP: world population 2028 within 8.0-8.6 bn', 8.0e9 <= world['pop_2028'] <= 8.6e9,
          f"{world['pop_2028'] / 1e9:.3f} bn (2027: {world['pop_2027'] / 1e9:.3f})")
    s_c = sum(r['pop_2028'] for r in countries)
    check('WPP: countries add up to World', abs(s_c / world['pop_2028'] - 1) < 0.005, f'{len(countries)} countries {s_c / 1e9:.3f} bn')
    # physics
    h1 = mj['h1']['trop'][0] / mj['h1']['trop'][1]
    exp = -(365.25 - 365.242189) * 1440
    check('drift: mean four-year shift vs the mean tropical year', abs(h1 - exp) < 0.1, f'{h1:.3f} min/yr vs {exp:.3f}')
    h7 = mj['h1']['sid'][0] / mj['h1']['sid'][1]
    exp7 = exp + 50.29 / 3600 / (360 / 365.242189) * 1440
    check('sidereal drift vs precession (50.29"/yr)', abs(h7 - exp7) < 0.3, f'{h7:+.3f} min/yr vs {exp7:+.3f}')
    ra = np.asarray(mj['reset_after_march'])
    rb = np.asarray(mj['reset_jan_feb'])
    check('2100 reset: return 2101 vs 2097 later by > 22 h', ra[:, 0].min() > 22 * 60,
          f'births after 1 March: {ra[:, 0].min() / 60:.2f}-{ra[:, 1].max() / 60:.2f} h (mean {ra[:, 2].mean() / 60:.2f}); January-February '
          f'{rb[:, 0].min() / 60:.2f}-{rb[:, 1].max() / 60:.2f} h')
    gd = max(max(abs(a - b) for a, b in zip(g['grid'], g['model'])) for g in misc['grid_check'])
    check('analytic hour cells vs per-minute grid', gd < 3e-4,
          '; '.join(f"{g['birth_year']}->{g['Y']} day before grid {g['grid'][2]:.5f} model {g['model'][2]:.5f}" for g in misc['grid_check']) + f'; max {gd:.1e}')
    ex = max(r[3] for e in misc['examples'] for r in e['rows'])
    check('example people: table vs direct', ex < 2, f'max {ex:.4f} s over {sum(len(e["rows"]) for e in misc["examples"])} returns')
    cal = misc['calculator']
    ok = len(cal) == 400 and all(r[2] < r[3] < r[4] < r[5] < r[6] for r in cal)
    check('calculator cases', ok, f'{len(cal)} births 1925-2025, returns 2026-2030 by direct root finding')
    if 'vsop' in misc:
        v = misc['vsop']
        check('VSOP87D truncated series vs swisseph', v['max_err_arcsec'] < 1.0,
              f"terms >= {VSOP_MIN_AMPLITUDE:g}: L {v['kept']['L']}, R {v['kept']['R']}; 1900-2110 max {v['max_err_arcsec']:.3f}\", mean {v['mean_err_arcsec']:.3f}\"")
    for Y in (2027, 2028):
        c = model_vs_real(d, br, Y)
        du, ds = 100 * (c['uniform'][1] - c['real'][1]), 100 * (c['spontaneous'][1] - c['real'][1])
        check(f'model vs Brazil real births {Y} (reported)', abs(du) < 10 and abs(ds) < 10,
              f"day before: real {100 * c['real'][1]:.2f} %, model uniform {100 * c['uniform'][1]:.2f} % ({du:+.2f} pp), "
              f"spontaneous {100 * c['spontaneous'][1]:.2f} % ({ds:+.2f} pp)")
    ser = world['series']['2028']['adults']['u']
    check('world series: 2028 point = the 2028 adult share', np.abs(np.asarray(ser) - np.asarray(world['2028_adults_u'])).max() < 1e-12,
          f"series 2028 day before {100 * ser[2]:.2f} %; series to {SERIES_YEARS[-1]} needs model births to {MODEL_YEARS[-1]}")
    rc = INDEPENDENT_RECOUNT
    h2 = 100 * real_shares(br, 2028)[1]
    h3 = 100 * world['2028_adults_u'][2]
    check('independent recount: Brazil 2028 and World adults 2028', abs(h2 - rc['H2_brazil_2028']) < 0.01 and abs(h3 - rc['H3_world_adults']) < 0.1,
          f"Brazil {h2:.2f} % (recount {rc['H2_brazil_2028']:.2f}), World 18+ {h3:.2f} % (recount {rc['H3_world_adults']:.2f}, 1-July "
          f"day windows)")
    man = _manifest()
    mk = [k for k in man if k.startswith('wpp/')]
    stale = [k for k in mk if (DATA / k).exists() and sha256(DATA / k) != man[k]['sha256']]
    check('manifest: WPP files unchanged', WPP_FILTERED.exists() and not stale and str(WPP_FILTERED.relative_to(DATA)) in man,
          f"{len(mk)} files" + (f', changed {stale}' if stale else ''))
    print('\nhypotheses:')
    for h in hypotheses_results(d):
        print(f"  {h['id']} {h['verdict']}: {h['detail']}")
    (WORK / 'validation.json').write_text(json.dumps(dict(checks=checks, problems=problems), ensure_ascii=False, indent=1))
    print(f'{len(checks) - len(problems)}/{len(checks)} checks passed')
    return not problems



# ------------------------------------------------------------------ export
SOURCES = [
    dict(id='sinasc', name='SINASC, Sistema de Informações sobre Nascidos Vivos (Ministério da Saúde / DATASUS), 2006-2024',
         url='https://opendatasus.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc',
         licence='CC BY-ND 3.0 (aggregates only, with attribution)'),
    dict(id='jp-vital', name='Vital Statistics of Japan (人口動態統計), e-Stat table 0003411915, 2015-2024',
         url='https://www.e-stat.go.jp/dbview?sid=0003411915', licence='Government of Japan Standard Terms of Use (CC BY 4.0 compatible)'),
    dict(id='nchs', name='NCHS Natality public-use files 2016-2024; Census county population estimates co-est2024',
         url='https://www.cdc.gov/nchs/data_access/vitalstatsonline.htm', licence='U.S. government works (public domain)'),
    dict(id='wpp', name='United Nations, DESA, Population Division. World Population Prospects 2024, single ages, Medium variant',
         url=WPP_URL, licence='CC BY 3.0 IGO'),
    dict(id='swisseph', name='Swiss Ephemeris (Astrodienst), sepl_18 / semo_18', url='https://www.astro.com/swisseph/',
         licence='AGPL-3.0 or Swiss Ephemeris Professional Licence'),
    dict(id='vsop87', name='VSOP87D, Bretagnon & Francou 1988, CDS catalogue VI/81 (truncated Earth series for the calculator)',
         url='https://cdsarc.cds.unistra.fr/viz-bin/cat/VI/81', licence='CDS: free for scientific use, cite the authors'),
    dict(id='startarot', name='Derived numbers (this study)', url=f'https://startarot.online/research/{SLUG}', licence='CC BY 4.0'),
]


def _r(x, n=4):
    if isinstance(x, dict):
        return {k: _r(v, n) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_r(v, n) for v in x]
    if isinstance(x, (float, np.floating)):
        v = round(float(x), n)
        return 0 if v == 0 else v
    if isinstance(x, np.integer):
        return int(x)
    return x


def export():
    if not (WORK / 'validation.json').exists():
        raise SystemExit('run validate first')
    val = json.loads((WORK / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed: ' + ', '.join(val['problems']))
    d = _load_all()
    br, jp, us, mj, m, misc, wpp = d['br'], d['jp'], d['us'], d['mj'], d['m'], d['misc'], d['wpp']
    by, ya = d['by'], d['ya']
    hy = hypotheses_results(d)
    csv_rows = []

    def row(section, area, group, key, Y, profile, zodiac, shares, source):
        for cat, v in zip(CATS5, shares):
            csv_rows.append([section, area, group, key, Y, profile, zodiac, cat, 'share', round(float(v), 6), source])
    # ---- real births
    real = {'return_years': RET_YEARS, 'outcomes': CATS5,
            'note': 'shares of births (29 February left out); return year 2024 counts births before 2024 only'}
    for cc, c, src in (('BR', br, 'sinasc'), ('JP', jp, 'jp-vital'), ('US', us, 'nchs')):
        prof = 'recorded'
        e = {'birth_years': [c['cohorts'][0], c['cohorts'][-1]], 'births': c['births'], 'feb29_births': c['feb29_births'],
             'shares': {}, 'shares_same_offset': {}, 'mean_clock_shift_min': {}, 'mean_ut_shift_min': {}}
        for Y in RET_YEARS:
            i = RET_YEARS.index(Y)
            e['shares'][Y] = real_shares(c, Y)
            e['shares_same_offset'][Y] = real_shares(c, Y, 'cat_birth_offset')
            e['mean_clock_shift_min'][Y] = c['shift_local'][i] / c['w'][i]
            e['mean_ut_shift_min'][Y] = c['shift_ut'][i] / c['w'][i]
            row('real', cc, 'all', '', Y, prof, 'tropical', e['shares'][Y], src)
            row('real', cc, 'birth UTC offset kept', '', Y, prof, 'tropical', e['shares_same_offset'][Y], src)
            for j, b in enumerate(c['cohorts']):
                cnt = c['cohort'][i][j]
                if sum(cnt):
                    row('real', cc, 'birth_year', b, Y, prof, 'tropical', _shares(cnt), src)
            for mo in range(12):
                row('real', cc, 'birth_month', mo + 1, Y, prof, 'tropical', _shares(c['month'][i][mo]), src)
        e['by_birth_year'] = {Y: [[b] + _shares(c['cohort'][RET_YEARS.index(Y)][j]) for j, b in enumerate(c['cohorts'])
                                  if sum(c['cohort'][RET_YEARS.index(Y)][j])] for Y in (2027, 2028)}
        e['by_month'] = {Y: [_shares(c['month'][RET_YEARS.index(Y)][mo]) for mo in range(12)] for Y in (2027, 2028, 2029)}
        e['moving'] = {Y: [[dh] + _shares(c['moving'][Y - 2027][k]) for k, dh in enumerate(MOVE)] for Y in (2027, 2028)}
        for Y in (2027, 2028):
            for k, dh in enumerate(MOVE):
                row('moving', cc, 'residence_shift_h', dh, Y, prof, 'tropical', _shares(c['moving'][Y - 2027][k]), src)
        if cc == 'BR':
            e['by_hour'] = {Y: [_shares(c['hour'][RET_YEARS.index(Y)][h]) for h in range(24)] for Y in (2027, 2028)}
            for Y in RET_YEARS:
                for h in range(24):
                    row('real', cc, 'birth_hour_local', h, Y, prof, 'tropical', _shares(c['hour'][RET_YEARS.index(Y)][h]), src)
                for k, nm in ((0, 'standard'), (1, 'dst')):
                    row('real', cc, 'clock_at_birth', nm, Y, prof, 'tropical', _shares(c['dst'][RET_YEARS.index(Y)][k]), src)
            dst_n = sum(a['dst_births'] for a in c['audit'].values())
            e['dst'] = {'births_in_dst': dst_n, 'share_of_births': dst_n / c['births'],
                        'by_year': {Y: {'dst': _shares(c['dst'][RET_YEARS.index(Y)][1]), 'standard': _shares(c['dst'][RET_YEARS.index(Y)][0]),
                                        'contribution_pp': 100 * (real_shares(c, Y)[1] - real_shares(c, Y, 'cat_birth_offset')[1])}
                                    for Y in range(2025, 2033)},
                        'note': 'contribution_pp = day-before share with the return read at the zone offset of year Y minus the '
                                'share with the birth\'s own offset (DST at birth: the clock then ran one hour ahead)'}
            e['audit'] = {k: sum(a[k] for a in c['audit'].values()) for k in
                          ('n_records', 'n_used', 'time_blank', 'time_invalid', 'unmatched_municipality', 'date_bad_or_other_year',
                           'nonexistent_local_times', 'repeated_local_times', 'spontaneous')}
            e['audit']['note'] = 'nonexistent/repeated local times counted per distinct (zone, date, minute) cell'
            e['model_comparison'] = {Y: model_vs_real(d, c, Y) for Y in range(2025, 2033)}
        if cc == 'US':
            e['zones'] = us['audit']['2024']['zones']
            e['zone_note'] = ('day of month spread equally over the dates with the recorded month and weekday; zone by Census county '
                              'births; zones with the same UTC-offset history merged')
        if cc == 'JP':
            e['note'] = 'births by date and hour, spread uniformly within the hour (minute centres), JST'
        real[cc] = e
    # ---- model
    ob = OUT_MODEL_YEARS
    ry = list(range(2024, 2033))
    model = {'birth_years': [ob[0], ob[-1]], 'return_years': ry,
             'fields': ['birth_year'] + [f'{Y}:{c}' for Y in ry for c in ('-2', '-1', '0', '+1')],
             'by_birth_year_uniform': [], 'spontaneous_day_before': {}, 'note': 'uniform dates; time uniform or spontaneous profile; zone-free'}
    for b in ob:
        ib = by.index(b)
        r = [b]
        for Y in ry:
            if Y > b:
                sh = _shares(m['sh_u'][ib, ya.index(Y)])
                r += [sh[0], sh[1], sh[2], sh[3]]
            else:
                r += [None] * 4
        model['by_birth_year_uniform'].append(r)
        for Y in RET_YEARS + [2026, 2027, 2028, 2029, 2030]:
            if Y > b:
                row('model', 'model', 'birth_year', b, Y, 'uniform', 'tropical', _shares(m['sh_u'][ib, ya.index(Y)]), 'startarot')
                row('model', 'model', 'birth_year', b, Y, 'spontaneous', 'tropical', _shares(m['sh_s'][ib, ya.index(Y)]), 'startarot')
        for Y in SID_YEARS:
            if Y > b:
                row('model', 'model', 'birth_year', b, Y, 'uniform', 'sidereal_lahiri', _shares(m['sd_u'][ib, ya.index(Y)]), 'startarot')
    model['spontaneous_day_before'] = {Y: [_shares(m['sh_s'][by.index(b), ya.index(Y)])[1] if Y > b else None for b in ob] for Y in (2027, 2028)}
    dec = {}
    for d0 in range(1930, 2030, 10):
        d1 = min(d0 + 9, 2025)
        dec[f'{d0}s'] = {Y: {'uniform': _shares(model_mean(d, d0, d1, Y)), 'spontaneous': _shares(model_mean(d, d0, d1, Y, 'sh_s'))}
                         for Y in (2027, 2028)}
        for Y in (2027, 2028):
            row('model', 'model', 'birth_decade', f'{d0}s', Y, 'uniform', 'tropical', dec[f'{d0}s'][Y]['uniform'], 'startarot')
            row('model', 'model', 'birth_decade', f'{d0}s', Y, 'spontaneous', 'tropical', dec[f'{d0}s'][Y]['spontaneous'], 'startarot')
    model['by_decade'] = dec
    model['born_1940_1959'] = {Y: _shares(model_mean(d, 1940, 1959, Y)) for Y in (2027, 2028, 2029)}
    leaps = list(range(2028, 2049, 4))
    cg = {'leap_years': leaps, 'note': 'fixed groups, equal weight per calendar day of birth; shares -2..+2 in each leap year'}
    for nm, (a0, a1) in COHORT_GROUPS.items():
        cg[nm] = {'uniform': {Y: _shares(model_mean(d, a0, a1, Y)) for Y in leaps},
                  'spontaneous': {Y: _shares(model_mean(d, a0, a1, Y, 'sh_s')) for Y in leaps}}
        for Y in leaps:
            row('model', 'model', 'cohort', nm, Y, 'uniform', 'tropical', cg[nm]['uniform'][Y], 'startarot')
            row('model', 'model', 'cohort', nm, Y, 'spontaneous', 'tropical', cg[nm]['spontaneous'][Y], 'startarot')
    first = next((Y for Y in range(2028, 2101, 4) if _shares(model_mean(d, 2006, 2024, Y))[1] > 0.5), None)
    cg['first_leap_year_above_half_2006_2024'] = {'uniform': first, 'spontaneous': next(
        (Y for Y in range(2028, 2101, 4) if _shares(model_mean(d, 2006, 2024, Y, 'sh_s'))[1] > 0.5), None)}
    model['cohort_growth'] = cg
    lu, ls = m['life_u'], m['life_s']
    i0, i1 = by.index(1950), by.index(2010)
    la = m['life_age']
    model['lifetime'] = {
        'ages': [1, 80],
        'on_day_by_birth_year': [float((lu[by.index(b)] * np.arange(81)).sum() / 80) if b + 80 <= 2110 else None for b in ob],
        'on_day_1950_2010': {'uniform': float((lu[i0:i1 + 1].mean(0) * np.arange(81)).sum() / 80),
                             'spontaneous': float((ls[i0:i1 + 1].mean(0) * np.arange(81)).sum() / 80)},
        'people_by_on_day_count_1950_2010': {'uniform': lu[i0:i1 + 1].mean(0).tolist(), 'spontaneous': ls[i0:i1 + 1].mean(0).tolist()},
        'by_age_1950_2010_uniform': [_shares(la[i0:i1 + 1, a].mean(0)) for a in range(80)],
        'note': 'share of the birthdays at ages 1-80 with the return on the calendar day; histogram = share of people by the number '
                '(0-80) of such birthdays',
    }
    for a in range(80):
        row('model', 'model', 'age_born_1950_2010', a + 1, '', 'uniform', 'tropical', model['lifetime']['by_age_1950_2010_uniform'][a], 'startarot')
    dd = m['h1_doy_trop']
    model['drift_by_day_of_year_min'] = np.round(-dd[:, 0] / dd[:, 1], 2).tolist()
    # ---- WPP
    cfields = ['iso3', 'name', 'pop_2028_m', 'median_age_2028'] + [f'{Y}_{g}_{p}:{c}' for Y in (2027, 2028) for g in ('all', 'adults')
                                                                   for p, cs in (('u', ('-2', '-1', '+1')), ('s', ('-1',))) for c in cs]
    crow = []
    for r in sorted((r for r in wpp if r['type'] == 'Country/Area'), key=lambda r: r['name']):
        x = [r['iso3'], r['name'], r['pop_2028'] / 1e6, r['median_age_2028']]
        for Y in (2027, 2028):
            for g in ('all', 'adults'):
                u, sp = _shares(r[f'{Y}_{g}_u']), _shares(r[f'{Y}_{g}_s'])
                x += [u[0], u[1], u[3], sp[1]]
        crow.append(x)
    for r in wpp:
        area = r['iso3'] or r['name']
        for Y in (2027, 2028):
            for g, gn in (('all', 'all ages'), ('adults', 'aged 18+')):
                row('wpp', area, gn, r['type'], Y, 'uniform', 'tropical', _shares(r[f'{Y}_{g}_u']), 'wpp')
                row('wpp', area, gn, r['type'], Y, 'spontaneous', 'tropical', _shares(r[f'{Y}_{g}_s']), 'wpp')
    countries = {'fields': cfields, 'rows': crow, 'note': 'UN WPP 2024 population by single age on 1 July; model shares (uniform dates)'}
    agg = {}
    for r in wpp:
        if r['type'] in ('World', 'Geographic region'):          # subregions: in the CSV only
            agg[r['name']] = {'pop_2028': r['pop_2028'], 'pop18_2028': r['pop18_2028'], 'median_age_2028': r['median_age_2028']}
            for Y in (2027, 2028):
                for g in ('all', 'adults'):
                    agg[r['name']][f'{Y}_{g}'] = {'uniform': _shares(r[f'{Y}_{g}_u']), 'spontaneous': _shares(r[f'{Y}_{g}_s'])}
    world = next(r for r in wpp if r['type'] == 'World')
    for grp in ('adults', 'all'):
        agg[f'series_{grp}'] = {'years': SERIES_YEARS, 'note': 'World, 2028 age structure held fixed (ages fixed, birth years shifted); '
                                'shares -2..+2', 'uniform': {Y: _shares(world['series'][str(Y)][grp]['u']) for Y in SERIES_YEARS},
                                'spontaneous': {Y: _shares(world['series'][str(Y)][grp]['s']) for Y in SERIES_YEARS}}
        for Y in SERIES_YEARS:
            for p, pn in (('u', 'uniform'), ('s', 'spontaneous')):
                row('wpp_series', 'WLD', 'aged 18+' if grp == 'adults' else 'all ages', '2028 ages fixed', Y, pn, 'tropical',
                    _shares(world['series'][str(Y)][grp][p]), 'wpp')
    for r in wpp:
        if r['type'] in ('World', 'Geographic region'):
            agg[r['name']]['july_window_uniform'] = {Y: {g: _shares(r[f'{Y}_{g}_u_window']) for g in ('all', 'adults')} for Y in (2027, 2028)}
    moving = {'shifts_h': MOVE, 'BR': real['BR']['moving'], 'JP': real['JP']['moving'], 'US': real['US']['moving'],
              'world_adults': {Y: {p: [[dh] + _shares(world[f'move_{Y}'][p][k]) for k, dh in enumerate(MOVE)] for p in ('u', 's')} for Y in (2027, 2028)},
              'note': 'the same return instant read in a zone shifted by the given hours from the birth zone; birthday = same calendar date'}
    for Y in (2027, 2028):
        for p, pn in (('u', 'uniform'), ('s', 'spontaneous')):
            for k, dh in enumerate(MOVE):
                row('moving', 'WLD', 'residence_shift_h', dh, Y, pn, 'tropical', _shares(world[f'move_{Y}'][p][k]), 'wpp')
    sdd = m['h1_doy_sid']
    sidereal = {'ayanamsa': 'Lahiri (SE_SIDM_LAHIRI)', 'mean_shift_min_per_year': mj['h1']['sid'][0] / mj['h1']['sid'][1],
                'by_day_of_year_min': [float((sdd[:, 0] / sdd[:, 1]).min()), float((sdd[:, 0] / sdd[:, 1]).max())],
                'world_adults_2028_cohort': {Y: {k: _shares(v) for k, v in world['sidereal'][str(Y)].items()} for Y in SID_YEARS},
                'note': 'the same people (adults in 2028) in every year; trop_* = the tropical shares for comparison'}
    for Y in SID_YEARS:
        for k, pn in (('u', 'uniform'), ('s', 'spontaneous')):
            row('sidereal', 'WLD', 'aged 18+ in 2028', '', Y, pn, 'sidereal_lahiri', _shares(world['sidereal'][str(Y)][k]), 'wpp')
    example_people = misc['examples']
    for e in example_people:
        for r in e['rows']:
            csv_rows.append(['example', e['zone'], 'born ' + e['birth_local'], '', r[0], 'exact', 'tropical', r[2], 'clock_shift_min',
                             round(r[1], 2), 'startarot'])
    example_people = [dict(birth_local=e['birth_local'], zone=e['zone'], natal_longitude=e['natal_longitude'],
                           fields=['year', 'clock_shift_min', 'outcome_days'], rows=[[r[0], round(r[1], 1), r[2]] for r in e['rows']])
                      for e in example_people]
    # leap day
    ib28 = [by.index(b) for b in ob if b < 2028]
    bm = m['by_month'][:, RET_YEARS.index(2028)]
    janfeb = np.mean([(bm[i, 0] * 31 + bm[i, 1] * 28) / 59 for i in ib28], 0)
    rest = np.mean([sum(bm[i, k] * n for k, n in enumerate([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]) if k >= 2) / 306 for i in ib28], 0)
    f29 = {}
    for cc, c in (('BR', br), ('JP', jp), ('US', us)):
        f29[cc] = {'births': c['feb29_births'], 'return_dates': {k: v / c['feb29_births'] for k, v in sorted(c['feb29'].items()) if int(k[:4]) <= 2032}}
    leap_day = {'model_2028_born_1925_2025': {'jan_feb': _shares(janfeb), 'mar_dec': _shares(rest)},
                'BR_by_month': real['BR']['by_month'], 'feb29_births': f29,
                'note': 'in a leap year the birthdays after 29 February come one calendar day later against the Sun; '
                        'January-February birthdays catch up the next year'}
    reset = {'jump_2097_2101_after_march_h': [float(np.min(np.asarray(mj['reset_after_march'])[:, 0]) / 60),
                                              float(np.max(np.asarray(mj['reset_after_march'])[:, 1]) / 60)],
             'jump_2097_2101_jan_feb_h': [float(np.min(np.asarray(mj['reset_jan_feb'])[:, 0]) / 60),
                                          float(np.max(np.asarray(mj['reset_jan_feb'])[:, 1]) / 60)],
             'years': list(range(2097, 2103)),
             'real': {cc: {Y: real[cc]['shares'][Y] for Y in range(2097, 2103)} for cc in ('BR', 'JP', 'US')},
             'model_birth_years': {b: {Y: _shares(m['sh_u'][by.index(b), ya.index(Y)]) for Y in range(2097, 2103)} for b in (1990, 2000, 2010, 2020)}}
    for b in (1990, 2000, 2010, 2020):
        for Y in range(2097, 2103):
            row('model', 'model', 'birth_year', b, Y, 'uniform', 'tropical', reset['model_birth_years'][b][Y], 'startarot')
    calc = {'fields': ['birth_unix_s', 'natal_longitude_deg'] + [f'return_{Y}_unix_s' for Y in range(2026, 2031)],
            'rows': misc['calculator'],
            'note': 'births uniform in UT 1925-2025; return nearest to the UT birthday of each year at 12:00 UT (29 February -> '
                    '1 March), found by root finding on swisseph (apparent tropical longitude), rounded to the second'}
    vsop = None
    if VSOP_FILE.exists():
        ser, _ = read_vsop()
        vsop = {'min_amplitude': VSOP_MIN_AMPLITUDE, 'L': [[[float(f'{a:.11g}'), round(b, 8), round(c, 8)] for a, b, c in blk] for blk in ser['L']],
                'R': [[[float(f'{a:.11g}'), round(b, 8), round(c, 8)] for a, b, c in blk] for blk in ser['R']],
                'check': misc['vsop'],
                'note': 'VSOP87D Earth, heliocentric ecliptic of date; terms with |A| >= min_amplitude (rad for L, au for R), '
                        'grouped by power of tau (Julian millennia TT from J2000)'}
    totals = {cc: {'birth_years': real[cc]['birth_years'], 'births': real[cc]['births'], 'feb29_births': real[cc]['feb29_births']} for cc in ('BR', 'JP', 'US')}
    totals['real_births'] = sum(real[cc]['births'] for cc in ('BR', 'JP', 'US'))
    totals['model'] = {'birth_years': [MODEL_YEARS[0], MODEL_YEARS[-1]], 'printed': [ob[0], ob[-1]]}
    totals['wpp'] = {'world_2028': world['pop_2028'], 'world_18plus_2028': world['pop18_2028'], 'countries': len(crow)}
    J = dict(
        generated_by='scripts/research/cosmic_birthday.py', slug=SLUG,
        definitions={'outcome': 'local date of the solar return minus the birthday date in that year (-1 = day before)',
                     'clock_shift': 'local clock time of the return minus the local clock time of birth, minutes',
                     'sun': 'apparent geocentric tropical longitude, Swiss Ephemeris (SEFLG_SWIEPH)',
                     'spontaneous': 'local-hour profile of spontaneous-onset births, Brazil SINASC (PARTO=1 & STTRABPART=2)'},
        totals=totals, real=real, model=model, countries=countries, world=agg, moving=moving, sidereal=sidereal,
        example_people=example_people, leap_day=leap_day, reset_2100=reset, calculator_checks=calc,
        hypotheses=[dict(id=h['id'], text=h['text'], verdict=h['verdict'], detail=h['detail']) for h in hy],
        added_after_count=ADDED_AFTER_COUNT,
        independent_recount=INDEPENDENT_RECOUNT,
        validation=dict(passed=sum(c['ok'] for c in val['checks']), total=len(val['checks']), checks=val['checks']),
        sources=SOURCES,
        spontaneous_profile_pct=(100 * m['profile']).tolist(),
    )
    J = _r(J)                                                    # shares to 4 decimals
    J['calculator_checks']['rows'] = misc['calculator']          # keep 6-decimal longitudes and whole seconds
    J['vsop87d_earth'] = vsop                                    # full precision of the series
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(J, ensure_ascii=False, separators=(',', ':')) + '\n')
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['section', 'area', 'group', 'key', 'return_year', 'time_profile', 'zodiac', 'outcome_days', 'metric', 'value', 'source'])
        w.writerows(csv_rows)
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB, {len(csv_rows)} rows)'
        + (f', {SCRIPT_COPY}' if SCRIPT_COPY else ''))


def _with_tables(fn, *need):
    def run():
        WORK.mkdir(parents=True, exist_ok=True)
        tabs = [SunTable(False), SunTable(True)][:len(need)]
        fn(*tabs)
        log(f'{fn.__name__} done, peak RSS {rss_mb():.0f} MB')
    return run


def main():
    steps = {
        'fetch': fetch, 'fetch-wpp': fetch_wpp, 'fetch-vsop': fetch_vsop,
        'compute': compute_all,
        'compute-br': _with_tables(compute_br, 't'), 'compute-jp': _with_tables(compute_jp, 't'),
        'compute-us': _with_tables(compute_us, 't'), 'compute-model': _with_tables(compute_model, 't', 's'),
        'compute-wpp': compute_wpp, 'compute-misc': _with_tables(compute_misc, 't', 's'),
        'validate': lambda: validate(), 'export': lambda: export(),
    }
    arg = sys.argv[1] if len(sys.argv) == 2 else ''
    if arg not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    ok = steps[arg]()
    sys.exit(1 if ok is False else 0)


if __name__ == '__main__':
    main()
