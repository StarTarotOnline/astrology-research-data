#!/usr/bin/env python3
"""Which birthdays do parents and doctors pick, and which do they avoid?

A birth that is booked - a planned C-section, an induction - gets a date and an hour from a diary, not from
nature. This script measures how far the calendar of births bends around days that mean something to people:
Friday the 13th, 1 April, Halloween, Valentine's Day, 29 February, "pretty" dates such as 08.08.08 or 12.12.12,
and 06.06.06. It also keeps the hour of birth and the share of births that fall on a weekend.

Sources (all free; only aggregates are published):
  * USA, births per day 1969-1988: NCHS natality files summed by day, as distributed with A. Vehtari's
    "Birthdays" case study (github.com/avehtari/casestudies, births_usa_1969.csv).
  * USA, births per day 1994-2014: FiveThirtyEight `births` (CC BY 4.0) - CDC/NCHS rows 1994-2003, SSA rows
    2004-2014.
  * France (metropolitan), births per day 1968-2024: INSEE, T79jnais.
  * England and Wales, births per day 1995-2024: ONS, birth registrations 2025, Table 12 (OGL v3).
  * Mexico, birth certificates 2008-2025: Secretaría de Salud, DGIS, SINAC open data (one zip per year).
  * Brazil, birth certificates 2011-2024: Ministério da Saúde / DATASUS, SINASC (DNBR<year>.dbc; CC BY-ND 3.0,
    so only aggregates leave this script). The Mexican and Brazilian files are the ones fetched by
    mother_birthday_births.py, which must lie next to this script; they are read from $MOM_BIRTHDAY_DATA.
  * Hours of birth in the USA: the hour profiles already computed by birth_sky.py
    (real-births-chart-frequencies.json, next to this script outside the repository), copied as they are.

Steps (own files go to $CHOSEN_BIRTHDAYS_DATA, default: `chosen-birthdays` next to $MOM_BIRTHDAY_DATA, or
~/startarot-data/chosen-birthdays):
    python3 chosen_birthdays.py fetch      # the four daily series (a few MB)
    python3 chosen_birthdays.py scan       # one pass over the Mexican and Brazilian certificates -> scan/*.npz
    python3 chosen_birthdays.py compute    # -> computed.json and daily.json
    python3 chosen_birthdays.py validate   # sanity checks + the registered hypotheses -> validation.json
    python3 chosen_birthdays.py export     # JSON for the page + CSV + a copy of this script (only if valid)
Needs numpy and pandas (pyarrow for the Brazilian cache).

Method in one paragraph. Every day is compared with the SAME WEEKDAY one, two and three weeks before and after
it (up to six neighbours), skipping neighbours that are themselves special: public holidays of the country, the
days from 23 December to 2 January, and every date this study tests. "Ratio" is births on the day divided by the
mean of its neighbours; a day needs at least three usable neighbours. The noise of that ratio is measured on the
ordinary days of the same series and year (the spread of the log ratio on days that are neither holidays nor
tested dates), and the 95 % interval of a group of days combines those spreads. A tested date that falls on a
public holiday of that country in that year (a Friday the 13th that is Good Friday, 11.11.11 in France) is left
out of its group. Where the certificates say how the baby arrived, births after spontaneous labour are the
control: nobody books them, so their ratio should stay at 1.

Exploration before registration. 19.11.2026: a crude version of the method (neighbours at one and two weeks,
no holiday calendar) on Mexico and Brazil by delivery type - the 13th by weekday, about twenty fixed dates and
about twenty-five repeating dates. 22.11.2026: the same crude version on the USA 1994-2014, all births - Friday
the 13th, 14 February, 1 April, 31 October, 4 July, 25 December, 1 January, 29 February, 06.06.06, 07.07.07,
08.08.08, 09.09.09, 10.10.10, 11.11.11, 12.12.12 and 11 September 2001. Nothing was counted for the USA
1969-1988, France or England and Wales, nor for hours by delivery type in Mexico, nor for weekends. Hypotheses
marked [seen in exploration] were written after seeing a crude number; the rest are blind.
"""

import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'chosen-birthdays'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    DAILY_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}-daily.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'chosen_birthdays.py'
    HOURS_JSON = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / 'real-births-chart-frequencies.json'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    DAILY_OUT = HERE / f'{FILE_STEM}-daily.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
    HOURS_JSON = HERE / 'real-births-chart-frequencies.json'
MOM = Path(os.environ.get('MOM_BIRTHDAY_DATA', Path.home() / 'startarot-data' / 'mom-birthday'))
DATA = Path(os.environ.get('CHOSEN_BIRTHDAYS_DATA') or (
    MOM.parent / 'chosen-birthdays' if 'MOM_BIRTHDAY_DATA' in os.environ else Path.home() / 'startarot-data' / 'chosen-birthdays'))
RAW = DATA / 'raw'

MX_YEARS = list(range(2008, 2026))
BR_YEARS = list(range(2011, 2025))
BR_TYPED_FROM = 2012  # labour and C-section timing fields are filled from the 2011 form on; 2011 is partial
MX_TYPED_MIN = 0.90  # a Mexican year is "typed" when at least this share of C-sections says planned/emergency

# ---------------------------------------------------------------------------------------------------------
# Registered hypotheses. The text is not edited after registration (the data test compares it with the
# registered copy); anything decided after the count goes to ADDED_AFTER_COUNT.
# "Ratio" = births on the day(s) / mean of the same weekday one to three weeks either side (see the method).
# "Upper end" / "lower end" = ends of the 95 % interval. Repeating dates are written day.month.year.
HYPOTHESES = {
    'H1': '[seen in exploration] USA 1994-2014, all births, Friday the 13th: ratio at most 0.97, and the 13th on '
          'the other six weekdays taken together is closer to 1 than Friday is.',
    'H2': 'USA 1969-1988, all births, Friday the 13th: ratio below 1.00 and closer to 1 than in 1994-2014.',
    'H3': 'France 1968-2024 and England and Wales 1995-2024, all births, Friday the 13th: ratio below 1.00 in '
          'both, with the upper end below 1.00 in at least one of them.',
    'H4': '[seen in exploration] Friday the 13th where the day is booked and where it is not: Mexico, planned '
          'C-sections (typed years) at most 0.92 and Brazil, C-sections before labour at most 0.92; Brazil, '
          'vaginal births after spontaneous labour within 0.98-1.02.',
    'H5': '[seen in exploration] USA 1994-2014, all births: Halloween (31 October) at most 0.92, Valentine\'s Day '
          '(14 February) at least 1.03, 1 April at most 0.97, 29 February at most 0.95.',
    'H6': 'USA 1969-1988, all births: each of the four dates of H5 is on the same side of 1 as in 1994-2014 and '
          'closer to 1.',
    'H7': 'France and England and Wales, all births: 1 April below 1.00 in both, and 29 February below 1.00 in '
          'both.',
    'H8': '[seen in exploration] USA, repeating dates: each of 07.07.07, 08.08.08, 09.09.09, 10.10.10, 11.11.11 and '
          '12.12.12 at least 1.10, and 06.06.06 at most 0.90.',
    'H9': 'USA, earlier repeating dates: the four dates 02.02.02, 03.03.03, 04.04.04 and 05.05.05 taken together '
          'at least 1.03; 09.09.99 at least 1.03; 07.07.77 and 08.08.88 taken together at least 1.02.',
    'H10': 'Repeating dates outside the USA: in France and in England and Wales the dates 07.07.07 to 12.12.12 '
           'taken together (without those that are a public holiday there) at least 1.03, and 06.06.06 below '
           '1.00 in both countries.',
    'H11': '[seen in exploration] Brazil, C-sections before labour: 20.02.2020 and 22.02.2022 each at least 1.20 '
           'and 12.12.12 at least 1.10; all C-sections on 11.11.11 at least 1.10 (the fields that separate '
           'C-sections before labour start in 2012); on 20.02.2020, 22.02.2022 and 12.12.12 vaginal births after '
           'spontaneous labour stay within 0.95-1.05, and on 11.11.11 all vaginal births do.',
    'H12': '[seen in exploration] Mexico: on Mother\'s Day (10 May) planned C-sections (typed years) at most 0.70; '
           'on Valentine\'s Day C-sections in private hospitals at least 1.10.',
    'H13': 'The hour: at least 85 % of Mexican planned C-sections (typed years) and at least 80 % of Brazilian '
           'C-sections before labour are born between 07:00 and 18:59, against at most 60 % of Mexican vaginal '
           'births and at most 60 % of Brazilian vaginal births after spontaneous labour.',
    'H14': 'The weekend: births on an average Saturday or Sunday, relative to an average Tuesday-Thursday, were at '
           'least 0.90 in the USA in 1969-1973 and at most 0.75 in 2010-2014; in France at least 0.90 in 1968-1972 '
           'and at most 0.85 in 2020-2024.',
    'H15': 'The season: with weekdays, holidays and tested dates taken out, the smoothed curve of births by day of '
           'the year peaks in September in the USA 1994-2014 (a conception around the turn of the year) and does '
           'not peak in September in France 1968-2024.',
}
HYPOTHESES_SHA256 = '55f8bdf1'  # first 8 hex of sha256(json.dumps(HYPOTHESES, sort_keys=True)); set at registration
ADDED_AFTER_COUNT = {
    'A1': '[after count] A repeating date that is itself a public holiday cannot be read against ordinary days: '
          '11.11.11 was Veterans Day in the USA and Armistice Day in France. By the registered method such a date '
          'drops out, so H8 is judged on the dates that can be tested and says so. For the page the date is read '
          'against the SAME holiday in other years instead (the ratio of the day divided by the mean ratio of '
          'that holiday on the same kind of day - weekday or weekend - in the other years of the series). Only the '
          'other years in which that calendar date was a public holiday too are used: 05.05.05 in France was '
          'Ascension, a movable feast, and among the other years only 2016 had it on 5 May. That comparison was '
          'not registered.',
    'A2': '[after count] The registered intervals were too narrow, and the validation step caught it: dates that mean '
          'nothing fell outside them almost half of the time. Averaged over twenty to fifty years the day-to-day '
          'noise shrinks to a few tenths of a percent, but a fixed date keeps a small bias of its own - the season '
          'bends, so a day near the September peak sits above the mean of its neighbours (22 September: +1.5 to '
          '+3 % in every country), and births pushed off a tested date land next to it. Intervals of groups of '
          'days are therefore taken from PLACEBO FAMILIES measured in the same series: for a fixed date, every '
          'calendar date that is never a holiday, a tested date nor one of the four placebo dates (those are checked '
          'against the family, so they stay out of it); for the 13th on a weekday, the same weekday on the 4th-10th '
          'and the 16th-26th of the month. The interval of a tested group is its ratio divided by the 97.5th and by '
          'the 2.5th percentile of the family, each taken relative to the median of the family (1.96 standard '
          'deviations where the family has fewer than 100 groups). Single repeating dates keep the registered '
          'single-day noise. Hypotheses that name an end of an interval (H3) are judged with the corrected intervals.',
    'A3': '[after count] For a single repeating date the page also says how many ORDINARY days of the same series '
          'had a lower ratio: a plain rank, added after the independent '
          'recount asked how unusual 06.06.06 is among days that mean nothing.',
}
# Numbers of the independent recount (22.11.2026), as it gave them: its own code, its own and STRICTER holiday list
# (US federal holidays with their observed days only; this script also sets aside Good Friday to Easter Monday, the
# days around Thanksgiving and 23 December - 2 January). This script does not compute them; the page prints them
# with that attribution. Totals of births matched exactly (85,386,227 and 70,485,508).
INDEPENDENT_RECOUNT = {
    'us_1994': {'friday_13th': 0.9453, 'friday_13th_days': 35, 'april_1': 0.9434, 'halloween': 0.8778,
                'leap_day': 0.9198, '2006-06-06': 0.8493, '2012-12-12': 1.1767, 'weekend_2009': 0.5911},
    'us_1969': {'friday_13th': 0.9725, 'friday_13th_days': 34, 'halloween': 0.9675, 'weekend_1969': 0.8762},
}

GESTATION_DAYS = 266  # conception to birth, the usual average (38 weeks); used only to label the season curve


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------------- fetch
SOURCES = {
    'fr_T79jnais.csv': 'https://www.insee.fr/fr/statistiques/fichier/8582123/T79jnais.csv',
    'ew2025.xlsx': 'https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/livebirths/'
                   'datasets/birthsinenglandandwalesbirthregistrations/2025/2025birthregistrations.xlsx',
    'US_births_1994-2003_CDC_NCHS.csv': 'https://raw.githubusercontent.com/fivethirtyeight/data/master/births/'
                                        'US_births_1994-2003_CDC_NCHS.csv',
    'US_births_2000-2014_SSA.csv': 'https://raw.githubusercontent.com/fivethirtyeight/data/master/births/'
                                   'US_births_2000-2014_SSA.csv',
    'births_usa_1969.csv': 'https://raw.githubusercontent.com/avehtari/casestudies/master/Birthdays/data/'
                           'births_usa_1969.csv',
}


def fetch():
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = {'fetched_on': dt.date.today().isoformat(), 'files': {}}
    for name, url in SOURCES.items():
        dest = RAW / name
        if not dest.exists() or dest.stat().st_size == 0:
            log('fetch', name)
            subprocess.run(['curl', '-sL', '-m', '600', '-A', 'Mozilla/5.0', '-o', str(dest), url], check=True)
        manifest['files'][name] = {'sha256': hashlib.sha256(dest.read_bytes()).hexdigest(), 'bytes': dest.stat().st_size,
                                   'url': url}
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    log('fetch done')


def xlsx_rows(path, sheet_name):
    """Rows of one sheet of an .xlsx as lists of strings/numbers (standard library only)."""
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
          'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
          'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns):
            shared.append(''.join(t.text or '' for t in si.iter('{%s}t' % ns['m'])))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rid = next(s.get('{%s}id' % ns['r']) for s in wb.find('m:sheets', ns) if s.get('name') == sheet_name)
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    target = next(r.get('Target') for r in rels.findall('p:Relationship', ns) if r.get('Id') == rid)
    target = target.lstrip('/')
    sheet = ET.fromstring(z.read(target if target.startswith('xl/') else 'xl/' + target))

    def col(ref):
        n = 0
        for ch in re.match(r'[A-Z]+', ref).group(0):
            n = n * 26 + ord(ch) - 64
        return n - 1

    rows = []
    for row in sheet.iter('{%s}row' % ns['m']):
        cells = {}
        for c in row.findall('m:c', ns):
            v = c.find('m:v', ns)
            if c.get('t') == 'inlineStr':
                val = ''.join(t.text or '' for t in c.iter('{%s}t' % ns['m']))
            elif v is None:
                continue
            elif c.get('t') == 's':
                val = shared[int(v.text)]
            else:
                try:
                    val = float(v.text)
                except ValueError:
                    val = v.text
            cells[col(c.get('r'))] = val
        rows.append([cells.get(i) for i in range(max(cells) + 1)] if cells else [])
    return rows


# --------------------------------------------------------------------------------------------- daily series
def read_series(key):
    """Births per day as {date: count} for one of the four all-births series."""
    import csv
    out = {}
    if key == 'fr':
        with (RAW / 'fr_T79jnais.csv').open(encoding='utf-8', errors='replace') as fh:
            for r in csv.DictReader(fh, delimiter=';'):
                if r.get('CHAMP2') != 'FM' or r.get('JOUR') == 'MM' or r.get('NBNAIS') in ('so', '', None):
                    continue
                try:
                    out[dt.date(int(r['ANNEE_1968_2024']), int(r['MOIS']), int(r['JOUR']))] = int(r['NBNAIS'])
                except ValueError:
                    pass
    elif key == 'ew':
        rows = xlsx_rows(RAW / 'ew2025.xlsx', 'Table_12')
        h = next(i for i, r in enumerate(rows) if r and r[0] == 'Date')
        hdr = rows[h]
        for r in rows[h + 1:]:
            if not r or not r[0] or '/' not in str(r[0]):
                continue
            dd, mm = map(int, str(r[0]).split('/'))
            for c in range(2, min(len(hdr), len(r))):
                if isinstance(r[c], float) and hdr[c] is not None:
                    try:
                        out[dt.date(int(float(hdr[c])), mm, dd)] = int(r[c])
                    except ValueError:
                        pass
    elif key == 'us_1994':
        for name, keep in (('US_births_1994-2003_CDC_NCHS.csv', lambda y: y < 2004), ('US_births_2000-2014_SSA.csv', lambda y: y >= 2004)):
            with (RAW / name).open() as fh:
                for r in csv.DictReader(fh):
                    if keep(int(r['year'])):
                        out[dt.date(int(r['year']), int(r['month']), int(r['date_of_month']))] = int(r['births'])
    elif key == 'us_1969':
        with (RAW / 'births_usa_1969.csv').open() as fh:
            for r in csv.DictReader(fh):
                out[dt.date(int(r['year']), int(r['month']), int(r['day']))] = int(float(r['births']))
    else:
        raise KeyError(key)
    return out


SERIES = {
    'us_1969': dict(country='us', name='USA', years=(1969, 1988), group='all births'),
    'us_1994': dict(country='us', name='USA', years=(1994, 2014), group='all births'),
    'fr': dict(country='fr', name='France (metropolitan)', years=(1968, 2024), group='all births'),
    'ew': dict(country='ew', name='England and Wales', years=(1995, 2024), group='all births'),
}

# --------------------------------------------------------------------------------------------- scan (MX, BR)
MX_CELLS = ['vag.priv', 'vag.pub', 'vag.other', 'cs_planned.priv', 'cs_planned.pub', 'cs_planned.other',
            'cs_emerg.priv', 'cs_emerg.pub', 'cs_emerg.other', 'cs_unk.priv', 'cs_unk.pub', 'cs_unk.other',
            'other.priv', 'other.pub', 'other.other']
BR_CELLS = ['vag_spont', 'vag_induced', 'vag_unk', 'cs_prelabour', 'cs_labour', 'cs_unk', 'other']
GROUPS = {
    'mx_all': ('mx', MX_CELLS),
    'mx_vaginal': ('mx', [c for c in MX_CELLS if c.startswith('vag.')]),
    'mx_cs': ('mx', [c for c in MX_CELLS if c.startswith('cs_')]),
    'mx_cs_private': ('mx', [c for c in MX_CELLS if c.startswith('cs_') and c.endswith('.priv')]),
    'mx_cs_public': ('mx', [c for c in MX_CELLS if c.startswith('cs_') and c.endswith('.pub')]),
    'mx_cs_planned': ('mx', [c for c in MX_CELLS if c.startswith('cs_planned.')]),
    'mx_cs_emergency': ('mx', [c for c in MX_CELLS if c.startswith('cs_emerg.')]),
    'br_all': ('br', BR_CELLS),
    'br_vaginal': ('br', ['vag_spont', 'vag_induced', 'vag_unk']),
    'br_vag_spont': ('br', ['vag_spont']),
    'br_vag_induced': ('br', ['vag_induced']),
    'br_cs': ('br', ['cs_prelabour', 'cs_labour', 'cs_unk']),
    'br_cs_prelabour': ('br', ['cs_prelabour']),
    'br_cs_labour': ('br', ['cs_labour']),
}
GROUP_NAME = {
    'mx_all': 'all births', 'mx_vaginal': 'vaginal births', 'mx_cs': 'all C-sections',
    'mx_cs_private': 'C-sections, private hospitals', 'mx_cs_public': 'C-sections, public hospitals',
    'mx_cs_planned': 'planned C-sections', 'mx_cs_emergency': 'emergency C-sections',
    'br_all': 'all births', 'br_vaginal': 'vaginal births', 'br_vag_spont': 'vaginal births after spontaneous labour',
    'br_vag_induced': 'vaginal births after induced labour', 'br_cs': 'all C-sections',
    'br_cs_prelabour': 'C-sections before labour', 'br_cs_labour': 'C-sections in labour',
}


def scan_frame(df, y, cells, counts, hours, filters):
    """df: kid (datetime), cell (str), hour (int, -1 = unknown). Adds to counts[cell, day of year 0..365] and
    hours[cell, weekend 0/1, hour]."""
    import numpy as np
    n0 = len(df)
    df = df[df['kid'].notna()]
    filters['no valid date'] += n0 - len(df)
    ok = df['kid'].dt.year == y
    filters['born in another year'] += int((~ok).sum())
    df = df[ok]
    doy = (df['kid'].dt.dayofyear - 1).to_numpy()
    wk = (df['kid'].dt.weekday >= 5).to_numpy().astype(int)
    hr = df['hour'].to_numpy()
    for cell, idx in df.groupby('cell', sort=False).indices.items():
        if cell not in cells:
            continue
        ci = cells.index(cell)
        counts[ci] += np.bincount(doy[idx], minlength=366)
        h, w = hr[idx], wk[idx]
        good = h >= 0
        hours[ci] += np.bincount(w[good] * 24 + h[good], minlength=48).reshape(2, 24)


def scan_mx(y, mb):
    import numpy as np
    import pandas as pd
    from collections import Counter
    z, name, enc = mb.open_mx(y)
    with z.open(name) as fh:
        cols = pd.read_csv(io.TextIOWrapper(fh, encoding=enc, errors='replace'), nrows=0).columns.tolist()
    schema = 'long' if 'FECHANACIMIENTOMADRE' in cols else 'short' if 'FECH_NACM' in cols else 'text'
    S = mb.MX_SCHEMAS[schema]
    use = [S[k] for k in ('kid', 'hour', 'deliv', 'cstype', 'place') if S[k]]
    counts = np.zeros((len(MX_CELLS), 366), dtype=np.int64)
    hours = np.zeros((len(MX_CELLS), 2, 24), dtype=np.int64)
    diag = {'schema': schema, 'n_raw': 0, 'filters': Counter(), 'cs_typed': [0, 0]}
    with z.open(name) as fh:
        for ch in pd.read_csv(io.TextIOWrapper(fh, encoding=enc, errors='replace'), usecols=use, dtype=str,
                              keep_default_na=False, chunksize=500_000):
            diag['n_raw'] += len(ch)
            ch = ch.apply(lambda s: s.str.strip())
            df = pd.DataFrame({'kid': mb.parse_dates(ch[S['kid']], '%d/%m/%Y')})
            hh = ch[S['hour']].str.extract(r'^(\d{1,2}):')[0]
            hv = pd.to_numeric(hh, errors='coerce')
            df['hour'] = hv.where(hv.between(0, 23)).fillna(-1).astype(int)
            deliv = np.where(ch[S['deliv']].isin(mb.MX_VAGINAL[schema]), 'vag',
                             np.where(ch[S['deliv']].isin(mb.MX_CS[schema]), 'cs', 'other'))
            if S['cstype']:
                t = ch[S['cstype']]
                cs = np.where(t == '1', 'cs_planned', np.where(t == '2', 'cs_emerg', 'cs_unk'))
                diag['cs_typed'][1] += int(((deliv == 'cs') & t.isin(['1', '2'])).sum())
            else:
                cs = np.full(len(ch), 'cs_unk')
            diag['cs_typed'][0] += int((deliv == 'cs').sum())
            deliv = np.where(deliv == 'cs', cs, deliv)
            place = ch[S['place']]
            sector = np.where(place.isin(mb.MX_PRIVATE[schema]), 'priv', np.where(place.isin(mb.MX_PUBLIC[schema]), 'pub', 'other'))
            df['cell'] = pd.Series(deliv, index=ch.index) + '.' + pd.Series(sector, index=ch.index)
            scan_frame(df, y, MX_CELLS, counts, hours, diag['filters'])
    return counts, hours, diag


def scan_br(y, mb):
    import numpy as np
    import pandas as pd
    from collections import Counter
    raw = pd.read_parquet(MOM / 'br' / f'sinasc_{y}.parquet')
    raw = raw.fillna('').apply(lambda s: s.str.strip())
    for c in ('DTNASC', 'HORANASC', 'PARTO', 'STCESPARTO', 'STTRABPART'):
        if c not in raw:
            raw[c] = ''
    counts = np.zeros((len(BR_CELLS), 366), dtype=np.int64)
    hours = np.zeros((len(BR_CELLS), 2, 24), dtype=np.int64)
    diag = {'schema': 'dnbr', 'n_raw': len(raw), 'filters': Counter(), 'cs_typed': [0, 0]}
    df = pd.DataFrame({'kid': mb.parse_dates(raw['DTNASC'], '%d%m%Y')})
    hh = raw['HORANASC'].str[:2]
    df['hour'] = pd.to_numeric(hh.where(raw['HORANASC'].str.fullmatch(r'([01]\d|2[0-3])[0-5]\d')), errors='coerce').fillna(-1).astype(int)
    p, cs, tr = raw['PARTO'], raw['STCESPARTO'], raw['STTRABPART']
    df['cell'] = np.select(
        [(p == '1') & (tr == '2'), (p == '1') & (tr == '1'), p == '1',
         (p == '2') & (cs == '1'), (p == '2') & (cs == '2'), p == '2'],
        ['vag_spont', 'vag_induced', 'vag_unk', 'cs_prelabour', 'cs_labour', 'cs_unk'], 'other')
    diag['cs_typed'] = [int((p == '2').sum()), int(((p == '2') & cs.isin(['1', '2'])).sum())]
    scan_frame(df, y, BR_CELLS, counts, hours, diag['filters'])
    return counts, hours, diag


def scan():
    import numpy as np
    sys.path.insert(0, str(HERE))
    import mother_birthday_births as mb  # readers of the Mexican and Brazilian files
    out = DATA / 'scan'
    out.mkdir(parents=True, exist_ok=True)
    only = os.environ.get('CHOSEN_BIRTHDAYS_ONLY')  # e.g. "mx:2023" while developing
    for country, years, fn in (('mx', MX_YEARS, scan_mx), ('br', BR_YEARS, scan_br)):
        for y in years:
            if only and f'{country}:{y}' not in only.split(','):
                continue
            npz, js = out / f'{country}_{y}.npz', out / f'{country}_{y}.json'
            if npz.exists() and js.exists():
                continue
            log(f'scan {country} {y}')
            counts, hours, diag = fn(y, mb)
            np.savez_compressed(npz, counts=counts, hours=hours)
            diag['filters'] = dict(diag['filters'])
            js.write_text(json.dumps(diag))
    log('scan done')


# --------------------------------------------------------------------------------------------- calendars
def easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    L = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * L) // 451
    month, day = divmod(h + L - 7 * m + 114, 31)
    return dt.date(y, month, day + 1)


def nth(y, m, weekday, n):
    """n-th (1-based; -1 = last) given weekday of a month."""
    if n > 0:
        d = dt.date(y, m, 1)
        return d + dt.timedelta(days=(weekday - d.weekday()) % 7 + 7 * (n - 1))
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


def observed(d):
    """US rule: a holiday on Saturday is observed on Friday, on Sunday - on Monday."""
    return {d, d - dt.timedelta(days=1) if d.weekday() == 5 else d + dt.timedelta(days=1) if d.weekday() == 6 else d}


def holidays(country, y):
    """Public holidays and the days around them that a birth diary avoids. Deliberately generous: a day in this
    set is never a neighbour and never a tested date."""
    D, td, E = dt.date, dt.timedelta, easter(y)
    h = {D(y, 12, 23) + td(days=i) for i in range(9)} | {D(y, 1, 1), D(y, 1, 2)}  # 23 Dec - 31 Dec, 1-2 Jan
    h |= {E - td(days=2), E - td(days=1), E, E + td(days=1)}  # Good Friday to Easter Monday
    if country == 'us':
        h |= observed(D(y, 1, 1)) | observed(D(y, 7, 4)) | observed(D(y, 12, 25))
        if y >= 1986:
            h.add(nth(y, 1, 0, 3))
        h.add(nth(y, 2, 0, 3) if y >= 1971 else D(y, 2, 22))
        h.add(nth(y, 5, 0, -1) if y >= 1971 else D(y, 5, 30))
        h.add(nth(y, 9, 0, 1))
        h.add(nth(y, 10, 0, 2) if y >= 1971 else D(y, 10, 12))
        h |= observed(D(y, 11, 11)) if not 1971 <= y <= 1977 else {nth(y, 10, 0, 4)}
        t = nth(y, 11, 3, 4)
        h |= {t - td(days=1), t, t + td(days=1)}
    elif country == 'fr':
        h |= {D(y, 5, 1), D(y, 7, 14), D(y, 8, 15), D(y, 11, 1), D(y, 11, 11), E + td(days=39), E + td(days=49), E + td(days=50)}
        if y >= 1982:
            h.add(D(y, 5, 8))
    elif country == 'ew':
        for d in (D(y, 1, 1), D(y, 12, 25), D(y, 12, 26)):
            h.add(d)
            if d.weekday() >= 5:
                h |= {d + td(days=2), d + td(days=1)}
        h.add(D(1995, 5, 8) if y == 1995 else D(2020, 5, 8) if y == 2020 else nth(y, 5, 0, 1))
        h |= {D(2002, 6, 3), D(2002, 6, 4)} if y == 2002 else {D(2012, 6, 4), D(2012, 6, 5)} if y == 2012 else \
            {D(2022, 6, 2), D(2022, 6, 3)} if y == 2022 else {nth(y, 5, 0, -1)}
        h.add(nth(y, 8, 0, -1))
        h |= {d for d in (D(1999, 12, 31), D(2011, 4, 29), D(2022, 9, 19), D(2023, 5, 8)) if d.year == y}
    elif country == 'mx':
        h |= {D(y, 5, 1), D(y, 9, 15), D(y, 9, 16), D(y, 11, 1), D(y, 11, 2), D(y, 12, 12), E - td(days=3)}
        h.add(nth(y, 2, 0, 1))
        h.add(nth(y, 3, 0, 3))
        h.add(nth(y, 11, 0, 3))
        h |= {D(y, 2, 5), D(y, 3, 21), D(y, 11, 20)}
    elif country == 'br':
        h |= {D(y, 4, 21), D(y, 5, 1), D(y, 9, 7), D(y, 10, 12), D(y, 11, 2), D(y, 11, 15), D(y, 11, 20),
              E - td(days=49), E - td(days=48), E - td(days=47), E - td(days=46), E + td(days=60), E + td(days=61)}
    return h


# Tested dates. FIXED: (label, month, day, countries where the date carries the meaning).
FIXED = [
    ('valentine', 2, 14, ('us', 'fr', 'ew', 'mx')), ('leap_day', 2, 29, ('us', 'fr', 'ew', 'mx', 'br')),
    ('april_fools', 4, 1, ('us', 'fr', 'ew', 'br')), ('halloween', 10, 31, ('us', 'ew')),
    ('mothers_day_mx', 5, 10, ('mx',)), ('valentine_br', 6, 12, ('br',)), ('fools_mx', 12, 28, ('mx',)),
]
REPEATING = ([dt.date(2000 + k, k, k) for k in range(1, 13)]
             + [dt.date(1977, 7, 7), dt.date(1988, 8, 8), dt.date(1999, 9, 9),
                dt.date(2020, 2, 20), dt.date(2022, 2, 22), dt.date(2020, 2, 2), dt.date(2022, 2, 2)])
# Public holidays, for the descriptive table only (no hypothesis is about them): the same ratio, the day itself kept.
HOLIDAY_DAYS = [('christmas_day', 12, 25, ('us', 'fr', 'ew', 'mx', 'br')), ('new_years_day', 1, 1, ('us', 'fr', 'ew', 'mx', 'br')),
                ('independence_day_us', 7, 4, ('us',)), ('bastille_day', 7, 14, ('fr',)), ('boxing_day', 12, 26, ('ew',))]
# Placebos: the same machinery on dates that mean nothing; reported next to the tested ones.
PLACEBO_FIXED = [('placebo_mar_14', 3, 14), ('placebo_jun_18', 6, 18), ('placebo_sep_22', 9, 22), ('placebo_oct_24', 10, 24)]
WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def special_dates(country, years):
    """Dates that are never neighbours: holidays, every tested date and the 13th."""
    s = set()
    for y in range(years[0] - 1, years[1] + 2):
        s |= holidays(country, y)
        for _, m, d, _c in FIXED:
            if (m, d) != (2, 29) or (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)):
                s.add(dt.date(y, m, d))
        s |= {dt.date(y, m, 13) for m in range(1, 13)}
    return s | set(REPEATING)


# --------------------------------------------------------------------------------------------- compute
class Daily:
    """One series of births per day with the same-weekday expectation and the noise of ordinary days."""

    def __init__(self, key, country, values, name, group):
        import numpy as np
        self.key, self.country, self.name, self.group = key, country, name, group
        days = sorted(values)
        self.start, self.end = days[0], days[-1]
        n = (self.end - self.start).days + 1
        self.v = np.full(n, np.nan)
        for d, x in values.items():
            self.v[(d - self.start).days] = x
        self.years = (self.start.year, self.end.year)
        self.hol = set()
        for y in range(self.years[0] - 1, self.years[1] + 2):
            self.hol |= holidays(country, y)
        spec = special_dates(country, self.years)
        self.special = np.array([(self.start + dt.timedelta(days=i)) in spec for i in range(n)])
        usable = np.where(self.special | (self.v <= 0), np.nan, self.v)
        stack = []
        for k in (-21, -14, -7, 7, 14, 21):
            sh = np.full(n, np.nan)
            if k > 0:
                sh[:-k] = usable[k:]
            else:
                sh[-k:] = usable[:k]
            stack.append(sh)
        stack = np.array(stack)
        cnt = (~np.isnan(stack)).sum(axis=0)
        with np.errstate(invalid='ignore'):
            self.e = np.where(cnt >= 3, np.nansum(stack, axis=0) / np.maximum(cnt, 1), np.nan)
        with np.errstate(invalid='ignore', divide='ignore'):
            self.lr = np.log(self.v / self.e)
        year = np.array([(self.start + dt.timedelta(days=i)).year for i in range(n)])
        self.year = year
        ordinary = ~self.special & np.isfinite(self.lr)
        self.sigma_year = {}
        for y in range(self.years[0], self.years[1] + 1):
            x = self.lr[ordinary & (year == y)]
            if len(x) >= 60:
                self.sigma_year[y] = float(1.4826 * np.median(np.abs(x - np.median(x))))
        self.sigma = float(np.median(list(self.sigma_year.values()))) if self.sigma_year else float('nan')
        self.placebo_mean = float(np.exp(np.nanmean(self.lr[ordinary]))) if ordinary.any() else float('nan')
        self.ordinary = ordinary

    def idx(self, d):
        i = (d - self.start).days
        return i if 0 <= i < len(self.v) else None

    def effect(self, dates, keep_holidays=False):
        """Ratio of a group of days with its 95 % interval; days that are public holidays or lack neighbours drop
        out (keep_holidays: the group IS a holiday, as in the descriptive table of Christmas and New Year)."""
        o = e = var = 0.0
        used = []
        for d in dates:
            i = self.idx(d)
            if i is None or (d in self.hol and not keep_holidays) or not math.isfinite(self.e[i]) or not self.v[i] > 0:
                continue
            used.append(i)
        if not used:
            return None
        tot_e = sum(self.e[i] for i in used)
        for i in used:
            o += self.v[i]
            e += self.e[i]
            s = self.sigma_year.get(int(self.year[i]), self.sigma)
            var += (self.e[i] / tot_e * s) ** 2
        r, se = o / e, math.sqrt(var)
        return {'ratio': round(r, 4), 'lo': round(r * math.exp(-1.96 * se), 4), 'hi': round(r * math.exp(1.96 * se), 4),
                'days': len(used), 'births': int(o), 'expected': int(round(e))}


def family_sd(effects):
    """Spread of the log ratio over a placebo family of groups (robust: 1.4826 x median absolute deviation)."""
    xs = sorted(math.log(e['ratio']) for e in effects if e)
    if len(xs) < 8:
        return None
    med = xs[len(xs) // 2]
    dev = sorted(abs(x - med) for x in xs)
    sd = 1.4826 * dev[len(dev) // 2]
    if len(xs) >= 100:  # enough groups: the 2.5th and 97.5th percentiles themselves (the family has heavy tails)
        lo, hi = xs[int(0.025 * (len(xs) - 1))] - med, xs[int(math.ceil(0.975 * (len(xs) - 1)))] - med
    else:  # few groups: 1.96 standard deviations
        m = sum(xs) / len(xs)
        s = math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))
        lo, hi = -1.96 * s, 1.96 * s
    return sd, len(xs), round(math.exp(med), 4), lo, hi


def widen(e, fam):
    """A2: replace the interval of a group by the placebo-family interval."""
    if e and fam:
        e['lo'], e['hi'] = round(e['ratio'] * math.exp(-fam[4]), 4), round(e['ratio'] * math.exp(-fam[3]), 4)
    return e


def fam_json(fam):
    return {'sd': round(fam[0], 5), 'groups': fam[1], 'median': fam[2], 'p2_5': round(math.exp(fam[3]), 4),
            'p97_5': round(math.exp(fam[4]), 4)} if fam else None


def all_dates(series):
    d = series.start
    while d <= series.end:
        yield d
        d += dt.timedelta(days=1)


def load_groups():
    """Mexican and Brazilian daily counts and hours by delivery group, from the scan."""
    import numpy as np
    raw = {}
    diag = {}
    for country, years, cells in (('mx', MX_YEARS, MX_CELLS), ('br', BR_YEARS, BR_CELLS)):
        for y in years:
            f = DATA / 'scan' / f'{country}_{y}.npz'
            if not f.exists():
                continue
            z = np.load(f)
            raw[(country, y)] = (z['counts'], z['hours'])
            diag[(country, y)] = json.loads(f.with_suffix('.json').read_text())
    mx_typed = [y for (c, y), g in diag.items() if c == 'mx' and g['cs_typed'][0] and g['cs_typed'][1] / g['cs_typed'][0] >= MX_TYPED_MIN]
    out, hours = {}, {}
    for g, (country, cells_) in GROUPS.items():
        all_cells = MX_CELLS if country == 'mx' else BR_CELLS
        ci = [all_cells.index(c) for c in cells_]
        ys = sorted(y for (c, y) in raw if c == country)
        if g in ('mx_cs_planned', 'mx_cs_emergency'):
            ys = sorted(mx_typed)
        if g in ('br_vag_spont', 'br_vag_induced', 'br_cs_prelabour', 'br_cs_labour'):
            ys = [y for y in ys if y >= BR_TYPED_FROM]
        ys = longest_run(ys)
        vals, hh = {}, np.zeros((2, 24), dtype=np.int64)
        for y in ys:
            counts, hrs = raw[(country, y)]
            row = counts[ci].sum(axis=0)
            for i in range(366 if (y % 4 == 0) else 365):
                vals[dt.date(y, 1, 1) + dt.timedelta(days=i)] = int(row[i])
            hh += hrs[ci].sum(axis=0)
        if vals:
            out[g] = vals
            hours[g] = hh
    return out, hours, diag, sorted(mx_typed)


def longest_run(ys):
    """The longest stretch of consecutive years (the neighbours of a day must exist)."""
    best, cur = [], []
    for y in ys:
        cur = cur + [y] if cur and y == cur[-1] + 1 else [y]
        if len(cur) > len(best):
            best = cur
    return best


def compute():
    import numpy as np
    series = {}
    for key, meta in SERIES.items():
        vals = {d: x for d, x in read_series(key).items() if meta['years'][0] <= d.year <= meta['years'][1]}
        series[key] = Daily(key, meta['country'], vals, meta['name'], meta['group'])
        log(key, series[key].start, series[key].end, f'sigma {series[key].sigma:.4f} placebo {series[key].placebo_mean:.4f}')
    gvals, ghours, diag, mx_typed = load_groups()
    for g, vals in gvals.items():
        series[g] = Daily(g, g[:2], vals, 'Mexico' if g[:2] == 'mx' else 'Brazil', GROUP_NAME[g])
        log(g, series[g].start, series[g].end, f'sigma {series[g].sigma:.4f} placebo {series[g].placebo_mean:.4f}')

    res = {'series': {}, 'null': {}, 'thirteenth': {}, 'fixed': {}, 'holiday': {}, 'placebo': {}, 'repeating': {}, 'weekend': {}, 'season': {},
           'hours': {}, 'mx_typed_years': mx_typed}
    for key, s in series.items():
        births = float(np.nansum(s.v))
        res['series'][key] = {'country': s.country, 'name': s.name, 'group': s.group, 'years': list(s.years),
                              'births': int(births), 'sigma': round(s.sigma, 5), 'placebo_mean': round(s.placebo_mean, 4),
                              'ordinary_days': int(s.ordinary.sum())}
        # the 13th by weekday, and the 12th and 14th as placebos of the same shape
        th = {}
        for dom in (12, 13, 14):
            by = {w: [] for w in range(7)}
            for d in all_dates(s):
                if d.day == dom:
                    by[d.weekday()].append(d)
            th[str(dom)] = {WEEKDAYS[w]: s.effect(ds) for w, ds in by.items()}
            th[str(dom)]['not Friday'] = s.effect([d for w, ds in by.items() if w != 4 for d in ds])
        fam_days = [*range(4, 11), *range(16, 27)]
        by_dom = {dom: {w: [] for w in range(7)} for dom in fam_days}
        for d in all_dates(s):
            if d.day in by_dom:
                by_dom[d.day][d.weekday()].append(d)
        fam_wd = family_sd([s.effect(ds) for dom in fam_days for ds in by_dom[dom].values()])
        fam_rest = family_sd([s.effect([d for w, ds in by_dom[dom].items() if w != 4 for d in ds]) for dom in fam_days])
        for dom in th:
            for wd, e in th[dom].items():
                widen(e, fam_rest if wd == 'not Friday' else fam_wd)
        res['null'][key] = {'weekday_of_month': fam_json(fam_wd), 'not_friday_of_month': fam_json(fam_rest)}
        res['thirteenth'][key] = th
        fx = {}
        for label, m, dd, countries in FIXED:
            if s.country in countries:
                ds = [d for d in all_dates(s) if (d.month, d.day) == (m, dd)]
                fx[label] = s.effect(ds)
                fx[label + '_weekdays'] = s.effect([d for d in ds if d.weekday() < 5])
        plain = {}
        for d in all_dates(s):
            plain.setdefault((d.month, d.day), []).append(d)
        # The four placebo dates are checked against this family in validate, so they stay out of it: a check
        # against a family that contains the checked dates passes by construction.
        placebo_md = {(m, dd) for _, m, dd in PLACEBO_FIXED}
        never_special = [ds for (m, dd), ds in plain.items() if (m, dd) != (2, 29) and (m, dd) not in placebo_md
                         and not any(s.special[s.idx(d)] for d in ds)]
        fam_fixed = family_sd([s.effect(ds) for ds in never_special])
        for e in fx.values():
            widen(e, fam_fixed)
        res['null'][key]['fixed_date'] = fam_json(fam_fixed)
        res['fixed'][key] = fx
        res['holiday'][key] = {label: widen(s.effect([d for d in all_dates(s) if (d.month, d.day) == (m, dd)], keep_holidays=True), fam_fixed)
                               for label, m, dd, cs in HOLIDAY_DAYS if s.country in cs}
        res['placebo'][key] = {label: widen(s.effect([d for d in all_dates(s) if (d.month, d.day) == (m, dd)]), fam_fixed)
                               for label, m, dd in PLACEBO_FIXED}
        rp = {}
        for d in REPEATING:
            if s.idx(d) is not None:
                e = s.effect([d])
                rp[d.isoformat()] = {**e, 'weekday': WEEKDAYS[d.weekday()]} if e else {'holiday': d in s.hol, 'weekday': WEEKDAYS[d.weekday()]}
                if e:  # A3: how many ordinary days of the series sit lower
                    rp[d.isoformat()]['lower_ordinary_days'] = int((s.lr[s.ordinary] < math.log(e['ratio'])).sum())
                    rp[d.isoformat()]['ordinary_days'] = int(s.ordinary.sum())
                if not e and d in s.hol:  # A1: against the same holiday in the other years
                    own = s.effect([d], keep_holidays=True)
                    # «The same holiday» only in years when that calendar date was a holiday too: 05.05.05 in France
                    # was Ascension, and 5 May of most other years is an ordinary day.
                    others = [s.effect([x], keep_holidays=True) for x in all_dates(s)
                              if (x.month, x.day) == (d.month, d.day) and x != d and x in s.hol
                              and (x.weekday() >= 5) == (d.weekday() >= 5)]
                    others = [x['ratio'] for x in others if x]
                    if own and others:
                        base = sum(others) / len(others)
                        rp[d.isoformat()]['vs_same_holiday'] = {'ratio': round(own['ratio'] / base, 4), 'own_ratio': own['ratio'],
                                                                'holiday_ratio_other_years': round(base, 4), 'other_years': len(others),
                                                                'births': own['births']}
        res['repeating'][key] = rp
        # weekends: an average Saturday or Sunday against an average Tuesday-Thursday, ordinary days only
        wk = []
        for y in range(s.years[0], s.years[1] + 1):
            we, mid = [], []
            for d in all_dates(s):
                if d.year != y or d in s.hol:
                    continue
                x = s.v[s.idx(d)]
                if not x > 0:
                    continue
                (we if d.weekday() >= 5 else mid if d.weekday() in (1, 2, 3) else []).append(x)
            if we and mid:
                wk.append({'year': y, 'ratio': round(float(np.mean(we) / np.mean(mid)), 4)})
        res['weekend'][key] = wk
        res['season'][key] = season_curve(s)

    for g, hh in ghours.items():
        tot = hh.sum()
        if tot:
            both = hh.sum(axis=0)
            res['hours'][g] = {'n': int(tot), 'share_pct': [round(100 * float(x) / float(tot), 3) for x in both],
                               'daytime_7_19': round(float(both[7:19].sum() / tot), 4),
                               'weekday_pct': [round(100 * float(x) / float(hh[0].sum()), 3) for x in hh[0]] if hh[0].sum() else None,
                               'weekend_share': round(float(hh[1].sum() / tot), 4)}
    if not HOURS_JSON.exists():
        log(f'no {HOURS_JSON.name} next to the script: the hours of birth in the USA are left out')
    else:
        us = json.loads(HOURS_JSON.read_text())['hour_profiles_pct']['US']
        res['hours_us'] = {k: us[k] for k in ('all', 'caesarean', 'spontaneous_vaginal', 'induced', 'out_of_hospital') if k in us}
    res['diag'] = {f'{c}_{y}': {'n_raw': g['n_raw'], 'schema': g['schema'], 'filters': g['filters'],
                                'cs_typed_share': round(g['cs_typed'][1] / g['cs_typed'][0], 4) if g['cs_typed'][0] else None}
                   for (c, y), g in sorted(diag.items())}
    (DATA / 'computed.json').write_text(json.dumps(res, indent=1))

    # the daily file behind the page's lookup: births and ratio for every day of the all-births series
    daily = {}
    for key in (*SERIES, 'mx_all', 'br_all'):
        if key not in series:
            continue
        s = series[key]
        n = [int(x) if x == x else 0 for x in s.v]
        r = [int(round(1000 * s.v[i] / s.e[i])) if math.isfinite(s.e[i]) and s.v[i] > 0 else 0 for i in range(len(s.v))]
        flags = ''.join('h' if (s.start + dt.timedelta(days=i)) in s.hol else '.' for i in range(len(s.v)))
        daily[key] = {'start': s.start.isoformat(), 'name': s.name, 'births': n, 'ratio_x1000': r, 'holiday': flags}
    (DATA / 'daily.json').write_text(json.dumps(daily, separators=(',', ':')))
    log('compute done')


def season_curve(s):
    """Births by day of the year with weekdays, holidays and tested dates taken out: each ordinary day divided by
    the mean of its year and by the weekday factor of that year, averaged over years, smoothed over 29 days."""
    import numpy as np
    acc, cnt = np.zeros(366), np.zeros(366)
    for y in range(s.years[0], s.years[1] + 1):
        idx = [i for i in range(len(s.v)) if s.year[i] == y and s.ordinary[i]]
        if len(idx) < 200:
            continue
        v = np.array([s.v[i] for i in idx])
        wd = np.array([(s.start + dt.timedelta(days=i)).weekday() for i in idx])
        fac = np.array([v[wd == w].mean() for w in range(7)]) / v.mean()
        x = v / v.mean() / fac[wd]
        for i, val in zip(idx, x):
            d = s.start + dt.timedelta(days=i)
            k = (dt.date(2000, d.month, d.day) - dt.date(2000, 1, 1)).days
            acc[k] += val
            cnt[k] += 1
    raw = np.where(cnt > 0, acc / np.maximum(cnt, 1), np.nan)
    filled = np.where(np.isnan(raw), np.nanmean(raw), raw)
    w = np.concatenate([filled[-14:], filled, filled[:14]])
    smooth = np.convolve(w, np.ones(29) / 29, mode='valid')
    smooth = smooth / smooth.mean()
    peak, trough = int(np.argmax(smooth)), int(np.argmin(smooth))
    day = lambda k: (dt.date(2000, 1, 1) + dt.timedelta(days=k))  # noqa: E731
    conc = lambda k: day(k) - dt.timedelta(days=GESTATION_DAYS)  # noqa: E731
    return {'curve_pct': [round(100 * float(x), 2) for x in smooth], 'peak': day(peak).strftime('%m-%d'),
            'trough': day(trough).strftime('%m-%d'), 'peak_pct': round(100 * float(smooth[peak]), 2),
            'trough_pct': round(100 * float(smooth[trough]), 2), 'peak_conception': conc(peak).strftime('%m-%d'),
            'trough_conception': conc(trough).strftime('%m-%d')}


# --------------------------------------------------------------------------------------------- validate
def hypotheses_sha():
    return hashlib.sha256(json.dumps(HYPOTHESES, sort_keys=True).encode()).hexdigest()[:8]


def validate():
    r = json.loads((DATA / 'computed.json').read_text())
    checks = []

    def check(name, ok, detail=''):
        checks.append({'check': name, 'ok': bool(ok), 'detail': str(detail)})

    check('hypotheses unchanged since registration', hypotheses_sha() == HYPOTHESES_SHA256, hypotheses_sha())
    S, T, F, R = r['series'], r['thirteenth'], r['fixed'], r['repeating']
    for key in ('us_1969', 'us_1994', 'fr', 'ew', 'mx_all', 'br_all', 'mx_cs', 'br_cs_prelabour', 'br_vag_spont'):
        check(f'{key} present', key in S)
    for key, s in S.items():
        check(f'{key}: ordinary days centre on 1', 0.995 <= s['placebo_mean'] <= 1.005, s['placebo_mean'])
    # published yearly totals (millions): the series must be the ones they say they are
    tot = lambda key, y0, y1: S[key]['births']  # noqa: E731
    check('USA 1994-2014 totals about 85 million', 80e6 < tot('us_1994', 0, 0) < 90e6, S['us_1994']['births'])
    check('USA 1969-1988 totals about 70 million', 65e6 < tot('us_1969', 0, 0) < 75e6, S['us_1969']['births'])
    check('France 1968-2024 totals about 43 million', 39e6 < tot('fr', 0, 0) < 47e6, S['fr']['births'])
    check('England and Wales 1995-2024 totals about 20 million', 17e6 < tot('ew', 0, 0) < 22e6, S['ew']['births'])
    # placebos: dates that mean nothing must sit inside their intervals almost always
    out = total = 0
    for key, pl in r['placebo'].items():
        for label, e in pl.items():
            if e:
                total += 1
                out += not (e['lo'] <= 1 <= e['hi'])
    check('placebo dates inside their placebo-family intervals (at most 15 % outside)', total and out / total <= 0.15, f'{out} of {total}')
    out = total = 0
    for key, th in T.items():
        for dom in ('12', '14'):
            for wd, e in th[dom].items():
                if e and wd != 'not Friday':
                    total += 1
                    out += not (e['lo'] <= 1 <= e['hi'])
    check('the 12th and the 14th by weekday inside their placebo-family intervals (at most 15 % outside)',
          total and out / total <= 0.15, f'{out} of {total}')
    H = r['hours']
    check('Mexican planned C-sections are a daytime affair', H['mx_cs_planned']['daytime_7_19'] > H['mx_cs_emergency']['daytime_7_19'],
          f"{H['mx_cs_planned']['daytime_7_19']} vs {H['mx_cs_emergency']['daytime_7_19']}")
    check('Brazilian spontaneous births ignore the weekend', 0.26 <= H['br_vag_spont']['weekend_share'] <= 0.30,
          H['br_vag_spont']['weekend_share'])

    fri = lambda key: T[key]['13']['Friday']  # noqa: E731
    rest = lambda key: T[key]['13']['not Friday']  # noqa: E731
    near = lambda e: abs(math.log(e['ratio']))  # noqa: E731
    fx = lambda key, label: F[key][label]  # noqa: E731
    rep = lambda key, d: R[key].get(d, {}).get('ratio')  # noqa: E731
    together = lambda key, ds: series_effect(r, key, ds)  # noqa: E731
    us4 = ('halloween', 'valentine', 'april_fools', 'leap_day')
    h8 = [x for x in (rep('us_1994', f'20{k:02d}-{k:02d}-{k:02d}') for k in range(7, 13)) if x is not None]
    notes = {}
    if len(h8) < 6:
        notes['H8'] = 'judged on the dates that are not public holidays (11.11.11 was Veterans Day; see A1)'
    wk = lambda key, y0, y1: mean([x['ratio'] for x in r['weekend'][key] if y0 <= x['year'] <= y1])  # noqa: E731
    hyp = {
        'H1': fri('us_1994')['ratio'] <= 0.97 and near(rest('us_1994')) < near(fri('us_1994')),
        'H2': fri('us_1969')['ratio'] < 1.00 and near(fri('us_1969')) < near(fri('us_1994')),
        'H3': fri('fr')['ratio'] < 1.00 and fri('ew')['ratio'] < 1.00 and (fri('fr')['hi'] < 1.00 or fri('ew')['hi'] < 1.00),
        'H4': fri('mx_cs_planned')['ratio'] <= 0.92 and fri('br_cs_prelabour')['ratio'] <= 0.92
              and 0.98 <= fri('br_vag_spont')['ratio'] <= 1.02,
        'H5': fx('us_1994', 'halloween')['ratio'] <= 0.92 and fx('us_1994', 'valentine')['ratio'] >= 1.03
              and fx('us_1994', 'april_fools')['ratio'] <= 0.97 and fx('us_1994', 'leap_day')['ratio'] <= 0.95,
        'H6': all((fx('us_1969', k)['ratio'] - 1) * (fx('us_1994', k)['ratio'] - 1) > 0
                  and near(fx('us_1969', k)) < near(fx('us_1994', k)) for k in us4),
        'H7': all(fx(c, k)['ratio'] < 1.00 for c in ('fr', 'ew') for k in ('april_fools', 'leap_day')),
        'H8': len(h8) >= 5 and all(x >= 1.10 for x in h8) and rep('us_1994', '2006-06-06') <= 0.90,
        'H9': together('us_1994', ['2002-02-02', '2003-03-03', '2004-04-04', '2005-05-05']) >= 1.03
              and rep('us_1994', '1999-09-09') >= 1.03 and together('us_1969', ['1977-07-07', '1988-08-08']) >= 1.02,
        'H10': all(together(c, [f'20{k:02d}-{k:02d}-{k:02d}' for k in range(7, 13)]) >= 1.03 and rep(c, '2006-06-06') < 1.00
                   for c in ('fr', 'ew')),
        'H11': rep('br_cs_prelabour', '2020-02-20') >= 1.20 and rep('br_cs_prelabour', '2022-02-22') >= 1.20
               and rep('br_cs', '2011-11-11') >= 1.10 and rep('br_cs_prelabour', '2012-12-12') >= 1.10
               and all(0.95 <= rep('br_vag_spont', d) <= 1.05 for d in ('2020-02-20', '2022-02-22', '2012-12-12'))
               and 0.95 <= rep('br_vaginal', '2011-11-11') <= 1.05,
        'H12': fx('mx_cs_planned', 'mothers_day_mx')['ratio'] <= 0.70 and fx('mx_cs_private', 'valentine')['ratio'] >= 1.10,
        'H13': H['mx_cs_planned']['daytime_7_19'] >= 0.85 and H['br_cs_prelabour']['daytime_7_19'] >= 0.80
               and H['mx_vaginal']['daytime_7_19'] <= 0.60 and H['br_vag_spont']['daytime_7_19'] <= 0.60,
        'H14': wk('us_1969', 1969, 1973) >= 0.90 and wk('us_1994', 2010, 2014) <= 0.75
               and wk('fr', 1968, 1972) >= 0.90 and wk('fr', 2020, 2024) <= 0.85,
        'H15': r['season']['us_1994']['peak'][:2] == '09' and r['season']['fr']['peak'][:2] != '09',
    }
    out = {'ok': all(c['ok'] for c in checks), 'checks': checks,
           'hypotheses': {k: {'text': HYPOTHESES[k], 'held': bool(v), **({'note': notes[k]} if k in notes else {})}
                          for k, v in hyp.items()},
           'hypotheses_sha': hypotheses_sha()}
    (DATA / 'validation.json').write_text(json.dumps(out, indent=1))
    for c in checks:
        log(('ok  ' if c['ok'] else 'FAIL') + f' {c["check"]}: {c["detail"]}')
    for k, v in out['hypotheses'].items():
        log(f'{k}: {"held" if v["held"] else "did not hold"}')
    return out['ok']


def mean(xs):
    return sum(xs) / len(xs) if xs else float('nan')


def series_effect(r, key, isodates):
    """Ratio of several repeating dates taken together (sum of births over sum of expected); holidays drop out."""
    o = e = 0
    for d in isodates:
        x = r['repeating'][key].get(d)
        if x and 'ratio' in x:
            o += x['births']
            e += x['expected']
    return o / e if e else float('nan')


# --------------------------------------------------------------------------------------------- export
def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if not val['ok']:
        log('validation failed - nothing exported')
        return False
    r = json.loads((DATA / 'computed.json').read_text())
    manifest = json.loads((DATA / 'manifest.json').read_text())
    page = {
        'generated_from': {'fetched_on': manifest.get('fetched_on'), 'script': 'chosen_birthdays.py'},
        'gestation_days': GESTATION_DAYS,
        **{k: r[k] for k in ('series', 'null', 'thirteenth', 'fixed', 'holiday', 'placebo', 'repeating', 'weekend', 'season', 'hours',
                             'mx_typed_years') if k in r},
        'hours_us': r.get('hours_us'),
        # The hour profile of the USA covers other years than the daily series (they end in 2014).
        'hours_us_years': json.loads(HOURS_JSON.read_text())['totals']['US']['years'] if HOURS_JSON.exists() else None,
        'independent_recount': INDEPENDENT_RECOUNT,
        'hypotheses': val['hypotheses'],
        'added_after_count': ADDED_AFTER_COUNT,
        'validation': {'ok': val['ok'], 'checks': val['checks']},
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(page, separators=(',', ':'), ensure_ascii=False) + '\n')
    DAILY_OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DATA / 'daily.json', DAILY_OUT)
    with CSV_OUT.open('w', newline='') as fh:
        # csv, not f-strings: group names such as «C-sections, private hospitals» contain a comma.
        out = csv.writer(fh, lineterminator='\n')
        out.writerow(['series', 'country', 'group', 'years', 'measure', 'date_or_weekday', 'ratio', 'lower_95', 'upper_95',
                      'days', 'births', 'expected'])

        def row(key, measure, label, e):
            s = r['series'][key]
            if e and 'ratio' in e:
                out.writerow([key, s['country'], s['group'], f"{s['years'][0]}-{s['years'][1]}", measure, label, e['ratio'],
                              e.get('lo', ''), e.get('hi', ''), e.get('days', ''), e.get('births', ''), e.get('expected', '')])

        for key in r['series']:
            for dom, th in r['thirteenth'][key].items():
                for wd, e in th.items():
                    row(key, f'day {dom} of the month', wd, e)
            for label, e in r['fixed'][key].items():
                row(key, 'fixed date', label, e)
            for label, e in r['placebo'][key].items():
                row(key, 'placebo date', label, e)
            for label, e in r['holiday'].get(key, {}).items():
                row(key, 'public holiday', label, e)
            for d, e in r['repeating'][key].items():
                row(key, 'repeating date', d, e)
                if e.get('vs_same_holiday'):  # A1: no interval, the ratio of two ratios
                    v = e['vs_same_holiday']
                    row(key, 'repeating date against the same holiday in other years', d,
                        {'ratio': v['ratio'], 'births': v['births']})
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {DAILY_OUT} ({DAILY_OUT.stat().st_size // 1024} KB), {CSV_OUT}')
    return True


if __name__ == '__main__':
    steps = {'fetch': fetch, 'scan': scan, 'compute': compute, 'validate': validate, 'export': export}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    sys.exit(1 if steps[sys.argv[1]]() is False else 0)
