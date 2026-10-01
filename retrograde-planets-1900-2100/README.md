# How often each planet is retrograde, 1900–2100

Full write-up: https://startarot.online/research/retrograde-planets-1900-2100

All 3,660 stations of Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune and Pluto from
1 January 1900 to the end of 2100, computed with Swiss Ephemeris and confirmed with NASA JPL's
DE440 ephemeris (same number of stations for every planet, times within 1.3 minutes).

## Key findings

- Mercury is retrograde 19.1% of the time, about 70 days a year: three times in 171 of the 201
  years and four times in 30 of them (next: 2029). Each retrograde lasts 19.8–24.2 days.
- Venus is the least often retrograde planet (7.2%). From Venus outwards the share grows with
  distance from the Sun, up to 44.1% for Pluto.
- At least one planet is retrograde 93.2% of the time; on average 2.3 are retrograde at once.
  The longest stretch with none ran from 22 January to 21 April 2023 (88 days).
- Seven of the eight are retrograde at once on only four occasions (1944, 1984, 1986, 2082);
  all eight, never.

## Files

- `retrograde-periods.csv`: one row per retrograde period (1,832 rows).
- `retrograde_periods.py`: the script that computes everything; run it to rebuild the CSV.

### Columns

| Column | Meaning |
|---|---|
| `planet` | Mercury … Pluto |
| `station_retrograde_utc` | Station retrograde, UT, rounded to the minute (`YYYY-MM-DDTHH:MMZ`) |
| `station_retrograde_lon_deg`, `station_retrograde_sign` | Apparent geocentric tropical longitude (0–360°) and sign at that station |
| `station_direct_utc`, `station_direct_lon_deg`, `station_direct_sign` | The same for the station direct |
| `duration_days` | Length of the retrograde period in days |
| `arc_deg` | How far the planet moves back |
| `cut_at_range_start`, `cut_at_range_end` | 1 if the period began before 1 January 1900 or ends after 2100; its missing station is then replaced by that boundary |

## Method, in short

Apparent geocentric ecliptic longitude (true equinox of date; for Jupiter to Pluto the centre of
mass of the planet and its moons) from Swiss Ephemeris with its built-in Moshier ephemeris. The
speed is the change of longitude over ±30 minutes, sampled daily; every sign change is refined by
bisection. The same search is repeated independently with Skyfield and JPL DE440. Details, the
agreement table and the limits (conventions that move the exact minute of slow planets' stations,
ΔT for future dates, time zones, sidereal zodiac) are in the write-up.

## Reproduce

```bash
pip install pyswisseph           # the JPL check also needs: pip install skyfield
python3 retrograde_periods.py    # writes retrograde-periods.csv and .json next to itself
```

The JPL check runs only if `de440s.bsp` (or `de440.bsp`) lies next to the script; otherwise it is
recorded as skipped.

## Cite

Matiushenok, V. (2026). How often each planet is retrograde, 1900–2100. StarTarot.online.
https://startarot.online/research/retrograde-planets-1900-2100 — data CC BY 4.0.
