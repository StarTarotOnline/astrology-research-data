# Ślub w miesiącu z „r”? 4,6 mln ślubów w Polsce dzień po dniu, 2002–2025 (A wedding in a month with an "r"? 4.6 million weddings in Poland, day by day)

Full write-up: https://startarot.online/pl/research/sluby-i-przesady-polska?utm_source=github&utm_medium=data-repo&utm_campaign=night-2026-11-11

Every marriage in Poland from 2002 to 2025, day by day, from GUS (civil and religious with civil effect): May, July without an "r", the 13th, "beautiful" dates, the leap year, the last days of Carnival, Lent and Advent, against Lithuania and Czechia. The write-up is in Polish.

## Files

- `poland-marriages.csv`: the dataset behind every number on the page.
- `poland_marriages.py`: the script that downloads the sources and computes everything; its docstring lists the
  columns, the method and every source in detail.

## Reproduce

```bash
pip install numpy pandas xlrd openpyxl
python3 poland_marriages.py fetch
python3 poland_marriages.py compute
python3 poland_marriages.py validate
python3 poland_marriages.py export
```

A copy run outside the StarTarot repository writes its CSV and JSON next to itself.

## Sources to credit

GUS (Statistics Poland), Baza Demografia, table 30 "Małżeństwa według dnia i miesiąca zawarcia związku małżeńskiego" 2002–2025 and table 14 (months by voivodeship). Controls: Statistics Lithuania (S3R845), CZSO (Demografická příručka 2024, OBY01CRQM), Eurostat demo_nind. The CSV holds Poland only.

## Cite

Matiushenok, V. (2026). Ślub w miesiącu z „r”? 4,6 mln ślubów w Polsce dzień po dniu, 2002–2025. StarTarot.online. https://startarot.online/pl/research/sluby-i-przesady-polska — data CC BY 4.0.
