#!/usr/bin/env python3
"""Marriages in Russia by month and by region: leap years, May, Great Lent and retrograde Venus.

Source of the numbers on https://startarot.online/ru/research/svadby-i-primety-rossiya

Needs Python 3.10+ and
    pip install numpy pandas openpyxl xlrd
plus ``bsdtar`` (libarchive: built into macOS, ``apt install libarchive-tools`` on Debian/Ubuntu) for the
RAR/ZIP archives, ``7z`` (``brew install p7zip`` / ``apt install p7zip-full``) for the one ARJ archive (the
2002 yearbook), and one of ``antiword`` (``apt install antiword``), ``textutil`` (macOS) or LibreOffice
``soffice`` for the Word files of the 2002–2009 yearbooks. The raw files (about 120 MB) go to
$MARRIAGES_DATA (default: ./marriages-data next to this script). Steps, in order:

    python3 russia_marriages.py fetch      # Rosstat yearbooks and bulletins (resumable)
    python3 russia_marriages.py compute    # tables + calendar + estimates -> $MARRIAGES_DATA
    python3 russia_marriages.py validate   # cross-checks between editions, levels and periods
    python3 russia_marriages.py export     # page JSON + dataset CSV (+ a copy of this script in the repo)

Run from the repo, export writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/russia-marriages.json      data the page renders
    frontend/static/research/russia-marriages.csv        the open dataset (long format)
    frontend/static/research/russia_marriages.py         a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

What is counted
---------------
Marriages REGISTERED by the civil registry (ZAGS), by month and by year of registration, where the
couple registered (not where it lives). A church wedding without registration is not counted.

Sources (all Rosstat, rosstat.gov.ru)
-------------------------------------
* Demographic Yearbook of Russia (Демографический ежегодник России), editions 2002–2023: the national
  table "marriages by month of registration" (1990, 1995, 2000, 2005–2022: each edition prints a few
  years, the editions agree to the unit where they overlap), the national annual series (1960–2022), and
  in the 2002–2015 editions marriages by region (1999–2014).
* Annual bulletins "Natural movement of the population" (Естественное движение населения), 2008–2023:
  marriages by region for the year and the year before (2007–2023); the 2009–2015 archives also hold the
  cumulative quarterly bulletins (Q1, H1, 9 months), i.e. regional marriages by quarter 2008–2015.
Monthly counts by region exist only in Rosstat's EMISS (fedstat.ru), which answers 403 outside Russia;
the regional analysis therefore works on years (and quarters), the monthly one on the national series.

Method
------
* Leap years: each year against its centred 2×4-year moving average (``cycle_ratios``), nationally
  1992–2016 and by region 2000–2016 (2000 on crude rates, 2004–2016 on counts); 1996 by region on a
  four-year window calibrated on the national series (``lead_ratio``), as no regional series has 1994.
* Months (``monthly_models``), 2005–2022 without the months of ``EXCLUDED_MONTHS``: log marriages per day on
  year and month effects, each month's own linear drift, Fridays, Saturdays, public holidays, the share of
  the month in Great Lent (with Holy and Bright weeks), Krasnaya Gorka, the share in the Apostles' fast, a
  "beautiful" date and the share with Venus retrograde. Significance by randomisation: Easter dates swapped
  between years, the Venus calendar shifted round the span.
* May against January (``may_vs_january``): marriages per open day, with a bound that closes the registry
  for all of 1–10 May.

Regions are today's subjects of the Federation without the four regions annexed in 2022 and without
Crimea and Sevastopol (no series before 2014). Autonomous okrugs nested in a krai or oblast are counted
in it (Tyumen with Khanty-Mansi and Yamal-Nenets, Arkhangelsk with Nenets), and regions merged in
2005–2008 are counted in today's borders (Rosstat's tables of those years already print the merged unit
with the okrug as an "of which" row).

TLS: rosstat.gov.ru presents a certificate of the Russian Trusted Root CA, which ordinary trust stores do
not carry. ``fetch`` downloads from that one host without certificate verification and checks every file
against the SHA-256 pinned in ``SHA256`` below instead: a changed file stops the run (Rosstat republished
it — look at what changed, then update the pin).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
SLUG = 'svadby-i-primety-rossiya'
FILE_STEM = 'russia-marriages'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'russia_marriages.py'
    VENUS_CSV = REPO_ROOT / 'frontend' / 'static' / 'research' / 'retrograde-periods.csv'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
    VENUS_CSV = HERE / 'retrograde-periods.csv'
VENUS_URL = 'https://startarot.online/research/retrograde-periods.csv'
DATA = Path(os.environ.get('MARRIAGES_DATA') or HERE / 'marriages-data')
RAW = DATA / 'raw'
UA = 'Mozilla/5.0 (research script; startarot.online)'
ROSSTAT = 'https://rosstat.gov.ru/storage/'

FIRST_YEAR, LAST_YEAR = 1990, 2023
# Years a shock outside the calendar moved by far more than any custom: the 2020 lockdowns. A year is
# left out of the leap-year comparison when its five-year window holds one of them.
SHOCK_YEARS = {2020}
MONTHS_RU = ['Январ', 'Феврал', 'Март', 'Апрел', 'Ма', 'Июн', 'Июл', 'Август', 'Сентябр', 'Октябр', 'Ноябр', 'Декабр']

# key: (url relative to ROSSTAT, kind, edition or bulletin year)
YEARBOOKS = {
    'dy2023': ('2024/04-20/VF5GE3HA/Dem_ej_03-2023.xlsx', 'yearbook', 2023),
    'dy2021': ('mediabank/dem21.rar', 'yearbook', 2021),
    'dy2019': ('mediabank/dem19.rar', 'yearbook', 2019),
    'dy2017': ('mediabank/2UmWgnCC/demo17.rar', 'yearbook', 2017),
    'dy2015': ('mediabank/demo15.rar', 'yearbook', 2015),
    'dy2014': ('mediabank/demo-pr14.rar', 'yearbook', 2014),
    'dy2013': ('mediabank/demo13.rar', 'yearbook', 2013),
    'dy2012': ('mediabank/demo12.rar', 'yearbook', 2012),
    'dy2009': ('mediabank/demo(3).zip', 'yearbook_doc', 2009),
    'dy2008': ('mediabank/demo(2).zip', 'yearbook_doc', 2008),
    'dy2007': ('mediabank/demo(1).zip', 'yearbook_doc', 2007),
    'dy2006': ('mediabank/demo.zip', 'yearbook_doc', 2006),
    'dy2005': ('mediabank/DEMO.zip', 'yearbook_doc', 2005),
    'dy2002': ('mediabank/DEM02.ARJ', 'yearbook_doc', 2002),
}
BULLETINS = {
    'edn2023': ('mediabank/EDN_2023.xlsx', 'bulletin', 2023),
    'edn2022': ('mediabank/EDN_2022.xlsx', 'bulletin', 2022),
    'edn2021': ('mediabank/EDN_2021.xlsx', 'bulletin', 2021),
    'edn2020': ('mediabank/73RhLoAX/edn_2020.xlsx', 'bulletin', 2020),
    'edn2019': ('mediabank/edn19.rar', 'bulletin', 2019),
    'edn2018': ('mediabank/edn18.xlsx', 'bulletin', 2018),
    'edn2017': ('mediabank/edn17-g.rar', 'bulletin', 2017),
    'edn2016': ('mediabank/edn16-g.rar', 'bulletin', 2016),
    'edn2015': ('mediabank/edn15-god.rar', 'bulletin', 2015),
    'edn2014': ('mediabank/edn14-god.rar', 'bulletin', 2014),
    'edn2013': ('mediabank/edn13-god.rar', 'bulletin', 2013),
    'edn2012': ('mediabank/edn12g.rar', 'bulletin', 2012),
    'edn2011': ('mediabank/edn11g.rar', 'bulletin', 2011),
    'edn2010': ('mediabank/edn10g.rar', 'bulletin', 2010),
    'edn2009': ('mediabank/edn09g.zip', 'bulletin', 2009),
    'edn2008': ('mediabank/edn08.zip', 'bulletin', 2008),
}
# "Regions of Russia. Socio-economic indicators", editions 2002–2007: crude marriage rate by region (per
# 1,000 population, one decimal) for 1990 and 1995–2006 — the only regional series before 2002. The
# 2005 edition (soc-pok.zip) is left out: its Word tables lose their cell boundaries in conversion.
REGION_BOOKS = {
    'rr2007': ('mediabank/soc-pok(2).zip', 'regions_doc', 2007),
    'rr2006': ('mediabank/soc-pok(1).zip', 'regions_doc', 2006),
    'rr2004': ('mediabank/reg_pok.zip', 'regions_doc', 2004),
    'rr2003': ('mediabank/TOM2.ZIP', 'regions_doc', 2003),
    'rr2002': ('mediabank/TOM2.rar', 'regions_doc', 2002),
}
# 2020 census (held in 2021), volume 5, table 1 "national composition": one sheet per region. The share of
# Russians among those who stated a nationality measures where the Russian Orthodox wedding customs are the
# majority's own.
CENSUS = {'census2021': ('mediabank/Tom5_tab1_VPN-2020.xlsx', 'census', 2021)}
SOURCES = {**YEARBOOKS, **BULLETINS, **REGION_BOOKS, **CENSUS}
# Pinned SHA-256 of every raw file (see TLS in the docstring); ``fetch`` prints the digest of an unpinned one.
SHA256: dict[str, str] = {
    'dy2023': '446453c3c56e251f7d9c93de3a3f66b2f43874109139be1092eae1f5db31142a',
    'dy2021': '53608591e7274db0c61a4987aab9914be550e3be509801baa9bb3da6807539b8',
    'dy2019': '5e5c52bcbe5b7412a23583cc8b04d009f922aee8dc84ca94ea39fa2a3de89150',
    'dy2017': 'c03b36cec69a936f2d8d15f7358a9ee3b47eea8dc7b4c75331f176ec7edec3d4',
    'dy2015': 'f32278358d9d1abedc6355a45228c182e107870748942876fe46ae0135a3e150',
    'dy2014': '38ebfde4de2081d6a863be721107ce42785ba7fbc2d762dba529a3d562c79f31',
    'dy2013': '19e62b38ef67bbc96ba2242ae7cf4926664ead9da52c14319e26964f04ca144a',
    'dy2012': '606705ecb47d466bc0174ed4516c3392a61255d9bfe9a33fab8ef9e16e92a6a8',
    'dy2009': 'a034f2fcfa11473224dcd8cdc93e019ccb8bb303bd1be37dfbe596645a01b04e',
    'dy2008': 'f7e73ab5dce3612815b14d596c9a71b468dc175ed4b48cc0c66b6f07bdf2b99a',
    'dy2007': 'dea8b147f06250c11293cb54cac4e50d2f0a3e7885a8102bf5ecd4d20473a501',
    'dy2006': 'bf2ae8993dbaf1e0f95e0ec50fb13217e6a8babfa6db70c4ebd33fea17eb2d92',
    'dy2005': '9c1e042135540d9394f9313f23bca86bbdf2ecf4ce7f6a5c246e2c278da23775',
    'dy2002': 'e2a056e74fe349167fd8a8c96ddd77e9f6662d1c7aeb28af583935330b49e4ba',
    'census2021': 'd4ada3910e33fc2322c5e8ab9fabc39c078841f043616bd6bbebd6964b28d6e1',
    'edn2023': '3c35d9f2e98f4f94aa357859e5630b190b5dac263e02393c48591ee534f46321',
    'edn2022': '7b6238031b42e6fae7862ecc07abb01bc7571c9b19298bf8209d7e6a83ed5b4a',
    'edn2021': '3debe163ac9ea648c0caa4b149c89cc8a6ca622a77f76d8dbadbb9bcb3ec3be9',
    'edn2020': 'd1196d7f95741f9f4fc8c660cc0e9ce9766d51b7c9c1757025da8edf9909753f',
    'edn2019': '50f02330c372d73cec9803680d890b9e79dc25ed7e2073d06acffd5fe74154cf',
    'edn2018': '1f9110b8050c4e37aca2a9d1022df195b84f0a250ab71213eb7f6d3441cdb4e5',
    'edn2017': '478d3aee70bdbfc6ce7f4bdcbadd75c0c7ad1875c9c91281ff0f4af4dbc2379a',
    'edn2016': 'd616e4f7dfd37ffaf26ec2b0ae0ffe0671f66651040d7fbbb53d94a2f18c3be8',
    'edn2015': '4480a441917be74f1a7a2535dc5b20685163db0c909684789c561a655c0faceb',
    'edn2014': '9c904d49efac26ea27eab7a4d658618301ef2aeb33f0b77e2277da314f64039c',
    'edn2013': '5530f82585af124ef54483ec4641d037e15cd59759d3d03aed0a32610ccdb32f',
    'edn2012': 'e9269ab6b8c099cc5c49d475db1ae3a5b9870979c30f30e559642163cd1c12e2',
    'edn2011': 'eb7ac58bb73f68b5f9df3aaa80615fe95611b7b97d116e0196453d6997e65ca4',
    'edn2010': 'f8042782b6b38944e1dff8e845acb09a4f9a22cac87bd5d2ee954f8573be5879',
    'edn2009': 'c69040419ebddc0674f197b01844129e3b9deaff40484f67df932d9b6fa39159',
    'edn2008': '3faaac344249fc2e79adc8df905cc9dc1a63ed5bd783c0971b2a9b547ac96aa3',
    'rr2007': '237abbdff0b94acf7e7fa0eb4ddd699c4564bd92d1cf7a25973c9e16527bf799',
    'rr2006': '3db21673a030fb3c3fc2975c8a14df7932cae9ea887f6281b19a830bce9c3376',
    'rr2004': '0b9c4d69f6eda097efce419839bb21b783d7d25c7965bd3e8f52598f52e797dc',
    'rr2003': '58ee00dbb983334c468e47f00c000d1538fa275b73fb29773fe5e4ee6f29a42d',
    'rr2002': '040a54660053fba1c16e244b6ec3033925c51455826358a0cc31dcb783586b70',
}

# Today's subjects (Rosstat order) and the names they had in the tables since 1990. Keys are
# ``norm()``-ed names; None = a row that is not a region of the analysis (see ``SKIP_REASON``).
REGIONS = {
    'BEL': 'Белгородская область', 'BRY': 'Брянская область', 'VLA': 'Владимирская область',
    'VOR': 'Воронежская область', 'IVA': 'Ивановская область', 'KLU': 'Калужская область',
    'KOS': 'Костромская область', 'KRS': 'Курская область', 'LIP': 'Липецкая область',
    'MOS': 'Московская область', 'ORL': 'Орловская область', 'RYA': 'Рязанская область',
    'SMO': 'Смоленская область', 'TAM': 'Тамбовская область', 'TVE': 'Тверская область',
    'TUL': 'Тульская область', 'YAR': 'Ярославская область', 'MOW': 'Москва',
    'KR': 'Республика Карелия', 'KO': 'Республика Коми', 'ARK': 'Архангельская область',
    'VLG': 'Вологодская область', 'KGD': 'Калининградская область', 'LEN': 'Ленинградская область',
    'MUR': 'Мурманская область', 'NGR': 'Новгородская область', 'PSK': 'Псковская область',
    'SPE': 'Санкт-Петербург', 'AD': 'Республика Адыгея', 'KL': 'Республика Калмыкия',
    'KDA': 'Краснодарский край', 'AST': 'Астраханская область', 'VGG': 'Волгоградская область',
    'ROS': 'Ростовская область', 'DA': 'Республика Дагестан', 'IN': 'Республика Ингушетия',
    'KB': 'Кабардино-Балкарская Республика', 'KC': 'Карачаево-Черкесская Республика',
    'SE': 'Республика Северная Осетия — Алания', 'CE': 'Чеченская Республика', 'STA': 'Ставропольский край',
    'BA': 'Республика Башкортостан', 'ME': 'Республика Марий Эл', 'MO': 'Республика Мордовия',
    'TA': 'Республика Татарстан', 'UD': 'Удмуртская Республика', 'CU': 'Чувашская Республика',
    'PER': 'Пермский край', 'KIR': 'Кировская область', 'NIZ': 'Нижегородская область',
    'ORE': 'Оренбургская область', 'PNZ': 'Пензенская область', 'SAM': 'Самарская область',
    'SAR': 'Саратовская область', 'ULY': 'Ульяновская область', 'KGN': 'Курганская область',
    'SVE': 'Свердловская область', 'TYU': 'Тюменская область', 'CHE': 'Челябинская область',
    'AL': 'Республика Алтай', 'TY': 'Республика Тыва', 'KK': 'Республика Хакасия',
    'ALT': 'Алтайский край', 'KYA': 'Красноярский край', 'IRK': 'Иркутская область',
    'KEM': 'Кемеровская область', 'NVS': 'Новосибирская область', 'OMS': 'Омская область',
    'TOM': 'Томская область', 'SA': 'Республика Саха (Якутия)', 'KAM': 'Камчатский край',
    'PRI': 'Приморский край', 'KHA': 'Хабаровский край', 'AMU': 'Амурская область',
    'MAG': 'Магаданская область', 'SAK': 'Сахалинская область', 'YEV': 'Еврейская автономная область',
    'CHU': 'Чукотский автономный округ', 'BU': 'Республика Бурятия', 'ZAB': 'Забайкальский край',
}
ALIASES = {
    'пермская': 'PER', 'читинская': 'ZAB', 'камчатская': 'KAM', 'тува': 'TY',
    'калмыкия хальмг тангч': 'KL', 'кемеровская кузбасс': 'KEM', 'чувашская чувашия': 'CU',
    'адыгея адыгея': 'AD', 'татарстан татарстан': 'TA', 'северная осетия': 'SE', 'рсо алания': 'SE',
}
SKIP = {
    'ненецкий': 'okrug counted in its oblast', 'ханты мансийский югра': 'okrug counted in its oblast',
    'ханты мансийский': 'okrug counted in its oblast', 'ямало ненецкий': 'okrug counted in its oblast',
    'хмао': 'okrug counted in its oblast', 'янао': 'okrug counted in its oblast',
    'коми пермяцкий': 'merged into Perm krai (2005)', 'агинский бурятский': 'merged into Zabaykalsky krai (2008)',
    'усть ордынский бурятский': 'merged into Irkutsk oblast (2008)', 'корякский': 'merged into Kamchatka krai (2007)',
    'таймырский долгано ненецкий': 'merged into Krasnoyarsk krai (2007)',
    'эвенкийский': 'merged into Krasnoyarsk krai (2007)', 'чечено ингушская': 'split in 1992',
}
# Units Rosstat counts in "Russia" but the analysis leaves out: kept under an X- code so that the
# regions still add up to the national row in ``validate``.
EXCLUDED = {
    'крым': 'X-CRIMEA', 'севастополь': 'X-SEVASTOPOL', 'донецкая народная': 'X-DPR',
    'луганская народная': 'X-LPR', 'запорожская': 'X-ZAP', 'херсонская': 'X-KHE',
}
HOMOGLYPHS = str.maketrans('aceopxyABCEHKMOPTX', 'асеорхуАВСЕНКМОРТХ')


def norm(name: str) -> str:
    s = str(name).replace(' ', ' ').translate(HOMOGLYPHS).lower().replace('ё', 'е')
    s = re.sub(r'^\s*\d+[аб]?\.\s*', '', s)            # "37. Кабардино-…", "75а. Таймырский…"
    s = re.sub(r'\s*\d+\)?\s*$', '', s)                 # footnote marks: "область1)"
    s = re.sub(r'\(\s*\d{4}[^)]*\)', ' ', s)            # "(1990 г. – включая Чеченскую Республику)"
    s = re.sub(r'[()\.,\-–—:]', ' ', s)
    s = re.sub(r'(?<!\w)(г|город|республика|область|край|автономный|автономная|авт|округ|ао|обл)(?!\w)', ' ', s)
    return ' '.join(s.split())


_KEYS = {norm(v): k for k, v in REGIONS.items()} | ALIASES
_KEYS[norm('Республика Северная Осетия-Алания')] = 'SE'


def region_code(name: str) -> str | None:
    """Code of a row name; None for a row that is no region of the analysis (totals, federal districts,
    nested or merged okrugs, …). Raises on a name nobody mapped, so a new spelling cannot drop a region."""
    n = norm(name)
    if n in _KEYS:
        return _KEYS[n]
    if n in ('российская федерация',) or 'федеральный' in n or n.startswith('в том числе') or ' без ' in f' {n} ':
        return None
    if n in SKIP:
        return None
    if n in EXCLUDED:
        return EXCLUDED[n]
    raise KeyError(f'unmapped region name: {name!r} (normalized {n!r})')


def log(*a):
    print(*a, flush=True)


# ------------------------------------------------------------------ downloads
def curl(url: str, dest: Path, tries: int = 8) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return
    tmp = dest.with_suffix(dest.suffix + '.part')
    for _ in range(tries):
        # --insecure only for rosstat.gov.ru, whose CA is not in common trust stores; the file is
        # checked against its pinned SHA-256 right after (``verify_pin``)
        insecure = ['--insecure'] if url.startswith(ROSSTAT) else []
        r = subprocess.run(['curl', '-sSL', '-f', *insecure, '-A', UA, '-m', '1800', '-C', '-', '-o', str(tmp), url])
        if r.returncode == 0:
            tmp.rename(dest)
            return
        time.sleep(5)
    raise RuntimeError(f'download failed: {url}')


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def verify_pin(key: str, p: Path) -> str:
    d = sha256(p)
    if SHA256.get(key) and SHA256[key] != d:
        raise RuntimeError(f'{p.name}: SHA-256 {d} differs from the pinned {SHA256[key]} — Rosstat changed the '
                           f'file; inspect it, then update SHA256["{key}"]')
    return d


def extract(archive: Path, dest: Path) -> None:
    """Unpack an archive and every archive inside it (the 2014/2015 yearbooks and the 2012 bulletin nest
    them). The 2012 bulletin stores its names in CP866: retried with that header charset."""
    dest.mkdir(parents=True, exist_ok=True)
    if archive.suffix.lower() == '.arj':  # libarchive has no ARJ reader
        if not shutil.which('7z'):
            raise RuntimeError('unpacking the 2002 yearbook (ARJ) needs 7z')
        subprocess.run(['7z', 'x', '-y', f'-o{dest}', str(archive)], capture_output=True, check=True)
        return
    for opts in ([], ['--options', 'hdrcharset=CP866']):
        if subprocess.run(['bsdtar', *opts, '-xf', str(archive), '-C', str(dest)], capture_output=True).returncode == 0:
            break
    else:
        raise RuntimeError(f'cannot unpack {archive}')
    done = {archive.resolve()}
    while True:
        inner = [p for p in dest.rglob('*') if p.suffix.lower() in ('.rar', '.zip') and p.resolve() not in done]
        if not inner:
            return
        for p in inner:
            done.add(p.resolve())
            sub = p.with_name(p.stem + '.d')
            sub.mkdir(exist_ok=True)
            for opts in ([], ['--options', 'hdrcharset=CP866']):
                if subprocess.run(['bsdtar', *opts, '-xf', str(p), '-C', str(sub)], capture_output=True).returncode == 0:
                    break


def fetch():
    digests = {}
    for key, (path, _, _) in SOURCES.items():
        url = ROSSTAT + path
        dest = RAW / key / Path(path).name
        curl(url, dest)
        digests[key] = verify_pin(key, dest)
        if dest.suffix.lower() in ('.rar', '.zip', '.arj'):
            out = RAW / key / 'x'
            if not out.exists():
                extract(dest, out)
        log(f'{key}: {dest.name} ok')
    if not VENUS_CSV.exists():
        curl(VENUS_URL, DATA / 'retrograde-periods.csv')
    missing = [k for k in SOURCES if not SHA256.get(k)]
    if missing:
        log('unpinned files — paste into SHA256:')
        for k in missing:
            log(f"    '{k}': '{digests[k]}',")


# ------------------------------------------------------------------ reading tables
def sheets(path: Path):
    """(title text of the first rows, rows) of every sheet of an .xls/.xlsx file."""
    if path.suffix.lower() == '.xlsx':
        import openpyxl
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            yield head_text(rows), rows
    else:
        import xlrd
        wb = xlrd.open_workbook(str(path))
        for sh in wb.sheets():
            rows = [sh.row_values(i) for i in range(sh.nrows)]
            yield head_text(rows), rows


def head_text(rows, n: int = 8) -> str:
    return ' '.join(str(c) for r in rows[:n] for c in r if c not in (None, '')).replace('\n', ' ').upper()


def tables(key: str):
    """Every sheet of a source (all .xls/.xlsx files of its archive)."""
    root = RAW / key
    files = [p for p in root.rglob('*') if p.suffix.lower() in ('.xls', '.xlsx') and p.stat().st_size > 0]
    for p in sorted(files):
        try:
            yield from ((p, t, rows) for t, rows in sheets(p))
        except Exception as e:  # a broken file in an archive must not pass silently
            raise RuntimeError(f'{p}: {e}') from e


def is_num(c) -> bool:
    return isinstance(c, (int, float)) and not isinstance(c, bool) and not (isinstance(c, float) and np.isnan(c))


def month_index(label) -> int | None:
    if not isinstance(label, str):
        return None
    s = label.strip()
    for i, p in enumerate(MONTHS_RU):
        if s.startswith(p) and not (p == 'Ма' and s.startswith('Март')):
            return i + 1
    return None


def doc_text(path: Path) -> str:
    """Plain text of a Word 97 file: antiword, textutil (macOS) or LibreOffice, the first one present."""
    if shutil.which('antiword'):
        r = subprocess.run(['antiword', '-m', 'UTF-8.txt', '-w', '0', str(path)], capture_output=True)
        if r.returncode == 0:
            return r.stdout.decode('utf-8', 'replace')
    if shutil.which('textutil'):
        r = subprocess.run(['textutil', '-convert', 'txt', '-stdout', str(path)], capture_output=True)
        if r.returncode == 0:
            return r.stdout.decode('utf-8', 'replace')
    for office in ('soffice', 'libreoffice'):
        if shutil.which(office):
            with tempfile.TemporaryDirectory() as td:
                subprocess.run([office, '--headless', '--convert-to', 'txt:Text', '--outdir', td, str(path)],
                               capture_output=True, check=True)
                return (Path(td) / (path.stem + '.txt')).read_text(encoding='utf-8', errors='replace')
    raise RuntimeError('reading the 2005–2009 yearbooks needs antiword, textutil or LibreOffice')


def doc_cells(key: str, name: str = r'R-3\.DOC') -> list[str]:
    """Table cells of one chapter of a Word book (by default chapter 3 of a yearbook, marriages and
    divorces), in reading order."""
    files = [p for p in (RAW / key).rglob('*') if re.fullmatch(name, p.name, re.I)]
    if len(files) != 1:
        raise RuntimeError(f'{key}: expected one {name}, found {files}')
    text = doc_text(files[0]).replace(' ', ' ')
    return [c.strip() for c in re.split(r'[\n|\t]', text) if c.strip()]


def cell_int(c: str) -> int | None:
    s = c.replace('\xa0', '').replace(' ', '')
    return int(s) if re.fullmatch(r'\d+', s) else None


def cell_rate(c: str) -> float | None:
    # "3,4." is a typo of the 2002 "Regions of Russia"; pages of the 2002 yearbook print "5.7"
    s = c.replace('\xa0', '').replace(' ', '').rstrip('.')
    return float(s.replace(',', '.')) if re.fullmatch(r'\d+[,.]\d', s) else None


MISSING_CELL = re.compile(r'^[…\-–—]+$|^\.\.\.$')


# ------------------------------------------------------------------ parsers
def parse_monthly_rows(rows, edition: int, src: str) -> list[dict]:
    """"Marriages by month of registration" in a sheet: a row of years, then one row per month."""
    out, years = [], None
    for r in rows:
        nums = [int(c) for c in r if is_num(c) and 1950 < c < 2100 and c == int(c)]
        if years is None and len(nums) >= 3:
            years = nums
            continue
        m = month_index(r[0]) if r else None
        if years and m:
            vals = [int(c) for c in r[1:] if is_num(c)]
            if len(vals) != len(years):
                raise RuntimeError(f'{src}: month {m} has {len(vals)} values for {len(years)} years')
            out += [{'year': y, 'month': m, 'marriages': v, 'edition': edition, 'source': src} for y, v in zip(years, vals)]
    return out


def parse_monthly_cells(cells: list[str], edition: int, src: str) -> list[dict]:
    i = next(k for k, c in enumerate(cells) if 'БРАКИ ПО МЕСЯЦАМ' in c.upper())
    years, out, k = [], [], i + 1
    while month_index(cells[k]) is None:
        v = cell_int(cells[k])
        if v and 1950 < v < 2100:
            years.append(v)
        k += 1
    for _ in range(12):
        m = month_index(cells[k])
        vals = [cell_int(c) for c in cells[k + 1:k + 1 + len(years)]]
        if m is None or None in vals:
            raise RuntimeError(f'{src}: unexpected cells after "marriages by month": {cells[k:k + 1 + len(years)]}')
        out += [{'year': y, 'month': m, 'marriages': v, 'edition': edition, 'source': src} for y, v in zip(years, vals)]
        k += 1 + len(years)
    return out


def parse_annual_rows(rows, edition: int, src: str) -> list[dict]:
    """National table 3.1 "marriages and divorces": rows [year, marriages, divorces, rates…]."""
    out = []
    for r in rows:
        v = [c for c in r if c not in (None, '')]
        if len(v) >= 3 and is_num(v[0]) and 1950 < v[0] < 2100 and is_num(v[1]) and v[1] > 1e5:
            out.append({'year': int(v[0]), 'marriages': int(v[1]), 'edition': edition, 'source': src})
    return out


def parse_annual_cells(cells: list[str], edition: int, src: str) -> list[dict]:
    i = next(k for k, c in enumerate(cells) if c.upper().startswith('3.1. БРАКИ И РАЗВОДЫ'))
    j = next(k for k in range(i + 1, len(cells)) if re.match(r'^3\.2\.', cells[k]))
    out = []
    for k in range(i, j - 1):
        y, m = cell_int(cells[k]), cell_int(cells[k + 1])
        if y and 1950 < y < 2100 and m and m > 1e5:
            out.append({'year': y, 'marriages': m, 'edition': edition, 'source': src})
    return out


def parse_regional_yearbook_rows(rows, edition: int, src: str) -> list[dict]:
    """Yearbook table "marriages, divorces and rates by region": a name row, then [year, marriages, …]."""
    out, cur = [], None
    for r in rows:
        v = [c for c in r if c not in (None, '')]
        if not v:
            continue
        if isinstance(v[0], str) and not re.fullmatch(r'[\d\s.,]+', v[0]):
            cur = v[0]
            # a name row can carry its first year on the same row
            v = v[1:]
        if cur and len(v) >= 2 and is_num(v[0]) and 1950 < v[0] < 2100 and is_num(v[1]):
            out.append({'name': cur, 'year': int(v[0]), 'marriages': int(v[1]), 'period': 'Y',
                        'edition': edition, 'source': src})
    return out


def parse_regional_yearbook_cells(cells: list[str], edition: int, src: str) -> list[dict]:
    i = next(k for k, c in enumerate(cells) if re.match(r'^3\.2\. БРАКИ, РАЗВОДЫ', c.upper()))
    j = next((k for k in range(i + 1, len(cells)) if re.match(r'^3\.3\.', cells[k])), len(cells))
    out, cur = [], None
    for k in range(i + 1, j):
        c = cells[k]
        if re.match(r'^\d+[аб]?\.\s', c) or (not re.match(r'^[\d\s,.…-]+$', c) and 'табл' not in c and 'table' not in c):
            cur = c
            continue
        # a record is [year, marriages, divorces, rate, rate]: the shape, not the value, tells a year from
        # a count (Altai's 2088 marriages are no year)
        y = cell_int(c)
        rec = cells[k + 1:k + 5]
        if (cur and y and 1950 < y < 2100 and len(rec) == 4 and cell_int(rec[0]) is not None
                and cell_int(rec[1]) is not None and cell_rate(rec[2]) is not None and cell_rate(rec[3]) is not None):
            out.append({'name': cur, 'year': y, 'marriages': cell_int(rec[0]), 'period': 'Y', 'edition': edition,
                        'source': src})
    return out


def parse_rates_cells(cells: list[str], edition: int, src: str) -> list[dict]:
    """"Crude marriage rates" of "Regions of Russia": a header of years, then per region its name and one
    rate per year ("…" where Rosstat had no estimate); page breaks repeat the header after
    "Продолжение табл.". Ends at the next table title."""
    i = next(k for k, c in enumerate(cells) if 'ОБЩИЕ КОЭФФИЦИЕНТЫ БРАЧНОСТИ' in c.upper())
    years, k = [], i + 1
    while not years or cell_int(cells[k]) is not None:
        v = cell_int(cells[k])
        if v and 1950 < v < 2100:
            years.append(v)
        k += 1
    out = []
    while k < len(cells) and not re.match(r'^\d+\.\d+\.\s+[А-ЯЁ]', cells[k]):
        c = cells[k]
        if re.match(r'^\d\)', c):  # footnotes close the table
            break
        if (c.startswith('Продолжение') or c.startswith('(на 1000') or re.fullmatch(r'в том числе:?', c.lower())
                or (cell_int(c) or 0) in years):
            k += 1
            continue
        vals = cells[k + 1:k + 1 + len(years)]
        if len(vals) < len(years) or not all(cell_rate(v) is not None or MISSING_CELL.match(v) for v in vals):
            raise RuntimeError(f'{src}: row {c!r} is not {len(years)} rates: {vals}')
        out += [{'name': c, 'year': y, 'rate': cell_rate(v), 'period': 'Y', 'edition': edition, 'source': src}
                for y, v in zip(years, vals) if cell_rate(v) is not None]
        k += 1 + len(years)
    return out


def parse_census(key: str) -> pd.DataFrame:
    """Russians and all who stated a nationality, per region sheet. Some sheets carry the cube's member
    keys ("[P16_Nationality]…") in the first column: the label is the first text cell that is not a key."""
    import openpyxl
    path = next(p for p in (RAW / key).rglob('*.xlsx'))
    rows = []
    for ws in openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets:
        code = 'RU' if norm(ws.title) == 'российская федерация' else region_code(ws.title)
        if code is None:
            continue
        got = {}
        for r in ws.iter_rows(values_only=True):
            cells = [c for c in r if c is not None]
            k = next((i for i, c in enumerate(cells) if isinstance(c, str) and not c.startswith('[')), None)
            if k is None or k + 1 >= len(cells) or not is_num(cells[k + 1]):
                continue
            label = cells[k].strip()
            if label.startswith('Указавшие национальную принадлежность'):
                got['stated'] = int(cells[k + 1])
            elif label.startswith('Русские'):
                got['russians'] = int(cells[k + 1])
        if set(got) != {'stated', 'russians'}:
            raise RuntimeError(f'{key}: sheet {ws.title!r} lacks the stated/Russians rows')
        rows.append({'code': code, **got})
    df = pd.DataFrame(rows)
    df['russian_share_pct'] = (df.russians / df.stated * 100).round(2)
    return df


def bulletin_period(head: str) -> str:
    if 'I КВАРТАЛ' in head:
        return 'Q1'
    if 'ПОЛУГОДИЕ' in head:
        return 'H1'
    if '9 МЕСЯЦ' in head or 'ЯНВАРЬ-СЕНТЯБРЬ' in head:
        return '9M'
    return 'Y'


def parse_bulletin(rows, head: str, edition: int, src: str) -> list[dict]:
    """Bulletin table "marriages and divorces by region": [name, marriages this year, marriages last year,
    change, divorces …] (the 2022–2023 bulletins print the current year only)."""
    years = []
    for y in re.findall(r'(?<!\d)((?:19|20)\d\d)\s*Г', head):
        if int(y) not in years:
            years.append(int(y))
    if not years:
        years = [edition]
    period, out = bulletin_period(head), []
    for r in rows:
        if not r or not isinstance(r[0], str) or not r[0].strip():
            continue
        nums = [c for c in r[1:] if is_num(c)]
        if len(nums) < len(years[:2]):
            continue
        for y, v in zip(years[:2], nums[:2]):
            out.append({'name': r[0], 'year': y, 'marriages': int(v), 'period': period,
                        'edition': edition, 'source': src})
    return out


def read_sources() -> dict[str, pd.DataFrame]:
    monthly, annual, regional, rates = [], [], [], []
    for key, (_, kind, ed) in SOURCES.items():
        if kind == 'census':
            continue
        if kind == 'regions_doc':
            rates += parse_rates_cells(doc_cells(key, r'R[-_]0?2\.DOC'), ed, key)
            continue
        if kind == 'yearbook_doc':
            cells = doc_cells(key)
            monthly += parse_monthly_cells(cells, ed, key) if any('БРАКИ ПО МЕСЯЦАМ' in c.upper() for c in cells) else []
            annual += parse_annual_cells(cells, ed, key)
            regional += parse_regional_yearbook_cells(cells, ed, key)
            continue
        for p, head, rows in tables(key):
            if kind == 'yearbook':
                if 'БРАКИ ПО МЕСЯЦАМ' in head:
                    monthly += parse_monthly_rows(rows, ed, key)
                elif head.startswith('3.1. БРАКИ И РАЗВОДЫ'):
                    annual += parse_annual_rows(rows, ed, key)
                elif re.match(r'^\d+\.\d+\. БРАКИ, РАЗВОДЫ', head) and ('СУБЪЕКТАМ' in head or 'РЕГИОНАМ' in head):
                    regional += parse_regional_yearbook_rows(rows, ed, key)
            elif 'ЧИСЛО БРАКОВ И РАЗВОДОВ ПО СУБЪЕКТАМ' in head:
                regional += parse_bulletin(rows, head, ed, key)
    unmapped = set()

    def code_of(n):
        try:
            return 'RU' if norm(n) == 'российская федерация' else region_code(n)
        except KeyError:
            unmapped.add(f'{n!r} -> {norm(n)!r}')

    def coded(rows):
        df = pd.DataFrame(rows)
        df['code'] = df.name.map(code_of)
        return df[df.code.notna()]
    regional, rates = coded(regional), coded(rates)
    if unmapped:
        raise KeyError('unmapped region names (add them to ALIASES or SKIP):\n  ' + '\n  '.join(sorted(unmapped)))
    return {'monthly': pd.DataFrame(monthly), 'annual': pd.DataFrame(annual), 'regional': regional, 'rates': rates}


def latest(df: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """One value per key: the latest edition that prints it (later editions carry revisions)."""
    return df.sort_values('edition').groupby(keys, as_index=False).last()


# ------------------------------------------------------------------ calendar
def orthodox_easter(y: int) -> dt.date:
    """Orthodox Easter (Julian computus, Meeus), as a Gregorian date (1900–2099: +13 days)."""
    a, b, c = y % 4, y % 7, y % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month, day = divmod(d + e + 114, 31)
    return dt.date(y, month, day + 1) + dt.timedelta(days=13)


def venus_retro_days() -> set[dt.date]:
    p = VENUS_CSV if VENUS_CSV.exists() else DATA / 'retrograde-periods.csv'
    t = pd.read_csv(p)
    t = t[t.planet == 'Venus']
    days = set()
    for _, r in t.iterrows():
        a = dt.date.fromisoformat(r.station_retrograde_utc[:10])
        b = dt.date.fromisoformat(r.station_direct_utc[:10])
        days |= {a + dt.timedelta(days=i) for i in range((b - a).days + 1)}
    return days


def public_holidays(y: int) -> set[dt.date]:
    """Non-working public holidays by the Labour Code of the year (without the weekend transfers set by
    decree each year, which add bridge days mostly in January and May — see ``may_vs_january``)."""
    if y < 1992:  # Orthodox Christmas is a holiday from 1991
        md = [(1, 1), (3, 8), (5, 1), (5, 2), (5, 9), (10, 7), (11, 7), (11, 8)] + [(1, 7)] * (y >= 1991)
    elif y < 2002:  # Constitution Day (12 December) is a holiday from 1994
        md = [(1, 1), (1, 2), (1, 7), (3, 8), (5, 1), (5, 2), (5, 9), (6, 12), (11, 7), (11, 8)] + [(12, 12)] * (y >= 1994)
    elif y < 2005:
        md = [(1, 1), (1, 2), (1, 7), (2, 23), (3, 8), (5, 1), (5, 2), (5, 9), (6, 12), (11, 7), (12, 12)]
    elif y < 2013:
        md = [(1, d) for d in (1, 2, 3, 4, 5, 7)] + [(2, 23), (3, 8), (5, 1), (5, 2), (5, 9), (6, 12), (11, 4)]
    else:
        md = [(1, d) for d in range(1, 9)] + [(2, 23), (3, 8), (5, 1), (5, 9), (6, 12), (11, 4)]
    return {dt.date(y, m, d) for m, d in md}


def repeating_date_month(y: int, m: int) -> bool:
    """A month holding a "beautiful" date that couples chase: 05.05.05 … 12.12.12, 20.02.2020, 22.02.2022."""
    return (2001 <= y <= 2012 and m == y - 2000) or (y, m) in ((2020, 2), (2022, 2))


def calendar(years: range) -> pd.DataFrame:
    """Per year and month: days, Fridays, Saturdays (the registry's busy days), public holidays, days of the
    two fasts whose dates move with Easter (Great Lent with Holy and Bright weeks, when the Church does not
    marry; and the Apostles' fast), whether the month holds Krasnaya Gorka (St Thomas Sunday, Easter + 7, the
    traditional first wedding day after Easter), a "beautiful" date, and the days with Venus retrograde."""
    venus = venus_retro_days()
    rows = []
    for y in years:
        hol = public_holidays(y)
        e = orthodox_easter(y)
        lent = {e + dt.timedelta(days=i) for i in range(-48, 7)}
        apostles_end = dt.date(y, 7, 11)  # 29 June of the Julian calendar
        apostles = {e + dt.timedelta(days=i) for i in range(57, (apostles_end - e).days + 1)}
        gorka = e + dt.timedelta(days=7)
        for m in range(1, 13):
            first = dt.date(y, m, 1)
            n = (dt.date(y + (m == 12), m % 12 + 1, 1) - first).days
            days = [first + dt.timedelta(days=i) for i in range(n)]
            rows.append({'year': y, 'month': m, 'days': n,
                         'fridays': sum(d.weekday() == 4 for d in days),
                         'saturdays': sum(d.weekday() == 5 for d in days),
                         'holidays': sum(d in hol for d in days),
                         'lent_days': sum(d in lent for d in days),
                         'apostles_fast_days': sum(d in apostles for d in days),
                         'krasnaya_gorka': int(gorka.month == m),
                         'repeating_date': int(repeating_date_month(y, m)),
                         'venus_retro_days': sum(d in venus for d in days),
                         'leap_year': int(y % 4 == 0)})
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ estimates
MA_WEIGHTS = (0.125, 0.25, 0.25, 0.25, 0.125)  # centred 2×4 moving average: one weight per leap phase


def cycle_ratios(s: pd.Series) -> pd.DataFrame:
    """log(marriages in a year / their centred 2×4-year moving average), with the year's place in the leap
    cycle (phase 0 = leap year). The 2×4 average gives every phase of the cycle the same weight, so it keeps
    the trend and drops the cycle; the mean log ratio by phase is the cycle itself. (A plain comparison with
    the two neighbouring years would not do: the years around a leap year are themselves displaced by it.)
    Years whose five-year window touches SHOCK_YEARS are left out."""
    rows = []
    for y in s.index:
        win = range(y - 2, y + 3)
        if all(w in s.index for w in win) and not (set(win) & SHOCK_YEARS):
            ma = sum(w_ * s[w] for w_, w in zip(MA_WEIGHTS, win))
            rows.append({'year': y, 'phase': y % 4, 'log_ratio': float(np.log(s[y] / ma))})
    return pd.DataFrame(rows, columns=['year', 'phase', 'log_ratio'])


def lead_ratio(s: pd.Series, y: int) -> float | None:
    """log(marriages in ``y`` / plain mean of y-1 … y+2): the four years hold each leap phase once, like
    the 2×4 average, but centred half a year late — for a year whose y-2 is missing (1996 by region: no
    regional series has 1994). Its offset is calibrated on the national series (``compute``)."""
    win = range(y - 1, y + 3)
    if not all(w in s.index for w in win) or set(win) & SHOCK_YEARS:
        return None
    return float(np.log(s[y] / np.mean([s[w] for w in win])))


# Months whose count a registry or a shock moved, not the calendar: left out of the monthly model.
EXCLUDED_MONTHS = {
    **{(2018, m): 'every registry office moved to the federal register ЕГР ЗАГС on 1 October 2018: '
                  'recorded registrations fell by 30–50 % for three months' for m in (10, 11, 12)},
    **{(2020, m): 'COVID-19: offices closed or limited from April; February held 20.02.2020' for m in range(1, 13)},
    **{(2022, m): 'mobilisation from 21 September 2022: weddings brought forward' for m in (9, 10, 11, 12)},
}
# The consecutive monthly series. 1990, 1995 and 2000 show an older season (more winter weddings, the
# Soviet calendar) that one set of month effects cannot carry; they enter only the May–January comparison.
MODEL_YEARS = range(2005, 2023)
MODEL_TERMS = ['fridays', 'saturdays', 'holidays', 'lent_share', 'krasnaya_gorka', 'apostles_share',
               'repeating_date', 'venus_share']
PERMUTATIONS = 2000
SEED = 20261023


def model_frame(monthly: pd.DataFrame, cal: pd.DataFrame) -> pd.DataFrame:
    d = monthly.merge(cal, on=['year', 'month'])
    keep = d.year.isin(MODEL_YEARS) & ~pd.Series(list(zip(d.year, d.month))).isin(EXCLUDED_MONTHS).values
    d = d[keep].reset_index(drop=True)
    d['lent_share'] = d.lent_days / d.days
    d['apostles_share'] = d.apostles_fast_days / d.days
    d['venus_share'] = d.venus_retro_days / d.days
    d['y'] = np.log(d.marriages / d.days)
    return d


def design(d: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    """Year effects (the level and the leap cycle of each year), month effects, a linear drift of each
    month's effect (the season moved over two decades: February and the summer gained), and the calendar
    terms. January is the base month."""
    t = (d.year - 2013).astype(float)
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
    se = dict(zip(names, np.sqrt(np.diag(cov))))
    return dict(zip(names, b)), res, se


def easter_terms(y: int, easter: dt.date) -> np.ndarray:
    """lent_share, krasnaya_gorka, apostles_share of each month of ``y`` for a given Easter date."""
    lent = {easter + dt.timedelta(days=i) for i in range(-48, 7)}
    apostles = {easter + dt.timedelta(days=i) for i in range(57, (dt.date(y, 7, 11) - easter).days + 1)}
    gorka = (easter + dt.timedelta(days=7)).month
    out = np.zeros((12, 3))
    for m in range(1, 13):
        first = dt.date(y, m, 1)
        n = (dt.date(y + (m == 12), m % 12 + 1, 1) - first).days
        days = [first + dt.timedelta(days=i) for i in range(n)]
        out[m - 1] = (sum(x in lent for x in days) / n, int(gorka == m), sum(x in apostles for x in days) / n)
    return out


def monthly_models(monthly: pd.DataFrame, cal: pd.DataFrame) -> dict:
    """The calendar terms of the monthly model, each with a randomisation test instead of the textbook
    standard error (months of one year share a level and neighbouring months share weather, so the OLS
    error is too optimistic):
    * Easter terms (Lent, Krasnaya Gorka, the Apostles' fast): every year gets the Easter of another model
      year (its day of the year), PERMUTATIONS times; p = share of permuted coefficients at least as far from
      zero as the real one.
    * Venus: the day-by-day retrograde calendar is shifted round the 2005–2022 span by a random number of
      days (keeping the real length and spacing of the periods), PERMUTATIONS times.
    The smallest effect the data can show (80 % power, two-sided 5 %) is about 2.8 × the spread of the
    permuted coefficients."""
    d = model_frame(monthly, cal)
    b, res, se = fit(d)
    rng = np.random.default_rng(SEED)
    years = list(MODEL_YEARS)
    doy = {y: (orthodox_easter(y) - dt.date(y, 1, 1)).days for y in years}
    terms = {(y, src): easter_terms(y, dt.date(y, 1, 1) + dt.timedelta(days=doy[src])) for y in years for src in years}
    rows = [(years.index(y), m - 1) for y, m in zip(d.year, d.month)]
    perm_easter = []
    for _ in range(PERMUTATIONS):
        src = dict(zip(years, rng.permutation(years)))
        e = np.array([terms[(years[i], src[years[i]])][m] for i, m in rows])
        dp = d.copy()
        dp['lent_share'], dp['krasnaya_gorka'], dp['apostles_share'] = e[:, 0], e[:, 1], e[:, 2]
        bp, _, _ = fit(dp)
        perm_easter.append([bp['lent_share'], bp['krasnaya_gorka'], bp['apostles_share']])
    perm_easter = np.array(perm_easter)

    start, end = dt.date(MODEL_YEARS[0], 1, 1), dt.date(MODEL_YEARS[-1], 12, 31)
    span = (end - start).days + 1
    venus = venus_retro_days()
    v = np.array([(start + dt.timedelta(days=i)) in venus for i in range(span)], dtype=float)
    month_of_day = np.array([((start + dt.timedelta(days=i)).year - start.year) * 12 + (start + dt.timedelta(days=i)).month - 1
                             for i in range(span)])
    n_months = int(month_of_day.max()) + 1
    days_in = np.bincount(month_of_day, minlength=n_months)
    row_month = ((d.year - start.year) * 12 + d.month - 1).values
    perm_venus = []
    for _ in range(PERMUTATIONS):
        # A random offset of 60 days or more. A multiple of Venus's synodic period (~584 days) nearly
        # reproduces the real calendar; such draws belong to the null distribution all the same.
        k = int(rng.integers(60, span - 60))
        share = np.bincount(month_of_day, weights=np.roll(v, k), minlength=n_months) / days_in
        dp = d.copy()
        dp['venus_share'] = share[row_month]
        bp, _, _ = fit(dp)
        perm_venus.append(bp['venus_share'])
    perm_venus = np.array(perm_venus)

    def summary(name: str, perm: np.ndarray) -> dict:
        obs = b[name]
        mde = 2.8 * float(perm.std())
        # the permuted coefficients as a histogram (log units), for the page's "real against random" chart
        edges = np.linspace(-4 * perm.std(), 4 * perm.std(), 33)
        counts, _ = np.histogram(np.clip(perm, edges[0], edges[-1]), bins=edges)
        return {'coef': round(float(obs), 4), 'pct': round(100 * float(np.exp(obs) - 1), 1),
                'perm_hist': {'edges': [round(float(e), 5) for e in edges], 'counts': counts.tolist()},
                'ols_se': round(float(se[name]), 4),
                'perm_sd': round(float(perm.std()), 4),
                'p_value': round(float((np.sum(np.abs(perm) >= abs(obs)) + 1) / (len(perm) + 1)), 4),
                # in log terms the bound is symmetric; in per cent a rise and a fall differ
                'mde_log': round(mde, 4), 'mde_pct_up': round(100 * (np.exp(mde) - 1), 1),
                'mde_pct_down': round(100 * (np.exp(-mde) - 1), 1)}

    out = {
        'years': [int(y) for y in sorted(d.year.unique())],
        'months': int(len(d)),
        'excluded_months': [{'year': y, 'month': m, 'reason': r} for (y, m), r in EXCLUDED_MONTHS.items()],
        'residual_sd': round(float(res.std(ddof=0)), 4),
        'permutations': PERMUTATIONS,
        # coefficients are per whole month: a month spent entirely in Lent, with Venus retrograde, …
        'lent_share': summary('lent_share', perm_easter[:, 0]),
        'krasnaya_gorka': summary('krasnaya_gorka', perm_easter[:, 1]),
        'apostles_share': summary('apostles_share', perm_easter[:, 2]),
        'venus_share': summary('venus_share', perm_venus),
        'other_terms': {k: {'coef': round(float(b[k]), 4), 'pct': round(100 * float(np.exp(b[k]) - 1), 1),
                            'ols_se': round(float(se[k]), 4)}
                        for k in ('fridays', 'saturdays', 'holidays', 'repeating_date')},
    }
    return out


def may_vs_january(monthly: pd.DataFrame, cal: pd.DataFrame) -> dict:
    """Marriages per day the registry is open, as a share of the year's rate, in January and in May. Both
    months lose days to long holidays; only May carries a custom ("в мае жениться — всю жизнь маяться").
    Open days = days − public holidays of the Labour Code (no weekend transfers). The bound for May assumes
    the registry closed for all of 1–10 May every year — more than the transfers gave in any of the "clean"
    years (all of 1–10 May was off only in 2020 and 2021, which are not among them) — so the part of May's
    gap it leaves is not the holidays'. January is no wedding-free control for the Church (the Nativity fast
    and Svyatki run to 18 January), so the comparison understates the gap rather than inflating it. "Clean" years have Easter by 23 April: Bright Week and
    Krasnaya Gorka then end in April, and May holds neither the Church's pause nor its first wedding day."""
    d = monthly.merge(cal, on=['year', 'month'])
    rows = []
    for y, g in d.groupby('year'):
        # a year with an excluded month has a distorted total, the base of both indices
        if len(g) != 12 or y in SHOCK_YEARS or any((y, m) in EXCLUDED_MONTHS for m in range(1, 13)):
            continue
        g = g.set_index('month')
        open_days = g.days - g.holidays
        base = g.marriages.sum() / open_days.sum()
        jan = g.marriages[1] / open_days[1] / base
        may = g.marriages[5] / open_days[5] / base
        may_bound = g.marriages[5] / (g.days[5] - 10) / base
        rows.append({'year': int(y), 'january': round(float(jan), 3), 'may': round(float(may), 3),
                     'may_if_closed_1_10': round(float(may_bound), 3),
                     'clean_may': bool(orthodox_easter(y) <= dt.date(y, 4, 23))})
    t = pd.DataFrame(rows)
    recent = t[t.year >= MODEL_YEARS[0]]
    cols = ('january', 'may', 'may_if_closed_1_10')
    return {'by_year': rows,
            'mean_2005_2022': {k: round(float(recent[k].mean()), 3) for k in cols},
            'mean_2005_2022_clean_may': {k: round(float(recent[recent.clean_may][k].mean()), 3) for k in cols}
            | {'years': [int(y) for y in recent[recent.clean_may].year]}}


def compute():
    src = read_sources()
    mon, ann, reg, rat = src['monthly'], src['annual'], src['regional'], src['rates']
    mon.to_csv(DATA / 'monthly_all_editions.csv', index=False)
    ann.to_csv(DATA / 'annual_all_editions.csv', index=False)
    reg.to_csv(DATA / 'regional_all_sources.csv', index=False)
    rat.to_csv(DATA / 'regional_rates_all_editions.csv', index=False)
    region = ~reg.code.isin(['RU']) & ~reg.code.str.startswith('X-')
    rates = latest(rat[~rat.code.isin(['RU']) & ~rat.code.str.startswith('X-')], ['code', 'year'])[
        ['code', 'year', 'rate', 'source']]

    monthly = latest(mon, ['year', 'month'])[['year', 'month', 'marriages', 'source']]
    annual = latest(ann, ['year'])[['year', 'marriages', 'source']]
    # years after the last yearbook: the bulletin's national row
    ru = latest(reg[(reg.code == 'RU') & (reg.period == 'Y')], ['year'])
    extra = ru[~ru.year.isin(annual.year)][['year', 'marriages', 'source']]
    annual = pd.concat([annual, extra]).sort_values('year').reset_index(drop=True)
    regional = latest(reg[region & (reg.period == 'Y')], ['code', 'year'])[['code', 'year', 'marriages', 'source']]

    # quarters from the cumulative bulletins (Q1, H1, 9M, year) of the same year
    cum = latest(reg[region], ['code', 'year', 'period']).pivot_table(
        index=['code', 'year'], columns='period', values='marriages')
    quarters = pd.DataFrame()
    if {'Q1', 'H1', '9M', 'Y'} <= set(cum.columns):
        c = cum.dropna(subset=['Q1', 'H1', '9M', 'Y'])
        quarters = pd.DataFrame({'Q1': c.Q1, 'Q2': c.H1 - c.Q1, 'Q3': c['9M'] - c.H1, 'Q4': c.Y - c['9M']})
        quarters = quarters.reset_index().melt(id_vars=['code', 'year'], var_name='quarter', value_name='marriages')

    cal = calendar(range(min(monthly.year.min(), FIRST_YEAR), LAST_YEAR + 1))
    monthly.to_csv(DATA / 'national_monthly.csv', index=False)
    annual.to_csv(DATA / 'national_annual.csv', index=False)
    regional.to_csv(DATA / 'regional_annual.csv', index=False)
    rates.to_csv(DATA / 'regional_rates.csv', index=False)
    quarters.to_csv(DATA / 'regional_quarterly.csv', index=False)
    cal.to_csv(DATA / 'calendar.csv', index=False)

    nat = annual[annual.year >= FIRST_YEAR].set_index('year').marriages
    nr = cycle_ratios(nat)
    # Regions: counts where a year's whole window has them (2004–2016), otherwise the crude rate (2000).
    # A ratio never mixes the two measures; population moves by about 1 % over a five-year window and
    # smoothly, which the moving average absorbs, so rates and counts give the same ratio.
    by_region = []
    for code in sorted(set(regional.code) | set(rates.code)):
        r = cycle_ratios(regional[regional.code == code].set_index('year').marriages).assign(measure='count')
        q = cycle_ratios(rates[rates.code == code].set_index('year').rate).assign(measure='rate')
        both = pd.concat([r, q[~q.year.isin(r.year)]], ignore_index=True)
        if len(both):
            by_region.append(both.assign(code=code))
    rr = pd.concat(by_region, ignore_index=True).sort_values(['code', 'year'])

    # 1996 by region: no series has 1994, so the 2×4 average cannot be formed. The four-year mean
    # 1995–1998 holds each phase once too, centred half a year late; its offset against the 2×4 measure is
    # taken from the national series, which has both, for 1996 — and shown for the other leap years.
    lead_offset = {int(y): round(lead_ratio(nat, y) - float(nr.set_index('year').log_ratio[y]), 4)
                   for y in nr[nr.phase == 0].year if lead_ratio(nat, y) is not None}
    lead96 = []
    for code in sorted(rates.code.unique()):
        v = lead_ratio(rates[rates.code == code].set_index('year').rate, 1996)
        if v is not None:
            lead96.append({'code': code, 'year': 1996, 'phase': 0, 'log_ratio': v - lead_offset[1996],
                           'measure': 'rate, 4-year window'})
    lead96 = pd.DataFrame(lead96)
    models = monthly_models(monthly, cal)
    may_jan = may_vs_january(monthly, cal)
    census = parse_census('census2021')
    census.to_csv(DATA / 'census_russian_share.csv', index=False)
    regions_tab, by_share = leap_by_region(pd.concat([rr, lead96], ignore_index=True), census, regional)
    regions_tab.to_csv(DATA / 'regional_summary.csv', index=False)
    mshare = monthly.merge(monthly.groupby('year').marriages.sum().rename('total'), on='year')
    mshare['share_pct'] = mshare.marriages / mshare.total * 100
    est = {
        'national_leap': {int(p): {'mean_log_ratio': round(float(g.log_ratio.mean()), 4), 'years': g.year.tolist()}
                          for p, g in nr.groupby('phase')},
        'regional_leap': {int(p): {'median_log_ratio': round(float(g.log_ratio.median()), 4),
                                   'share_negative': round(float((g.log_ratio < 0).mean()), 3), 'n': int(len(g))}
                          for p, g in rr.groupby('phase')},
        'national_cycle': [[int(r.year), int(r.phase), round(float(r.log_ratio), 4)] for r in nr.itertuples()],
        'regional_1996': {'median_log_ratio': round(float(lead96.log_ratio.median()), 4),
                          'share_negative': round(float((lead96.log_ratio < 0).mean()), 3), 'n': int(len(lead96)),
                          'national_offset_by_leap_year': lead_offset},
        'leap_by_russian_share': by_share,
        'monthly_model': models,
        'may_vs_january': may_jan,
        'may_share_pct': {int(r.year): round(float(r.share_pct), 2) for r in mshare[mshare.month == 5].itertuples()},
        'january_share_pct': {int(r.year): round(float(r.share_pct), 2) for r in mshare[mshare.month == 1].itertuples()},
    }
    pd.concat([rr, lead96], ignore_index=True).to_csv(DATA / 'regional_cycle_ratios.csv', index=False)
    (DATA / 'estimates.json').write_text(json.dumps(est, ensure_ascii=False, indent=1))
    log(f'monthly {len(monthly)} rows ({monthly.year.nunique()} years), annual {annual.year.min()}–{annual.year.max()}, '
        f'regional counts {regional.code.nunique()} regions × {regional.year.min()}–{regional.year.max()}, '
        f'rates {rates.code.nunique()} regions × {sorted(rates.year.unique())}, '
        f'quarterly {quarters.year.nunique() if len(quarters) else 0} years')
    for p, v in est['national_leap'].items():
        log(f'  national, phase {p}{" (leap)" if p == 0 else ""}: {100 * (np.exp(v["mean_log_ratio"]) - 1):+.1f} % vs the 4-year average')
    for p, v in est['regional_leap'].items():
        log(f'  regions,  phase {p}{" (leap)" if p == 0 else ""}: median {100 * (np.exp(v["median_log_ratio"]) - 1):+.1f} %, '
            f'below the average in {100 * v["share_negative"]:.0f} % of {v["n"]}')
    v = est['regional_1996']
    log(f'  regions,  1996 (4-year window): median {100 * (np.exp(v["median_log_ratio"]) - 1):+.1f} %, below in '
        f'{100 * v["share_negative"]:.0f} % of {v["n"]}; national offsets {v["national_offset_by_leap_year"]}')
    for g in by_share['groups']:
        log(f'  regions with {g["label"]} Russians: leap {g["leap_pct"]:+.1f} %, year before {g["pre_leap_pct"]:+.1f} % '
            f'({g["regions"]} regions)')
    log(f'  leap effect per +10 p.p. of Russians: {by_share["slope_pct_per_10pp"]:+.2f} % (permutation p = {by_share["p_value"]})')
    log(f'  monthly model {models["years"][0]}–{models["years"][-1]}, {models["months"]} months, '
        f'residual sd {models["residual_sd"]}:')
    for k in ('lent_share', 'krasnaya_gorka', 'apostles_share', 'venus_share'):
        m = models[k]
        log(f'    {k:15s} {m["pct"]:+6.1f} % (p = {m["p_value"]}, smallest visible effect '
            f'{m["mde_pct_up"]:+.1f} / {m["mde_pct_down"]:+.1f} %)')
    for k, m in models['other_terms'].items():
        log(f'    {k:15s} {m["pct"]:+6.1f} % (OLS se {m["ols_se"]})')
    log(f'  per open day, share of the year rate 2005–2022: {may_jan["mean_2005_2022"]}; '
        f'clean May years: {may_jan["mean_2005_2022_clean_may"]}')


SHARE_GROUPS = [(0, 30, 'under 30 %'), (30, 70, '30–70 %'), (70, 101, '70 % and more')]


def leap_by_region(ratios: pd.DataFrame, census: pd.DataFrame, regional: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Each region's leap-year effect (mean log ratio of its leap years: 1996 on the four-year window, 2000
    on rates, 2004–2016 on counts) and the year-before effect, against the share of Russians in the 2020
    census. Slope by least squares over regions (equal weight), tested by shuffling the shares between
    regions PERMUTATIONS times."""
    leap = ratios[ratios.phase == 0].groupby('code').log_ratio.agg(['mean', 'size'])
    pre = ratios[ratios.phase == 3].groupby('code').log_ratio.mean()
    last = regional.sort_values('year').groupby('code').last()
    t = (census[census.code.isin(REGIONS)].set_index('code')[['russian_share_pct']]
         .join(leap.rename(columns={'mean': 'leap_log', 'size': 'leap_years'}), how='inner')
         .join(pre.rename('pre_leap_log')).join(last[['year', 'marriages']].rename(
             columns={'year': 'last_year', 'marriages': 'last_year_marriages'})))
    t['name'] = t.index.map(REGIONS)
    t = t.reset_index().rename(columns={'index': 'code'})
    x, y = t.russian_share_pct.to_numpy(float), t.leap_log.to_numpy(float)

    def slope(xv):
        return float(np.polyfit(xv, y, 1)[0])
    b = slope(x)
    rng = np.random.default_rng(SEED)
    perm = np.array([slope(rng.permutation(x)) for _ in range(PERMUTATIONS)])
    groups = []
    for lo, hi, label in SHARE_GROUPS:
        g = t[(t.russian_share_pct >= lo) & (t.russian_share_pct < hi)]
        groups.append({'label': label, 'regions': int(len(g)), 'codes': sorted(g.code),
                       'leap_pct': round(100 * float(np.exp(g.leap_log.median()) - 1), 1),
                       'pre_leap_pct': round(100 * float(np.exp(g.pre_leap_log.median()) - 1), 1),
                       'share_below_zero': round(float((g.leap_log < 0).mean()), 3)})
    # The same slope without Ingushetia, Chechnya and Dagestan: does the link live on them alone?
    rest = ~t.code.isin(['IN', 'CE', 'DA']).to_numpy()
    b_rest = float(np.polyfit(x[rest], y[rest], 1)[0])
    out = {'regions': int(len(t)), 'groups': groups,
           'slope_pct_per_10pp': round(100 * (float(np.exp(10 * b)) - 1), 2),
           'slope_pct_per_10pp_without_east_caucasus': round(100 * (float(np.exp(10 * b_rest)) - 1), 2),
           'correlation_without_east_caucasus': round(float(np.corrcoef(x[rest], y[rest])[0, 1]), 3),
           'p_value': round(float((np.sum(np.abs(perm) >= abs(b)) + 1) / (len(perm) + 1)), 4),
           'correlation': round(float(np.corrcoef(x, y)[0, 1]), 3)}
    return t, out


# ------------------------------------------------------------------ validation
def validate():
    """Cross-checks; any failure stops ``export``. Results -> $MARRIAGES_DATA/validation.json."""
    mon = pd.read_csv(DATA / 'monthly_all_editions.csv')
    ann = pd.read_csv(DATA / 'annual_all_editions.csv')
    reg = pd.read_csv(DATA / 'regional_all_sources.csv')
    monthly = pd.read_csv(DATA / 'national_monthly.csv')
    annual = pd.read_csv(DATA / 'national_annual.csv')
    problems, checks = [], {}

    # 1. editions print the same monthly numbers
    spread = mon.groupby(['year', 'month']).marriages.agg(['min', 'max', 'size'])
    bad = spread[spread['min'] != spread['max']]
    checks['monthly_editions_disagree'] = len(bad)
    problems += [f'monthly {y}-{m:02d}: editions print {r["min"]}…{r["max"]}' for (y, m), r in bad.iterrows()]

    # 2. twelve months add up to the year
    s = monthly.groupby('year').agg(total=('marriages', 'sum'), n=('month', 'size')).join(annual.set_index('year').marriages)
    s = s[s.n == 12]
    off = s[(s.total - s.marriages).abs() > 0.001 * s.marriages]
    checks['months_vs_year_max_rel'] = round(float(((s.total - s.marriages).abs() / s.marriages).max()), 6)
    problems += [f'{y}: months sum to {r.total}, year {r.marriages}' for y, r in off.iterrows()]

    # 3. regions (with the X- units) add up to Russia in the same table; rows of nested okrugs are dropped
    y = reg[reg.period == 'Y']
    tot = y[y.code != 'RU'].groupby(['source', 'year']).marriages.sum()
    ru = y[y.code == 'RU'].groupby(['source', 'year']).marriages.first()
    j = pd.concat([tot.rename('regions'), ru.rename('ru')], axis=1).dropna()
    j['rel'] = (j.regions - j.ru) / j.ru
    checks['regions_vs_russia_max_rel'] = round(float(j.rel.abs().max()), 5)
    problems += [f'{s_} {y_}: regions sum to {r.regions:.0f}, Russia {r.ru:.0f} ({100 * r.rel:+.2f} %)'
                 for (s_, y_), r in j[j.rel.abs() > 0.005].iterrows()]

    # 4. the same region-year in different sources
    d = y.groupby(['code', 'year']).marriages.agg(['min', 'max'])
    d['rel'] = (d['max'] - d['min']) / d['max']
    checks['region_year_sources_max_rel'] = round(float(d.rel.max()), 5)
    problems += [f'{c} {y_}: sources print {r["min"]}…{r["max"]}' for (c, y_), r in d[d.rel > 0.01].iterrows()]

    # 5. every year of the range is there
    miss = sorted(set(range(FIRST_YEAR, LAST_YEAR + 1)) - set(annual.year))
    checks['national_annual_missing_years'] = miss
    problems += [f'national annual: no {m}' for m in miss]

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
    monthly = pd.read_csv(DATA / 'national_monthly.csv')
    annual = pd.read_csv(DATA / 'national_annual.csv')
    regional = pd.read_csv(DATA / 'regional_annual.csv')
    quarters = pd.read_csv(DATA / 'regional_quarterly.csv')
    cal = pd.read_csv(DATA / 'calendar.csv')
    est = json.loads((DATA / 'estimates.json').read_text())
    summary = pd.read_csv(DATA / 'regional_summary.csv')
    years_m = sorted(monthly.year.unique())
    c = cal[cal.year.isin(years_m)].sort_values(['year', 'month'])
    rng_years = annual[(annual.year >= FIRST_YEAR) & (annual.year <= LAST_YEAR)]
    out = {
        'generated_by': 'scripts/research/russia_marriages.py',
        'first_year': FIRST_YEAR, 'last_year': LAST_YEAR,
        'total_marriages': int(rng_years.marriages.sum()),
        'national_monthly': monthly[['year', 'month', 'marriages']].astype(int).values.tolist(),
        'national_annual': annual[annual.year >= FIRST_YEAR][['year', 'marriages']].astype(int).values.tolist(),
        'easter': {int(y): orthodox_easter(int(y)).isoformat() for y in years_m},
        # per model month: days, lent days, Krasnaya Gorka, Fridays, Saturdays, holidays, Venus days, beautiful date
        'calendar_columns': ['year', 'month', 'days', 'lent_days', 'krasnaya_gorka', 'fridays', 'saturdays',
                             'holidays', 'venus_retro_days', 'repeating_date'],
        'calendar': c[['year', 'month', 'days', 'lent_days', 'krasnaya_gorka', 'fridays', 'saturdays', 'holidays',
                       'venus_retro_days', 'repeating_date']].astype(int).values.tolist(),
        'regions': [{'code': r.code, 'name': r.name, 'russian_share_pct': round(float(r.russian_share_pct), 1),
                     'leap_pct': round(100 * float(np.exp(r.leap_log) - 1), 1),
                     'pre_leap_pct': round(100 * float(np.exp(r.pre_leap_log) - 1), 1),
                     'leap_years': int(r.leap_years), 'last_year': int(r.last_year),
                     'last_year_marriages': int(r.last_year_marriages)}
                    for r in summary.sort_values('code').itertuples()],
        'excluded_months': [{'year': y, 'month': m, 'reason': r} for (y, m), r in EXCLUDED_MONTHS.items()],
        'estimates': est,
        'validation': val['checks'],
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(',', ':')) + '\n')
    # dataset: one row per level, unit and period
    parts = [
        monthly.assign(level='national', code='RU', region='Российская Федерация', period=monthly.month.map('M{:02d}'.format)),
        annual.assign(level='national', code='RU', region='Российская Федерация', period='Y'),
        regional.assign(level='region', region=regional.code.map(REGIONS), period='Y'),
    ]
    if len(quarters):
        parts.append(quarters.assign(level='region', region=quarters.code.map(REGIONS), period=quarters.quarter,
                                     source='bulletins (cumulative quarters)'))
    rates = pd.read_csv(DATA / 'regional_rates.csv')
    parts.append(rates.assign(level='region', region=rates.code.map(REGIONS), period='Y'))
    ds = pd.concat(parts, ignore_index=True)
    # one row per unit and period: a count and, for 1990–2006, the crude rate of "Regions of Russia"
    ds = ds.groupby(['level', 'code', 'region', 'year', 'period'], as_index=False).agg(
        marriages=('marriages', 'max'), marriage_rate_per_1000=('rate', 'max'),
        source=('source', lambda s: '+'.join(sorted(set(s)))))
    ds['marriages'] = ds.marriages.round().astype('Int64')
    ds = ds.sort_values(['level', 'code', 'year', 'period'])
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    ds[['level', 'code', 'region', 'year', 'period', 'marriages', 'marriage_rate_per_1000', 'source']].to_csv(
        CSV_OUT, index=False, lineterminator='\n')
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
