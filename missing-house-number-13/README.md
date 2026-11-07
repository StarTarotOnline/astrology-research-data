# Where did house number 13 go? In Zurich, 56% of the streets with a 9, 11, 15 and 17 have no 13

Full write-up, with a lookup for your city: https://startarot.online/research/missing-house-number-13

43 million addresses in the official address registers of fifteen countries. For every street that
has a 9, an 11, a 15 and a 17, is there a 13 (in any form: 13, 13a, 13 bis)? The same question is
asked of every other odd number from 5 to 43 on its own neighbours, and those nineteen numbers are
the control group.

## Key findings

- In France and Switzerland 13 is the most skipped odd number from 5 to 43. France: missing on
  7.4% of the streets where it should be, against 4.8% for the other odd numbers. Switzerland:
  18.6% against 8.4%.
- Zurich skips 13 on 56% of eligible streets (160 of 287; other numbers 12%), Basel 41%,
  Winterthur 38%, Limoges 40%. 27 French villages have no 13 on any eligible street.
- Paris uses "11 bis": on 45% of Paris streets without a 13 the house before it is an 11 bis or
  11 ter, against 10% on streets that kept their 13. The 8th arrondissement skips 27%, the 16th
  20%, the 11th 1%.
- Newer streets skip more: +1.5 extra gaps at 13 per 100 streets for streets in the tax office's
  street file since 1987–88, +5.1 for streets added since 2010.
- Madrid, Prague and Bologna show no clear gap at 13. Milan skips 13 and Italy's unlucky 17,
  Taipei 13 and its unlucky 4.
- No discount: against its neighbours on the same street, a No. 13 in France sells for 0.26% less
  per square metre [−0.81; +0.30] over 40,697 sales of a 13.
- The gaps are real, not register errors: France's separate record of property sales (DVF,
  2021–2025) shows a sale of a No. 13 on 2.3% of the streets where the address register has no 13,
  against a No. 11 on 18%.

## Files

- `house-number-13.csv`: one row per area and number (9,640 rows).
- `house_number_13.py`: the script that downloads every register and computes everything.

### Columns

| Column | Meaning |
|---|---|
| `area_type` | `national`, `region`, `department`, `canton`, `language area`, `city`, `district`, plus the special tables (`consecutive` numbering, `sales: new builds 2024`, `price effect (DVF, %)`) |
| `country` | ISO country code |
| `area_id`, `area_name` | The area within that table |
| `number` | The house number tested |
| `eligible_streets` | Streets that have the four neighbouring numbers (N−4, N−2, N+2, N+4) |
| `missing` | Of those, streets where N is absent in every form |
| `share_pct` | `missing` / `eligible_streets`, % |
| `source` | Register id (see the sources below) |

## Method, in short

A street is the register's own street id; a number counts as present with any suffix. For a number N
a street is eligible when N−4, N−2, N+2 and N+4 are all present; the background is the mean share
of the 19 other odd numbers 5–43 on the same streets, and areas are compared by the excess of 13
over it. Hypotheses were written down before the full count and are printed with their outcomes in
the write-up, including the two that did not hold (cities do not skip more than villages; there is
no price discount). Intervals: cluster bootstrap over communes for countries and regions, binomial
errors for cities.

## Reproduce

```bash
pip install numpy pandas
python3 house_number_13.py fetch      # every register, about 2.3 GB
python3 house_number_13.py compute
python3 house_number_13.py validate
python3 house_number_13.py export     # writes the CSV and a JSON summary next to the script
```

## Sources to credit

Base Adresse Nationale (IGN, DINUM, communes), DGFiP TOPO and DVF (geo-dvf, Etalab): Licence Ouverte
2.0. swisstopo, official building address directory (swisstopo OGD terms, source named). ČÚZK RÚIAN
(CC BY 4.0). Kartverket, Matrikkelen-Adresse (CC BY 4.0). Geobasis NRW, Gebäudereferenzen
(dl-de/zero-2-0). Registrų centras, address register (open data, source named). GUGiK, PRG address
points. Gemeente Amsterdam, BAG (CC0). BOSA / BeST, Brussels (CC BY 4.0). Helsinki region address
list (CC BY 4.0). Ayuntamiento de Madrid, callejero (CC BY 4.0). Comune di Milano (CC BY) and Comune
di Bologna (CC BY 4.0). ФНС России, ГАР, region 78 (open data of the FNS). DataSF, EAS (PDDL 1.0).
Taipei City Government, door-plate data (Open Government Data License Taiwan 1.0). Contains HM Land
Registry data © Crown copyright and database right 2026, licensed under the Open Government Licence
v3.0. Contains information from HDB Property Information accessed on 2026-11-04 from data.gov.sg,
made available under the Singapore Open Data Licence version 1.0. Department outlines:
gregoiredavid/france-geojson (from IGN/INSEE data, Licence Ouverte).

## Cite

Matiushenok, V. (2026). Where did house number 13 go? In Zurich, 56% of the streets with a 9, 11, 15
and 17 have no 13. StarTarot.online. https://startarot.online/research/missing-house-number-13 — data CC BY 4.0.
