#!/usr/bin/env python3
"""Can a chatbot shuffle? What 23 OpenAI chat models "pull" when asked for a tarot card.

Pre-registration written on 14 November 2026 BEFORE the full count (the fetch follows in a later commit).

The question. People ask chatbots for tarot readings. A chat model has no deck: when it "pulls a card" it writes the
most plausible next words. This study counts which cards come out, model by model, and what moves them: the wording,
the topic of the question, the language, the asker's zodiac sign and mood.

What had been seen before this text was written (a pilot of about 1,100 draws, so these are NOT blind):
* "Pull one tarot card for me. Reply with just the name of the card." - chat-latest, gpt-6-luna and gpt-6.1-sol:
  The Star in 96 of 96 draws each; chat-latest again with one answer per request: 40 of 40. gpt-4o (50 draws):
  The Empress 20, The Star 10, six other Major Arcana, no minor card. Sixteen draws on each of the other models:
  The Star 16 of 16 on gpt-5.5, both gpt-5.6 "sol"/"terra", gpt-5.6-luna, gpt-6-sol, gpt-6-astra, gpt-6.1-terra;
  two to four different cards on the 2024-2025 models and gpt-5.4.
* chat-latest, free-form answers: "Pick a random tarot card." (64) and "Draw a tarot card for me" (16) - The Star in
  every answer, with "I've shuffled the deck" in most.
* chat-latest: a card "about my love life" - The Lovers 64 of 64; "about my career and money" - Ace of Pentacles
  63 of 64; a past-present-future spread - "The Hermit, The Star, The Sun" 53 of 64.
Nothing else was run: no fairness prompt, no numbers, no reversals, no signs, no moods, no other language, no
follow-up cards, no dated system message.

Design
------
* One draw = one independent completion (a fresh conversation with no history). Requests ask for up to 8 completions
  at once (the API's n); a control cell repeats the main prompt with one completion per request.
* Sampling settings are the API defaults; no temperature, no seed, no system message (except the "date" cell).
* Every card prompt ends with "Reply with just the name of the card." so that answers can be counted; a control cell
  drops that sentence and reads the card out of a free-form answer.
* Models: the 22 chat models an ordinary API key lists on the day of the fetch, May 2024 to October 2026 (MODELS),
  plus the alias "chat-latest". "Pro" variants, search, codex and audio models are left out.
  Reasoning-heavy or expensive models get fewer draws (tiers in MODELS); that is a budget decision made here.
* Cells (CONDITIONS below gives the exact words):
    neutral   five wordings of "pull a card"                         every model
    fair      "...from the full 78-card deck, every card equally likely"  every model
    number    "Pick a random number from 1 to 78."                  every model
    single    main wording, one completion per request               chat-latest
    free      main wording without the format sentence               chat-latest, gpt-4o, gpt-6-luna
    reversal  "...upright or reversed"                              chat-latest + PANEL
    topic     eight questions (love, career, money, the ex, ...)     chat-latest + DUO
    spread    past, present, future                                  chat-latest + PANEL
    zodiac    "I'm a <sign>." before the main wording                chat-latest + DUO
    mood      three moods before the main wording                    chat-latest + DUO
    language  the main wording in 16 languages                       chat-latest + DUO
    sequence  one chat, five cards ("Pull another one.")             chat-latest + DUO
    date      a ChatGPT-style system message with 60 different dates chat-latest
* Measures. Top card and its share (Wilson 95 % interval). Effective deck = exp(Shannon entropy) of the cards drawn
  in a cell: 78 for a fair deck, 1 when one card always comes. Share of Minor Arcana (56 of 78 in a deck), of "hard"
  cards (HARD_CARDS, 10 of 78), of reversals.
* Answers are mapped to cards by PARSE rules (English names, numerals, common variants). Names in other languages
  are mapped by ALIASES, a table filled in AFTER the fetch from the distinct answer strings: it is a dictionary of
  translations, not a decision about the data, and every unmapped answer is counted and printed.
* A hard budget cap stops the fetch (BUDGET_USD, estimated from the usage the API returns and PRICES).

Limits known in advance
-----------------------
* This is the API, not the ChatGPT app: the app adds a system prompt, the date, memory and tools. The "date" cell
  imitates one of those; the rest is a limit the page must print.
* One vendor. Other chatbots are not measured here.
* The alias "chat-latest" moves: the resolved model name returned by the API is stored with every request.
"""

HYPOTHESES = {
    'H1': '[seen in the pilot] On chat-latest, over the five neutral wordings together, one card takes more than '
          '90 % of the draws, and that card is The Star.',
    'H2': '[seen in a 16-draw pilot] Newer is narrower: over the dated models (chat-latest excluded), the Spearman '
          'correlation between API release date and the effective deck on the neutral wordings is negative, and '
          'every model released in 2026 has an effective deck below 3 cards.',
    'H3': 'Asking for fairness does not fix it: with the "fair" wording no model reaches an effective deck of 39 '
          'cards (half a deck), and chat-latest stays below 10.',
    'H4': 'The Minor Arcana (72 % of a deck) get less than 10 % of the neutral draws on every model.',
    'H5': 'Hard cards (HARD_CARDS, 12.8 % of a deck) are under 1 % of the neutral draws on chat-latest and under '
          '3 % on every model.',
    'H6': 'Asked "upright or reversed", chat-latest answers "reversed" in under 10 % of draws.',
    'H7': '[love and money seen in the pilot] The question picks the card: on chat-latest the top card takes more '
          'than 50 % of the draws in each of the eight topics; for love the top card is The Lovers or a Cups card, '
          'for money a Pentacles card.',
    'H8': 'Tell it your sign: for at least 8 of the 12 signs, the most frequent card on chat-latest is the Major '
          'Arcana card the Golden Dawn tradition assigns to that sign (ZODIAC_CARD).',
    'H9': 'Bad week, good card: after "I\'m having a terrible week." hard cards are under 5 % of the chat-latest '
          'draws and the top card is The Star.',
    'H10': 'In at least 12 of the 16 languages the top card on chat-latest is The Star, and in every language the '
           'top card takes more than 50 % of the draws.',
    'H11': '[seen in the pilot] In the past-present-future spread on chat-latest the future card is The Sun, The '
           'Star or The World in more than 90 % of spreads, and one exact three-card sequence takes more than 50 %.',
    'H12': 'The second card is fixed too: in the five-card chats on chat-latest one card is the second card in more '
           'than 50 % of chats, and fewer than 1 % of chats repeat a card.',
    'H13': 'A date does not shuffle the deck: with a dated system message The Star still takes more than 90 % of '
           'the chat-latest draws over the 60 dates.',
    'H14': 'Numbers fare no better: asked for a random number from 1 to 78, chat-latest gives one number in more '
           'than 20 % of draws, and that number is 37 or 42.',
}
ADDED_AFTER_COUNT: dict[str, str] = {
    'A1': '[during the fetch, before any of the cells it touches was read] Budget. The cost cap stopped the first '
          'fetch after the neutral, fair, number and single cells, and the account ran dry during the second. What '
          'was fetched after the cap: reversal and spread at 400 draws on chat-latest and 200 on each panel model; '
          'the eight topics at 200 draws on chat-latest; free-form answers, 100 on gpt-4o and on gpt-6-luna; and '
          'four signs on chat-latest (184, 192, 176 and 88 draws, all kept). A last, smaller fetch followed, '
          'limited by output tokens instead of estimated dollars: the other eight signs and the 16 '
          'languages at 100 draws each, chat-latest only, and the dated system message as registered (16 draws on '
          'each of 60 dates). Dropped, never fetched: the mood cells (H9 not run), the five-card chats (H12 not '
          'run), and every topic, sign, mood, language and chat cell on gpt-4o and gpt-6-luna. No hypothesis, '
          'wording or threshold changed.',
    'A2': '[after the fetch] Free-form control on chat-latest. The cell was fetched with a 200-token cap on the '
          'answer; 283 of its 304 answers came back empty, cut off by the cap (finish reason "length"), so only '
          'the shortest answers survived: 21 of them. Those rows are set aside, reported as what they are and not '
          'counted in any share; the cell was not fetched again (budget). The free-form control therefore rests '
          'on gpt-4o and gpt-6-luna.',
    'A3': '[after the count] Small samples flatter nobody: exp(entropy) of n draws is biased low, and a fair '
          '78-card deck sampled only 48 to 200 times does not show 78 cards either. Every "fair" and neutral cell '
          'therefore carries the effective deck a truly uniform deck gives at the same n (mean of 2,000 simulated '
          'samples, fixed seed), the share of those samples that come out as narrow as the model, and the '
          'Miller-Madow corrected effective deck. H3 is judged as registered, on the raw number; the page prints '
          'the corrected one next to it.',
    'A4': '[after the count] Free-form answers are also searched for the word "shuffle": the share of answers in '
          'which the model says it shuffled the deck.',
    'A5': '[after the count] Descriptions the page added after seeing the numbers, none of them a test: the line '
          'drawn at April 2026 (GPT-5.5 and later); the rank of the small cards named under the "fair" wording '
          '(Sevens); the last digits of the favourite numbers. Also added on an independent review: hidden '
          'reasoning tokens per draw for every model, the rank correlation of H2 over the models before April '
          '2026 alone, and a permutation check that the up-to-8 completions of one request agree no more than '
          'completions of different requests.',
    'A6': '[after the count] Language cells also record how the card was written and whether the answer added, '
          'unasked, that the card was upright.',
    'A7': '[after the count] Controls the independent review asked for and the budget did not allow: uncapped '
          'free-form answers on chat-latest, the reversal question with the two words swapped, a repeat on another '
          'day, a higher reasoning effort, a fuller ChatGPT-style system message, and larger "fair" cells for '
          'gpt-5 and o3. The page lists them as open.',
}

import collections
import concurrent.futures
import csv
import datetime
import hashlib
import json
import math
import os
import re
import shutil
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

FILE_STEM = 'ai-tarot-draws'
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
IN_REPO = (REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research').is_dir()
if IN_REPO:
    JSON_OUT = REPO_ROOT / 'frontend' / 'src' / 'lib' / 'research' / f'{FILE_STEM}.json'
    CSV_OUT = REPO_ROOT / 'frontend' / 'static' / 'research' / f'{FILE_STEM}.csv'
    SCRIPT_COPY = REPO_ROOT / 'frontend' / 'static' / 'research' / 'ai_tarot_draws.py'
else:  # the published copy: write next to the script
    JSON_OUT = HERE / f'{FILE_STEM}.json'
    CSV_OUT = HERE / f'{FILE_STEM}.csv'
    SCRIPT_COPY = None
_MAC_DATA = Path.home() / 'startarot-data' / 'ai-tarot-draws'
DATA = Path(os.environ.get('AI_TAROT_DATA') or (_MAC_DATA if _MAC_DATA.parent.is_dir() else HERE / 'ai-tarot-draws-data'))
RAW = DATA / 'raw'
BUDGET_USD = float(os.environ.get('AI_TAROT_BUDGET', '13'))
# A second limit that does not depend on guessed prices: output tokens one `fetch` run may spend (0 = no limit).
RUN_OUTPUT_TOKENS = int(os.environ.get('AI_TAROT_RUN_OUTPUT_TOKENS', '0'))
THREADS = int(os.environ.get('AI_TAROT_THREADS', '12'))

# (model id, tier). Tier sets the number of draws: reasoning-heavy and expensive models get fewer.
MODELS = [
    ('gpt-4o', 'std'), ('gpt-4o-mini', 'std'), ('gpt-4.1', 'std'), ('gpt-4.1-mini', 'std'), ('o3', 'slow'),
    ('gpt-5', 'xslow'), ('gpt-5-mini', 'slow'), ('gpt-5-nano', 'slow'), ('gpt-5.1', 'std'), ('gpt-5.2', 'std'),
    ('gpt-5.4', 'std'), ('gpt-5.4-mini', 'std'), ('gpt-5.4-nano', 'std'), ('gpt-5.5', 'slow'),
    ('gpt-5.6-luna', 'std'), ('gpt-5.6-terra', 'std'), ('gpt-5.6-sol', 'slow'), ('gpt-6-astra', 'slow'),
    ('gpt-6-luna', 'std'), ('gpt-6-sol', 'std'), ('gpt-6.1-sol', 'std'), ('gpt-6.1-terra', 'std'),
    ('chat-latest', 'chat'),
]
CHAT = 'chat-latest'
PANEL = ['gpt-4o', 'gpt-4o-mini', 'gpt-5.1', 'gpt-5.4-mini', 'gpt-6-luna', 'gpt-6-sol']
FREE_MODELS = ['gpt-4o', 'gpt-6-luna']
# draws per wording: neutral, fair, number
TIER_DRAWS = {'std': (200, 200, 200), 'slow': (80, 80, 80), 'xslow': (48, 48, 48), 'chat': (2000, 400, 400)}

FORMAT = ' Reply with just the name of the card.'
MAIN = 'Pull one tarot card for me.'
NEUTRAL = {
    'n1': MAIN,
    'n2': 'Draw a tarot card for me.',
    'n3': 'Pick a random tarot card.',
    'n4': 'Shuffle the deck and pull a single tarot card for me.',
    'n5': 'What is my tarot card of the day?',
}
FAIR = ('Pull one tarot card at random from the full 78-card deck, Major and Minor Arcana, '
        'with every card equally likely.')
NUMBER = 'Pick a random number from 1 to 78. Reply with just the number.'
REVERSAL = ('Pull one tarot card for me and tell me whether it came out upright or reversed. '
            'Reply in the form: card name, upright or reversed.')
ZODIAC_DRAWS = {'aries': 184, 'taurus': 192, 'gemini': 176, 'cancer': 88}  # A1: fetched before the stop
TOPICS = {
    'love': 'about my love life', 'career': 'about my career', 'money': 'about money',
    'ex': 'about whether I should text my ex', 'year': 'for my year ahead',
    'decision': 'about a big decision I have to make', 'move': 'about moving to a new city',
    'friends': 'about my friendships',
}
SPREAD = ('Do a three-card tarot spread for me: past, present, future. '
          'Reply with just the three card names, separated by commas.')
SIGNS = ['Aries', 'Taurus', 'Gemini', 'Cancer', 'Leo', 'Virgo', 'Libra', 'Scorpio', 'Sagittarius', 'Capricorn',
         'Aquarius', 'Pisces']
ZODIAC_CARD = {  # Golden Dawn attributions of the Major Arcana to the signs
    'Aries': 'the-emperor', 'Taurus': 'the-hierophant', 'Gemini': 'the-lovers', 'Cancer': 'the-chariot',
    'Leo': 'strength', 'Virgo': 'the-hermit', 'Libra': 'justice', 'Scorpio': 'death',
    'Sagittarius': 'temperance', 'Capricorn': 'the-devil', 'Aquarius': 'the-star', 'Pisces': 'the-moon',
}
MOODS = {
    'terrible': "I'm having a terrible week.",
    'best': "I'm having the best week of my life.",
    'scared': "I'm scared about what's coming.",
}
LANGUAGES = {  # the main wording + the format sentence, translated
    'en': MAIN + FORMAT,
    'es': 'Saca una carta del tarot para mí. Responde solo con el nombre de la carta.',
    'pt': 'Tire uma carta de tarô para mim. Responda apenas com o nome da carta.',
    'de': 'Zieh eine Tarotkarte für mich. Antworte nur mit dem Namen der Karte.',
    'fr': 'Tire une carte de tarot pour moi. Réponds uniquement avec le nom de la carte.',
    'it': 'Estrai una carta dei tarocchi per me. Rispondi solo con il nome della carta.',
    'pl': 'Wyciągnij dla mnie jedną kartę tarota. Odpowiedz tylko nazwą karty.',
    'ru': 'Вытяни для меня одну карту таро. Ответь только названием карты.',
    'lt': 'Ištrauk man vieną Taro kortą. Atsakyk tik kortos pavadinimu.',
    'tr': 'Benim için bir tarot kartı çek. Sadece kartın adını yaz.',
    'id': 'Tarik satu kartu tarot untukku. Jawab hanya dengan nama kartunya.',
    'ja': 'タロットカードを1枚引いてください。カードの名前だけを答えてください。',
    'zh': '请为我抽一张塔罗牌。只回答牌的名称。',
    'ko': '타로 카드 한 장을 뽑아 주세요. 카드 이름만 답해 주세요.',
    'hi': 'मेरे लिए एक टैरो कार्ड निकालिए। केवल कार्ड का नाम बताइए।',
    'ar': 'اسحب لي بطاقة تاروت واحدة. أجب باسم البطاقة فقط.',
}
LANGUAGE_NAMES = {
    'en': 'English', 'es': 'Spanish', 'pt': 'Portuguese', 'de': 'German', 'fr': 'French', 'it': 'Italian',
    'pl': 'Polish', 'ru': 'Russian', 'lt': 'Lithuanian', 'tr': 'Turkish', 'id': 'Indonesian', 'ja': 'Japanese',
    'zh': 'Chinese', 'ko': 'Korean', 'hi': 'Hindi', 'ar': 'Arabic',
}
ANOTHER = 'Pull another one.' + FORMAT
SEQUENCE_LENGTH = 5
DATE_SYSTEM = 'You are ChatGPT, a large language model trained by OpenAI.\nCurrent date: {date}'
DATES = [(datetime.date(2026, 1, 1) + datetime.timedelta(days=6 * i)).isoformat() for i in range(60)]
HARD_CARDS = ['the-tower', 'death', 'the-devil', 'three-of-swords', 'five-of-swords', 'eight-of-swords',
              'nine-of-swords', 'ten-of-swords', 'five-of-cups', 'five-of-pentacles']
FUTURE_BRIGHT = ['the-sun', 'the-star', 'the-world']

# USD per 1M tokens (input, output) for the budget cap only; unknown models are charged at UNKNOWN_PRICE.
PRICES = {
    'gpt-6-astra': (10.0, 50.0), 'gpt-6-sol': (2.0, 10.0), 'gpt-6-luna': (0.1, 0.5), 'gpt-5.6-sol': (4.0, 20.0),
    'gpt-5.6-terra': (2.0, 12.0), 'gpt-5.6-luna': (0.2, 1.2), 'gpt-5.4': (2.5, 15.0), 'gpt-5.4-mini': (0.75, 4.5),
    'gpt-5.4-nano': (0.2, 1.25), 'gpt-5.2': (1.75, 14.0), 'gpt-5-mini': (0.25, 2.0), 'gpt-5-nano': (0.05, 0.4),
    'gpt-4o': (2.5, 10.0), 'gpt-4o-mini': (0.15, 0.6), 'gpt-4.1': (2.0, 8.0), 'gpt-4.1-mini': (0.4, 1.6),
    'o3': (2.0, 8.0), 'gpt-5': (1.25, 10.0), 'gpt-5.1': (1.25, 10.0), 'gpt-5.5': (5.0, 30.0),
    'gpt-6.1-sol': (2.0, 10.0), 'gpt-6.1-terra': (1.0, 5.0),
}
UNKNOWN_PRICE = (5.0, 30.0)

MAJORS = [
    ('the-fool', 'The Fool', r'fool'), ('the-magician', 'The Magician', r'magician|magus'),
    ('the-high-priestess', 'The High Priestess', r'high priestess|priestess|popess'),
    ('the-empress', 'The Empress', r'empress'), ('the-emperor', 'The Emperor', r'emperor'),
    ('the-hierophant', 'The Hierophant', r'hierophant|high priest|pope'), ('the-lovers', 'The Lovers', r'lovers'),
    ('the-chariot', 'The Chariot', r'chariot'), ('strength', 'Strength', r'strength'),
    ('the-hermit', 'The Hermit', r'hermit'), ('wheel-of-fortune', 'Wheel of Fortune', r'wheel of fortune|the wheel'),
    ('justice', 'Justice', r'justice'), ('the-hanged-man', 'The Hanged Man', r'hanged man|hanged one'),
    ('death', 'Death', r'death'), ('temperance', 'Temperance', r'temperance'), ('the-devil', 'The Devil', r'devil'),
    ('the-tower', 'The Tower', r'tower'), ('the-star', 'The Star', r'star'), ('the-moon', 'The Moon', r'moon'),
    ('the-sun', 'The Sun', r'sun'), ('judgement', 'Judgement', r'judgement|judgment'),
    ('the-world', 'The World', r'world|universe'),
]
RANKS = ['ace', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'page', 'knight', 'queen',
         'king']
RANK_WORDS = {**{r: r for r in RANKS}, **{str(i + 1): RANKS[i] for i in range(10)}, 'princess': 'page',
              'prince': 'knight', 'knave': 'page'}
SUIT_WORDS = {'wands': 'wands', 'staves': 'wands', 'rods': 'wands', 'batons': 'wands', 'cups': 'cups',
              'chalices': 'cups', 'swords': 'swords', 'pentacles': 'pentacles', 'coins': 'pentacles',
              'disks': 'pentacles', 'discs': 'pentacles'}
SUITS = ['wands', 'cups', 'swords', 'pentacles']


def cards():
    out = [{'id': cid, 'name': name, 'arcana': 'major', 'suit': None} for cid, name, _ in MAJORS]
    for suit in SUITS:
        for rank in RANKS:
            out.append({'id': f'{rank}-of-{suit}', 'name': f'{rank.capitalize()} of {suit.capitalize()}',
                        'arcana': 'minor', 'suit': suit})
    return out


CARDS = cards()
BY_ID = {c['id']: c for c in CARDS}
assert len(CARDS) == 78

# ALIASES: normalized answer string -> card id, for names in other languages. Filled after the fetch from the
# distinct answers (see the docstring); `compute` prints every answer it cannot map.
ALIASES: dict[str, str] = {
    'la estrella': 'the-star', 'a estrela': 'the-star', 'der stern': 'the-star', "l'étoile": 'the-star',
    'la stella': 'the-star', 'gwiazda': 'the-star', 'звезда': 'the-star', 'žvaigždė': 'the-star',
    'yıldız': 'the-star', 'النجمة': 'the-star',
    '星': 'the-star', '星(正位置)': 'the-star',                       # Japanese: "The Star (upright)"
    '星星(正位)': 'the-star', '命运之轮(正位)': 'wheel-of-fortune',     # Chinese, also with "(upright)"
    '운명의 수레바퀴': 'wheel-of-fortune',                             # Korean
}

_MAJOR_RE = [(cid, re.compile(r'\b(?:' + pat + r')\b')) for cid, _, pat in MAJORS]
_MINOR_RE = re.compile(r'\b(' + '|'.join(sorted(RANK_WORDS, key=len, reverse=True)) + r')\s+of\s+(' +
                       '|'.join(SUIT_WORDS) + r')\b')
_CAP_MAJOR_RE = re.compile('|'.join(sorted((re.escape(name) for _, name, _ in MAJORS), key=len, reverse=True)))
_CAP_MINOR_RE = re.compile(r'\b(' + '|'.join(r.capitalize() for r in RANKS) + r'|[2-9]|10)\s+of\s+(' +
                           '|'.join(s.capitalize() for s in SUIT_WORDS) + r')\b')
_NAME_TO_ID = {name: cid for cid, name, _ in MAJORS}


def normalize(text):
    text = unicodedata.normalize('NFKC', text or '').lower()
    text = text.replace('’', "'").replace('`', "'")
    text = re.sub(r'[*_#>"“”«»🔮✨⭐🌟🃏🌙☀️🌞]', ' ', text)
    text = re.sub(r'\((?:[ivxl]+|\d+)\)', ' ', text)        # (XVII), (17)
    text = re.sub(r'\b(?:[ivxl]+|\d+)\s*[.:\-–—]\s+', ' ', text)  # "XVII. The Star", "17 - The Star"
    return re.sub(r'\s+', ' ', text).strip(' .!,;:-–—')


def find_cards(text):
    """All English card names in a normalized string, in order of appearance."""
    hits = []
    for m in _MINOR_RE.finditer(text):
        hits.append((m.start(), m.end(), f'{RANK_WORDS[m.group(1)]}-of-{SUIT_WORDS[m.group(2)]}'))
    taken = [(a, b) for a, b, _ in hits]
    for cid, rx in _MAJOR_RE:
        for m in rx.finditer(text):
            if any(a <= m.start() < b for a, b in taken):
                continue
            hits.append((m.start(), m.end(), cid))
    hits.sort()
    out = []  # drop a shorter name inside a longer one ("priestess" in "high priestess" is one regex already)
    for a, b, cid in hits:
        if out and a < out[-1][1]:
            continue
        out.append((a, b, cid))
    return [cid for _, _, cid in out]


def parse_card(answer):
    """One card from a name-only answer: (card id | None, strict?)."""
    text = normalize(answer)
    if text in ALIASES:
        return ALIASES[text], True
    bare = re.sub(r'\b(?:upright|reversed|card|tarot)\b', ' ', text)
    bare = re.sub(r'\s+', ' ', bare).strip(' .!,;:-–—()')
    if bare in ALIASES:
        return ALIASES[bare], True
    found = find_cards(text)
    if len(found) == 1:
        return found[0], len(bare) <= 28
    if found:
        return found[0], False
    for key, cid in ALIASES.items():  # a foreign name inside a longer answer
        if len(key) >= 3 and key in text:
            return cid, False
    return None, False


def parse_free(answer):
    """First card named in a free-form English answer, by its capitalized name."""
    best = None
    for rx, kind in ((_CAP_MINOR_RE, 'minor'), (_CAP_MAJOR_RE, 'major')):
        m = rx.search(answer or '')
        if m and (best is None or m.start() < best[0]):
            if kind == 'minor':
                cid = f'{RANK_WORDS[m.group(1).lower()]}-of-{SUIT_WORDS[m.group(2).lower()]}'
            else:
                cid = _NAME_TO_ID[m.group(0)]
            best = (m.start(), cid)
    return best[1] if best else None


def parse_orientation(answer):
    text = normalize(answer)
    rev, up = 'revers' in text, 'upright' in text
    return 'reversed' if rev and not up else 'upright' if up and not rev else None


def parse_spread(answer):
    parts = [p for p in re.split(r'[,;\n→|/]| - | – | — ', answer or '') if p.strip()]
    found = [parse_card(re.sub(r'^\s*(?:past|present|future)\s*[:\-–—]\s*', '', p, flags=re.I))[0] for p in parts]
    found = [c for c in found if c]
    if len(found) != 3:
        found = find_cards(normalize(answer))
    return found if len(found) == 3 else None


def parse_number(answer):
    m = re.search(r'\d+', answer or '')
    if not m:
        return None
    n = int(m.group(0))
    return n if 1 <= n <= 78 else None


# ----------------------------------------------------------------------------------------------- cells

def user(text):
    return [{'role': 'user', 'content': text}]


def build_cells():
    cells = []

    def add(cond, variant, model, kind, messages, draws, per_request=8, max_tokens=None):
        cells.append({'id': f'{cond}.{variant}.{model}', 'cond': cond, 'variant': variant, 'model': model,
                      'kind': kind, 'messages': messages, 'draws': draws, 'per_request': per_request,
                      'max_tokens': max_tokens})

    for model, tier in MODELS:
        n_neutral, n_fair, n_number = TIER_DRAWS[tier]
        for key, wording in NEUTRAL.items():
            add('neutral', key, model, 'card', user(wording + FORMAT), n_neutral)
        add('fair', 'fair', model, 'card', user(FAIR + FORMAT), n_fair)
        add('number', 'number', model, 'number', user(NUMBER), n_number)
    add('single', 'n1', CHAT, 'card', user(MAIN + FORMAT), 200, per_request=1)
    for model, cap in (('gpt-4o', 200), ('gpt-6-luna', 600)):  # A1, A2
        add('free', 'n1', model, 'free', user(MAIN), 100, max_tokens=cap)
    for model in [CHAT] + PANEL:
        add('reversal', 'reversal', model, 'reversal', user(REVERSAL), 400 if model == CHAT else 200)  # A1
        add('spread', 'spread', model, 'spread', user(SPREAD), 400 if model == CHAT else 200)  # A1
    for key, about in TOPICS.items():  # A1: chat-latest only from here on
        add('topic', key, CHAT, 'card', user(f'Pull one tarot card {about}.' + FORMAT), 200)
    for sign in SIGNS:
        article = 'an' if sign[0] in 'AEIOU' else 'a'
        add('zodiac', sign.lower(), CHAT, 'card', user(f"I'm {article} {sign}. " + MAIN + FORMAT),
            ZODIAC_DRAWS.get(sign.lower(), 100))
    for lang, wording in LANGUAGES.items():
        add('language', lang, CHAT, 'card', user(wording), 100)
    for date in DATES:
        add('date', date, CHAT, 'card',
            [{'role': 'system', 'content': DATE_SYSTEM.format(date=date)}] + user(MAIN + FORMAT), 16)
    return cells


CELLS = build_cells()


# ----------------------------------------------------------------------------------------------- fetch

def api_key():
    key = os.environ.get('OPENAI_API_KEY')
    if not key and IN_REPO and (REPO_ROOT / 'backend' / '.env').is_file():
        for line in (REPO_ROOT / 'backend' / '.env').read_text().splitlines():
            if line.startswith('OPENAI_API_KEY='):
                key = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not key:
        raise SystemExit('Set OPENAI_API_KEY.')
    return key


_lock = threading.Lock()
_spend = {'usd': 0.0, 'stop': False, 'out': 0, 'requests': 0}


def api(path, body=None, tries=6):
    data = json.dumps(body).encode() if body is not None else None
    for attempt in range(tries):
        req = urllib.request.Request('https://api.openai.com/v1/' + path, data=data, headers={
            'Authorization': 'Bearer ' + api_key(), 'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=300) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            text = error.read().decode('utf-8', 'replace')[:400]
            if 'insufficient_quota' in text or 'credit_balance_exhausted' in text:
                # an empty account is not a rate limit: retrying only hides it (and the same balance may feed a
                # production service), so stop every worker at once
                _spend['stop'] = True
                return {'error': f'HTTP {error.code}: {text}'}
            if error.code in (429, 500, 502, 503, 504) and attempt + 1 < tries:
                time.sleep(2 ** attempt + 1)
                continue
            return {'error': f'HTTP {error.code}: {text}'}
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            if attempt + 1 < tries:
                time.sleep(2 ** attempt + 1)
                continue
            return {'error': f'network: {error}'}
    return {'error': 'retries exhausted'}


def cost(model, usage):
    p_in, p_out = PRICES.get(model, UNKNOWN_PRICE)
    return (usage.get('prompt_tokens', 0) * p_in + usage.get('completion_tokens', 0) * p_out) / 1e6


def read_rows(cell):
    path = RAW / f"{cell['id']}.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def have(cell):
    return sum(len(row['answers']) if cell['kind'] != 'sequence' else 1 for row in read_rows(cell)
               if 'answers' in row)


def complete(cell, messages, n):
    body = {'model': cell['model'], 'messages': messages, 'n': n}
    if cell['max_tokens']:
        body['max_completion_tokens'] = cell['max_tokens']
    return api('chat/completions', body)


def one_request(cell, n):
    if _spend['stop']:
        return None
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
    usage = collections.Counter()
    if cell['kind'] == 'sequence':
        messages, answers, resolved = list(cell['messages']), [], None
        for _ in range(SEQUENCE_LENGTH):
            r = complete(cell, messages, 1)
            if 'error' in r:
                return {'ts': now, 'error': r['error']}
            text = r['choices'][0]['message']['content'] or ''
            answers.append(text)
            resolved = r.get('model')
            for k in ('prompt_tokens', 'completion_tokens'):
                usage[k] += r['usage'].get(k, 0)
            messages = messages + [{'role': 'assistant', 'content': text}, {'role': 'user', 'content': ANOTHER}]
        row = {'ts': now, 'model': resolved, 'usage': dict(usage), 'answers': answers}
    else:
        r = complete(cell, cell['messages'], n)
        if 'error' in r:
            return {'ts': now, 'error': r['error']}
        usage.update({k: r['usage'].get(k, 0) for k in ('prompt_tokens', 'completion_tokens')})
        usage['reasoning_tokens'] = (r['usage'].get('completion_tokens_details') or {}).get('reasoning_tokens', 0)
        row = {'ts': now, 'model': r.get('model'), 'fingerprint': r.get('system_fingerprint'),
               'usage': dict(usage), 'answers': [c['message']['content'] or '' for c in r['choices']],
               'finish': sorted({c.get('finish_reason') for c in r['choices']})}
    with _lock:
        _spend['usd'] += cost(cell['model'], usage)
        _spend['out'] += usage.get('completion_tokens', 0)
        _spend['requests'] += 1
        if _spend['usd'] >= BUDGET_USD or (RUN_OUTPUT_TOKENS and _spend['out'] >= RUN_OUTPUT_TOKENS):
            _spend['stop'] = True
        with (RAW / f"{cell['id']}.jsonl").open('a') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    return row


def spent_so_far():
    total = 0.0
    for cell in CELLS:
        for row in read_rows(cell):
            total += cost(cell['model'], row.get('usage') or {})
    return total


def fetch(only=None):
    RAW.mkdir(parents=True, exist_ok=True)
    models = {m['id']: m['created'] for m in api('models')['data']}
    missing = [m for m, _ in MODELS if m not in models]
    if missing:
        raise SystemExit(f'models not listed for this key: {missing}')
    (DATA / 'models.json').write_text(json.dumps({m: models[m] for m, _ in MODELS}, indent=1))
    _spend['usd'] = spent_so_far()
    print(f'spent so far (estimate): ${_spend["usd"]:.2f} of ${BUDGET_USD:.2f}')
    jobs = []
    for cell in CELLS:
        if only and not re.search(only, cell['id']):
            continue
        left = cell['draws'] - have(cell)
        while left > 0:
            n = 1 if cell['kind'] == 'sequence' else min(cell['per_request'], left)
            jobs.append((cell, n))
            left -= n
    print(f'{len(jobs)} requests to send, {sum(n for _, n in jobs)} answers'
          + (f'; this run stops at {RUN_OUTPUT_TOKENS} output tokens' if RUN_OUTPUT_TOKENS else ''))
    if os.environ.get('AI_TAROT_DRY') == '1':
        return
    errors = collections.Counter()
    done = 0
    with concurrent.futures.ThreadPoolExecutor(THREADS) as pool:
        for row in pool.map(lambda job: one_request(*job), jobs):
            done += 1
            if row and 'error' in row:
                errors[row['error'][:120]] += 1
            if done % 500 == 0:
                print(f'  {done}/{len(jobs)}  ${_spend["usd"]:.2f}', flush=True)
    print(f'done; {_spend["requests"]} requests, {_spend["out"]} output tokens this run; '
          f'estimated spend ${_spend["usd"]:.2f}; stopped by a limit: {_spend["stop"]}')
    for message, count in errors.most_common(10):
        print('  error x', count, message)
    short = [(c['id'], have(c), c['draws']) for c in CELLS if have(c) < c['draws']]
    print(f'{len(short)} cells short of their draws', short[:8])


# ----------------------------------------------------------------------------------------------- compute

def wilson(k, n, z=1.959964):
    if n == 0:
        return [0.0, 0.0]
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [max(0.0, centre - half), min(1.0, centre + half)]


def effective(counter):
    total = sum(counter.values())
    if not total:
        return None
    return math.exp(-sum(v / total * math.log(v / total) for v in counter.values() if v))


_UNIFORM_CACHE: dict[int, list[float]] = {}


def uniform_effective(n, sims=2000):
    """Effective deck of n draws from a fair 78-card deck: sorted simulated values (A3)."""
    if n not in _UNIFORM_CACHE:
        import random
        rng = random.Random(78_000 + n)
        _UNIFORM_CACHE[n] = sorted(
            effective(collections.Counter(rng.randrange(78) for _ in range(n))) for _ in range(sims))
    return _UNIFORM_CACHE[n]


def against_uniform(summary):
    """What a fair deck would show at this n, and how often it comes out as narrow as observed."""
    if not summary['n']:
        return
    sims = uniform_effective(summary['n'])
    summary['uniform_effective'] = sum(sims) / len(sims)
    summary['uniform_as_narrow'] = sum(1 for v in sims if v <= summary['effective']) / len(sims)
    summary['uniform_min'] = sims[0]
    # Miller-Madow: entropy + (observed cards - 1) / 2n
    summary['effective_mm'] = summary['effective'] * math.exp((summary['distinct'] - 1) / (2 * summary['n']))


def spearman(xs, ys):
    def ranks(values):
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            for k in range(i, j + 1):
                out[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return out
    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def summarize(counter, unparsed=0):
    n = sum(counter.values())
    top = counter.most_common(1)[0] if counter else (None, 0)
    is_card = bool(counter) and all(isinstance(k, str) and k in BY_ID for k in counter)
    out = {'n': n, 'unparsed': unparsed, 'top': top[0], 'top_n': top[1],
           'top_share': top[1] / n if n else None, 'top_ci': wilson(top[1], n), 'distinct': len(counter),
           'effective': effective(counter),
           'counts': dict(sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0]))))}
    if is_card:
        out['minor_share'] = sum(v for k, v in counter.items() if BY_ID[k]['arcana'] == 'minor') / n
        out['hard_share'] = sum(v for k, v in counter.items() if k in HARD_CARDS) / n
    return out


def cell_answers(cell):
    for row in read_rows(cell):
        if 'answers' not in row:
            continue
        if cell['kind'] == 'sequence':
            yield row['answers']
        else:
            yield from row['answers']


def set_aside_free():
    """The capped free-form rows on chat-latest (A2): what survived the cap. Reported, never counted."""
    path = DATA / 'set-aside' / f'free-capped-200.n1.{CHAT}.jsonl'
    if not path.is_file():
        return None
    answers = [a for line in path.read_text().splitlines() if line.strip()
               for a in json.loads(line).get('answers', [])]
    kept = [a for a in answers if a.strip()]
    cards_ = collections.Counter(c for c in map(parse_free, kept) if c)
    return {'fetched': len(answers), 'empty': len(answers) - len(kept), 'survived': len(kept),
            'cards': dict(cards_.most_common()), 'says_shuffled': sum(1 for a in kept if re.search(r'shuffl', a, re.I))}


def independence(shuffles=200):
    """Do the up-to-8 completions of one request agree more than completions of different requests? (A5)

    For every neutral and fair cell that names more than one card: the share of agreeing pairs inside a request,
    against the same share after the answers are shuffled across the requests of the cell."""
    import random
    rng = random.Random(8)

    def within(groups):
        same = pairs = 0
        for group in groups:
            counts = collections.Counter(group)
            same += sum(v * (v - 1) // 2 for v in counts.values())
            pairs += len(group) * (len(group) - 1) // 2
        return same / pairs if pairs else 0.0

    zs, gaps = [], []
    for cell in CELLS:
        if cell['cond'] not in ('neutral', 'fair') or cell['per_request'] < 2:
            continue
        groups = []
        for row in read_rows(cell):
            ids = [c for c in (parse_card(a)[0] for a in row.get('answers', [])) if c]
            if len(ids) > 1:
                groups.append(ids)
        flat = [c for g in groups for c in g]
        if len(set(flat)) < 2 or len(groups) < 5:
            continue
        observed = within(groups)
        sims = []
        for _ in range(shuffles):
            rng.shuffle(flat)
            it = iter(flat)
            sims.append(within([[next(it) for _ in g] for g in groups]))
        mean = sum(sims) / len(sims)
        sd = math.sqrt(sum((v - mean) ** 2 for v in sims) / (len(sims) - 1))
        if sd > 0:
            zs.append((observed - mean) / sd)
            gaps.append(observed - mean)
    return {'cells': len(zs), 'mean_z': sum(zs) / len(zs), 'stouffer_z': sum(zs) / math.sqrt(len(zs)),
            'share_abs_z_over_2': sum(1 for z in zs if abs(z) > 1.96) / len(zs),
            'mean_gap': sum(gaps) / len(gaps)}


def compute():
    unparsed_all = collections.Counter()
    loose = collections.Counter()
    table = {}       # cell id -> summary
    extra = {}
    for cell in CELLS:
        counter, bad = collections.Counter(), 0
        if cell['kind'] in ('card', 'free'):
            for answer in cell_answers(cell):
                if cell['kind'] == 'free':
                    cid, strict = parse_free(answer), True
                else:
                    cid, strict = parse_card(answer)
                if cid is None:
                    bad += 1
                    unparsed_all[(cell['cond'], normalize(answer)[:60])] += 1
                    continue
                if not strict:
                    loose[cell['id']] += 1
                counter[cid] += 1
            table[cell['id']] = summarize(counter, bad)
            if cell['cond'] == 'language':  # how the card was written, and whether "upright" was volunteered
                written = collections.Counter(a.strip() for a in cell_answers(cell))
                table[cell['id']]['written'] = written.most_common(1)[0][0] if written else None
                table[cell['id']]['says_upright'] = sum(
                    v for k, v in written.items() if re.search(r'正位|upright', k, re.I))
            if cell['kind'] == 'free':  # A4
                texts = list(cell_answers(cell))
                table[cell['id']]['says_shuffled'] = sum(1 for t in texts if re.search(r'shuffl', t, re.I))
                table[cell['id']]['answers'] = len(texts)
        elif cell['kind'] == 'number':
            for answer in cell_answers(cell):
                n = parse_number(answer)
                if n is None:
                    bad += 1
                    continue
                counter[n] += 1
            table[cell['id']] = summarize(counter, bad)
        elif cell['kind'] == 'reversal':
            orient = collections.Counter()
            for answer in cell_answers(cell):
                cid, _ = parse_card(answer)
                o = parse_orientation(answer)
                if cid is None or o is None:
                    bad += 1
                    unparsed_all[(cell['cond'], normalize(answer)[:60])] += 1
                    continue
                counter[cid] += 1
                orient[o] += 1
            s = summarize(counter, bad)
            s['reversed'] = orient['reversed']
            s['reversed_share'] = orient['reversed'] / s['n'] if s['n'] else None
            s['reversed_ci'] = wilson(orient['reversed'], s['n'])
            table[cell['id']] = s
        elif cell['kind'] == 'spread':
            sequences, future, position = collections.Counter(), collections.Counter(), [collections.Counter() for _ in range(3)]
            repeats = 0
            for answer in cell_answers(cell):
                three = parse_spread(answer)
                if not three:
                    bad += 1
                    unparsed_all[(cell['cond'], normalize(answer)[:60])] += 1
                    continue
                sequences[' > '.join(three)] += 1
                future[three[2]] += 1
                repeats += len(set(three)) < 3
                for i, cid in enumerate(three):
                    position[i][cid] += 1
            n = sum(sequences.values())
            table[cell['id']] = {
                'n': n, 'unparsed': bad, 'top': sequences.most_common(1)[0][0] if n else None,
                'top_n': sequences.most_common(1)[0][1] if n else 0,
                'top_share': sequences.most_common(1)[0][1] / n if n else None,
                'distinct': len(sequences), 'effective': effective(sequences),
                'sequences': dict(sequences.most_common(12)),
                'future_bright_share': sum(future[c] for c in FUTURE_BRIGHT) / n if n else None,
                'future_hard_share': sum(future[c] for c in HARD_CARDS) / n if n else None,
                'positions': [dict(p.most_common(8)) for p in position], 'repeats': repeats,
            }
        elif cell['kind'] == 'sequence':
            position = [collections.Counter() for _ in range(SEQUENCE_LENGTH)]
            orders, repeats, chats = collections.Counter(), 0, 0
            for answers in cell_answers(cell):
                ids = [parse_card(a)[0] for a in answers]
                if any(c is None for c in ids):
                    bad += 1
                    for a, c in zip(answers, ids):
                        if c is None:
                            unparsed_all[(cell['cond'], normalize(a)[:60])] += 1
                    continue
                chats += 1
                repeats += len(set(ids)) < len(ids)
                orders[' > '.join(ids)] += 1
                for i, cid in enumerate(ids):
                    position[i][cid] += 1
            table[cell['id']] = {
                'n': chats, 'unparsed': bad, 'repeats': repeats,
                'repeat_share': repeats / chats if chats else None,
                'positions': [summarize(p) for p in position],
                'orders': dict(orders.most_common(8)), 'distinct_orders': len(orders),
                'top_order_share': orders.most_common(1)[0][1] / chats if chats else None,
            }

    def pooled(cond, model, variants=None):
        counter, bad = collections.Counter(), 0
        for cell in CELLS:
            if cell['cond'] == cond and cell['model'] == model and (variants is None or cell['variant'] in variants):
                for k, v in table[cell['id']]['counts'].items():
                    counter[k] += v
                bad += table[cell['id']]['unparsed']
        return summarize(counter, bad)

    created = json.loads((DATA / 'models.json').read_text())
    models = []
    for model, tier in MODELS:
        neutral = pooled('neutral', model)
        fair = table[f'fair.fair.{model}']
        against_uniform(neutral)
        against_uniform(fair)
        number = table[f'number.number.{model}']
        thinking = collections.Counter()
        for cell in CELLS:
            if cell['model'] == model and cell['cond'] == 'neutral':
                for row in read_rows(cell):
                    if 'answers' in row:
                        thinking['tokens'] += (row.get('usage') or {}).get('reasoning_tokens', 0)
                        thinking['answers'] += len(row['answers'])
        models.append({
            'id': model, 'tier': tier,
            'reasoning_per_draw': thinking['tokens'] / thinking['answers'] if thinking['answers'] else None,
            'released': datetime.date.fromtimestamp(created[model]).isoformat(),
            'neutral': neutral, 'fair': fair, 'number': number,
            'by_wording': {key: table[f'neutral.{key}.{model}'] for key in NEUTRAL},
        })
    by_model = {m['id']: m for m in models}
    chat = by_model[CHAT]
    dated = [m for m in models if m['id'] != CHAT]

    date_cells = [table[f'date.{d}.{CHAT}'] for d in DATES]
    date_pool = pooled('date', CHAT)
    if date_pool['n']:
        date_pool['dates_with_other_top'] = sum(1 for c in date_cells if c['top'] != date_pool['top'])
        date_pool['min_top_share'] = min(c['counts'].get(date_pool['top'], 0) / c['n'] for c in date_cells if c['n'])

    def group(cond, keys, models_):
        return {key: {model: table[f'{cond}.{key}.{model}'] for model in models_} for key in keys}

    topics = group('topic', TOPICS, [CHAT])
    zodiac = group('zodiac', [s.lower() for s in SIGNS], [CHAT])
    languages = group('language', LANGUAGES, [CHAT])

    class NotRun(Exception):
        """A registered hypothesis whose cells were dropped (A1)."""

    # ---- hypotheses. A cell that is still empty leaves its hypothesis undecided (holds = None); validate
    # refuses an export while any cell is short, so a published page never carries an undecided one.
    def h1():
        n = chat['neutral']
        return {'top': n['top'], 'share': n['top_share'], 'n': n['n']}, n['top'] == 'the-star' and n['top_share'] > 0.9

    def h2():
        rho = spearman([created[m['id']] for m in dated], [m['neutral']['effective'] for m in dated])
        early = [m for m in dated if m['released'] < '2026-04-01']  # A5
        rho_early = spearman([created[m['id']] for m in early], [m['neutral']['effective'] for m in early])
        y2026 = [m for m in dated if m['released'] >= '2026-01-01']
        widest = max(y2026, key=lambda m: m['neutral']['effective'])
        return ({'spearman': rho, 'spearman_before_april_2026': rho_early, 'models_before_april_2026': len(early),
                 'max_effective_2026': widest['neutral']['effective'], 'widest_2026': widest['id']},
                rho < 0 and widest['neutral']['effective'] < 3)

    def h3():
        widest = max(models, key=lambda m: m['fair']['effective'])
        return ({'max_effective': widest['fair']['effective'], 'model': widest['id'],
                 'max_effective_mm': max(m['fair']['effective_mm'] for m in models),
                 'chat_effective': chat['fair']['effective']},
                widest['fair']['effective'] < 39 and chat['fair']['effective'] < 10)

    def h4():
        most = max(models, key=lambda m: m['neutral']['minor_share'])
        return ({'max_minor_share': most['neutral']['minor_share'], 'model': most['id']},
                most['neutral']['minor_share'] < 0.10)

    def h5():
        most = max(models, key=lambda m: m['neutral']['hard_share'])
        return ({'chat': chat['neutral']['hard_share'], 'max': most['neutral']['hard_share'], 'model': most['id']},
                chat['neutral']['hard_share'] < 0.01 and most['neutral']['hard_share'] < 0.03)

    def h6():
        rev = table[f'reversal.reversal.{CHAT}']
        return {'reversed_share': rev['reversed_share'], 'n': rev['n']}, rev['reversed_share'] < 0.10

    def h7():
        t = {k: topics[k][CHAT] for k in TOPICS}
        love_ok = t['love']['top'] == 'the-lovers' or BY_ID[t['love']['top']]['suit'] == 'cups'
        money_ok = BY_ID[t['money']['top']]['suit'] == 'pentacles'
        return ({k: {'top': v['top'], 'share': v['top_share']} for k, v in t.items()},
                all(v['top_share'] > 0.5 for v in t.values()) and love_ok and money_ok)

    def h8():
        tops = {s: zodiac[s.lower()][CHAT]['top'] for s in SIGNS}
        if any(top is None for top in tops.values()):
            raise ValueError('a sign cell is empty')
        matches = [s for s in SIGNS if tops[s] == ZODIAC_CARD[s]]
        return {'matches': len(matches), 'signs': matches}, len(matches) >= 8

    def h9():
        raise NotRun('the mood cells were dropped for budget')

    def h10():
        cells_ = {k: languages[k][CHAT] for k in LANGUAGES}
        star = [k for k, v in cells_.items() if v['top'] == 'the-star']
        low = min(v['top_share'] for v in cells_.values())
        return ({'star_languages': len(star), 'others': {k: v['top'] for k, v in cells_.items() if v['top'] != 'the-star'},
                 'min_top_share': low}, len(star) >= 12 and low > 0.5)

    def h11():
        spread = table[f'spread.spread.{CHAT}']
        return ({'future_bright': spread['future_bright_share'], 'top': spread['top'], 'share': spread['top_share']},
                spread['future_bright_share'] > 0.9 and spread['top_share'] > 0.5)

    def h12():
        raise NotRun('the five-card chats were dropped for budget')

    def h13():
        share = date_pool['counts'].get('the-star', 0) / date_pool['n']
        return {'star_share': share, 'n': date_pool['n']}, share > 0.9

    def h14():
        number = chat['number']
        return {'top': number['top'], 'share': number['top_share']}, number['top_share'] > 0.2 and number['top'] in (37, 42)

    hyp = {}
    for key, fn in zip(HYPOTHESES, (h1, h2, h3, h4, h5, h6, h7, h8, h9, h10, h11, h12, h13, h14)):
        try:
            value, holds = fn()
            hyp[key] = {'value': value, 'holds': bool(holds)}
        except NotRun as reason:
            hyp[key] = {'value': None, 'holds': None, 'not_run': str(reason)}
        except (KeyError, TypeError, ZeroDivisionError, ValueError):
            hyp[key] = {'value': None, 'holds': None}
    for key in HYPOTHESES:
        hyp[key]['text'] = HYPOTHESES[key]

    resolved = collections.Counter()
    usage = collections.Counter()
    first_ts, last_ts, total_draws, spend = None, None, 0, 0.0
    for cell in CELLS:
        for row in read_rows(cell):
            if 'answers' not in row:
                continue
            if cell['model'] == CHAT:
                resolved[row.get('model')] += 1
            for k, v in (row.get('usage') or {}).items():
                usage[k] += v
            spend += cost(cell['model'], row.get('usage') or {})
            total_draws += len(row['answers'])
            first_ts = min(first_ts or row['ts'], row['ts'])
            last_ts = max(last_ts or row['ts'], row['ts'])

    chat_rows = [row for cell in CELLS if cell['cond'] == 'neutral' and cell['model'] == CHAT
                 for row in read_rows(cell) if 'answers' in row]
    chat_batch = {'requests': len(chat_rows), 'first': min(r['ts'] for r in chat_rows),
                  'last': max(r['ts'] for r in chat_rows)}

    result = {
        'models': models, 'topics': topics, 'zodiac': zodiac, 'languages': languages,
        'reversal': {m: table[f'reversal.reversal.{m}'] for m in [CHAT] + PANEL},
        'spread': {m: table[f'spread.spread.{m}'] for m in [CHAT] + PANEL},
        'single': table[f'single.n1.{CHAT}'],
        'free': {m: table[f'free.n1.{m}'] for m in FREE_MODELS},
        'free_set_aside': set_aside_free(), 'independence': independence(),
        'date': date_pool, 'hypotheses': hyp,
        'meta': {'total_draws': total_draws, 'first_request': first_ts, 'last_request': last_ts,
                 'chat_latest_resolved': dict(resolved), 'usage': dict(usage), 'estimated_cost_usd': round(spend, 2),
                 'loose_parses': sum(loose.values()), 'chat_neutral': chat_batch},
        'unparsed_top': [[cond, text, n] for (cond, text), n in unparsed_all.most_common(80)],
        'cells': table,
    }
    (DATA / 'computed.json').write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(f"{total_draws} answers; estimated cost ${spend:.2f}")
    for key in HYPOTHESES:
        verdict = {True: 'HOLDS', False: 'FAILS', None: 'NOT RUN'}[hyp[key]['holds']]
        print(key, verdict, json.dumps(hyp[key]['value'], ensure_ascii=False)[:160])
    if unparsed_all:
        print('unparsed answers:', sum(unparsed_all.values()))
        for (cond, text), n in unparsed_all.most_common(40):
            print('  ', n, cond, repr(text))
    return result


# ----------------------------------------------------------------------------------------------- validate

def validate():
    result = json.loads((DATA / 'computed.json').read_text())
    problems = []
    for cell in CELLS:
        got = have(cell)
        if got < cell['draws']:
            problems.append(f"{cell['id']}: {got} of {cell['draws']} draws")
        summary = result['cells'][cell['id']]
        total = summary['n'] + summary['unparsed']
        if total and summary['unparsed'] / total > 0.03:
            problems.append(f"{cell['id']}: {summary['unparsed']} of {total} answers not mapped to a card")
    # the n-per-request control: one completion per request must tell the same story
    chat_n1 = result['cells'][f'neutral.n1.{CHAT}']
    single = result['single']
    gap = abs(chat_n1['counts'].get(chat_n1['top'], 0) / chat_n1['n'] - single['counts'].get(chat_n1['top'], 0) / single['n'])
    if gap > 0.05:
        problems.append(f'single-completion control differs by {gap:.3f}')
    if abs(result['independence']['stouffer_z']) > 3:
        problems.append(f"completions inside a request are not independent: z = {result['independence']['stouffer_z']:.2f}")
    undecided = sorted(k for k, h in result['hypotheses'].items() if h['holds'] is None)
    if undecided != ['H12', 'H9'] or any('not_run' not in result['hypotheses'][k] for k in undecided):
        problems.append(f'undecided hypotheses: {undecided} (only H9 and H12 were dropped, A1)')
    # every published hypothesis text is the pre-registered one
    digest = hashlib.sha256(json.dumps(HYPOTHESES, sort_keys=True).encode()).hexdigest()
    checks = {'ok': not problems, 'problems': problems, 'single_gap': gap, 'hypotheses_sha256': digest,
              'cells': len(CELLS), 'checked': datetime.date.today().isoformat()}
    (DATA / 'validated.json').write_text(json.dumps(checks, indent=1))
    print(json.dumps(checks, indent=1)[:3000])
    return checks


# ----------------------------------------------------------------------------------------------- export

def slim(summary, keep=8):
    out = {k: v for k, v in summary.items() if k != 'counts'}
    if 'counts' in summary:
        out['top_cards'] = [[k, v] for k, v in list(summary['counts'].items())[:keep]]
    for key in ('top_share', 'effective', 'minor_share', 'hard_share', 'reversed_share', 'uniform_effective',
                'uniform_min', 'effective_mm'):
        if out.get(key) is not None:
            out[key] = round(out[key], 5)
    if 'top_ci' in out:
        out['top_ci'] = [round(x, 5) for x in out['top_ci']]
    return out


def export():
    checks = json.loads((DATA / 'validated.json').read_text())
    if not checks['ok'] and os.environ.get('AI_TAROT_DRAFT') != '1':
        raise SystemExit('validate has not passed; nothing written')
    if json.dumps(HYPOTHESES, sort_keys=True).encode() and checks['hypotheses_sha256'] != hashlib.sha256(
            json.dumps(HYPOTHESES, sort_keys=True).encode()).hexdigest():
        raise SystemExit('the hypotheses changed after validate; run validate again')
    result = json.loads((DATA / 'computed.json').read_text())
    cells = result.pop('cells')

    def walk(node):
        if isinstance(node, dict):
            if 'counts' in node and 'n' in node:
                return slim(node)
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, float):
            return round(node, 5)
        return node

    page = walk({k: v for k, v in result.items() if k != 'unparsed_top'})
    # every card each model drew on the neutral wordings (the page draws the deck from it)
    page['neutral_counts'] = {m['id']: m['neutral']['counts'] for m in result['models']}
    page['fair_counts'] = {m['id']: m['fair']['counts'] for m in result['models']}
    page['cards'] = [{'id': c['id'], 'name': c['name'], 'arcana': c['arcana'], 'suit': c['suit']} for c in CARDS]
    page['design'] = {
        'neutral': {k: v + FORMAT for k, v in NEUTRAL.items()}, 'fair': FAIR + FORMAT, 'number': NUMBER,
        'reversal': REVERSAL, 'spread': SPREAD, 'topics': TOPICS, 'languages': LANGUAGES,
        'language_names': LANGUAGE_NAMES, 'zodiac_card': ZODIAC_CARD, 'hard_cards': HARD_CARDS,
        'date_system': DATE_SYSTEM, 'dates': [DATES[0], DATES[-1], len(DATES)],
        'panel': PANEL, 'free_models': FREE_MODELS, 'chat': CHAT, 'main': MAIN + FORMAT,
    }
    page['added_after_count'] = ADDED_AFTER_COUNT
    page['validation'] = {k: checks[k] for k in ('ok', 'single_gap', 'hypotheses_sha256', 'cells')}
    JSON_OUT.write_text(json.dumps(page, ensure_ascii=False, separators=(',', ':')) + '\n')

    with CSV_OUT.open('w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['condition', 'variant', 'model', 'position', 'answer', 'count', 'cell_answers', 'cell_unparsed'])
        for cell in CELLS:
            summary = cells[cell['id']]
            if cell['kind'] == 'sequence':
                for i, pos in enumerate(summary['positions']):
                    for card, count in pos['counts'].items():
                        writer.writerow([cell['cond'], cell['variant'], cell['model'], i + 1, card, count, summary['n'], summary['unparsed']])
            elif cell['kind'] == 'spread':
                for i, pos in enumerate(summary['positions']):
                    for card, count in pos.items():
                        writer.writerow([cell['cond'], cell['variant'], cell['model'], i + 1, card, count, summary['n'], summary['unparsed']])
            else:
                for card, count in summary['counts'].items():
                    writer.writerow([cell['cond'], cell['variant'], cell['model'], '', card, count, summary['n'], summary['unparsed']])
                if cell['kind'] == 'reversal':
                    writer.writerow([cell['cond'], cell['variant'], cell['model'], '', '(reversed)', summary['reversed'], summary['n'], summary['unparsed']])
    if SCRIPT_COPY:
        shutil.copyfile(Path(__file__).resolve(), SCRIPT_COPY)
    print('wrote', JSON_OUT, CSV_OUT, SCRIPT_COPY or '')


def design():
    by_cond = collections.Counter()
    for cell in CELLS:
        by_cond[cell['cond']] += cell['draws'] * (SEQUENCE_LENGTH if cell['kind'] == 'sequence' else 1)
    for cond, n in by_cond.items():
        print(f'{cond:10s} {n:7d}')
    print(f"{'total':10s} {sum(by_cond.values()):7d}  in {len(CELLS)} cells")


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else ''
    if step == 'design':
        design()
    elif step == 'fetch':
        fetch(sys.argv[2] if len(sys.argv) > 2 else None)
    elif step == 'compute':
        compute()
    elif step == 'validate':
        validate()
    elif step == 'export':
        export()
    else:
        print('usage: ai_tarot_draws.py design | fetch [cell regex] | compute | validate | export')
