#!/usr/bin/env python3
"""The Fire Horse and the birth register: Japan 1966, Japan 2026 and the zodiac in official birth series.

Source of the numbers on https://startarot.online/research/fire-horse-japan-births

Needs Python 3.10+ and
    pip install numpy pandas xlrd
plus ``pdftotext`` (poppler: ``brew install poppler`` / ``apt install poppler-utils``) and ``curl``. The raw files
(about 140 MB, 120 of them two scanned yearbooks) go to $FIRE_HORSE_DATA (default ~/startarot-data/eastern-zodiac-births).
Steps, in order:

    python3 fire_horse_births.py fetch      # what is missing is downloaded; prints URL and SHA-256 of every file
    python3 fire_horse_births.py compute    # everything below -> $FIRE_HORSE_DATA/computed.json
    python3 fire_horse_births.py validate   # sums, printed ratios, two readings of the scans, annual against monthly
    python3 fire_horse_births.py export     # page JSON + dataset CSV (+ a copy of this script); refuses if validate failed

Run from the repo, export writes (GENERATED: regenerate, do not hand-edit):
    frontend/src/lib/research/fire-horse-births.json   data the page renders
    frontend/static/research/fire-horse-births.csv     the open dataset (long format)
    frontend/static/research/fire_horse_births.py      a copy of this script
A copy downloaded from the page writes the JSON and CSV next to itself.

Sources (detail, licence and the attribution each requires: SOURCES below, printed into the JSON)
-----------------------------------------------------------------------------------------------
Downloadable by command (``fetch``): e-Stat tables 4.1 and 4.2 (Japan annual and monthly, Japanese in Japan), the scanned
Vital Statistics 1966 and 1967 yearbooks (e-Stat), MHLW monthly reports 2026, SingStat M810051, C&SD 115-01012A and
115-01012, Taiwan's Department of Household Registration (session cookie, then GET; a first request sometimes returns an
HTML error page, ``fetch`` retries), DOSM births by ethnicity, Hong Kong Observatory calendars (Lunar New Year dates).

NOT downloadable by command: KOSIS. Its data endpoint answers only inside a session opened by the table page, and a
replay of the request from curl returns an error, so the two series were read in a browser and saved as CSV:
    1. open https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B8000G (monthly; DT_1B8000F for annual);
    2. from the frame statHtmlContent.do take the form ParamInfo and POST it to /statHtml/html.do with fieldList set to
       PRD "M,<all months 198101..202608>,@" (annual: "Y,<1970..2025>,@"), ITM_ID T1, OV_L1_ID 00 (whole country) and, for
       the monthly table, OV_L2_ID 10 (births); annual keeps its default OV_L1_ID list and takes the row 출생아수(명);
    3. the response's "result" is an HTML table: 1981.01.. in the header, value and weight cells alternate in the row.
Saved as kr_kosis_DT_1B8000G_monthly.csv and kr_kosis_DT_1B8000F_annual.csv, accessed 2026-11-02.

Scans. The yearbooks are images. Numbers read from them are constants below, each with its table and printed page:
    Vital Statistics 1966 vol.1 (jin1966a.pdf): table 3.4 (p.52, file page 29), text pp.68-69 (file 37), tables 3.23-3.24
    (pp.70-71, file 38), 3.25-3.26 (pp.72-73, file 39), 3.27-3.30 (pp.74-75, file 40).
    Vital Statistics 1967 vol.1 (jin1967a.pdf): table 4.3 (p.54, file 30), table 4 (pp.276-279, files 141-142).
Tables 3.24-3.27 were read twice, independently (DAILY and DAILY_SECOND_READING; validate compares them), then checked by
arithmetic and against the ratios printed in table 3.23. By eye, the second reading at 300 dpi; no OCR. Tables 3.4, 3.23,
3.28-3.30 and 4 and the text were read once, at 200-300 dpi, and checked by sums or against e-Stat where a check exists.
The report's text calls the daily tables 届出日別 (by date as notified) and speaks of avoiding the notification of girls, so
these are dates written on forms, not observed births.

Method
------
Fixed before the first full run, and listed here with what was NOT blind: before that run the author had already seen the
Singapore numbers of an earlier pass, Japan's 1966 annual total and the 1966 report's own text and tables, and the
Dragon, Tiger, Horse and Goat were chosen because folklore names them. Everything on the 1966 report is therefore
description of an official document, not a test. HK without mainland mothers, the COVID and window variants, the 1906
count, the whole-year check on displaced girls and the net of Japan were added after the first results.

Calendar: Japan's eto runs on the Gregorian year. Everywhere else the lunar year starts at Lunar New Year (LUNAR_NEW_YEAR,
validated against the Hong Kong Observatory tables). Malaysia and the older parts of other series exist only by Gregorian
year, so January births of a Dragon year are counted as Dragons there.

A. Year effect (``year_effect``). Log births per day of the year, minus a straight line fitted over the clean years within
   +-6 (the 8 animals outside Tiger, Dragon, Horse, Goat; needs >=5 of them, on both sides; the year itself never in), so
   no target year is ever in another's base. Japan: 1965-1967 also out of every base. Placebo: same statistic for every
   clean year. Interval: mean +- 1.96 * SD_placebo / sqrt(n). Range: placebo p5..p95. All cells form one
   Benjamini-Hochberg family, z = mean / (SD_placebo / sqrt(n)).
B. Boundary step (``boundary_table``). Monthly series only. Log births per day, deseasonalised (ratio to centred 2x12 MA,
   median by month within +-8 years). Step = mean of the 6 months after the Lunar New Year month minus the 6 before; that
   month is dropped. Placebo: same step at real boundaries between clean years and at fake boundaries (3..9 months after
   Lunar New Year) inside runs of clean years.
C. Ethnic control. Series A applied to log(Chinese) - log(controls): Singapore Malays + Indians, Malaysia bumi_malay +
   indian. Year shocks common to both cancel; the local line handles differing pretrends. Controls alone also go through A.
D. Displaced girls (``displaced``). Own count, day by day and month by month, in the four months of tables 3.24-3.27:
   girls_expected = boys / (norm / 100), deviation = girls - expected, norm 105 with range 104-106. ASSUMES boys' dates are
   unaffected by the superstition and any other New Year shift of dates is equal for both sexes. That assumption is partly
   visible and cannot be proved: boys also pile up on 1 January 1967 (4,236 against about 3,050 on later days) and are few
   on 31 December of both years, so a sex-neutral New Year custom exists on top, and no ordinary year is in these tables
   to measure it. Totals by day are therefore NOT evidence of the superstition alone; the ratio is.

Descriptive only, no test behind it: everything from the 1966 report; 1906; ``find_your_year`` (each year against the mean
of its 2+2 neighbours: a Tiger has a Dragon among its neighbours and the other way round, which is exactly why A uses a
clean base; ``clean_pct`` there is the A figure); ``japan_net`` (depends on the base years, three printed).

Known facts a reader of the numbers must keep:
* Tables 3.24-3.27 are a special tabulation and their month totals are 0.7-0.9 % below the monthly table in the same report
  (e.g. December 1966: 133,102 against 134,327). The report does not explain the gap; ``checks`` prints it.
* The ministry's "8-10 thousand" is its own figure from those four months. The whole-year sex ratio of 1966 (107.6) with a
  105.3 norm gives more; ``displaced.annual_check`` prints it, with February-November at 106.2: not explained here.
* Reported abortions fell in 1966 (843,248 -> 808,378, Eugenic Protection statistics). Reported abortions may undercount;
  this says what the ministry concluded, not that the question is closed.
* Japan 2024-2026 preliminary figures include foreigners in Japan and Japanese abroad; Japanese-only figures end in May 2026.
* Hong Kong 2001-2012 carries births to mainland mothers (table 115-01012), ended by policy in 2013: series "HK excl." drops
  those whose spouse is not a permanent resident. HK 2003 coincides with SARS.
* Taiwan's monthly series is by REGISTRATION date (up to 60 days late), which smears its boundary steps. Korea's January and
  February of the 1980s-90s are visibly swollen. Malaysia has two Dragons with a base (2000 opens the series), and 2024 alone
  is fragile: Chinese births flat on 2023 (a rebound year) while Malays fell 10.7 %. The fall after each Dragon is plainer:
  ``my_dragon_exit``, year on year, descriptive.
* Korea 1990: the sex ratio at birth (116.5, KOSTAT release) is NOT in this script's data: the release was seen only as a
  search excerpt, and the count of births shows nothing for that Horse.

Could not be collected: China (NBS answers 403 outside China), Macao (only recent quarterly bulletins found), Malaysia
monthly by ethnicity and before 2000, Taiwan monthly before 1998 (query system returns an empty page, DGBAS yearbook 403),
Chinese abroad (not searched). Japan's final 2026 data arrive in February and June 2027.

Licences: see SOURCES. SingStat's raw monthly series is NOT in the CSV: the Singapore Open Data Licence allows reuse with a
notice but gives no rights downstream, so it cannot be passed on under CC BY; the CSV carries only lunar-year aggregates
with that notice. C&SD and KOSIS allow redistribution on their own terms, not CC BY. So a CC BY line on the page must cover
our calculations and the Japanese, Taiwanese and Malaysian series, and say the Singapore, Hong Kong and Korean rows stay
under their owners' terms. The CSV's rows series=_attribution carry the required credit for every source.
"""
import calendar
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from math import erfc, sqrt
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
FILE_STEM = 'fire-horse-births'
if (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir():
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'fire_horse_births.py'
else:
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
DATA = Path(os.environ.get('FIRE_HORSE_DATA', Path.home() / 'startarot-data' / 'eastern-zodiac-births'))
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120 Safari/537.36'
ACCESSED = '2026-11-02'

ESTAT = 'https://www.e-stat.go.jp/stat-search/file-download?statInfId={}&fileKind={}'
MHLW = 'https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/'
TW_PANEL = 'https://www.ris.gov.tw/info-popudata/app/awFastDownload/toMain_panel'
TW_VIEW = 'https://www.ris.gov.tw/info-popudata/app/awFastDownload/view'
FILES = {  # local name -> url
    'sg_M810051.json': 'https://tablebuilder.singstat.gov.sg/api/table/tabledata/M810051',
    'hk_115_01012A.json': 'https://www.censtatd.gov.hk/api/get.php?id=115-01012A&lang=en&full_series=1',
    'hk_115_01012.json': 'https://www.censtatd.gov.hk/api/get.php?id=115-01012&lang=en&full_series=1',
    'my_birth_sex_ethnic.csv': 'https://storage.dosm.gov.my/demography/birth_sex_ethnic.csv',
    'jp_annual_4_1.bin': ESTAT.format('000040503640', 1),
    'jp_est_000040503641.bin': ESTAT.format('000040503641', 1),
    'jp_reports/jin1966a.pdf': ESTAT.format('000031845546', 2),
    'jp_reports/jin1967a.pdf': ESTAT.format('000031845514', 2),
    'jp_202608.xlsx': MHLW + 's2026/xls/202608.xlsx',
    'jp_202608.pdf': MHLW + 's2026/dl/202608.pdf',
    'jp_m2026_toukeihyo05.pdf': MHLW + 'm2026/dl/toukeihyo_05.pdf',
}
PINNED_SHA256 = {  # images of printed books: these must never change
    'jp_reports/jin1966a.pdf': '42d4492020096692c065bef413894ab79bd331dfc36e11796098c7ba742631ff',
    'jp_reports/jin1967a.pdf': '9344391f7ee62520ed8d3053f1eb8f2fd61037fe9ca2f5abdf8f1012002bffc6',
}
# Monthly reports (gaisu): Japanese in Japan, with sex. The Fire Horse's entry boundary (December 2025, January 2026) is here.
GAISU_MONTHS = [(y, m) for y in (2024, 2025, 2026) for m in range(1, 13) if (2024, 8) <= (y, m) <= (2026, 5)]
FILES |= {f'jp_gaisu/g{y}_{m:02d}.pdf': f'https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/m{y}/dl/toukeihyo_{m:02d}.pdf'
          for y, m in GAISU_MONTHS}
MANUAL = {'kr_kosis_DT_1B8000G_monthly.csv': 'https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B8000G',
          'kr_kosis_DT_1B8000F_annual.csv': 'https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B8000F'}
TW_FILES = {'tw/y2s1.xls': ('y2s1', '')} | {f'tw/m1s5_{y:03d}00.xls': ('m1s5', f'{y:03d}00') for y in range(87, 116)}
HKO = {f'hko/T{y}e.txt': f'https://www.hko.gov.hk/en/gts/time/calendar/text/files/T{y}e.txt' for y in range(1960, 2028)}

SOURCES = [
    dict(id='jp_estat', name='Vital Statistics, tables 4.1 and 4.2 (annual 1899-2025; months of selected years); Vital Statistics 1966 and 1967 yearbooks (scans)',
         publisher='Ministry of Health, Labour and Welfare, via e-Stat', url='https://www.e-stat.go.jp/stat-search/files?toukei=00450011',
         licence='e-Stat terms of use: numeric data and simple tables are outside copyright and free to use; the rest allows reproduction, adaptation and commercial use and is stated to be compatible with CC BY 4.0',
         licence_url='https://www.e-stat.go.jp/terms-of-use', cc_by_derived=True, cc_by_raw=True, raw_in_csv=True,
         attribution='Source: Portal Site of Official Statistics of Japan (e-Stat), https://www.e-stat.go.jp/ ; Vital Statistics (Ministry of Health, Labour and Welfare), processed by StarTarot. 出典：政府統計の総合窓口(e-Stat)（https://www.e-stat.go.jp/）「人口動態統計」（厚生労働省）を加工して作成',
         restrictions='Do not present processed figures as the government\'s own.'),
    dict(id='jp_mhlw', name='Monthly preliminary report 2026-08; monthly report (Japanese only) 2026-05', publisher='Ministry of Health, Labour and Welfare',
         url=MHLW + 's2026/08.html', licence='Public Data License 1.0 (PDL1.0), which states compatibility with CC BY 4.0', licence_url='https://www.mhlw.go.jp/chosakuken/index.html',
         cc_by_derived=True, cc_by_raw=True, raw_in_csv=True,
         attribution=f'Source: Ministry of Health, Labour and Welfare website, {MHLW}s2026/08.html (accessed {ACCESSED}); processed by StarTarot. 出典：「人口動態統計速報」「人口動態統計月報（概数）」（厚生労働省）を加工して作成',
         restrictions='Do not present processed figures as the government\'s own. Logos excluded.'),
    dict(id='sg_singstat', name='Live-Births By Sex And Ethnic Group, Monthly (M810051)', publisher='Singapore Department of Statistics',
         url=FILES['sg_M810051.json'], licence='SingStat Terms of Use, under which the Singapore Open Data Licence v1.0 prevails: use, distribute, modify and adapt, also commercially, with a notice; sub-licensing only as needed to use your site, no rights for downstream sub-licensees; the Terms make the right revocable',
         licence_url='https://www.singstat.gov.sg/terms-of-use', cc_by_derived=False, cc_by_raw=False, raw_in_csv=False,
         attribution=f'Contains information from Live-Births By Sex And Ethnic Group, Monthly (M810051) accessed on {ACCESSED} from the Singapore Department of Statistics, which is made available under the terms of the Singapore Open Data Licence version 1.0, https://data.gov.sg/open-data-licence . Aggregated to lunar years by StarTarot; not attributed to or endorsed by the Government.',
         restrictions='Raw monthly series kept out of the CSV: it cannot be passed on under CC BY. The licence is silent on relicensing derived data, so derived rows carry this notice and stay outside the CC BY line. Remove on request, per the Terms.'),
    dict(id='hk_csd', name='Tables 115-01012A (monthly number of live births by sex) and 115-01012 (live births to Mainland women)', publisher='Census and Statistics Department, Hong Kong',
         url='https://www.censtatd.gov.hk/en/web_table.html?id=115-01012A', licence='C&SD Important Notices: Statistical Information may be downloaded, adapted, distributed and reproduced free of charge, also commercially, with credit; other uses need written consent; sub-licensing not addressed. DATA.GOV.HK terms: same, with credit',
         licence_url='https://www.censtatd.gov.hk/en/page_31.html', cc_by_derived=False, cc_by_raw=False, raw_in_csv=True,
         attribution='Source: website of the Census and Statistics Department, Hong Kong (https://www.censtatd.gov.hk/), and DATA.GOV.HK. Intellectual property rights: Government of the Hong Kong Special Administrative Region. Modified by StarTarot where marked (net of births to mainland mothers).',
         restrictions='The credit must follow into any subsequent copy and modifications must be flagged: not the same as CC BY, so these rows stay outside the CC BY line.'),
    dict(id='kr_kosis', name='월.분기.연간 인구동향(출생,사망,혼인,이혼) DT_1B8000G; 인구동태건수 및 동태율 추이 DT_1B8000F', publisher='국가데이터처 (Ministry of Data and Statistics, Korea), 인구동향조사',
         url=MANUAL['kr_kosis_DT_1B8000G_monthly.csv'], licence='KOSIS use guide: statistics may be freely reused and redistributed, also commercially; selling a table unchanged for money is banned; figures and their meaning must not be altered. International and North Korean statistics excluded (not used here)',
         licence_url='https://stat.kosis.kr/nsistN/kosisUseGuide.do', cc_by_derived=True, cc_by_raw=False, raw_in_csv=True,
         attribution=f'국가데이터처, 「인구동향조사」, 월.분기.연간 인구동향 (2026-10-28 갱신) and 인구동태건수 및 동태율 추이 (2026-09-22 갱신), KOSIS, https://kosis.kr/statHtml/statHtml.do?orgId=101&tblId=DT_1B8000G , 2026.11.02.',
         restrictions='Required fields: agency, survey, compilation date, access date, table title, URL. Not stated as CC BY; raw rows stay under KOSIS terms.'),
    dict(id='tw_ris', name='出生數及粗出生率 (y2s1); 縣市出生死亡結婚離婚(按登記) (m1s5)', publisher='Department of Household Registration, Ministry of the Interior, Taiwan',
         url=TW_PANEL, licence='Open Government Data License, version 1.0: reuse and sub-license for any purpose; following CC BY 4.0 also satisfies it', licence_url='https://data.gov.tw/license',
         cc_by_derived=True, cc_by_raw=True, raw_in_csv=True,
         attribution='Department of Household Registration, Ministry of the Interior (Taiwan), 2026, 出生數及粗出生率 and 縣市出生死亡結婚離婚; Open Government Data License, version 1.0, https://data.gov.tw/license',
         restrictions='Without the notice the licence counts as never granted. No implied endorsement; do not alter so as to contradict the original.'),
    dict(id='my_dosm', name='Annual Live Births by Sex & Ethnicity', publisher='National Registration Department and Department of Statistics Malaysia (OpenDOSM)',
         url='https://open.dosm.gov.my/data-catalogue/births_annual_sex_ethnic', licence='CC BY 4.0', licence_url='https://creativecommons.org/licenses/by/4.0/',
         cc_by_derived=True, cc_by_raw=True, raw_in_csv=True, attribution='Department of Statistics Malaysia (OpenDOSM), Annual Live Births by Sex & Ethnicity, CC BY 4.0. Calculations by StarTarot.',
         restrictions='DOSM notes that 2010-2019 will be revised.'),
    dict(id='calc', name='Calculations in fire_horse_births.py', publisher='StarTarot', url='https://startarot.online/research/fire-horse-japan-births', licence='CC BY 4.0, except rows derived from sg_singstat', licence_url='https://creativecommons.org/licenses/by/4.0/',
         cc_by_derived=True, cc_by_raw=True, raw_in_csv=True, attribution='StarTarot, https://startarot.online/research/fire-horse-japan-births', restrictions=''),
]

# ---------------------------------------------------------------- numbers from the scanned yearbooks
# Vital Statistics 1966 vol.1, tables 3.24 (p.71), 3.25 (p.72), 3.26 (p.73), 3.27 (p.74): births by stated date of birth.
# (total, boys, girls). "span" is the printed row 1-20 or 21-31.
DAILY = {
    '1965-12': dict(table='3.24', page=71, month=(143576, 72067, 71509), span=('1-20', 91790, 47093, 44697), days={
        21: (5133, 2705, 2428), 22: (4860, 2468, 2392), 23: (4956, 2542, 2414), 24: (4600, 2355, 2245), 25: (4667, 2346, 2321), 26: (4048, 2065, 1983),
        27: (4354, 2183, 2171), 28: (4935, 2485, 2450), 29: (4260, 2096, 2164), 30: (5285, 2068, 3217), 31: (4688, 1661, 3027)}),
    '1966-01': dict(table='3.25', page=72, month=(121967, 64084, 57883), span=('21-31', 44735, 22799, 21936), days={
        1: (3696, 2366, 1330), 2: (3042, 1801, 1241), 3: (3397, 1924, 1473), 4: (3388, 1921, 1467), 5: (3873, 2128, 1745), 6: (3786, 2079, 1707), 7: (3909, 2125, 1784),
        8: (3856, 2058, 1798), 9: (3300, 1716, 1584), 10: (3924, 2056, 1868), 11: (4345, 2213, 2132), 12: (4211, 2217, 1994), 13: (3969, 1984, 1985), 14: (4011, 2076, 1935),
        15: (4200, 2193, 2007), 16: (3615, 1851, 1764), 17: (4018, 2081, 1937), 18: (4443, 2289, 2154), 19: (4059, 2081, 1978), 20: (4190, 2126, 2064)}),
    '1966-12': dict(table='3.26', page=73, month=(133102, 71825, 61277), span=('1-20', 88670, 46164, 42506), days={
        21: (4651, 2491, 2160), 22: (4559, 2456, 2103), 23: (4701, 2593, 2108), 24: (4511, 2488, 2023), 25: (4232, 2411, 1821), 26: (4338, 2462, 1876),
        27: (4253, 2530, 1723), 28: (3964, 2425, 1539), 29: (3484, 2124, 1360), 30: (3301, 2061, 1240), 31: (2438, 1620, 818)}),
    '1967-01': dict(table='3.27', page=74, month=(190123, 94560, 95563), span=('21-31', 65091, 33419, 31672), days={
        1: (10123, 4236, 5887), 2: (8681, 3107, 5574), 3: (6501, 2879, 3622), 4: (5148, 2599, 2549), 5: (6610, 3068, 3542), 6: (5685, 2886, 2799), 7: (5909, 3027, 2882),
        8: (5392, 2775, 2617), 9: (5409, 2796, 2613), 10: (6212, 3145, 3067), 11: (5802, 2967, 2835), 12: (5958, 3123, 2835), 13: (5963, 3051, 2912), 14: (5554, 2918, 2636),
        15: (5763, 3036, 2727), 16: (5620, 2878, 2742), 17: (6027, 3056, 2971), 18: (6193, 3174, 3019), 19: (6104, 3122, 2982), 20: (6378, 3298, 3080)}),
}
# A second, independent reading of the same tables, done without sight of DAILY: table,row,total,boys,girls.
DAILY_SECOND_READING = """
3.24,month,143576,72067,71509;3.24,span,91790,47093,44697;3.24,21,5133,2705,2428;3.24,22,4860,2468,2392;3.24,23,4956,2542,2414;3.24,24,4600,2355,2245;3.24,25,4667,2346,2321
3.24,26,4048,2065,1983;3.24,27,4354,2183,2171;3.24,28,4935,2485,2450;3.24,29,4260,2096,2164;3.24,30,5285,2068,3217;3.24,31,4688,1661,3027
3.25,month,121967,64084,57883;3.25,1,3696,2366,1330;3.25,2,3042,1801,1241;3.25,3,3397,1924,1473;3.25,4,3388,1921,1467;3.25,5,3873,2128,1745;3.25,6,3786,2079,1707;3.25,7,3909,2125,1784
3.25,8,3856,2058,1798;3.25,9,3300,1716,1584;3.25,10,3924,2056,1868;3.25,11,4345,2213,2132;3.25,12,4211,2217,1994;3.25,13,3969,1984,1985;3.25,14,4011,2076,1935;3.25,15,4200,2193,2007
3.25,16,3615,1851,1764;3.25,17,4018,2081,1937;3.25,18,4443,2289,2154;3.25,19,4059,2081,1978;3.25,20,4190,2126,2064;3.25,span,44735,22799,21936
3.26,month,133102,71825,61277;3.26,span,88670,46164,42506;3.26,21,4651,2491,2160;3.26,22,4559,2456,2103;3.26,23,4701,2593,2108;3.26,24,4511,2488,2023;3.26,25,4232,2411,1821
3.26,26,4338,2462,1876;3.26,27,4253,2530,1723;3.26,28,3964,2425,1539;3.26,29,3484,2124,1360;3.26,30,3301,2061,1240;3.26,31,2438,1620,818
3.27,month,190123,94560,95563;3.27,1,10123,4236,5887;3.27,2,8681,3107,5574;3.27,3,6501,2879,3622;3.27,4,5148,2599,2549;3.27,5,6610,3068,3542;3.27,6,5685,2886,2799;3.27,7,5909,3027,2882
3.27,8,5392,2775,2617;3.27,9,5409,2796,2613;3.27,10,6212,3145,3067;3.27,11,5802,2967,2835;3.27,12,5958,3123,2835;3.27,13,5963,3051,2912;3.27,14,5554,2918,2636;3.27,15,5763,3036,2727
3.27,16,5620,2878,2742;3.27,17,6027,3056,2971;3.27,18,6193,3174,3019;3.27,19,6104,3122,2982;3.27,20,6378,3298,3080;3.27,span,65091,33419,31672
"""
# Table 3.23 (p.70): boys per 100 girls as printed, total column.
PRINTED_RATIO = {
    '1965-12': dict(month=100.8, span=105.4, days=[111.4, 103.2, 105.3, 104.9, 101.1, 104.1, 100.6, 101.4, 96.9, 64.3, 54.9]),
    '1966-01': dict(month=110.7, span=103.9, days=[177.9, 145.1, 130.6, 130.9, 121.9, 121.8, 119.1, 114.5, 108.3, 110.1, 103.8, 111.2, 99.9, 107.3, 109.3, 104.9, 107.4, 106.3, 105.2, 103.0]),
    '1966-12': dict(month=117.2, span=108.6, days=[115.3, 116.8, 123.0, 123.0, 132.4, 131.2, 146.8, 157.6, 156.2, 166.2, 198.0]),
    '1967-01': dict(month=99.0, span=105.5, days=[72.0, 55.7, 79.5, 102.0, 86.6, 103.1, 105.0, 106.0, 107.0, 102.5, 104.7, 110.2, 104.8, 110.7, 111.3, 105.0, 102.9, 105.1, 104.7, 107.1]),
}
# 31 December 1966, city and rural parts: table 3.26 (p.73) counts, table 3.23 (p.70) printed ratios.
DEC31_1966 = dict(city=dict(total=2072, boys=1373, girls=699, printed_ratio=196.4), rural=dict(total=366, boys=247, girls=119, printed_ratio=207.6))
# Table 3.4 (p.52): births by month, as printed; the printed year totals are in TABLE_3_4_TOTAL.
TABLE_3_4 = {
    1962: [164532, 144354, 147130, 139575, 127427, 114899, 129925, 132957, 131526, 130185, 123798, 132308],
    1963: [167663, 147328, 148653, 146671, 132715, 121801, 133215, 135806, 132384, 130533, 125766, 136986],
    1964: [162209, 144454, 148384, 147115, 137133, 129003, 142853, 142802, 141225, 139839, 134631, 147113],
    1965: [167220, 151449, 159421, 154749, 140137, 135226, 151439, 157205, 158681, 159240, 144084, 144846],
    1966: [122783, 110695, 111909, 109581, 102788, 100914, 113106, 114427, 111795, 112387, 116262, 134327],
}
TABLE_3_4_TOTAL = {1962: 1618616, 1963: 1659521, 1964: 1716761, 1965: 1823697, 1966: 1360974}
# Vital Statistics 1967 vol.1, table 4 (pp.276-279): All Japan, 1967 by month: total, boys, girls; first the year.
TABLE_4_1967_YEAR = (1935647, 992778, 942869)
TABLE_4_1967 = [(191510, 95205, 96305), (171359, 88054, 83305), (183887, 94714, 89173), (165341, 85127, 80214), (160426, 82441, 77985), (146094, 75253, 70841),
                (161803, 83909, 77894), (160167, 82468, 77699), (153225, 78704, 74521), (148940, 76147, 72793), (141570, 72678, 68892), (151325, 78078, 73247)]
# Vital Statistics 1967 vol.1, table 4.3 (p.54): births per day in thousands, rounded; only a check on TABLE_4_1967.
TABLE_4_3_1967 = [6.18, 6.12, 5.93, 5.51, 5.18, 4.87, 5.22, 5.17, 5.11, 4.80, 4.72, 4.88]
# Vital Statistics 1966 vol.1, table 3.28 (p.75): induced abortions reported under the Eugenic Protection Law.
ABORTIONS = {1955: 1170143, 1956: 1159288, 1957: 1122316, 1958: 1128231, 1959: 1098853, 1960: 1063256, 1961: 1035329, 1962: 985351, 1963: 955092, 1964: 878748, 1965: 843248, 1966: 808378}
# Tables 3.29 and 3.30 (p.75): birth survey of September 1966 (married women under 40; 8 prefectures and 3 cities, 100 census districts).
SURVEY_3_29 = dict(total=1917, already_born=166, due=75, no_birth_planned=1638, unknown=38, no_birth_planned_pct=85.4)
SURVEY_3_30 = dict(total=1638, want_but_none=293, not_in_hinoeuma=64, not_for_now=399, not_wanted=775, unknown=107,
                   pct=dict(want_but_none=17.9, not_in_hinoeuma=3.9, not_for_now=24.4, not_wanted=47.3, unknown=6.5),
                   not_in_hinoeuma_pct_by_area=dict(big_cities=4.9, other_cities=3.9, towns_villages=3.5))
# Text of the special section, pp.68-69, as printed.
MINISTRY_TEXT = dict(
    decline='出生数136万で前年より46万，25.4％減という異常な減少を示した。',
    sex_ratio_norm_and_estimate='性比は，通常105±1であるから，これで修正してみると，8千から1万の女児が，41年の出生から洩れたことになる。',
    share='したがって，このみせかけの減少は，46万減に対して2％程度の寄与にすぎない。',
    meiji_1906='ちなみに，明治39年の出生減少は，専らこの操作によったものといわれている。',
    abortions='41年の中絶件数は約81万で，前年より3万5千ほど減少しており，むしろ近年みられている減少傾向の一環としての推移といえる。',
    abortions_conclusion='したがつて，41年の出生減少は，妊娠中絶とあまり関係なく惹起されたことになる。',
    awareness='「ひのえうま」の認識状況をみると，98％と大半のものが知っており，これには，マスコミが大きな影響を与えていたことがわかる。',
    conclusion='41年の出生減少は，やはり「ひのえうま」を意識したうえでの受胎調節の強化によって実現されたもので，人口史上，特筆すべき現象であるということが出来る。',
)
MINISTRY_NUMBERS = dict(norm=105, norm_band=1, girls_low=8000, girls_high=10000, share_of_drop_pct=2, drop_thousand=460, drop_pct=25.4, knew_pct=98, abortions_1966_about=810000, abortions_fall_about=35000)

# ---------------------------------------------------------------- calendar
LUNAR_NEW_YEAR = dict(zip(range(1960, 2028), """01-28 02-15 02-05 01-25 02-13 02-02 01-21 02-09 01-30 02-17 02-06 01-27 02-15 02-03 01-23
02-11 01-31 02-18 02-07 01-28 02-16 02-05 01-25 02-13 02-02 02-20 02-09 01-29 02-17 02-06 01-27 02-15 02-04 01-23 02-10
01-31 02-19 02-07 01-28 02-16 02-05 01-24 02-12 02-01 01-22 02-09 01-29 02-18 02-07 01-26 02-14 02-03 01-23 02-10 01-31
02-19 02-08 01-28 02-16 02-05 01-25 02-12 02-01 01-22 02-10 01-29 02-17 02-06""".split()))
LUNAR_NEW_YEAR = {y: dt.date(y, *map(int, v.split('-'))) for y, v in LUNAR_NEW_YEAR.items()}
ANIMALS = 'Rat Ox Tiger Rabbit Dragon Snake Horse Goat Monkey Rooster Dog Pig'.split()
TARGETS = ('Tiger', 'Dragon', 'Horse', 'Goat')


def animal(y):
    return ANIMALS[(y - 4) % 12]


def log(*a):
    print(*a, flush=True)


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------- fetch
def _curl(url, dest, *extra):
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.part')
    subprocess.run(['curl', '-sS', '-L', '--fail', '--retry', '3', '-m', '600', '-A', UA, '-o', str(tmp), *extra, url], check=True)
    tmp.rename(dest)


def fetch():
    """Downloads only what is missing and prints URL and SHA-256 of every file."""
    for name, url in {**FILES, **HKO}.items():
        p = DATA / name
        if not p.exists():
            log('downloading', url)
            _curl(url, p)
        log(f'{url}\n  {name} sha256={sha256(p)}')
        if name in PINNED_SHA256 and sha256(p) != PINNED_SHA256[name]:
            raise SystemExit(f'{name} changed: the scan is not the one the constants were read from')
    missing_tw = [n for n in TW_FILES if not (DATA / n).exists() or not (DATA / n).read_bytes().startswith(b'\xd0\xcf\x11\xe0')]
    if missing_tw:
        with tempfile.TemporaryDirectory() as td:
            jar = str(Path(td) / 'jar')
            subprocess.run(['curl', '-sS', '-m', '60', '-A', UA, '-c', jar, '-o', os.devnull, TW_PANEL], check=True)
            for n in missing_tw:
                m4c, d5c = TW_FILES[n]
                for attempt in range(3):
                    _curl(f'{TW_VIEW}?type=xls&m4c={m4c}&d5c={d5c}', DATA / n, '-b', jar, '-e', TW_PANEL)
                    if (DATA / n).read_bytes().startswith(b'\xd0\xcf\x11\xe0'):
                        break
                else:
                    raise SystemExit(f'{n}: portal keeps returning an error page')
    for n, (m4c, d5c) in TW_FILES.items():
        log(f'{TW_VIEW}?type=xls&m4c={m4c}&d5c={d5c}\n  {n} sha256={sha256(DATA / n)}')
    for n, url in MANUAL.items():
        p = DATA / n
        if not p.exists():
            raise SystemExit(f'{n} is missing and cannot be fetched by command: see the KOSIS steps in the docstring ({url})')
        log(f'{url} (read in a browser, see docstring)\n  {n} sha256={sha256(p)}')


# ---------------------------------------------------------------- loaders
def _pd():
    import numpy as np
    import pandas as pd
    return np, pd


def read_xlsx_rows(path):
    """First sheet as lists of cell values; plain zip + xml, so no openpyxl."""
    ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', ns):
                shared.append(''.join(t.text or '' for t in si.iter('{%s}t' % ns['m'])))
        sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
    rows = []
    for row in sheet.find('m:sheetData', ns).findall('m:row', ns):
        vals = []
        for c in row.findall('m:c', ns):
            v = c.find('m:v', ns)
            if v is None or v.text is None:
                continue
            if c.get('t') == 's':
                vals.append(shared[int(v.text)])
            else:
                try:
                    vals.append(float(v.text))
                except ValueError:
                    vals.append(v.text)
        rows.append(vals)
    return rows


def pdf_text(path):
    return subprocess.run(['pdftotext', '-layout', str(path), '-'], check=True, capture_output=True).stdout.decode('utf8', 'replace')


def load_sg():
    _, pd = _pd()
    rows = json.loads((DATA / 'sg_M810051.json').read_text())['Data']['row']
    out = {}
    names = {'1': 'total', '1.1': 'chinese', '1.2': 'malay', '1.3': 'indian'}
    for r in rows:
        if r['seriesNo'] in names:
            s = {}
            for c in r['columns']:
                y, m = c['key'].split()
                s[pd.Period(f'{y}-{dt.datetime.strptime(m, "%b").month:02d}', 'M')] = float(c['value'])
            out[names[r['seriesNo']]] = pd.Series(s).sort_index()
    return out


def load_hk():
    _, pd = _pd()
    rows = json.loads((DATA / 'hk_115_01012A.json').read_text())['dataSet']
    m = {pd.Period(f"{r['period'][:4]}-{r['period'][4:]}", 'M'): float(r['figure']) for r in rows if r['freq'] == 'M' and r['SEX'] == ''}
    y = {int(r['period']): float(r['figure']) for r in rows if r['freq'] == 'Y' and r['SEX'] == ''}
    mw = json.loads((DATA / 'hk_115_01012.json').read_text())['dataSet']
    mw_df = pd.DataFrame(mw)
    non_pr = mw_df[mw_df.PER_STATUS_PARENT.isin(['mw_np', 'mw_oth'])].assign(y=lambda d: d.period.astype(int)).groupby('y').figure.sum().astype(float)
    return pd.Series(m).sort_index(), pd.Series(y).sort_index(), non_pr


def load_kr():
    _, pd = _pd()
    df = pd.read_csv(DATA / 'kr_kosis_DT_1B8000G_monthly.csv')
    s = {}
    for _, r in df.iterrows():
        for i, c in enumerate(df.columns[1:], 1):
            if pd.notna(r[c]):
                s[pd.Period(f'{int(r["year"])}-{i:02d}', 'M')] = float(r[c])
    a = pd.read_csv(DATA / 'kr_kosis_DT_1B8000F_annual.csv')
    return pd.Series(s).sort_index(), pd.Series(a.births.values.astype(float), index=a.year.values)


def load_tw():
    import xlrd
    _, pd = _pd()
    s = {}
    for f in sorted((DATA / 'tw').glob('m1s5_*.xls')):
        y = int(f.stem.split('_')[1][:3]) + 1911
        b = xlrd.open_workbook(f)
        for name in b.sheet_names():
            if not re.fullmatch(r'\d{2,5}', name):
                continue
            month = int(name[-2:])
            sh = b.sheet_by_name(name)
            hdr = ' '.join(str(sh.cell_value(1, j)) for j in range(sh.ncols))
            mm = re.search(r'(\d+)\s*年\s*(\d+)\s*月', hdr)
            assert mm and int(mm.group(1)) + 1911 == y and int(mm.group(2)) == month, (f, name, hdr)
            hit = next((sh.cell_value(i, 2) for i in range(3, min(sh.nrows, 12)) if str(sh.cell_value(i, 1)).strip() == '計' and isinstance(sh.cell_value(i, 2), float)), None)
            assert hit, (f, name)
            s[pd.Period(f'{y}-{month:02d}', 'M')] = float(hit)
    b = xlrd.open_workbook(DATA / 'tw/y2s1.xls')
    reg, occ, sex = {}, {}, {}
    for nm, tgt in (('全國(登記)', reg), ('全國(發生)', occ)):
        sh = b.sheet_by_name(nm)
        for i in range(4, sh.nrows):
            y, v = sh.cell_value(i, 1), sh.cell_value(i, 2)
            if isinstance(y, float) and isinstance(v, float):
                tgt[int(y)] = v
                if nm == '全國(發生)' and isinstance(sh.cell_value(i, 5), float):
                    sex[int(y)] = sh.cell_value(i, 5)
    return pd.Series(s).sort_index(), pd.Series(reg).sort_index(), pd.Series(occ).sort_index(), pd.Series(sex).sort_index()


def load_jp_annual():
    """Table 4.1: year -> dict(births, boys, girls, sex_ratio)."""
    txt = (DATA / 'jp_annual_4_1.bin').read_bytes().decode('cp932', 'replace')
    out = {}
    for ln in txt.splitlines():
        p = [x.strip() for x in ln.split(',')]
        if re.fullmatch(r'\d{4}', p[0]) and p[1].strip().isdigit():
            out[int(p[0])] = dict(births=int(p[1]), boys=int(p[2]), girls=int(p[3]), sex_ratio=float(p[5]))
    return out


def load_jp_table_4_2():
    """Table 4.2: selected years by month, Japanese in Japan."""
    txt = (DATA / 'jp_est_000040503641.bin').read_bytes().decode('cp932', 'replace')
    out = {}
    for ln in txt.splitlines():
        p = ln.split(',')
        if p[0].replace(' ', '').startswith('出生率'):
            break
        if re.fullmatch(r'\d{4}', p[0]) and p[1].isdigit():
            out[int(p[0])] = [int(x) for x in p[2:14]]
    return out


def load_jp_2026():
    """Preliminary (all registrations) 2024-2026 from the xlsx; Japanese only 2025-2026-05 from the PDF."""
    rows = read_xlsx_rows(DATA / 'jp_202608.xlsx')
    prelim = []
    for r in rows:
        s = ' '.join(x for x in r if isinstance(x, str))
        if '令和' in s and len(prelim) < 3:
            prelim.append([int(x) for x in r if isinstance(x, float)])
    assert len(prelim) == 3 and len(prelim[0]) == 8 and len(prelim[1]) == 12, [len(p) for p in prelim]
    printed = re.search(r'１月から当月までの累計.*?出\s+生\s+([\d ]+?)\s{2,}([\d ]+?)\s{2,}', pdf_text(DATA / 'jp_202608.pdf'), re.S)
    gaisu = pdf_text(DATA / 'jp_m2026_toukeihyo05.pdf')
    months = {2025: [], 2026: []}
    year = None
    for ln in gaisu.splitlines():
        m = re.match(r'\s*(?:令和([７８])年)?\s*(\d{1,2})月\s+(\d[\d ]*?\d)\s{2,}', ln)
        if not m:
            continue
        if m.group(1):
            year = {'７': 2025, '８': 2026}[m.group(1)]
        if year and int(m.group(2)) == len(months[year]) + 1:
            months[year].append(int(m.group(3).replace(' ', '')))
    gp = re.search(r'累\s+計\s+１月～５月\s+出\s+生\s+([\d ]+?)\s{2,}([\d ]+?)\s{2,}', gaisu, re.S)
    return dict(y2026=prelim[0], y2025=prelim[1], y2024=prelim[2],
                printed_2026=int(printed.group(1).replace(' ', '')), printed_2025=int(printed.group(2).replace(' ', '')),
                citizens_2025=months[2025], citizens_2026=months[2026],
                citizens_printed_2026=int(gp.group(1).replace(' ', '')), citizens_printed_2025=int(gp.group(2).replace(' ', '')))


def load_recent_sex_ratio():
    """Monthly reports (gaisu), Japanese in Japan: national births, boys, girls, month by month."""
    out = []
    for y, m in GAISU_MONTHS:
        for ln in pdf_text(DATA / f'jp_gaisu/g{y}_{m:02d}.pdf').splitlines():
            hit = re.match(r'\s*全\s+国\s+(\d[\d ]*?\d)\s{2,}(\d[\d ]*?\d)\s{2,}(\d[\d ]*?\d)\s{2,}', ln)
            if hit:
                total, boys, girls = (int(x.replace(' ', '')) for x in hit.groups())
                if boys + girls == total:
                    out.append(dict(month=f'{y}-{m:02d}', total=total, boys=boys, girls=girls, ratio=100 * boys / girls))
                    break
        else:
            raise SystemExit(f'no national row in the monthly report {y}-{m:02d}')
    return out


def load_my():
    _, pd = _pd()
    df = pd.read_csv(DATA / 'my_birth_sex_ethnic.csv')
    df = df[df.sex == 'both'].copy()
    df['year'] = df.date.str[:4].astype(int)
    return df.pivot(index='year', columns='ethnicity', values='abs')


# ---------------------------------------------------------------- calculation
def lunar_year_rate(ms):
    """Births and births per day by lunar year; complete years only, months split by share of days."""
    np, pd = _pd()
    out = {}
    first, last = ms.index.min(), ms.index.max()
    for y in sorted(LUNAR_NEW_YEAR):
        if y + 1 not in LUNAR_NEW_YEAR:
            continue
        a, b = LUNAR_NEW_YEAR[y], LUNAR_NEW_YEAR[y + 1]
        pa, pb = pd.Period(a, 'M'), pd.Period(b - dt.timedelta(1), 'M')
        if pa < first or pb > last:
            continue
        tot = 0.0
        for p in pd.period_range(pa, pb, freq='M'):
            if p not in ms.index:
                tot = float('nan')
                break
            d0, d1 = p.start_time.date(), p.end_time.date()
            ov = (min(d1, b - dt.timedelta(1)) - max(d0, a)).days + 1
            tot += ms[p] * ov / p.days_in_month
        out[y] = (tot, tot / (b - a).days)
    return pd.DataFrame(out, index=['births', 'rate']).T.dropna()


def deseason(ms):
    np, pd = _pd()
    per = ms / np.array([p.days_in_month for p in ms.index])
    lg = np.log(per.values)
    ma = pd.Series(lg).rolling(12).mean()
    ma2 = ((ma + ma.shift(-1)) / 2).shift(-5).values  # centred 2x12
    dev = lg - ma2
    months = np.array([p.month for p in ms.index])
    years = np.array([p.year for p in ms.index])
    adj = np.empty(len(lg))
    for i in range(len(lg)):
        sel = (months == months[i]) & (np.abs(years - years[i]) <= 8) & ~np.isnan(dev)
        adj[i] = lg[i] - np.median(dev[sel])
    return pd.Series(adj, index=ms.index)


def step_at(adj, p, w=6):
    bef = [p - k for k in range(1, w + 1)]
    aft = [p + k for k in range(1, w + 1)]
    if all(x in adj.index for x in bef + aft):
        return float(adj[aft].mean() - adj[bef].mean())
    return float('nan')


def boundary_table(ms):
    np, pd = _pd()
    adj = deseason(ms)
    rows, plc = [], []
    for y in sorted(LUNAR_NEW_YEAR):
        p = pd.Period(LUNAR_NEW_YEAR[y], 'M')
        s = step_at(adj, p)
        if np.isnan(s):
            continue
        prev, cur = animal(y - 1), animal(y)
        rows.append(dict(year=y, enter=cur, leave=prev, step=s))
        if cur not in TARGETS and prev not in TARGETS:
            plc.append(('real', y, s))
        for off in range(3, 10):
            if not ({animal(k) for k in range(y - 1, y + 2)} & set(TARGETS)):
                f = step_at(adj, p + off)
                if not np.isnan(f):
                    plc.append(('fake', y, f))
    return pd.DataFrame(rows), pd.DataFrame(plc, columns=['kind', 'year', 'step'])


def year_effect(ser, y, extra=(), w=6, min_n=5):
    """Residual of year y from a line over clean neighbours; y itself is never in the fit."""
    np, _ = _pd()
    nb = [k for k in range(y - w, y + w + 1) if k != y and k in ser.index and animal(k) not in TARGETS and k not in extra and np.isfinite(ser[k])]
    if len(nb) < min_n or not any(k < y for k in nb) or not any(k > y for k in nb):
        return float('nan')
    b, a = np.polyfit(nb, ser.loc[nb].values, 1)
    return float(ser[y] - (a + b * y))


def effects(ser, extra=(), **kw):
    np, pd = _pd()
    rows = []
    for y in ser.index:
        e = year_effect(ser, int(y), extra, **kw)
        if np.isfinite(e):
            rows.append(dict(year=int(y), animal=animal(int(y)), eff=e))
    return pd.DataFrame(rows)


def pct(x):
    from math import exp
    return 100 * (exp(x) - 1)


def summarise(name, eff, calendar_kind):
    plc = eff[~eff.animal.isin(TARGETS)].eff
    sd = float(plc.std(ddof=1))
    out = []
    for an in TARGETS:
        ev = eff[eff.animal == an]
        if ev.empty:
            continue
        m = float(ev.eff.mean())
        se = sd / sqrt(len(ev))
        out.append(dict(series=name, calendar=calendar_kind, animal=an, n=len(ev), mean_pct=pct(m), lo_pct=pct(m - 1.96 * se), hi_pct=pct(m + 1.96 * se),
                        plc_p5=pct(float(plc.quantile(.05))), plc_p95=pct(float(plc.quantile(.95))), plc_sd_pct=100 * sd, plc_n=int(len(plc)), z=m / se,
                        positive=int((ev.eff > 0).sum()), events=[[int(r.year), pct(r.eff)] for r in ev.itertuples()]))
    return out


def bh(p):
    n = len(p)
    order = sorted(range(n), key=lambda i: p[i])
    q = [0.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        prev = min(prev, p[i] * n / rank)
        q[i] = prev
    return q


def daily_rows():
    """Flatten DAILY: every printed row with its date or span."""
    rows = []
    for ym, t in DAILY.items():
        y, m = map(int, ym.split('-'))
        printed = PRINTED_RATIO[ym]
        day_rows = sorted(t['days'].items())
        for (d, (tot, b, g)), r in zip(day_rows, printed['days']):
            rows.append(dict(date=f'{y}-{m:02d}-{d:02d}', kind='day', total=tot, boys=b, girls=g, ratio=100 * b / g, printed_ratio=r, table=t['table'], page=t['page']))
        lab, tot, b, g = t['span']
        rows.append(dict(date=f'{y}-{m:02d} days {lab}', kind='span', total=tot, boys=b, girls=g, ratio=100 * b / g, printed_ratio=printed['span'], table=t['table'], page=t['page']))
        tot, b, g = t['month']
        rows.append(dict(date=f'{y}-{m:02d}', kind='month', total=tot, boys=b, girls=g, ratio=100 * b / g, printed_ratio=printed['month'], table=t['table'], page=t['page']))
    return rows


def displaced(annual):
    """Own count of displaced girls: see D in the docstring."""
    def dev(norm, b, g):
        return g - b / (norm / 100)
    by_norm = {}
    for norm in (104, 105, 106):
        months = {ym: dev(norm, t['month'][1], t['month'][2]) for ym, t in DAILY.items()}
        surplus = months['1965-12'] + months['1967-01']
        deficit = -(months['1966-01'] + months['1966-12'])
        by_norm[str(norm)] = dict(months=months, girls_surplus_outside_1966=surplus, girls_missing_from_1966=deficit,
                                  boundary_1965_66=dict(surplus_dec=months['1965-12'], missing_jan=-months['1966-01']),
                                  boundary_1966_67=dict(missing_dec=-months['1966-12'], surplus_jan=months['1967-01']),
                                  low=min(surplus, deficit), high=max(surplus, deficit))
    # peak days only: rows where the deviation exceeds what a day normally holds
    days = [dict(date=r['date'], deviation_at_105=dev(105, r['boys'], r['girls'])) for r in daily_rows() if r['kind'] == 'day']
    a66, a65, a67 = annual[1966], annual[1965], annual[1967]
    norm_annual = (a65['sex_ratio'] + a67['sex_ratio']) / 2
    rest_b = a66['boys'] - DAILY['1966-01']['month'][1] - DAILY['1966-12']['month'][1]
    rest_g = a66['girls'] - DAILY['1966-01']['month'][2] - DAILY['1966-12']['month'][2]
    annual_check = dict(ratio_1965=a65['sex_ratio'], ratio_1966=a66['sex_ratio'], ratio_1967=a67['sex_ratio'], norm=norm_annual,
                        girls_short_1966_at_norm=-dev(norm_annual, a66['boys'], a66['girls']), ratio_feb_nov_1966=100 * rest_b / rest_g,
                        girls_short_feb_nov_at_norm=-dev(norm_annual, rest_b, rest_g),
                        note='Feb-Nov = year (table 4.1) minus January and December of tables 3.25-3.26; the two tables differ by under 1 %.')
    y1906 = {}
    for norm in (104, 105, 106):
        y1906[str(norm)] = {str(y): dev(norm, annual[y]['boys'], annual[y]['girls']) for y in (1905, 1906, 1907)}
    return dict(assumptions=['Boys are not moved by the superstition; a girl moved out of 1966 appears as a surplus of girls in the neighbouring month.',
                             'Any other New Year shift of dates is equal for both sexes (boys do pile up on 1 January 1967, so such a shift exists; no ordinary year is in the tables to size it).',
                             'Norm 105 boys per 100 girls, range 104-106 (the ministry\'s own 105 plus or minus 1).',
                             'Counted over whole months of tables 3.24-3.27; the two estimates (girls missing from 1966, surplus girls next to it) need not match and give a range.'],
                by_norm=by_norm, days=days, annual_check=annual_check, japan_1906_deviation=y1906,
                ministry=dict(low=MINISTRY_NUMBERS['girls_low'], high=MINISTRY_NUMBERS['girls_high'], share_of_drop_pct=MINISTRY_NUMBERS['share_of_drop_pct']))


# Public test, written down before any of these numbers exists. The page prints it as it stands here; change nothing after
# the first publication except by adding the outcome, with its date, in a separate commit.
PREDICTION = dict(
    written='2026-11-03',
    total=dict(
        threshold=693300,
        derivation='January-August 2026 (464,110) plus September-December 2025 (241,292) minus 5 %, rounded down to hundreds',
        source='MHLW preliminary report for December 2026',
        source_url='https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/s2026/12.html',
        check_by='2027-03-05',
    ),
    sex_ratio=dict(
        december_2026_at_least=108,
        january_2027_at_most=102,
        reference_december_1966=117.2,
        reference_january_1967=99.0,
        source='MHLW monthly report (gaisu) for December 2026 and January 2027, Japanese in Japan',
        source_url_december='https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/m2026/12.html',
        source_url_january='https://www.mhlw.go.jp/toukei/saikin/hw/jinkou/geppo/m2027/01.html',
        check_by='2027-07-31',
    ),
)


def compute():
    np, pd = _pd()
    sg = load_sg()
    hk_m, hk_y, hk_non_pr = load_hk()
    kr_m, kr_y = load_kr()
    tw_m, tw_reg, tw_occ, tw_sex = load_tw()
    jp = load_jp_annual()
    jp42 = load_jp_table_4_2()
    j26 = load_jp_2026()
    my = load_my()
    jp_y = pd.Series({y: float(v['births']) for y, v in jp.items()}).sort_index()

    sg_lun = {k: lunar_year_rate(v) for k, v in sg.items()}
    hk_lun = lunar_year_rate(hk_m)
    kr_lun = lunar_year_rate(kr_m)
    tw_lun = lunar_year_rate(tw_m)
    tw_st = pd.concat([tw_reg[tw_reg.index < 1974], tw_occ]).sort_index()
    hk_res = (hk_y - hk_non_pr.reindex(hk_y.index).fillna(0)).dropna()
    hk_res = hk_res[hk_res.index >= 1986]
    ctrl = sg_lun['malay'].rate + sg_lun['indian'].rate
    my_ctrl = my['bumi_malay'] + my['indian']
    series = {
        'SG Chinese': (np.log(sg_lun['chinese'].rate), 'lunar', ()),
        'SG Malays': (np.log(sg_lun['malay'].rate), 'lunar', ()),
        'SG Indians': (np.log(sg_lun['indian'].rate), 'lunar', ()),
        'SG Chinese minus controls': (np.log(sg_lun['chinese'].rate) - np.log(ctrl), 'lunar', ()),
        'HK': (np.log(hk_lun.rate), 'lunar', ()),
        'HK Gregorian': (np.log(hk_y), 'gregorian', ()),
        'HK excl. mainland mothers (spouse not permanent resident)': (np.log(hk_res), 'gregorian', ()),
        'KR': (np.log(kr_lun.rate), 'lunar', ()),
        'KR Gregorian': (np.log(kr_y), 'gregorian', ()),
        'TW': (np.log(tw_lun.rate), 'lunar', ()),
        'TW Gregorian': (np.log(tw_st), 'gregorian', ()),
        'JP': (np.log(jp_y[jp_y.index >= 1952]), 'gregorian', (1965, 1967)),
        'MY Chinese': (np.log(my['chinese']), 'gregorian', ()),
        'MY Malays': (np.log(my['bumi_malay']), 'gregorian', ()),
        'MY Indians': (np.log(my['indian']), 'gregorian', ()),
        'MY Chinese minus controls': (np.log(my['chinese']) - np.log(my_ctrl), 'gregorian', ()),
    }
    table, all_eff = [], {}
    for name, (s, kind, extra) in series.items():
        e = effects(s, extra)
        all_eff[name] = e
        table += summarise(name, e, kind)
    ps = [erfc(abs(r['z']) / sqrt(2)) for r in table]
    for r, p, q in zip(table, ps, bh(ps)):
        r['p'], r['q'] = p, q
    ej = all_eff['JP']
    jp_h = ej[(ej.animal == 'Horse') & (ej.year != 1966)]

    steps = []
    for name, ms in {'SG Chinese': sg['chinese'], 'SG Malays': sg['malay'], 'SG Indians': sg['indian'], 'HK': hk_m, 'KR': kr_m, 'TW': tw_m}.items():
        b, plc = boundary_table(ms)
        sd = float(plc.step.std(ddof=1))
        for an in TARGETS:
            for side in ('enter', 'leave'):
                ev = b[b[side] == an]
                if ev.empty:
                    continue
                m = float(ev.step.mean())
                steps.append(dict(series=name, animal=an, side=side, n=len(ev), mean_pct=pct(m), plc_sd_pct=100 * sd, plc_n=int(len(plc)),
                                  plc_p5=pct(float(plc.step.quantile(.05))), plc_p95=pct(float(plc.step.quantile(.95))), z=m / (sd / sqrt(len(ev))),
                                  events=[[int(r.year), pct(r.step)] for r in ev.itertuples()]))

    rob = []
    for name in ('SG Chinese', 'SG Chinese minus controls', 'TW Gregorian', 'HK', 'KR', 'MY Chinese minus controls', 'JP'):
        s, _, extra = series[name]
        for w in (4, 6, 8):
            for nocovid in (False, True):
                ex = set(extra) | ({2020, 2021, 2022} if nocovid else set())
                rs = effects(s, tuple(ex), w=w, min_n=4)
                for an in ('Tiger', 'Dragon'):
                    ev = rs[rs.animal == an]
                    rob.append(dict(series=name, window=w, without_covid_base=nocovid, animal=an, n=len(ev), mean_pct=pct(float(ev.eff.mean()))))

    def yoy(a, b):
        return 100 * (a / b - 1)
    m65, m66 = TABLE_3_4[1965], TABLE_3_4[1966]
    m67 = [t[0] for t in TABLE_4_1967]
    n26 = len(j26['y2026'])
    compare = dict(
        basis='2024-2026: MHLW preliminary, includes foreigners in Japan and Japanese abroad. 1965-1966: Japanese in Japan, final.',
        months=[dict(month=i + 1, y2024=j26['y2024'][i], y2025=j26['y2025'][i], y2026=j26['y2026'][i] if i < n26 else None,
                     yoy_2025=yoy(j26['y2025'][i], j26['y2024'][i]), yoy_2026=yoy(j26['y2026'][i], j26['y2025'][i]) if i < n26 else None,
                     y1965=m65[i], y1966=m66[i], yoy_1966=yoy(m66[i], m65[i]), y1967=m67[i], yoy_1967_on_1965=yoy(m67[i], m65[i])) for i in range(12)],
        to_date=dict(months=n26, y2024=sum(j26['y2024'][:n26]), y2025=sum(j26['y2025'][:n26]), y2026=sum(j26['y2026']), yoy_2025=yoy(sum(j26['y2025'][:n26]), sum(j26['y2024'][:n26])),
                     yoy_2026=yoy(sum(j26['y2026']), sum(j26['y2025'][:n26])), y1965=sum(m65[:n26]), y1966=sum(m66[:n26]), yoy_1966=yoy(sum(m66[:n26]), sum(m65[:n26]))),
        citizens_only=dict(basis='Japanese in Japan, MHLW monthly report (概数) 2026-05', months=len(j26['citizens_2026']), y2025=j26['citizens_2025'], y2026=j26['citizens_2026'],
                           sum_2025=sum(j26['citizens_2025'][:5]), sum_2026=sum(j26['citizens_2026']), yoy=yoy(sum(j26['citizens_2026']), sum(j26['citizens_2025'][:5])),
                           others_share_2025=100 * (1 - sum(j26['citizens_2025'][:5]) / sum(j26['y2025'][:5])), others_share_2026=100 * (1 - sum(j26['citizens_2026']) / sum(j26['y2026'][:5]))),
        monthly_noise_2025=dict(sd_yoy_months=float(np.std([yoy(a, b) for a, b in zip(j26['y2025'], j26['y2024'])], ddof=1))),
    )
    per_day = lambda y, m, v: v / calendar.monthrange(y, m)[1]
    cliff = dict(dec_1965=per_day(1965, 12, m65[11]), jan_1966=per_day(1966, 1, m66[0]), dec_1966=per_day(1966, 12, m66[11]), jan_1967=per_day(1967, 1, m67[0]))
    cliff['jan66_on_dec65_pct'] = yoy(cliff['jan_1966'], cliff['dec_1965'])
    cliff['jan67_on_dec66_pct'] = yoy(cliff['jan_1967'], cliff['dec_1966'])
    for y in (1963, 1964, 1965):
        cliff[f'jan{y % 100}_on_dec{(y - 1) % 100}_pct'] = yoy(per_day(y, 1, TABLE_3_4[y][0]), per_day(y - 1, 12, TABLE_3_4[y - 1][11]))

    net = []
    for base in ([1960, 1961, 1962, 1963, 1964, 1968, 1969, 1970], list(range(1958, 1965)) + list(range(1968, 1973)), list(range(1955, 1965)) + list(range(1968, 1975))):
        b, c = np.polyfit(base, np.log(jp_y.loc[base].values), 1)
        d = {y: float(jp_y[y] - np.exp(c + b * y)) for y in (1965, 1966, 1967)}
        net.append(dict(base=f'{base[0]}-1964 and 1968-{base[-1]}', y1965=d[1965], y1966=d[1966], y1967=d[1967], net=sum(d.values())))

    # E. find your year
    clean_by = {'Singapore Chinese': 'SG Chinese', 'Hong Kong': 'HK', 'South Korea': 'KR', 'Taiwan': 'TW Gregorian', 'Japan': 'JP', 'Malaysia Chinese': 'MY Chinese'}
    fy = {}
    for label, ser, kind in (('Singapore Chinese', sg_lun['chinese'].births, 'lunar'), ('Hong Kong', hk_lun.births, 'lunar'), ('South Korea', kr_lun.births, 'lunar'),
                             ('Taiwan', tw_st, 'gregorian'), ('Japan', jp_y[jp_y.index >= 1947], 'gregorian'), ('Malaysia Chinese', my['chinese'], 'gregorian')):
        ce = all_eff[clean_by[label]].set_index('year').eff
        rows = []
        for y in ser.index:
            y = int(y)
            nb = [y - 2, y - 1, y + 1, y + 2]
            if all(k in ser.index for k in nb):
                rows.append(dict(year=y, animal=animal(y), births=float(ser[y]), vs_neighbours_pct=100 * (float(ser[y]) / float(ser.loc[nb].mean()) - 1), clean_pct=pct(float(ce[y])) if y in ce.index else None))
        srt = sorted(rows, key=lambda r: r['vs_neighbours_pct'])
        fy[label] = dict(calendar=kind, years=rows, lowest=[r['year'] for r in srt[:3]], highest=[r['year'] for r in srt[-3:][::-1]])

    annual_rows = [dict(year=y, births=v['births'], boys=v['boys'], girls=v['girls'], sex_ratio=v['sex_ratio']) for y, v in sorted(jp.items())]
    y1906 = {y: annual_rows_item for y, annual_rows_item in ((r['year'], r) for r in annual_rows) if 1904 <= y <= 1908}
    r = dict(
        meta=dict(slug='fire-horse-japan-births', data_accessed=ACCESSED, japan_prelim_through='2026-08', japan_citizens_through='2026-05', singapore_through='2026-09', hong_kong_through='2026-08', korea_through='2026-08', taiwan_through='2026-09', malaysia_through=2025,
                  generated_by='scripts/research/fire_horse_births.py', not_collected=['China (NBS 403)', 'Macao (no long series found)', 'Malaysia monthly by ethnicity and before 2000', 'Taiwan monthly before 1998', 'Chinese abroad (not searched)']),
        sources=SOURCES,
        japan_daily=[{k: v for k, v in row.items() if k != 'printed_ratio'} | dict(printed_ratio=row['printed_ratio']) for row in daily_rows()],
        dec31_1966_city_rural=DEC31_1966,
        displaced=displaced(jp),
        japan_1906=dict(years=y1906, change_1906_pct=yoy(jp[1906]['births'], jp[1905]['births']), change_1907_pct=yoy(jp[1907]['births'], jp[1906]['births']), source='e-Stat table 4.1'),
        ministry=dict(numbers=MINISTRY_NUMBERS, text=MINISTRY_TEXT, abortions=ABORTIONS, abortions_change_1966=ABORTIONS[1966] - ABORTIONS[1965], survey_3_29=SURVEY_3_29, survey_3_30=SURVEY_3_30,
                      reference='Vital Statistics 1966 vol.1, pp.68-69 (text), p.75 (tables 3.28-3.30), p.70 (table 3.23)'),
        japan_annual=annual_rows,
        japan_monthly={'1965': m65, '1966': m66, '1967': m67, '2024': j26['y2024'], '2025': j26['y2025'], '2026': j26['y2026'],
                       'basis': '1965-1967 Japanese in Japan, final (scans). 2024-2026 preliminary, includes foreigners in Japan and Japanese abroad.',
                       'citizens_2024': jp42[2024], 'citizens_2025': jp42[2025]},
        japan_1967_by_month_sex=[dict(month=i + 1, total=t[0], boys=t[1], girls=t[2]) for i, t in enumerate(TABLE_4_1967)],
        japan_cliff_births_per_day=cliff,
        japan_net=net,
        compare_2026=compare,
        year_effects=table,
        japan_horse_without_1966=dict(n=len(jp_h), mean_pct=pct(float(jp_h.eff.mean())), events=[[int(x.year), pct(x.eff)] for x in jp_h.itertuples()]),
        boundary_steps=steps,
        robustness=rob,
        events={name: [[int(x.year), x.animal, pct(x.eff)] for x in e.itertuples()] for name, e in all_eff.items()},
        sg_lunar=[dict(year=int(y), animal=animal(int(y)), chinese_per_day=float(sg_lun['chinese'].rate[y]), malay_per_day=float(sg_lun['malay'].rate[y]), indian_per_day=float(sg_lun['indian'].rate[y]),
                       chinese_births=float(sg_lun['chinese'].births[y])) for y in sg_lun['chinese'].index],
        tw_annual=dict(rows=[dict(year=int(y), births=float(tw_st[y]), basis='registered' if y < 1974 else 'occurred', sex_ratio=float(tw_sex[y]) if y in tw_sex.index else None) for y in tw_st.index]),
        hk_annual=[dict(year=int(y), births=float(hk_y[y]), mainland_non_pr=float(hk_non_pr[y]) if y in hk_non_pr.index else None) for y in hk_y.index],
        kr_annual=[dict(year=int(y), births=float(kr_y[y])) for y in kr_y.index],
        my_annual=[dict(year=int(y), chinese=float(my['chinese'][y]), bumi_malay=float(my['bumi_malay'][y]), indian=float(my['indian'][y])) for y in my.index],
        my_dragon_exit=[dict(year=y, chinese_pct=yoy(float(my['chinese'][y]), float(my['chinese'][y - 1])), bumi_malay_pct=yoy(float(my['bumi_malay'][y]), float(my['bumi_malay'][y - 1])), indian_pct=yoy(float(my['indian'][y]), float(my['indian'][y - 1]))) for y in (2001, 2013, 2025)],
        find_your_year=fy,
        prediction=PREDICTION,
        recent_sex_ratio=load_recent_sex_ratio(),
    )
    (DATA / 'computed.json').write_text(json.dumps(r, ensure_ascii=False))
    (DATA / 'validation.json').unlink(missing_ok=True)
    log('compute done:', DATA / 'computed.json')


# ---------------------------------------------------------------- validate
def validate() -> bool:
    np, pd = _pd()
    problems, checks = [], []

    def check(name, ok, detail=''):
        checks.append(dict(name=name, ok=bool(ok), detail=str(detail)))
        if not ok:
            problems.append(f'{name}: {detail}')

    if not (DATA / 'computed.json').exists():
        raise SystemExit('run compute first')
    r = json.loads((DATA / 'computed.json').read_text())

    # scans: pins
    for n, want in PINNED_SHA256.items():
        check(f'scan unchanged {n}', sha256(DATA / n) == want)
    # tables 3.24-3.27: every printed row
    for ym, t in DAILY.items():
        bad_rows, bad_ratio = [], []
        printed = PRINTED_RATIO[ym]
        for (d, (tot, b, g)), rr in zip(sorted(t['days'].items()), printed['days']):
            if b + g != tot:
                bad_rows.append(d)
            if abs(100 * b / g - rr) > 0.05:
                bad_ratio.append((d, round(100 * b / g, 2), rr))
        _, st, sb, sg_ = t['span']
        mt, mb, mg = t['month']
        check(f'{ym} boys + girls = total on every day', not bad_rows, bad_rows)
        check(f'{ym} span row boys + girls = total', sb + sg_ == st)
        check(f'{ym} month row boys + girls = total', mb + mg == mt)
        check(f'{ym} days + span = month, all three columns', (sum(v[0] for v in t['days'].values()) + st, sum(v[1] for v in t['days'].values()) + sb, sum(v[2] for v in t['days'].values()) + sg_) == (mt, mb, mg),
              (sum(v[0] for v in t['days'].values()) + st, sum(v[1] for v in t['days'].values()) + sb, sum(v[2] for v in t['days'].values()) + sg_, mt, mb, mg))
        check(f'{ym} ratios match table 3.23 within 0.05', not bad_ratio, bad_ratio)
        check(f'{ym} span ratio', abs(100 * sb / sg_ - printed['span']) <= 0.05, round(100 * sb / sg_, 2))
        check(f'{ym} month ratio', abs(100 * mb / mg - printed['month']) <= 0.05, round(100 * mb / mg, 2))
    # the two readings
    second = {}
    for item in re.split(r'[;\n]', DAILY_SECOND_READING):
        if item.strip():
            tb, row, *vals = item.strip().split(',')
            second[(tb, row)] = tuple(map(int, vals))
    diffs = []
    for ym, t in DAILY.items():
        tb = t['table']
        pairs = [('month', t['month']), ('span', t['span'][1:])] + [(str(d), v) for d, v in t['days'].items()]
        for row, v in pairs:
            if second.get((tb, row)) != tuple(v):
                diffs.append((tb, row, v, second.get((tb, row))))
    check('tables 3.24-3.27: two independent readings agree on all rows', not diffs and len(second) == sum(2 + len(t['days']) for t in DAILY.values()), diffs or f'{len(second)} rows')
    # 31 December 1966, parts
    c, ru = DEC31_1966['city'], DEC31_1966['rural']
    dec = DAILY['1966-12']['days'][31]
    check('31 Dec 1966: city + rural = all, each column', (c['total'] + ru['total'], c['boys'] + ru['boys'], c['girls'] + ru['girls']) == dec)
    for part in (c, ru):
        check(f'31 Dec 1966 part ratio {part["printed_ratio"]}', abs(100 * part['boys'] / part['girls'] - part['printed_ratio']) <= 0.05 and part['boys'] + part['girls'] == part['total'])
    # table 3.4 and table 4
    jp = load_jp_annual()
    for y, v in TABLE_3_4.items():
        check(f'table 3.4 {y}: months sum to printed total', sum(v) == TABLE_3_4_TOTAL[y], sum(v))
        check(f'table 3.4 {y}: total equals e-Stat 4.1', TABLE_3_4_TOTAL[y] == jp[y]['births'])
    check('table 3.4 row 1965 equals e-Stat table 4.2', load_jp_table_4_2()[1965] == TABLE_3_4[1965])
    tt = [t[0] for t in TABLE_4_1967]
    check('1967 table 4: months sum to the year, three columns', (sum(tt), sum(t[1] for t in TABLE_4_1967), sum(t[2] for t in TABLE_4_1967)) == TABLE_4_1967_YEAR)
    check('1967 table 4: boys + girls = total each month', all(t[1] + t[2] == t[0] for t in TABLE_4_1967))
    check('1967 table 4: year equals e-Stat 4.1, three columns', TABLE_4_1967_YEAR == (jp[1967]['births'], jp[1967]['boys'], jp[1967]['girls']))
    check('1967 table 4 against per-day table 4.3', all(abs(t / calendar.monthrange(1967, i + 1)[1] / 1000 - p) <= 0.005 for i, (t, p) in enumerate(zip(tt, TABLE_4_3_1967))))
    # special tabulation against the monthly tables: printed, not a failure unless wide
    gaps = {'1965-12': TABLE_3_4[1965][11], '1966-01': TABLE_3_4[1966][0], '1966-12': TABLE_3_4[1966][11], '1967-01': tt[0]}
    gap_txt = {ym: round(100 * (DAILY[ym]['month'][0] / v - 1), 2) for ym, v in gaps.items()}
    check('tables 3.24-3.27 month totals within 1.5 % of the monthly tables (gap unexplained by the report)', all(abs(x) < 1.5 for x in gap_txt.values()), gap_txt)
    # ministry text against its own tables
    check('text "about 810 thousand, 35 thousand fewer" = table 3.28', abs(ABORTIONS[1966] - 810000) < 5000 and abs(ABORTIONS[1965] - ABORTIONS[1966] - 35000) < 1000, ABORTIONS[1965] - ABORTIONS[1966])
    check('text 46 thousand x 10 and 25.4 % = table 4.1', abs(jp[1965]['births'] - jp[1966]['births'] - 460000) < 5000 and abs(100 * (1 - jp[1966]['births'] / jp[1965]['births']) - 25.4) < 0.05)
    s29, s30 = SURVEY_3_29, SURVEY_3_30
    check('table 3.29 adds up', s29['already_born'] + s29['due'] + s29['no_birth_planned'] + s29['unknown'] == s29['total'] and abs(100 * s29['no_birth_planned'] / s29['total'] - s29['no_birth_planned_pct']) <= 0.05)
    check('table 3.30 adds up', sum(s30[k] for k in ('want_but_none', 'not_in_hinoeuma', 'not_for_now', 'not_wanted', 'unknown')) == s30['total'])
    check('table 3.30 percentages', all(abs(100 * s30[k] / s30['total'] - v) <= 0.05 for k, v in s30['pct'].items()))
    # calendar against the Hong Kong Observatory
    bad = []
    for y, d in LUNAR_NEW_YEAR.items():
        txt = (DATA / f'hko/T{y}e.txt').read_text('latin-1')
        m = re.search(r'^(\d{4})/(\d{1,2})/(\d{1,2})\s+1st Lunar month', txt, re.M | re.I)
        if not m or dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) != d:
            bad.append((y, d.isoformat(), m.group(0) if m else None))
    check('Lunar New Year dates = Hong Kong Observatory, 1960-2027', not bad, bad)
    check('animals: 1966 Horse, 2024 Dragon, 2026 Horse, 2022 Tiger', (animal(1966), animal(2024), animal(2026), animal(2022)) == ('Horse', 'Dragon', 'Horse', 'Tiger'))
    # official series: monthly against annual
    hk_m, hk_y, _ = load_hk()
    kr_m, kr_y = load_kr()
    tw_m, tw_reg, _, _ = load_tw()
    sg = load_sg()
    my = load_my()
    j26 = load_jp_2026()
    for lab, ms, ys, yrs in (('HK', hk_m, hk_y, range(1976, 2026)), ('KR', kr_m, kr_y, range(1981, 2026)), ('TW', tw_m, tw_reg, range(1998, 2026))):
        worst = float((ms.groupby(lambda p: p.year).sum().reindex(yrs) / ys.reindex(yrs) - 1).abs().max())
        check(f'{lab}: months sum to annual table', worst < 0.0005, worst)
    check('TW: 345 months, 1998-01..2026-09', len(tw_m) == 345 and str(tw_m.index.min()) == '1998-01' and str(tw_m.index.max()) == '2026-09', len(tw_m))
    check('SG: Chinese + Malays + Indians never above total', bool((sg['chinese'] + sg['malay'] + sg['indian'] <= sg['total']).all()))
    my_all = pd.read_csv(DATA / 'my_birth_sex_ethnic.csv')
    my_all = my_all[my_all.sex == 'both']
    tot = my_all[my_all.ethnicity == 'overall'].assign(y=lambda d: d.date.str[:4].astype(int)).set_index('y')['abs']
    full = my.drop(columns=['overall']).dropna()  # 2025 prints no "other" groups yet
    worst = float((full.sum(axis=1) / tot.reindex(full.index) - 1).abs().max())
    check('MY: ethnic groups sum to overall where all are printed', worst < 0.001, f'{worst} over {len(full)} years')
    check('JP 2026 preliminary: months sum to the printed Jan-Aug', sum(j26['y2026']) == j26['printed_2026'] and sum(j26['y2025'][:8]) == j26['printed_2025'], (sum(j26['y2026']), j26['printed_2026'], sum(j26['y2025'][:8]), j26['printed_2025']))
    check('JP citizens: months sum to the printed Jan-May', sum(j26['citizens_2026']) == j26['citizens_printed_2026'] and sum(j26['citizens_2025'][:5]) == j26['citizens_printed_2025'], (j26['citizens_2026'], j26['citizens_printed_2026']))
    check('JP citizens 2025: 12 months, 2026: 5 months', len(j26['citizens_2025']) == 12 and len(j26['citizens_2026']) == 5)
    # JSON shape
    need = ['meta', 'sources', 'japan_daily', 'displaced', 'ministry', 'japan_annual', 'japan_monthly', 'compare_2026', 'year_effects', 'boundary_steps', 'events', 'sg_lunar', 'tw_annual', 'hk_annual', 'kr_annual', 'my_annual', 'find_your_year']
    check('all JSON sections present', all(k in r for k in need), [k for k in need if k not in r])
    check('japan_annual spans 1899-2025 less the war gap', r['japan_annual'][0]['year'] == 1899 and r['japan_annual'][-1]['year'] == 2025, len(r['japan_annual']))
    check('every target cell has a q', all(0 <= c['q'] <= 1 for c in r['year_effects']))
    src_ids = {s['id'] for s in SOURCES}
    check('sources cover the seven publishers', {'jp_estat', 'jp_mhlw', 'sg_singstat', 'hk_csd', 'kr_kosis', 'tw_ris', 'my_dosm'} <= src_ids)
    check('SingStat raw monthly stays out of the CSV', not next(s for s in SOURCES if s['id'] == 'sg_singstat')['raw_in_csv'])

    td = r['compare_2026']['to_date']
    rest_2025 = sum(m['y2025'] for m in r['compare_2026']['months'][8:])
    want = int((td['y2026'] + 0.95 * rest_2025) // 100 * 100)
    recent = r['recent_sex_ratio']
    check('recent monthly sex ratios: 22 months, plausible', len(recent) == 22 and all(100 < x['ratio'] < 110 for x in recent), f'{len(recent)}')
    check('prediction thresholds lie outside the recent monthly range',
          max(x['ratio'] for x in recent) < PREDICTION['sex_ratio']['december_2026_at_least']
          and min(x['ratio'] for x in recent) > PREDICTION['sex_ratio']['january_2027_at_most'])
    check('prediction threshold follows its derivation', want == PREDICTION['total']['threshold'], f'{want}')
    (DATA / 'validation.json').write_text(json.dumps(dict(problems=problems, checks=checks), ensure_ascii=False))
    ok_n = sum(c['ok'] for c in checks)
    log(f'{ok_n}/{len(checks)} checks passed')
    for p in problems:
        log('PROBLEM', p)
    for c in checks:
        if c['name'].startswith(('tables 3.24-3.27 month totals', 'tables 3.24-3.27: two')):
            log(c['name'], c['detail'])
    return not problems


# ---------------------------------------------------------------- export
def _round(x, digits=3):
    if isinstance(x, dict):
        return {k: _round(v, digits) for k, v in x.items()}
    if isinstance(x, list):
        return [_round(v, digits) for v in x]
    if isinstance(x, float):
        return round(x, digits)
    return x


def derived_source(series):
    """Calculated rows inherit the terms of the series they come from: Singapore and Hong Kong are not CC BY."""
    if series.startswith(('SG', 'Singapore')):
        return 'calc from sg_singstat'
    if series.startswith(('HK', 'Hong Kong')):
        return 'calc from hk_csd'
    return 'calc'


def export():
    if not (DATA / 'validation.json').exists():
        raise SystemExit('run validate first')
    val = json.loads((DATA / 'validation.json').read_text())
    if val['problems']:
        raise SystemExit('validation failed: run validate and resolve its problems first')
    r = json.loads((DATA / 'computed.json').read_text())
    r['checks'] = dict(passed=sum(c['ok'] for c in val['checks']), total=len(val['checks']), items=val['checks'],
                       files={n: sha256(DATA / n) for n in list(FILES) + list(MANUAL)})
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(_round(r), ensure_ascii=False, separators=(',', ':')) + '\n')

    rows = []

    def add(series, period, measure, value, source):
        if value is None:
            return
        rows.append((series, period, measure, round(value, 3) if isinstance(value, float) else value, source))
    for s in SOURCES:
        add('_attribution', s['id'], 'attribution', s['attribution'], s['id'])
    for d in r['japan_daily']:
        src = f"jp_estat table {d['table']} p.{d['page']}"
        for m in ('total', 'boys', 'girls'):
            add('japan_daily', d['date'], m, d[m], src)
        add('japan_daily', d['date'], 'sex_ratio_printed', d['printed_ratio'], 'jp_estat table 3.23 p.70')
    for y in r['japan_annual']:
        for m in ('births', 'boys', 'girls', 'sex_ratio'):
            add('japan_annual', y['year'], m, y[m], 'jp_estat table 4.1')
    for y in ('1965', '1966', '1967', '2024', '2025', '2026'):
        src = 'jp_mhlw preliminary 2026-08' if y >= '2024' else ('jp_estat 1966 yearbook table 3.4' if y != '1967' else 'jp_estat 1967 yearbook table 4')
        for i, v in enumerate(r['japan_monthly'][y], 1):
            add('japan_monthly', f'{y}-{i:02d}', 'births', v, src)
    for y, key in ((2025, 'y2025'), (2026, 'y2026')):
        for i, v in enumerate(r['compare_2026']['citizens_only'][key], 1):
            add('japan_monthly_citizens', f'{y}-{i:02d}', 'births', v, 'jp_mhlw monthly report 2026-05')
    for y, v in r['ministry']['abortions'].items():
        add('japan_abortions_reported', y, 'count', v, 'jp_estat 1966 yearbook table 3.28')
    for norm, d in r['displaced']['by_norm'].items():
        for k in ('girls_missing_from_1966', 'girls_surplus_outside_1966'):
            add('displaced_girls_own_count', f'norm {norm}', k, d[k], 'calc')
    for c in r['year_effects']:
        p = f"{c['series']} {c['animal']}"
        src = derived_source(c['series'])
        for k in ('n', 'mean_pct', 'lo_pct', 'hi_pct', 'plc_p5', 'plc_p95', 'q'):
            add('year_effect', p, k, c[k], src)
    for c in r['boundary_steps']:
        p = f"{c['series']} {c['animal']} {c['side']}"
        src = derived_source(c['series'])
        for k in ('n', 'mean_pct', 'plc_sd_pct', 'plc_p5', 'plc_p95'):
            add('boundary_step', p, k, c[k], src)
    for name, evs in r['events'].items():
        src = derived_source(name)
        for y, an, v in evs:
            if an in TARGETS:
                add(f'event {name}', y, f'{an} effect pct', v, src)
    for x in r['recent_sex_ratio']:
        for k in ('total', 'boys', 'girls', 'ratio'):
            add('japan_recent_monthly', x['month'], k, x[k], 'jp_mhlw monthly report')
    for y in r['sg_lunar']:
        for k in ('chinese_per_day', 'malay_per_day', 'indian_per_day'):
            add('singapore_lunar_year', y['year'], k, y[k], 'sg_singstat aggregated by StarTarot')
    for y in r['tw_annual']['rows']:
        add('taiwan_annual', y['year'], f"births {y['basis']}", y['births'], 'tw_ris y2s1')
        add('taiwan_annual', y['year'], 'sex_ratio', y['sex_ratio'], 'tw_ris y2s1')
    for y in r['hk_annual']:
        add('hong_kong_annual', y['year'], 'births', y['births'], 'hk_csd 115-01012A')
        add('hong_kong_annual', y['year'], 'births_to_mainland_mothers_spouse_not_permanent', y['mainland_non_pr'], 'hk_csd 115-01012')
    for y in r['kr_annual']:
        add('korea_annual', y['year'], 'births', y['births'], 'kr_kosis DT_1B8000F')
    for y in r['my_annual']:
        for k in ('chinese', 'bumi_malay', 'indian'):
            add('malaysia_annual', y['year'], k, y[k], 'my_dosm')
    for c, d in r['find_your_year'].items():
        src = derived_source(c)
        for y in d['years']:
            add(f'find_your_year {c}', y['year'], 'vs_neighbours_pct', y['vs_neighbours_pct'], src)
            add(f'find_your_year {c}', y['year'], 'clean_base_pct', y['clean_pct'], src)
    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open('w', newline='') as fh:
        w = csv.writer(fh, lineterminator='\n')
        w.writerow(['series', 'period', 'measure', 'value', 'source'])
        w.writerows(rows)
    if SCRIPT_COPY:
        shutil.copyfile(__file__, SCRIPT_COPY)
    log(f'wrote {JSON_OUT} ({JSON_OUT.stat().st_size // 1024} KB), {CSV_OUT} ({CSV_OUT.stat().st_size // 1024} KB, {len(rows)} rows)' + (f', {SCRIPT_COPY}' if SCRIPT_COPY else ''))


if __name__ == '__main__':
    steps = {'fetch': fetch, 'compute': compute, 'validate': validate, 'export': export}
    if len(sys.argv) != 2 or sys.argv[1] not in steps:
        raise SystemExit(f'usage: {sys.argv[0]} {"|".join(steps)}')
    ok = steps[sys.argv[1]]()
    sys.exit(1 if ok is False else 0)
