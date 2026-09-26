# Astrology research data: computed answers, with scripts and CSV

Small, reproducible studies of questions astrologers ask about the sky, each computed from scratch
with Swiss Ephemeris and published with its script and data. Each study also has a full write-up
on [startarot.online/research](https://startarot.online/research).

| Study | What it answers | Data |
|---|---|---|
| [How common is each rising sign, by latitude](rising-sign-by-latitude/) | Share of every Ascendant sign at latitudes 0–65°, tropical and sidereal (Lahiri), with rising times. | [rising-sign-by-latitude.csv](rising-sign-by-latitude/rising-sign-by-latitude.csv) |
| [How often the MC falls in the whole-sign 10th house](mc-whole-sign-10th-house/) | Odds that the Midheaven is in the tenth sign from the Ascendant, by latitude and rising sign, and why that is exactly when Porphyry charts have intercepted signs. | [mc-whole-sign-10th.csv](mc-whole-sign-10th-house/mc-whole-sign-10th.csv) |

Every number in a study comes from its script: the scripts need Python 3 and
[`pyswisseph`](https://pypi.org/project/pyswisseph/) and write their CSV (and a JSON summary)
next to themselves. Nothing here says what an astrological placement means; the studies are about
the geometry and the astronomy.

Related: [a structured dataset of the 78 Rider–Waite–Smith tarot cards](https://github.com/StarTarotOnline/tarot-rws-dataset)
with Waite's meanings and the Golden Dawn correspondences (DOI
[10.5281/zenodo.21381779](https://doi.org/10.5281/zenodo.21381779)).

## Licence

Data and documentation: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Scripts: MIT.
See [NOTICE](NOTICE), [LICENSE](LICENSE) (CC BY 4.0) and [LICENSE-CODE](LICENSE-CODE) (MIT).

## Citation

Cite the study you used, e.g.:

> StarTarot.online (2026). How common is each rising sign, by latitude.
> https://startarot.online/research/rising-sign-by-latitude

## About

Published by [StarTarot](https://startarot.online/), a tarot and astrology website in nine
languages. Questions and corrections: issues here or help@startarot.online.
