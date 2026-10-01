# How hospital birth times reshape the birth chart: 95.7 million births in Brazil, Japan and the USA

Full write-up: https://startarot.online/research/real-births-chart-frequencies
Em português, o estudo do Brasil: https://startarot.online/pt/research/mapa-astral-nascimentos-reais-brasil

"How rare is my chart" answers usually assume that babies are born at any hour equally often. They
are not: births cluster in working hours. This study computes the sky for every recorded birth in
Brazil (53.6 million, 2006–2024), Japan (8.5 million, 2015–2024) and the USA (33.6 million,
2016–2024) and publishes how often each chart feature really occurs, next to what astronomy alone
would give.

## Key findings

- Most babies born in 2024 had a day chart (the Sun above the horizon): 63.6% in Brazil, 67.5% in
  Japan and 59.3% in the USA, against 50% if births were spread evenly over the day.
- It is not caesareans alone: Japan has the highest share of day charts with about one caesarean
  in five births. In Brazil about two thirds of the rise since 2006 comes from the larger
  caesarean share.
- For the Sun, each Placidus house is one sixth of its own day or night, so the Sun's house works
  as a clock. The commonest house for the Sun is the 10th in Brazil (1.53 times its share with
  even birth times) and the 8th in Japan (1.77 times).
- Over a whole year the hour of birth barely changes how common each Ascendant sign or Moon sign
  is (at most 0.28 and 0.12 percentage points), but it reshapes combinations tied to the date:
  in Brazil some Sun–Ascendant pairs are 0.53 times and others 1.55 times as common as with even
  birth times.
- The expected share of Mars in Michel Gauquelin's key sectors for babies born in a single year
  is anywhere from 12.4% to 22.4% in Japan (14.8–19.7% in Brazil), not a fixed one sixth.

Nothing here describes people born outside these countries and years.

## Files

- `real-births-chart-frequencies.csv`: 113,978 rows, long format (7.4 MB).
- `birth_sky.py`: the script that downloads the registers and computes everything.

### Columns

| Column | Meaning |
|---|---|
| `country` | `BR`, `JP` or `US` |
| `scope` | `national`, or a Brazilian state as `UF` + IBGE code (`UF35` = São Paulo) |
| `year` | Year of birth (BR 2006–2024, JP 2015–2024, US 2016–2024) |
| `rung` | Which comparison the row belongs to, see below |
| `feature` | Chart feature, see below |
| `category` | Value of the feature (a sign, a house number, a sector, an hour, `yes`) |
| `share_pct` | Share of births of that country, scope, year and rung with this category |
| `weighted_births` | Number of births behind the share (fractional where births are spread over dates or places) |

### Rungs: four comparisons built for the same places

| `rung` | What it holds fixed |
|---|---|
| `B1_period_astronomy` | The same number of births on every date and at every hour |
| `B2_real_dates` | The real number of births on each date, spread evenly over the hours |
| `B3_spontaneous_profile` | The real dates, spread over the day like births that were not induced |
| `B4_real` | Every birth at its recorded time |

### Features

- `sect_day` (Sun above the horizon, the same as the Sun in Placidus houses 7–12),
  `sect_day_whole` (whole-sign houses 7–12), `sect_day_apparent` (apparent sunrise and sunset).
- For the Sun, Moon, Mercury, Venus, Mars, Jupiter and Saturn: `<planet>_sign` (tropical),
  `<planet>_house` (Placidus), `<planet>_whole` (whole-sign house), `<planet>_gq` (Gauquelin's 36
  sectors; sector 1 starts at rising, 10 at culmination).
- `asc_sign`, `mc_sign`; Lahiri sidereal `sun_sign_sid`, `moon_sign_sid`, `asc_sign_sid`.
- `sun_asc`: Sun sign × Ascendant sign pairs.
- `smv_all_above`, `smv_any_above`, `smv_all_upper`, `smv_any_upper`: the Sun, Mercury and Venus
  above the horizon, or in houses 7–12.
- `birth_hour_*`: the share of births in each clock hour, by type of birth; `caesarean_share`.

## Sources to credit

- **Brazil**: SINASC, Ministério da Saúde / DATASUS, 2006–2024. OpenDataSUS publishes the register
  under CC BY-ND 3.0; this dataset contains aggregates only, never individual records.
- **Japan**: Vital Statistics, e-Stat table 0003411915, 2015–2024 (Government of Japan Standard
  Terms of Use).
- **USA**: NCHS Natality public-use files 2016–2024 and Census Bureau county data (public domain).
  The US files carry no day of month and no place, so dates and places are imputed; the error of
  that imputation is measured on Brazilian data with the same information removed and published
  with the US numbers in the write-up.

## Reproduce

```bash
pip install numpy pandas pyarrow pyswisseph pyreaddbc dbfread timezonefinder
python3 birth_sky.py fetch      # several GB into ./birth-sky-data; Brazil's FTP is slow
python3 birth_sky.py compute
python3 birth_sky.py export     # writes the CSV and a JSON summary next to the script
```

The script also needs `curl` and `unzip` on PATH. `python3 birth_sky.py selftest` checks its
closed formulas against Swiss Ephemeris.

## Cite

Matiushenok, V. (2026). How hospital birth times reshape the birth chart: 95.7 million births in
Brazil, Japan and the USA. StarTarot.online.
https://startarot.online/research/real-births-chart-frequencies — data CC BY 4.0.
