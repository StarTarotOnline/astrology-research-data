# How often the MC falls in the whole-sign 10th house, by latitude and rising sign

Full write-up: https://startarot.online/research/mc-whole-sign-10th-house

At a given latitude, what are the odds that the Midheaven sits in the tenth sign from the
Ascendant? Computed for latitudes 0–65° N, tropical and sidereal (Lahiri), by rising sign:
2,376,000 charts. Plus a proof that in Porphyry houses intercepted signs appear exactly when the MC
is not in the whole-sign 10th house.

## Key findings

- At the equator the MC is in the whole-sign 10th house in 90.5% of charts; 70.9% at 30° N, 48.8%
  at 45° N, 38.0% at 52° N, 29.5% at 60° N and 23.7% at 65° N.
- From 45° N northward the MC is more often outside the whole-sign 10th than inside it.
- The rising sign matters more than the latitude: with Aries or Pisces rising (tropical) the MC is
  in the 10th sign in every chart at every latitude in the range; with Taurus, Gemini, Capricorn or
  Aquarius rising it never is from 50° N onward.
- In Porphyry houses a chart has intercepted signs if and only if the MC is outside the whole-sign
  10th house; verified on all 2,376,000 charts with no exceptions.

## Files

- `mc-whole-sign-10th.csv`: one row per latitude, zodiac and rising sign (`all` for every sign
  together).
- `mc_whole_sign_10th.py`: the script; run it to rebuild the CSV.

### Columns

`rising_share_pct` is the share of all charts at that latitude with that rising sign;
`mc_in_whole_sign_10th_pct` and `mc_house_1_pct` … `mc_house_12_pct` are shares of the charts in that
row; `porphyry_no_interception_pct` is filled for tropical `all` rows only.

## Reproduce

```bash
pip install pyswisseph
python3 mc_whole_sign_10th.py   # writes the CSV and a JSON summary next to itself
```

## Cite

Matiushenok, V. (2026). How often the MC falls in the whole-sign 10th house, by latitude and
rising sign. StarTarot.online. https://startarot.online/research/mc-whole-sign-10th-house — data CC BY 4.0.
