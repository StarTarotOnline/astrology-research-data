#!/usr/bin/env python3
"""Where house number 13 goes missing: skipped numbers in official address registers.

Pre-registration, written on 4 November 2026 BEFORE the full count (the script itself follows in a
later commit). What had been seen by then: Paris and four other French departments (75, 44, 69, 13,
67) — in Paris 13 is missing on 7.4% of streets that have 11 and 15 (and 9 and 17), against 2.1% for
other odd numbers; the "11 bis" stands in for 13 on 42% of those streets. Everything below is tested
as written; hypotheses added after the count starts are listed separately and marked as such.

Metric: for a number N, the share of streets where N is absent while N-2, N+2, N-4 and N+4 (same
parity) are present; the placebo is every other odd number 5..43 on the same streets. Regions are
compared by the absolute excess per 100 such streets, not by the ratio (the ratio grows wherever the
register is clean).

Source of the numbers on https://startarot.online/research/missing-house-number-13

Needs Python 3.10+ with ``pip install numpy pandas`` (tested on the system Python 3.13 with numpy 2.3, pandas 3.0)
and ``curl``. Raw files (about 2.3 GB; BAN alone 0.9 GB, DVF 0.5 GB) go to $HOUSE13_DATA (default
~/startarot-data/house-13/raw when that folder exists, otherwise ./house-13-data next to this script); intermediate
tables go to $HOUSE13_DATA/_work. Steps, in order:

    python3 house_number_13.py fetch            # every source: downloads what is missing, writes manifest.json
    python3 house_number_13.py fetch-<source>   # one source (ids in SOURCES: fetch-ban, fetch-pl, fetch-no, ...)
    python3 house_number_13.py compute          # everything below -> _work/computed.json (first run ~7 min, then ~2.5 min)
    python3 house_number_13.py validate         # reconciliation with the earlier counts, row accounting, manifest
    python3 house_number_13.py export           # page JSON + long CSV (+ a copy of this script); refuses if validate failed

Heavy work runs in ONE process, one source at a time (BAN is streamed department by department, DVF year by year, TOPO
streamed against the BAN street ids); measured on an M-series Mac: peak RSS 1.1 GB. The first compute extracts BAN into
per-street bitmask tables (_work/fr_streets, ~3.5 min) and DVF into single-dwelling sales (_work/dvf, ~1.5 min); later runs
reuse them while the source files keep their size.
Run from the repo, export writes (GENERATED: regenerate, do not hand-edit):
    frontend/src/lib/research/house-number-13.json   data the page renders
    frontend/static/research/house-number-13.csv     the open dataset (long format: area x number)
    frontend/static/research/house_number_13.py      a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

What is counted
---------------
A street is a register's own street id (BAN id_fantoir, else INSEE code + name; swisstopo STR_ESID; PRG ID_SIMC+ID_ULIC;
...: see each loader). A house number is its integer part: 13, 13 bis, 13a, 13/1, 13 k1, 13之1 all mean "13 is there".
Duplicates (street, number, suffix) count once. For N: eligible = N-4, N-2, N+2, N+4 all present; missing = N absent
with every suffix. r(N) = missing / eligible. Background bg = mean of r over the 19 other odd numbers 5..43; excess =
r(13) - bg in percentage points (= extra missing 13s per 100 streets that should have one); ratio = r(13) / bg; rank of
13 among the 20 odd numbers (1 = most often missing). Earlier scout counts printed a POOLED background (sum of missing /
sum of eligible over the 19 numbers): r(13) is identical, bg differs in the second decimal (Zurich: 12.5 pooled).
Intervals: a cluster bootstrap over communes / municipalities (Poisson(1) weights, 1000 replicates, percentile 95 %)
for countries, regions, cantons, departments, language areas and size classes; for cities and districts the binomial
error of r(13) plus that of the background (streets independent). p-values are one-sided (excess > 0) from z =
excess / SD. Multiplicity: H1-H7 Holm; every table of areas (departments, regions, cantons, Paris arrondissements,
the cross-country city list, the list of areas) Benjamini-Hochberg within the table, q < 0.05.
Local numbers, apart from the main metric: 17 (Italy, Ticino) on the same odd scheme with its background = the odd
numbers other than 13 and 17; the family 4/14/24/34 on the scheme N-2, N+2, N+4 for every even 4..44 (4 has no
neighbour 0), background = the even numbers 6..38 without a digit 4. San Francisco numbers by hundred blocks: street x
hundred = "street", N = number mod 100. Singapore HDB blocks and Czech house numbers (č.p.) run consecutively: N-2, N-1,
N+1, N+2, a separate inset. England and Wales (Price Paid 2024) is a register of SALES: "no sale of a new No.13".

Sources, licences, snapshot dates: SOURCES below (printed into the JSON with the size of the raw files); every file's
SHA-256, size, download time and HTTP Last-Modified are in $HOUSE13_DATA/manifest.json. In short: BAN (Base Adresse
Nationale, 03.11.2026), TOPO (DGFiP, 13.10.2026) and DVF (geo-dvf, years 2021-2025, files of 18.05.2026) — Licence
Ouverte 2.0; swisstopo official building address directory (03.11.2026) — swisstopo OGD terms (free use, source
named); ČÚZK RÚIAN (31.10.2026) — CC BY 4.0; Kartverket Matrikkelen-Adresse (31.10.2026) — CC BY 4.0; Geobasis NRW
Gebäudereferenzen (01.07.2026) — dl-de/zero-2-0; Registrų centras address register (04.11.2026) — open data with
attribution; GUGiK PRG address points (03.11.2026) — free for any purpose (art. 40a Prawo geodezyjne); BAG Amsterdam
— CC0; BeST Brussels (01.11.2026) — CC BY 4.0; Helsinki region address list (02.11.2026) — CC BY 4.0; Madrid callejero
(02.11.2026) — CC BY 4.0; Milan ds634 (01.10.2026) — CC BY; Bologna civici (referendum 2025) — CC BY 4.0; FNS GAR,
region 78 (30.10.2026) — open data of the FNS; DataSF EAS — PDDL 1.0; Taipei door-plate data (Songshan district only)
— OGDL-Taiwan 1.0; HM Land Registry Price Paid 2024 — OGL v3.0 (contains HM Land Registry data © Crown copyright and
database right 2026); data.gov.sg HDB property information — Singapore Open Data Licence; department outlines —
gregoiredavid/france-geojson "departements-version-simplifiee" (from IGN/INSEE data, Licence Ouverte), simplified again
here to SVG paths.

Caveats a reader of the numbers must keep
-----------------------------------------
* "Not in the register" is not "skipped when numbering": a house can be demolished, merged with its neighbour or not yet
  registered. That noise is in every number alike; the placebo numbers measure it, and only the EXCESS of 13 is read.
  The level of the noise differs between registers (1.4 % in Amsterdam, 19 % in San Francisco blocks): compare places by
  the absolute excess, not by the ratio.
* Price Paid is sales, not houses: a street where No.13 exists but was not sold in 2024 looks the same as one without it.
  Only new builds (flag new = Y) are shown, where the whole street is sold within a year or two.
* Taipei covers one district (Songshan): the city portal's file "all of Taipei" holds only district 63000010. A lane
  (巷/弄) takes the number of the house it starts from, so lane numbers count as present on the parent street.
* Switzerland's language areas are a heuristic: the language of a commune is the majority language of its street names
  (rue/chemin -> fr, via/piazza -> it, -strasse/-weg -> de; "via" in Graubünden -> rm except the Italian valleys).
* DVF has no Alsace-Moselle (57, 67, 68) and no Mayotte; prices are per m2 of single-dwelling sales, 2021-2025.
* TOPO's date is when the street's RECORD was created (1987-88 initial load in 95 departments), not when it was built;
  a renamed street gets a new record. That blurs old and new together, towards no effect.
* Lithuania's cities other than Vilnius are not named: the register carries municipality codes without names, and only
  code 13 (Vilnius city, settlement 31003) was checked against the classifier.

Verdicts: 'holds' when every clause of the hypothesis holds; 'does not hold' when its main clause fails; 'mixed' when
the main clause holds somewhere or in part and another clause fails (H4: 17 skipped in Milan but not in Bologna, and 13 is
skipped too; H5: 4/14/34 skipped in Taipei, but 13 more). Main clauses and their one-sided p (Holm over H1-H7):
H1 bootstrap share where 13's excess does not exceed the runner-up's; H2 share where big cities (top 20 by streets,
Paris/Lyon/Marseille whole) do not exceed rural communes (< 2,000 addresses); H3 share where the Paris lift of "11 with a
suffix" on streets without 13 does not exceed the province's; H4 17's excess in Milan + Bologna pooled (binomial); H5 the
4/14/24/34 family's excess in Taipei (binomial); H6 No.13 cheaper in France (z of the street fixed-effects estimate;
England and Wales 2024 printed alongside); H7 streets added to TOPO since 2000 vs streets of the initial load.

Reconciliation with the earlier counts (validate checks them): France 19,279 missing of 260,642 eligible and Paris 155 of
2,098 are the agents' BAN counts of 04.11.2026, to the street; Zurich 160 of 287 (55.8 %) and every other scout count
listed in EXPECTED. The French intervals differ in the second decimal from fr-report.md (1000 replicates here, 2000
there), which is bootstrap noise. Bootstrap p-values have a floor of 1/1001 (H1, H3, H7 print 0.001). National Norway
(+1.4 pp) is lower than the scout's four cities (+2.6), and the 66 Polish cities (+2.8) lower than the scout's six (+4.4):
the cities with the strongest effect had been probed first, which is why the whole registers were taken.

Everything listed in ADDED_AFTER_COUNT was decided after the counts had started; it is printed, marked as such, and
H1-H7 were not rewritten.
"""

HYPOTHESES = {
    'H1': 'Across France, 13 is the most skipped odd number of 5..43 (larger excess than any other).',
    'H2': 'The excess for 13 is higher in large cities than in rural communes (absolute excess).',
    'H3': 'The "11 bis instead of 13" mechanism is stronger in Paris than in the rest of France.',
    'H4': 'In Italy 17 is skipped more often than its odd neighbours, and 13 is not.',
    'H5': 'Where 4 is the unlucky number (Taiwan, Hong Kong, China, ...), 4 (and 14, 24, ...) is skipped, '
          'and 13 less or not at all.',
    'H6': 'Where 13 is unlucky (United Kingdom, France, ...) house number 13 sells for less than its '
          'neighbours on the same street (France DVF, England and Wales Price Paid) - or not: either '
          'outcome is printed.',
    'H7': 'Newer streets (without historical numbering) skip 13 more often than old ones, if the age of a '
          'street can be told from the data.',
}
ADDED_AFTER_COUNT: dict[str, str] = {
    'A1': '[after count] H1 robustness: neighbours +-2 only; "dense" streets (>= 80 % of same-parity numbers in N+-10); '
          'local background 9, 11, 15, 17; without corner cases (an address of another street within 15 m of where N '
          'would stand); without Paris; without Limousin (19, 23, 87); metropolitan France; overseas separately.',
    'A2': '[after count] Controls printed: even numbers 6..32, 101..121 (113), the 4/14/24/34 family in France.',
    'A3': '[after count] Size classes of cities (addresses, Paris/Lyon/Marseille whole) and big cities >= 50,000 '
          'addresses against rural communes, next to the pre-registered top-20 comparison of H2.',
    'A4': '[after count] H3 details: bis/ter only, "13 bis without a plain 13", 12 bis; share of the excess on streets '
          'with 11 bis.',
    'A5': '[after count] H7 details: street type as an age proxy (allée/impasse/résidence vs rue/avenue/...), the TOPO '
          'difference within departments (weighted), provenance splits (certification, source of position).',
    'A6': '[after count] H6: number of DVF sales at No.13 against its neighbours (are there fewer sales?).',
    'A7': '[after count] Empirical-Bayes shrinkage of department excess towards the national one (for the map); '
          'communes where every eligible street lacks 13.',
    'A8': '[after count] Switzerland by language area (heuristic commune language) and by canton; Milan without '
          'passi carrai (driveway numbers); Taipei with lane numbers counted as present.',
    'A9': '[after count] National Norway and all 66 Polish cities with powiat rights (the scout count had 4 and 6 '
          'cities); the cross-country list of every city with >= 150 streets eligible for 13.',
    'A10': '[after count] Background of the 4-family without 40, 42, 44 (they carry a 4 too).',
    'A11': '[after count] Cadastre check, independent of BAN: on streets eligible for 13 in BAN (9, 11, 15, 17 present), split '
           'into "13 absent in BAN" and "13 present in BAN", the share of streets where DVF 2021-2025 has at least one '
           'mutation at No.13, and the same for No.11 and No.15 as controls. Streets are joined by their FANTOIR/TOPO code '
           '(BAN id_fantoir = DVF code_commune or ancien_code_commune + "_" + adresse_code_voie); BAN streets without a '
           'FANTOIR id are joined by normalised name within the commune and counted separately.',
}

import collections
import csv
import datetime as dt
import gc
import glob
import gzip
import hashlib
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import time
import unicodedata
import urllib.request
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'house-number-13'
SLUG = 'missing-house-number-13'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'house_number_13.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
_MAC_DATA = Path.home() / 'startarot-data' / 'house-13' / 'raw'
DATA = Path(os.environ.get('HOUSE13_DATA') or (_MAC_DATA if _MAC_DATA.is_dir() else HERE / 'house-13-data'))
WORK = DATA / '_work'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36'
REPS = 1000
T0 = time.time()

# ---------------------------------------------------------------- sources
BAN_BASE = 'https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/'
TOPO_URL = ('https://data.economie.gouv.fr/api/explore/v2.1/catalog/datasets/topo-fichier-des-entites-topographiques/'
            'exports/csv?select=code_dep,code_commune,code_voie,code_type_topo,nature_de_voie,date_creation_de_article,'
            'date_annulation,type_voie&delimiter=%3B')
DVF_YEARS = (2021, 2022, 2023, 2024, 2025)
PL_PRG = 'https://integracja.gugik.gov.pl/PRG/pobierz.php?teryt={}&adresy'
GAR_URL = 'https://fias-file.nalog.ru/downloads/2026.10.30/gar_xml.zip'
UK_PP = 'http://prod2.publicdata.landregistry.gov.uk.s3-website-eu-west-1.amazonaws.com/pp-2024.csv'
SG_DATASET = 'd_17f5382f26140b1fdae0ba2ef6239d2f'

# The 66 cities with powiat rights (TERYT powiat code -> name).
PL_CITIES = {
    '0261': 'Jelenia Góra', '0262': 'Legnica', '0264': 'Wrocław', '0265': 'Wałbrzych', '0461': 'Bydgoszcz',
    '0462': 'Grudziądz', '0463': 'Toruń', '0464': 'Włocławek', '0661': 'Biała Podlaska', '0662': 'Chełm',
    '0663': 'Lublin', '0664': 'Zamość', '0861': 'Gorzów Wielkopolski', '0862': 'Zielona Góra', '1061': 'Łódź',
    '1062': 'Piotrków Trybunalski', '1063': 'Skierniewice', '1261': 'Kraków', '1262': 'Nowy Sącz', '1263': 'Tarnów',
    '1461': 'Ostrołęka', '1462': 'Płock', '1463': 'Radom', '1464': 'Siedlce', '1465': 'Warszawa', '1661': 'Opole',
    '1861': 'Krosno', '1862': 'Przemyśl', '1863': 'Rzeszów', '1864': 'Tarnobrzeg', '2061': 'Białystok',
    '2062': 'Łomża', '2063': 'Suwałki', '2261': 'Gdańsk', '2262': 'Gdynia', '2263': 'Słupsk', '2264': 'Sopot',
    '2461': 'Bielsko-Biała', '2462': 'Bytom', '2463': 'Chorzów', '2464': 'Częstochowa', '2465': 'Dąbrowa Górnicza',
    '2466': 'Gliwice', '2467': 'Jastrzębie-Zdrój', '2468': 'Jaworzno', '2469': 'Katowice', '2470': 'Mysłowice',
    '2471': 'Piekary Śląskie', '2472': 'Ruda Śląska', '2473': 'Rybnik', '2474': 'Siemianowice Śląskie',
    '2475': 'Sosnowiec', '2476': 'Świętochłowice', '2477': 'Tychy', '2478': 'Zabrze', '2479': 'Żory', '2661': 'Kielce',
    '2861': 'Elbląg', '2862': 'Olsztyn', '3061': 'Kalisz', '3062': 'Konin', '3063': 'Leszno', '3064': 'Poznań',
    '3261': 'Koszalin', '3262': 'Szczecin', '3263': 'Świnoujście',
}

# id, country, publisher, name, licence, snapshot (what the data describe), files: {relative path: url}.
# url is the page a reader of the article lands on (the dataset's page, https): the Sources list links it, so it is never a
# download link (the full GAR is tens of GB, Price Paid ~150 MB); what fetch downloads is in files.
SOURCES = [
    dict(id='ban', country='FR', publisher='Base Adresse Nationale (IGN, DINUM, communes)', name='adresses-<département>.csv.gz, latest',
         url=BAN_BASE, licence='Licence Ouverte 2.0', snapshot='2026-11-03', files='fr/adresses-*.csv.gz'),
    dict(id='topo', country='FR', publisher='DGFiP', name='Fichier des entités topographiques (TOPO), street records with creation date',
         url='https://data.economie.gouv.fr/explore/assets/topo-fichier-des-entites-topographiques/', licence='Licence Ouverte 2.0',
         snapshot='2026-10-13', files={'topo/topo_sel.csv.gz': TOPO_URL}),
    dict(id='dvf', country='FR', publisher='DGFiP / Etalab (geo-dvf)', name='Demandes de valeurs foncières 2021-2025, full.csv.gz',
         url='https://files.data.gouv.fr/geo-dvf/latest/csv/', licence='Licence Ouverte 2.0', snapshot='2026-05-18',
         files={f'dvf/full-{y}.csv.gz': f'https://files.data.gouv.fr/geo-dvf/latest/csv/{y}/full.csv.gz' for y in DVF_YEARS}),
    dict(id='map', country='FR', publisher='Grégoire David, france-geojson (from IGN / INSEE data)',
         name='departements-version-simplifiee.geojson', licence='Licence Ouverte 2.0', snapshot='2026-11-04',
         url='https://github.com/gregoiredavid/france-geojson',
         files={'map/departements-version-simplifiee.geojson':
                'https://raw.githubusercontent.com/gregoiredavid/france-geojson/master/departements-version-simplifiee.geojson'}),
    dict(id='ch', country='CH', publisher='swisstopo', name='Amtliches Gebäudeadressverzeichnis (official building address directory)',
         url='https://data.geo.admin.ch/ch.swisstopo.amtliches-gebaeudeadressverzeichnis/', licence='swisstopo OGD terms (open use, source named)',
         snapshot='2026-11-03', files={'ch/ch_2056.csv.zip': 'https://data.geo.admin.ch/ch.swisstopo.amtliches-gebaeudeadressverzeichnis/'
                                       'amtliches-gebaeudeadressverzeichnis_ch/amtliches-gebaeudeadressverzeichnis_ch_2056.csv.zip'}),
    dict(id='cz', country='CZ', publisher='ČÚZK', name='RÚIAN address points, CSV by municipality', licence='CC BY 4.0',
         url='https://vdp.cuzk.gov.cz/', snapshot='2026-10-31',
         files={'cz/ruian_20261031_OB_ADR_csv.zip': 'https://vdp.cuzk.gov.cz/vymenny_format/csv/20261031_OB_ADR_csv.zip'}),
    dict(id='no', country='NO', publisher='Kartverket', name='Matrikkelen - Adresse, whole country CSV', licence='CC BY 4.0',
         url='https://www.geonorge.no/', snapshot='2026-10-31',
         files={'no/Basisdata_0000_Norge_25833_MatrikkelenAdresse_CSV.zip': 'https://nedlasting.geonorge.no/geonorge/Basisdata/'
                'MatrikkelenAdresse/CSV/Basisdata_0000_Norge_25833_MatrikkelenAdresse_CSV.zip'}),
    dict(id='nrw', country='DE', publisher='Geobasis NRW', name='Gebäudereferenzen (whole of North Rhine-Westphalia)',
         licence='dl-de/zero-2-0', url='https://www.opengeodata.nrw.de/', snapshot='2026-07-01',
         files={'de/gebref_nrw.zip': 'https://www.opengeodata.nrw.de/produkte/geobasis/lk/akt/gebref_txt/gebref_EPSG25832_ASCII.zip'}),
    dict(id='lt', country='LT', publisher='Registrų centras', name='Adresų registras, adr_stat_lr.csv',
         licence='open data, source named', url='https://www.registrucentras.lt/', snapshot='2026-11-04',
         files={'lt/adr_stat_lr.csv': 'https://www.registrucentras.lt/aduomenys/?byla=adr_stat_lr.csv'}),
    dict(id='pl', country='PL', publisher='GUGiK', name='PRG punkty adresowe, 66 cities with powiat rights',
         licence='free for any purpose (art. 40a Prawo geodezyjne i kartograficzne)', url='https://integracja.gugik.gov.pl/PRG/',
         snapshot='2026-11-03', files={f'pl/{t}.zip': PL_PRG.format(t) for t in PL_CITIES}),
    dict(id='nl', country='NL', publisher='Gemeente Amsterdam (BAG)', name='BAG nummeraanduidingen, Amsterdam and Weesp',
         licence='CC0', url='https://api.data.amsterdam.nl/', snapshot='2026-11-04',
         files={'nl/ams_num.csv': 'https://api.data.amsterdam.nl/v1/bag/nummeraanduidingen/?_format=csv&_fields=identificatie,'
                'huisnummer,huisletter,huisnummertoevoeging,ligtAanOpenbareruimteId,statusOmschrijving,eindGeldigheid&_pageSize=1000000'}),
    dict(id='be', country='BE', publisher='BOSA / BeST (Brussels region)', name='openaddress-bebru', licence='CC BY 4.0',
         url='https://opendata.bosa.be/', snapshot='2026-11-01',
         files={'be/openaddress-bebru.zip': 'https://opendata.bosa.be/download/best/openaddress-bebru.zip'}),
    dict(id='fi', country='FI', publisher='Helsinki region (Helsinki, Espoo, Vantaa, Kauniainen)', name='PKS osoiteluettelo',
         licence='CC BY 4.0', url='https://kartta.hel.fi/', snapshot='2026-11-02',
         files={'fi/pks_osoiteluettelo.csv': 'https://kartta.hel.fi/ws/geoserver/avoindata/wfs?service=WFS&version=2.0.0&request=GetFeature'
                '&typeNames=avoindata:PKS_osoiteluettelo&outputFormat=csv'}),
    dict(id='es', country='ES', publisher='Ayuntamiento de Madrid', name='Callejero oficial, direcciones vigentes', licence='CC BY 4.0',
         url='https://datos.madrid.es/', snapshot='2026-11-02',
         files={'es/direccionesvigentes_20261102.csv': 'https://datos.madrid.es/dataset/213605-0-callejero-oficial-madrid/resource/'
                '213605-4-callejero-oficial-madrid-csv/download/direccionesvigentes_20261102.csv'}),
    dict(id='it-mi', country='IT', publisher='Comune di Milano', name='ds634 numeri civici', licence='CC BY',
         url='https://dati.comune.milano.it/', snapshot='2026-10-01',
         files={'it/milano.zip': 'https://dati.comune.milano.it/dataset/5c6519f6-6d26-41c9-b53b-6106e08d1b90/resource/'
                '533b4e63-3d78-4bb5-aeb4-6c5f648f7f21/download/ds634_civici_coordinategeografiche_20261001_final_csv.zip'}),
    dict(id='it-bo', country='IT', publisher='Comune di Bologna', name='Referendum 2025 - civici per sezione elettorale',
         licence='CC BY 4.0', url='https://opendata.comune.bologna.it/', snapshot='2025-05-29',
         files={'it/bologna_civici_ref2025.csv': 'https://opendata.comune.bologna.it/api/explore/v2.1/catalog/datasets/'
                'referendum-2025-civici-per-sezione-elettorale/exports/csv?delimiter=%3B'}),
    dict(id='ru', country='RU', publisher='ФНС России', name='ГАР (gar_xml.zip), region 78: AS_HOUSES, AS_ADDR_OBJ, AS_ADM_HIERARCHY',
         licence='open data of the FNS', url='https://www.nalog.gov.ru/opendata/7707329152-fias/', snapshot='2026-10-30',
         files={'ru/gar_78_houses.csv': GAR_URL}),
    dict(id='us', country='US', publisher='DataSF', name='Enterprise Addressing System (EAS) base addresses', licence='PDDL 1.0',
         url='https://data.sf.gov/', snapshot='2026-11-04',
         files={'us/sf_eas.csv': 'https://data.sf.gov/resource/3mea-di5p.csv?$select=eas_baseid,address_number,address_number_suffix,'
                'street_full_street_name,cnn,zip_code&$limit=5000000'}),
    dict(id='tw', country='TW', publisher='Taipei City Government', name='臺北市門牌位置數值資料 (file holds Songshan district only)',
         licence='Open Government Data License Taiwan 1.0', url='https://data.gov.tw/dataset/155472', snapshot='2026-11-04',
         files={'tw/taipei.csv': 'https://data.taipei/api/dataset/b7c8e724-1e98-45ee-a0bd-f3840623ed97/resource/'
                'ce76ca0c-7f94-4935-ab47-1d2a41ca2abb/download'}),
    dict(id='uk', country='GB', publisher='HM Land Registry', name='Price Paid Data 2024 (England and Wales), slimmed columns',
         licence='OGL v3.0', url='https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads',
         snapshot='2024 sales, file of 2026-11-04', files={'uk/pp-2024-slim.csv': UK_PP}),
    dict(id='sg', country='SG', publisher='Housing & Development Board', name='HDB Property Information', licence='Singapore Open Data Licence v1.0',
         url='https://data.gov.sg/', snapshot='2026-11-04', files={'sg/hdb_property_info.csv': SG_DATASET}),
]
SRC = {s['id']: s for s in SOURCES}


def log(*a):
    print(f'[{time.time() - T0:7.1f}s]', *a, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def source_files(s):
    if isinstance(s['files'], str):
        return {str(Path(p).relative_to(DATA)): BAN_BASE + Path(p).name for p in sorted(glob.glob(str(DATA / s['files'])))}
    return s['files']


# ---------------------------------------------------------------- fetch
def _curl(url, dest, *extra):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + '.part')
    subprocess.run(['curl', '-sS', '-L', '--fail', '--retry', '5', '--retry-all-errors', '-m', '1800', '-A', UA, '-o', str(tmp), *extra, url], check=True)
    tmp.rename(dest)


def _last_modified(url):
    try:
        out = subprocess.run(['curl', '-sIL', '-m', '60', '-A', UA, url], capture_output=True, text=True).stdout
    except Exception:
        return ''
    lm = [x.split(':', 1)[1].strip() for x in out.splitlines() if x.lower().startswith('last-modified:')]
    return lm[-1] if lm else ''


def _logged_times():
    """Download times and Last-Modified recorded by the earlier download logs (BAN, DVF), if present."""
    out = {}
    for sub in ('fr', 'dvf'):
        p = DATA / sub / '_download_log.tsv'
        if p.exists():
            for r in csv.DictReader(p.open(), delimiter='\t'):
                out[f"{sub}/{r['file']}"] = (r['downloaded_utc'], r.get('last_modified', ''))
    return out


def _fetch_ban():
    d = DATA / 'fr'
    names = []
    try:
        html = urllib.request.urlopen(urllib.request.Request(BAN_BASE, headers={'User-Agent': UA}), timeout=60).read().decode()
        names = sorted(set(re.findall(r'adresses-[0-9AB]+\.csv\.gz', html)))
    except Exception as e:
        log('BAN index not reachable, keeping the files on disk:', e)
    lg = d / '_download_log.tsv'
    if names and not lg.exists():
        d.mkdir(parents=True, exist_ok=True)
        lg.write_text('file\tdownloaded_utc\tbytes\tlast_modified\tetag\n')
    for n in names:
        if (d / n).exists():
            continue
        lm = _last_modified(BAN_BASE + n)
        _curl(BAN_BASE + n, d / n)
        with lg.open('a') as fh:
            fh.write(f"{n}\t{dt.datetime.now(dt.timezone.utc):%Y-%m-%dT%H:%M:%SZ}\t{(d / n).stat().st_size}\t{lm}\t\n")


def _fetch_topo(dest):
    log('TOPO export (7.9 M records, a few minutes)')
    tmp = dest.with_name('topo.csv.part')
    _curl(TOPO_URL, tmp)
    with open(tmp, 'rb') as fi, gzip.open(dest, 'wb') as fo:
        shutil.copyfileobj(fi, fo)
    tmp.unlink()


def _fetch_uk(dest):
    """pp-2024.csv (163 MB, no header) streamed into the columns used here."""
    cols = ['tid', 'price', 'date', 'postcode', 'ptype', 'new', 'duration', 'paon', 'saon', 'street', 'locality', 'town',
            'district', 'county', 'cat', 'status']
    keep = ['price', 'date', 'postcode', 'ptype', 'new', 'paon', 'saon', 'street', 'town', 'district', 'cat']
    p = subprocess.Popen(['curl', '-sS', '-L', '--fail', '-A', UA, UK_PP], stdout=subprocess.PIPE)
    tmp = dest.with_name(dest.name + '.part')
    with open(tmp, 'w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(keep)
        for r in csv.reader(io.TextIOWrapper(p.stdout, encoding='utf-8')):
            d = dict(zip(cols, r))
            w.writerow([d['price'], d['date'][:10]] + [d[k] for k in keep[2:]])
    if p.wait() != 0:
        raise SystemExit('Price Paid download failed')
    tmp.rename(dest)


class _HttpFile(io.RawIOBase):
    """Read-only seekable file over HTTP Range requests (to take three members out of the 58 GB GAR archive)."""

    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': UA})
        self.size = int(urllib.request.urlopen(req, timeout=60).headers['Content-Length'])

    def seekable(self):
        return True

    def readable(self):
        return True

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def tell(self):
        return self.pos

    def readinto(self, b):
        if self.pos >= self.size or not len(b):
            return 0
        end = min(self.pos + len(b), self.size) - 1
        req = urllib.request.Request(self.url, headers={'Range': f'bytes={self.pos}-{end}', 'User-Agent': UA})
        data = urllib.request.urlopen(req, timeout=300).read()
        b[:len(data)] = data
        self.pos += len(data)
        return len(data)


def _fetch_ru(dest, reg='78'):
    import xml.etree.ElementTree as ET
    z = zipfile.ZipFile(io.BufferedReader(_HttpFile(GAR_URL), buffer_size=4 << 20))
    names = {n.split('/')[1].split('_2')[0]: n for n in z.namelist() if n.startswith(reg + '/')}

    def rows(kind, tag):
        with z.open(names[kind]) as fh:
            for _, el in ET.iterparse(io.BufferedReader(fh, 4 << 20), events=('end',)):
                if el.tag == tag:
                    yield el.attrib
                el.clear()
    houses = {a['OBJECTID']: (a.get('HOUSENUM', ''), a.get('ADDNUM1', ''), a.get('ADDTYPE1', ''), a.get('HOUSETYPE', ''))
              for a in rows('AS_HOUSES', 'HOUSE') if a.get('ISACTUAL') == '1' and a.get('ISACTIVE') == '1'}
    streets = {a['OBJECTID']: (a.get('NAME', ''), a.get('TYPENAME', ''), a.get('LEVEL', ''))
               for a in rows('AS_ADDR_OBJ', 'OBJECT') if a.get('ISACTUAL') == '1' and a.get('ISACTIVE') == '1'}
    tmp = dest.with_name(dest.name + '.part')
    with open(tmp, 'w', newline='') as fo:
        w = csv.writer(fo)
        w.writerow(['street_id', 'street', 'level', 'housenum', 'addnum1', 'addtype1', 'housetype'])
        for a in rows('AS_ADM_HIERARCHY', 'ITEM'):
            oid = a.get('OBJECTID')
            if oid in houses and a.get('ISACTIVE') == '1':
                p = a.get('PARENTOBJID')
                s = streets.get(p, ('', '', ''))
                w.writerow([p, s[1] + ' ' + s[0], s[2], *houses[oid]])
    tmp.rename(dest)


def _fetch_sg(dest):
    base = f'https://api-open.data.gov.sg/v1/public/api/datasets/{SG_DATASET}'
    urllib.request.urlopen(urllib.request.Request(base + '/initiate-download', headers={'User-Agent': UA}), timeout=60).read()
    for _ in range(20):
        js = json.load(urllib.request.urlopen(urllib.request.Request(base + '/poll-download', headers={'User-Agent': UA}), timeout=60))
        url = (js.get('data') or {}).get('url')
        if url:
            _curl(url, dest)
            return
        time.sleep(3)
    raise SystemExit('data.gov.sg did not return a download URL')


def fetch(only=None):
    """Downloads only what is missing (nothing is re-downloaded) and writes manifest.json: size, SHA-256, time, Last-Modified."""
    mpath = DATA / 'manifest.json'
    man = json.loads(mpath.read_text()) if mpath.exists() else {}
    logged = _logged_times()
    for s in SOURCES:
        if only and s['id'] != only:
            continue
        if s['id'] == 'ban':
            _fetch_ban()
        for rel, url in source_files(s).items():
            p = DATA / rel
            if not p.exists():
                log('downloading', rel)
                special = {'topo': _fetch_topo, 'uk': _fetch_uk, 'ru': _fetch_ru, 'sg': _fetch_sg}.get(s['id'])
                if special:
                    special(p)
                else:
                    _curl(url, p)
            st = p.stat()
            old = man.get(rel, {})
            if old.get('bytes') == st.st_size and old.get('mtime') == int(st.st_mtime) and old.get('sha256'):
                continue
            when, lm = logged.get(rel, (None, ''))
            man[rel] = dict(source=s['id'], url=url, bytes=st.st_size, mtime=int(st.st_mtime), sha256=sha256(p),
                            fetched_utc=when or dt.datetime.fromtimestamp(st.st_mtime, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                            last_modified=lm or old.get('last_modified', ''))
            log(f'{rel}  {st.st_size / 1e6:.1f} MB  sha256={man[rel]["sha256"][:16]}...')
        mpath.write_text(json.dumps(man, indent=1, ensure_ascii=False, sort_keys=True))


# ---------------------------------------------------------------- metric core
def _np():
    import warnings
    import numpy as np
    import pandas as pd
    warnings.filterwarnings('ignore', category=RuntimeWarning)
    return np, pd


ODD = list(range(5, 44, 2))
I13 = ODD.index(13)
I17 = ODD.index(17)
EVENS = list(range(4, 45, 2))
FOURS = (4, 14, 24, 34)
FOUR_BG = [n for n in EVENS if '4' not in str(n)]
CONSEC = list(range(5, 44))


def neighbours(N, scheme):
    d = {'sides': (-4, -2, 2, 4), 'sides3': (-2, 2, 4), 'consec': (-2, -1, 1, 2)}[scheme]
    return [N + x for x in d if N + x >= 1]


def has(mask, n):
    np, _ = _np()
    if n > 63:
        return np.zeros(len(mask), bool)
    return ((mask >> np.uint64(n)) & np.uint64(1)).astype(bool)


def ab(mask, Ns, scheme='sides', extra_ok=None):
    """(missing, eligible) flags per street x number, int8."""
    np, _ = _np()
    A = np.zeros((len(mask), len(Ns)), np.int8)
    B = np.zeros_like(A)
    cache = {}

    def h(n):
        if n not in cache:
            cache[n] = has(mask, n)
        return cache[n]
    for j, N in enumerate(Ns):
        ok = np.ones(len(mask), bool)
        for x in neighbours(N, scheme):
            ok &= h(x)
        if extra_ok is not None:
            ok &= extra_ok(N)
        B[:, j] = ok
        A[:, j] = ok & ~h(N)
    return A, B


def stats(a, b, t=I13, bgi=None):
    """a, b: (..., k) missing / eligible sums. r13, bg (mean of the background rates), excess (pp), ratio, rank, gap."""
    np, _ = _np()
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    k = a.shape[-1]
    bgi = [i for i in range(k) if i != t] if bgi is None else list(bgi)
    with np.errstate(invalid='ignore', divide='ignore'):
        r = np.where(b > 0, a / np.where(b > 0, b, 1), np.nan)
        rt = r[..., t]
        bg = np.nanmean(r[..., bgi], axis=-1)
        others = np.delete(r, t, axis=-1)
        rank = 1 + np.sum(others > rt[..., None], axis=-1)
        tot = np.nansum(r, axis=-1, keepdims=True)
        cnt = np.sum(~np.isnan(r), axis=-1, keepdims=True)
        excn = 100 * (r - (tot - r) / (cnt - 1))
        runner = np.nanmax(np.delete(excn, t, axis=-1), axis=-1)
    exc = 100 * (rt - bg)
    return dict(r13=100 * rt, bg=100 * bg, excess=exc, ratio=rt / bg, rank=rank, gap=exc - runner)


def binom_se(a, b, t=I13, bgi=None):
    np, _ = _np()
    a = np.asarray(a, float)
    b = np.asarray(b, float)
    k = a.shape[-1]
    bgi = [i for i in range(k) if i != t] if bgi is None else list(bgi)
    with np.errstate(invalid='ignore', divide='ignore'):
        r = a / b
        v = r * (1 - r) / b
    vb = v[..., bgi]
    n = np.sum(~np.isnan(vb), axis=-1)
    return 100 * np.sqrt(v[..., t] + np.nansum(vb, axis=-1) / n ** 2)


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2)) if z == z else float('nan')


def boot(a_c, b_c, t=I13, bgi=None, reps=REPS, seed=13):
    """Poisson(1)-weight bootstrap over clusters; returns excess, gap to the runner-up and rank arrays."""
    np, _ = _np()
    rng = np.random.default_rng(seed)
    nc = a_c.shape[0]
    a32 = a_c.astype(np.float32)
    b32 = b_c.astype(np.float32)
    ex, gap, rk = [], [], []
    for s in range(0, reps, 100):
        W = rng.poisson(1.0, size=(min(100, reps - s), nc)).astype(np.float32)
        st = stats(W @ a32, W @ b32, t, bgi)
        ex.append(st['excess'])
        gap.append(st['gap'])
        rk.append(st['rank'])
    return np.concatenate(ex), np.concatenate(gap), np.concatenate(rk)


def group_sums(codes, A, B, ng=None):
    np, _ = _np()
    ng = int(codes.max()) + 1 if ng is None else ng
    a = np.zeros((ng, A.shape[1]))
    b = np.zeros((ng, A.shape[1]))
    for j in range(A.shape[1]):
        a[:, j] = np.bincount(codes, weights=A[:, j], minlength=ng)
        b[:, j] = np.bincount(codes, weights=B[:, j], minlength=ng)
    return a, b


def result(A, B, idx=None, clusters=None, t=I13, bgi=None, seed=13, reps=REPS, keep_boot=False):
    """Point estimate + interval: cluster bootstrap if clusters are given (>= 5 of them), else binomial."""
    np, pd = _np()
    if idx is not None:
        A, B = A[idx], B[idx]
        if clusters is not None:
            clusters = clusters[idx]
    a, b = A.sum(0).astype(float), B.sum(0).astype(float)
    st = {k: float(v) for k, v in stats(a, b, t, bgi).items()}
    out = dict(eligible13=int(b[t]), missing13=int(a[t]), r13=st['r13'], bg=st['bg'], excess=st['excess'], ratio=st['ratio'],
               rank13=int(st['rank']), gap=st['gap'], a=[int(x) for x in a], b=[int(x) for x in b])
    codes = pd.factorize(clusters)[0] if clusters is not None else None
    if codes is not None and len(codes) and codes.max() >= 4 and b[t] > 0:
        ac, bc = group_sums(codes, A, B)
        ex, gp, rk = boot(ac, bc, t, bgi, reps=reps, seed=seed)
        sd = float(np.nanstd(ex))
        out.update(lo=float(np.nanpercentile(ex, 2.5)), hi=float(np.nanpercentile(ex, 97.5)), sd=sd, ci='cluster',
                   n_clusters=int(codes.max() + 1), p_top=float(np.mean(rk == 1)),
                   gap_lo=float(np.nanpercentile(gp, 2.5)), gap_hi=float(np.nanpercentile(gp, 97.5)),
                   p_gap=float((np.sum(gp <= 0) + 1) / (len(gp) + 1)))
        if keep_boot:
            out['_boot'] = ex
    else:
        se = float(binom_se(a, b, t, bgi)) if b[t] > 0 else float('nan')
        out.update(lo=st['excess'] - 1.96 * se, hi=st['excess'] + 1.96 * se, sd=se, ci='binomial')
    out['p'] = norm_sf(out['excess'] / out['sd']) if out['sd'] and out['sd'] == out['sd'] and out['sd'] > 0 else float('nan')
    return out


def bh(ps):
    """Benjamini-Hochberg q-values, nan-safe."""
    idx = [i for i, p in enumerate(ps) if p == p and p is not None]
    q = [float('nan')] * len(ps)
    m = len(idx)
    order = sorted(idx, key=lambda i: ps[i])
    run = 1.0
    for rnk in range(m - 1, -1, -1):
        i = order[rnk]
        run = min(run, ps[i] * m / (rnk + 1))
        q[i] = min(run, 1.0)
    return q


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    out = [None] * len(ps)
    run = 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        out[i] = run
    return out


def add_q(rows, key='p'):
    for r, q in zip(rows, bh([r.get(key, float('nan')) for r in rows])):
        r['q'] = q
    return rows


# ---------------------------------------------------------------- generic register -> street table
_num = re.compile(r'^\s*(\d+)\s*(.*?)\s*$')


def parse_num(s):
    m = _num.match(s or '')
    if not m:
        return None, s
    return int(m.group(1)), m.group(2)


class Streets:
    """Street-level bitmasks of the numbers present (bit n = number n, any suffix) built from register rows.
    Every row read is either kept (a distinct street+number+suffix address) or dropped with a reason."""

    def __init__(self, name, attrs=()):
        self.name, self.attr_names = name, tuple(attrs)
        self.row, self.any, self.suf, self.attrs, self.n_addr = {}, [], [], [], []
        self.seen = set()
        self.qa = collections.Counter()

    def read(self):
        self.qa['rows'] += 1

    def drop(self, why):
        self.qa['drop: ' + why] += 1

    def _i(self, key, attrs):
        i = self.row.get(key)
        if i is None:
            i = self.row[key] = len(self.any)
            self.any.append(0)
            self.suf.append(0)
            self.n_addr.append(0)
            self.attrs.append(attrs)
        return i

    def add(self, key, raw, attrs=(), extra='', number=None, suffix=None):
        if number is None:
            n, sx = parse_num(raw)
        else:
            n, sx = number, suffix or ''
        if n is None:
            return self.drop('number not parsed')
        if n == 0:
            return self.drop('number 0')
        h = hash((key, n, sx, extra))
        if h in self.seen:
            return self.drop('duplicate address')
        self.seen.add(h)
        self.qa['kept'] += 1
        i = self._i(key, attrs)
        self.n_addr[i] += 1
        if n <= 63:
            self.any[i] |= 1 << n
            if sx:
                self.suf[i] |= 1 << n

    def occupy(self, key, n, attrs=()):
        """A number taken by something that is not an address (a lane named after the house it starts from)."""
        if 0 < n <= 63:
            self.any[self._i(key, attrs)] |= 1 << n

    def table(self):
        np, _ = _np()
        t = dict(name=self.name, any=np.array(self.any, dtype=np.uint64), suf=np.array(self.suf, dtype=np.uint64),
                 n_addr=np.array(self.n_addr), qa=dict(self.qa))
        for j, nm in enumerate(self.attr_names):
            t[nm] = np.array([a[j] for a in self.attrs], dtype=object)
        self.seen = None
        return t


def _csv_rows(fh, delimiter=','):
    return csv.DictReader(fh, delimiter=delimiter)


def load_ch():
    s = Streets('ch', ('commune', 'commune_name', 'canton', 'label'))
    with zipfile.ZipFile(DATA / 'ch/ch_2056.csv.zip') as z, z.open(z.namelist()[0]) as fh:
        for r in _csv_rows(io.TextIOWrapper(fh, encoding='utf-8-sig'), ';'):
            s.read()
            if r['ADR_STATUS'] not in ('real', 'existing'):
                s.drop('status ' + r['ADR_STATUS'])
            elif not r['STR_ESID']:
                s.drop('no street')
            elif not r['ADR_NUMBER']:
                s.drop('no number')
            else:
                s.add(r['STR_ESID'], r['ADR_NUMBER'], (r['COM_FOSNR'], r['COM_NAME'], r['COM_CANTON'], r['STN_LABEL']))
    return s.table()


def load_cz():
    o = Streets('cz', ('obec', 'obec_name'))
    cp = Streets('cz_cp', ('obec',))
    with zipfile.ZipFile(DATA / 'cz/ruian_20261031_OB_ADR_csv.zip') as z:
        for name in z.namelist():
            if not name.endswith('.csv'):
                continue
            with z.open(name) as fh:
                for r in _csv_rows(io.TextIOWrapper(fh, encoding='cp1250'), ';'):
                    o.read()
                    cp.read()
                    if r['Číslo orientační'] and r['Kód ulice']:
                        o.add(r['Kód ulice'], r['Číslo orientační'] + r['Znak čísla orientačního'], (r['Kód obce'], r['Název obce']))
                    else:
                        o.drop('no street or no orientation number')
                    if r['Typ SO'] == 'č.p.' and r['Číslo domovní']:
                        cp.add(r['Kód části obce'], r['Číslo domovní'], (r['Kód obce'],))
                    else:
                        cp.drop('not a č.p. house number')
    return o.table(), cp.table()


def load_nrw():
    s = Streets('nrw', ('gemeinde', 'gemeinde_name'))
    with zipfile.ZipFile(DATA / 'de/gebref_nrw.zip') as z, z.open('gebref.txt') as fh:
        for line in io.TextIOWrapper(fh, encoding='utf-8', errors='replace'):
            s.read()
            f = line.rstrip('\n').split(';')
            if len(f) < 18:
                s.drop('malformed line')
                continue
            if not f[15]:
                s.drop('no number')
                continue
            gmd = f[3][1:] + f[5] + f[7] + f[9]
            s.add(gmd + ':' + f[13], f[15] + f[16], (gmd, f[10]))
    return s.table()


def load_no():
    s = Streets('no', ('kommune', 'kommune_name'))
    with zipfile.ZipFile(DATA / 'no/Basisdata_0000_Norge_25833_MatrikkelenAdresse_CSV.zip') as z:
        name = [n for n in z.namelist() if n.endswith('.csv')][0]
        with z.open(name) as fh:
            for r in _csv_rows(io.TextIOWrapper(fh, encoding='utf-8-sig'), ';'):
                s.read()
                if r['adressetype'] != 'vegadresse':
                    s.drop('cadastral address (no street)')
                elif not r['nummer']:
                    s.drop('no number')
                else:
                    s.add((r['kommunenummer'], r['adressekode']), r['nummer'] + r['bokstav'],
                          (r['kommunenummer'], r['kommunenavn'].title()))
    return s.table()


def load_lt():
    s = Streets('lt', ('sav', 'gyv'))
    with open(DATA / 'lt/adr_stat_lr.csv', encoding='utf-8-sig') as fh:
        for r in _csv_rows(fh, '|'):
            s.read()
            if not r['GAT_KODAS']:
                s.drop('no street (village address)')
            elif not r['NR']:
                s.drop('no number')
            else:
                s.add(r['GAT_KODAS'], r['NR'] + ((' k' + r['KORPUSO_NR']) if r['KORPUSO_NR'] else ''), (r['SAV_KODAS'], r['GYV_KODAS']))
    return s.table()


def _dbf(fh, fields):
    hdr = fh.read(32)
    nrec, hlen, rlen = struct.unpack('<IHH', hdr[4:12])
    flds, off = [], 1
    while True:
        d = fh.read(32)
        if d[0] == 0x0D:
            break
        flds.append((d[:11].split(b'\0')[0].decode('ascii'), off, d[16]))
        off += d[16]
    fh.seek(hlen)
    want = [x for x in flds if x[0] in fields]
    for _ in range(nrec):
        rec = fh.read(rlen)
        if not rec:
            break
        if rec[:1] == b'*':
            yield None
            continue
        yield {n: rec[a:a + ln].decode('utf-8', 'replace').strip() for n, a, ln in want}


def load_pl():
    s = Streets('pl', ('city',))
    for t in PL_CITIES:
        with zipfile.ZipFile(DATA / f'pl/{t}.zip') as z, z.open(f'PRG_PunktyAdresowe_{t}.dbf') as fh:
            for r in _dbf(io.BufferedReader(fh, 1 << 20), {'ID_SIMC', 'ID_ULIC', 'NUMER_PORZ'}):
                s.read()
                if r is None:
                    s.drop('deleted DBF record')
                elif not r['ID_ULIC']:
                    s.drop('no street')
                else:
                    s.add((r['ID_SIMC'], r['ID_ULIC']), r['NUMER_PORZ'], (t,))
    return s.table()


def load_nl():
    s = Streets('nl')
    with open(DATA / 'nl/ams_num.csv', encoding='utf-8') as fh:
        for r in _csv_rows(fh):
            s.read()
            if r['eindGeldigheid']:
                s.drop('ended')
            elif not r['huisnummer']:
                s.drop('no number')
            else:
                s.add(r['ligtAanOpenbareruimteId'], None, number=int(r['huisnummer']), suffix=r['huisletter'],
                      extra=r['huisnummertoevoeging'])
    return s.table()


def load_be():
    s = Streets('be')
    with zipfile.ZipFile(DATA / 'be/openaddress-bebru.zip') as z, z.open(z.namelist()[0]) as fh:
        for r in _csv_rows(io.TextIOWrapper(fh, encoding='utf-8')):
            s.read()
            if r['status'] != 'current':
                s.drop('status ' + r['status'])
            elif not r['house_number']:
                s.drop('no number')
            else:
                s.add(r['street_id'] + '@' + r['municipality_id'], r['house_number'], extra=r['box_number'])
    return s.table()


def load_fi():
    s = Streets('fi', ('city',))
    with open(DATA / 'fi/pks_osoiteluettelo.csv', encoding='utf-8-sig') as fh:
        for r in _csv_rows(fh):
            s.read()
            if not r['osoitenumero']:
                s.drop('no number')
            else:
                s.add((r['kaupunki'], r['katunimi']), r['osoitenumero'] + (r['osoitekirjain'] or '') +
                      (('-' + r['osoitenumero2']) if r['osoitenumero2'] else ''), (r['kaupunki'],))
    return s.table()


def load_es():
    s = Streets('es')
    with open(DATA / 'es/direccionesvigentes_20261102.csv', encoding='latin1') as fh:
        for r in _csv_rows(fh, ';'):
            s.read()
            if r['CLASE_APP'] != 'NUMERO':
                s.drop('not a house number (' + r['CLASE_APP'].strip().lower() + ')')
            else:
                s.add(r['COD_VIA'], r['NUMERO'] + (r['CALIFICADOR'] or '').strip())
    return s.table()


def load_milan():
    s = Streets('it_mi')
    s2 = Streets('it_mi_nocarrai')
    with zipfile.ZipFile(DATA / 'it/milano.zip') as z, z.open(z.namelist()[0]) as fh:
        for r in _csv_rows(io.TextIOWrapper(fh, encoding='utf-8-sig'), ';'):
            s.read()
            s2.read()
            if r['STATOCIVICO'] != 'Applicato' or r['DATA_SOPPRESSIONE'] not in ('0', ''):
                s.drop('not in force')
                s2.drop('not in force')
                continue
            raw = r['NUMERO'] + (r['LETTERA'] or '').strip() + (('/' + r['BARRA'].strip()) if r['BARRA'].strip() else '')
            s.add(r['CODICE_VIA'], raw)
            if r['PASSOCARRAIO'] not in ('0', ''):
                s2.drop('driveway number (passo carraio)')
            else:
                s2.add(r['CODICE_VIA'], raw)
    return s.table(), s2.table()


def load_bologna():
    s = Streets('it_bo')
    with open(DATA / 'it/bologna_civici_ref2025.csv', encoding='utf-8-sig') as fh:
        for r in _csv_rows(fh, ';'):
            s.read()
            if r['data_cess']:
                s.drop('ceased')
            else:
                s.add(r['codvia'], r['civico'] + (('/' + r['subciv']) if r['subciv'] else ''))
    return s.table()


def load_ru():
    s = Streets('ru')
    with open(DATA / 'ru/gar_78_houses.csv', encoding='utf-8') as fh:
        for r in _csv_rows(fh):
            s.read()
            if r['level'] != '8':
                s.drop('not on a street (parent level != 8)')
            else:
                s.add(r['street_id'], r['housenum'] + ((' к' + r['addnum1']) if r['addnum1'] else ''))
    return s.table()


def load_sf():
    s = Streets('us')
    with open(DATA / 'us/sf_eas.csv', encoding='utf-8') as fh:
        for r in _csv_rows(fh):
            s.read()
            n, _ = parse_num(r['address_number'])
            if n is None:
                s.drop('number not parsed')
            elif not r['street_full_street_name']:
                s.drop('no street')
            elif n % 100 == 0:
                s.drop('number ends in 00 (no N in 1..99)')
            else:
                s.add((r['street_full_street_name'], n // 100), None, number=n % 100,
                      suffix=(r['address_number_suffix'] or '').strip(), extra=str(n))
    return s.table()


FW = str.maketrans('０１２３４５６７８９', '0123456789')


def load_tw():
    s = Streets('tw')
    rx = re.compile(r'^(\d+)(?:之(\d+))?號')
    with open(DATA / 'tw/taipei.csv', encoding='utf-8-sig') as fh:
        rd = csv.reader(fh)
        hdr = next(rd)
        ix = {h: i for i, h in enumerate(hdr)}
        lanes = []
        for r in rd:
            s.read()
            if len(r) < len(hdr):
                s.drop('short row')
                continue
            m = rx.match(r[ix['號']].translate(FW).strip())
            if not m:
                s.drop('number not parsed')
                continue
            street = r[ix['街路段']] or r[ix['地區']]
            if not street:
                s.drop('no street')
                continue
            lane, alley = r[ix['巷']].translate(FW), r[ix['弄']].translate(FW)
            dist = r[ix['鄉鎮市區代碼']]
            s.add((dist, street, lane, alley), None, number=int(m.group(1)), suffix=m.group(2) or '')
            lm = re.match(r'^(\d+)巷$', lane)
            if lm and not alley:
                lanes.append(((dist, street, '', ''), int(lm.group(1))))
            am = re.match(r'^(\d+)弄$', alley)
            if am:
                lanes.append(((dist, street, lane, ''), int(am.group(1))))
    for key, n in lanes:
        s.occupy(key, n)
    return s.table()


def load_uk():
    """Two street tables (all 2024 sales of houses, new builds only) and the sales for the price comparison."""
    al, nw = Streets('uk_all'), Streets('uk_new')
    sales = []
    with open(DATA / 'uk/pp-2024-slim.csv', encoding='utf-8') as fh:
        for r in _csv_rows(fh):
            al.read()
            nw.read()
            why = 'flat (secondary address)' if r['saon'] else ('no street' if not r['street'] else None)
            if why:
                al.drop(why)
                nw.drop(why)
                continue
            key = (r['street'], r['town'], r['district'])
            al.add(key, r['paon'])
            if r['new'] == 'Y':
                nw.add(key, r['paon'])
            else:
                nw.drop('not a new build')
            n, sx = parse_num(r['paon'])
            if n and not sx and n <= 60 and r['cat'] == 'A' and r['ptype'] in 'DSTF':
                sales.append((key, n, float(r['price']), r['ptype'] + r['new'], r['date'][5:7]))
    return al.table(), nw.table(), sales


def load_sg():
    town = collections.defaultdict(set)
    qa = collections.Counter()
    with open(DATA / 'sg/hdb_property_info.csv', encoding='utf-8') as fh:
        for r in _csv_rows(fh):
            qa['rows'] += 1
            n, _ = parse_num(r['blk_no'])
            if n is None:
                qa['drop: number not parsed'] += 1
                continue
            if n in town[r['bldg_contract_town']]:
                qa['drop: block number repeated within the town'] += 1
                continue
            qa['kept'] += 1
            town[r['bldg_contract_town']].add(n)
    return town, dict(qa)


# ---------------------------------------------------------------- France: BAN -> street table
FULLBIS = {'bis', 'ter', 'quater', 'quinquies', 'sexies'}
BTQ = {'b', 't', 'q'}  # Paris codes bis/ter/quater as b/t/q; elsewhere 'b' is often the letter B
FR_COLS = ['dep', 'key', 'code_insee', 'insee_anc', 'commune', 'voie', 'fantoir', 'n_addr', 'n_num', 'max_num', 'any_lo', 'plain_lo',
           'bis_lo', 'btq_lo', 'let_lo', 'any_hi', 'corner_lo', 'cert_share', 'src_pos', 'src_nom']


def extract_ban(path, outdir):
    """One BAN department -> one row per street with bitmasks: any (any suffix), plain, bis/ter, b/t/q, other letter;
    numbers 96..158 for the 113 control; corner flags (an address of ANOTHER street within 15 m of the midpoint of
    N-2 and N+2)."""
    dep = re.search(r'adresses-(\w+)\.csv', path.name).group(1)
    streets, keys, seen = {}, [], set()
    qa = collections.Counter()
    grid = collections.defaultdict(list)
    CELL, R = 20.0, 15.0
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        for row in csv.DictReader(f, delimiter=';'):
            qa['rows'] += 1
            try:
                n = int(row['numero'])
            except ValueError:
                qa['drop: number not an integer'] += 1
                continue
            if n <= 0:
                qa['drop: number 0'] += 1
                continue
            if n >= 5000:
                qa['drop: number >= 5000 (lieu-dit codes)'] += 1
                continue
            rep = (row['rep'] or '').strip().lower()
            key = row['id_fantoir'] or (row['code_insee'] + '|' + row['nom_voie'].lower())
            if (key, n, rep) in seen:
                qa['drop: duplicate address'] += 1
                continue
            seen.add((key, n, rep))
            qa['kept'] += 1
            s = streets.get(key)
            if s is None:
                s = streets[key] = dict(idx=len(keys), code_insee=row['code_insee'], insee_anc=row['code_insee_ancienne_commune'],
                                        commune=row['nom_commune'], voie=row['nom_voie'], fantoir=row['id_fantoir'], n_addr=0,
                                        max_num=0, any_lo=0, plain_lo=0, bis_lo=0, btq_lo=0, let_lo=0, any_hi=0, cert=0,
                                        src=collections.Counter(), srcnom=collections.Counter(), xy={}, nums=set())
                keys.append(key)
            s['n_addr'] += 1
            s['nums'].add(n)
            s['max_num'] = max(s['max_num'], n)
            s['cert'] += row['certification_commune'] == '1'
            s['src'][row['source_position']] += 1
            s['srcnom'][row['source_nom_voie']] += 1
            if n <= 62:
                b = 1 << n
                s['any_lo'] |= b
                if not rep:
                    s['plain_lo'] |= b
                elif rep in FULLBIS:
                    s['bis_lo'] |= b
                elif rep in BTQ:
                    s['btq_lo'] |= b
                else:
                    s['let_lo'] |= b
            elif 96 <= n <= 158:
                s['any_hi'] |= 1 << (n - 96)
            try:
                x, y = float(row['x']), float(row['y'])
            except ValueError:
                continue
            if n <= 62 and (n not in s['xy'] or not rep):
                s['xy'][n] = (x, y)
            grid[(int(x // CELL), int(y // CELL))].append((x, y, s['idx']))
    out = outdir / f'streets-{dep}.csv.gz'
    tmp = outdir / f'streets-{dep}.csv.gz.part'
    with gzip.open(tmp, 'wt', encoding='utf-8', newline='') as g:
        w = csv.writer(g)
        w.writerow(FR_COLS)
        for key, s in streets.items():
            cm, xy = 0, s['xy']
            for N in range(5, 62, 2):
                if (N - 2) in xy and (N + 2) in xy:
                    (x1, y1), (x2, y2) = xy[N - 2], xy[N + 2]
                    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
                    cx, cy = int(mx // CELL), int(my // CELL)
                    if any(si != s['idx'] and (px - mx) ** 2 + (py - my) ** 2 <= R * R
                           for dx in (-1, 0, 1) for dy in (-1, 0, 1) for (px, py, si) in grid.get((cx + dx, cy + dy), ())):
                        cm |= 1 << N
            w.writerow([dep, key, s['code_insee'], s['insee_anc'], s['commune'], s['voie'], s['fantoir'], s['n_addr'], len(s['nums']),
                        s['max_num'], s['any_lo'], s['plain_lo'], s['bis_lo'], s['btq_lo'], s['let_lo'], s['any_hi'], cm,
                        round(s['cert'] / s['n_addr'], 3), s['src'].most_common(1)[0][0], s['srcnom'].most_common(1)[0][0]])
    tmp.rename(out)
    qa = dict(qa)
    qa['streets'] = len(streets)
    qa['source_bytes'] = path.stat().st_size
    (outdir / f'qa-{dep}.json').write_text(json.dumps(qa))
    return qa


def ban_streets():
    outdir = WORK / 'fr_streets'
    outdir.mkdir(parents=True, exist_ok=True)
    files = sorted((DATA / 'fr').glob('adresses-*.csv.gz'))
    only = os.environ.get('HOUSE13_FR_DEPS')
    if only:
        files = [f for f in files if f.name[9:-7] in only.split(',')]
    for i, f in enumerate(files):
        dep = f.name[9:-7]
        q = outdir / f'qa-{dep}.json'
        if q.exists() and (outdir / f'streets-{dep}.csv.gz').exists() and json.loads(q.read_text()).get('source_bytes') == f.stat().st_size:
            continue
        qa = extract_ban(f, outdir)
        log(f'BAN {dep} ({i + 1}/{len(files)}): {qa.get("rows", 0)} rows, {qa["streets"]} streets')
    return [f.name[9:-7] for f in files]


def topo_dates():
    """TOPO -> BAN-compatible fantoir key ('<insee>_<code_voie>') + creation date; a live record wins, then the earliest."""
    out = WORK / 'topo_dates.csv.gz'
    if out.exists():
        return out
    best = {}
    with gzip.open(DATA / 'topo/topo_sel.csv.gz', 'rt', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f, delimiter=';'):
            dep, com = row['code_dep'], row['code_commune']
            insee = dep + com[-2:] if len(dep) == 3 else ((dep + com)[-5:] if len(dep + com) >= 5 else (dep + com).zfill(5))
            key = insee + '_' + row['code_voie']
            cand = (row['date_annulation'] not in ('', '00000000'), row['date_creation_de_article'])
            if key not in best or cand < best[key]:
                best[key] = cand
    with gzip.open(out, 'wt', encoding='utf-8', newline='') as g:
        w = csv.writer(g)
        w.writerow(['fantoir', 'date_creation', 'annulled'])
        for k, (ann, d) in best.items():
            w.writerow([k, d, int(ann)])
    return out


REGIONS = {'Auvergne-Rhône-Alpes': '01 03 07 15 26 38 42 43 63 69 73 74', 'Bourgogne-Franche-Comté': '21 25 39 58 70 71 89 90',
           'Bretagne': '22 29 35 56', 'Centre-Val de Loire': '18 28 36 37 41 45', 'Corse': '2A 2B',
           'Grand Est': '08 10 51 52 54 55 57 67 68 88', 'Hauts-de-France': '02 59 60 62 80', 'Île-de-France': '75 77 78 91 92 93 94 95',
           'Normandie': '14 27 50 61 76', 'Nouvelle-Aquitaine': '16 17 19 23 24 33 40 47 64 79 86 87',
           'Occitanie': '09 11 12 30 31 32 34 46 48 65 66 81 82', 'Pays de la Loire': '44 49 53 72 85',
           "Provence-Alpes-Côte d'Azur": '04 05 06 13 83 84', 'Outre-mer': '971 972 973 974 975 976 977 978 984 986 987 988 989'}
OVERSEAS = {'971': 'Guadeloupe', '972': 'Martinique', '973': 'Guyane', '974': 'La Réunion', '975': 'Saint-Pierre-et-Miquelon',
            '976': 'Mayotte', '977': 'Saint-Barthélemy', '978': 'Saint-Martin', '984': 'Terres australes et antarctiques',
            '986': 'Wallis-et-Futuna', '987': 'Polynésie française', '988': 'Nouvelle-Calédonie', '989': 'Clipperton'}
PLM = {'75056': 'Paris', '69123': 'Lyon', '13055': 'Marseille'}


def city_code(insee):
    out = insee.copy()
    out[insee.str.match(r'^751(0[1-9]|1[0-9]|20)$')] = '75056'
    out[insee.str.match(r'^6938[1-9]$')] = '69123'
    out[insee.str.match(r'^132(0[1-9]|1[0-6])$')] = '13055'
    return out


def load_fr(deps):
    np, pd = _np()
    dtype = {'dep': str, 'code_insee': str, 'commune': str, 'voie': str, 'fantoir': str, 'n_addr': np.int32, 'n_num': np.int32,
             'max_num': np.int32, 'any_lo': np.uint64, 'plain_lo': np.uint64, 'bis_lo': np.uint64, 'btq_lo': np.uint64,
             'let_lo': np.uint64, 'any_hi': np.uint64, 'corner_lo': np.uint64, 'cert_share': np.float32, 'src_pos': str}
    parts = [pd.read_csv(WORK / 'fr_streets' / f'streets-{d}.csv.gz', usecols=list(dtype), dtype=dtype, keep_default_na=False)
             for d in deps]
    df = pd.concat(parts, ignore_index=True)
    del parts
    for c in ('dep', 'src_pos', 'commune'):
        df[c] = df[c].astype('category')
    # only the first word of the street name is used (street type, H7 details): keep it as a category, drop the name
    df['first'] = pd.Categorical([''.join(ch for ch in unicodedata.normalize('NFKD', v.split(' ', 1)[0]) if not unicodedata.combining(ch)).lower()
                                  if v else '' for v in df.voie])
    df['nkey'] = pd.Categorical([name_key(v) if not f else '' for v, f in zip(df.voie, df.fantoir)])
    return df.drop(columns='voie')


_ABBR = {'r': 'rue', 'av': 'avenue', 'ave': 'avenue', 'bd': 'boulevard', 'pl': 'place', 'all': 'allee', 'imp': 'impasse',
         'che': 'chemin', 'chem': 'chemin', 'rte': 'route', 'sq': 'square', 'qu': 'quai', 'crs': 'cours', 'pass': 'passage',
         'vla': 'villa', 'res': 'residence', 'lot': 'lotissement', 'rpt': 'rond point', 'fg': 'faubourg', 'esp': 'esplanade',
         'sen': 'sentier', 'ham': 'hameau', 'gal': 'galerie', 'prom': 'promenade', 'pt': 'petit', 'gde': 'grande', 'gr': 'grand'}
_STOP = {'de', 'du', 'des', 'la', 'le', 'les', 'l', 'd', 'st', 'saint', 'ste', 'sainte', 'a', 'au', 'aux', 'en'}


def name_key(name):
    """Street name normalised for the BAN <-> DVF join (DVF abbreviates the type: 'AV MONTAIGNE' = 'Avenue Montaigne')."""
    w = re.sub(r'[^a-z0-9]+', ' ', ''.join(c for c in unicodedata.normalize('NFKD', name or '') if not unicodedata.combining(c)).lower()).split()
    if w and w[0] in _ABBR:
        w = _ABBR[w[0]].split() + w[1:]
    return ' '.join(x for x in w if x not in _STOP)


def dvf_streets():
    """Every DVF 2021-2025 mutation row with an integer address number (any nature, any local, any suffix) -> per street a
    bitmask of numbers 1..62. Streets are keyed '<commune>_<code_voie>' (also under the former commune's code) and, for the
    name fallback, '<commune>|<normalised name>'. Cached in _work/dvf_streets.tsv.gz."""
    out = WORK / 'dvf_streets.tsv.gz'
    meta = WORK / 'dvf_streets.json'
    sizes = {str(y): (DATA / f'dvf/full-{y}.csv.gz').stat().st_size for y in DVF_YEARS}
    if out.exists() and meta.exists() and json.loads(meta.read_text()).get('sizes') == sizes:
        with gzip.open(out, 'rt', encoding='utf-8') as fh:
            return {k: int(m) for k, m in csv.reader(fh, delimiter='\t')}, json.loads(meta.read_text())['qa']
    masks = collections.defaultdict(int)
    qa = collections.Counter()
    for y in DVF_YEARS:
        with gzip.open(DATA / f'dvf/full-{y}.csv.gz', 'rt', encoding='utf-8', newline='') as f:
            rd = csv.reader(f)
            h = {c: i for i, c in enumerate(next(rd))}
            iN, iV, iNom, iC, iA = h['adresse_numero'], h['adresse_code_voie'], h['adresse_nom_voie'], h['code_commune'], h['ancien_code_commune']
            for r in rd:
                qa['rows'] += 1
                num = r[iN]
                if not num.isdigit():
                    qa['drop: no integer number'] += 1
                    continue
                n = int(num)
                if not 1 <= n <= 62:
                    qa['drop: number outside 1..62'] += 1
                    continue
                qa['kept'] += 1
                b = 1 << n
                cv = r[iV].upper()
                if cv:
                    masks[r[iC] + '_' + cv] |= b
                    if r[iA] and r[iA] != r[iC]:
                        masks[r[iA] + '_' + cv] |= b
                masks[r[iC] + '|' + name_key(r[iNom])] |= b
        log('DVF cadastre', y)
    tmp = out.with_name(out.name + '.part')
    with gzip.open(tmp, 'wt', encoding='utf-8', newline='') as fh:
        w = csv.writer(fh, delimiter='\t')
        for k, m in masks.items():
            w.writerow([k, m])
    tmp.rename(out)
    meta.write_text(json.dumps(dict(sizes=sizes, qa=dict(qa))))
    return dict(masks), dict(qa)


def cadastre_check(df, A, B, commune, dep):
    """A11: on BAN streets eligible for 13, does DVF know a No.13 (and No.11, No.15) on the same street?"""
    np, _ = _np()
    masks, qa = dvf_streets()
    low50 = (1 << 51) - 1
    fant = df.fantoir.astype(str).to_numpy()
    nkey = df.nkey.astype(str).to_numpy()
    el = B[:, I13] == 1
    m = np.zeros(len(df), dtype=np.int64)
    how = np.zeros(len(df), dtype=np.int8)  # 1 = FANTOIR code, 2 = name (street without FANTOIR id)
    for i in np.where(el)[0]:
        if fant[i]:
            v = masks.get(fant[i][:6] + fant[i][6:].upper())
            if v is not None:
                m[i], how[i] = v, 1
        elif nkey[i]:
            v = masks.get(commune[i] + '|' + nkey[i])
            if v is not None:
                m[i], how[i] = v, 2
    indvf = (m & low50) != 0
    has_n = {n: ((m >> n) & 1).astype(bool) for n in (11, 13, 15)}
    miss = el & (A[:, I13] == 1)
    pres = el & (A[:, I13] == 0)
    out = dict(qa=qa)
    for name, sel in (('all', np.ones(len(df), bool)), ('paris', dep == '75'), ('limoges', commune == '87085'),
                      ('rest', dep != '75')):
        g = {}
        for lab, grp in (('missing', miss & sel), ('present', pres & sel)):
            pre = '' if lab == 'missing' else 'present_'
            inn = grp & indvf
            g['streets_' + lab] = int(grp.sum())
            g[f'{pre}in_dvf'] = int(inn.sum())
            g[f'{pre}in_dvf_by_code'] = int((inn & (how == 1)).sum())
            g[f'{pre}in_dvf_by_name'] = int((inn & (how == 2)).sum())
            for n in (13, 11, 15):
                g[f'{pre}with_sale{n}'] = int((inn & has_n[n]).sum())
                g[f'{pre}share_sale{n}'] = 100 * float((inn & has_n[n]).sum()) / max(int(inn.sum()), 1)
        out[name] = g
    return out


def svg_map(geo_path, deps_wanted=None, budget=80_000):
    """Department outlines (metropolitan France) -> SVG path strings: conic-ish projection, Douglas-Peucker, integer coords."""
    gj = json.loads(Path(geo_path).read_text())
    lat0 = math.radians(46.5)

    def proj(lon, lat):
        return lon * math.cos(lat0), -lat
    feats = []
    for f in gj['features']:
        g = f['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        feats.append((f['properties']['code'], f['properties']['nom'], [[[proj(*p) for p in ring] for ring in poly] for poly in polys]))
    xs = [p[0] for _, _, ps in feats for poly in ps for ring in poly for p in ring]
    ys = [p[1] for _, _, ps in feats for poly in ps for ring in poly for p in ring]
    W = 1000.0
    k = W / (max(xs) - min(xs))
    H = (max(ys) - min(ys)) * k
    x0, y0 = min(xs), min(ys)

    def dp(pts, tol):
        if len(pts) < 3:
            return pts
        keep = [False] * len(pts)
        keep[0] = keep[-1] = True
        stack = [(0, len(pts) - 1)]
        while stack:
            i, j = stack.pop()
            (ax, ay), (bx, by) = pts[i], pts[j]
            dx, dy = bx - ax, by - ay
            L = math.hypot(dx, dy) or 1e-12
            best, bi = -1, None
            for m in range(i + 1, j):
                px, py = pts[m]
                d = abs(dy * (px - ax) - dx * (py - ay)) / L if (dx or dy) else math.hypot(px - ax, py - ay)
                if d > best:
                    best, bi = d, m
            if bi is not None and best > tol:
                keep[bi] = True
                stack += [(i, bi), (bi, j)]
        return [p for p, kk in zip(pts, keep) if kk]

    def build(tol):
        out = []
        for code, nom, polys in feats:
            parts = []
            for poly in polys:
                for ring in poly:
                    pts = [((x - x0) * k, (y - y0) * k) for x, y in ring]
                    area = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
                    if area < 4:
                        continue
                    s = dp(pts, tol)
                    q = []
                    for x, y in s:
                        p = (round(x), round(y))
                        if not q or p != q[-1]:
                            q.append(p)
                    if len(q) < 4:
                        continue
                    seg = [f'M{q[0][0]} {q[0][1]}l']
                    seg += [f'{x1 - x0_} {y1 - y0_}'.replace(' -', '-') for (x0_, y0_), (x1, y1) in zip(q, q[1:-1] if q[-1] == q[0] else q[1:])]
                    parts.append(seg[0] + ' '.join(seg[1:]).replace(' -', '-') + 'z')
            out.append(dict(code=code, name=nom, d=''.join(parts)))
        return out
    tol = 0.4
    while True:
        deps = build(tol)
        size = sum(len(d['d']) + 20 for d in deps)
        if size <= budget - 2000 or tol > 6:
            break
        tol *= 1.25
    return dict(viewBox=f'0 0 {round(W)} {round(H)}', tolerance=round(tol, 2), departments=deps), {d['code']: d['name'] for d in deps}


# ---------------------------------------------------------------- France analysis
def compute_france():
    np, pd = _np()
    deps = ban_streets()
    qa_fr = collections.Counter()
    for d in deps:
        for k, v in json.loads((WORK / 'fr_streets' / f'qa-{d}.json').read_text()).items():
            if k != 'source_bytes':
                qa_fr[k] += v
    paris_qa = json.loads((WORK / 'fr_streets' / 'qa-75.json').read_text()) if '75' in deps else {}
    gmap, dep_names = svg_map(DATA / 'map/departements-version-simplifiee.geojson')
    dep_names.update(OVERSEAS)
    df = load_fr(deps)
    log('France streets', len(df), 'addresses', int(df.n_addr.sum()))
    insee = df.code_insee
    df['city'] = city_code(insee)
    anyl = df.any_lo.to_numpy(np.uint64)
    A, B = ab(anyl, ODD)
    commune = df.code_insee.to_numpy()
    dep = df.dep.astype(str).to_numpy()
    city = df.city.to_numpy()
    R = dict(qa=dict(qa_fr), qa_paris=paris_qa, n_streets=int(len(df)), n_addr=int(df.n_addr.sum()))

    tot = result(A, B, clusters=commune, seed=1)
    R['total'] = tot
    log('France 13:', tot['missing13'], '/', tot['eligible13'], f"excess {tot['excess']:.2f} [{tot['lo']:.2f}; {tot['hi']:.2f}]")
    loc = [ODD.index(n) for n in (9, 11, 15, 17)]
    rob = {}
    rob['local_bg'] = dict(excess=tot['r13'] - 100 * float(np.mean(np.array(tot['a'])[loc] / np.array(tot['b'])[loc])))
    metro = ~pd.Series(dep).str.match(r'^9[78]').to_numpy()
    for name, m in (('metropole', metro), ('overseas', ~metro), ('without_paris', dep != '75'),
                    ('without_limousin', ~np.isin(dep, ['19', '23', '87']))):
        rob[name] = result(A, B, np.where(m)[0], commune, seed=2)
    for name, kw in (('pm2', dict(scheme='sides')), ('dense', {})):
        if name == 'pm2':
            A2 = np.zeros_like(A)
            B2 = np.zeros_like(B)
            for j, N in enumerate(ODD):
                ok = has(anyl, N - 2) & has(anyl, N + 2)
                B2[:, j] = ok
                A2[:, j] = ok & ~has(anyl, N)
        else:
            def dense_ok(N):
                rng = [x for x in range(N - 10, N + 11, 2) if x > 0 and x != N]
                return sum(has(anyl, x).astype(int) for x in rng) >= 0.8 * len(rng)
            A2, B2 = ab(anyl, ODD, extra_ok=dense_ok)
        rob[name] = result(A2, B2, clusters=commune, seed=3)
        del A2, B2
    corner = df.corner_lo.to_numpy(np.uint64)
    C = np.stack([has(corner, N) for N in ODD], 1)
    rob['no_corner'] = result(A * ~C, B * ~C, clusters=commune, seed=4)
    rob['corner_share_missing'] = {N: round(100 * float(C[A[:, j] == 1, j].mean()), 2) for j, N in enumerate(ODD)}
    del C
    R['robustness'] = rob
    # controls: even numbers, 1xx, the 4 family
    E = EVENS[1:15]  # 6..32
    Ae, Be = ab(anyl, E)
    R['control_even'] = {N: dict(r=100 * Ae[:, j].sum() / Be[:, j].sum(), eligible=int(Be[:, j].sum())) for j, N in enumerate(E)}
    for N in (12, 14, 16):
        j = E.index(N)
        R['control_even'][N]['excess'] = float(stats(Ae.sum(0), Be.sum(0), j)['excess'])
    del Ae, Be
    hi = df.any_hi.to_numpy(np.uint64)
    HI = list(range(105, 122, 2))
    Ah = np.zeros((len(df), len(HI)), np.int8)
    Bh = np.zeros_like(Ah)
    for j, N in enumerate(HI):
        ok = np.ones(len(df), bool)
        for x in neighbours(N, 'sides'):
            ok &= has(hi, x - 96)
        Bh[:, j] = ok
        Ah[:, j] = ok & ~has(hi, N - 96)
    j113 = HI.index(113)
    R['control_1xx'] = {N: dict(r=100 * Ah[:, j].sum() / max(Bh[:, j].sum(), 1), eligible=int(Bh[:, j].sum())) for j, N in enumerate(HI)}
    R['control_113'] = {k: float(v) for k, v in stats(Ah.sum(0), Bh.sum(0), j113).items()}
    del Ah, Bh
    A4, B4 = ab(anyl, EVENS, 'sides3')
    R['control_fours'] = fours_block(A4, B4)
    del A4, B4

    # departments
    rows = []
    dcode = pd.factorize(dep)
    for d, idx in pd.Series(np.arange(len(df))).groupby(dep).groups.items():
        idx = np.asarray(idx)
        r = result(A, B, idx, commune, seed=5)
        r.update(code=d, name=dep_names.get(d, d), n_streets=int(len(idx)), addresses=int(df.n_addr.to_numpy()[idx].sum()))
        rows.append(r)
    add_q(rows)
    mu = tot['excess']
    sds = np.array([r['sd'] for r in rows])
    xs = np.array([r['excess'] for r in rows])
    tau2 = max(float(np.nanmean((xs - mu) ** 2 - sds ** 2)), 0.0)
    for r in rows:
        r['shrunk'] = mu + tau2 / (tau2 + r['sd'] ** 2) * (r['excess'] - mu) if r['sd'] == r['sd'] else mu
        r['p_holm'] = None
    hp = holm([r['p'] if r['p'] == r['p'] else 1.0 for r in rows])
    for r, h in zip(rows, hp):
        r['p_holm'] = h
    R['departments'] = sorted(rows, key=lambda r: -r['excess'])
    del dcode
    log('departments done')

    d2r = {d: r for r, ds in REGIONS.items() for d in ds.split()}
    reg = np.array([d2r.get(d, '?') for d in dep], dtype=object)
    rr = []
    for name in REGIONS:
        r = result(A, B, np.where(reg == name)[0], commune, seed=6)
        r.update(name=name)
        rr.append(r)
    lim = result(A, B, np.where(np.isin(dep, ['19', '23', '87']))[0], commune, seed=7)
    lim.update(name='Limousin (19, 23, 87)', former_region=True)
    rr.append(lim)
    R['regions'] = sorted(add_q(rr), key=lambda r: -r['excess'])

    # communes (cities PLM-merged for the city list; communes for "no 13 anywhere")
    cc, cu = pd.factorize(commune)
    ac, bc = group_sums(cc, A, B, len(cu))
    cname = df.groupby('code_insee', sort=False).commune.first()
    R['communes_all_missing'] = []
    R['communes_ge10'] = 0
    for i in np.where(bc[:, I13] >= 10)[0]:
        R['communes_ge10'] += 1
        if ac[i, I13] == bc[i, I13]:
            R['communes_all_missing'].append(dict(insee=cu[i], name=cname[cu[i]], dep=cu[i][:3] if cu[i].startswith('97') else cu[i][:2],
                                                  eligible13=int(bc[i, I13])))
    R['communes_ge50pct'] = int(np.sum((bc[:, I13] >= 10) & (ac[:, I13] >= 0.5 * bc[:, I13])))
    st_c = stats(ac, bc)
    se_c = binom_se(ac, bc)
    with np.errstate(invalid='ignore', divide='ignore'):
        pc = [norm_sf(e / s) if b >= 20 and s > 0 else float('nan') for e, s, b in zip(st_c['excess'], se_c, bc[:, I13])]
    R['communes_sig_bh'] = int(sum(1 for q in bh(pc) if q == q and q < 0.05))
    R['communes_tested'] = int(sum(1 for p in pc if p == p))
    del ac, bc

    ci, cuu = pd.factorize(city)
    a_ci, b_ci = group_sums(ci, A, B, len(cuu))
    nstreets = np.bincount(ci, minlength=len(cuu))
    caddr = np.bincount(ci, weights=df.n_addr.to_numpy(), minlength=len(cuu))
    cities = []
    top_i = set(np.argsort(-nstreets, kind='stable')[:20].tolist())
    for i in sorted(set(np.where(b_ci[:, I13] >= 150)[0].tolist()) | top_i):
        r = result(a_ci[i][None], b_ci[i][None])
        code = cuu[i]
        r.update(id='fr-' + code, country='FR', name=PLM.get(code) or cname.get(code, code), insee=code,
                 n_streets=int(nstreets[i]), addresses=int(caddr[i]), top20=i in top_i)
        cities.append(r)
    R['cities'] = cities
    top20 = {cuu[i] for i in top_i}
    log('cities done')

    # Paris arrondissements
    pa = []
    for code in sorted(c for c in cu if re.match(r'^751(0[1-9]|1[0-9]|20)$', c)):
        r = result(A, B, np.where(commune == code)[0])
        r.update(arr=int(code[-2:]), insee=code)
        pa.append(r)
    R['paris'] = add_q(pa)

    # size classes (cities PLM-merged, addresses of the city) and H2
    city_addr = pd.Series(caddr, index=cuu)
    df_city_addr = city_addr.reindex(city).to_numpy()
    bins = [0, 500, 2000, 10000, 50000, 10 ** 12]
    labels = ['<500', '500-2k', '2k-10k', '10k-50k', '>=50k']
    sc = []
    for lo_, hi_, lab in zip(bins[:-1], bins[1:], labels):
        r = result(A, B, np.where((df_city_addr >= lo_) & (df_city_addr < hi_))[0], city, seed=8)
        r.update(size_class=lab, n_cities=r.get('n_clusters'))
        sc.append(r)
    R['size_classes'] = sc
    rural = np.where(df_city_addr < 2000)[0]
    h2 = {}
    for nm, m in (('top20', np.isin(city, list(top20))), ('ge50k', df_city_addr >= 50000)):
        big = result(A, B, np.where(m)[0], city, seed=9, keep_boot=True)
        rur = result(A, B, rural, city, seed=10, keep_boot=True)
        if '_boot' not in big or '_boot' not in rur:
            continue
        d = big.pop('_boot') - rur.pop('_boot')
        h2[nm] = dict(big=strip(big), rural=strip(rur), diff=big['excess'] - rur['excess'], lo=float(np.nanpercentile(d, 2.5)),
                      hi=float(np.nanpercentile(d, 97.5)), p=float((np.sum(d <= 0) + 1) / (np.sum(~np.isnan(d)) + 1)))
    R['H2'] = h2
    log('H2 done')

    # H3: "11 with a suffix" on streets without 13, Paris vs province
    paris = dep == '75'
    suf = (df.bis_lo.to_numpy(np.uint64) | df.btq_lo.to_numpy(np.uint64) | df.let_lo.to_numpy(np.uint64))
    bisf = df.bis_lo.to_numpy(np.uint64) | df.btq_lo.to_numpy(np.uint64)
    plain = df.plain_lo.to_numpy(np.uint64)
    clus3 = np.where(paris, np.arange(len(df)).astype(str), commune)
    cl3 = pd.factorize(clus3)[0]

    def share_boot(num1, den1, num2, den2, seed=7):
        S = np.stack([np.bincount(cl3, weights=x.astype(float), minlength=cl3.max() + 1) for x in (num1, den1, num2, den2)], 1)
        rng = np.random.default_rng(seed)
        out = []
        for s in range(0, REPS, 250):
            W = rng.poisson(1.0, size=(min(250, REPS - s), S.shape[0])).astype(np.float32)
            T = W @ S.astype(np.float32)
            out.append(T[:, 0] / T[:, 1] - T[:, 2] / T[:, 3])
        return np.concatenate(out)
    h3, bts = {}, {}
    for region, m in (('paris', paris), ('rest', ~paris)):
        el = (B[:, I13] == 1) & m
        mi = (A[:, I13] == 1) & m
        pr = el & ~mi
        h11, h11b, h12 = has(suf, 11), has(bisf, 11), has(suf, 12)
        bt = share_boot(mi & h11, mi, pr & h11, pr)
        bts[region] = bt
        plac = []
        for j, N in enumerate(ODD):
            if N in (5, 13):
                continue
            elN, miN = (B[:, j] == 1) & m, (A[:, j] == 1) & m
            hN = has(suf, N - 2)
            plac.append(100 * (hN[miN].mean() - hN[elN & ~miN].mean()))
        only13 = el & has(anyl, 13) & ~has(plain, 13)
        onlyN = [float(np.mean((((B[:, j] == 1) & m) & has(anyl, N) & ~has(plain, N))[(B[:, j] == 1) & m])) * 100
                 for j, N in enumerate(ODD) if N != 13]
        bgm = np.mean([A[m, j].sum() / B[m, j].sum() for j in range(len(ODD)) if j != I13])
        h3[region] = dict(**{'with': 100 * float(h11[pr].mean()), 'without': 100 * float(h11[mi].mean())},
                          lift=100 * float(h11[mi].mean() - h11[pr].mean()),
                          lo=100 * float(np.percentile(bt, 2.5)), hi=100 * float(np.percentile(bt, 97.5)),
                          bis_with=100 * float(h11b[pr].mean()), bis_without=100 * float(h11b[mi].mean()),
                          b12_lift=100 * float(h12[mi].mean() - h12[pr].mean()),
                          placebo_lift_mean=float(np.mean(plac)), placebo_lift_max=float(np.max(plac)),
                          bis13_without_plain13=100 * float(only13.sum() / max(el.sum(), 1)), bisN_without_plainN=float(np.mean(onlyN)),
                          missing13=int(mi.sum()), eligible13=int(el.sum()),
                          excess_streets=float(mi.sum() - bgm * el.sum()),
                          excess_streets_with11suffix=float((mi & h11).sum() - (pr & h11).sum() * bgm / (1 - bgm)))
    d = bts['paris'] - bts['rest']
    h3['diff'] = dict(diff=h3['paris']['lift'] - h3['rest']['lift'], lo=100 * float(np.nanpercentile(d, 2.5)),
                      hi=100 * float(np.nanpercentile(d, 97.5)), p=float((np.sum(d <= 0) + 1) / (np.sum(~np.isnan(d)) + 1)))
    R['H3'] = h3
    del suf, bisf, plain
    log('H3 done')

    # H7: TOPO creation date of the street record, street type, provenance
    need = set(df.fantoir)
    year_of = {}
    with gzip.open(topo_dates(), 'rt', encoding='utf-8', newline='') as fh:  # streamed: 7.9 M records would not fit as a frame
        for k, d_, _ in csv.reader(fh):
            if k in need and d_[:4].isdigit():
                year_of[k] = int(d_[:4])
    del need
    yr = np.array([year_of.get(k, np.nan) for k in df.fantoir], dtype=float)
    del year_of
    R['topo_match_share'] = float(np.mean(~np.isnan(yr) & (df.fantoir.to_numpy() != '')))
    init = pd.Series(yr).groupby(dep).agg(lambda s: s.mode().iloc[0] if s.notna().any() else np.nan)
    iy = pd.Series(dep).map(init).to_numpy(float)
    known = ~np.isnan(yr)
    age = np.full(len(df), 'unknown', object)
    age[known & (yr > iy + 2) & (yr < 2000)] = 'added later, before 2000'
    age[known & (yr >= 2000) & (yr < 2010)] = 'added 2000-2009'
    age[known & (yr >= 2010)] = 'added 2010+'
    age[known & (yr <= iy + 2)] = 'in register at initial load'
    age[(df.fantoir.to_numpy() == '')] = 'no FANTOIR id'
    groups = []
    for g in ('in register at initial load', 'added later, before 2000', 'added 2000-2009', 'added 2010+', 'no FANTOIR id'):
        r = result(A, B, np.where(age == g)[0], commune, seed=11)
        r.update(group=g)
        groups.append(r)
    old = result(A, B, np.where(age == 'in register at initial load')[0], commune, seed=12, keep_boot=True)
    new = result(A, B, np.where(np.isin(age, ['added 2000-2009', 'added 2010+']))[0], commune, seed=13, keep_boot=True)
    d = new.pop('_boot') - old.pop('_boot')
    age_res = dict(groups=groups, new=strip(new), old=strip(old), diff=new['excess'] - old['excess'], lo=float(np.nanpercentile(d, 2.5)),
                   hi=float(np.nanpercentile(d, 97.5)), p=float((np.sum(d <= 0) + 1) / (np.sum(~np.isnan(d)) + 1)),
                   init_years=collections.Counter(int(v) for v in init.dropna()).most_common(5))
    per = []
    oldm, newm = age == 'in register at initial load', np.isin(age, ['added 2000-2009', 'added 2010+'])
    for dd, idx in pd.Series(np.arange(len(df))).groupby(dep).groups.items():
        idx = np.asarray(idx)
        o, n = idx[oldm[idx]], idx[newm[idx]]
        if B[o, I13].sum() < 30 or B[n, I13].sum() < 30:
            continue
        so = stats(A[o].sum(0), B[o].sum(0))
        sn = stats(A[n].sum(0), B[n].sum(0))
        per.append((dd, int(B[o, I13].sum()), int(B[n, I13].sum()), float(sn['excess'] - so['excess'])))
    w = np.array([1 / (1 / x[1] + 1 / x[2]) for x in per])
    dv = np.array([x[3] for x in per])
    rng = np.random.default_rng(4)
    bs = [np.sum(w[k] * dv[k]) / w[k].sum() for k in (rng.integers(0, len(per), len(per)) for _ in range(REPS))]
    nolim = np.array([x[0] not in ('19', '23', '87') for x in per])
    age_res['within_department'] = dict(n_departments=len(per), diff=float(np.sum(w * dv) / w.sum()), lo=float(np.percentile(bs, 2.5)),
                                        hi=float(np.percentile(bs, 97.5)), share_positive=float(np.mean(dv > 0)),
                                        without_limousin=float(np.sum(w[nolim] * dv[nolim]) / w[nolim].sum()))
    first = df['first'].astype(str).to_numpy()
    OLD = {'rue', 'avenue', 'boulevard', 'place', 'quai', 'cours', 'faubourg'}
    NEW = {'impasse', 'allee', 'allees', 'residence', 'lotissement', 'clos', 'square', 'hameau', 'domaine', 'parc'}
    tp = []
    for g, m in (('rue/avenue/boulevard/place/quai', np.isin(first, list(OLD))), ('allée/impasse/résidence/lotissement', np.isin(first, list(NEW))),
                 ('route', first == 'route'), ('chemin', first == 'chemin'), ('lieu-dit and other', ~np.isin(first, list(OLD | NEW | {'route', 'chemin'})))):
        r = result(A, B, np.where(m)[0], commune, seed=14)
        r.update(group=g)
        tp.append(r)
    age_res['street_type'] = tp
    ce = df.cert_share.to_numpy()
    sp = df.src_pos.astype(str).to_numpy()
    prov = []
    for g, m in (('certified by the commune', ce >= 0.999), ('not certified', ce < 0.999), ('position from the commune', sp == 'commune')):
        r = result(A, B, np.where(m)[0], commune, seed=15)
        r.update(group=g)
        prov.append(r)
    age_res['provenance'] = prov
    R['age'] = age_res
    R['cadastre'] = cadastre_check(df, A, B, commune, dep)
    log('cadastre check done')
    log('H7 done')
    R['profile'] = [100 * a / b for a, b in zip(tot['a'], tot['b'])]
    R['map'] = gmap
    del df, A, B
    gc.collect()
    R['price'] = compute_dvf()
    return R


def strip(r):
    return {k: v for k, v in r.items() if k not in ('a', 'b', '_boot')}


def fours_block(A4, B4):
    """4/14/24/34 on the scheme N-2, N+2, N+4; background = even numbers without a digit 4."""
    np, _ = _np()
    a, b = A4.sum(0).astype(float), B4.sum(0).astype(float)
    bgi = [EVENS.index(n) for n in FOUR_BG]
    with np.errstate(invalid='ignore', divide='ignore'):
        r = a / b
    bg = float(np.nanmean(r[bgi]))
    out = dict(bg=100 * bg, numbers=[])
    for n in FOURS:
        j = EVENS.index(n)
        se = float(binom_se(a, b, j, bgi))
        out['numbers'].append(dict(n=n, r=100 * float(r[j]), eligible=int(b[j]), missing=int(a[j]), excess=100 * (float(r[j]) - bg),
                                   lo=100 * (float(r[j]) - bg) - 1.96 * se, hi=100 * (float(r[j]) - bg) + 1.96 * se))
    fj = [EVENS.index(n) for n in FOURS]
    rf = a[fj].sum() / b[fj].sum()
    vf = rf * (1 - rf) / b[fj].sum()
    vb = np.nansum((r[bgi] * (1 - r[bgi]) / b[bgi])) / len(bgi) ** 2
    se = 100 * math.sqrt(vf + vb)
    out['family'] = dict(r=100 * rf, excess=100 * (rf - bg), lo=100 * (rf - bg) - 1.96 * se, hi=100 * (rf - bg) + 1.96 * se,
                         p=norm_sf(100 * (rf - bg) / se), eligible=int(b[fj].sum()), missing=int(a[fj].sum()))
    out['profile'] = {n: 100 * float(r[j]) for j, n in enumerate(EVENS)}
    return out


# ---------------------------------------------------------------- H6: DVF prices
DVF_KEEP = ['date_mutation', 'valeur_fonciere', 'adresse_numero', 'adresse_suffixe', 'adresse_nom_voie', 'adresse_code_voie', 'code_commune',
            'code_departement', 'type_local', 'surface_reelle_bati', 'nombre_pieces_principales']


def dvf_extract(src, dst):
    """Single-dwelling sales: nature 'Vente', exactly one Appartement/Maison (rows of the same dwelling over parcels collapsed),
    no commercial local, number 1..199, surface >= 9 m2, price > 0."""
    qa = collections.Counter()
    cur_id, cur = None, []
    tmp = dst.with_name(dst.name + '.part')
    with gzip.open(src, 'rt', encoding='utf-8', newline='') as f, gzip.open(tmp, 'wt', encoding='utf-8', newline='') as g:
        w = csv.writer(g)
        w.writerow(['id_mutation'] + DVF_KEEP)

        def flush(mid, rows):
            if not rows:
                return
            qa['mutations'] += 1
            if rows[0]['nature_mutation'] != 'Vente':
                qa['drop: not a sale'] += 1
                return
            dw, commercial = {}, False
            for x in rows:
                c = x['code_type_local']
                if c in ('1', '2'):
                    dw[(c, x['surface_reelle_bati'], x['nombre_pieces_principales'], x['adresse_numero'], x['adresse_suffixe'],
                        x['adresse_code_voie'], x['code_commune'])] = x
                elif c == '4':
                    commercial = True
            if commercial:
                qa['drop: commercial local'] += 1
                return
            if len(dw) != 1:
                qa['drop: %s dwellings' % ('0' if not dw else '2+')] += 1
                return
            x = next(iter(dw.values()))
            try:
                n, s, v = int(x['adresse_numero']), float(x['surface_reelle_bati']), float(x['valeur_fonciere'])
            except ValueError:
                qa['drop: bad number or surface'] += 1
                return
            if not (1 <= n <= 199) or s < 9 or v <= 0:
                qa['drop: out of range'] += 1
                return
            qa['kept'] += 1
            w.writerow([mid] + [x[k] for k in DVF_KEEP])
        for row in csv.DictReader(f):
            qa['rows'] += 1
            if row['id_mutation'] != cur_id:
                flush(cur_id, cur)
                cur_id, cur = row['id_mutation'], []
            cur.append(row)
        flush(cur_id, cur)
    tmp.rename(dst)
    return dict(qa)


def fe_fit(sub, N, controls):
    """log price on 1[number == N] within fixed-effect groups (FWL), CR1 standard errors clustered by street."""
    np, pd = _np()
    sub = sub.assign(isN=(sub.num == N).astype(float))
    X = pd.concat([sub[['isN']]] + [c(sub) for c in controls], axis=1)
    g = sub.grp.to_numpy()
    Xd = (X - X.groupby(g).transform('mean')).to_numpy(float)
    yd = (sub.y - sub.y.groupby(g).transform('mean')).to_numpy(float)
    inv = np.linalg.pinv(Xd.T @ Xd)
    b = inv @ (Xd.T @ yd)
    e = yd - Xd @ b
    cl = sub.street.to_numpy()
    sc = pd.DataFrame(Xd * e[:, None]).groupby(cl).sum().to_numpy()
    G, n, k = sc.shape[0], len(yd), Xd.shape[1] + len(np.unique(g))
    V = inv @ (sc.T @ sc) @ inv * G / (G - 1) * (n - 1) / max(n - k, 1)
    return float(b[0]), float(np.sqrt(V[0, 0])), int(sub.isN.sum()), n, int(sub.street.nunique())


def price_by_number(d, controls, Ns=range(7, 42, 2), min_n=30):
    np, _ = _np()
    rows = []
    for N in Ns:
        nb = [N + k for k in (-6, -4, -2, 2, 4, 6) if N + k > 0]
        sub = d[d.num.isin(nb + [N])]
        both = np.intersect1d(sub[sub.num == N].street.unique(), sub[sub.num != N].street.unique())
        sub = sub[sub.street.isin(both)]
        if (sub.num == N).sum() < min_n:
            continue
        b, se, nN, n, ns = fe_fit(sub, N, controls)
        rows.append(dict(n=N, effect_pct=100 * (math.exp(b) - 1), lo=100 * (math.exp(b - 1.96 * se) - 1),
                         hi=100 * (math.exp(b + 1.96 * se) - 1), z=b / se, n_at=nN, n_sales=n, n_streets=ns))
    return rows


def summarize_price(rows):
    r13 = [r for r in rows if r['n'] == 13]
    if not r13:
        return None
    r13 = r13[0]
    oth = [r for r in rows if r['n'] != 13]
    eff = [r['effect_pct'] for r in oth]
    return dict(effect_pct=r13['effect_pct'], lo=r13['lo'], hi=r13['hi'], z=r13['z'], n13=r13['n_at'], n_sales=r13['n_sales'],
                n_streets=r13['n_streets'], p_cheaper=1 - norm_sf(r13['z']), placebo_mean=sum(eff) / len(eff),
                placebo_sd=(sum((x - sum(eff) / len(eff)) ** 2 for x in eff) / (len(eff) - 1)) ** 0.5,
                rank_cheapest=1 + sum(1 for x in eff if x < r13['effect_pct']), of=len(rows))


def compute_dvf():
    np, pd = _np()
    outd = WORK / 'dvf'
    outd.mkdir(parents=True, exist_ok=True)
    qa = {}
    for y in DVF_YEARS:
        dst, q = outd / f'sales-{y}.csv.gz', outd / f'qa-{y}.json'
        src = DATA / f'dvf/full-{y}.csv.gz'
        if not (dst.exists() and q.exists() and json.loads(q.read_text()).get('source_bytes') == src.stat().st_size):
            r = dvf_extract(src, dst)
            r['source_bytes'] = src.stat().st_size
            q.write_text(json.dumps(r))
            log('DVF', y, r['kept'], 'sales kept')
        qa[y] = json.loads(q.read_text())
    dt_ = dict(adresse_numero=np.int16, adresse_suffixe=str, adresse_code_voie=str, code_commune=str, code_departement=str,
               type_local=str, surface_reelle_bati=np.float32, nombre_pieces_principales=np.float32, valeur_fonciere=np.float64,
               adresse_nom_voie=str, date_mutation=str)
    parts, n_loaded = [], 0
    for y in DVF_YEARS:  # one year at a time, kept as a compact frame (memory)
        x = pd.read_csv(outd / f'sales-{y}.csv.gz', usecols=list(dt_), dtype=dt_, keep_default_na=False,
                        na_values={'nombre_pieces_principales': ['']})
        n_loaded += len(x)
        x = x[x.adresse_suffixe == '']
        vc = np.where(x.adresse_code_voie != '', x.adresse_code_voie, x.adresse_nom_voie.str.upper())
        parts.append(pd.DataFrame(dict(
            y=np.log(x.valeur_fonciere.to_numpy() / x.surface_reelle_bati.to_numpy()), num=x.adresse_numero.to_numpy(),
            skey=pd.Categorical(x.code_commune.to_numpy() + '_' + vc), house=(x.type_local == 'Maison').to_numpy(),
            dep=pd.Categorical(x.code_departement.to_numpy()), year=np.int16(y),
            lsurf=np.log(x.surface_reelle_bati.to_numpy()).astype(np.float32),
            rooms=x.nombre_pieces_principales.fillna(0).clip(0, 6).astype(np.int8).to_numpy())))
        del x, vc
        gc.collect()
    res = dict(qa=qa, rows_loaded=n_loaded)
    d = pd.concat(parts, ignore_index=True)
    del parts
    res['rows_plain_number'] = len(d)
    # trim 1 % / 99 % of log price per m2 within department x dwelling type (symbolic prices, data-entry errors)
    d['dep'] = d.dep.astype(str)
    q = d.groupby(['dep', 'house']).y.quantile([0.01, 0.99]).unstack()
    lo_ = pd.MultiIndex.from_arrays([d.dep, d.house]).map(q[0.01])
    hi_ = pd.MultiIndex.from_arrays([d.dep, d.house]).map(q[0.99])
    d = d[(d.y.to_numpy() >= np.asarray(lo_)) & (d.y.to_numpy() <= np.asarray(hi_))].reset_index(drop=True)
    n_all = len(d)
    d['street'] = pd.factorize(d.skey.astype(str))[0]
    d = d.drop(columns='skey')
    d['grp'] = d.street.astype(np.int64) * 2 + d.house.astype(np.int64)
    res['sales_by_number'] = {int(k): int(v) for k, v in d[d.num <= 45].groupby('num').size().items()}
    controls = [lambda s: s[['lsurf']], lambda s: pd.get_dummies(s.year, prefix='y', drop_first=True, dtype=float),
                lambda s: pd.get_dummies(s.rooms, prefix='r', drop_first=True, dtype=float)]
    by = price_by_number(d, controls)
    res['by_number'] = by
    res.update(summarize_price(by))
    res['n_sales'] = res['n_sales_all'] = n_all
    for name, m in (('paris', d.dep == '75'), ('rest', d.dep != '75'), ('apartments', ~d.house), ('houses', d.house)):
        res[name] = summarize_price(price_by_number(d[m.to_numpy()], controls))
    log('DVF done: 13 =', round(res['effect_pct'], 2), '%')
    return res


# ---------------------------------------------------------------- other countries
CH_CITIES = {'261': 'Zürich', '6621': 'Genève', '2701': 'Basel', '351': 'Bern', '5586': 'Lausanne', '230': 'Winterthur',
             '1061': 'Luzern', '3203': 'St. Gallen', '5192': 'Lugano'}
CH_FR = ('GE', 'VD', 'NE', 'JU')
GR_ITALIAN = {'Mesocco', 'Soazza', 'Lostallo', 'Cama', 'Grono', 'Roveredo (GR)', 'San Vittore', 'Rossa', 'Buseno', 'Castaneda',
              'Santa Maria in Calanca', 'Calanca', 'Bregaglia', 'Poschiavo', 'Brusio'}
_FR = re.compile(r"^(rue|chemin|ch\.|route|rte|avenue|av\.|place|impasse|allée|boulevard|quai|sentier|promenade|passage|clos|esplanade|"
                 r"faubourg|ruelle|montée|square|grand-rue|grand'rue|chemin|champ|pré|les |la |le |l')\b", re.I)
_IT = re.compile(r'^(via|vicolo|piazza|piazzetta|strada|salita|contrada|viale|sentiero|riva|lungolago|carrale|stradone|vicolo)\b', re.I)
_RM = re.compile(r'^(via|vietta|plazza|stradun|senda|truoch|quartier|chasa|punt|curtin|giassa|streda|veia|vial|sur)\b', re.I)
_DE = re.compile(r'(strasse|straße|weg|gasse|platz|rain|matte|halde|steig|allee|ring|hof|acker|feld|graben|stutz|park|quai|ufer)\b', re.I)


def ch_language(t):
    """Majority language of each commune's street names (heuristic, see docstring)."""
    np, _ = _np()
    cnt = collections.defaultdict(collections.Counter)
    for com, name, cant, lab in zip(t['commune'], t['commune_name'], t['canton'], t['label']):
        lab = lab or ''
        if cant == 'GR' and _RM.match(lab) and name not in GR_ITALIAN:
            cnt[com]['rm'] += 1
        elif _IT.match(lab):
            cnt[com]['it'] += 1
        elif _FR.match(lab):
            cnt[com]['fr'] += 1
        elif _DE.search(lab):
            cnt[com]['de'] += 1
    lang = {}
    for com, cant in zip(t['commune'], t['canton']):
        if com not in lang:
            c = cnt.get(com)
            lang[com] = c.most_common(1)[0][0] if c else ('fr' if cant in CH_FR else 'it' if cant == 'TI' else 'de')
    return np.array([lang[c] for c in t['commune']], dtype=object)


def generic(t, label, scope, country, clusters=None, seed=21, fours=False):
    A, B = ab(t['any'], ODD)
    r = result(A, B, clusters=t[clusters] if clusters else None, seed=seed)
    r.update(name=label, scope=scope, country=country, addresses=int(t['n_addr'].sum()), n_streets=int(len(t['any'])))
    suf = t['suf']
    h11 = has(suf, 11)
    mi, el = A[:, I13] == 1, B[:, I13] == 1
    if mi.sum() and (el & ~mi).sum():
        r['bis11'] = [100 * float(h11[mi].mean()), 100 * float(h11[el & ~mi].mean())]
    if fours:
        A4, B4 = ab(t['any'], EVENS, 'sides3')
        r['fours'] = fours_block(A4, B4)
    return r, A, B


def sub_result(A, B, t, mask, clusters=None, seed=31, **meta):
    np, _ = _np()
    idx = np.where(mask)[0]
    r = result(A, B, idx, t[clusters] if clusters else None, seed=seed)
    r.update(addresses=int(t['n_addr'][idx].sum()), n_streets=int(len(idx)), **meta)
    return r


def t17(A, B, idx=None, clusters=None, seed=41):
    """17 as the target: background = odd numbers other than 13 and 17."""
    bgi = [i for i in range(len(ODD)) if i not in (I13, I17)]
    return result(A, B, idx, clusters, t=I17, bgi=bgi, seed=seed)


def consecutive(sets, Ns=CONSEC):
    """Consecutive numbering (Singapore HDB towns, Czech č.p. by part of municipality): neighbours N-2, N-1, N+1, N+2."""
    a = [0] * len(Ns)
    b = [0] * len(Ns)
    for s in sets:
        for j, N in enumerate(Ns):
            if all(x in s for x in neighbours(N, 'consec')):
                b[j] += 1
                a[j] += N not in s
    return a, b


def compute_others():
    np, pd = _np()
    R = dict(areas={}, cities=[], qa={})
    gc.collect()

    # Switzerland
    t = load_ch()
    R['qa']['ch'] = t['qa']
    r, A, B = generic(t, 'Switzerland', 'national', 'CH', 'commune')
    R['areas']['ch'] = r
    cant = []
    for c in sorted(set(t['canton'])):
        cant.append(sub_result(A, B, t, t['canton'] == c, 'commune', code=c))
    lang = ch_language(t)
    langs = [sub_result(A, B, t, lang == L, 'commune', lang=L, n_communes=int(len(set(t['commune'][lang == L])))) for L in ('de', 'fr', 'it', 'rm')]
    ti = np.where(t['canton'] == 'TI')[0]
    ticino = dict(r13=strip(result(A, B, ti, t['commune'], seed=51)), r17=strip(t17(A, B, ti, t['commune'])))
    R['areas']['ch-ticino'] = sub_result(A, B, t, t['canton'] == 'TI', 'commune', name='Ticino', scope='region', country='CH')
    chc = []
    for code, nm in CH_CITIES.items():
        chc.append(sub_result(A, B, t, t['commune'] == code, name=nm, code=code))
    for code in sorted(set(t['commune'])):
        m = t['commune'] == code
        if B[m, I13].sum() >= 150:
            nm = t['commune_name'][np.argmax(m)]
            R['cities'].append(sub_result(A, B, t, m, id='ch-' + code, country='CH', name=nm))
    R['switzerland'] = dict(total=strip(r), cantons=add_q(cant), languages=add_q(langs), cities=add_q(chc), ticino=ticino,
                            profile=[100 * a / b for a, b in zip(r['a'], r['b'])])
    for code, key in (('261', 'ch-zurich'), ('2701', 'ch-basel'), ('351', 'ch-bern'), ('230', 'ch-winterthur'), ('6621', 'ch-geneva'),
                      ('5586', 'ch-lausanne'), ('5192', 'ch-lugano')):
        R['areas'][key] = sub_result(A, B, t, t['commune'] == code, name=CH_CITIES[code], scope='city', country='CH')
    R['_pool'] = {'ch': (r['a'], r['b'], int(t['n_addr'].sum()), len(t['any']))}
    del t, A, B, lang
    gc.collect()
    log('Switzerland done')

    def national(key, loader, label, country, clusters, cities_col, names_col=None, named=(), scope='national', pool=True):
        t = loader()
        R['qa'][key] = t['qa']
        r, A, B = generic(t, label, scope, country, clusters)
        R['areas'][key] = r
        if pool:
            R['_pool'][key] = (r['a'], r['b'], int(t['n_addr'].sum()), len(t['any']))
        col = t[cities_col]
        codes, inv = np.unique(col.astype(str), return_inverse=True)
        bsum = np.bincount(inv, weights=B[:, I13], minlength=len(codes))
        for i in np.where(bsum >= 150)[0]:
            m = inv == i
            nm = t[names_col][np.argmax(m)] if names_col else codes[i]
            R['cities'].append(sub_result(A, B, t, m, id=f'{country.lower()}-{codes[i]}', country=country, name=nm))
        for code, akey, nm in named:
            R['areas'][akey] = sub_result(A, B, t, col == code, name=nm, scope='city', country=country)
        return t, A, B

    t, A, B = national('lt', load_lt, 'Lithuania', 'LT', 'sav', 'sav', None, named=(('13', 'lt-vilnius', 'Vilnius'),))
    # municipality codes carry no names in this register: only Vilnius (13) is checked and kept in the city list
    R['cities'] = [dict(c, name='Vilnius') if c['id'] == 'lt-13' else c for c in R['cities'] if c['country'] != 'LT' or c['id'] == 'lt-13']
    del t, A, B
    gc.collect()
    log('Lithuania done')

    o, cp = load_cz()
    R['qa']['cz'], R['qa']['cz_cp'] = o['qa'], cp['qa']
    r, A, B = generic(o, 'Czechia (orientation numbers)', 'national', 'CZ', 'obec')
    R['areas']['cz'] = r
    R['_pool']['cz'] = (r['a'], r['b'], int(o['n_addr'].sum()), len(o['any']))
    for code, akey, nm in (('554782', 'cz-praha', 'Praha'), ('582786', 'cz-brno', 'Brno')):
        R['areas'][akey] = sub_result(A, B, o, o['obec'] == code, name=nm, scope='city', country='CZ')
    codes, inv = np.unique(o['obec'].astype(str), return_inverse=True)
    bsum = np.bincount(inv, weights=B[:, I13], minlength=len(codes))
    for i in np.where(bsum >= 150)[0]:
        m = inv == i
        R['cities'].append(sub_result(A, B, o, m, id='cz-' + codes[i], country='CZ', name=o['obec_name'][np.argmax(m)]))
    sets = collections.defaultdict(set)
    for k, i in zip(range(len(cp['any'])), cp['any']):
        sets[k] = {n for n in range(1, 64) if (int(i) >> n) & 1}
    a, b = consecutive(sets.values())
    R['consecutive_cz'] = dict(a=a, b=b, addresses=int(cp['n_addr'].sum()), parts=len(cp['any']))
    del o, cp, A, B, sets
    gc.collect()
    log('Czechia done')

    t, A, B = national('no', load_no, 'Norway', 'NO', 'kommune', 'kommune', 'kommune_name',
                       named=(('0301', 'no-oslo', 'Oslo'), ('4601', 'no-bergen', 'Bergen'), ('5001', 'no-trondheim', 'Trondheim'),
                              ('1103', 'no-stavanger', 'Stavanger')))
    del t, A, B
    gc.collect()
    log('Norway done')
    t, A, B = national('nrw', load_nrw, 'North Rhine-Westphalia', 'DE', 'gemeinde', 'gemeinde', 'gemeinde_name', scope='region',
                       named=(('5315000', 'de-koln', 'Köln'),))
    del t, A, B
    gc.collect()
    log('NRW done')
    t = load_pl()
    R['qa']['pl'] = t['qa']
    r, A, B = generic(t, '66 Polish cities with powiat rights', 'region', 'PL', 'city')
    R['areas']['pl'] = r
    R['_pool']['pl'] = (r['a'], r['b'], int(t['n_addr'].sum()), len(t['any']))
    plc = []
    for code, nm in PL_CITIES.items():
        x = sub_result(A, B, t, t['city'] == code, id='pl-' + code, country='PL', name=nm)
        plc.append(x)
        if x['eligible13'] >= 150:
            R['cities'].append(x)
    R['poland'] = add_q(plc)
    for code, akey in (('1261', 'pl-krakow'), ('1465', 'pl-warszawa'), ('1061', 'pl-lodz'), ('0264', 'pl-wroclaw'), ('3064', 'pl-poznan'),
                       ('2261', 'pl-gdansk')):
        R['areas'][akey] = sub_result(A, B, t, t['city'] == code, name=PL_CITIES[code], scope='city', country='PL')
    del t, A, B
    gc.collect()
    log('Poland done')

    for key, loader, label, country in (('nl', load_nl, 'Amsterdam (with Weesp)', 'NL'), ('be', load_be, 'Brussels (region)', 'BE'),
                                        ('fi', load_fi, 'Helsinki, Espoo, Vantaa, Kauniainen', 'FI'), ('es', load_es, 'Madrid', 'ES'),
                                        ('ru', load_ru, 'Saint Petersburg', 'RU')):
        t = loader()
        R['qa'][key] = t['qa']
        r, A, B = generic(t, label, 'city', country, fours=key in ('nl', 'ru'))
        R['areas'][key] = r
        R['_pool'][key] = (r['a'], r['b'], int(t['n_addr'].sum()), len(t['any']))
        if r['eligible13'] >= 150:
            R['cities'].append(dict(strip(r), id=key))
        del t, A, B
    log('city registers done')

    mi, mi2 = load_milan()
    bo = load_bologna()
    R['qa']['it-mi'], R['qa']['it-mi-nocarrai'], R['qa']['it-bo'] = mi['qa'], mi2['qa'], bo['qa']
    italy = {}
    pool17 = []
    for key, t, label in (('it-milan', mi, 'Milan'), ('it-bologna', bo, 'Bologna'), ('it-milan-nocarrai', mi2, 'Milan without driveway numbers')):
        r, A, B = generic(t, label, 'city', 'IT')
        r17 = t17(A, B)
        italy[key] = dict(r13=strip(r), r17=strip(r17))
        if key != 'it-milan-nocarrai':
            R['areas'][key] = r
            R['_pool'][key] = (r['a'], r['b'], int(t['n_addr'].sum()), len(t['any']))
            pool17.append((r17['a'], r17['b']))
            if r['eligible13'] >= 150:
                R['cities'].append(dict(strip(r), id=key))
    a = [x + y for x, y in zip(*[p[0] for p in pool17])]
    b = [x + y for x, y in zip(*[p[1] for p in pool17])]
    np_a, np_b = np.array([a], float), np.array([b], float)
    p17 = t17(np_a, np_b)
    italy['pooled17'] = strip(p17)
    italy['ticino'] = ticino
    R['italy'] = italy
    del mi, mi2, bo

    t = load_sf()
    R['qa']['us'] = t['qa']
    r, _, _ = generic(t, 'San Francisco (number within its hundred block)', 'city', 'US', fours=True)
    R['areas']['us'] = r
    t = load_tw()
    R['qa']['tw'] = t['qa']
    r, _, _ = generic(t, 'Taipei, Songshan district', 'district', 'TW', fours=True)
    R['areas']['tw'] = r
    R['_pool']['tw'] = (r['a'], r['b'], int(t['n_addr'].sum()), len(t['any']))
    al, nw, sales = load_uk()
    R['qa']['uk_all'], R['qa']['uk_new'] = al['qa'], nw['qa']
    rn, _, _ = generic(nw, 'England and Wales, new builds sold in 2024', 'national', 'GB')
    ra, _, _ = generic(al, 'England and Wales, all house sales 2024', 'national', 'GB')
    R['uk'] = dict(new=rn, all=strip(ra), addresses=int(al['n_addr'].sum()))
    R['uk']['price'] = uk_price(sales)
    del al, nw, sales
    town, qa = load_sg()
    R['qa']['sg'] = qa
    a, b = consecutive(town.values())
    res = {}
    big = list(range(3, 999))
    aa, bb = consecutive(town.values(), big)
    def agg(pred):
        return sum(x for n, x in zip(big, aa) if pred(n)), sum(x for n, x in zip(big, bb) if pred(n))
    for nm, pt, pb in (('ends_in_4', lambda n: n % 10 == 4, lambda n: n % 10 != 4),
                       ('ends_in_0', lambda n: n % 10 == 0, lambda n: n % 10 != 0),
                       ('x13', lambda n: n % 100 == 13, lambda n: n % 2 == 1 and n % 100 != 13)):
        m1, e1 = agg(pt)
        m0, e0 = agg(pb)
        p1, p0 = m1 / e1, m0 / e0
        pp = (m1 + m0) / (e1 + e0)
        z = (p1 - p0) / math.sqrt(pp * (1 - pp) * (1 / e1 + 1 / e0))
        res[nm] = dict(r=100 * p1, bg=100 * p0, eligible=e1, missing=m1, z=z)
    R['consecutive_sg'] = dict(a=a, b=b, last_digit=res, blocks=qa['kept'], towns=len(town))
    log('others done')
    return R


def uk_price(sales):
    """H6 for England and Wales on 2024 only: log price of No.N vs odd neighbours on the same street, FE street x type x new."""
    np, pd = _np()
    if not sales:
        return None
    d = pd.DataFrame(sales, columns=['key', 'num', 'price', 'kind', 'month'])
    d['street'] = pd.factorize(d.key.astype(str))[0]
    d['grp'] = pd.factorize(d.street.astype(str) + d.kind)[0]
    d['y'] = np.log(d.price)
    controls = [lambda s: pd.get_dummies(s.month, prefix='m', drop_first=True, dtype=float)]
    rows = price_by_number(d[['y', 'num', 'street', 'grp', 'month']], controls, min_n=20)
    out = summarize_price(rows)
    if out:
        out['by_number'] = rows
    return out


# ---------------------------------------------------------------- compute: all, then the page structures
AREA_ORDER = ['fr', 'ch', 'lt', 'cz', 'no', 'nrw', 'pl', 'nl', 'be', 'fi', 'es', 'it-milan', 'it-bologna', 'ru', 'us', 'tw',
              'fr-paris', 'fr-limoges', 'fr-marseille', 'fr-lyon', 'fr-strasbourg', 'fr-nice', 'fr-limousin', 'fr-paris-08',
              'ch-zurich', 'ch-basel', 'ch-bern', 'ch-winterthur', 'ch-geneva', 'ch-lausanne', 'ch-lugano', 'ch-ticino',
              'pl-warszawa', 'pl-krakow', 'pl-lodz', 'pl-wroclaw', 'pl-poznan', 'pl-gdansk', 'lt-vilnius', 'no-oslo', 'no-bergen',
              'no-trondheim', 'no-stavanger', 'cz-praha', 'cz-brno', 'de-koln']


def compute():
    WORK.mkdir(parents=True, exist_ok=True)
    fr = compute_france()
    (WORK / 'france.json').write_text(json.dumps(fr, default=_jsonable))
    gc.collect()
    ot = compute_others()
    ot_pool = ot.pop('_pool')
    out = dict(france=fr, others=ot, pool={k: list(v) for k, v in ot_pool.items()}, computed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    (WORK / 'computed.json').write_text(json.dumps(out, default=_jsonable))
    log('computed ->', WORK / 'computed.json')


def _jsonable(x):
    try:
        import numpy as np
        if isinstance(x, np.integer):
            return int(x)
        if isinstance(x, np.floating):
            return float(x)
        if isinstance(x, np.ndarray):
            return x.tolist()
    except ImportError:
        pass
    raise TypeError(type(x))


# ---------------------------------------------------------------- validate
# Earlier counts (agents' BAN count and scout probes, 04.11.2026): missing / eligible for 13 (17 where marked).
EXPECTED = {
    'France': (19279, 260642), 'Paris': (155, 2098), 'Switzerland': (3684, 19813), 'Zürich': (160, 287), 'Genève': (26, 96),
    'Basel': (66, 161), 'Bern': (57, 167), 'Lausanne': (13, 97), 'Winterthur': (65, 169), 'Luzern': (14, 89), 'St. Gallen': (17, 75),
    'Lugano': (18, 102), 'Ticino': (175, 1289), 'Ticino 17': (108, 993), 'Czechia': (394, 7792), 'Praha': (80, 1792), 'Brno': (13, 688),
    'Czechia č.p.': (701, 8179), 'NRW': (3583, 52425), 'Madrid': (93, 2726), 'Helsinki region': (91, 1532), 'Bologna': (18, 458),
    'Bologna 17': (15, 358), 'Milan': (89, 328), 'Milan 17': (58, 244), 'Milan without driveways': (55, 212), 'Lithuania': (778, 15382),
    'Vilnius': (90, 989), 'Amsterdam': (68, 2777), 'Oslo': (44, 880), 'Stavanger': (57, 511), 'Bergen': (42, 523), 'Trondheim': (23, 522),
    'Wrocław': (32, 863), 'Łódź': (65, 580), 'Kraków': (108, 630), 'Warszawa': (108, 942), 'Gdańsk': (49, 429), 'Poznań': (55, 739),
    'Saint Petersburg': (106, 707), 'Taipei Songshan': (32, 123), 'UK new builds': (289, 450), 'UK all sales': (312, 490),
    'San Francisco': (257, 544), 'Brussels': (109, 2104),
}


def validate() -> bool:
    c = json.loads((WORK / 'computed.json').read_text())
    fr, ot = c['france'], c['others']
    checks, problems = [], []

    def check(name, ok, detail):
        checks.append(dict(name=name, ok=bool(ok), detail=detail))
        print(('OK   ' if ok else 'FAIL ') + name + ': ' + detail)
        if not ok:
            problems.append(name)
    ar = ot['areas']
    pa = {p['arr']: p for p in fr['paris']}
    paris_city = next(x for x in fr['cities'] if x['insee'] == '75056')
    chc = {x['name']: x for x in ot['switzerland']['cities']}
    pl = {x['name']: x for x in ot['poland']}
    it = ot['italy']
    got = {
        'France': fr['total'], 'Paris': paris_city, 'Switzerland': ar['ch'], 'Ticino': it['ticino']['r13'],
        'Ticino 17': it['ticino']['r17'], 'Czechia': ar['cz'], 'Praha': ar['cz-praha'], 'Brno': ar['cz-brno'], 'NRW': ar['nrw'],
        'Madrid': ar['es'], 'Helsinki region': ar['fi'], 'Bologna': it['it-bologna']['r13'], 'Bologna 17': it['it-bologna']['r17'],
        'Milan': it['it-milan']['r13'], 'Milan 17': it['it-milan']['r17'], 'Milan without driveways': it['it-milan-nocarrai']['r13'],
        'Lithuania': ar['lt'], 'Vilnius': ar['lt-vilnius'], 'Amsterdam': ar['nl'], 'Oslo': ar['no-oslo'], 'Stavanger': ar['no-stavanger'],
        'Bergen': ar['no-bergen'], 'Trondheim': ar['no-trondheim'], 'Saint Petersburg': ar['ru'], 'Taipei Songshan': ar['tw'],
        'UK new builds': ot['uk']['new'], 'UK all sales': ot['uk']['all'], 'San Francisco': ar['us'], 'Brussels': ar['be'],
    }
    for nm in ('Zürich', 'Genève', 'Basel', 'Bern', 'Lausanne', 'Winterthur', 'Luzern', 'St. Gallen', 'Lugano'):
        got[nm] = chc[nm]
    for nm in ('Wrocław', 'Łódź', 'Kraków', 'Warszawa', 'Gdańsk', 'Poznań'):
        got[nm] = pl[nm]
    cz_cp = ot['consecutive_cz']
    got['Czechia č.p.'] = dict(missing13=cz_cp['a'][CONSEC.index(13)], eligible13=cz_cp['b'][CONSEC.index(13)])
    for nm, (m, e) in EXPECTED.items():
        g = got[nm]
        check(f'earlier count: {nm}', (g['missing13'], g['eligible13']) == (m, e),
              f"{g['missing13']}/{g['eligible13']} (expected {m}/{e})")
    z = chc['Zürich']
    check('Zürich share', abs(z['r13'] - 55.75) < 0.01, f"{z['r13']:.2f} %")
    # controls
    ev = fr['control_even']
    for N in ('12', '14', '16'):
        check(f'France even control {N}', abs(ev[N]['excess']) < 1.0, f"r={ev[N]['r']:.2f} %, excess vs other evens {ev[N]['excess']:+.2f} pp")
    c113 = fr['control_113']
    check('France 113 control', c113['excess'] < 1.0 and c113['excess'] < 0.4 * fr['total']['excess'],
          f"r={c113['r13']:.2f} %, bg(105..121)={c113['bg']:.2f} %, excess {c113['excess']:+.2f} pp, rank {int(c113['rank'])}/9")
    # row accounting
    qas = dict(ot['qa'])
    qas['ban'] = fr['qa']
    for k, q in qas.items():
        drops = sum(v for kk, v in q.items() if kk.startswith('drop: '))
        check(f'rows {k}', q['rows'] == q['kept'] + drops,
              f"{q['rows']} rows = {q['kept']} addresses + {drops} dropped (" +
              ', '.join(f"{kk[6:]} {v}" for kk, v in sorted(q.items()) if kk.startswith('drop: ')) + ')')
    check('BAN addresses = sum over streets', fr['qa']['kept'] == fr['n_addr'], f"{fr['qa']['kept']} vs {fr['n_addr']}")
    for k, q in fr['price']['qa'].items():
        drops = sum(v for kk, v in q.items() if kk.startswith('drop: '))
        check(f'DVF {k} mutations', q['mutations'] == q['kept'] + drops, f"{q['mutations']} = {q['kept']} kept + {drops} dropped")
    # manifest
    man = json.loads((DATA / 'manifest.json').read_text()) if (DATA / 'manifest.json').exists() else {}
    for s in SOURCES:
        files = source_files(s)
        miss = [f for f in files if f not in man or not man[f].get('sha256')]
        stale = [f for f in files if f in man and (DATA / f).exists() and man[f]['bytes'] != (DATA / f).stat().st_size]
        check(f'manifest {s["id"]}', files and not miss and not stale and s.get('snapshot'),
              f"{len(files)} files, snapshot {s.get('snapshot')}" + (f', missing {miss[:3]}' if miss else '') + (f', changed {stale[:3]}' if stale else ''))
    check('map size', len(json.dumps(fr['map'], separators=(',', ':'))) <= 80_000,
          f"{len(json.dumps(fr['map'], separators=(',', ':')))} bytes, {len(fr['map']['departments'])} departments, tolerance {fr['map']['tolerance']}")
    check('map has 2A/2B and 96 departments', len(fr['map']['departments']) == 96 and {'2A', '2B'} <= {d['code'] for d in fr['map']['departments']},
          ', '.join(sorted(d['code'] for d in fr['map']['departments']))[:60] + '...')
    allr = [fr['total']] + list(ar.values()) + fr['departments']
    check('rates within 0..100', all(0 <= x['r13'] <= 100 and 0 <= x['bg'] <= 100 for x in allr if x['eligible13']), f'{len(allr)} rows')
    # A11: the independent verifier joined BAN and DVF by normalised street NAME (verify/dvf_cross.py, 04.11.2026); here the
    # join is by FANTOIR code, which finds MORE streets: names miss pairs like BAN "allées de Montbrun" / DVF "ALL DE MONTBRUN"
    # (plural vs abbreviated type). In Limoges that street is the one extra with a No.13 mutation: a single garage
    # (Dépendance) sold at 13 allées de Montbrun in 2021 (mutation 2021-1497336), while BAN has 9, 11, 15, 17 there and no 13.
    # Rule: the code join finds at least the verifier's streets and at most 10 % more; No.13 agrees up to KNOWN_EXTRA;
    # the No.11 / No.15 shares agree within 5 pp.
    VERIFIER = {'limoges': (126, 1, 14, 21), 'paris': (143, 1, 75, 83)}
    KNOWN_EXTRA = {'limoges': 1, 'paris': 0}
    for nm, (ind, s13, s11, s15) in VERIFIER.items():
        g = fr['cadastre'][nm]
        ok = (s13 <= g['with_sale13'] <= s13 + KNOWN_EXTRA[nm] and abs(g['share_sale11'] - 100 * s11 / ind) < 5
              and abs(g['share_sale15'] - 100 * s15 / ind) < 5 and ind <= g['in_dvf'] <= 1.1 * ind)
        check(f'cadastre {nm} vs verifier', ok,
              f"streets without 13 in BAN found in DVF {g['in_dvf']} (verifier {ind}; by code {g['in_dvf_by_code']}, by name {g['in_dvf_by_name']}): "
              f"No.13 on {g['with_sale13']} ({s13}, known extra {KNOWN_EXTRA[nm]}), No.11 on {g['with_sale11']} ({s11}), "
              f"No.15 on {g['with_sale15']} ({s15}); shares 13/11/15 {g['share_sale13']:.1f}/{g['share_sale11']:.1f}/{g['share_sale15']:.1f} % "
              f"vs verifier {100 * s13 / ind:.1f}/{100 * s11 / ind:.1f}/{100 * s15 / ind:.1f} %")
    print(f'Paris 8e: {pa[8]["missing13"]}/{pa[8]["eligible13"]}  excess {pa[8]["excess"]:+.1f}')
    (WORK / 'validation.json').write_text(json.dumps(dict(checks=checks, problems=problems), ensure_ascii=False, indent=1))
    print(f'{len(checks) - len(problems)}/{len(checks)} checks passed')
    return not problems


# ---------------------------------------------------------------- export
def _round(x, digits=3):
    if isinstance(x, dict):
        return {k: _round(v, digits) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, digits) for v in x]
    if isinstance(x, float):
        return None if x != x else round(x, digits)
    return x


AREA_KEYS = ('eligible13', 'missing13', 'r13', 'bg', 'excess', 'lo', 'hi', 'ratio', 'rank13', 'ci')


def _area(r, **meta):
    out = dict(meta)
    out.update({k: r[k] for k in AREA_KEYS if k in r})
    for k in ('addresses', 'q', 'n_streets', 'bis11'):
        if k in r and k not in out:
            out[k] = r[k]
    return out


def hypotheses(fr, ot):
    it, tw = ot['italy'], ot['areas']['tw']
    h = []
    tot = fr['total']
    h.append(dict(id='H1', p=tot['p_gap'], verdict='holds' if tot['gap_lo'] > 0 and tot['rank13'] == 1 else 'does not hold',
                  numbers=dict(r13=tot['r13'], bg=tot['bg'], excess=tot['excess'], lo=tot['lo'], hi=tot['hi'], rank13=tot['rank13'],
                               gap_to_runner_up=tot['gap'], gap_lo=tot['gap_lo'], gap_hi=tot['gap_hi'], share_boot_13_first=tot['p_top'])))
    h2 = fr['H2']['top20']
    h.append(dict(id='H2', p=h2['p'], verdict='holds' if h2['lo'] > 0 else 'does not hold',
                  numbers=dict(big_cities=h2['big']['excess'], rural=h2['rural']['excess'], diff=h2['diff'], lo=h2['lo'], hi=h2['hi'],
                               ge50k_diff=fr['H2']['ge50k']['diff'], ge50k_lo=fr['H2']['ge50k']['lo'], ge50k_hi=fr['H2']['ge50k']['hi'])))
    h3 = fr['H3']
    h.append(dict(id='H3', p=h3['diff']['p'], verdict='holds' if h3['diff']['lo'] > 0 else 'does not hold',
                  numbers=dict(paris_without=h3['paris']['without'], paris_with=h3['paris']['with'], rest_without=h3['rest']['without'],
                               rest_with=h3['rest']['with'], diff=h3['diff']['diff'], lo=h3['diff']['lo'], hi=h3['diff']['hi'])))
    mil, bol, p17 = it['it-milan'], it['it-bologna'], it['pooled17']
    c17 = [x['r17']['lo'] > 0 for x in (mil, bol)]
    c13 = [x['r13']['lo'] > 0 for x in (mil, bol)]
    v4 = 'holds' if all(c17) and not any(c13) else ('mixed' if any(c17) else 'does not hold')
    h.append(dict(id='H4', p=p17['p'], verdict=v4,
                  numbers=dict(milan_excess17=mil['r17']['excess'], milan_lo17=mil['r17']['lo'], milan_excess13=mil['r13']['excess'],
                               milan_lo13=mil['r13']['lo'], bologna_excess17=bol['r17']['excess'], bologna_excess13=bol['r13']['excess'],
                               ticino_excess13=it['ticino']['r13']['excess'], ticino_excess17=it['ticino']['r17']['excess'],
                               pooled_excess17=p17['excess'])))
    fam = tw['fours']['family']
    v5 = 'holds' if fam['lo'] > 0 and tw['excess'] < fam['excess'] else ('mixed' if fam['lo'] > 0 else 'does not hold')
    h.append(dict(id='H5', p=fam['p'], verdict=v5,
                  numbers=dict(family_excess=fam['excess'], family_lo=fam['lo'], family_hi=fam['hi'], excess13=tw['excess'], lo13=tw['lo'],
                               hi13=tw['hi'], eligible13=tw['eligible13'])))
    pr = fr['price']
    uk = ot['uk'].get('price') or {}
    h.append(dict(id='H6', p=pr['p_cheaper'], verdict='holds' if pr['hi'] < 0 else 'does not hold',
                  numbers=dict(france_effect_pct=pr['effect_pct'], france_lo=pr['lo'], france_hi=pr['hi'], n13=pr['n13'],
                               paris_effect_pct=pr['paris']['effect_pct'], uk_effect_pct=uk.get('effect_pct'), uk_lo=uk.get('lo'),
                               uk_hi=uk.get('hi'), uk_n13=uk.get('n13'))))
    ag = fr['age']
    h.append(dict(id='H7', p=ag['p'], verdict='holds' if ag['lo'] > 0 else 'does not hold',
                  numbers=dict(old=ag['old']['excess'], new=ag['new']['excess'], diff=ag['diff'], lo=ag['lo'], hi=ag['hi'],
                               within_department=ag['within_department']['diff'], street_type_diff=ag['street_type'][1]['excess'] - ag['street_type'][0]['excess'],
                               uk_new_builds_excess=ot['uk']['new']['excess'])))
    for x, ph in zip(h, holm([x['p'] for x in h])):
        x['p_holm'] = ph
        x['text'] = HYPOTHESES[x['id']]
    return h


def export():
    if not (WORK / 'validation.json').exists():
        raise SystemExit('run validate first')
    val = json.loads((WORK / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed: run validate and resolve its problems first')
    c = json.loads((WORK / 'computed.json').read_text())
    fr, ot, pool = c['france'], c['others'], c['pool']
    man = json.loads((DATA / 'manifest.json').read_text())
    sources = []
    for s in SOURCES:
        files = source_files(s)
        sources.append(dict(id=s['id'], country=s['country'], publisher=s['publisher'], name=s['name'], url=s['url'], licence=s['licence'],
                            snapshot=s['snapshot'], files_mb=round(sum(man[f]['bytes'] for f in files) / 1e6, 1), n_files=len(files)))
    ar = dict(ot['areas'])
    ar['fr'] = dict(fr['total'], name='France', scope='national', country='FR', addresses=fr['n_addr'], n_streets=fr['n_streets'])
    frc = {x['insee']: x for x in fr['cities']}
    for code, key, nm in (('75056', 'fr-paris', 'Paris'), ('87085', 'fr-limoges', 'Limoges'), ('13055', 'fr-marseille', 'Marseille'),
                          ('69123', 'fr-lyon', 'Lyon'), ('67482', 'fr-strasbourg', 'Strasbourg'), ('06088', 'fr-nice', 'Nice')):
        ar[key] = dict(frc[code], name=nm, scope='city', country='FR')
    lim = next(r for r in fr['regions'] if r.get('former_region'))
    ar['fr-limousin'] = dict(lim, name='Limousin (Corrèze, Creuse, Haute-Vienne)', scope='region', country='FR')
    p8 = next(p for p in fr['paris'] if p['arr'] == 8)
    ar['fr-paris-08'] = dict(p8, name='Paris 8e arrondissement', scope='district', country='FR')
    areas = [_area(ar[k], id=k, country=ar[k]['country'], name=ar[k]['name'], scope=ar[k].get('scope', 'city')) for k in AREA_ORDER]
    ps = [ar[k]['p'] for k in AREA_ORDER]
    for a_, q in zip(areas, bh(ps)):
        a_['q'] = q
    cities = []
    for x in fr['cities']:
        if x['eligible13'] >= 150:
            cities.append(dict(x, id=x['id'], country='FR'))
    cities += [x for x in ot['cities'] if x['eligible13'] >= 150]
    cities = [_area(x, id=x['id'], country=x['country'], name=x['name']) for x in cities]
    for x, q in zip(cities, bh([norm_sf(x['excess'] / ((x['hi'] - x['lo']) / 3.92)) if x['hi'] > x['lo'] else float('nan') for x in cities])):
        x['q'] = q
    cities = [{k: x[k] for k in ('id', 'country', 'name', 'eligible13', 'missing13', 'r13', 'bg', 'excess', 'lo', 'hi', 'rank13', 'q')}
              for x in sorted(cities, key=lambda x: -x['excess'])]
    # pooled profile and totals
    pa = [0] * len(ODD)
    pb = [0] * len(ODD)
    tot_addr = fr['n_addr']
    tot_streets = fr['n_streets']
    for k, (a, b, na, ns) in pool.items():
        pa = [x + y for x, y in zip(pa, a)]
        pb = [x + y for x, y in zip(pb, b)]
        tot_addr += na
        tot_streets += ns
    pa = [x + y for x, y in zip(pa, fr['total']['a'])]
    pb = [x + y for x, y in zip(pb, fr['total']['b'])]
    # Czech address points carry a house number (č.p.) and only some an orientation number on a street: count them once, all
    # registers only: the England and Wales sales and the Singapore blocks are not address registers, kept apart
    tot_addr += ar['us']['addresses'] + ot['consecutive_cz']['addresses'] - pool['cz'][2]
    tot_streets += ar['us']['n_streets']
    pst = stats(pa, pb)
    pooled = dict(r13=float(pst['r13']), bg=float(pst['bg']), excess=float(pst['excess']), rank13=int(pst['rank']), eligible13=pb[I13],
                  missing13=pa[I13], areas=['fr'] + list(pool))
    sw = ot['switzerland']
    deps = [dict(code=d['code'], name=d['name'], eligible13=d['eligible13'], missing13=d['missing13'], r13=d['r13'], bg=d['bg'],
                 excess=d['excess'], lo=d['lo'], hi=d['hi'], q=d['q'], shrunk=d['shrunk'], rank13=d['rank13']) for d in fr['departments']]
    pr = fr['price']
    italy = {}
    for k, nm in (('it-milan', 'milan'), ('it-bologna', 'bologna'), ('it-milan-nocarrai', 'milan_no_driveways')):
        x = ot['italy'][k]
        italy[nm] = dict(r13=x['r13']['r13'], bg13=x['r13']['bg'], excess13=x['r13']['excess'], lo13=x['r13']['lo'], hi13=x['r13']['hi'],
                         rank13=x['r13']['rank13'], eligible13=x['r13']['eligible13'], r17=x['r17']['r13'], bg17=x['r17']['bg'],
                         excess17=x['r17']['excess'], lo17=x['r17']['lo'], hi17=x['r17']['hi'], rank17=x['r17']['rank13'],
                         eligible17=x['r17']['eligible13'])
    ti = ot['italy']['ticino']
    italy['ticino'] = dict(r13=ti['r13']['r13'], bg13=ti['r13']['bg'], excess13=ti['r13']['excess'], lo13=ti['r13']['lo'], hi13=ti['r13']['hi'],
                           eligible13=ti['r13']['eligible13'], r17=ti['r17']['r13'], bg17=ti['r17']['bg'], excess17=ti['r17']['excess'],
                           lo17=ti['r17']['lo'], hi17=ti['r17']['hi'], eligible17=ti['r17']['eligible13'])
    italy['pooled17'] = dict(excess17=ot['italy']['pooled17']['excess'], lo17=ot['italy']['pooled17']['lo'], hi17=ot['italy']['pooled17']['hi'])
    tw = ot['areas']['tw']
    uk = ot['uk']
    cz, sg = ot['consecutive_cz'], ot['consecutive_sg']
    czs = stats(cz['a'], cz['b'], CONSEC.index(13))
    sgs = stats(sg['a'], sg['b'], CONSEC.index(13))
    hy = hypotheses(fr, ot)
    J = dict(
        slug=SLUG,
        sources=sources,
        totals=dict(addresses=tot_addr, streets=tot_streets, eligible_13=pb[I13], uk_sales=ot['uk']['addresses'],
                    sg_blocks=ot['consecutive_sg']['blocks']),
        profile=dict(numbers=ODD, france=fr['profile'], switzerland=sw['profile'], pooled=[100 * a / b for a, b in zip(pa, pb)]),
        pooled=pooled,
        areas=areas,
        cities=cities,
        france=dict(
            total=dict(_area(fr['total']), addresses=fr['n_addr'], streets=fr['n_streets'], gap=fr['total']['gap'], gap_lo=fr['total']['gap_lo'],
                       gap_hi=fr['total']['gap_hi'], share_boot_13_first=fr['total']['p_top'],
                       robustness={k: (dict(excess=v['excess'], lo=v.get('lo'), hi=v.get('hi'), rank13=v.get('rank13'), eligible13=v.get('eligible13'))
                                       if isinstance(v, dict) and 'excess' in v else v) for k, v in fr['robustness'].items()},
                       controls=dict(even={k: v for k, v in fr['control_even'].items()}, n1xx=fr['control_1xx'], c113=fr['control_113'],
                                     fours=fr['control_fours'])),
            departments=deps,
            departments_summary=dict(n=len(deps), positive=sum(d['excess'] > 0 for d in deps), sig_bh=sum((d['q'] or 1) < 0.05 for d in deps),
                                     sig_holm=sum((d['p_holm'] or 1) < 0.05 for d in fr['departments']),
                                     rank1=sum(d['rank13'] == 1 for d in deps)),
            regions=[dict(name=r['name'], eligible13=r['eligible13'], r13=r['r13'], bg=r['bg'], excess=r['excess'], lo=r['lo'], hi=r['hi'],
                          q=r['q'], rank13=r['rank13']) for r in fr['regions']],
            paris=[dict(arr=p['arr'], eligible13=p['eligible13'], missing13=p['missing13'], r13=p['r13'], bg=p['bg'], excess=p['excess'],
                        lo=p['lo'], hi=p['hi'], q=p['q'], rank13=p['rank13']) for p in fr['paris']],
            communes_all_missing=sorted(fr['communes_all_missing'], key=lambda x: -x['eligible13']),
            communes=dict(with_ge10_eligible=fr['communes_ge10'], half_or_more_missing=fr['communes_ge50pct'], tested=fr['communes_tested'],
                          sig_bh=fr['communes_sig_bh']),
            size_classes=[dict(size_class=s['size_class'], n_cities=s.get('n_clusters'), eligible13=s['eligible13'], r13=s['r13'], bg=s['bg'],
                               excess=s['excess'], lo=s['lo'], hi=s['hi'], rank13=s['rank13']) for s in fr['size_classes']],
            h2=fr['H2'],
            bis=dict(paris=fr['H3']['paris'], rest=fr['H3']['rest'], diff=fr['H3']['diff']),
            age=dict(groups=[dict(group=g['group'], eligible13=g['eligible13'], r13=g['r13'], bg=g['bg'], excess=g['excess'], lo=g['lo'], hi=g['hi'])
                             for g in fr['age']['groups']],
                     new_minus_old=dict(diff=fr['age']['diff'], lo=fr['age']['lo'], hi=fr['age']['hi']),
                     within_department=fr['age']['within_department'],
                     street_type=[dict(group=g['group'], eligible13=g['eligible13'], excess=g['excess'], lo=g['lo'], hi=g['hi']) for g in fr['age']['street_type']],
                     provenance=[dict(group=g['group'], eligible13=g['eligible13'], excess=g['excess'], lo=g['lo'], hi=g['hi']) for g in fr['age']['provenance']],
                     topo_match_share=fr['topo_match_share'], note='TOPO date = creation of the street record (initial load 1987-88), not construction'),
            price=dict(n_sales=pr['n_sales'], n13=pr['n13'], effect_pct=pr['effect_pct'], lo=pr['lo'], hi=pr['hi'], p_cheaper=pr['p_cheaper'],
                       rank_cheapest=pr['rank_cheapest'], of=pr['of'], placebo_sd=pr['placebo_sd'],
                       paris=pr['paris'], rest=pr['rest'], apartments=pr['apartments'], houses=pr['houses'],
                       by_number=[dict(n=r['n'], effect_pct=r['effect_pct'], lo=r['lo'], hi=r['hi'], n_at=r['n_at']) for r in pr['by_number']],
                       sales_by_number=pr['sales_by_number'],
                       note='DVF 2021-2025, single-dwelling sales, price per m2, street x dwelling-type fixed effects; no 57, 67, 68, 976'),
            cadastre=dict({k: v for k, v in fr['cadastre'].items() if k != 'qa'},
                          note='A11, added after the count: BAN streets eligible for 13 joined to DVF 2021-2025 by FANTOIR code '
                               '(name within the commune for BAN streets without one); "with_saleN" = streets with at least one DVF '
                               'mutation at No.N, among the streets found in DVF (in_dvf)'),
            map=fr['map']),
        switzerland=dict(total=_area(sw['total']), cantons=[_area(x, code=x['code']) for x in sw['cantons']],
                         languages=[_area(x, lang=x['lang'], n_communes=x['n_communes']) for x in sw['languages']],
                         cities=[_area(x, name=x['name'], code=x['code']) for x in sw['cities']]),
        italy=italy,
        taiwan=dict(district='Songshan (松山區), Taipei', r13=tw['r13'], bg=tw['bg'], excess=tw['excess'], lo=tw['lo'], hi=tw['hi'],
                    eligible13=tw['eligible13'], missing13=tw['missing13'],
                    fours=[dict(n=x['n'], r=x['r'], bg=tw['fours']['bg'], excess=x['excess'], lo=x['lo'], hi=x['hi'], eligible=x['eligible'])
                           for x in tw['fours']['numbers']], family=tw['fours']['family'],
                    note='one district: the city file holds only Songshan; lane numbers count as present on the parent street'),
        fours_elsewhere={k: dict(family=ot['areas'][k]['fours']['family'], bg=ot['areas'][k]['fours']['bg']) for k in ('us', 'ru', 'nl')} |
                       {'fr': dict(family=fr['control_fours']['family'], bg=fr['control_fours']['bg'])},
        uk_new_builds=dict(streets=uk['new']['eligible13'], missing13=uk['new']['missing13'], r13=uk['new']['r13'], bg=uk['new']['bg'],
                           excess=uk['new']['excess'], lo=uk['new']['lo'], hi=uk['new']['hi'], rank13=uk['new']['rank13'],
                           price=({k: uk['price'][k] for k in ('effect_pct', 'lo', 'hi', 'n13', 'n_sales', 'n_streets')} if uk.get('price') else None),
                           note='Price Paid 2024 is a register of sales: "no sale of a new No.13 in 2024", not "no house No.13"'),
        consecutive=dict(czech_cp=dict(r13=float(czs['r13']), bg=float(czs['bg']), excess=float(czs['excess']), rank13=int(czs['rank']),
                                       of=len(CONSEC), eligible13=cz['b'][CONSEC.index(13)]),
                         singapore=dict(r13=float(sgs['r13']), bg=float(sgs['bg']), excess=float(sgs['excess']),
                                        eligible13=sg['b'][CONSEC.index(13)], last_digit=sg['last_digit'], blocks=sg['blocks']),
                         note='consecutive numbering, neighbours N-2, N-1, N+1, N+2; background = all other numbers 5..43'),
        hypotheses=[dict(id=x['id'], text=x['text'], verdict=x['verdict'], p=x['p'], p_holm=x['p_holm'], numbers=x['numbers']) for x in hy],
        added_after_count=ADDED_AFTER_COUNT,
        validation=dict(passed=sum(c_['ok'] for c_ in val['checks']), total=len(val['checks']),
                        checks=[c_ for c_ in val['checks'] if not c_['name'].startswith('manifest')],
                        files={f: m['sha256'] for f, m in man.items() if not f.startswith('fr/') and not f.startswith('pl/')}
                        | {'fr/*': hashlib.sha256(''.join(man[f]['sha256'] for f in sorted(man) if f.startswith('fr/')).encode()).hexdigest(),
                           'pl/*': hashlib.sha256(''.join(man[f]['sha256'] for f in sorted(man) if f.startswith('pl/')).encode()).hexdigest()}),
    )
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(_round(J), ensure_ascii=False, separators=(',', ':')) + '\n')

    rows = []

    def add(atype, country, aid, name, a, b, Ns, source):
        for N, x, y in zip(Ns, a, b):
            rows.append([atype, country, aid, name, N, int(y), int(x), round(100 * x / y, 3) if y else '', source])
    add('national', 'FR', 'fr', 'France', fr['total']['a'], fr['total']['b'], ODD, 'ban')
    for d in fr['departments']:
        add('department', 'FR', 'fr-' + d['code'], d['name'], d['a'], d['b'], ODD, 'ban')
    for r in fr['regions']:
        add('region', 'FR', 'fr-reg-' + re.sub(r'[^a-z]+', '-', unicodedata.normalize('NFKD', r['name']).encode('ascii', 'ignore').decode().lower()).strip('-'), r['name'], r['a'], r['b'], ODD, 'ban')
    for p in fr['paris']:
        add('district', 'FR', 'fr-' + p['insee'], f"Paris {p['arr']}e", p['a'], p['b'], ODD, 'ban')
    src_of = {'de': 'nrw', 'ch': 'ch', 'lt': 'lt', 'cz': 'cz', 'no': 'no', 'nrw': 'nrw', 'pl': 'pl', 'nl': 'nl', 'be': 'be', 'fi': 'fi', 'es': 'es',
              'it-milan': 'it-mi', 'it-bologna': 'it-bo', 'ru': 'ru', 'us': 'us', 'tw': 'tw'}
    for k in AREA_ORDER:
        if k == 'fr' or k.startswith('fr-'):
            continue
        x = ar[k]
        add(x.get('scope', 'city'), x['country'], k, x['name'], x['a'], x['b'], ODD, src_of.get(k, src_of.get(k.split('-')[0], k.split('-')[0])))
    for x in sw['cantons']:
        add('canton', 'CH', 'ch-' + x['code'], x['code'], x['a'], x['b'], ODD, 'ch')
    for x in sw['languages']:
        add('language area', 'CH', 'ch-lang-' + x['lang'], x['lang'], x['a'], x['b'], ODD, 'ch')
    done = {(ar[k]['country'], ar[k]['name']) for k in AREA_ORDER if not k.startswith('fr')}
    for x in fr['cities'] + ot['cities']:
        if x['eligible13'] >= 150 and x['id'] not in AREA_ORDER and (x['country'], x['name']) not in done:
            add('city', x['country'], x['id'], x['name'], x['a'], x['b'], ODD, {'FR': 'ban', 'CH': 'ch', 'CZ': 'cz', 'NO': 'no', 'DE': 'nrw',
                                                                                  'PL': 'pl', 'LT': 'lt'}.get(x['country'], x['id']))
    tw4 = ot['areas']['tw']['fours']
    for x in tw4['numbers']:
        rows.append(['district (scheme N-2, N+2, N+4)', 'TW', 'tw', 'Taipei, Songshan', x['n'], x['eligible'], x['missing'], round(x['r'], 3), 'tw'])
    add('sales: new builds 2024', 'GB', 'uk-new', 'England and Wales, new builds', uk['new']['a'], uk['new']['b'], ODD, 'uk')
    add('consecutive', 'CZ', 'cz-cp', 'Czechia, house numbers (č.p.)', cz['a'], cz['b'], CONSEC, 'cz')
    add('consecutive', 'SG', 'sg-hdb', 'Singapore HDB blocks', sg['a'], sg['b'], CONSEC, 'sg')
    for r in pr['by_number']:
        rows.append(['price effect (DVF, %)', 'FR', 'fr-dvf', 'France, No.N vs odd neighbours, % per m2', r['n'], r['n_sales'], r['n_at'],
                     round(r['effect_pct'], 3), 'dvf'])
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['area_type', 'country', 'area_id', 'area_name', 'number', 'eligible_streets', 'missing', 'share_pct', 'source'])
        w.writerows(rows)
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB, {len(rows)} rows)' +
        (f', {SCRIPT_COPY}' if SCRIPT_COPY else ''))


if __name__ == '__main__':
    steps = {'fetch': fetch, 'compute': compute, 'validate': validate, 'export': export}
    arg = sys.argv[1] if len(sys.argv) == 2 else ''
    if arg.startswith('fetch-') and arg[6:] in SRC:
        fetch(arg[6:])
        sys.exit(0)
    if arg not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}|fetch-<{",".join(SRC)}>')
    ok = steps[arg]()
    sys.exit(1 if ok is False else 0)
