# On 31 December 1966, Japan recorded two boys for every girl. The Fire Horse in official birth series

Full write-up: https://startarot.online/research/fire-horse-japan-births

Japan's 1966 was a Fire Horse year (hinoeuma), and folk belief held that a girl born in one brings
misfortune on her husband. This study reads the official record of that year and of the zodiac
years elsewhere: Japan's daily birth tables around both edges of 1966 (read from the scanned
Vital Statistics yearbooks), Japan's annual series 1899–2025 and the months of 2026, and birth
series of Singapore, Taiwan, Hong Kong, South Korea and Malaysia. It is about what people do because
of a sign, not about whether signs do anything. Nothing here tests astrology.

## Key findings

- The recorded ratio flips at each edge of the Fire Horse year. 31 December 1966: 1,620 boys and
  818 girls, 198 per 100. 1 January 1967: 4,236 boys and 5,887 girls, 72 per 100. A year earlier,
  the mirror image: 54.9 on 31 December 1965, 177.9 on 1 January 1966. The usual ratio is about 105.
  The yearbook calls these tables "by date as notified", so they are dates written on forms.
- Against a ratio of 105, 10,277 girls are missing from 1966 and 8,380 surplus girls appear outside
  it, about 9,000 either way; the health ministry's own estimate was 8,000 to 10,000. That is about
  2% of the fall in births.
- The fall itself was real and planned: births were already down 26.6% in January 1966. In the
  ministry's survey 98% knew the belief, and 3.9% of the wives planning no birth that year gave it
  as the reason.
- 2026 is again a Fire Horse year. January to August 2026: 464,110 births against 464,517 a year
  earlier, −0.09%, against −27.2% over the same months of 1966. An effect of 1–3% cannot be ruled
  out yet.
- Elsewhere, a different animal moves the numbers. Chinese births in Singapore run about 10% above
  trend in Dragon years, and Malay births beside them do not. The Fire Horse shows no such dent
  outside Japan.

## A public test, written down on 3 November 2026

- By 5 March 2027 (MHLW preliminary report for December 2026): 2026 at 693,300 births or more means
  no distinguishable fall this year; below that means a fall late in the year, cause not established.
- By 31 July 2027 (MHLW monthly reports for December 2026 and January 2027): 108 or more boys per
  100 girls in December 2026, or 102 or fewer in January 2027, would point to date-shifting. They
  stood at 117.2 and 99.0 last time; the 22 months before the test ranged from 103.3 to 107.2.

The outcome will be added to the write-up and here under these same rules, whichever way it goes.

## Files

- `fire-horse-births.csv`: every series and effect on the page, in long format (3,080 rows).
- `fire_horse_births.py`: the script that downloads the sources and computes everything.

### Columns

| Column | Meaning |
|---|---|
| `series` | What the row belongs to, e.g. `japan_daily`, `japan_annual`, `year_effect`, `boundary_step`, `find_your_year Japan`, `event SG Chinese`; `_attribution` rows carry each source's required credit |
| `period` | Day, month, year or lunar year the value refers to; for `year_effect` and `boundary_step`, the cell (e.g. `SG Chinese Tiger`, `SG Chinese Tiger enter`); for `_attribution`, the source id |
| `measure` | What the value is: `births`, `boys`, `girls`, `sex_ratio` (boys per 100 girls); for effects `mean_pct`, `lo_pct`/`hi_pct` (95% interval), `plc_p5`/`plc_p95` (placebo range), `n`, `q` (Benjamini–Hochberg) |
| `value` | The number |
| `source` | The publisher and table, or `calc` for our calculation; `calc from sg_singstat` and `calc from hk_csd` mark rows derived from those sources, which stay under their terms (see below) |

## Method, in short

Year effect: log births per day of a year, minus a straight line through the clean years within ±6
(the animals other than Tiger, Dragon, Horse and Goat), with the same statistic for every clean year
as the placebo; all cells form one Benjamini–Hochberg family. Boundary step: in monthly series, the
mean of the six deseasonalised months after Lunar New Year minus the six before. Ethnic control: the
same effect for Chinese births minus Malay and Indian births. Japan's zodiac year is the Gregorian
year; elsewhere the lunar year starts at Lunar New Year. The daily tables were read twice,
independently, by eye from the scans and checked by sums and against the ratios the yearbook prints.
What was fixed in advance and what was not is listed in the script's header. Details, the limits
and the effects table are in the write-up.

## Reproduce

```bash
pip install numpy pandas xlrd           # plus pdftotext (poppler) and curl
python3 fire_horse_births.py fetch      # downloads the sources (about 140 MB, mostly two scanned yearbooks)
python3 fire_horse_births.py compute
python3 fire_horse_births.py validate
python3 fire_horse_births.py export     # writes the CSV and a JSON summary next to the script
```

KOSIS (South Korea) cannot be downloaded by command; the script's header says how the two tables
were saved by hand.

## Sources to credit

- Japan: Source: Portal Site of Official Statistics of Japan (e-Stat), https://www.e-stat.go.jp/ ;
  Vital Statistics (Ministry of Health, Labour and Welfare), processed by StarTarot. Monthly 2026:
  Ministry of Health, Labour and Welfare website (Public Data License 1.0), processed by StarTarot.
- Taiwan: Department of Household Registration, Ministry of the Interior, 出生數及粗出生率 and
  縣市出生死亡結婚離婚; Open Government Data License, version 1.0.
- Malaysia: Department of Statistics Malaysia (OpenDOSM), Annual Live Births by Sex & Ethnicity,
  CC BY 4.0. Calculations by StarTarot.
- Singapore: Contains information from Live-Births By Sex And Ethnic Group, Monthly (M810051)
  accessed on 2026-11-02 from the Singapore Department of Statistics, which is made available under
  the terms of the Singapore Open Data Licence version 1.0, https://data.gov.sg/open-data-licence .
  Aggregated to lunar years by StarTarot; not attributed to or endorsed by the Government.
- Hong Kong: Source: website of the Census and Statistics Department, Hong Kong
  (https://www.censtatd.gov.hk/), and DATA.GOV.HK. Intellectual property rights: Government of the
  Hong Kong Special Administrative Region. Modified by StarTarot where marked (net of births to
  mainland mothers).
- South Korea: 국가데이터처, 「인구동향조사」, KOSIS, https://kosis.kr/ , accessed 2026.11.02.

Our calculations and the rows from Japan, Taiwan and Malaysia are under CC BY 4.0. Rows from
Singapore, Hong Kong and South Korea, and rows calculated from them, stay under their publishers'
own terms, marked row by row in `source`; Singapore's raw monthly series is not redistributed, only
aggregates by lunar year.

## Cite

Matiushenok, V. (2026). On 31 December 1966, Japan recorded two boys for every girl. StarTarot.online.
https://startarot.online/research/fire-horse-japan-births — data CC BY 4.0 except where marked.
