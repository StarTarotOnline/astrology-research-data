#!/usr/bin/env python3
"""How common is each rising sign (Ascendant sign), by geographic latitude.

Source of the numbers on https://startarot.online/research/rising-sign-by-latitude.
Needs Python 3 and pyswisseph (``pip install pyswisseph``). Run from the repo root:

    python3 scripts/research/rising_sign_by_latitude.py

Writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/rising-sign-by-latitude.json   data the page renders
    frontend/static/research/rising-sign-by-latitude.csv     downloadable long-format table
    frontend/static/research/rising_sign_by_latitude.py      a copy of this script, served next
                                                             to the page (the repository is private)

A copy downloaded from the page runs anywhere and writes rising-sign-by-latitude.json
and rising-sign-by-latitude.csv next to itself; the cross-check against the MC study
(``published_check``) runs only if mc-whole-sign-10th.csv lies next to it as well.

Method
------
At a fixed latitude the Ascendant depends on one number only: the local sidereal
time, expressed as the right ascension of the Midheaven (ARMC). Over a year of
birth dates the ARMC at any fixed clock time sweeps the whole 0–360° circle, so
ARMC is uniformly distributed across charts even though births cluster by hour.
We therefore sweep ARMC in equal steps (0.01°, i.e. 36 000 charts per latitude)
at every integer latitude 0–65° N, take the Ascendant from ``swisseph.houses_armc``
(pure geometry: no ephemeris files, no date besides the obliquity) and count how
often each sign is rising. The share of a sign is also its rising time: a share of
s % means the sign is on the eastern horizon for s % of the sidereal day, i.e.
0.24·s sidereal hours.

Exact check: below the polar circle the Ascendant moves monotonically with the
ARMC, so the share of a sign is exactly the ARMC interval between the moments its
two boundaries rise. The point λ of the ecliptic is on the eastern horizon when
ARMC = RA(λ) − H0(λ) with cos H0 = −tan φ tan δ. ``exact_check`` in the JSON
compares those interval lengths with the grid at six latitudes.

Southern hemisphere: the Ascendant at latitude −φ and sidereal time ARMC + 180° is
the point opposite the Ascendant at +φ and ARMC (the antipode of a rising point
rises at the antipodal latitude half a sidereal day later: φ and δ both change
sign, which leaves cos H0 = −tan φ tan δ, and so the hour angle of rising,
unchanged). A uniform sweep does not care about the 180° shift, so the
share of a sign at −φ equals the share of the OPPOSITE sign (Aries ↔ Libra,
Taurus ↔ Scorpio, …) at +φ, in either zodiac. ``southern_check`` verifies this by
direct computation at −30° and −52°.

Two zodiacs: tropical, and sidereal with the Lahiri ayanamsa of the reference
date subtracted from every longitude. The obliquity is the true obliquity of
2026-01-01 from ``swe.calc_ut(..., ECL_NUT)``; both constants are printed into
the JSON and are shared with scripts/research/mc_whole_sign_10th.py, whose CSV
``rising_share_pct`` column must agree with this one (``published_check``).

Robustness to the hour-of-birth distribution
--------------------------------------------
The uniform sweep is the limit of "births spread over the whole day and the whole
year". Real births cluster by clock hour (and, more weakly, by season). The
``robustness`` block measures how far three extreme scenarios move the shares,
using the real sidereal time of every day of 2026 (``swe.sidtime``):

* ``single_hour`` — ALL births at one clock time, uniform over the 365 days of
  the year, for every quarter-hour of the day (96 clock times). Any hour-of-day
  distribution is a mixture of these, so its shift is bounded by the worst one.
* ``seasonal_uniform_hours`` — births uniform over the day, with a ±10 % cosine
  seasonality by day of year, for twelve phases of the cosine.
* ``single_hour_seasonal`` — both at once.

The reported number is the largest absolute shift of any sign's share, in
percentage points, over every latitude, both zodiacs and every clock time /
phase. ``discrete_uniform`` (uniform clock times, uniform days) shows how much of
that is just the discreteness of the 96 × 365 grid.

Edge of the range
-----------------
Above the polar circle (90° − ε = 66.56°) part of the ecliptic never rises: the
Ascendant, as Swiss Ephemeris defines it there (the intersection with the horizon
that lies in the east), jumps by ~180° twice a day and runs backwards through the
zodiac for part of the day. ``edge`` tabulates that behaviour at 66–70° N so the
page can say precisely why the table stops at 65°.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import swisseph as swe

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
if (REPO_ROOT / "frontend" / "src" / "lib" / "research").is_dir():
    # In the StarTarot repository: rewrite the files the page is built from.
    JSON_OUT = REPO_ROOT / "frontend" / "src" / "lib" / "research" / "rising-sign-by-latitude.json"
    CSV_OUT = REPO_ROOT / "frontend" / "static" / "research" / "rising-sign-by-latitude.csv"
    SCRIPT_COPY = REPO_ROOT / "frontend" / "static" / "research" / "rising_sign_by_latitude.py"
    PUBLISHED_CSV = REPO_ROOT / "frontend" / "static" / "research" / "mc-whole-sign-10th.csv"
else:
    # A copy downloaded from the page: the repository paths do not exist here.
    JSON_OUT = HERE / "rising-sign-by-latitude.json"
    CSV_OUT = HERE / "rising-sign-by-latitude.csv"
    SCRIPT_COPY = None
    PUBLISHED_CSV = HERE / "mc-whole-sign-10th.csv"

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
LATITUDES = list(range(0, 66))  # 0–65° N inclusive
STEP_DEG = 0.01  # ARMC step for the main sweep (same as mc_whole_sign_10th.py)
REFERENCE_DATE = (2026, 1, 1)  # obliquity and ayanamsa epoch (same as mc_whole_sign_10th.py)
EXACT_CHECK_LATITUDES = (0, 30, 45, 52, 60, 65)
SOUTHERN_CHECK_LATITUDES = (-30, -52)
EDGE_LATITUDES = (66, 66.5, 67, 68, 70)
ZODIACS = ("tropical", "sidereal_lahiri")

# Robustness scenarios: real sidereal time of every day of this year, at every
# quarter-hour of the clock, with an optional ±10 % cosine seasonality.
ROBUSTNESS_YEAR = 2026
ROBUSTNESS_CLOCK_TIMES = 96  # every 15 minutes
ROBUSTNESS_SEASONAL_AMPLITUDE = 0.10
ROBUSTNESS_SEASONAL_PHASES = 12


def sign_of(lon: float) -> int:
    return int(math.floor((lon % 360.0) / 30.0)) % 12


def ascendant(armc: float, lat: float, eps: float) -> float:
    return swe.houses_armc(armc % 360.0, lat, eps, b"O")[1][0]


def sweep(lat: float, eps: float, ayanamsa: float, step: float) -> dict[str, list[int]]:
    """Counts of charts per rising sign for both zodiacs on a uniform ARMC grid."""
    n = int(round(360.0 / step))
    trop = [0] * 12
    sid = [0] * 12
    for k in range(n):
        armc = (k + 0.5) * step  # half-step offset keeps the Ascendant off exact boundaries
        asc = ascendant(armc, lat, eps)
        trop[sign_of(asc)] += 1
        sid[sign_of(asc - ayanamsa)] += 1
    return {"samples": [n], "tropical": trop, "sidereal_lahiri": sid}


def exact_shares(lat: float, eps: float, ayanamsa: float) -> dict[str, list[float]]:
    """Share of each rising sign (%) with no grid: ARMC interval between the
    rising of the sign's two boundaries (valid below the polar circle only)."""
    phi = math.radians(lat)
    e = math.radians(eps)

    def rising_armc(lon: float) -> float:
        lam = math.radians(lon)
        ra = math.degrees(math.atan2(math.sin(lam) * math.cos(e), math.cos(lam))) % 360.0
        dec = math.asin(math.sin(lam) * math.sin(e))
        h0 = math.degrees(math.acos(-math.tan(phi) * math.tan(dec)))
        return (ra - h0) % 360.0

    out = {}
    for zodiac, offset in (("tropical", 0.0), ("sidereal_lahiri", ayanamsa)):
        points = [rising_armc(30.0 * k + offset) for k in range(12)]
        out[zodiac] = [
            round(100.0 * ((points[(k + 1) % 12] - points[k]) % 360.0) / 360.0, 4) for k in range(12)
        ]
    return out


def edge_behaviour(lat: float, eps: float, step: float) -> dict:
    """What the Ascendant does at and above the polar circle: 180° jumps,
    retrograde motion through the zodiac, signs that never rise."""
    n = int(round(360.0 / step))
    counts = [0] * 12
    jumps = 0
    retrograde = 0
    prev = None
    for k in range(n):
        asc = ascendant((k + 0.5) * step, lat, eps)
        counts[sign_of(asc)] += 1
        if prev is not None:
            delta = (asc - prev + 180.0) % 360.0 - 180.0
            if abs(delta) > 90.0:
                jumps += 1
            elif delta < 0:
                retrograde += 1
        prev = asc
    return {
        "latitude": lat,
        "samples": n,
        "tropical_shares": [pct(c, n) for c in counts],
        "jumps": jumps,
        "retrograde_share_pct": pct(retrograde, n),
        "never_rising_signs": [SIGNS[i] for i, c in enumerate(counts) if c == 0],
    }


def pct(num: float, den: float, digits: int = 2) -> float:
    return round(100.0 * num / den, digits) if den else 0.0


def hours(share_pct: float) -> float:
    """Rising time in sidereal hours: the share of the 24-hour sidereal day."""
    return round(24.0 * share_pct / 100.0, 3)


def summarise(counts: list[int], n: int) -> dict:
    shares = [pct(c, n) for c in counts]
    rarest = min(range(12), key=lambda i: (counts[i], i))
    commonest = max(range(12), key=lambda i: (counts[i], -i))
    return {
        "shares": shares,
        "hours": [hours(s) for s in shares],
        "rarest": {"sign": SIGNS[rarest], "share": shares[rarest]},
        "commonest": {"sign": SIGNS[commonest], "share": shares[commonest]},
        # From raw counts, not from the rounded shares.
        "ratio": round(counts[commonest] / counts[rarest], 2) if counts[rarest] else None,
    }


def robustness_armcs() -> tuple[list[list[float]], list[int]]:
    """ARMC (deg) for every (clock time, day) of the robustness year, at longitude 0;
    the clock-time phase is what the 96 clock times sweep, so longitude is immaterial."""
    jd0 = swe.julday(ROBUSTNESS_YEAR, 1, 1, 0.0)
    days = 366 if (ROBUSTNESS_YEAR % 4 == 0 and (ROBUSTNESS_YEAR % 100 or not ROBUSTNESS_YEAR % 400)) else 365
    grid = []
    for t in range(ROBUSTNESS_CLOCK_TIMES):
        hour = 24.0 * t / ROBUSTNESS_CLOCK_TIMES
        grid.append([(swe.sidtime(jd0 + d + hour / 24.0) * 15.0) % 360.0 for d in range(days)])
    return grid, list(range(days))


def robustness_at(lat: float, eps: float, ayanamsa: float, grid: list[list[float]],
                  base: dict[str, list[float]]) -> dict:
    """Largest absolute shift (pp) of any sign's share under each scenario, at one latitude."""
    days = len(grid[0])
    # sign index per (clock time, day), both zodiacs
    signs = {z: [] for z in ZODIACS}
    for row in grid:
        trop_row = []
        sid_row = []
        for armc in row:
            asc = ascendant(armc, lat, eps)
            trop_row.append(sign_of(asc))
            sid_row.append(sign_of(asc - ayanamsa))
        signs["tropical"].append(trop_row)
        signs["sidereal_lahiri"].append(sid_row)

    weights = [
        [1.0 + ROBUSTNESS_SEASONAL_AMPLITUDE * math.cos(2.0 * math.pi * (d / days - p / ROBUSTNESS_SEASONAL_PHASES))
         for d in range(days)]
        for p in range(ROBUSTNESS_SEASONAL_PHASES)
    ]

    def shift(counts: list[float], total: float, zodiac: str) -> float:
        return max(abs(100.0 * counts[i] / total - base[zodiac][i]) for i in range(12))

    out = {"discrete_uniform": 0.0, "single_hour": 0.0,
           "seasonal_uniform_hours": 0.0, "single_hour_seasonal": 0.0}
    for zodiac in ZODIACS:
        rows = signs[zodiac]
        # discrete uniform: every clock time, every day, weight 1
        counts = [0.0] * 12
        for row in rows:
            for s in row:
                counts[s] += 1
        out["discrete_uniform"] = max(out["discrete_uniform"], shift(counts, len(rows) * days, zodiac))
        # single clock time, uniform days
        for row in rows:
            counts = [0.0] * 12
            for s in row:
                counts[s] += 1
            out["single_hour"] = max(out["single_hour"], shift(counts, days, zodiac))
        # seasonality with uniform clock times, and combined with a single clock time
        for w in weights:
            total_w = sum(w)
            all_counts = [0.0] * 12
            for row in rows:
                counts = [0.0] * 12
                for d, s in enumerate(row):
                    counts[s] += w[d]
                out["single_hour_seasonal"] = max(out["single_hour_seasonal"], shift(counts, total_w, zodiac))
                for i in range(12):
                    all_counts[i] += counts[i]
            out["seasonal_uniform_hours"] = max(
                out["seasonal_uniform_hours"], shift(all_counts, total_w * len(rows), zodiac))
    return {key: round(value, 3) for key, value in out.items()}


def published_check(rows: list[dict]) -> dict | None:
    """The MC study's CSV carries the same rising-sign shares (rising_share_pct);
    both scripts share the grid, the obliquity and the ayanamsa, so they must agree.
    None when that CSV is not at hand (a downloaded copy of this script)."""
    if not PUBLISHED_CSV.is_file():
        return None
    by_lat = {row["latitude"]: row for row in rows}
    compared = 0
    max_diff = {z: 0.0 for z in ZODIACS}
    with PUBLISHED_CSV.open(encoding="utf-8") as fh:
        for line in csv.DictReader(fh):
            if line["rising_sign"] == "all":
                continue
            zodiac = line["zodiac"]
            lat = int(line["latitude_deg"])
            ours = by_lat[lat][zodiac]["shares"][SIGNS.index(line["rising_sign"])]
            max_diff[zodiac] = max(max_diff[zodiac], abs(ours - float(line["rising_share_pct"])))
            compared += 1
    return {
        "csv": (PUBLISHED_CSV.relative_to(REPO_ROOT / "frontend").as_posix()
                if SCRIPT_COPY is not None else PUBLISHED_CSV.name),
        "column": "rising_share_pct",
        "rows_compared": compared,
        "tropical_max_abs_diff_pct": round(max_diff["tropical"], 4),
        "sidereal_lahiri_max_abs_diff_pct": round(max_diff["sidereal_lahiri"], 4),
    }


def main() -> int:
    jd = swe.julday(*REFERENCE_DATE, 0.0)
    eps = swe.calc_ut(jd, swe.ECL_NUT)[0][0]
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd)
    print(f"obliquity (true, {REFERENCE_DATE}) = {eps:.6f}°, Lahiri ayanamsa = {ayanamsa:.6f}°",
          file=sys.stderr)

    rows = []
    for lat in LATITUDES:
        r = sweep(lat, eps, ayanamsa, STEP_DEG)
        n = r["samples"][0]
        row = {"latitude": lat, "samples": n}
        for zodiac in ZODIACS:
            row[zodiac] = summarise(r[zodiac], n)
        rows.append(row)
        t = row["tropical"]
        print(f"lat {lat:2d}: rarest {t['rarest']['sign']} {t['rarest']['share']:5.2f}%  "
              f"commonest {t['commonest']['sign']} {t['commonest']['share']:5.2f}%  ratio {t['ratio']}",
              file=sys.stderr)

    # Grid vs exact interval computation.
    exact_check = []
    for lat in EXACT_CHECK_LATITUDES:
        exact = exact_shares(lat, eps, ayanamsa)
        grid = next(r for r in rows if r["latitude"] == lat)
        exact_check.append({
            "latitude": lat,
            "max_abs_diff_pct": round(max(
                abs(grid[z]["shares"][i] - exact[z][i]) for z in ZODIACS for i in range(12)), 4),
            "tropical_exact": exact["tropical"],
            "sidereal_lahiri_exact": exact["sidereal_lahiri"],
        })

    # Southern hemisphere: −φ equals +φ with every sign replaced by its opposite.
    southern_check = []
    for lat in SOUTHERN_CHECK_LATITUDES:
        south = sweep(lat, eps, ayanamsa, STEP_DEG)
        n = south["samples"][0]
        north = next(r for r in rows if r["latitude"] == -lat)
        entry = {"latitude": lat, "north_latitude": -lat}
        for zodiac in ZODIACS:
            south_shares = [pct(c, n) for c in south[zodiac]]
            opposite = [north[zodiac]["shares"][(i + 6) % 12] for i in range(12)]
            entry[zodiac] = {
                "south_shares": south_shares,
                "north_opposite_shares": opposite,
                "max_abs_diff_pct": round(max(abs(a - b) for a, b in zip(south_shares, opposite)), 4),
            }
        southern_check.append(entry)

    # Agreement with the already published MC study.
    published = published_check(rows)

    # Robustness to the hour-of-birth and season-of-birth distributions.
    grid, _days = robustness_armcs()
    robustness_rows = []
    worst = {"discrete_uniform": 0.0, "single_hour": 0.0,
             "seasonal_uniform_hours": 0.0, "single_hour_seasonal": 0.0}
    for row in rows:
        base = {z: row[z]["shares"] for z in ZODIACS}
        shifts = robustness_at(row["latitude"], eps, ayanamsa, grid, base)
        robustness_rows.append({"latitude": row["latitude"], **shifts})
        for key in worst:
            worst[key] = max(worst[key], shifts[key])
        print(f"lat {row['latitude']:2d}: robustness single-hour {shifts['single_hour']:.3f} pp, "
              f"seasonal {shifts['seasonal_uniform_hours']:.3f} pp, "
              f"combined {shifts['single_hour_seasonal']:.3f} pp", file=sys.stderr)

    # Edge of the range.
    edge = [edge_behaviour(lat, eps, STEP_DEG) for lat in EDGE_LATITUDES]

    payload = {
        "generated_by": "scripts/research/rising_sign_by_latitude.py",
        "reference_date": "%04d-%02d-%02d" % REFERENCE_DATE,
        "obliquity_deg": round(eps, 6),
        "polar_circle_deg": round(90.0 - eps, 2),
        "ayanamsa_lahiri_deg": round(ayanamsa, 6),
        "armc_step_deg": STEP_DEG,
        "samples_per_latitude": int(round(360.0 / STEP_DEG)),
        "latitude_range": [LATITUDES[0], LATITUDES[-1]],
        "swisseph_version": swe.version,
        "signs": SIGNS,
        "zodiacs": list(ZODIACS),
        "latitudes": rows,
        "exact_check": exact_check,
        "southern_check": southern_check,
        "published_check": published,
        "robustness": {
            "year": ROBUSTNESS_YEAR,
            "clock_times": ROBUSTNESS_CLOCK_TIMES,
            "days": len(grid[0]),
            "seasonal_amplitude_pct": round(100.0 * ROBUSTNESS_SEASONAL_AMPLITUDE),
            "seasonal_phases": ROBUSTNESS_SEASONAL_PHASES,
            "max_shift_pct": {key: round(value, 3) for key, value in worst.items()},
            "by_latitude": robustness_rows,
        },
        "edge": edge,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # share_pct: share of all charts at the latitude with that rising sign;
        # rising_hours: the same share as sidereal hours of the 24-hour sidereal day.
        w.writerow(["latitude_deg", "zodiac", "sign", "share_pct", "rising_hours"])
        for row in rows:
            for zodiac in ZODIACS:
                for i, sign in enumerate(SIGNS):
                    w.writerow([row["latitude"], zodiac, sign,
                                row[zodiac]["shares"][i], row[zodiac]["hours"][i]])

    if SCRIPT_COPY is not None:
        SCRIPT_COPY.write_bytes(Path(__file__).read_bytes())

    print(f"published check: {published if published else f'skipped, no {PUBLISHED_CSV.name} here'}",
          file=sys.stderr)
    print(f"robustness max shifts (pp): {payload['robustness']['max_shift_pct']}", file=sys.stderr)
    print(f"wrote {JSON_OUT} and {CSV_OUT}", file=sys.stderr)
    ok = ((published is None or published["tropical_max_abs_diff_pct"] == 0.0)
          and all(e["max_abs_diff_pct"] <= 0.01 for e in exact_check)
          and all(e[z]["max_abs_diff_pct"] == 0.0 for e in southern_check for z in ZODIACS))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
