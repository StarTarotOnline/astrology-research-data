# Born on your mother's birthday? What 68 million birth records from Mexico and Brazil show

Full write-up: https://startarot.online/research/born-on-mothers-birthday

Every birth certificate in Mexico (SINAC, 2008–2025) and Brazil (SINASC, 2012–2024) carries two dates: the
baby's and the mother's. This study counts how often they fall on the same day and month, against what chance
predicts, and splits the count by how the baby arrived: a C-section booked in advance, an emergency or in-labour
C-section, a vaginal birth with or without induction, a private or a public hospital, a birth at home.

## Key findings

- Mexico, 2024–2025: planned C-sections fall on the mother's birthday 1.36 times as often as chance (95% CI
  1.31–1.43); in private hospitals 1.46, in public hospitals 1.10. Emergency C-sections 1.06, vaginal births
  1.02. The days on either side of the birthday dip (0.94 and 0.92): births were moved onto it.
- Brazil: C-sections done before labour began hit the birthday 1.37 times as often as chance, births after
  spontaneous labour 1.17. The gap, 0.20, shrank from 0.27 in 2012 to 0.08 in 2024.
- Planned C-sections also land on the mother's day of the month in another month 1.10 times as often (Mexico).
- The paperwork ghost: in older records the mother's day and month were often written as the baby's. Mexican
  vaginal births matched the mother's birthday 1.83 times as often as chance in 2008, falling to 1.02 by 2024;
  home births 1.65 before 2024; Brazilian spontaneous births about 1.17 in every year. The excess grows with
  the mother's age and does not copy the certificate date. Raw counts of "babies born on Mom's birthday" in
  birth records are inflated by it.

The hypotheses were written into the script before the full count (only Mexico 2023 was explored); the page
prints the outcome of each, the misses included, and what was decided after the count.

## Files

- `mother-birthday-births.csv`: births by day relative to the mother's birthday, observed and expected, plus
  the same-number and same-sign counts, for each country, kind of delivery and span of years.
- `mother_birthday_births.py`: the script that downloads the certificates and computes every number on the
  page; its docstring gives the method, the registered hypotheses and the decisions taken after the count.

### Columns

| Column | Meaning |
|---|---|
| `country` | `mx` Mexico, `br` Brazil |
| `group` | Kind of delivery, e.g. `mx_cs_planned`, `mx_cs_private`, `mx_vaginal`, `br_cs_prelabour`, `br_vag_spont` |
| `years` | Span of birth years (`except 2023` = the explored year left out; Mexico `2024-2025` = the clean years) |
| `measure` | `offset` (babies born `offset_days` after the mother's birthday), `same_dom_other_month`, `same_sign`, `same_sign_beyond_3_days`, `same_month` |
| `offset_days` | Child's day of the year minus the mother's, −30 to 30 (empty for the other measures) |
| `observed` | Births counted |
| `expected_if_independent` | Births expected if the two birthdays were unrelated, computed within each year and kind of delivery |
| `births_in_group` | All births in the group and span |

The birthday ratio on the page is `observed / expected` at offset 0, divided by the same ratio over offsets 8–30
on both sides.

## Reproduce

```bash
# Python 3.10+ with numpy and pandas (pyarrow, pyreaddbc and dbfread for Brazil)
python3 mother_birthday_births.py fetch      # about 4 GB of zip and dbc files
python3 mother_birthday_births.py scan
python3 mother_birthday_births.py compute
python3 mother_birthday_births.py validate
python3 mother_birthday_births.py export
```

Our download ran on 18 November 2026. `MOM_BIRTHDAY_NULL=1` runs the same count on shuffled mothers' dates: every
ratio then comes out at 1 within its interval.

## Sources to credit

- Mexico: Secretaría de Salud, Dirección General de Información en Salud (DGIS), Nacimientos open data (SINAC),
  dgis.salud.gob.mx. Aggregated counts only.
- Brazil: SINASC, Ministério da Saúde / DATASUS (OpenDataSUS, CC BY-ND 3.0). Aggregated counts only.

## Cite

Matiushenok, V. (2026). Happy birthday, Mom: booked C-sections land on her birthday more often than chance.
StarTarot.online. https://startarot.online/research/born-on-mothers-birthday — data CC BY 4.0.
