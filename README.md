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
| [What is the rarest zodiac sign?](rarest-zodiac-sign/) | The Sun sign of 710 million births recorded by day or month in 55 countries, 1960–2024, tropical and sidereal: which signs are rare, which are common, and how much of it is sign length, season and holidays. | [zodiac-sign-frequency.csv](rarest-zodiac-sign/zodiac-sign-frequency.csv) |
| [On 31 December 1966, Japan recorded two boys for every girl](fire-horse-japan-births/) | What the Fire Horse year did to Japan's birth register: 198 boys per 100 girls recorded on the last day of 1966 and 72 on the next, how many girls were moved across New Year and how much of the fall that explains, 2026 against 1966 with a public test for 2027, and the zodiac years in birth series of Singapore, Taiwan, Malaysia, Hong Kong and South Korea. | [fire-horse-births.csv](fire-horse-japan-births/fire-horse-births.csv) |
| [Your real birthday is a day earlier: the solar return in 2028](solar-return-before-birthday/) | When the Sun really gets back to its birth longitude against the calendar birthday: 60% of the world's adults early in 2028, the 11.2-minute drift since 1901, by age, hour of birth, country, sidereal zodiac and 29 February, from 96 million real births and the UN age structure of 237 countries. | [solar-return-before-birthday.csv](solar-return-before-birthday/solar-return-before-birthday.csv) |
| [The last true Capricorn was born on 20 January 2024](zodiac-signs-vs-constellations/) | Where the Sun really was for 309 million births: tropical sign, sidereal sign and IAU constellation, Ophiuchus against Scorpius, and the date each sign stops overlapping the constellation it is named after. | [zodiac-constellations.csv](zodiac-signs-vs-constellations/zodiac-constellations.csv) |
| [Where did house number 13 go?](missing-house-number-13/) | How often 13 is skipped on streets that have a 9, 11, 15 and 17, in 43 million addresses of fifteen countries' official registers: Zurich 56%, Paris's "11 bis", newer streets, and whether a No. 13 sells for less. | [house-number-13.csv](missing-house-number-13/house-number-13.csv) |
| [Not Death, not the Lovers: the tarot card people google most is The World](which-tarot-card-does-the-world-search-for/) | The World first: a year of Google meaning searches for all 78 cards in English and the Major Arcana in seven more languages, in 22 countries, and why a ranking by Google topics misleads. | [tarot-card-search.csv](which-tarot-card-does-the-world-search-for/tarot-card-search.csv) |
| [The zodiac sign of champions is Aquarius, Libra or Taurus: 730,728 athletes, and the rulebook that decides](zodiac-signs-of-athletes/) | Sun signs of 730,728 athletes in 25 sports from Wikidata against official births by month: over-represented signs follow youth-sport cutoff dates; 56 predictions written down before the count. | [athlete-birth-signs.csv](zodiac-signs-of-athletes/athlete-birth-signs.csv) |
| [ChatGPT tarot reading: we asked its model for a card 10,000 times. It pulled The Star 10,000 times](chatgpt-tarot-reading/) | What 22 OpenAI chat models and the `chat-latest` alias pull when asked for a tarot card, through the API: 44,696 answers, The Star in 10,000 of 10,000 on `chat-latest`, a deck that narrows as the models get newer, and how the question, the zodiac sign and the language move the card. | [ai-tarot-draws.csv](chatgpt-tarot-reading/ai-tarot-draws.csv) |
| [Shipyards once refused to launch on a Friday. Then they started dodging the 13th](ship-launch-friday-superstition/) | The weekday of 20,468 ship launches in Wikidata, 1800–2025: Friday got 6.4% of launches in 1860–1899 and Saturday 26.6%, the 13th was avoided from 1900, and Friday ships were not lost more often in two independent loss records. | [ship-launch-days.csv](ship-launch-friday-superstition/ship-launch-days.csv) |
| [Born on your mother's birthday? What 68 million birth records from Mexico and Brazil show](born-on-mothers-birthday/) | Babies born on their mother's birthday against chance, by kind of delivery: planned C-sections 1.36 in Mexico 2024–2025 (private hospitals 1.46), vaginal births at chance, and a paperwork ghost that copied babies' birthdays into their mothers' in older records. | [mother-birthday-births.csv](born-on-mothers-birthday/mother-birthday-births.csv) |
| [On 6/6/06, one American birth in seven was missing: the birthdays parents and doctors pick and avoid](chosen-and-avoided-birthdays/) | 292 million births day by day in the USA, France, England and Wales, Mexico and Brazil: 06.06.06 −15% and 12.12.12 +16% in the USA, Friday the 13th and 29 February lose booked births while births after spontaneous labour stay put, Christmas, and the hour of birth. | [chosen-birthdays.csv](chosen-and-avoided-birthdays/chosen-birthdays.csv) |
| [Можно ли жениться в високосный год? 36,2 млн свадеб в России, 1990–2023](svadby-i-primety-rossiya/) | Marriages in Russia by year, month and 80 regions (Rosstat, 1990–2023): leap years, May, Great Lent and retrograde Venus. Write-up in Russian. | [russia-marriages.csv](svadby-i-primety-rossiya/russia-marriages.csv) |
| [Anno bisesto, anno funesto? 19,1 milioni di matrimoni in Italia, 1960–2024](matrimoni-e-superstizioni-italia/) | Marriages in Italy by year since 1960 and by month, rite and 98 provinces since 2004 (ISTAT, Eurostat): leap years, Lent, November, May, retrograde Venus and Mars. Write-up in Italian. | [italy-marriages.csv](matrimoni-e-superstizioni-italia/italy-marriages.csv) |
| [Ślub w miesiącu z „r”? 4,6 mln ślubów w Polsce dzień po dniu, 2002–2025](sluby-i-przesady-polska/) | Every marriage in Poland 2002–2025, day by day (GUS): months with and without an "r", the 13th, Lent and Advent, against Lithuania and Czechia. Write-up in Polish. | [poland-marriages.csv](sluby-i-przesady-polska/poland-marriages.csv) |
| [Stimmen die Bauernregeln? Wetterdaten von 1.282 DWD-Stationen, 1760–2025](bauernregeln-wetterdaten/) | 1,282 DWD stations, 1760–2025, against twelve German weather-lore rules, the Ice Saints, white Christmas and the Moon. Write-up in German. | [germany-weather-lore.csv](bauernregeln-wetterdaten/germany-weather-lore.csv) |

Every number in a study comes from its script: the scripts need Python 3 and
[`pyswisseph`](https://pypi.org/project/pyswisseph/) and write their CSV (and a JSON summary)
next to themselves. The studies of real births, of zodiac signs, of the solar return, of the constellations and of the
Fire Horse also download public birth statistics, and the house-number study downloads address registers; their
folders list what they need. Nothing here says what an astrological placement means;
the studies are about the geometry, the astronomy, when people are born and what they do because of a sign or a number.

Related: [a structured dataset of the 78 Rider–Waite–Smith tarot cards](https://github.com/StarTarotOnline/tarot-rws-dataset)
with Waite's meanings and the Golden Dawn correspondences (DOI
[10.5281/zenodo.21381779](https://doi.org/10.5281/zenodo.21381779)).

## Licence

Data and documentation: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Scripts: MIT.
See [NOTICE](NOTICE), [LICENSE](LICENSE) (CC BY 4.0) and [LICENSE-CODE](LICENSE-CODE) (MIT).
The studies of real births, of zodiac signs, of the solar return, of the constellations and of the Fire Horse are built
from public birth statistics, and the house-number study from official address registers; credit them together with the
dataset, as listed in their folders ([real births](real-births-chart-frequencies/#sources-to-credit),
[zodiac signs](rarest-zodiac-sign/#sources-to-credit), [solar return](solar-return-before-birthday/#sources-to-credit),
[constellations](zodiac-signs-vs-constellations/#sources-to-credit), [Fire Horse](fire-horse-japan-births/#sources-to-credit),
[house numbers](missing-house-number-13/#sources-to-credit)). The studies of tarot searches, athletes, weddings in Russia, Italy and Poland and German weather lore are built from Google Trends, Wikidata, national statistics offices and the Deutscher Wetterdienst; each folder lists its sources under "Sources to credit".
In the Fire Horse study, rows from Singapore, Hong Kong and South Korea stay under their publishers' terms, marked in the CSV.

## Citation

Cite the study you used, e.g.:

> Matiushenok, V. (2026). How common is each rising sign, by latitude. StarTarot.online.
> https://startarot.online/research/rising-sign-by-latitude

## About

Published by [StarTarot](https://startarot.online/), a tarot and astrology website in nine
languages. Questions and corrections: issues here or help@startarot.online.
