#!/usr/bin/env python3
"""Are babies born on their mother's birthday more often than chance - and who picks the date?

Every birth certificate in Mexico (SINAC, 2008-2025) and Brazil (SINASC, 2011-2024) carries two dates: the
child's date of birth and the mother's. This script counts how often the two fall on the same day and month,
against what chance predicts, and splits the count by how the baby arrived: a C-section booked before labour,
a C-section in labour or in an emergency, a vaginal birth with or without induction, a private or a public
hospital. If mothers (or their doctors) pick the mother's birthday for a booked delivery, the excess should
sit in booked C-sections and be absent where nobody picks the day - spontaneous labour.

Sources (all free, aggregates published):
  * Mexico - Secretaría de Salud, Dirección General de Información en Salud (DGIS), "Nacimientos" open data
    (Subsistema de Información sobre Nacimientos, SINAC), one zip per year:
    http://www.dgis.salud.gob.mx/descargas/datosabiertos/nacimientos/sinac_<year>.zip
    Published as open data by DGIS; only aggregates are published here, with attribution.
  * Brazil - Ministério da Saúde / DATASUS, SINASC (Sistema de Informações sobre Nascidos Vivos), national
    files DNBR<year>.dbc from ftp.datasus.gov.br/dissemin/publicos/SINASC/1996_/Dados/DNRES/. The mother's
    date of birth (DTNASCMAE) arrives with the 2011 form. OpenDataSUS publishes SINASC under CC BY-ND 3.0:
    only aggregates are published here.

Steps (raw data goes to $MOM_BIRTHDAY_DATA, default ~/startarot-data/mom-birthday, about 4 GB):
    python3 mother_birthday_births.py fetch      # zips and dbc files (needs curl; Brazil also pyreaddbc + dbfread)
    python3 mother_birthday_births.py scan       # one pass per file -> joint/<country>_<year>.npz + scan json
    python3 mother_birthday_births.py compute    # -> computed.json
    python3 mother_birthday_births.py validate   # sanity checks + the registered hypotheses -> validation.json
    python3 mother_birthday_births.py export     # JSON for the page + CSV + a copy of this script (only if valid)
Needs numpy and pandas (and pyarrow for the Brazilian cache).

Records: single births only (twins share a date and would count twice), the child born in the year of the
file, the mother aged 10-55 at the birth by the two dates.

Method in one paragraph. Day and month only: 29 February is dropped for mother and child alike, and every
other date becomes a day of a 365-day year. For each country, year of birth and delivery cell (how the baby
arrived x private or public hospital) the script keeps the full 365 x 365 table of mother's day x child's day.
"Offset" k is the child's day minus the mother's day, around the year (-182..+182); k = 0 is a birth on the
mother's birthday. The chance expectation E(k) is what the two calendars give when they are independent -
sum over days of (mothers born on d) x (children born on d + k) / n - computed inside each year and cell and
then summed, so weekdays, holidays and the seasons of each year are in the expectation. R(k) = O(k) / E(k).
Mothers and children share seasons a little (Recio Alcaide et al., Population Studies 2023: about 5 %
more same-MONTH births in Spain and France),
so R is not exactly 1 near k = 0 even without any choice. The spike is therefore measured against nearby
offsets: baseline B = sum O / sum E over 8 <= |k| <= 30, spike S = R(0) / B. The 95 % interval of S uses the
Poisson error of O(0) and of the baseline, inflated by the day-to-day overdispersion measured on far offsets
(31 <= |k| <= 182, from first differences of log R, so the slow seasonal shape does not count as noise). The
same machinery gives the "own number" test (child born on the mother's day of the month in another month),
the same Sun sign (by the usual table of dates), the same month, and D, the ratio for the 7 days either side
of the birthday, which shows whether births were pulled in from the days around it.

Exploration before registration (18.11.2026): one year, Mexico 2023 (1.52 million births). A first pilot
counted all births 1.19 vs the independence expectation, planned C-sections 1.40, emergency C-sections 1.14,
vaginal births 1.11; same day of the month in another month 1.077 for planned C-sections and 1.003 for vaginal
births; same Sun sign 1.018, same month 1.020. Testing this script on the same year then printed every group of
the compute step for 2023, the private / public split among them (C-sections 1.43 vs 1.13). Column schemas of
Mexico 2008-2025 and of Brazil 2012 and 2023 were read, with the coding of hospitals (place of birth against
the CLUES institution code) and the share of C-sections with a recorded type, but no other outcome was
counted. Hypotheses about Mexico are therefore tested on every year EXCEPT 2023 and marked [seen in
exploration]; Brazil is blind.
"""

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
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'mother-birthday-births'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'mother_birthday_births.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('MOM_BIRTHDAY_DATA', Path.home() / 'startarot-data' / 'mom-birthday'))

MX_YEARS = list(range(2008, 2026))
BR_YEARS = list(range(2011, 2025))
MX_EXPLORED = 2023  # the one year seen before registration
MX_URL = 'http://www.dgis.salud.gob.mx/descargas/datosabiertos/nacimientos/sinac_{y}.zip'
BR_URL = 'ftp://ftp.datasus.gov.br/dissemin/publicos/SINASC/1996_/Dados/DNRES/DNBR{y}.dbc'

# ---------------------------------------------------------------------------------------------------------
# Registered hypotheses. Their text is not edited after registration (the data test compares it with the
# registered copy); anything decided after the count goes to ADDED_AFTER_COUNT.
# S = spike on the mother's birthday against the 8-30-day baseline; "lower end" = lower end of its 95 % interval.
# "MX blind years" = every Mexican year except 2023; "MX typed years" = blind years in which at least 90 % of
# C-sections carry the planned/emergency type.
HYPOTHESES = {
    'H1': '[seen in exploration] Mexico, planned C-sections, MX typed years: S >= 1.25 and the lower end > 1.15.',
    'H2': 'Brazil, C-sections done before labour began: S >= 1.20 and the lower end > 1.10.',
    'H3': 'Brazil, vaginal births after spontaneous labour (not induced): S within 0.95-1.05.',
    'H4': '[seen in exploration for Mexico] The spike follows the booking: S of planned C-sections exceeds S of '
          'emergency C-sections by at least 0.10 in Mexico (MX typed years), and S of C-sections before labour '
          'exceeds S of C-sections in labour by at least 0.10 in Brazil.',
    'H5': '[seen in exploration] Mexico, all C-sections, MX blind years: S in private hospitals exceeds S in '
          'public hospitals by at least 0.10.',
    'H6': '[seen in exploration for Mexico] The own number: a child is born on the mother\'s day of the month in '
          'ANOTHER month more often than chance - planned C-sections (MX typed years) and C-sections before '
          'labour (Brazil): ratio >= 1.02 with the lower end > 1.00 in both countries; Brazil spontaneous vaginal '
          'births: ratio within 0.98-1.02.',
    'H7': 'Not a typing artefact: among births dated on the mother\'s birthday, the share whose certificate date '
          'is not 0-7 days after the birth date is at most 1.5 times the share among all other births, for '
          'vaginal births and for C-sections, in Mexico (MX blind years) and in Brazil (years that carry the '
          'declaration date).',
    'H8': '[seen in exploration for Mexico] Same Sun sign (usual table of dates), all births: ratio >= 1.01 in '
          'both countries (Mexico: MX blind years), and still >= 1.01 when pairs within 3 days of the mother\'s '
          'birthday are left out.',
    'H9': '[seen in exploration for Mexico] Pulled in from the days around: for planned C-sections (MX typed '
          'years) and C-sections before labour (Brazil), D, the ratio of the 7 days either side of the birthday '
          'to the baseline, is below 1.00 with the upper end of its 95 % interval below 1.00, in both countries.',
    'H10': 'Brazil, vaginal births after induced labour: S >= 1.05.',
}
HYPOTHESES_SHA256 = 'af5efe9c'  # first 8 hex of sha256(json.dumps(HYPOTHESES, sort_keys=True))
ADDED_AFTER_COUNT = {
    'A1': '[after count] The paperwork ghost. Births where nobody picks the day spike on the mother\'s birthday '
          'too: Mexican vaginal births 1.83 in 2008, falling year by year to 1.02 in 2024-2025, and Brazilian '
          'births after spontaneous labour about 1.17 in every year (H3 did not hold). A delivery cannot be timed '
          'to a birthday in spontaneous labour, so in those records the mother\'s day and month were written as '
          'the child\'s. H7 looked for the opposite slip (a wrong child\'s date, caught by the certificate date) '
          'and could not see this one. Two decisions follow, both made after the count: (a) Mexico\'s "clean '
          'years" are the years in which vaginal births spike at most 1.05 (CLEAN_MAX_SPIKE): 2024 and 2025, and '
          'the Mexican headline numbers come from them; (b) the effect of choosing the day is the spike of a booked '
          'delivery MINUS the spike of births where nobody picks the day, same country and years. (b) assumes the '
          'slip hits every kind of delivery alike, which the data cannot check; where booked deliveries happen in '
          'hospitals with better paperwork, the difference understates the choice.',
    'A2': '[after count] Which date is copied: the mother\'s day is compared with the CERTIFICATE (Mexico) or '
          'declaration (Brazil) day in records certified on another day than the birth. A form that pre-filled the '
          'mother\'s date with "today" would spike there; the comparison is printed next to the same rows against '
          'the child\'s birth day.',
    'A3': '[after count] Two more views of the ghost, prompted by the independent recount: home births (Mexico: '
          'place code HOGAR / 12 / 11 by schema, Brazil: LOCNASC 3), where nobody books a day, and vaginal births by '
          'the mother\'s age band. Both are read as raw observed / expected against the independence expectation '
          'of each year, without the 8-30-day baseline.',
}

# ---------------------------------------------------------------------------------------------------------
CUM = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
MONTH_OF = [m for m in range(12) for _ in range([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m])]
DOM_OF = [d for m in range(12) for d in range([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][m])]
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn',
         'Aquarius', 'Pisces']
SIGN_STARTS = [(3, 21), (4, 20), (5, 21), (6, 21), (7, 23), (8, 23), (9, 23), (10, 23), (11, 22), (12, 22),
               (1, 20), (2, 19)]  # the table most horoscope pages print


def sign_of_doy(i):
    m, d = MONTH_OF[i] + 1, DOM_OF[i] + 1
    best = None
    for s, (sm, sd) in enumerate(SIGN_STARTS):
        if (m, d) >= (sm, sd) and (best is None or (sm, sd) > SIGN_STARTS[best]):
            best = s
    return 9 if best is None else best  # 1-19 January: Capricorn


SIGN_OF = [sign_of_doy(i) for i in range(365)]

# Delivery cells. Mexico: how the baby arrived x sector; Brazil: how the baby arrived.
MX_DELIV = ['vag', 'cs_planned', 'cs_emerg', 'cs_unk', 'other']
MX_SECTOR = ['priv', 'pub', 'other']
MX_CELLS = [f'{d}.{s}' for d in MX_DELIV for s in MX_SECTOR]
BR_CELLS = ['vag_spont', 'vag_induced', 'vag_unk', 'cs_prelabour', 'cs_labour', 'cs_unk', 'other']

GROUPS = {
    'mx_all': ('mx', MX_CELLS),
    'mx_vaginal': ('mx', [c for c in MX_CELLS if c.startswith('vag.')]),
    'mx_cs': ('mx', [c for c in MX_CELLS if c.startswith('cs_')]),
    'mx_cs_planned': ('mx', [c for c in MX_CELLS if c.startswith('cs_planned.')]),
    'mx_cs_emergency': ('mx', [c for c in MX_CELLS if c.startswith('cs_emerg.')]),
    'mx_cs_private': ('mx', [c for c in MX_CELLS if c.startswith('cs_') and c.endswith('.priv')]),
    'mx_cs_public': ('mx', [c for c in MX_CELLS if c.startswith('cs_') and c.endswith('.pub')]),
    'mx_vaginal_private': ('mx', ['vag.priv']),
    'mx_vaginal_public': ('mx', ['vag.pub']),
    'mx_cs_planned_private': ('mx', ['cs_planned.priv']),
    'mx_cs_planned_public': ('mx', ['cs_planned.pub']),
    'br_all': ('br', BR_CELLS),
    'br_vaginal': ('br', ['vag_spont', 'vag_induced', 'vag_unk']),
    'br_vag_spont': ('br', ['vag_spont']),
    'br_vag_induced': ('br', ['vag_induced']),
    'br_cs': ('br', ['cs_prelabour', 'cs_labour', 'cs_unk']),
    'br_cs_prelabour': ('br', ['cs_prelabour']),
    'br_cs_labour': ('br', ['cs_labour']),
}
CLEAN_MAX_SPIKE = 1.05  # A1: a Mexican year is clean when its vaginal births spike at most this much
NEAR = range(1, 8)
BASE = range(8, 31)
FAR = range(31, 183)
PROFILE_K = range(-30, 31)


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------------------------- fetch
def curl_resume(url, dest, tries=12):
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


BR_KEEP = ['DTNASC', 'DTNASCMAE', 'HORANASC', 'PARTO', 'STCESPARTO', 'STTRABPART', 'GRAVIDEZ', 'LOCNASC',
           'DTDECLARAC', 'DTCADASTRO', 'IDADEMAE']


def fetch():
    DATA.mkdir(parents=True, exist_ok=True)
    for y in MX_YEARS:
        f = DATA / 'mx' / f'sinac_{y}.zip'
        log(f'mx {y}')
        curl_resume(MX_URL.format(y=y), f)
    import pandas as pd
    for y in BR_YEARS:
        pq = DATA / 'br' / f'sinasc_{y}.parquet'
        if pq.exists():
            continue
        dbc = DATA / 'br' / f'DNBR{y}.dbc'
        log(f'br {y}')
        curl_resume(BR_URL.format(y=y), dbc)
        import pyreaddbc
        import dbfread
        dbf = dbc.with_suffix('.dbf')
        pyreaddbc.dbc2dbf(str(dbc), str(dbf))
        t = dbfread.DBF(str(dbf), encoding='latin-1', load=False)
        keep = [k for k in BR_KEEP if k in t.field_names]
        recs = ([r.get(k) for k in keep] for r in t)
        pd.DataFrame.from_records(recs, columns=keep).astype('string').to_parquet(pq)
        dbf.unlink()
    manifest = {'fetched_on': dt.date.today().isoformat(), 'files': {}}
    for f in sorted([*DATA.glob('mx/*.zip'), *DATA.glob('br/*.dbc')]):
        h = hashlib.sha256()
        with f.open('rb') as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b''):
                h.update(chunk)
        manifest['files'][f'{f.parent.name}/{f.name}'] = {'sha256': h.hexdigest(), 'bytes': f.stat().st_size}
    (DATA / 'manifest.json').write_text(json.dumps(manifest, indent=1))
    log('fetch done')


# --------------------------------------------------------------------------------------------- scan
# Mexico ships three schemas. Each maps to: mother's date, child's date, hour, certificate date, singleton,
# delivery, C-section type, place (sector) and the CLUES code (whose letters 3-5 name the institution).
MX_SCHEMAS = {
    'text': dict(mom='fecha_nac_madre', kid='fecha_nacimiento_nac_vivo', hour='hora_nacimiento_nac_vivo',
                 cert='fecha_certificacion', single='producto_de_un_embarazo', deliv='procedimiento_utilizado',
                 cstype=None, place='lugar_de_nacimiento', clues='clues'),
    'short': dict(mom='FECH_NACM', kid='FECH_NACH', hour='HORA_NACH', cert='FECH_CERT', single='PRODUCTO',
                  deliv='PROCNAC', cstype=None, place='INST_NAC', clues='CLUES'),
    'long': dict(mom='FECHANACIMIENTOMADRE', kid='FECHANACIMIENTO', hour='HORANACIMIENTO', cert='FECHACERTIFICADO',
                 single='PRODUCTOEMBARAZO', deliv='RESOLUCIONEMBARAZO', cstype='TIPOCESAREA',
                 place='LUGARNACIMIENTO', clues='CLUES'),
}
MX_PUBLIC_TEXT = {'SECRETARÍA DE SALUD', 'IMSS', 'IMSS OPORTUNIDADES', 'ISSSTE', 'OTRA UNIDAD PÚBLICA', 'SEDENA',
                  'SEMAR', 'PEMEX', 'IMSS BIENESTAR', 'IMSS-BIENESTAR'}
MX_PRIVATE = {'text': {'UNIDAD MÉDICA PRIVADA'}, 'short': {'10'}, 'long': {'09'}}
MX_PUBLIC = {'text': MX_PUBLIC_TEXT, 'short': {'01', '02', '03', '04', '05', '06', '07', '08'},
             'long': {'01', '02', '03', '04', '05', '06', '07', '08', '14'}}
MX_VAGINAL = {'text': {'EUTÓCICO', 'DISTÓCICO', 'FÓRCEPS'}, 'short': {'1', '3', '4'}, 'long': {'1', '2'}}
MX_CS = {'text': {'CESÁREA'}, 'short': {'2'}, 'long': {'3'}}
MX_SINGLE = {'text': {'ÚNICO'}, 'short': {'1'}, 'long': {'1'}}
# A3: home births (checked by data: almost no C-sections, mostly attended by a midwife)
MX_HOME = {'text': {'HOGAR'}, 'short': {'12'}, 'long': {'11'}}
AGE_BANDS = [(10, 19), (20, 29), (30, 39), (40, 55)]
PUBLIC_CLUES = {'SSA', 'IMS', 'IMO', 'IMB', 'IST', 'SDN', 'SMA', 'PMX', 'SME', 'HUN', 'DIF', 'CRO', 'SMM'}


def open_mx(y):
    z = zipfile.ZipFile(DATA / 'mx' / f'sinac_{y}.zip')
    name = [n for n in z.namelist() if not n.endswith('/')][0]
    if name.lower().endswith('.zip'):
        z = zipfile.ZipFile(io.BytesIO(z.read(name)))
        name = [n for n in z.namelist() if not n.endswith('/')][0]
    with z.open(name) as fh:
        head = fh.read(1 << 20)
    try:
        head.decode('utf-8')
        enc = 'utf-8'
    except UnicodeDecodeError as e:
        enc = 'utf-8' if e.start > len(head) - 4 else 'latin-1'
    return z, name, enc


def doy_arrays(day, month):
    import numpy as np
    cum = np.array(CUM)
    return cum[month - 1] + day - 1


def parse_dates(s, fmt):
    import pandas as pd
    return pd.to_datetime(s.str.strip(), format=fmt, errors='coerce')


def accumulate(frame, cells, joint, diag):
    """frame: mom (datetime), kid (datetime), cell (str), hour (int or -1), lag (days or NaN)."""
    import numpy as np
    for cell, g in frame.groupby('cell', sort=False):
        if cell not in cells:
            continue
        md = g['md'].to_numpy()
        if NULL_RUN:
            md = NULL_RNG.permutation(md)
            g = g.assign(md=md)
        idx = md * 365 + g['kd'].to_numpy()
        joint[cells.index(cell)] += np.bincount(idx, minlength=365 * 365).astype(np.int64).reshape(365, 365)
        bday = (g['md'] == g['kd']).to_numpy()
        lag = g['lag'].to_numpy()
        ok = (lag >= 0) & (lag <= 7)
        has = ~np.isnan(lag)
        for b in (True, False):
            sel = bday == b
            diag['lag'][cell]['bday' if b else 'other'][0] += int((has & sel).sum())
            diag['lag'][cell]['bday' if b else 'other'][1] += int((has & sel & ~ok).sum())
        # A2: does the mother's day copy the CERTIFICATE date? Only rows certified on another day than the birth.
        cd = g['cd'].to_numpy()
        kd = g['kd'].to_numpy()
        other = (cd >= 0) & (cd != kd)
        diag['vs_certificate'] += np.bincount((cd[other] - md[other]) % 365, minlength=365)
        diag['vs_birth_same_rows'] += np.bincount((kd[other] - md[other]) % 365, minlength=365)
        h = g['hour'].to_numpy()
        diag['hours'][cell][0] += int((h >= 0).sum())
        diag['hours'][cell][1] += int(((h >= 7) & (h < 15)).sum())
        wd = g['kid'].dt.weekday.to_numpy()
        diag['sunday'][cell][0] += int(len(wd))
        diag['sunday'][cell][1] += int((wd == 6).sum())


def accumulate_ghost(frame, diag):
    """A3: calendars of mothers and children by place (home or facility), delivery and mother's age band, so the
    birthday ratio can be read where nobody picks the day (home births) and by the mother's age."""
    import numpy as np
    deliv = frame['cell'].str.split('.').str[0].str.split('_').str[0]  # vag / cs / other
    band = np.select([frame['age'].between(lo, hi) for lo, hi in AGE_BANDS], [f'{lo}-{hi}' for lo, hi in AGE_BANDS], '')
    key = np.where(frame['home'], 'home', 'facility') + '|' + deliv.to_numpy() + '|' + band
    for k, idx in frame.groupby(key, sort=False).indices.items():
        md = frame['md'].to_numpy()[idx]
        kd = frame['kd'].to_numpy()[idx]
        if NULL_RUN:
            md = NULL_RNG.permutation(md)
        slot = diag['ghost'].setdefault(k, {'n': 0, 'M': np.zeros(365, np.int64), 'K': np.zeros(365, np.int64),
                                            'D': np.zeros(365, np.int64)})
        slot['n'] += len(idx)
        slot['M'] += np.bincount(md, minlength=365)
        slot['K'] += np.bincount(kd, minlength=365)
        slot['D'] += np.bincount(md[md == kd], minlength=365)


# Null run: MOM_BIRTHDAY_NULL=1 shuffles the mothers' days inside each file and delivery cell before counting
# (use a separate $MOM_BIRTHDAY_DATA/joint, e.g. by pointing MOM_BIRTHDAY_DATA at a copy with symlinked raw
# folders). Every spike must then be 1 within its interval: the run checks the machinery and the intervals.
NULL_RUN = os.environ.get('MOM_BIRTHDAY_NULL') == '1'
NULL_RNG = None
if NULL_RUN:
    import numpy as _np
    NULL_RNG = _np.random.default_rng(20261118)


def new_diag(cells):
    import numpy as np
    return {'ghost': {}, 'vs_certificate': np.zeros(365, dtype=np.int64), 'vs_birth_same_rows': np.zeros(365, dtype=np.int64),
            'lag': {c: {'bday': [0, 0], 'other': [0, 0]} for c in cells}, 'hours': {c: [0, 0] for c in cells},
            'sunday': {c: [0, 0] for c in cells}, 'filters': Counter(), 'clues_check': Counter(),
            'cs_typed': [0, 0]}


def finish_frame(df, filters):
    """Common filters: valid dates, child born in the file year, mother 10-55, no 29 February."""
    n0 = len(df)
    df = df[df['mom'].notna() & df['kid'].notna()]
    filters['bad date'] += n0 - len(df)
    age = (df['kid'].dt.year - df['mom'].dt.year
           - ((df['kid'].dt.month < df['mom'].dt.month)
              | ((df['kid'].dt.month == df['mom'].dt.month) & (df['kid'].dt.day < df['mom'].dt.day))).astype(int))
    n1 = len(df)
    keep = (age >= 10) & (age <= 55)
    df = df[keep].assign(age=age[keep])
    filters['mother age outside 10-55'] += n1 - len(df)
    feb29 = ((df['mom'].dt.month == 2) & (df['mom'].dt.day == 29)) | ((df['kid'].dt.month == 2) & (df['kid'].dt.day == 29))
    filters['29 February'] += int(feb29.sum())
    df = df[~feb29].copy()
    df['md'] = doy_arrays(df['mom'].dt.day.to_numpy(), df['mom'].dt.month.to_numpy())
    df['kd'] = doy_arrays(df['kid'].dt.day.to_numpy(), df['kid'].dt.month.to_numpy())
    df['lag'] = (df['cert'] - df['kid']).dt.days.astype('float')
    cert_ok = df['cert'].notna() & ~((df['cert'].dt.month == 2) & (df['cert'].dt.day == 29))
    df['cd'] = -1
    df.loc[cert_ok, 'cd'] = doy_arrays(df.loc[cert_ok, 'cert'].dt.day.to_numpy(), df.loc[cert_ok, 'cert'].dt.month.to_numpy())
    return df


def scan_mx(y):
    import numpy as np
    import pandas as pd
    z, name, enc = open_mx(y)
    with z.open(name) as fh:
        cols = pd.read_csv(io.TextIOWrapper(fh, encoding=enc, errors='replace'), nrows=0).columns.tolist()
    schema = 'long' if 'FECHANACIMIENTOMADRE' in cols else 'short' if 'FECH_NACM' in cols else 'text'
    S = MX_SCHEMAS[schema]
    use = [v for v in S.values() if v]
    joint = np.zeros((len(MX_CELLS), 365, 365), dtype=np.int64)
    diag = new_diag(MX_CELLS)
    diag['schema'] = schema
    n_raw = 0
    with z.open(name) as fh:
        reader = pd.read_csv(io.TextIOWrapper(fh, encoding=enc, errors='replace'), usecols=use, dtype=str,
                             keep_default_na=False, chunksize=500_000)
        for ch in reader:
            n_raw += len(ch)
            ch = ch.apply(lambda s: s.str.strip())
            df = pd.DataFrame({
                'mom': parse_dates(ch[S['mom']], '%d/%m/%Y'), 'kid': parse_dates(ch[S['kid']], '%d/%m/%Y'),
                'cert': parse_dates(ch[S['cert']], '%d/%m/%Y'),
            })
            hh = ch[S['hour']].str.extract(r'^(\d{1,2}):')[0]
            df['hour'] = pd.to_numeric(hh, errors='coerce').fillna(-1).astype(int)
            single = ch[S['single']].isin(MX_SINGLE[schema])
            deliv = np.where(ch[S['deliv']].isin(MX_VAGINAL[schema]), 'vag',
                             np.where(ch[S['deliv']].isin(MX_CS[schema]), 'cs', 'other'))
            if S['cstype']:
                t = ch[S['cstype']]
                cs = np.where(t == '1', 'cs_planned', np.where(t == '2', 'cs_emerg', 'cs_unk'))
                diag['cs_typed'][0] += int((deliv == 'cs').sum())
                diag['cs_typed'][1] += int(((deliv == 'cs') & t.isin(['1', '2'])).sum())
            else:
                cs = np.full(len(ch), 'cs_unk')
                diag['cs_typed'][0] += int((deliv == 'cs').sum())
            deliv = np.where(deliv == 'cs', cs, deliv)
            place = ch[S['place']]
            sector = np.where(place.isin(MX_PRIVATE[schema]), 'priv', np.where(place.isin(MX_PUBLIC[schema]), 'pub', 'other'))
            inst = ch[S['clues']].str[2:5]
            inst_class = np.where(inst == 'SMP', 'SMP', np.where(inst.isin(PUBLIC_CLUES), 'public', 'none'))
            cc = pd.Series(list(zip(sector, inst_class))).value_counts()
            for (s_, i_), v in cc.items():
                diag['clues_check'][f'{s_}|{i_}'] += int(v)
            df['cell'] = pd.Series(deliv, index=ch.index) + '.' + pd.Series(sector, index=ch.index)
            df['home'] = place.isin(MX_HOME[schema]).to_numpy()
            n_multi = int((~single).sum())
            diag['filters']['not a singleton'] += n_multi
            df = df[single.to_numpy()]
            kid_year_ok = df['kid'].dt.year == y
            diag['filters']['child born in another year'] += int((df['kid'].notna() & ~kid_year_ok).sum())
            df = df[kid_year_ok | df['kid'].isna()]
            df = finish_frame(df, diag['filters'])
            accumulate(df, MX_CELLS, joint, diag)
            accumulate_ghost(df, diag)
    diag['n_raw'] = n_raw
    return joint, diag


def scan_br(y):
    import numpy as np
    import pandas as pd
    raw = pd.read_parquet(DATA / 'br' / f'sinasc_{y}.parquet')
    raw = raw.fillna('').apply(lambda s: s.str.strip())
    for c in BR_KEEP:
        if c not in raw:
            raw[c] = ''
    joint = np.zeros((len(BR_CELLS), 365, 365), dtype=np.int64)
    diag = new_diag(BR_CELLS)
    diag['schema'] = 'dnbr'
    diag['n_raw'] = len(raw)
    diag['mother_date_filled'] = int((raw['DTNASCMAE'].str.len() == 8).sum())
    has_decl = 'DTDECLARAC' in raw and (raw['DTDECLARAC'].str.len() == 8).mean() >= 0.9
    diag['declaration_date'] = bool(has_decl)
    df = pd.DataFrame({'mom': parse_dates(raw['DTNASCMAE'], '%d%m%Y'), 'kid': parse_dates(raw['DTNASC'], '%d%m%Y')})
    df['cert'] = parse_dates(raw['DTDECLARAC'], '%d%m%Y') if has_decl else pd.NaT
    hh = raw['HORANASC'].str[:2]
    df['hour'] = pd.to_numeric(hh.where(raw['HORANASC'].str.fullmatch(r'([01]\d|2[0-3])[0-5]\d')), errors='coerce').fillna(-1).astype(int)
    p, cs, tr = raw['PARTO'], raw['STCESPARTO'], raw['STTRABPART']
    cell = np.select(
        [(p == '1') & (tr == '2'), (p == '1') & (tr == '1'), p == '1',
         (p == '2') & (cs == '1'), (p == '2') & (cs == '2'), p == '2'],
        ['vag_spont', 'vag_induced', 'vag_unk', 'cs_prelabour', 'cs_labour', 'cs_unk'], 'other')
    df['cell'] = cell
    df['home'] = (raw['LOCNASC'] == '3').to_numpy()
    single = (raw['GRAVIDEZ'] == '1').to_numpy()
    diag['filters']['not a singleton'] += int((~single).sum())
    df = df[single]
    kid_year_ok = df['kid'].dt.year == y
    diag['filters']['child born in another year'] += int((df['kid'].notna() & ~kid_year_ok).sum())
    df = df[kid_year_ok | df['kid'].isna()]
    df = finish_frame(df, diag['filters'])
    accumulate(df, BR_CELLS, joint, diag)
    accumulate_ghost(df, diag)
    return joint, diag


def scan():
    import numpy as np
    out = DATA / 'joint'
    out.mkdir(parents=True, exist_ok=True)
    jobs = [('mx', y) for y in MX_YEARS] + [('br', y) for y in BR_YEARS]
    only = os.environ.get('MOM_BIRTHDAY_ONLY')  # e.g. "mx:2023" while developing
    for country, y in jobs:
        if only and f'{country}:{y}' not in only.split(','):
            continue
        npz, js = out / f'{country}_{y}.npz', out / f'{country}_{y}.json'
        if npz.exists() and js.exists() and 'ghost' in json.loads(js.read_text()):
            continue
        log(f'scan {country} {y}')
        joint, diag = (scan_mx if country == 'mx' else scan_br)(y)
        np.savez_compressed(npz, joint=joint.astype(np.int32))
        diag['filters'] = dict(diag['filters'])
        diag['clues_check'] = dict(diag['clues_check'])
        diag['vs_certificate'] = diag['vs_certificate'].tolist()
        diag['vs_birth_same_rows'] = diag['vs_birth_same_rows'].tolist()
        diag['ghost'] = {k: {'n': v['n'], 'M': v['M'].tolist(), 'K': v['K'].tolist(), 'D': v['D'].tolist()}
                         for k, v in diag['ghost'].items()}
        diag['kept'] = int(joint.sum())
        js.write_text(json.dumps(diag, indent=1))
        log(f'  kept {diag["kept"]} of {diag["n_raw"]}')


# --------------------------------------------------------------------------------------------- compute
def offset_index():
    import numpy as np
    return (np.arange(365)[:, None] + np.arange(365)[None, :]) % 365  # [mother day, k] -> child day


def cell_vectors(J):
    """For one 365x365 table: O(k), E(k), n, and the totals of the masked measures."""
    import numpy as np
    n = J.sum()
    if n == 0:
        return None
    idx = offset_index()
    M, K = J.sum(1).astype(float), J.sum(0).astype(float)
    O = J[np.arange(365)[:, None], idx].sum(0).astype(float)
    E = (M[:, None] * K[idx]).sum(0) / n
    P = np.outer(M, K) / n
    out = {'n': float(n), 'O': O, 'E': E, 'O_diag': np.diag(J).astype(float), 'E_diag': np.diag(P)}
    for name, mask in MASKS.items():
        out[name] = (float((J * mask).sum()), float((P * mask).sum()))
    return out


def build_masks():
    import numpy as np
    month = np.array(MONTH_OF)
    dom = np.array(DOM_OF)
    sign = np.array(SIGN_OF)
    k = (np.arange(365)[None, :] - np.arange(365)[:, None]) % 365
    k = np.where(k > 182, k - 365, k)
    return {
        'same_dom_other_month': (dom[:, None] == dom[None, :]) & (month[:, None] != month[None, :]),
        'same_sign': sign[:, None] == sign[None, :],
        'same_sign_beyond_3_days': (sign[:, None] == sign[None, :]) & (np.abs(k) > 3),
        'same_month': month[:, None] == month[None, :],
    }


MASKS = {}


def ks(rng):
    return [k for r in rng for k in (r, -r)]


def stats(vecs):
    """vecs: list of cell_vectors dicts (one per country-year-cell) -> the numbers the page prints."""
    import numpy as np
    vecs = [v for v in vecs if v]
    n = sum(v['n'] for v in vecs)
    O = sum(v['O'] for v in vecs)
    E = sum(v['E'] for v in vecs)
    R = O / E
    at = lambda k: k % 365  # noqa: E731
    base_o = sum(O[at(k)] for k in ks(BASE))
    base_e = sum(E[at(k)] for k in ks(BASE))
    B = base_o / base_e
    far = [at(k) for k in range(-182, 183) if abs(k) in FAR]
    lr = np.log(np.maximum(O, 0.5) / E)  # a tiny group can have an empty day
    d = np.concatenate([np.diff(lr[[at(k) for k in range(-182, -30)]]), np.diff(lr[[at(k) for k in range(31, 183)]])])
    pois = np.mean(1 / np.maximum(O[far], 0.5))
    phi = max(1.0, float(np.var(d) / (2 * pois)))
    o0, e0 = O[0], E[0]
    S = (o0 / e0) / B
    se = math.sqrt(phi / o0 + 1 / base_o)
    near_o = sum(O[at(k)] for k in ks(NEAR))
    near_e = sum(E[at(k)] for k in ks(NEAR))
    D = (near_o / near_e) / B
    se_d = math.sqrt(phi / near_o + 1 / base_o)
    placebo = float(np.mean([(R[f] / B) >= S for f in far]))
    out = {
        'n': int(n), 'on_birthday': int(o0), 'expected_independent': round(float(e0), 1),
        'ratio_independent': round(float(o0 / e0), 4), 'baseline': round(float(B), 4),
        'spike': round(float(S), 4), 'lo': round(float(S * math.exp(-1.96 * se)), 4),
        'hi': round(float(S * math.exp(1.96 * se)), 4),
        'extra_births': round(float(o0 - B * e0), 1), 'one_in': round(float(n / o0), 1),
        'near': round(float(D), 4), 'near_lo': round(float(D * math.exp(-1.96 * se_d)), 4),
        'near_hi': round(float(D * math.exp(1.96 * se_d)), 4),
        'overdispersion': round(phi, 3), 'placebo_share_at_least_as_high': round(placebo, 4),
        'profile': [{'k': k, 'o': int(O[at(k)]), 'e': round(float(E[at(k)]), 1),
                     'r': round(float(R[at(k)] / B), 4)} for k in PROFILE_K],
    }
    for name in MASKS:
        mo = sum(v[name][0] for v in vecs)
        me = sum(v[name][1] for v in vecs)
        r = mo / me
        s = math.sqrt(phi / mo)
        out[name] = {'o': int(mo), 'e': round(me, 1), 'ratio': round(r, 4), 'lo': round(r * math.exp(-1.96 * s), 4),
                     'hi': round(r * math.exp(1.96 * s), 4)}
    return out


def load_country(country, years):
    import numpy as np
    cells = MX_CELLS if country == 'mx' else BR_CELLS
    vec, diag = {}, {}
    for y in years:
        npz = DATA / 'joint' / f'{country}_{y}.npz'
        if not npz.exists():
            continue
        J = np.load(npz)['joint'].astype(np.int64)
        diag[y] = json.loads((DATA / 'joint' / f'{country}_{y}.json').read_text())
        for i, c in enumerate(cells):
            vec[(y, c)] = cell_vectors(J[i])
    return vec, diag


def compute():
    MASKS.update(build_masks())
    mx_vec, mx_diag = load_country('mx', MX_YEARS)
    br_vec, br_diag = load_country('br', BR_YEARS)
    mx_years = sorted(mx_diag)
    mx_blind = [y for y in mx_years if y != MX_EXPLORED]
    mx_typed_all = [y for y in mx_years if mx_diag[y]['cs_typed'][0]
                    and mx_diag[y]['cs_typed'][1] / mx_diag[y]['cs_typed'][0] >= 0.90]
    mx_typed = [y for y in mx_typed_all if y != MX_EXPLORED]
    br_years = [y for y in sorted(br_diag) if br_diag[y]['mother_date_filled'] / br_diag[y]['n_raw'] >= 0.90]
    br_decl = [y for y in br_years if br_diag[y]['declaration_date']]
    sets = {'mx_all_years': mx_years, 'mx_blind': mx_blind, 'mx_typed': mx_typed, 'mx_typed_all': mx_typed_all,
            'br_years': br_years, 'br_declaration_years': br_decl}

    def g(group, years):
        country, cells = GROUPS[group]
        vec = mx_vec if country == 'mx' else br_vec
        return stats([vec[(y, c)] for y in years for c in cells if (y, c) in vec])

    # A1: Mexican years whose births without a chosen day (vaginal births) show no birthday spike - the years in
    # which the mother's date is not copied from the child's.
    mx_clean = [y for y in mx_years if g('mx_vaginal', [y])['spike'] <= CLEAN_MAX_SPIKE]
    sets['mx_clean'] = mx_clean
    sets['mx_typed_clean'] = [y for y in mx_typed_all if y in mx_clean]

    groups = {}
    for name, (country, _) in GROUPS.items():
        if country == 'mx':
            ylist = {'all': mx_years, 'blind': mx_blind, 'clean': mx_clean}
            if 'planned' in name or 'emergency' in name:
                ylist = {'all': mx_typed_all, 'blind': mx_typed, 'clean': sets['mx_typed_clean']}
        else:
            ylist = {'all': br_years}
        groups[name] = {k: g(name, v) for k, v in ylist.items() if v}

    # A1: the effect of choosing the day = spike of a booked delivery minus the spike of births where nobody picks
    # the day, same country and years (the copying slip is assumed to hit every delivery alike).
    def minus(a, b):
        se = lambda x: (math.log(x['hi']) - math.log(x['lo'])) / 3.92 * x['spike']  # noqa: E731
        d = a['spike'] - b['spike']
        e = math.sqrt(se(a) ** 2 + se(b) ** 2)
        return {'diff': round(d, 4), 'lo': round(d - 1.96 * e, 4), 'hi': round(d + 1.96 * e, 4)}

    G = groups
    choice = {
        'mx_planned_minus_vaginal_clean': minus(G['mx_cs_planned']['clean'], G['mx_vaginal']['clean']),
        'mx_planned_private_minus_vaginal_clean': minus(G['mx_cs_planned_private']['clean'], G['mx_vaginal']['clean']),
        'mx_planned_public_minus_vaginal_clean': minus(G['mx_cs_planned_public']['clean'], G['mx_vaginal']['clean']),
        'mx_emergency_minus_vaginal_clean': minus(G['mx_cs_emergency']['clean'], G['mx_vaginal']['clean']),
        'br_prelabour_minus_spontaneous': minus(G['br_cs_prelabour']['all'], G['br_vag_spont']['all']),
        'br_labour_minus_spontaneous': minus(G['br_cs_labour']['all'], G['br_vag_spont']['all']),
        'br_induced_minus_spontaneous': minus(G['br_vag_induced']['all'], G['br_vag_spont']['all']),
        'br_prelabour_by_year': [{'year': y, **minus(g('br_cs_prelabour', [y]), g('br_vag_spont', [y]))}
                                 for y in br_years],
    }
    # extra births on the mother's birthday that the choice explains (the copying slip taken out)
    for key, a, b in (('mx_planned_clean', G['mx_cs_planned']['clean'], G['mx_vaginal']['clean']),
                      ('br_prelabour', G['br_cs_prelabour']['all'], G['br_vag_spont']['all'])):
        e0b = a['expected_independent'] * a['baseline']
        choice[f'{key}_extra_births'] = round((a['spike'] - b['spike']) * e0b, 1)

    # A2: the mother's day against the CERTIFICATE day (rows certified on another day than the birth): a copy of
    # some date of the form other than the child's would spike here.
    def vs(diags, years, key):
        import numpy as np
        c = sum(np.array(diags[y][key], dtype=float) for y in years)
        base = np.mean([c[k % 365] for k in ks(BASE)])
        return {'n': int(c.sum()), 'at_0': int(c[0]), 'ratio': round(float(c[0] / base), 4)}

    # A3: the birthday ratio where nobody picks the day (home births) and by the mother's age. Raw O/E against the
    # independence expectation of each year and key - no 8-30-day baseline (the tables keep only the diagonal).
    def ghost(diags, years, place=None, deliv=None, band=None):
        import numpy as np
        o = e = n = 0.0
        for y in years:
            for k, v in diags[y]['ghost'].items():
                pl, dl, bd = k.split('|')
                if (place and pl != place) or (deliv and dl != deliv) or (band and bd != band) or v['n'] == 0:
                    continue
                M, K = np.array(v['M'], float), np.array(v['K'], float)
                o += sum(v['D'])
                e += float((M * K).sum() / v['n'])
                n += v['n']
        r = o / e if e else None
        se = 1 / math.sqrt(o) if o else 0
        return {'n': int(n), 'o': int(o), 'e': round(e, 1), 'ratio': round(r, 4) if r else None,
                'lo': round(r * math.exp(-1.96 * se), 4) if r else None, 'hi': round(r * math.exp(1.96 * se), 4) if r else None}

    mx_ghost_years = [y for y in mx_years if y not in mx_clean]
    bands = [f'{lo}-{hi}' for lo, hi in AGE_BANDS]
    ghosts = {
        'mx_home_by_year': [{'year': y, **ghost(mx_diag, [y], 'home')} for y in mx_years],
        'mx_home_ghost_years': ghost(mx_diag, mx_ghost_years, 'home'),
        'mx_home_clean': ghost(mx_diag, mx_clean, 'home'),
        'br_home': ghost(br_diag, br_years, 'home'),
        'mx_vaginal_by_age_ghost_years': {b: ghost(mx_diag, mx_ghost_years, 'facility', 'vag', b) for b in bands},
        'mx_vaginal_by_age_clean': {b: ghost(mx_diag, mx_clean, 'facility', 'vag', b) for b in bands},
        'br_vaginal_by_age': {b: ghost(br_diag, br_years, 'facility', 'vag', b) for b in bands},
        'mx_ghost_years': mx_ghost_years,
    }

    copy_check = {
        'mx_vs_certificate': vs(mx_diag, mx_years, 'vs_certificate'),
        'mx_vs_birth_same_rows': vs(mx_diag, mx_years, 'vs_birth_same_rows'),
        'br_vs_declaration': vs(br_diag, br_decl, 'vs_certificate'),
        'br_vs_birth_same_rows': vs(br_diag, br_decl, 'vs_birth_same_rows'),
    }

    by_year = {}
    for name in ('mx_all', 'mx_cs', 'mx_vaginal', 'mx_vaginal_public', 'mx_vaginal_private', 'mx_cs_private',
                 'mx_cs_public', 'mx_cs_planned', 'mx_cs_planned_private', 'br_all', 'br_cs_prelabour', 'br_cs_labour',
                 'br_vag_spont', 'br_vag_induced'):
        country = GROUPS[name][0]
        years = (mx_typed_all if 'planned' in name else mx_years) if country == 'mx' else br_years
        rows = []
        for y in years:
            s = g(name, [y])
            rows.append({'year': y, **{k: s[k] for k in ('n', 'on_birthday', 'spike', 'lo', 'hi', 'extra_births')}})
        by_year[name] = rows

    # the mother's birthday calendar: for each day of the year, births on that birthday against chance
    calendar = {}
    for name, years in (('mx_all', mx_years), ('br_all', br_years), ('mx_cs', mx_years), ('br_cs_prelabour', br_years)):
        if not years:
            continue
        country, cells = GROUPS[name]
        vec = mx_vec if country == 'mx' else br_vec
        od = sum(vec[(y, c)]['O_diag'] for y in years for c in cells if vec.get((y, c)))
        ed = sum(vec[(y, c)]['E_diag'] for y in years for c in cells if vec.get((y, c)))
        B = groups[name]['all']['baseline']
        calendar[name] = {'o': [int(x) for x in od], 'e': [round(float(x) * B, 2) for x in ed]}

    # diagnostics summed over the years each hypothesis uses
    def diag_sum(diags, years, key):
        tot = defaultdict(lambda: [0, 0])
        for y in years:
            for c, v in diags[y][key].items():
                if key == 'lag':
                    for side in ('bday', 'other'):
                        tot[f'{c}|{side}'][0] += v[side][0]
                        tot[f'{c}|{side}'][1] += v[side][1]
                else:
                    tot[c][0] += v[0]
                    tot[c][1] += v[1]
        return {k: v for k, v in tot.items()}

    def lag_by_deliv(country, years, diags):
        lag = diag_sum(diags, years, 'lag')
        out = {}
        for deliv in ('vag', 'cs'):
            for side in ('bday', 'other'):
                n = sum(v[0] for k, v in lag.items() if k.startswith(deliv) and k.endswith('|' + side))
                bad = sum(v[1] for k, v in lag.items() if k.startswith(deliv) and k.endswith('|' + side))
                out[f'{deliv}|{side}'] = {'n': n, 'outside_0_7': bad, 'share': round(bad / n, 5) if n else None}
        return out

    diagnostics = {
        'mx_certificate_lag': lag_by_deliv('mx', mx_blind, mx_diag),
        'br_certificate_lag': lag_by_deliv('br', br_decl, br_diag) if br_decl else None,
        'mx_daytime_share': {c: round(v[1] / v[0], 4) for c, v in diag_sum(mx_diag, mx_years, 'hours').items() if v[0]},
        'br_daytime_share': {c: round(v[1] / v[0], 4) for c, v in diag_sum(br_diag, br_years, 'hours').items() if v[0]},
        'mx_sunday_share': {c: round(v[1] / v[0], 4) for c, v in diag_sum(mx_diag, mx_years, 'sunday').items() if v[0]},
        'br_sunday_share': {c: round(v[1] / v[0], 4) for c, v in diag_sum(br_diag, br_years, 'sunday').items() if v[0]},
        'mx_clues_check': dict(sum((Counter(mx_diag[y]['clues_check']) for y in mx_years), Counter())),
        'mx_filters': dict(sum((Counter(mx_diag[y]['filters']) for y in mx_years), Counter())),
        'br_filters': dict(sum((Counter(br_diag[y]['filters']) for y in br_years), Counter())),
    }
    files = {
        'mx': [{'year': y, 'schema': mx_diag[y]['schema'], 'records': mx_diag[y]['n_raw'], 'kept': mx_diag[y]['kept'],
                'cs_typed_share': round(mx_diag[y]['cs_typed'][1] / mx_diag[y]['cs_typed'][0], 4)
                if mx_diag[y]['cs_typed'][0] else None} for y in mx_years],
        'br': [{'year': y, 'records': br_diag[y]['n_raw'], 'kept': br_diag[y]['kept'],
                'mother_date_share': round(br_diag[y]['mother_date_filled'] / br_diag[y]['n_raw'], 4),
                'declaration_date': br_diag[y]['declaration_date']} for y in sorted(br_diag)],
    }
    both = [groups[g]['all'] for g in ('mx_all', 'br_all') if groups[g]]
    total = sum(x['n'] for x in both)
    headline = {'births': total, 'on_birthday': sum(x['on_birthday'] for x in both),
                'extra': round(sum(x['extra_births'] for x in both))}
    r = {'sets': sets, 'groups': groups, 'by_year': by_year, 'calendar': calendar, 'diagnostics': diagnostics,
         'files': files, 'headline': headline, 'choice': choice, 'copy_check': copy_check, 'ghosts': ghosts}
    (DATA / 'computed.json').write_text(json.dumps(r, indent=1))
    log(f'computed: {total} births, {headline["on_birthday"]} on the mother\'s birthday, about {headline["extra"]} extra')
    log(json.dumps(choice))
    log(json.dumps(copy_check))
    log(json.dumps(ghosts))
    for name, v in groups.items():
        for k, s in v.items():
            log(f'  {name:24s} {k:6s} n={s["n"]:>10d} S={s["spike"]:.3f} [{s["lo"]:.3f}-{s["hi"]:.3f}] '
                f'D={s["near"]:.3f} dom={s["same_dom_other_month"]["ratio"]:.3f} sign={s["same_sign"]["ratio"]:.4f}')
    return True


# --------------------------------------------------------------------------------------------- validate
def hypotheses_sha():
    return hashlib.sha256(json.dumps(HYPOTHESES, sort_keys=True).encode()).hexdigest()[:8]


def validate():
    r = json.loads((DATA / 'computed.json').read_text())
    checks = []

    def check(name, ok, detail=''):
        checks.append({'check': name, 'ok': bool(ok), 'detail': detail})

    G, sets, dg = r['groups'], r['sets'], r['diagnostics']
    check('hypotheses unchanged since registration', hypotheses_sha() == HYPOTHESES_SHA256, hypotheses_sha())
    check('Mexico: all 18 years scanned', len(sets['mx_all_years']) == len(MX_YEARS), str(sets['mx_all_years']))
    check('Brazil: years with the mother\'s date', len(sets['br_years']) >= 12, str(sets['br_years']))
    check('Mexico: years with the C-section type', len(sets['mx_typed']) >= 2, str(sets['mx_typed_all']))
    check('Mexico: clean years (A1)', len(sets.get('mx_clean', [])) >= 2 and len(sets.get('mx_typed_clean', [])) >= 2,
          str(sets.get('mx_clean')))
    n_mx, n_br = G['mx_all']['all']['n'], G['br_all']['all']['n']
    check('Mexico cohort', 25e6 <= n_mx <= 45e6, f'{n_mx}')
    check('Brazil cohort', 25e6 <= n_br <= 45e6, f'{n_br}')
    cc = dg['mx_clues_check']
    priv = sum(v for k, v in cc.items() if k.startswith('priv|'))
    pub = sum(v for k, v in cc.items() if k.startswith('pub|'))
    check('private births never carry a public CLUES', cc.get('priv|public', 0) / priv < 0.01,
          f'{cc.get("priv|public", 0)} of {priv}')
    check('public births rarely carry a private CLUES', cc.get('pub|SMP', 0) / pub < 0.01, f'{cc.get("pub|SMP", 0)} of {pub}')
    # the planned-C-section code must look booked: more daytime births and fewer Sundays than emergencies
    mxd, mxs = dg['mx_daytime_share'], dg['mx_sunday_share']
    check('MX planned C-sections are a daytime affair', mxd['cs_planned.pub'] > mxd['cs_emerg.pub'] + 0.10,
          f'{mxd["cs_planned.pub"]} vs {mxd["cs_emerg.pub"]}')
    check('MX planned C-sections avoid Sunday', mxs['cs_planned.pub'] < mxs['cs_emerg.pub'],
          f'{mxs["cs_planned.pub"]} vs {mxs["cs_emerg.pub"]}')
    brd, brs = dg['br_daytime_share'], dg['br_sunday_share']
    check('BR pre-labour C-sections are a daytime affair', brd['cs_prelabour'] > brd['cs_labour'] + 0.05,
          f'{brd["cs_prelabour"]} vs {brd["cs_labour"]}')
    check('BR pre-labour C-sections avoid Sunday', brs['cs_prelabour'] < brs['cs_labour'],
          f'{brs["cs_prelabour"]} vs {brs["cs_labour"]}')
    check('BR spontaneous births ignore Sunday', 0.12 <= brs['vag_spont'] <= 0.16, f'{brs["vag_spont"]}')

    mt = lambda name: G[name]['blind']  # noqa: E731  Mexico, years outside the exploration
    br = lambda name: G[name]['all']  # noqa: E731
    lag_ok = lambda lag: all(  # noqa: E731
        lag[f'{d}|bday']['share'] <= 1.5 * lag[f'{d}|other']['share'] for d in ('vag', 'cs'))
    hyp = {
        'H1': mt('mx_cs_planned')['spike'] >= 1.25 and mt('mx_cs_planned')['lo'] > 1.15,
        'H2': br('br_cs_prelabour')['spike'] >= 1.20 and br('br_cs_prelabour')['lo'] > 1.10,
        'H3': 0.95 <= br('br_vag_spont')['spike'] <= 1.05,
        'H4': mt('mx_cs_planned')['spike'] - mt('mx_cs_emergency')['spike'] >= 0.10
              and br('br_cs_prelabour')['spike'] - br('br_cs_labour')['spike'] >= 0.10,
        'H5': mt('mx_cs_private')['spike'] - mt('mx_cs_public')['spike'] >= 0.10,
        'H6': all(x['same_dom_other_month']['ratio'] >= 1.02 and x['same_dom_other_month']['lo'] > 1.00
                  for x in (mt('mx_cs_planned'), br('br_cs_prelabour')))
              and 0.98 <= br('br_vag_spont')['same_dom_other_month']['ratio'] <= 1.02,
        'H7': lag_ok(dg['mx_certificate_lag']) and (dg['br_certificate_lag'] is None or lag_ok(dg['br_certificate_lag'])),
        'H8': all(x['same_sign']['ratio'] >= 1.01 and x['same_sign_beyond_3_days']['ratio'] >= 1.01
                  for x in (mt('mx_all'), br('br_all'))),
        'H9': all(x['near'] < 1.00 and x['near_hi'] < 1.00 for x in (mt('mx_cs_planned'), br('br_cs_prelabour'))),
        'H10': br('br_vag_induced')['spike'] >= 1.05,
    }
    out = {'ok': all(c['ok'] for c in checks), 'checks': checks,
           'hypotheses': {k: {'text': HYPOTHESES[k], 'held': bool(v)} for k, v in hyp.items()},
           'hypotheses_sha': hypotheses_sha()}
    (DATA / 'validation.json').write_text(json.dumps(out, indent=1))
    for c in checks:
        log(('ok  ' if c['ok'] else 'FAIL') + f' {c["check"]}: {c["detail"]}')
    for k, v in out['hypotheses'].items():
        log(f'{k}: {"held" if v["held"] else "did not hold"}')
    return out['ok']


# --------------------------------------------------------------------------------------------- export
CSV_GROUPS = ['mx_all', 'mx_vaginal', 'mx_cs', 'mx_cs_planned', 'mx_cs_emergency', 'mx_cs_private', 'mx_cs_public',
              'br_all', 'br_vag_spont', 'br_vag_induced', 'br_cs', 'br_cs_prelabour', 'br_cs_labour']


def export():
    val = json.loads((DATA / 'validation.json').read_text())
    if not val['ok']:
        log('validation failed - nothing exported')
        return False
    r = json.loads((DATA / 'computed.json').read_text())
    manifest = json.loads((DATA / 'manifest.json').read_text())
    page = {
        'generated_from': {'fetched_on': manifest.get('fetched_on'), 'script': 'mother_birthday_births.py'},
        'signs': SIGNS,
        **{k: r[k] for k in ('sets', 'groups', 'by_year', 'diagnostics', 'files', 'headline', 'choice', 'copy_check',
                                     'ghosts')},
        'hypotheses': val['hypotheses'],
        'added_after_count': ADDED_AFTER_COUNT,
        'validation': {'ok': val['ok'], 'checks': val['checks']},
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(page, separators=(',', ':'), ensure_ascii=False) + '\n')
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('w') as fh:
        fh.write('country,group,years,measure,offset_days,observed,expected_if_independent,births_in_group\n')
        for name in CSV_GROUPS:
            written = set()
            for span, s in r['groups'][name].items():
                key = {'all': 'mx_all_years', 'blind': 'mx_blind', 'clean': 'mx_clean'}[span] if name[:2] == 'mx' else 'br_years'
                if 'planned' in name or 'emergency' in name:
                    key = {'all': 'mx_typed_all', 'blind': 'mx_typed', 'clean': 'mx_typed_clean'}[span]
                years = r['sets'][key]
                yr = f'{min(years)}-{max(years)}' + (' except 2023' if span == 'blind' and 2023 in range(min(years), max(years)) else '')
                if tuple(years) in written:  # planned C-sections: the blind and the clean years are the same two
                    continue
                written.add(tuple(years))
                for p in s['profile']:
                    fh.write(f'{name[:2]},{name},{yr},offset,{p["k"]},{p["o"]},{p["e"]},{s["n"]}\n')
                for m in MASKS_EXPORT:
                    fh.write(f'{name[:2]},{name},{yr},{m},,{s[m]["o"]},{s[m]["e"]},{s["n"]}\n')
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB)')
    return True


MASKS_EXPORT = ['same_dom_other_month', 'same_sign', 'same_sign_beyond_3_days', 'same_month']

if __name__ == '__main__':
    steps = {'fetch': fetch, 'scan': scan, 'compute': compute, 'validate': validate, 'export': export}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    sys.exit(1 if steps[sys.argv[1]]() is False else 0)
