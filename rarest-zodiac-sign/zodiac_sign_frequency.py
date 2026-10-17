#!/usr/bin/env python3
"""How common is each zodiac sign? Births by Sun sign in the countries that publish births by month.

Source of the numbers on https://startarot.online/research/rarest-zodiac-sign

Needs Python 3.10+ and
    pip install numpy pandas pyarrow scipy pyswisseph openpyxl pyreaddbc dbfread
(pyreaddbc and dbfread only for Brazil). The raw data (about 1.5 GB to download, 30 MB kept) go to
$ZODIAC_DATA (default: ./zodiac-sign-data next to this script). Steps, in order:

    python3 zodiac_sign_frequency.py fetch      # all sources (resumable; Brazil's FTP is slow)
    python3 zodiac_sign_frequency.py compute    # sign counts per country-year -> $ZODIAC_DATA/counts.parquet
    python3 zodiac_sign_frequency.py validate   # error of every estimation step, measured on daily data
    python3 zodiac_sign_frequency.py export     # page JSON + dataset CSV (+ a copy of this script in the repo)

Sub-steps: fetch-eurostat|fetch-stff|fetch-france|fetch-ew|fetch-us|fetch-br|fetch-jp. If you already
have the SINASC parquet files of birth_sky.py (startarot.online/research/real-births-chart-frequencies),
point $SINASC_PARQUET at their folder and fetch-br reads them instead of the FTP.

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/zodiac-sign-frequency.json     data the page renders
    frontend/static/research/zodiac-sign-frequency.csv       the open dataset (long format)
    frontend/static/research/zodiac_sign_frequency.py        a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

What is counted
---------------
The Sun's sign at the moment of birth, tropical and sidereal (Lahiri), for every live birth of a
country-year whose births are published by DATE OF OCCURRENCE. Sign ingresses are computed with Swiss
Ephemeris (built-in Moshier ephemeris; seconds of error, irrelevant at day resolution) and converted
to the country's civil clock with the IANA tz database (one zone per country: the most populous one;
for the USA the Central zone, nearest the population-weighted mean offset).
On the day of an ingress the births of that day are split by the share of the local day before and
after the ingress instant (time uniform over the day; error measured on Brazil's recorded times).

Where daily counts are published (France, England and Wales, the USA 1969–1988 and 1994–2014, Brazil,
Japan 2015–2024) the count is exact up to that split. Everywhere else monthly counts are spread over days:
a monotone cubic through the cumulative monthly totals (mean-preserving, continuous across years),
times a calendar-day and weekday template, renormalised to each month's total. The template is the
mean log ratio of daily births to the same smooth curve in the six daily series of five countries
(equal weight per country). Its error is measured by leaving each daily country out (``validate``): that measured
error is published as the uncertainty of the monthly countries, and signs closer than it are ties.

Expected share without any seasonality = the share of the calendar spent with the Sun in the sign
(the same days of the same years). Signs differ in length by up to 2 days because Earth's orbit is
elliptical: that alone makes winter signs rarer, and the page separates it from seasonality.

Sources and their limits
------------------------
Eurostat demo_fmonth — live births by month of occurrence, 1960–2024 (country coverage varies),
CC BY 4.0. Germany = DE_TOT (incl. the former GDR), France 1960–1967 = FX (metropolitan).
Human Fertility Database, Short-Term Fertility Fluctuations (STFF), CC BY 4.0 — from 2000, preferred
over Eurostat where both exist. Only the years STFF's metadata calls final (and by date of
occurrence), with all 12 months: e.g. Russia 2000–2020 (from 2021 STFF carries births by month of
registration), Slovakia 2000–2015. For a country STFF covers, Eurostat years after STFF's last final
year are not used either: they are the same preliminary national figures (Slovakia 2016–2024,
Poland 2023–2024, the 2024 figures of Italy, Spain, the Netherlands, Ireland, Lithuania, ...).
Not used, because the national series counts births by month of REGISTRATION: Taiwan, Ukraine,
Azerbaijan (a registration month shifts births by up to several weeks, more than a sign's width
matters). INSEE T79JNAIS — daily births, metropolitan France 1968–2024, Licence Ouverte 2.0.
ONS Births in England and Wales 2025, table 12 — daily births 1995–2024, OGL v3.0.
US daily births 1969–1988: NCHS natality files (U.S. government work) summed by day from the Google
BigQuery public natality sample (a 50 % sample, weighted, in some states and years — every count of
1969–1971 is even), as distributed with A. Vehtari's Birthdays case study
(github.com/avehtari/casestudies); yearly totals within 0.5 % of NCHS's published ones. 1994–2014: FiveThirtyEight
`births` (CC BY 4.0) — CDC/NCHS rows for 1994–2003, SSA rows for 2004–2014 (SSA counts run about 2 %
above CDC, with a jump in 2000). No US data for 1989–1993.
SINASC (Ministério da Saúde / DATASUS) — every Brazilian live birth 1997–2024 by date (1996, the
system's first and incomplete year, is left out) (and from 2006
hour); OpenDataSUS publishes it under CC BY-ND 3.0: we publish aggregates only.
e-Stat table 0003411915 (Vital Statistics of Japan) — daily births 2015–2024, Government of Japan
Standard Terms of Use (compatible with CC BY 4.0).
Priority per country-year: daily > STFF > Eurostat. Countries with under 100,000 births in total are
kept in the CSV but left out of the rankings. Nothing here describes people born elsewhere or in
other years; the pooled figures are weighted by births, so large countries and recent decades count
most.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import gzip
import html
import http.cookiejar
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'rarest-zodiac-sign'
FILE_STEM = 'zodiac-sign-frequency'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'zodiac_sign_frequency.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('ZODIAC_DATA') or HERE / 'zodiac-sign-data')
RAW = DATA / 'raw'
UA = 'Mozilla/5.0 (research script; startarot.online)'

SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius',
         'Capricorn', 'Aquarius', 'Pisces']
ZODIACS = ['tropical', 'sidereal']
LAST_YEAR = 2024
MIN_BIRTHS_RANKED = 100_000
# Ties: a sign shares the rarest/commonest place if it is within the measurement margin of it in at
# least this share of BOOTSTRAP resamples of the country-years (see ``export``).
TIE_SHARE = 0.25
BOOTSTRAP = 400
J1970 = 2440587.5

# code: (name, IANA zone of the most populous part, region, hemisphere)
ENTITIES = {
    'AT': ('Austria', 'Europe/Vienna', 'Western Europe', 'N'),
    'BE': ('Belgium', 'Europe/Brussels', 'Western Europe', 'N'),
    'CH': ('Switzerland', 'Europe/Zurich', 'Western Europe', 'N'),
    'DE': ('Germany', 'Europe/Berlin', 'Western Europe', 'N'),
    'FR': ('France (metropolitan)', 'Europe/Paris', 'Western Europe', 'N'),
    'IE': ('Ireland', 'Europe/Dublin', 'Western Europe', 'N'),
    'LI': ('Liechtenstein', 'Europe/Vaduz', 'Western Europe', 'N'),
    'LU': ('Luxembourg', 'Europe/Luxembourg', 'Western Europe', 'N'),
    'MC': ('Monaco', 'Europe/Monaco', 'Western Europe', 'N'),
    'NL': ('Netherlands', 'Europe/Amsterdam', 'Western Europe', 'N'),
    'UK': ('United Kingdom', 'Europe/London', 'Western Europe', 'N'),
    'DK': ('Denmark', 'Europe/Copenhagen', 'Northern Europe', 'N'),
    'EE': ('Estonia', 'Europe/Tallinn', 'Northern Europe', 'N'),
    'FI': ('Finland', 'Europe/Helsinki', 'Northern Europe', 'N'),
    'IS': ('Iceland', 'Atlantic/Reykjavik', 'Northern Europe', 'N'),
    'LT': ('Lithuania', 'Europe/Vilnius', 'Northern Europe', 'N'),
    'LV': ('Latvia', 'Europe/Riga', 'Northern Europe', 'N'),
    'NO': ('Norway', 'Europe/Oslo', 'Northern Europe', 'N'),
    'SE': ('Sweden', 'Europe/Stockholm', 'Northern Europe', 'N'),
    'AD': ('Andorra', 'Europe/Andorra', 'Southern Europe', 'N'),
    'AL': ('Albania', 'Europe/Tirane', 'Southern Europe', 'N'),
    'BA': ('Bosnia and Herzegovina', 'Europe/Sarajevo', 'Southern Europe', 'N'),
    'CY': ('Cyprus', 'Asia/Nicosia', 'Southern Europe', 'N'),
    'EL': ('Greece', 'Europe/Athens', 'Southern Europe', 'N'),
    'ES': ('Spain', 'Europe/Madrid', 'Southern Europe', 'N'),
    'HR': ('Croatia', 'Europe/Zagreb', 'Southern Europe', 'N'),
    'IT': ('Italy', 'Europe/Rome', 'Southern Europe', 'N'),
    'ME': ('Montenegro', 'Europe/Podgorica', 'Southern Europe', 'N'),
    'MK': ('North Macedonia', 'Europe/Skopje', 'Southern Europe', 'N'),
    'MT': ('Malta', 'Europe/Malta', 'Southern Europe', 'N'),
    'PT': ('Portugal', 'Europe/Lisbon', 'Southern Europe', 'N'),
    'RS': ('Serbia', 'Europe/Belgrade', 'Southern Europe', 'N'),
    'SI': ('Slovenia', 'Europe/Ljubljana', 'Southern Europe', 'N'),
    'SM': ('San Marino', 'Europe/San_Marino', 'Southern Europe', 'N'),
    'XK': ('Kosovo', 'Europe/Belgrade', 'Southern Europe', 'N'),
    'BG': ('Bulgaria', 'Europe/Sofia', 'Eastern Europe', 'N'),
    'BY': ('Belarus', 'Europe/Minsk', 'Eastern Europe', 'N'),
    'CZ': ('Czechia', 'Europe/Prague', 'Eastern Europe', 'N'),
    'HU': ('Hungary', 'Europe/Budapest', 'Eastern Europe', 'N'),
    'MD': ('Moldova', 'Europe/Chisinau', 'Eastern Europe', 'N'),
    'PL': ('Poland', 'Europe/Warsaw', 'Eastern Europe', 'N'),
    'RO': ('Romania', 'Europe/Bucharest', 'Eastern Europe', 'N'),
    'RU': ('Russia', 'Europe/Moscow', 'Eastern Europe', 'N'),
    'SK': ('Slovakia', 'Europe/Bratislava', 'Eastern Europe', 'N'),
    'AM': ('Armenia', 'Asia/Yerevan', 'Western Asia', 'N'),
    'GE': ('Georgia', 'Asia/Tbilisi', 'Western Asia', 'N'),
    'IL': ('Israel', 'Asia/Jerusalem', 'Western Asia', 'N'),
    'TR': ('Türkiye', 'Europe/Istanbul', 'Western Asia', 'N'),
    'JP': ('Japan', 'Asia/Tokyo', 'East and Southeast Asia', 'N'),
    'KR': ('South Korea', 'Asia/Seoul', 'East and Southeast Asia', 'N'),
    'SG': ('Singapore', 'Asia/Singapore', 'East and Southeast Asia', 'N'),
    'CA': ('Canada', 'America/Toronto', 'North America', 'N'),
    'GL': ('Greenland', 'America/Nuuk', 'North America', 'N'),
    'US': ('United States', 'America/Chicago', 'North America', 'N'),
    'BR': ('Brazil', 'America/Sao_Paulo', 'South America', 'S'),
    'CL': ('Chile', 'America/Santiago', 'South America', 'S'),
    'AU': ('Australia', 'Australia/Sydney', 'Oceania', 'S'),
    'NZ': ('New Zealand', 'Pacific/Auckland', 'Oceania', 'S'),
}
# Eurostat geo -> entity (aggregates, DE without the GDR, FR with overseas from 1994 are not used)
EUROSTAT_GEO = {g: g for g in ENTITIES if g not in ('FR', 'DE', 'JP', 'KR', 'SG', 'CA', 'GL', 'US', 'BR', 'CL',
                                                     'AU', 'NZ', 'IL')}
EUROSTAT_GEO.update({'DE_TOT': 'DE', 'FX': 'FR'})
EUROSTAT_NOT_USED = {'UA': 'Ukraine: national monthly series by month of registration',
                     'AZ': 'Azerbaijan: national monthly series by month of registration'}
# STFF code -> (entity, first year, last year): only years that STFF metadata gives by date of
# OCCURRENCE (Slovakia from 2016 and Russia after 2020 are by month of registration; Poland's
# 2023–2024 by month of occurrence but year of registration, marked as to be replaced)
_EU_STFF = {'AUT': 'AT', 'BEL': 'BE', 'BGR': 'BG', 'CHE': 'CH', 'CZE': 'CZ', 'DNK': 'DK', 'ESP': 'ES', 'EST': 'EE',
            'FIN': 'FI', 'GRC': 'EL', 'HRV': 'HR', 'HUN': 'HU', 'IRL': 'IE', 'ISL': 'IS', 'ITA': 'IT', 'LTU': 'LT',
            'LUX': 'LU', 'LVA': 'LV', 'NLD': 'NL', 'NOR': 'NO', 'PRT': 'PT', 'ROU': 'RO', 'SRB': 'RS', 'SVN': 'SI',
            'SWE': 'SE', 'DEUTNP': 'DE'}
# Last year STFF metadata (23.02.2026) calls FINAL; later years are preliminary — incomplete (late
# registrations) or by month of registration.
STFF_FINAL = {'AUT': 2024, 'BEL': 2024, 'BGR': 2024, 'CHE': 2024, 'CZE': 2024, 'DNK': 2024, 'ESP': 2023,
              'EST': 2024, 'FIN': 2024, 'GRC': 2023, 'HRV': 2024, 'HUN': 2024, 'IRL': 2023, 'ISL': 2024,
              'ITA': 2023, 'LTU': 2023, 'LUX': 2024, 'LVA': 2024, 'NLD': 2023, 'NOR': 2024, 'PRT': 2024,
              'ROU': 2023, 'SRB': 2024, 'SVN': 2024, 'SWE': 2024, 'DEUTNP': 2024, 'AUS': 2023, 'CAN': 2023,
              'CHL': 2022, 'ISR': 2023, 'JPN': 2024, 'KOR': 2023, 'NZL': 2024, 'SGP': 2024, 'USA': 2024,
              'GRL': 2024, 'RUS': 2020, 'GBR_NP': 2022, 'SVK': 2015, 'POL': 2022}
STFF_CODES = {code: (ent, 2000, STFF_FINAL[code]) for code, ent in _EU_STFF.items()}
STFF_CODES.update({'AUS': ('AU', 2000, STFF_FINAL['AUS']), 'CAN': ('CA', 2000, STFF_FINAL['CAN']),
                   'CHL': ('CL', 2000, STFF_FINAL['CHL']), 'ISR': ('IL', 2000, STFF_FINAL['ISR']),
                   'JPN': ('JP', 2000, STFF_FINAL['JPN']), 'KOR': ('KR', 2000, STFF_FINAL['KOR']),
                   'NZL': ('NZ', 2000, STFF_FINAL['NZL']), 'SGP': ('SG', 2000, STFF_FINAL['SGP']),
                   'USA': ('US', 2000, STFF_FINAL['USA']), 'GRL': ('GL', 2000, STFF_FINAL['GRL']),
                   'RUS': ('RU', 2000, STFF_FINAL['RUS']), 'GBR_NP': ('UK', 2006, STFF_FINAL['GBR_NP']),
                   'SVK': ('SK', 2000, STFF_FINAL['SVK']), 'POL': ('PL', 2000, STFF_FINAL['POL'])})
# Series known to count births by month of REGISTRATION: the calibration of the weekday test below.
REGISTRATION_CONTROLS = {('Eurostat', 'UA'), ('Eurostat', 'AZ'), ('HFD STFF', 'TWN'), ('HFD STFF', 'UKR')}
# Weekday test: a registration office works Monday to Friday, so a series by month of registration
# grows with the number of working days in the month almost one for one (elasticity ≈ 1); births by
# date of occurrence barely do (scheduled births give 0.1–0.3). Series above this are not used.
MAX_WEEKDAY_ELASTICITY = 0.40
# Year-end step (log births per day) above which a country-decade is marked: four times the largest
# step of any decade of the daily series (0.05). Not used to drop data — the counts cannot tell
# births timed into January from births recorded there.
YEAR_END_STEP = 0.20
# An entity-year whose births of unknown month exceed this share of the year is not used.
MAX_UNKNOWN_MONTH = 0.02
STFF_NOT_USED = {'TWN': 'Taiwan: births by month of registration',
                 'UKR': 'Ukraine: births by month of registration'}
# Brazil from 1997: SINASC started in 1996 and covered about three quarters of that year's births,
# with coverage growing within the year (January 4 % below the later Januaries).
DAILY = {'FR': (1968, 2024), 'UK_EW': (1995, 2024), 'US_1969': (1969, 1988), 'US': (1994, 2014), 'BR': (1997, 2024),
         'JP': (2015, 2024)}
# series of one country share a weight in the calendar template and leave the validation together
DAILY_COUNTRY = {'US_1969': 'US'}
DAILY_TZ = {'FR': 'Europe/Paris', 'UK_EW': 'Europe/London', 'US': 'America/Chicago', 'US_1969': 'America/Chicago',
            'BR': 'America/Sao_Paulo', 'JP': 'Asia/Tokyo'}
DAILY_NAME = {'FR': 'metropolitan France', 'UK_EW': 'England and Wales', 'US': 'the USA', 'US_1969': 'the USA',
              'BR': 'Brazil', 'JP': 'Japan'}
# daily series that ARE an entity of the tables (England and Wales is only part of the UK)
DAILY_AS_ENTITY = {'FR': 'FR', 'US_1969': 'US', 'US': 'US', 'BR': 'BR', 'JP': 'JP'}


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ downloads
def curl(url: str, dest: Path, tries: int = 8) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + '.part')
    for _ in range(tries):
        r = subprocess.run(['curl', '-sSL', '-f', '-A', UA, '-m', '3600', '-C', '-', '-o', str(tmp), url])
        if r.returncode == 0:
            tmp.rename(dest)
            return
        time.sleep(5)
    raise RuntimeError(f'download failed: {url}')


def fetch_eurostat():
    gz = RAW / 'demo_fmonth.tsv.gz'
    curl('https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/demo_fmonth?format=TSV&compressed=true', gz)


def fetch_stff():
    curl('https://www.humanfertility.org/File/GetDocumentFree/STFF/stff.csv', RAW / 'stff.csv')


def fetch_france():
    curl('https://www.insee.fr/fr/statistiques/fichier/8582123/T79jnais.csv', RAW / 'fr_T79jnais.csv')


def fetch_ew():
    curl('https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/'
         'datasets/birthsinenglandandwalesbirthregistrations/2025/2025birthregistrations.xlsx', RAW / 'ew2025.xlsx')


def fetch_us():
    base = 'https://raw.githubusercontent.com/fivethirtyeight/data/master/births/'
    curl(base + 'US_births_1994-2003_CDC_NCHS.csv', RAW / 'US_births_1994-2003_CDC_NCHS.csv')
    curl(base + 'US_births_2000-2014_SSA.csv', RAW / 'US_births_2000-2014_SSA.csv')
    curl('https://raw.githubusercontent.com/avehtari/casestudies/master/Birthdays/data/births_usa_1969.csv',
         RAW / 'births_usa_1969.csv')


def fetch_br():
    """Brazil: births per local date and hour, one CSV per year (from DTNASC and HORANASC)."""
    out_dir = RAW / 'br'
    out_dir.mkdir(parents=True, exist_ok=True)
    reuse = os.environ.get('SINASC_PARQUET')
    for y in range(DAILY['BR'][0], DAILY['BR'][1] + 1):
        out = out_dir / f'br_{y}.csv'
        if out.exists():
            continue
        if reuse and (Path(reuse) / f'sinasc_{y}.parquet').exists():
            df = pd.read_parquet(Path(reuse) / f'sinasc_{y}.parquet')
            if 'HORANASC' not in df:  # files before 2006 carry no birth time
                df['HORANASC'] = pd.Series(pd.NA, index=df.index, dtype='string')
            df = df[['DTNASC', 'HORANASC']]
        else:
            import pyreaddbc
            from dbfread import DBF
            dbc = out_dir / f'DNBR{y}.dbc'
            dbf = out_dir / f'DNBR{y}.dbf'
            curl(f'ftp://ftp.datasus.gov.br/dissemin/publicos/SINASC/1996_/Dados/DNRES/DNBR{y}.dbc', dbc)
            pyreaddbc.dbc2dbf(str(dbc), str(dbf))
            rows = [(r.get('DTNASC'), r.get('HORANASC')) for r in  # HORANASC is absent before 2006
                    DBF(str(dbf), encoding='iso-8859-1', load=False, char_decode_errors='replace')]
            df = pd.DataFrame(rows, columns=['DTNASC', 'HORANASC']).astype('string')
            dbf.unlink()
            dbc.unlink()
        date = pd.to_datetime(df.DTNASC, format='%d%m%Y', errors='coerce')
        hh = pd.to_numeric(df.HORANASC.str.slice(0, 2), errors='coerce')
        mm = pd.to_numeric(df.HORANASC.str.slice(2, 4), errors='coerce')
        hour = hh.where((hh >= 0) & (hh < 24) & (mm >= 0) & (mm < 60) & (df.HORANASC.str.len() == 4))
        t = pd.DataFrame({'date': date, 'hour': hour.fillna(-1).astype(int)}).dropna(subset=['date'])
        t = t[t.date.dt.year == y]
        t.groupby(['date', 'hour']).size().rename('n').reset_index().to_csv(out, index=False)
        log(f'BR {y}: {len(t):,} births with a valid date')


ESTAT_SID = '0003411915'


def _estat_opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [('User-Agent', UA)]
    op.open(f'https://www.e-stat.go.jp/dbview?sid={ESTAT_SID}').read()
    return op


def _estat_days(op, year, month):
    """National births per day of one month (e-Stat dbview; replicates the page's own request)."""
    enc = lambda o: base64.b64encode(gzip.compress(json.dumps(o, ensure_ascii=False, separators=(',', ':')).encode())).decode()
    sid = ESTAT_SID
    matter = lambda mid, tbl, disp, **kw: {'matterId': mid, 'tableName': tbl, 'dispTableName': f'S9N8B_{sid}_{disp}', **kw}
    item = lambda code, name='': {'name': name, 'code': code, 'explanation': ''}
    tops = [matter(18, 'MH_HS9N8B_0000000001', 'HS', positionNum=1, allSelected=1, listData=[item('10040', '出生数')]),
            matter(6, 'MH_BU9N8B_0001059317', 'BUN04', positionNum=2, allSelected=1, listData=[item('000000')]),
            matter(2, 'MH_TMY9N8B_0001006171', 'TIME', positionNum=3, allSelected=1, listData=[item(f'{year}000000')]),
            matter(5, 'MH_BU9N8B_0001059308', 'BUN03', positionNum=4, allSelected=0, listData=[item(f'{100 + 10 * month:05d}')])]
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
    out = []
    for tr in re.findall(r'<tr>(.*?)</tr>', res['table'], re.S):
        cells = [html.unescape(re.sub(r'<[^>]+>', '', c)).strip() for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', tr, re.S)]
        if len(cells) >= 26 and '総数' not in cells[-26]:
            v = cells[-25]
            out.append((int(cells[-26].replace('日', '')), int(v.replace(',', '')) if v not in ('-', '…', '') else 0))
    return out


def fetch_jp():
    """Japan, births per day: one request per month (e-Stat answers an occasional request with a
    server error — retried with a fresh session); finished years are cached, so a rerun resumes."""
    dest = RAW / 'jp_daily.csv'
    if dest.exists():
        return
    part_dir = RAW / 'jp'
    part_dir.mkdir(parents=True, exist_ok=True)
    op = None
    for y in range(DAILY['JP'][0], DAILY['JP'][1] + 1):
        part = part_dir / f'jp_{y}.csv'
        if part.exists():
            continue
        rows = []
        for m in range(1, 13):
            for attempt in range(6):
                try:
                    op = op or _estat_opener()
                    days = _estat_days(op, y, m)
                    break
                except Exception as exc:  # noqa: BLE001 — any failure of the remote view: retry
                    if attempt == 5:
                        raise
                    log(f'JP {y}-{m:02d}: {exc}; retrying')
                    op = None
                    time.sleep(10 * (attempt + 1))
            rows += [(f'{y}-{m:02d}-{d:02d}', n) for d, n in days if n]
            time.sleep(0.7)
        pd.DataFrame(rows, columns=['date', 'n']).to_csv(part, index=False)
        log(f'JP {y} fetched')
    pd.concat([pd.read_csv(f) for f in sorted(part_dir.glob('jp_*.csv'))]).to_csv(dest, index=False)


# ------------------------------------------------------------------ readers
def read_eurostat(raw: bool = False) -> pd.DataFrame:
    """Monthly births. ``raw``: every geo, every value, with month 'UNK' and 'TOTAL' and the flag.
    Otherwise used geos only, months 1–12, provisional values ('p') of the last two years dropped."""
    t = pd.read_csv(RAW / 'demo_fmonth.tsv.gz', sep='\t', dtype=str)
    key = t.columns[0]
    parts = t[key].str.split(',', expand=True)
    parts.columns = ['freq', 'unit', 'month', 'geo']
    t = pd.concat([parts, t.drop(columns=key)], axis=1)
    t = t.melt(id_vars=['freq', 'unit', 'month', 'geo'], var_name='year', value_name='v')
    t['year'] = t.year.str.strip().astype(int)
    t['flag'] = t.v.str.extract(r'([a-z]+)\s*$')[0].fillna('')
    t['v'] = pd.to_numeric(t.v.str.replace(r'[^0-9.]', '', regex=True), errors='coerce')
    t = t[t.v.notna()].rename(columns={'v': 'births'})
    if raw:
        return t[['geo', 'year', 'month', 'births', 'flag']]
    t = t[t.month.str.match(r'^M\d\d$') & t.geo.isin(EUROSTAT_GEO)]
    # 'p' (provisional) matters only in a series' last two years: older years keep a flag nobody
    # cleared (Denmark 1996–1997, Czechia 1996) and have no other source
    last = t.groupby('geo').year.transform('max')
    t = t[~(t.flag.str.contains('p') & (t.year >= last - 1))]
    t['month'] = t.month.str[1:].astype(int)
    t['entity'] = t.geo.map(EUROSTAT_GEO)
    return t[['entity', 'year', 'month', 'births']]


def unknown_month_share() -> pd.DataFrame:
    """entity, year, source, share of the year's births with unknown month."""
    e = read_eurostat(raw=True)
    e = e[e.geo.isin(EUROSTAT_GEO)]
    w = e.pivot_table(index=['geo', 'year'], columns='month', values='births', aggfunc='sum')
    known = w[[f'M{m:02d}' for m in range(1, 13)]].sum(axis=1, min_count=12)
    unk = w['UNK'].fillna(0) if 'UNK' in w else 0
    out = pd.DataFrame({'unknown': unk, 'known': known}).dropna().reset_index()
    out = out.assign(entity=out.geo.map(EUROSTAT_GEO), source='Eurostat')
    s = pd.read_csv(RAW / 'stff.csv', na_values='.')
    rows = []
    for code, (ent, y0, y1) in STFF_CODES.items():
        for _, r in s[(s.CountryCode == code) & s.Year.between(y0, y1)].iterrows():
            known = float(sum(r[m] for m in ['January', 'February', 'March', 'April', 'May', 'June', 'July',
                                              'August', 'September', 'October', 'November', 'December']))
            total = float(r.TOT) if pd.notna(r.TOT) else known
            # unknown = what the twelve months miss of the annual total (UNK is often left empty)
            rows.append((ent, int(r.Year), 'HFD STFF', max(total - known, 0.0), known))
    st = pd.DataFrame(rows, columns=['entity', 'year', 'source', 'unknown', 'known'])
    out = pd.concat([out[['entity', 'year', 'source', 'unknown', 'known']], st[['entity', 'year', 'source', 'unknown', 'known']]])
    out['share'] = out.unknown / (out.unknown + out.known)
    return out


def weekday_elasticity(g: pd.DataFrame) -> tuple[float, float, int]:
    """How monthly counts follow the number of Monday–Friday days in the month: slope of log births
    per day on log(weekday share of the month), with year and calendar-month effects removed.
    ≈ 1 for counts by registration (offices closed at weekends), 0.1–0.3 for births by date.
    Outlier years (``suspect_years``) are left out first: Belarus with its January 2005 at a third
    of normal scores 0.67, without that year 0.34."""
    g = g[g.births > 0].copy()
    full = g.groupby('year').month.nunique()
    g = g[g.year.isin(full[full == 12].index)]
    if g.year.nunique() >= 3:
        bad = suspect_years(g.assign(entity='x', source='x'))
        g = g[~g.year.isin(bad.year)]
    if g.year.nunique() < 3:
        return float('nan'), float('nan'), int(g.year.nunique())
    first = pd.to_datetime(dict(year=g.year, month=g.month, day=1))
    dim = first.dt.days_in_month.values
    wdays = np.array([np.sum(pd.date_range(f, periods=n).weekday < 5) for f, n in zip(first, dim)])
    y = np.log(g.births.values / dim)
    x = np.log(wdays / dim)
    yr, mo = g.year.values, g.month.values
    def demean(v):
        v = v.copy()
        for _ in range(20):
            v -= pd.Series(v).groupby(yr).transform('mean').values
            v -= pd.Series(v).groupby(mo).transform('mean').values
        return v
    yd, xd = demean(y), demean(x)
    beta = float((xd * yd).sum() / (xd * xd).sum())
    resid = yd - beta * xd
    dof = max(len(y) - g.year.nunique() - 12, 1)
    se = float(np.sqrt((resid ** 2).sum() / dof / (xd * xd).sum()))
    return beta, se, int(g.year.nunique())


def registration_screen(daily: dict[str, pd.Series]) -> pd.DataFrame:
    """Weekday elasticity of every monthly series (used and not), of the known registration-month
    series and of the daily series summed to months (known occurrence)."""
    rows = []
    e = read_eurostat(raw=True)
    e = e[e.month.str.match(r'^M\d\d$') & (e.geo.isin(EUROSTAT_GEO) | e.geo.isin(EUROSTAT_NOT_USED))]
    e = e.assign(month=e.month.str[1:].astype(int))
    for geo, g in e.groupby('geo'):
        b, se, n = weekday_elasticity(g)
        kind = 'registration (known)' if ('Eurostat', geo) in REGISTRATION_CONTROLS else 'monthly'
        rows.append(('Eurostat', geo, EUROSTAT_GEO.get(geo), kind, b, se, n))
    st = pd.read_csv(RAW / 'stff.csv', na_values='.')
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
              'October', 'November', 'December']
    def stff_rows(code, y0, y1):
        out = []
        for _, r in st[(st.CountryCode == code) & st.Year.between(y0, y1)].iterrows():
            out += [(int(r.Year), i, r[m]) for i, m in enumerate(months, start=1)]
        return pd.DataFrame(out, columns=['year', 'month', 'births']).dropna()
    for code, (ent, y0, y1) in STFF_CODES.items():
        b, se, n = weekday_elasticity(stff_rows(code, y0, y1))
        rows.append(('HFD STFF', code, ent, 'monthly', b, se, n))
    for code in STFF_NOT_USED:
        b, se, n = weekday_elasticity(stff_rows(code, 2000, LAST_YEAR))
        rows.append(('HFD STFF', code, None, 'registration (known)', b, se, n))
    b, se, n = weekday_elasticity(stff_rows('RUS', 2021, LAST_YEAR))
    rows.append(('HFD STFF', 'RUS 2021+', None, 'registration (known)', b, se, n))
    for key, s in daily.items():
        m = s.resample('MS').sum()
        g = pd.DataFrame({'year': m.index.year, 'month': m.index.month, 'births': m.values})
        b, se, n = weekday_elasticity(g)
        rows.append((DAILY_SOURCE[key], key, DAILY_AS_ENTITY.get(key), 'occurrence (daily)', b, se, n))
    return pd.DataFrame(rows, columns=['source', 'series', 'entity', 'kind', 'elasticity', 'se', 'years'])


def read_stff() -> pd.DataFrame:
    s = pd.read_csv(RAW / 'stff.csv', na_values='.')
    months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
              'October', 'November', 'December']
    rows = []
    for code, (ent, y0, y1) in STFF_CODES.items():
        for _, r in s[(s.CountryCode == code) & s.Year.between(y0, y1)].iterrows():
            for i, m in enumerate(months, start=1):
                rows.append((ent, int(r.Year), i, r[m]))
    return pd.DataFrame(rows, columns=['entity', 'year', 'month', 'births']).dropna()


def read_daily(key: str) -> pd.Series:
    if key == 'FR':
        f = pd.read_csv(RAW / 'fr_T79jnais.csv', sep=';', dtype=str)
        f = f[(f.CHAMP2 == 'FM') & (f.JOUR != 'MM') & (f.NBNAIS != 'so')]  # 'so' = no such date
        idx = pd.to_datetime(f.ANNEE_1968_2024 + '-' + f.MOIS + '-' + f.JOUR, errors='coerce')
        s = pd.Series(f.NBNAIS.astype(int).values, index=idx)
    elif key == 'UK_EW':
        import openpyxl
        ws = openpyxl.load_workbook(RAW / 'ew2025.xlsx', read_only=True)['Table_12']
        rows = list(ws.iter_rows(values_only=True))
        h = [i for i, r in enumerate(rows) if r[0] == 'Date'][0]
        hdr, out = rows[h], {}
        for r in rows[h + 1:]:
            if not r[0] or '/' not in str(r[0]):
                continue
            dd, mm = map(int, str(r[0]).split('/'))
            for c, yr in enumerate(hdr[2:], start=2):
                if isinstance(r[c], (int, float)):
                    try:
                        out[pd.Timestamp(year=int(yr), month=mm, day=dd)] = int(r[c])
                    except ValueError:
                        pass
        s = pd.Series(out)
    elif key == 'US':
        a = pd.read_csv(RAW / 'US_births_1994-2003_CDC_NCHS.csv')
        b = pd.read_csv(RAW / 'US_births_2000-2014_SSA.csv')
        t = pd.concat([a[a.year < 2004], b[b.year >= 2004]])
        s = pd.Series(t.births.values, index=pd.to_datetime(dict(year=t.year, month=t.month, day=t.date_of_month)))
    elif key == 'US_1969':
        t = pd.read_csv(RAW / 'births_usa_1969.csv')
        s = pd.Series(t.births.values, index=pd.to_datetime(dict(year=t.year, month=t.month, day=t.day)))
    elif key == 'BR':
        t = pd.concat([pd.read_csv(f, parse_dates=['date']) for f in sorted((RAW / 'br').glob('br_*.csv'))])
        s = t.groupby('date').n.sum()
    elif key == 'JP':
        t = pd.read_csv(RAW / 'jp_daily.csv', parse_dates=['date'])
        s = pd.Series(t.n.values, index=t.date)
    else:
        raise KeyError(key)
    s = s[~s.index.isna()].sort_index()
    s = s[~s.index.duplicated()]
    y0, y1 = DAILY[key]
    s = s[(s.index.year >= y0) & (s.index.year <= y1)].astype(float)
    full = pd.date_range(s.index[0], s.index[-1])
    if len(full) != len(s):
        raise RuntimeError(f'{key}: {len(full) - len(s)} missing days')
    return s


def br_hour_profile() -> pd.DataFrame:
    """Brazil 2006–2024: births per date × local hour (hour −1 = no valid time)."""
    t = pd.concat([pd.read_csv(f, parse_dates=['date']) for f in sorted((RAW / 'br').glob('br_*.csv'))])
    return t[t.date.dt.year >= 2006]


# ------------------------------------------------------------------ astronomy
_swe = None


def swe():
    global _swe
    if _swe is None:
        import swisseph
        swisseph.set_sid_mode(swisseph.SIDM_LAHIRI)
        _swe = swisseph
    return _swe


_ING = {}


def ingresses(sidereal: bool):
    """(jd_ut array, sign entered array) for 1958–2027."""
    if sidereal in _ING:
        return _ING[sidereal]
    s = swe()
    flag = s.FLG_MOSEPH | (s.FLG_SIDEREAL if sidereal else 0)
    jd = s.julday(1958, 1, 1)
    end = s.julday(2027, 1, 1)
    k = int(s.calc_ut(jd, s.SUN, flag)[0][0] // 30)
    jds, ks = [], []
    while True:
        k = (k + 1) % 12
        jd = s.solcross_ut(30.0 * k, jd, flag)
        if jd > end:
            break
        jds.append(jd)
        ks.append(k)
        jd += 1
    _ING[sidereal] = (np.array(jds), np.array(ks))
    return _ING[sidereal]


def day_bounds_jd(dates: pd.DatetimeIndex, tz: str) -> tuple[np.ndarray, np.ndarray]:
    z = ZoneInfo(tz)
    days = list(dates) + [dates[-1] + pd.Timedelta(days=1)]
    jd = np.array([J1970 + dt.datetime(d.year, d.month, d.day, tzinfo=z).timestamp() / 86400 for d in days])
    return jd[:-1], jd[1:]


def sign_fractions(dates: pd.DatetimeIndex, tz: str, sidereal: bool, shift_hours: float = 0.0,
                   hour_weights: np.ndarray | None = None) -> np.ndarray:
    """[n_days, 12] share of each local civil day's births with the Sun in each sign.
    Births are uniform over the real length of the day unless ``hour_weights`` [n_days, 24] (local
    clock hours) are given. ``shift_hours`` moves the zone (sensitivity test)."""
    ing_jd, ing_k = ingresses(sidereal)
    start, end = day_bounds_jd(dates, tz)
    start = start - shift_hours / 24
    end = end - shift_hours / 24
    i0 = np.searchsorted(ing_jd, start, side='right') - 1
    sign0 = ing_k[i0]
    F = np.zeros((len(dates), 12))
    F[np.arange(len(dates)), sign0] = 1.0
    j = i0 + 1
    has = ing_jd[j] < end
    for i in np.where(has)[0]:
        f = (ing_jd[j[i]] - start[i]) / (end[i] - start[i])
        if hour_weights is not None and hour_weights[i].sum() > 0:
            w = hour_weights[i] / hour_weights[i].sum()
            x = f * 24
            h = int(x)
            f = w[:h].sum() + (w[h] * (x - h) if h < 24 else 0)
        F[i, sign0[i]] = f
        F[i, ing_k[j[i]]] += 1 - f
    return F


# ------------------------------------------------------------------ monthly -> daily
def smooth_daily(mon: pd.Series) -> pd.Series:
    """Mean-preserving daily curve: monotone cubic (PCHIP) through cumulative monthly totals,
    per contiguous run of months."""
    from scipy.interpolate import PchipInterpolator
    mon = mon.sort_index()
    runs, cur = [], [mon.index[0]]
    for a, b in zip(mon.index[:-1], mon.index[1:]):
        if (b.year - a.year) * 12 + b.month - a.month == 1:
            cur.append(b)
        else:
            runs.append(cur)
            cur = [b]
    runs.append(cur)
    out = []
    for run in runs:
        m = mon.loc[run]
        edges = list(m.index) + [m.index[-1] + pd.offsets.MonthBegin(1)]
        x = np.array([(e - edges[0]).days for e in edges], float)
        c = np.concatenate([[0], np.cumsum(m.values)])
        idx = pd.date_range(edges[0], edges[-1] - pd.Timedelta(days=1))
        if len(run) == 1:
            out.append(pd.Series(m.values[0] / len(idx), index=idx))
            continue
        p = PchipInterpolator(x, c)
        out.append(pd.Series(np.diff(p(np.arange(len(idx) + 1, dtype=float))), index=idx))
    return pd.concat(out)


def calendar_template(daily: dict[str, pd.Series]) -> tuple[pd.Series, pd.Series]:
    """Calendar-day (MM-DD) and weekday log-effects relative to the smooth curve, equal weight per
    daily series, fitted jointly by alternating means."""
    by_country = {}
    for key, s in daily.items():
        base = smooth_daily(s.resample('MS').sum()).reindex(s.index)
        by_country.setdefault(DAILY_COUNTRY.get(key, key), []).append(np.log(s / base))
    parts = []
    for rs in by_country.values():  # equal weight per country: each contributes its mean over its years
        r = pd.concat(rs)
        parts.append((r, r.index.strftime('%m-%d'), r.index.weekday))
    h = pd.Series(0.0, index=sorted({m for _, md, _ in parts for m in md}))
    w = pd.Series(0.0, index=range(7))
    for _ in range(10):
        h = pd.concat([(r - w.reindex(wd).values).groupby(md).mean() for r, md, wd in parts], axis=1).mean(axis=1)
        w = pd.concat([(r - h.reindex(md).values).groupby(wd).mean() for r, md, wd in parts], axis=1).mean(axis=1)
    return h, w


def monthly_to_daily(mon: pd.Series, h: pd.Series, w: pd.Series) -> pd.Series:
    base = smooth_daily(mon)
    idx = base.index
    est = base * np.exp(h.reindex(idx.strftime('%m-%d')).fillna(0).values + w.reindex(idx.weekday).values)
    per = idx.to_period('M')
    est = est / est.groupby(per).transform('sum').values * mon.reindex(per.to_timestamp()).values
    return est


def sign_table(daily: pd.Series, tz: str, **kw) -> pd.DataFrame:
    """Births per (year, zodiac, sign) from a daily series."""
    out = []
    for z in ZODIACS:
        F = sign_fractions(daily.index, tz, z == 'sidereal', **kw)
        t = pd.DataFrame(F * daily.values[:, None], columns=SIGNS)
        t['year'] = daily.index.year
        g = t.groupby('year').sum()
        out.append(g.stack().rename('births').reset_index().rename(columns={'level_1': 'sign'}).assign(zodiac=z))
    return pd.concat(out)


def day_share_table(years: list[int], tz: str) -> pd.DataFrame:
    """Share of each calendar year spent with the Sun in each sign (the no-seasonality expectation)."""
    idx = pd.date_range(f'{min(years)}-01-01', f'{max(years)}-12-31')
    idx = idx[idx.year.isin(years)]
    return sign_table(pd.Series(1.0, index=idx), tz).rename(columns={'births': 'days'})


# ------------------------------------------------------------------ compute
def load_all_daily() -> dict[str, pd.Series]:
    return {k: read_daily(k) for k in DAILY}


def monthly_sources(screen: pd.DataFrame | None = None) -> pd.DataFrame:
    """entity, year, month, births, source — one source per entity-year (daily > STFF > Eurostat),
    complete years only, after the data-basis screens (weekday test, unknown months, outlier
    years); what each screen removed is written to $ZODIAC_DATA/excluded_years.csv."""
    e = read_eurostat().assign(source='Eurostat')
    s = read_stff().assign(source='HFD STFF')
    removed = []
    # For a country STFF covers, Eurostat years after STFF's last FINAL year are the same
    # preliminary national figures STFF leaves out (Slovakia 2016–2024 by month of registration,
    # Poland 2023–2024, most 2024 values): not used either.
    stff_last = {}
    for code, (ent, y0, y1) in STFF_CODES.items():
        stff_last[ent] = max(stff_last.get(ent, 0), y1)
    late = e.entity.map(stff_last).notna() & (e.year > e.entity.map(stff_last))
    for (ent, y), g in e[late & (e.year <= LAST_YEAR)].groupby(['entity', 'year']):
        if g.month.nunique() == 12:
            removed.append((ent, int(y), 'Eurostat', 'after the last final HFD year', float(stff_last[ent]),
                            int(g.births.sum())))
    e = e[~late]
    t = pd.concat([e, s])
    t = t[t.year <= LAST_YEAR]
    # 1. series that behave like counts by month of registration
    if screen is not None:
        bad = screen[(screen.kind == 'monthly') & (screen.elasticity > MAX_WEEKDAY_ELASTICITY) & screen.entity.notna()]
        for _, r in bad.iterrows():
            hit = (t.source == r.source) & (t.entity == r.entity)
            for y in sorted(t[hit].year.unique()):
                removed.append((r.entity, int(y), r.source, 'weekday test', round(float(r.elasticity), 2),
                                int(t[hit & (t.year == y)].births.sum())))
            t = t[~hit]
    # 2. years with many births of unknown month
    unk = unknown_month_share()
    unk = unk[unk.share > MAX_UNKNOWN_MONTH]
    for _, r in unk.iterrows():
        hit = (t.source == r.source) & (t.entity == r.entity) & (t.year == r.year)
        if hit.any():
            removed.append((r.entity, int(r.year), r.source, 'unknown month', round(float(r.share) * 100, 1),
                            int(t[hit].births.sum())))
            t = t[~hit]
    full = t.groupby(['entity', 'year', 'source']).month.nunique()
    full = full[full == 12].reset_index()[['entity', 'year', 'source']]
    t = t.merge(full)
    # HFD STFF first: its curators check the date basis country by country; Eurostat's monthly table
    # carries a few registration-month years (e.g. Germany and Ireland 2002, Slovakia 2008)
    rank = {'HFD STFF': 0, 'Eurostat': 1}
    best = full.assign(r=full.source.map(rank)).sort_values('r').drop_duplicates(['entity', 'year'])
    t = t.merge(best[['entity', 'year', 'source']])
    daily_years = {(DAILY_AS_ENTITY[k], y) for k, (y0, y1) in DAILY.items() if k in DAILY_AS_ENTITY
                   for y in range(y0, y1 + 1)}
    # Brazil 1996 (partial first year of SINASC) is not replaced by anything either
    daily_years |= {('BR', 1996)}
    keep = [(a, b) not in daily_years for a, b in zip(t.entity, t.year)]
    t = t[keep]
    # 3. outlier years
    out = suspect_years(t)
    for _, r in out.iterrows():
        removed.append((r.entity, int(r.year), r.source, f'outlier month {int(r.month)}', float(r.deviation_pct), int(r.births)))
    pd.DataFrame(removed, columns=['entity', 'year', 'source', 'reason', 'value', 'births']).to_csv(
        DATA / 'excluded_years.csv', index=False)
    drop = set(zip(out.entity, out.year))
    return t[[(a, b) not in drop for a, b in zip(t.entity, t.year)]]


def suspect_years(t: pd.DataFrame, rel: float = 0.20, z: float = 5.0) -> pd.DataFrame:
    """Entity-years whose monthly profile breaks from the neighbouring years (±3) in a way no real
    birth cohort does: some month more than ``rel`` off the neighbours' median profile (per day) and
    more than ``z`` Poisson sigmas. Catches registration-month and keying errors (Belarus January
    2005 at a third of normal, Poland December 1995); real shocks such as the COVID-19 dip in Spain,
    December 2020 – January 2021 (−17 %), stay below it."""
    t = t.assign(dim=pd.to_datetime(dict(year=t.year, month=t.month, day=1)).dt.days_in_month)
    out = []
    for ent, g in t.groupby('entity'):
        P = g.pivot_table(index='year', columns='month', values='births')
        D = g.pivot_table(index='year', columns='month', values='dim')
        r = (P / D).div((P / D).sum(axis=1), axis=0)
        for y in P.index:
            nb = [k for k in P.index if k != y and abs(k - y) <= 3]
            if len(nb) < 2:  # at the edge of a series or after a gap: the four nearest years
                nb = sorted((k for k in P.index if k != y), key=lambda k: abs(k - y))[:4]
            if len(nb) < 2:
                continue
            exp = r.loc[nb].median() * D.loc[y]
            exp = exp / exp.sum() * P.loc[y].sum()
            dev = (P.loc[y] - exp) / exp
            zz = (P.loc[y] - exp) / np.sqrt(exp)
            hit = (dev.abs() > rel) & (zz.abs() > z)
            if hit.any():
                m = int(dev.abs()[hit].idxmax())
                out.append((ent, int(y), g.source.iloc[0], m, round(float(dev[m]) * 100, 1), int(P.loc[y].sum())))
    return pd.DataFrame(out, columns=['entity', 'year', 'source', 'month', 'deviation_pct', 'births'])


def compute():
    daily = load_all_daily()
    screen = registration_screen(daily)
    screen.to_csv(DATA / 'registration_screen.csv', index=False)
    h, w = calendar_template(daily)
    pd.DataFrame({'log_effect': h}).to_csv(DATA / 'template_calendar_day.csv')
    pd.DataFrame({'log_effect': w}).to_csv(DATA / 'template_weekday.csv')
    rows = []
    for key, ent in DAILY_AS_ENTITY.items():
        t = sign_table(daily[key], ENTITIES[ent][1])
        rows.append(t.assign(entity=ent, method='daily', source=DAILY_SOURCE[key]))
    mon = monthly_sources(screen)
    for (ent, src), g in mon.groupby(['entity', 'source']):
        m = g.assign(d=pd.to_datetime(dict(year=g.year, month=g.month, day=1))).set_index('d').births.sort_index()
        est = monthly_to_daily(m, h, w)
        rows.append(sign_table(est, ENTITIES[ent][1]).assign(entity=ent, method='monthly', source=src))
        log(f'{ent} {src}: {m.index.year.min()}–{m.index.year.max()}, {int(m.sum()):,} births')
    counts = pd.concat(rows, ignore_index=True)
    # Year-end step: the jump in births per day from December to January, minus the mean of the
    # neighbouring steps (November to December, January to February). A smooth season gives about
    # zero; births moved, or dates recorded, from December into January give a step.
    jd = []
    def year_end_steps(m: pd.Series):
        r = np.log(m / m.index.days_in_month)
        for y in sorted(set(m.index.year)):
            keys = [pd.Timestamp(a, b, 1) for a, b in ((y, 11), (y, 12), (y + 1, 1), (y + 1, 2))]
            if all(k in r.index for k in keys):
                nov, dec, jan, feb = (r[k] for k in keys)
                yield int(y), float((jan - dec) - ((dec - nov) + (feb - jan)) / 2)
    for key, s in daily.items():
        for y, v in year_end_steps(s.resample('MS').sum()):
            jd.append((key, DAILY_AS_ENTITY.get(key), 'daily', y, v))
    for ent, g in mon.groupby('entity'):
        m = g.assign(d=pd.to_datetime(dict(year=g.year, month=g.month, day=1))).set_index('d').births.sort_index()
        for y, v in year_end_steps(m):
            jd.append((ent, ent, 'monthly', y, v))
    pd.DataFrame(jd, columns=['series', 'entity', 'method', 'year', 'step']).to_csv(
        DATA / 'year_end_step.csv', index=False)
    # disagreement between the two monthly sources on the years both have
    h_w = (h, w)
    e_all = read_eurostat().assign(source='Eurostat')
    s_all = read_stff().assign(source='HFD STFF')
    both = e_all.merge(s_all, on=['entity', 'year', 'month'], suffixes=('_e', '_s'))
    full = both.groupby(['entity', 'year']).month.nunique()
    both = both.merge(full[full == 12].reset_index()[['entity', 'year']])
    sdiff = {}
    for ent, g in both.groupby('entity'):
        g = g.assign(d=pd.to_datetime(dict(year=g.year, month=g.month, day=1))).set_index('d').sort_index()
        res = {}
        for z in ZODIACS:
            a = sign_table(monthly_to_daily(g.births_e, *h_w), ENTITIES[ent][1])
            b = sign_table(monthly_to_daily(g.births_s, *h_w), ENTITIES[ent][1])
            sa = shares(a[a.zodiac == z], [])
            sb = shares(b[b.zodiac == z], [])
            res[z] = round(float((sa - sb).abs().values.max()), 3)
        sdiff[ent] = {'years': [int(g.year.min()), int(g.year.max())], 'n_years': int(g.year.nunique()), **res}
    (DATA / 'source_diff.json').write_text(json.dumps(sdiff, indent=1))
    # expectation without seasonality: the same entity-years, by days
    exp = []
    for ent, g in counts.groupby('entity'):
        ys = sorted(g.year.unique())
        exp.append(day_share_table(ys, ENTITIES[ent][1]).assign(entity=ent))
    counts = counts.merge(pd.concat(exp), on=['entity', 'year', 'zodiac', 'sign'])
    counts.to_parquet(DATA / 'counts.parquet')
    log(f'counts: {counts.entity.nunique()} entities, {counts[counts.zodiac == "tropical"].births.sum():,.0f} births')


DAILY_SOURCE = {'FR': 'INSEE (daily)', 'UK_EW': 'ONS (daily)', 'US': 'CDC/SSA via FiveThirtyEight (daily)',
                'US_1969': 'NCHS via Google BigQuery (daily)',
                'BR': 'SINASC (daily)', 'JP': 'e-Stat (daily)'}


# ------------------------------------------------------------------ validate
def shares(t: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    if not by:
        t, by = t.assign(_all=0), ['_all']
    g = t.groupby(by + ['sign']).births.sum().unstack('sign')[SIGNS]
    return g.div(g.sum(axis=1), axis=0) * 100


def validate():
    daily = load_all_daily()
    res = {'leave_one_out': {}, 'timezone_shift': {}, 'within_day': {}, 'overlap': {}}
    for key, s in daily.items():
        others = {k: v for k, v in daily.items() if DAILY_COUNTRY.get(k, k) != DAILY_COUNTRY.get(key, key)}
        h, w = calendar_template(others)
        tz = DAILY_TZ[key]
        exact = sign_table(s, tz)
        mon = s.resample('MS').sum()
        models = {'uniform_within_month': pd.Series(mon.reindex(s.index.to_period('M').to_timestamp()).values
                                                    / s.index.days_in_month, index=s.index),
                  'smooth': smooth_daily(mon).reindex(s.index),
                  'smooth_with_template': monthly_to_daily(mon, h, w).reindex(s.index)}
        out = {}
        for name, est in models.items():
            et = sign_table(est, tz)
            r = {}
            for z in ZODIACS:
                ex, es = exact[exact.zodiac == z], et[et.zodiac == z]
                for per, f in (('year', lambda y: y), ('decade', lambda y: y // 10 * 10), ('all', lambda y: 0)):
                    a = shares(ex.assign(p=ex.year.map(f)), ['p'])
                    b = shares(es.assign(p=es.year.map(f)), ['p'])
                    if per == 'decade':  # complete decades only
                        n = ex.assign(p=ex.year.map(f)).groupby('p').year.nunique()
                        ok = n[n == 10].index
                        a, b = a.loc[ok], b.loc[ok]
                    e = (b - a).abs()
                    r[f'{z}_{per}'] = {'max_pp': round(float(e.values.max()), 3), 'mean_pp': round(float(e.values.mean()), 3)} if len(e) else None
            out[name] = r
        res['leave_one_out'][key] = out
        log(key, json.dumps(out['smooth_with_template']))
        # time-zone sensitivity: ±3 h
        sh = {}
        for d in (-3, 3):
            t = sign_table(s, tz, shift_hours=d)
            e = (shares(t[t.zodiac == 'tropical'], []) - shares(exact[exact.zodiac == 'tropical'], [])).abs()
            sh[f'{d:+d}h'] = round(float(e.values.max()), 3)
        res['timezone_shift'][key] = sh
    # within-day split: Brazil 2006–2024 at recorded hours vs uniform
    hp = br_hour_profile()
    hp = hp[hp.hour >= 0].pivot_table(index='date', columns='hour', values='n', aggfunc='sum').fillna(0)
    hp = hp.reindex(columns=range(24), fill_value=0)
    s = daily['BR']
    s = s[s.index.year >= 2006]
    W = hp.reindex(s.index).fillna(0).values
    uni = sign_table(s, DAILY_TZ['BR'])
    rec = []
    for z in ZODIACS:
        F = sign_fractions(s.index, DAILY_TZ['BR'], z == 'sidereal', hour_weights=W)
        t = pd.DataFrame(F * s.values[:, None], columns=SIGNS).assign(year=s.index.year).groupby('year').sum()
        rec.append(t.stack().rename('births').reset_index().rename(columns={'level_1': 'sign'}).assign(zodiac=z))
    rec = pd.concat(rec)
    for z in ZODIACS:
        a = shares(uni[uni.zodiac == z], ['year'])
        b = shares(rec[rec.zodiac == z], ['year'])
        res['within_day'][z] = {'max_pp_year': round(float((a - b).abs().values.max()), 3),
                                'max_pp_all': round(float((shares(uni[uni.zodiac == z], []) - shares(rec[rec.zodiac == z], [])).abs().values.max()), 3)}
    # Eurostat vs STFF where both have the same entity-year
    e = read_eurostat()
    st = read_stff()
    both = e.merge(st, on=['entity', 'year', 'month'], suffixes=('_e', '_s'))
    full = both.groupby(['entity', 'year']).month.nunique()
    both = both.merge(full[full == 12].reset_index()[['entity', 'year']])
    for ent, g in both.groupby('entity'):
        tot = g.groupby('year')[['births_e', 'births_s']].sum()
        se = g.pivot_table(index='year', columns='month', values='births_e')
        ss = g.pivot_table(index='year', columns='month', values='births_s')
        res['overlap'][ent] = {'years': [int(tot.index.min()), int(tot.index.max())],
                               'max_total_diff_pct': round(float(((tot.births_s / tot.births_e - 1).abs() * 100).max()), 2),
                               'max_month_share_diff_pp': round(float(((ss.div(ss.sum(1), axis=0) - se.div(se.sum(1), axis=0)).abs() * 100).values.max()), 3)}
    (DATA / 'validation.json').write_text(json.dumps(res, indent=1))
    log(json.dumps(res['timezone_shift']), json.dumps(res['within_day']), json.dumps(res['overlap']))


# ------------------------------------------------------------------ export
def r3(x: float) -> float:
    return round(float(x), 3)


def block(t: pd.DataFrame, u: float, ties: tuple[list, list] | None = None) -> dict:
    """Shares of one zodiac for a set of entity-years. Expected = each entity-year's births spread
    over its days (no seasonality), so the sign lengths of exactly those years and places."""
    t = t.assign(total=t.groupby(['entity', 'year']).births.transform('sum'),
                 dtot=t.groupby(['entity', 'year']).days.transform('sum'))
    t = t.assign(exp=t.total * t.days / t.dtot)
    g = t.groupby('sign')[['births', 'exp']].sum().reindex(SIGNS)
    share = g.births / g.births.sum() * 100
    exp = g.exp / g.exp.sum() * 100
    lo, hi = share.min(), share.max()
    return {
        'births': [int(round(v)) for v in g.births],
        'shares': [r3(v) for v in share],
        'expected': [r3(v) for v in exp],
        'index': [round(float(v), 1) for v in share / exp * 100],
        'rarest': ties[0] if ties else [s for s in SIGNS if share[s] - lo <= u],
        'commonest': ties[1] if ties else [s for s in SIGNS if hi - share[s] <= u],
        'rarest_sign': share.idxmin(),
        'commonest_sign': share.idxmax(),
        'ratio': round(float(hi / lo), 3),
    }


def export():
    counts = pd.read_parquet(DATA / 'counts.parquet')
    val = json.loads((DATA / 'validation.json').read_text())
    excluded = pd.read_csv(DATA / 'excluded_years.csv')
    screen = pd.read_csv(DATA / 'registration_screen.csv')
    steps = pd.read_csv(DATA / 'year_end_step.csv')
    steps['decade'] = steps.year // 10 * 10
    sdec = steps.groupby(['series', 'entity', 'method', 'decade'], dropna=False).step.agg(['mean', 'size']).reset_index()
    sdec = sdec.rename(columns={'mean': 'step', 'size': 'n'})
    step_control = float(sdec[(sdec.method == 'daily') & (sdec.n >= 5)].step.abs().max())
    step_flags = {}
    for _, r in sdec[(sdec.method == 'monthly') & (sdec.step > YEAR_END_STEP) & (sdec.n >= 3)].iterrows():
        step_flags.setdefault(r.entity, []).append({'decade': int(r.decade), 'step': round(float(r.step), 3),
                                                    'ratio': round(float(np.exp(r.step)), 2)})
    loo = val['leave_one_out']
    # measured error of the monthly route (leave-one-country-out), and of the daily route (the split
    # of an ingress day at uniform time, measured on Brazil's recorded hours)
    um = {z: {p: max(v['smooth_with_template'][f'{z}_{p}']['max_pp'] for v in loo.values()
                     if v['smooth_with_template'][f'{z}_{p}']) for p in ('year', 'decade', 'all')} for z in ZODIACS}
    ud = {z: {'year': val['within_day'][z]['max_pp_year'], 'decade': val['within_day'][z]['max_pp_year'],
              'all': val['within_day'][z]['max_pp_all']} for z in ZODIACS}

    sdiff = json.loads((DATA / 'source_diff.json').read_text())
    rng = np.random.default_rng(20261017)

    def margin(t: pd.DataFrame, z: str, period: str) -> float:
        """Measurement margin: the measured error of the route (monthly or daily, weighted by
        births) + the disagreement between Eurostat and HFD for the countries in the block
        (weighted by their monthly births)."""
        tz = t[t.zodiac == z]
        fm = tz[tz.method == 'monthly'].births.sum() / tz.births.sum()
        mb = tz[tz.method == 'monthly'].groupby('entity').births.sum()
        src = float(sum(mb[e] * sdiff.get(e, {}).get(z, 0.0) for e in mb.index) / tz.births.sum()) if len(mb) else 0.0
        return round(fm * um[z][period] + (1 - fm) * ud[z][period] + src, 3)

    def ties(tz: pd.DataFrame, u: float) -> tuple[list, list]:
        """Signs tied for rarest / commonest: within the margin ``u`` of the extreme, in the data or
        in at least TIE_SHARE of resamples of the years (within each country, so the mix of
        countries stays fixed). Complete counts have no sampling error, but an order that flips
        from year to year is not a property of the country."""
        P = tz.pivot_table(index=['entity', 'year'], columns='sign', values='births')[SIGNS]
        Y = P.values
        sh0 = Y.sum(axis=0) / Y.sum() * 100
        lo = (sh0 - sh0.min() <= u)
        hi = (sh0.max() - sh0 <= u)
        n = len(Y)
        if n >= 2:
            W = np.zeros((BOOTSTRAP, n))
            ents = P.index.get_level_values(0).values
            for e in np.unique(ents):
                idx = np.where(ents == e)[0]
                W[:, idx] = rng.multinomial(len(idx), np.full(len(idx), 1 / len(idx)), size=BOOTSTRAP)
            B = W @ Y
            sh = B / B.sum(axis=1, keepdims=True) * 100
            lo |= ((sh - sh.min(axis=1, keepdims=True)) <= u).mean(axis=0) >= TIE_SHARE
            hi |= ((sh.max(axis=1, keepdims=True) - sh) <= u).mean(axis=0) >= TIE_SHARE
        return [s for s, k in zip(SIGNS, lo) if k], [s for s, k in zip(SIGNS, hi) if k]

    def both(t: pd.DataFrame, period: str = 'all') -> dict:
        out = {}
        for z in ZODIACS:
            u = margin(t, z, period)
            tz = t[t.zodiac == z]
            out[z] = dict(block(tz, u, ties(tz, u)), uncertainty_pp=u)
        return out

    trop = counts[counts.zodiac == 'tropical']
    totals = trop.groupby('entity').births.sum()
    ranked = [e for e in totals.index if totals[e] >= MIN_BIRTHS_RANKED]

    countries = []
    for ent in sorted(totals.index, key=lambda e: -totals[e]):
        t = counts[counts.entity == ent]
        tt = t[t.zodiac == 'tropical']
        srcs = tt.groupby('source').year.agg(['min', 'max', 'nunique']).reset_index().sort_values('min')
        runs = []  # contiguous runs of years per source, in order
        for src, g in tt.groupby('source'):
            ys = sorted(g.year.unique())
            start = prev = ys[0]
            for y in ys[1:] + [None]:
                if y is None or y != prev + 1:
                    runs.append({'source': src, 'years': [int(start), int(prev)]})
                    start = y
                prev = y if y is not None else prev
        runs.sort(key=lambda r: r['years'][0])
        decades = {}
        for d, g in t.groupby(t.year // 10 * 10):
            n = g.year.nunique()
            b = both(g, 'decade')
            decades[str(int(d))] = {'years': [int(g.year.min()), int(g.year.max())], 'n_years': int(n),
                                    'births': int(round(g[g.zodiac == 'tropical'].births.sum())),
                                    **{z: {'shares': [round(v, 2) for v in b[z]['shares']],
                                           'expected': [round(v, 2) for v in b[z]['expected']],
                                           'rarest': b[z]['rarest'], 'commonest': b[z]['commonest'],
                                           'uncertainty_pp': b[z]['uncertainty_pp']} for z in ZODIACS}}
        name, tz, region, hemi = ENTITIES[ent]
        countries.append({
            'code': ent, 'name': name, 'region': region, 'hemisphere': hemi, 'time_zone': tz,
            'ranked': ent in ranked,
            'years': [int(tt.year.min()), int(tt.year.max())], 'n_years': int(tt.year.nunique()),
            'births': int(round(totals[ent])),
            'monthly_share_pct': round(float(tt[tt.method == 'monthly'].births.sum() / totals[ent] * 100), 1),
            'sources': [{'source': r.source, 'years': [int(r['min']), int(r['max'])], 'n_years': int(r['nunique'])}
                        for _, r in srcs.iterrows()],
            'source_runs': runs,
            **both(t),
            'decades': decades,
            'year_end_step': step_flags.get(ent, []),
            'source_disagreement_pp': sdiff.get(ent),
        })

    rk = counts[counts.entity.isin(ranked)]
    pooled = both(rk)
    by_region = []
    for region in dict.fromkeys(v[2] for v in ENTITIES.values()):
        ents = [e for e in ranked if ENTITIES[e][2] == region]
        if ents:
            g = rk[rk.entity.isin(ents)]
            by_region.append({'region': region, 'countries': ents,
                              'births': int(round(g[g.zodiac == 'tropical'].births.sum())), **both(g)})
    by_hemisphere = {}
    for hemi in ('N', 'S'):
        ents = [e for e in ranked if ENTITIES[e][3] == hemi]
        g = rk[rk.entity.isin(ents)]
        by_hemisphere[hemi] = {'countries': ents, 'births': int(round(g[g.zodiac == 'tropical'].births.sum())), **both(g)}
    # the same countries in every decade: those with every year from 1960
    # the same countries in every decade: every year 1960–2019 (all complete decades); requiring
    # 2024 too dropped Spain, Italy and the Netherlands over one preliminary year
    LONG_RUN = (1960, 2019)
    long_ents = [e for e in ranked
                 if set(range(LONG_RUN[0], LONG_RUN[1] + 1)) <= set(trop[trop.entity == e].year)]
    long_run = []
    for d in range(1960, LAST_YEAR + 1, 10):
        g = rk[rk.entity.isin(long_ents) & (rk.year >= d) & (rk.year < d + 10)]
        long_run.append({'decade': d, 'years': [int(g.year.min()), int(g.year.max())],
                         'births': int(round(g[g.zodiac == 'tropical'].births.sum())), **both(g, 'decade')})
    # pooled by decade over all ranked countries (the mix of countries changes)
    pooled_decades = []
    for d in range(1960, LAST_YEAR + 1, 10):
        g = rk[(rk.year >= d) & (rk.year < d + 10)]
        pooled_decades.append({'decade': d, 'countries': int(g.entity.nunique()),
                               'births': int(round(g[g.zodiac == 'tropical'].births.sum())), **both(g, 'decade')})
    # sign lengths, 1960–2024, in days (geocentric; independent of the zone)
    lengths = {}
    for z in ZODIACS:
        jd, k = ingresses(z == 'sidereal')
        y = np.array([swe().revjul(j)[0] for j in jd])
        dur = np.diff(jd)
        sign = k[:-1]
        ok = (y[:-1] >= 1960) & (y[:-1] <= LAST_YEAR)
        lengths[z] = [round(float(dur[ok & (sign == i)].mean()), 3) for i in range(12)]

    # holidays in the daily series: births on the day against the smooth seasonal curve with the
    # series' own weekday effect, and what the dips take from Capricorn (those days at the curve)
    holidays = []
    HOLI = ['12-24', '12-25', '12-26', '12-31', '01-01']
    for key in ('FR', 'UK_EW', 'US_1969', 'US', 'BR', 'JP'):
        s = read_daily(key)
        base = smooth_daily(s.resample('MS').sum()).reindex(s.index)
        r = np.log(s / base)
        md = s.index.strftime('%m-%d')
        wd = pd.Series(r.values, index=s.index)[~md.isin(HOLI)].groupby(s.index[~md.isin(HOLI)].weekday).mean()
        expect = base * np.exp(wd.reindex(s.index.weekday).values)
        eff = {d: round(float((s[md == d] / expect[md == d]).mean() - 1) * 100, 1) for d in HOLI}
        cf = s.where(~md.isin(HOLI), expect)
        a = sign_table(s, DAILY_TZ[key])
        b = sign_table(cf, DAILY_TZ[key])
        sh = lambda t: shares(t[t.zodiac == 'tropical'], []).iloc[0]
        holidays.append({'series': DAILY_NAME[key], 'years': list(DAILY[key]), 'effect_pct': eff,
                         'capricorn_pp': r3(sh(a)['Capricorn']),
                         'capricorn_without_dips_pp': r3(sh(b)['Capricorn'])})

    # The year of births: births on each calendar day against the year's daily mean, averaged over
    # the years of a daily series; the northern line is the mean of the northern daily countries
    # (the two US series count as one), Brazil is drawn on its own (southern seasons).
    def day_index(s: pd.Series) -> pd.Series:
        r = s / s.groupby(s.index.year).transform('mean')
        return r.groupby(s.index.strftime('%m-%d')).mean()
    day_series = {k: read_daily(k) for k in DAILY}
    us = pd.concat([day_series['US_1969'], day_series['US']])
    north = pd.concat([day_index(day_series['FR']), day_index(day_series['UK_EW']), day_index(us),
                       day_index(day_series['JP'])], axis=1).mean(axis=1)
    brazil = day_index(day_series['BR'])
    md = [d.strftime('%m-%d') for d in pd.date_range('2024-01-01', '2024-12-31')]
    # mean day of the year (0 = 1 January, in a leap-year calendar) of each tropical ingress, UT
    ing_jd, ing_k = ingresses(False)
    starts = {}
    for j, k in zip(ing_jd, ing_k):
        y, m, d, h = swe().revjul(j)
        if 1960 <= y <= LAST_YEAR:
            doy = (dt.date(2024, m, d) - dt.date(2024, 1, 1)).days + h / 24
            starts.setdefault(int(k), []).append(doy)
    calendar = {
        'days': md,
        'north': [round(float(north.get(d, np.nan)) * 100, 2) for d in md],
        'brazil': [round(float(brazil.get(d, np.nan)) * 100, 2) for d in md],
        'north_series': ['metropolitan France', 'England and Wales', 'the USA', 'Japan'],
        # every daily country on its own (the two US series as one), for the chart's toggles
        'series': [{'name': name, 'years': years, 'values': [round(float(v.get(d, np.nan)) * 100, 1) for d in md]}
                   for name, years, v in (('France (metropolitan)', list(DAILY['FR']), day_index(day_series['FR'])),
                                          ('England and Wales', list(DAILY['UK_EW']), day_index(day_series['UK_EW'])),
                                          ('United States', [DAILY['US_1969'][0], DAILY['US'][1]], day_index(us)),
                                          ('Japan', list(DAILY['JP']), day_index(day_series['JP'])),
                                          ('Brazil', list(DAILY['BR']), day_index(day_series['BR'])))],
        'sign_start_day': [round(float(np.mean(starts[k])), 2) for k in range(12)],
    }

    summary = {
        'swisseph_version': swe().version,
        'last_year': LAST_YEAR,
        'births_total': int(round(totals.sum())),
        'births_ranked': int(round(totals[ranked].sum())),
        'countries_total': int(len(totals)),
        'countries_ranked': len(ranked),
        'min_births_ranked': MIN_BIRTHS_RANKED,
        'years': [int(trop.year.min()), int(trop.year.max())],
        'country_years': int(trop.groupby(['entity', 'year']).ngroups),
        'births_daily': int(round(trop[trop.method == 'daily'].births.sum())),
        'births_monthly': int(round(trop[trop.method == 'monthly'].births.sum())),
    }
    excluded_births = int(excluded.births.sum()) if len(excluded) else 0
    out = {
        'signs': SIGNS,
        'zodiacs': ZODIACS,
        'summary': summary,
        'sign_length_days': lengths,
        'pooled': pooled,
        'by_hemisphere': by_hemisphere,
        'by_region': by_region,
        'long_run': {'countries': long_ents, 'years_required': list(LONG_RUN), 'decades': long_run},
        'pooled_decades': pooled_decades,
        'countries': countries,
        'uncertainty': {'monthly_pp': um, 'daily_pp': ud},
        'validation': {
            'leave_one_out': [{'series': DAILY_NAME[k], 'years': list(DAILY[k]), **v} for k, v in loo.items()],
            'timezone_shift_3h_max_pp': max(max(v.values()) for v in val['timezone_shift'].values()),
            'within_day': val['within_day'],
            'eurostat_vs_stff': val['overlap'],
        },
        'holidays': holidays,
        'calendar': calendar,
        'year_end_step': {'flag_above': YEAR_END_STEP, 'daily_max_abs': round(step_control, 3),
                          'daily_max_ratio': round(float(np.exp(step_control)), 3)},
        'registration_screen': {
            'max_elasticity': MAX_WEEKDAY_ELASTICITY,
            'series': [{'source': r.source, 'series': (ENTITIES[r.entity][0] if isinstance(r.entity, str) and r.entity in ENTITIES and r.kind == 'monthly' else (DAILY_NAME.get(r.series) or r.series)),
                        'code': r.series, 'kind': r.kind, 'elasticity': round(float(r.elasticity), 3), 'se': round(float(r.se), 3),
                        'years': int(r.years)} for _, r in screen.dropna(subset=['elasticity']).iterrows()],
        },
        'max_unknown_month_pct': MAX_UNKNOWN_MONTH * 100,
        'ties': {'share_of_resamples': TIE_SHARE, 'resamples': BOOTSTRAP},
        'excluded_years': excluded.assign(name=excluded.entity.map(lambda e: ENTITIES[e][0])).to_dict(orient='records'),
        'excluded_births': excluded_births,
        'not_used': [{'source': 'Eurostat', 'code': c, 'reason': r} for c, r in EUROSTAT_NOT_USED.items()]
                    + [{'source': 'HFD STFF', 'code': c, 'reason': r} for c, r in STFF_NOT_USED.items()],
        'daily_series': [{'series': DAILY_NAME[k], 'years': list(DAILY[k]), 'source': DAILY_SOURCE[k]} for k in DAILY],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    # dataset: one row per country, year, zodiac and sign
    c = counts.copy()
    c['total'] = c.groupby(['entity', 'year', 'zodiac']).births.transform('sum')
    c['dtot'] = c.groupby(['entity', 'year', 'zodiac']).days.transform('sum')
    c['share_pct'] = (c.births / c.total * 100).round(3)
    c['expected_share_pct'] = (c.days / c.dtot * 100).round(3)
    c['country'] = c.entity.map(lambda e: ENTITIES[e][0])
    c['sign_order'] = c.sign.map(SIGNS.index)
    c = c.sort_values(['entity', 'year', 'zodiac', 'sign_order'])
    c['births_estimated'] = c.births.round(1)
    c = c.rename(columns={'entity': 'country_code'})
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    c[['country_code', 'country', 'year', 'zodiac', 'sign', 'births_estimated', 'share_pct', 'expected_share_pct',
       'method', 'source']].to_csv(CSV_OUT, index=False, lineterminator='\n')
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('step', choices=['fetch', 'fetch-eurostat', 'fetch-stff', 'fetch-france', 'fetch-ew', 'fetch-us',
                                     'fetch-br', 'fetch-jp', 'compute', 'validate', 'export'])
    a = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    for name, fn in (('eurostat', fetch_eurostat), ('stff', fetch_stff), ('france', fetch_france), ('ew', fetch_ew),
                     ('us', fetch_us), ('jp', fetch_jp), ('br', fetch_br)):
        if a.step in ('fetch', f'fetch-{name}'):
            fn()
    if a.step == 'compute':
        compute()
    if a.step == 'validate':
        validate()
    if a.step == 'export':
        export()
    return 0


if __name__ == '__main__':
    sys.exit(main())
