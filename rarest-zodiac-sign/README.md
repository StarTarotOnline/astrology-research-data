# What is the rarest zodiac sign? Sun signs of 710 million births in 55 countries

Full write-up: https://startarot.online/research/rarest-zodiac-sign

The Sun sign of 710,312,124 live births recorded by day or by month in 55 countries, in years
between 1960 and 2024 (each country's own years), tropical and sidereal (Lahiri). 290 million of
them come from births by day (metropolitan France, the USA, Brazil, Japan) and are exact up to the
split of the day of an ingress; the rest are monthly counts spread over days by a method whose
error is measured on the daily countries.

## Key findings

- The rarest signs are Capricorn (7.71% of births) and Sagittarius (7.75%), a tie; the commonest
  are Cancer (8.89%) and Leo (8.82%). For every 100 babies born under Capricorn, 115 are born
  under Cancer.
- Aquarius, often called the rarest sign, is fourth from the bottom (8.07%), mostly because it is
  a short sign: per day it gets an average number of births.
- About half of the gap is astronomy. Earth moves fastest in January, so Capricorn lasts 29.4 days
  and Cancer 31.5; births spread evenly over the calendar would already give 8.06% to 8.61%. The
  rest is the season of births and the holidays (18–38% fewer births on Christmas Day outside
  Japan).
- Exceptions follow the local calendar of births: Brazil and Sweden (over 1960–2024; since 2000
  Sweden too is led by summer signs) peak between March and May; South Korea's commonest sign is
  Aquarius, with a December-to-January jump in births that may be partly a recording effect.
- In the 14 European countries with every year from 1960 to 2019 the commonest signs moved from Aries,
  Taurus, Gemini and Cancer in the 1960s to Cancer, Leo and Virgo in the 2010s.

## Files

- `zodiac-sign-frequency.csv`: one row per country, year, zodiac and sign (2,070 country-years).
- `zodiac_sign_frequency.py`: the script that downloads the sources and computes everything.

### Columns

| Column | Meaning |
|---|---|
| `country_code`, `country` | Country (Eurostat-style two-letter code; `UK` = United Kingdom, `EL` = Greece) |
| `year` | Calendar year of birth |
| `zodiac` | `tropical` or `sidereal` (Lahiri) |
| `sign` | Aries … Pisces |
| `births_estimated` | Births with the Sun in the sign (exact for daily data up to the split of the ingress day; estimated from monthly counts otherwise) |
| `share_pct` | Share of the year's births, % |
| `expected_share_pct` | Share of the year's calendar days with the Sun in the sign, % (no seasonality) |
| `method` | `daily` or `monthly` |
| `source` | Where the counts come from |

## Method, in short

Sun ingresses from Swiss Ephemeris (Moshier), converted to each country's civil time (IANA zone of
the most populous part; for the USA the Central zone, nearest the population-weighted mean).
Births of an ingress day are split by the share of the day before and after the ingress. Monthly counts are spread over days along a mean-preserving monotone cubic
through the cumulative counts, adjusted by a calendar-day and weekday pattern learned from the
daily countries; leaving each daily country out of that pattern and comparing with its exact
answer gives the published error (up to 0.11 points per sign over a whole period). Series by month
of registration are not used (documented ones, plus a working-day test that the script runs on
every series), nor preliminary years, nor years with many births of unknown month or with a broken
monthly profile.
Details, the validation tables and the limits are in the write-up.

## Reproduce

```bash
pip install numpy pandas pyarrow scipy pyswisseph openpyxl pyreaddbc dbfread
python3 zodiac_sign_frequency.py fetch      # downloads the sources (Brazil's FTP is slow)
python3 zodiac_sign_frequency.py compute
python3 zodiac_sign_frequency.py validate
python3 zodiac_sign_frequency.py export     # writes the CSV and a JSON summary next to the script
```

## Sources to credit

Eurostat (`demo_fmonth`, CC BY 4.0); Human Fertility Database, Short-Term Fertility Fluctuations
(CC BY 4.0); INSEE (T79JNAIS, Licence Ouverte); ONS, Births in England and Wales (OGL v3.0);
NCHS natality data via the Google BigQuery natality sample (A. Vehtari's Birthdays case study) and
FiveThirtyEight `births` (CC BY 4.0); SINASC, Ministério da Saúde / DATASUS (CC BY-ND 3.0: only
aggregates are published); e-Stat, Vital Statistics of Japan.

## Cite

Matiushenok, V. (2026). What is the rarest zodiac sign? Sun signs of 710 million births in 55
countries. StarTarot.online. https://startarot.online/research/rarest-zodiac-sign — data CC BY 4.0.
