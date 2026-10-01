# Astrology research data: computed answers, with scripts and CSV

Small, reproducible studies of questions astrologers ask about the sky, each computed from scratch
and published with its script and data. Each study also has a full write-up
on [startarot.online/research](https://startarot.online/research).

| Study | What it answers | Data |
|---|---|---|
| [How common is each rising sign, by latitude](rising-sign-by-latitude/) | Share of every Ascendant sign at latitudes 0–65°, tropical and sidereal (Lahiri), with rising times. | [rising-sign-by-latitude.csv](rising-sign-by-latitude/rising-sign-by-latitude.csv) |
| [How often the MC falls in the whole-sign 10th house](mc-whole-sign-10th-house/) | Odds that the Midheaven is in the tenth sign from the Ascendant, by latitude and rising sign, and why that is exactly when Porphyry charts have intercepted signs. | [mc-whole-sign-10th.csv](mc-whole-sign-10th-house/mc-whole-sign-10th.csv) |
| [How often each planet is retrograde, 1900–2100](retrograde-planets-1900-2100/) | All 3,660 stations of Mercury through Pluto, confirmed with NASA JPL DE440: the share of time each planet is retrograde, how many are retrograde at once, and every retrograde period. | [retrograde-periods.csv](retrograde-planets-1900-2100/retrograde-periods.csv) |
| [How hospital birth times reshape the birth chart](real-births-chart-frequencies/) | How often each chart feature really occurs among 95.7 million recorded births in Brazil, Japan and the USA, against what astronomy alone would give: day charts, the Sun's house, Sun–Ascendant pairs, Mars in the Gauquelin sectors. | [real-births-chart-frequencies.csv](real-births-chart-frequencies/real-births-chart-frequencies.csv) |

Every number in a study comes from its script: the scripts need Python 3 and
[`pyswisseph`](https://pypi.org/project/pyswisseph/) and write their CSV (and a JSON summary)
next to themselves. The study of real births also downloads several gigabytes of public birth
registers; its folder lists what it needs. Nothing here says what an astrological placement means;
the studies are about the geometry, the astronomy and, in the last one, when people are born.

Related: [a structured dataset of the 78 Rider–Waite–Smith tarot cards](https://github.com/StarTarotOnline/tarot-rws-dataset)
with Waite's meanings and the Golden Dawn correspondences (DOI
[10.5281/zenodo.21381779](https://doi.org/10.5281/zenodo.21381779)).

## Licence

Data and documentation: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Scripts: MIT.
See [NOTICE](NOTICE), [LICENSE](LICENSE) (CC BY 4.0) and [LICENSE-CODE](LICENSE-CODE) (MIT).
The study of real births is built from public registers of Brazil, Japan and the USA; credit
them together with the dataset, as listed in [its folder](real-births-chart-frequencies/#sources-to-credit).

## Citation

Cite the study you used, e.g.:

> Matiushenok, V. (2026). How common is each rising sign, by latitude. StarTarot.online.
> https://startarot.online/research/rising-sign-by-latitude

## About

Published by [StarTarot](https://startarot.online/), a tarot and astrology website in nine
languages. Questions and corrections: issues here or help@startarot.online.
