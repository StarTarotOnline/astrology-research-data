# Not Death, not the Lovers: the tarot card people google most is The World

Full write-up: https://startarot.online/research/which-tarot-card-does-the-world-search-for?utm_source=github&utm_medium=data-repo&utm_campaign=night-2026-11-11

A year of Google searches for the meaning of each tarot card (1 November 2025 – 31 October 2026): all 78 cards in English and the 22 Major Arcana in seven more languages, read in 22 countries. The most looked-up cards, each country's favourite, where Death really ranks, and why a ranking by Google topics misleads. Wikipedia page views of the card articles are given alongside.

## Files

- `tarot-card-search.csv`: the dataset behind every number on the page.
- `tarot_card_search.py`: the script that downloads the sources and computes everything; its docstring lists the
  columns, the method and every source in detail.

## Reproduce

```bash
# Python 3.10+, standard library only
python3 tarot_card_search.py fetch-wiki
python3 tarot_card_search.py fetch-wiki-redirects
python3 tarot_card_search.py fetch-v2
python3 tarot_card_search.py fetch-trends
python3 tarot_card_search.py fetch-map
python3 tarot_card_search.py compute
python3 tarot_card_search.py validate
python3 tarot_card_search.py export
```

A copy run outside the StarTarot repository writes its CSV and JSON next to itself.

## Sources to credit

Google Trends: search terms, interest over time and compared breakdown by region (cite as Google Trends; data fetched on 2026-11-08). Wikimedia pageviews API, monthly, article plus its redirects (CC0). Natural Earth 1:110m admin 0 countries, v5.1.2 (public domain).

## Cite

Matiushenok, V. (2026). Which tarot card does the world look up? A year of Google meaning searches for the 78 tarot cards. StarTarot.online. https://startarot.online/research/which-tarot-card-does-the-world-search-for — data CC BY 4.0.
