# Stimmen die Bauernregeln? Wetterdaten von 1.282 DWD-Stationen, 1760–2025 (Does German weather lore hold? 1,282 weather stations)

Full write-up: https://startarot.online/de/research/bauernregeln-wetterdaten?utm_source=github&utm_medium=data-repo&utm_campaign=night-2026-11-11

Daily measurements of 1,282 climate stations of the Deutscher Wetterdienst (1760–2025) against twelve versions of German "Lostag" rules (Siebenschläfer, Medardus, Lichtmess, Mariä Geburt, Petri Stuhlfeier, green Christmas) and against the Ice Saints, the "sheep cold", white Christmas, changes of the Moon and the Hundred-Year Calendar. The CSV has one row per station and measure (late frost and white Christmas by period). The write-up is in German.

## Files

- `germany-weather-lore.csv`: the dataset behind every number on the page.
- `germany_weather_lore.py`: the script that downloads the sources and computes everything; its docstring lists the
  columns, the method and every source in detail.

## Reproduce

```bash
pip install numpy pandas pyswisseph
python3 germany_weather_lore.py fetch
python3 germany_weather_lore.py compute
python3 germany_weather_lore.py validate
python3 germany_weather_lore.py export
```

A copy run outside the StarTarot repository writes its CSV and JSON next to itself.

## Sources to credit

Deutscher Wetterdienst, daily climate records of the German station network (opendata.dwd.de, CC BY 4.0). Moon phases from the Swiss Ephemeris.

## Cite

Matiushenok, V. (2026). Stimmen die Bauernregeln? Wetterdaten von 1.282 DWD-Stationen, 1760–2025. StarTarot.online. https://startarot.online/de/research/bauernregeln-wetterdaten — data CC BY 4.0.
