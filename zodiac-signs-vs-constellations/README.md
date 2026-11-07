# The last true Capricorn was born on 20 January 2024: zodiac signs against the real constellations

Full write-up: https://startarot.online/research/zodiac-signs-vs-constellations

Where the Sun really was for 309,212,768 live births recorded by day in metropolitan France
(1968–2024), England and Wales (1995–2024), the USA (1969–1988, 1994–2014), Brazil (1997–2024)
and Japan (2015–2024): the tropical sign of Western astrology, the sidereal sign (Lahiri) of
Indian astrology, and the official IAU constellation that held the Sun.

## Key findings

- Only 12.3% of these births had the Sun in the constellation of their tropical sign. Every Libra
  had the Sun in Virgo, 99.9% of Geminis in Taurus, 62% of Sagittarians in Ophiuchus.
- By constellation, 4.9% of births fall in Ophiuchus and 1.7% in Scorpius (18.3 against 6.5 days
  a year).
- Each tropical sign overlaps its namesake constellation for a shrinking stretch at the end of the
  sign (about 20 minutes less every year). The overlaps closed for Libra in 1438, Scorpio in
  1926–27, Gemini on 21 June 1989 and Capricorn on 20 January 2024 (13:55–14:07 UTC); Leo's, the
  last, closes in 2852–53.
- Around AD 1 the signs and constellations agreed for 83% of the year, by today's boundaries.
  The sidereal sign agrees with the constellation for 80% of these births.

## Files

- `zodiac-constellations.csv`: births by country, year, tropical sign, sidereal sign and
  constellation.
- `zodiac_constellations.py`: the script that computes everything (it reads the daily series
  through `zodiac_sign_frequency.py` from the `rarest-zodiac-sign` folder, which must sit next
  to it).

### Columns

| Column | Meaning |
|---|---|
| `country` | France (metropolitan), England and Wales, USA, Brazil, Japan |
| `year` | Calendar year of birth |
| `tropical` | Tropical sign (from the true equinox of date) |
| `sidereal` | Sidereal sign, Lahiri ayanamsa |
| `constellation` | IAU constellation of the Sun (Delporte 1930 boundaries) |
| `births_estimated` | Births of that year in that combination; a day with a change is split by the share of the day, uniform time (Brazil from 2006: by recorded hour) |
| `source` | Where the daily counts come from |

## Method, in short

Sun from Swiss Ephemeris (Moshier), apparent, on the mean equator of date, precessed to B1875 and
looked up in Roman (1987) as shipped with astropy; a second precession route (IAU 1976 angles) is
checked against it. Last overlaps are tested one minute before the Sun leaves each tropical sign,
every year from about 2900 BC to AD 2998; years that move under other conventions (nutation,
geometric Sun) are given as two years.

## Reproduce

The script reads the daily birth series through `zodiac_sign_frequency.py`: copy that script from
the `rarest-zodiac-sign` folder next to this one, run its fetch steps, and point `$ZODIAC_DATA` at
the same folder for both.

```bash
pip install numpy pandas pyarrow pyswisseph astropy openpyxl
for s in fetch-france fetch-ew fetch-us fetch-br fetch-jp; do python3 zodiac_sign_frequency.py $s; done
python3 zodiac_constellations.py compute
python3 zodiac_constellations.py validate
python3 zodiac_constellations.py export     # writes the CSV and a JSON summary next to the script
```

## Sources to credit

INSEE, births by day, metropolitan France (T79JNAIS, Licence Ouverte); ONS, Births in England and
Wales, table 12 (OGL v3.0); NCHS natality data via the Google BigQuery natality sample (A. Vehtari's
Birthdays case study) and CDC/SSA births by day via FiveThirtyEight `births` (CC BY 4.0); SINASC,
Ministério da Saúde / DATASUS (CC BY-ND 3.0: only aggregates are published); e-Stat, Vital
Statistics of Japan, table 0003411915. Constellation boundaries: E. Delporte (IAU, 1930) and
N. G. Roman (1987), PASP 99, 695 (CDS VI/42). Swiss Ephemeris; astropy.

## Cite

Matiushenok, V. (2026). The last true Capricorn was born on 20 January 2024: zodiac signs against
the real constellations. StarTarot.online. https://startarot.online/research/zodiac-signs-vs-constellations — data CC BY 4.0.
