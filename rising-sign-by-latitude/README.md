# How common is each rising sign, by latitude

Full write-up: https://startarot.online/research/rising-sign-by-latitude

The share of every Ascendant (rising) sign at each degree of latitude from the equator to 65° N,
tropical and sidereal (Lahiri), with rising times: 2,376,000 computed charts.

## Key findings

- At the equator every rising sign is almost equally common: 7.8% for the rarest, 8.9% for the
  commonest.
- The spread grows with latitude. In the northern hemisphere the rarest rising signs are Aries and
  Pisces: 5.9% each at 30° N, 3.6% at 52° N (London, Berlin), 2.0% at 60° N, 0.6% at 65° N.
- From 23° N up the commonest is always one of Leo, Virgo, Libra or Scorpio; the
  commonest-to-rarest ratio is 3.3 at 52° N and 26.5 at 65° N.
- In the southern hemisphere the table is the same with every sign replaced by its opposite.
- If every birth happened at the same clock hour, no sign's share would move by more than 0.34
  points.

## Files

- `rising-sign-by-latitude.csv`: one row per latitude (0–65), zodiac and sign.
- `rising_sign_by_latitude.py`: the script; run it to rebuild the CSV.

### Columns

`latitude_deg` (0–65, northern hemisphere), `zodiac` (`tropical` or `sidereal_lahiri`), `sign`,
`share_pct` (share of all charts at that latitude with that rising sign), `rising_hours` (the same
share as sidereal hours of the day). For a southern latitude take the row of the opposite sign.

## Reproduce

```bash
pip install pyswisseph
python3 rising_sign_by_latitude.py   # writes the CSV and a JSON summary next to itself
```

The cross-check against the MC study runs only if `mc-whole-sign-10th.csv` lies next to the script.

## Cite

StarTarot.online (2026). How common is each rising sign, by latitude.
https://startarot.online/research/rising-sign-by-latitude — data CC BY 4.0.
