# On 6/6/06, one American birth in seven was missing: the birthdays parents and doctors pick and avoid

Full write-up: https://startarot.online/research/chosen-and-avoided-birthdays

292 million births counted day by day: the USA (1969–1988 and 1994–2014), France (1968–2024), England and
Wales (1995–2024), and the birth certificates of Mexico (2008–2025) and Brazil (2011–2024), which also say how
the baby arrived. The study measures how far the calendar of births bends around days that mean something to
people: Friday the 13th, 1 April, Halloween, Valentine's Day, 29 February, Christmas, repeating dates such as
08.08.08, and 06.06.06. It also keeps the hour of birth, the weekend and the season.

## Key findings

- 06.06.06 was one of the emptiest ordinary days in two decades: the USA had 15% fewer births than the Tuesdays
  around it (95% interval 0.82–0.88), roughly 1,600 to 2,500 births short. Of 6,762 ordinary days in 1994–2014,
  one had a lower ratio.
- Repeating dates gain births: 07.07.07, 08.08.08, 09.09.09, 10.10.10 and 12.12.12 each brought 12 to 17% more
  American births than an ordinary day of the same weekday. 11.11.11 was Veterans Day; it had 22% more births
  than other Veterans Days.
- Friday the 13th: USA 1994–2014, all births, −6.0%; C-sections in Mexican private hospitals −13.6%; Brazilian
  C-sections before labour −10.0%; births after spontaneous labour in Brazil +0.4% (noise).
- 29 February is skipped where the day is booked: C-sections in Mexican private hospitals fall to 0.53 of an
  ordinary day and Brazilian C-sections before labour to 0.69, while Brazilian births after spontaneous labour
  stay at 0.98. In the USA the whole day is down 8.2%.
- Christmas is the limit: planned C-sections in Mexico 0.21 of an ordinary day, Brazilian C-sections before
  labour 0.40, all American births 0.60 in 1994–2014.
- The hour has a schedule too: American births peak at 8 a.m., with 1.53 times the babies of an even hour;
  births planned at home peak at 2 a.m.
- France and England and Wales joined in only a little: their repeating dates from 07.07.07 to 12.12.12 come to
  +2.6% and +2.5% together, below the +3% written down before counting.

Fifteen expectations were written into the script and committed before the full count; six were written after
a rough look at some of the data and say so. Four did not hold, and the page prints all of them, together with
what was decided after the count (`ADDED_AFTER_COUNT` in the script).

## Files

- `chosen-birthdays.csv`: every ratio of single dates and groups of dates behind the page, with its 95%
  interval and the births behind it.
- `chosen_birthdays.py`: the script that downloads the daily series, reads the certificates and computes every
  number on the page; its docstring gives the method, the registered hypotheses and the decisions taken after
  the count.

### Columns

| Column | Meaning |
|---|---|
| `series` | Series key: `us_1969`, `us_1994`, `fr`, `ew`, `mx_all`, `mx_cs_private`, `mx_vaginal`, `br_cs_prelabour`, `br_vag_spont`, … |
| `country` | `us`, `fr`, `ew` (England and Wales), `mx`, `br` |
| `group` | Births in the series, e.g. `all births`, `C-sections, private hospitals`, `vaginal births after spontaneous labour` |
| `years` | Span of birth years |
| `measure` | `day 12/13/14 of the month` (by weekday, plus `not Friday`), `fixed date`, `placebo date`, `public holiday`, `repeating date`, `repeating date against the same holiday in other years` |
| `date_or_weekday` | The weekday, the date label (`leap_day`, `april_fools`, `halloween`, `christmas_day`, `placebo_sep_22`, …; `_weekdays` = the same date on weekdays only) or the ISO date |
| `ratio` | Births on the day(s) divided by the mean of the same weekday one to three weeks either side |
| `lower_95`, `upper_95` | 95% interval of the ratio |
| `days` | Days in the group |
| `births`, `expected` | Births counted, and births expected from the neighbouring weeks |

A repeating date that is itself a public holiday (01.01.01 everywhere, 11.11.11 in the USA and France) has no ratio of its own; its
row `repeating date against the same holiday in other years` gives the day's ratio divided by the mean ratio of
that holiday in the years when the same date was a holiday too, without an interval.

## Method, in short

Every day is compared with the same weekday one, two and three weeks before and after it, skipping neighbours
that are holidays, days around Christmas and New Year, or dates the study tests. Intervals of groups of days come
from families of dates that mean nothing in the same series (2.5th and 97.5th percentiles); four placebo dates
(14 March, 18 June, 22 September, 24 October), kept out of those families, check them. Where the certificates
say how the baby arrived, births after spontaneous labour are the control (in Mexico, vaginal births, which
include inductions: a rougher control). The American series are all births: they do not say which were booked.

## Reproduce

```bash
# Python 3.10+ with numpy and pandas (pyarrow for the Brazilian cache)
python3 chosen_birthdays.py fetch      # the four daily series (a few MB)
python3 chosen_birthdays.py scan       # one pass over the Mexican and Brazilian certificates, about 20 minutes
python3 chosen_birthdays.py compute
python3 chosen_birthdays.py validate
python3 chosen_birthdays.py export     # writes the CSV and a JSON summary next to the script
```

The Mexican and Brazilian certificates are the ones `mother_birthday_births.py` downloads (folder
`born-on-mothers-birthday`): that script must sit next to this one, and its data folder is read from
`$MOM_BIRTHDAY_DATA`. The hours of birth in the USA are copied from `real-births-chart-frequencies.json`, the
summary that `birth_sky.py` (folder `real-births-chart-frequencies`) writes; put it next to the script, or the
American hours are left out. Our download ran on 22 November 2026.

## Sources to credit

- USA, births per day 1969–1988: NCHS natality files summed by day, from A. Vehtari's "Birthdays" case study
  (github.com/avehtari/casestudies).
- USA, births per day 1994–2014: FiveThirtyEight `births` (CC BY 4.0), from CDC/NCHS and the Social Security
  Administration.
- France: INSEE, births per day (T79jnais).
- England and Wales: Office for National Statistics, birth registrations (Open Government Licence v3.0).
- Mexico: Secretaría de Salud, Dirección General de Información en Salud (DGIS), Nacimientos open data (SINAC).
  Aggregated counts only.
- Brazil: SINASC, Ministério da Saúde / DATASUS (OpenDataSUS, CC BY-ND 3.0). Aggregated counts only.

## Cite

Matiushenok, V. (2026). On 6/6/06, one American birth in seven was missing. StarTarot.online.
https://startarot.online/research/chosen-and-avoided-birthdays — data CC BY 4.0.
