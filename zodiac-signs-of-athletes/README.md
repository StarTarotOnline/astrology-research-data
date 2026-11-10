# The zodiac sign of champions is Aquarius, Libra or Taurus: 730,728 athletes, and the rulebook that decides

Full write-up: https://startarot.online/research/zodiac-signs-of-athletes?utm_source=github&utm_medium=data-repo&utm_campaign=night-2026-11-11

Exact birthdays of 730,728 athletes in 25 sports from Wikidata (born 1950–2007) against official births by month: which Sun signs are over-represented in each sport and country, why the answer follows youth-sport cutoff dates, and 56 predictions written down before the count. The CSV holds observed and expected counts by group, cohort and month or sign; no individual people are listed.

## Files

- `athlete-birth-signs.csv`: the dataset behind every number on the page.
- `athlete_birth_signs.py`: the script that downloads the sources and computes everything; its docstring lists the
  columns, the method and every source in detail.

## Reproduce

```bash
pip install numpy pandas pyreadr
python3 athlete_birth_signs.py fetch
python3 athlete_birth_signs.py compute
python3 athlete_birth_signs.py validate
python3 athlete_birth_signs.py export
```

A copy run outside the StarTarot repository writes its CSV and JSON next to itself.

## Sources to credit

Wikidata (CC0), queried through QLever on 28 October 2026. Lahman Baseball Database (SABR, CC BY-SA 3.0), used only as a check of Wikidata's coverage; only aggregates are quoted, nothing from it is redistributed. Official births by month: Eurostat demo_fmonth; Human Fertility Database, Short-Term Fertility Fluctuations (CC BY 4.0); NCHS and SSA daily US births; INSEE daily French births. Youth-sport cutoff dates: as cited on the write-up page and in the script.

## Cite

Matiushenok, V. (2026). The zodiac sign of champions: birthdays of 730,728 athletes, and the rulebook behind them. StarTarot.online. https://startarot.online/research/zodiac-signs-of-athletes — data CC BY 4.0.
