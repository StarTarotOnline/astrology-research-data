# Можно ли жениться в високосный год? 36,2 млн свадеб в России, 1990–2023 (Is it bad luck to marry in a leap year? 36.2 million weddings in Russia)

Full write-up: https://startarot.online/ru/research/svadby-i-primety-rossiya?utm_source=github&utm_medium=data-repo&utm_campaign=night-2026-11-11

Marriages registered in Russia by year (1990–2023), by month (1990, 1995, 2000 and 2005–2022) and in 80 regions, all from Rosstat: the leap year and the year before it, May, Great Lent, Krasnaya Gorka and retrograde Venus. Registrations by the civil registry (ZAGS), where the couple registered. The write-up is in Russian.

## Files

- `russia-marriages.csv`: the dataset behind every number on the page.
- `russia_marriages.py`: the script that downloads the sources and computes everything; its docstring lists the
  columns, the method and every source in detail.

## Reproduce

```bash
pip install numpy pandas openpyxl xlrd   # plus bsdtar, 7z and antiword/textutil, see the script
python3 russia_marriages.py fetch
python3 russia_marriages.py compute
python3 russia_marriages.py validate
python3 russia_marriages.py export
```

A copy run outside the StarTarot repository writes its CSV and JSON next to itself.

## Sources to credit

Federal State Statistics Service (Rosstat): Demographic Yearbook of Russia (editions 2002–2023), the annual and quarterly bulletins "Natural movement of the population" (regions 2007–2023), "Regions of Russia" 2002–2007 and volume 5 of the 2020 census. National series as Rosstat publishes them.

## Cite

Matiushenok, V. (2026). Можно ли жениться в високосный год? 36,2 млн свадеб в России, 1990–2023. StarTarot.online. https://startarot.online/ru/research/svadby-i-primety-rossiya — data CC BY 4.0.
