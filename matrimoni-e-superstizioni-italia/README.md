# Anno bisesto, anno funesto? 19,1 milioni di matrimoni in Italia, 1960–2024 (Leap year, bad year? 19.1 million weddings in Italy)

Full write-up: https://startarot.online/it/research/matrimoni-e-superstizioni-italia?utm_source=github&utm_medium=data-repo&utm_campaign=night-2026-11-11

Marriages celebrated in Italy by year (1960–2024) and, from 2004 to 2024, by month, rite (religious and civil) and 98 provinces with stable borders (ISTAT, Eurostat): the leap year, Lent, November, May, and retrograde Venus and Mars. Civil unions are not counted. The write-up is in Italian.

## Files

- `italy-marriages.csv`: the dataset behind every number on the page.
- `italy_marriages.py`: the script that downloads the sources and computes everything; its docstring lists the
  columns, the method and every source in detail.

## Reproduce

```bash
pip install numpy pandas   # plus curl
python3 italy_marriages.py fetch
python3 italy_marriages.py compute
python3 italy_marriages.py validate
python3 italy_marriages.py export
```

A copy run outside the StarTarot repository writes its CSV and JSON next to itself.

## Sources to credit

ISTAT, table "Matrimoni per rito e mese di celebrazione" (2004–2024: Italy, regions, provinces, religious and civil marriages). Eurostat demo_nind for 1960–2003.

## Cite

Matiushenok, V. (2026). Anno bisesto, anno funesto? 19,1 milioni di matrimoni in Italia, 1960–2024. StarTarot.online. https://startarot.online/it/research/matrimoni-e-superstizioni-italia — data CC BY 4.0.
