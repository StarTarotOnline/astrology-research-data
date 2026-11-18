# Shipyards once refused to launch on a Friday. Then they started dodging the 13th

Full write-up: https://startarot.online/research/ship-launch-friday-superstition

"Never launch a ship on a Friday" is an old sailors' rule. This study counts it in the calendar: the weekday
of every ship launch in Wikidata dated to the day, 1800–2025 (20,468 ships, most of them warships), and then
asks whether ships launched on a Friday were lost more often, in two independent loss records.

## Key findings

- In 1860–1899 only 6.4% of launches fell on a Friday and 26.6% on a Saturday: Friday got 0.40 times the
  launches of an average Monday to Thursday (95% CI 0.32–0.49). Every big navy shows the dip.
- Official openings of the same years dipped on Fridays too, but much less; births recorded in Wikidata show
  no Friday dip at all, so the dates carry no weekday artefact.
- The 13th of the month was not avoided before 1900 (1.00), then got about half the usual launches in
  1900–1945 (0.54) and stayed below normal until 2000.
- Friday ships were not lost more often: compared with ships of the same launch year, navy and type, the odds
  ratio is 0.95 (0.73–1.25) in Wikidata loss records and 0.95 (0.79–1.14) in Wikipedia's lists of shipwrecks.
  A raw count makes Friday ships look luckier, because Friday launches became common only after 1946.

The hypotheses were written into the script before the final count; the page prints the outcome of each.

## Files

- `ship-launch-days.csv`: one row per ship.
- `ship_launch_days.py`: the script that fetches the sources and computes every number on the page; its
  docstring gives the method, the registered hypotheses and what was changed after the count.

### Columns

| Column | Meaning |
|---|---|
| `qid` | Wikidata item of the ship |
| `launch_date` | Launch date (Gregorian, day precision) |
| `weekday` | Weekday of the launch |
| `type` | Broad type from P31 and its parent classes |
| `operator_group` | Operator at launch (navies with fewer than 50 ships grouped) |
| `lost_wikidata` | 1 if Wikidata records a non-deliberate loss |
| `deliberate_wikidata` | 1 if the recorded end was deliberate (scuttling, target, weapons test) |
| `loss_date_wikidata` | Date of the loss event, if any |
| `in_wikipedia_shipwreck_list` | 1 if the ship is named in the ship cell of a row of an English Wikipedia shipwreck list from its launch month on |
| `first_list_month` | Month of the first such list |
| `has_enwiki_article` | 1 if the ship has an English Wikipedia article (needed for the list comparison) |

## Reproduce

```bash
# Python 3.10+, standard library only
python3 ship_launch_days.py fetch      # Wikidata through QLever + Wikipedia API, about half an hour
python3 ship_launch_days.py compute
python3 ship_launch_days.py validate
python3 ship_launch_days.py export
```

Our pull ran on 17 November 2026. A new pull reads Wikidata as it is on its own day, so counts can drift.
No casualty data is read or used.

## Sources to credit

- Wikidata (CC0), queried through the QLever endpoint of the University of Freiburg, 17 November 2026.
- English Wikipedia, chronological lists of shipwrecks (CC BY-SA 4.0), read through the MediaWiki API on the
  same date: only which ship each row names is used.

## Cite

Matiushenok, V. (2026). Shipyards once refused to launch on a Friday. Then they started dodging the 13th.
StarTarot.online. https://startarot.online/research/ship-launch-friday-superstition — data CC BY 4.0.
