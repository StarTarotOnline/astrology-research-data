# Your real birthday is a day earlier: in 2028 the solar return beats the date for 3 in 5 adults

Full write-up, with a calculator for your own return: https://startarot.online/research/solar-return-before-birthday

A solar return is the instant the Sun gets back to the ecliptic longitude it had at birth. This
study compares the local calendar date of that instant with the birthday: for the world's adults
(UN World Population Prospects 2024 age structure, birth times spread evenly over the day), for
every date of birth from 1901, and for 96 million real births at their recorded time in Brazil
(minute, 2006–2024), Japan (hour, 2015–2024) and the USA (minute, with month and weekday only,
2016–2024).

## Key findings

- In 2028 the Sun comes back early for 60% of the world's adults: 57% the day before the
  birthday, 3% two days before. 37% get it on the day.
- From 1901 to 2099 the Gregorian calendar averages 365.25 days, because 2000 kept its leap day,
  while the tropical year is about 11 minutes shorter. Averaged over each four-year cycle the
  return moves 11.2 minutes earlier against the birth clock time every year (10.4 for January
  birthdays to 12.1 for June). 2100, with no 29 February, resets it.
- Every leap year looks like 2028 (2024 did, 2032 will). The year after a leap year is still 52%
  early; the third year is the low point (15% in 2027).
- The older the person, the earlier the return: 77% of people born in the 1950s get it early in
  2028, and 1 in 10 born 1940–1959 two days early.
- The hour of birth decides most. Among 54 million Brazilian births of 2006–2024, 74% of those
  born between midnight and 6 a.m. get the 2028 return a day early, against 11% of those born
  after 6 p.m.
- Over a lifetime (age 1 to 80, born 1950–2010) the return falls on the birthday itself in 57% of
  the years.
- In every one of 237 countries and territories more than half of adults are early in 2028; the
  ranking follows age (Japan 65.9%, Central African Republic 53.9%).
- The sidereal return (Lahiri) drifts the other way, about 9.2 minutes later a year: in 2028, 67%
  of adults get it on the day, 18% a day or more late, 15% early.

## Files

- `solar-return-before-birthday.csv`: every share behind the page, long format (43,945 rows).
- `cosmic_birthday.py`: the script that computes everything. It reads the birth files of
  `birth_sky.py` from the `real-births-chart-frequencies` folder, which must sit next to it.

### Columns

| Column | Meaning |
|---|---|
| `section` | `real` (recorded births), `model` (every date of a birth year equally), `wpp` (countries and regions with the UN age structure), `wpp_series` (world over return years), `moving` (living in another time zone than the birthplace), `sidereal`, `example` (one person born 15 June 1990) |
| `area` | `BR`, `JP`, `US`, an ISO3 code or `WLD` for UN populations, `model`, or the time zone of the example |
| `group`, `key` | The breakdown and its value: `birth_year`, `birth_month`, `birth_hour_local`, `residence_shift_h`, `aged 18+`, `all ages`, … |
| `return_year` | Year of the solar return |
| `time_profile` | Birth times: `recorded`, `uniform` over the day, `spontaneous` (Brazil's profile of spontaneous labours), `exact` (the example) |
| `zodiac` | `tropical` or `sidereal_lahiri` |
| `outcome_days` | Local date of the return minus the birthday: −2 … +2 |
| `metric`, `value` | `share` (0–1) of the group with that outcome, or `clock_shift_min` for the example |
| `source` | `sinasc`, `jp-vital`, `nchs`, `wpp` or `startarot` (pure astronomy) |

People born on 29 February are counted apart and left out of every share.

## Method, in short

Apparent geocentric longitude of the Sun from Swiss Ephemeris, tropical zodiac (sidereal: Lahiri).
The return in a year is the instant the Sun is back at the birth longitude nearest the birthday,
dated in the time zone of birth with that zone's rules for the year. Hypotheses were committed
before the full count and are printed with their outcomes in the write-up. An independent recount
with its own code and astropy matches the world's adults within 0.02 percentage points.

## Reproduce

```bash
pip install numpy pandas pyarrow pyswisseph
python3 cosmic_birthday.py fetch      # UN WPP single ages, VSOP87D Earth; births through birth_sky.py if missing
python3 cosmic_birthday.py compute
python3 cosmic_birthday.py validate
python3 cosmic_birthday.py export     # writes the CSV and a JSON summary next to the script
```

## Sources to credit

SINASC, Ministério da Saúde / DATASUS (CC BY-ND 3.0: only aggregates are published); e-Stat,
Vital Statistics of Japan, table 0003411915; NCHS Natality public-use files and U.S. Census Bureau
county population estimates; UN DESA Population Division, World Population Prospects 2024
(CC BY 3.0 IGO); Swiss Ephemeris (Astrodienst); VSOP87D, P. Bretagnon and G. Francou (1988).

## Cite

Matiushenok, V. (2026). Your real birthday is a day earlier: in 2028 the solar return beats the date
for 3 in 5 adults. StarTarot.online. https://startarot.online/research/solar-return-before-birthday — data CC BY 4.0.
