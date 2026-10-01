#!/usr/bin/env python3
"""How often the MC falls in the whole-sign 10th house, by latitude and rising sign,
and when Porphyry houses produce intercepted signs.

Source of the numbers on https://startarot.online/research/mc-whole-sign-10th-house.
Needs Python 3 and pyswisseph (``pip install pyswisseph``). Run from the repo root:

    python3 scripts/research/mc_whole_sign_10th.py

Writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/mc-whole-sign-10th.json   data the page renders
    frontend/static/research/mc-whole-sign-10th.csv     downloadable long-format table
    frontend/static/research/mc_whole_sign_10th.py      a copy of this script, served next
                                                        to the page (the repository is private)

A copy downloaded from the page runs anywhere and writes mc-whole-sign-10th.json
and mc-whole-sign-10th.csv next to itself.

Method
------
A chart is fixed, for house purposes, by two numbers: the geographic latitude and
the local sidereal time (ARMC, the right ascension of the MC). Over a full year of
birth dates the ARMC at any fixed clock time sweeps the whole 0–360° circle, so
ARMC is uniformly distributed across charts even though births cluster by hour.
We therefore sweep ARMC in equal steps (default 0.01°, i.e. 36 000 charts per
latitude) at each integer latitude 0–65° N, compute the cusps with
``swisseph.houses_armc`` (pure geometry: no ephemeris files, no date besides the
obliquity), and count — both the binary "MC in the whole-sign 10th" flag and the
full distribution of the whole-sign house the MC falls in.

Exact check: below the polar circle both the MC and the Ascendant move
monotonically with the ARMC, so the flag changes only where one of them crosses a
sign boundary — 24 breakpoints per latitude. The share is then a sum of interval
lengths with no grid at all; ``exact_check`` in the JSON compares it with the
grid result at four latitudes.

The ecliptic obliquity is the true obliquity of date on 2026-01-01 (from
``swe.calc_ut(..., ECL_NUT)``); the sidereal comparison subtracts the Lahiri
ayanamsa of the same date. Both are printed into the JSON. The sensitivity block
shows how much the headline shares move when the obliquity is shifted by ±0.05°
(more than its change over a human lifetime); the epoch block, how much the
sidereal shares (the totals and the shares by rising sign) move when the ayanamsa is
taken for 1950 instead, at every latitude.

Applicability
-------------
Latitudes 0–65° only. Above the polar circle (66.56°) part of the ecliptic never
rises and the opposite part never sets; the Ascendant (the eastern intersection of
ecliptic and horizon) jumps by about 180° twice a day and runs backwards in
between, and Placidus and Koch are not defined: Swiss Ephemeris switches to
Porphyry and reports it only as an error ("within polar circle, switched to
Porphyry"). Southern latitudes mirror the northern ones sign-for-sign
(Aries ↔ Libra etc.) and are not tabulated. Results are per chart, not per person:
the sweep weights every sidereal time equally, which is what a year of births does.

Definitions
-----------
* Rising sign: the sign of the Ascendant.
* "MC in the whole-sign 10th": the MC lies in the sign that is 9 signs after the
  rising sign (the tenth sign counting the rising sign as the first).
* Intercepted sign: a sign that contains no house cusp. Two intercepted signs
  always appear together (opposite each other) in any quadrant system.

Theorem verified here (and provable — see the page): with Porphyry houses a chart
has intercepted signs if and only if the MC is NOT in the whole-sign 10th house.
The "if" half holds for every quadrant system (Placidus, Koch, Regiomontanus,
Campanus, …); the "only if" half is specific to Porphyry's equal trisection.
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import swisseph as swe

HERE = Path(__file__).resolve().parent
# A downloaded copy may sit in a top-level folder (`/content` in Colab), where
# `HERE.parents[1]` does not exist.
REPO_ROOT = HERE.parents[1] if len(HERE.parents) > 1 else HERE
if (REPO_ROOT / "frontend" / "src" / "lib" / "research").is_dir():
    # In the StarTarot repository: rewrite the files the page is built from.
    JSON_OUT = REPO_ROOT / "frontend" / "src" / "lib" / "research" / "mc-whole-sign-10th.json"
    CSV_OUT = REPO_ROOT / "frontend" / "static" / "research" / "mc-whole-sign-10th.csv"
    SCRIPT_COPY = REPO_ROOT / "frontend" / "static" / "research" / "mc_whole_sign_10th.py"
else:
    # A copy downloaded from the page: the repository paths do not exist here.
    JSON_OUT = HERE / "mc-whole-sign-10th.json"
    CSV_OUT = HERE / "mc-whole-sign-10th.csv"
    SCRIPT_COPY = None

SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
LATITUDES = list(range(0, 66))  # 0–65° N inclusive
STEP_DEG = 0.01  # ARMC step for the main sweep
OTHER_SYSTEMS_STEP_DEG = 0.1  # coarser sweep for the cross-system check
REFERENCE_DATE = (2026, 1, 1)
# Quadrant systems that keep MC = cusp 10 and ASC = cusp 1 and split each quadrant
# into three houses. Alcabitius ('B') is included as a classical one.
OTHER_QUADRANT_SYSTEMS = {"P": "Placidus", "K": "Koch", "R": "Regiomontanus",
                          "C": "Campanus", "B": "Alcabitius"}
EXACT_CHECK_LATITUDES = (0, 45, 52, 60)  # grid vs. exact interval computation
SOUTHERN_CHECK_LATITUDE = -52  # mirror check: −φ equals +φ with the rising signs swapped
# How much the ayanamsa epoch moves the sidereal shares, counted in the main sweep at
# every latitude: the largest shift is near 61° N, not at the ends of the range.
AYANAMSA_EPOCH_CHECK = (1950, 1, 1)


def sign_of(lon: float) -> int:
    return int(math.floor((lon % 360.0) / 30.0)) % 12


def mc_whole_sign_house(asc: float, mc: float) -> int:
    """Whole-sign house of the MC, 1–12, counting the rising sign as the first."""
    return (sign_of(mc) - sign_of(asc)) % 12 + 1


def mc_in_whole_sign_10th(asc: float, mc: float) -> bool:
    return mc_whole_sign_house(asc, mc) == 10


def has_interception(cusps: tuple[float, ...]) -> bool:
    return len({sign_of(c) for c in cusps}) < 12


def sweep(lat: float, eps: float, step: float, ayanamsa: float, epoch_ayanamsa: float | None = None):
    """One latitude. Returns per-rising-sign counters for tropical and sidereal
    zodiacs, plus Porphyry interception counters and the theorem check; with
    ``epoch_ayanamsa``, also the sidereal counters for that second ayanamsa."""
    n = int(round(360.0 / step))
    trop_rising = [0] * 12
    trop_hit = [0] * 12
    trop_house = [[0] * 12 for _ in range(12)]  # [rising sign][MC house − 1]
    sid_rising = [0] * 12
    sid_hit = [0] * 12
    sid_house = [[0] * 12 for _ in range(12)]
    porphyry_no_interception = 0
    theorem_mismatch = 0
    epoch_rising = [0] * 12
    epoch_hit = [0] * 12
    for k in range(n):
        armc = (k + 0.5) * step  # half-step offset keeps cusps off exact sign boundaries
        cusps, ascmc = swe.houses_armc(armc, lat, eps, b"O")
        asc, mc = ascmc[0], ascmc[1]
        rising = sign_of(asc)
        trop_rising[rising] += 1
        house = mc_whole_sign_house(asc, mc)
        trop_house[rising][house - 1] += 1
        in_10th = house == 10
        if in_10th:
            trop_hit[rising] += 1
        intercepted = has_interception(cusps)
        if not intercepted:
            porphyry_no_interception += 1
        if in_10th == intercepted:
            theorem_mismatch += 1
        # Sidereal: same geometry, every longitude shifted by the ayanamsa.
        asc_s, mc_s = asc - ayanamsa, mc - ayanamsa
        rising_s = sign_of(asc_s)
        sid_rising[rising_s] += 1
        house_s = mc_whole_sign_house(asc_s, mc_s)
        sid_house[rising_s][house_s - 1] += 1
        if house_s == 10:
            sid_hit[rising_s] += 1
        if epoch_ayanamsa is not None:
            asc_e, mc_e = asc - epoch_ayanamsa, mc - epoch_ayanamsa
            rising_e = sign_of(asc_e)
            epoch_rising[rising_e] += 1
            if mc_in_whole_sign_10th(asc_e, mc_e):
                epoch_hit[rising_e] += 1
    return {
        "samples": n,
        "tropical": {"rising": trop_rising, "hit": trop_hit, "house": trop_house},
        "sidereal": {"rising": sid_rising, "hit": sid_hit, "house": sid_house},
        "porphyry_no_interception": porphyry_no_interception,
        "theorem_mismatch": theorem_mismatch,
        "sidereal_at_epoch": {"rising": epoch_rising, "hit": epoch_hit},
    }


def exact_share(lat: float, eps: float) -> float:
    """Share of ARMC (in %) with the MC in the whole-sign 10th, with no grid.

    Below the polar circle the MC and the Ascendant both move monotonically with
    the ARMC, so the flag can change only where the MC or the Ascendant crosses
    a sign boundary. The MC is at longitude λ when ARMC = RA(λ); the point λ is
    on the eastern horizon when its hour angle is −H0 with cos H0 = −tan φ tan δ,
    i.e. when ARMC = RA(λ) − H0. That gives 24 breakpoints; the flag is sampled
    once inside each interval and the interval lengths are summed.
    """
    phi = math.radians(lat)
    e = math.radians(eps)
    points = []
    for k in range(12):
        lam = math.radians(30.0 * k)
        ra = math.degrees(math.atan2(math.sin(lam) * math.cos(e), math.cos(lam))) % 360.0
        dec = math.asin(math.sin(lam) * math.sin(e))
        h0 = math.degrees(math.acos(-math.tan(phi) * math.tan(dec)))
        points.append(ra)  # MC crosses 30k°
        points.append((ra - h0) % 360.0)  # Ascendant crosses 30k°
    points = sorted(set(points))
    total = 0.0
    for i, start in enumerate(points):
        end = points[(i + 1) % len(points)]
        length = (end - start) % 360.0 if i + 1 < len(points) else (end + 360.0 - start)
        mid = (start + length / 2.0) % 360.0
        _, ascmc = swe.houses_armc(mid, lat, eps, b"O")
        if mc_in_whole_sign_10th(ascmc[0], ascmc[1]):
            total += length
    return round(100.0 * total / 360.0, 4)


def sweep_other_systems(lat: float, eps: float, step: float):
    """Cross-system check: does "MC outside whole-sign 10th ⇒ intercepted" hold,
    and how often do charts WITH the MC in the 10th still have interceptions?"""
    n = int(round(360.0 / step))
    out = {}
    for code, name in OTHER_QUADRANT_SYSTEMS.items():
        outside_without_interception = 0
        inside_with_interception = 0
        inside = 0
        for k in range(n):
            armc = (k + 0.5) * step
            cusps, ascmc = swe.houses_armc(armc, lat, eps, code.encode())
            in_10th = mc_in_whole_sign_10th(ascmc[0], ascmc[1])
            intercepted = has_interception(cusps)
            if in_10th:
                inside += 1
                if intercepted:
                    inside_with_interception += 1
            elif not intercepted:
                outside_without_interception += 1
        out[code] = {
            "name": name,
            "samples": n,
            "mc_in_10th": inside,
            "mc_in_10th_with_interception": inside_with_interception,
            "mc_outside_10th_without_interception": outside_without_interception,
        }
    return out


def pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 2) if den else 0.0


def house_shares(counts: list[int], den: int) -> dict[str, float]:
    """Non-zero whole-sign houses of the MC → share in %, keyed by house number."""
    return {str(i + 1): pct(c, den) for i, c in enumerate(counts) if c}


def main() -> int:
    jd = swe.julday(*REFERENCE_DATE, 0.0)
    eps_true = swe.calc_ut(jd, swe.ECL_NUT)[0][0]
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    ayanamsa = swe.get_ayanamsa_ut(jd)
    # The same Lahiri ayanamsa taken for a much earlier date (epoch check below).
    ayanamsa_epoch = swe.get_ayanamsa_ut(swe.julday(*AYANAMSA_EPOCH_CHECK, 0.0))
    print(f"obliquity (true, {REFERENCE_DATE}) = {eps_true:.6f}°, Lahiri ayanamsa = {ayanamsa:.6f}°",
          file=sys.stderr)

    rows = []
    epoch_counts = {}
    total_mismatch = 0
    for lat in LATITUDES:
        r = sweep(lat, eps_true, STEP_DEG, ayanamsa, ayanamsa_epoch)
        epoch_counts[lat] = r["sidereal_at_epoch"]
        total_mismatch += r["theorem_mismatch"]
        n = r["samples"]
        trop_total = sum(r["tropical"]["hit"])
        sid_total = sum(r["sidereal"]["hit"])
        trop_house_all = [sum(r["tropical"]["house"][s][h] for s in range(12)) for h in range(12)]
        sid_house_all = [sum(r["sidereal"]["house"][s][h] for s in range(12)) for h in range(12)]
        rows.append({
            "latitude": lat,
            "samples": n,
            "tropical_share": pct(trop_total, n),
            "sidereal_lahiri_share": pct(sid_total, n),
            "porphyry_no_interception_share": pct(r["porphyry_no_interception"], n),
            "theorem_mismatch": r["theorem_mismatch"],
            # Whole-sign house of the MC across all charts, share in % by house number.
            "mc_house_shares": house_shares(trop_house_all, n),
            "sidereal_mc_house_shares": house_shares(sid_house_all, n),
            "by_rising_sign": [
                {
                    "sign": SIGNS[i],
                    "rising_count": r["tropical"]["rising"][i],
                    "mc_in_10th_count": r["tropical"]["hit"][i],
                    "rising_share": pct(r["tropical"]["rising"][i], n),
                    "mc_in_10th_share": pct(r["tropical"]["hit"][i], r["tropical"]["rising"][i]),
                    "mc_house_shares": house_shares(r["tropical"]["house"][i], r["tropical"]["rising"][i]),
                    "sidereal_rising_share": pct(r["sidereal"]["rising"][i], n),
                    "sidereal_mc_in_10th_share": pct(r["sidereal"]["hit"][i], r["sidereal"]["rising"][i]),
                    "sidereal_mc_house_shares": house_shares(r["sidereal"]["house"][i], r["sidereal"]["rising"][i]),
                }
                for i in range(12)
            ],
        })
        print(f"lat {lat:2d}: tropical {rows[-1]['tropical_share']:5.1f}%  sidereal "
              f"{rows[-1]['sidereal_lahiri_share']:5.1f}%  porphyry-no-interception "
              f"{rows[-1]['porphyry_no_interception_share']:5.1f}%  mismatches {r['theorem_mismatch']}",
              file=sys.stderr)

    # Obliquity sensitivity at the check latitudes.
    sensitivity = []
    for lat in EXACT_CHECK_LATITUDES:
        base = next(row for row in rows if row["latitude"] == lat)["tropical_share"]
        shifted = []
        for d_eps in (-0.05, 0.05):
            r = sweep(lat, eps_true + d_eps, STEP_DEG, ayanamsa)
            shifted.append(pct(sum(r["tropical"]["hit"]), r["samples"]))
        sensitivity.append({"latitude": lat, "share": base,
                            "share_at_minus_0_05": shifted[0], "share_at_plus_0_05": shifted[1]})

    # Cross-system check on a coarser grid at every 5°.
    other_systems = []
    for lat in range(0, 66, 5):
        other_systems.append({"latitude": lat, "systems": sweep_other_systems(lat, eps_true, OTHER_SYSTEMS_STEP_DEG)})

    forward_violations = sum(
        s["mc_outside_10th_without_interception"]
        for entry in other_systems for s in entry["systems"].values()
    )

    # Grid vs. exact: proves the 0.01° step is fine at two decimals.
    exact_check = [
        {"latitude": lat,
         "grid_share": next(r for r in rows if r["latitude"] == lat)["tropical_share"],
         "exact_share": exact_share(lat, eps_true)}
        for lat in EXACT_CHECK_LATITUDES
    ]

    # Southern hemisphere: −φ gives the same totals as +φ with the rising signs
    # swapped for their opposites (Aries ↔ Libra, …).
    south = sweep(SOUTHERN_CHECK_LATITUDE, eps_true, STEP_DEG, ayanamsa)
    north = next(r for r in rows if r["latitude"] == -SOUTHERN_CHECK_LATITUDE)
    southern_check = {
        "latitude": SOUTHERN_CHECK_LATITUDE,
        "tropical_share": pct(sum(south["tropical"]["hit"]), south["samples"]),
        "north_tropical_share": north["tropical_share"],
        "by_rising_sign": [
            {"sign": SIGNS[i],
             "mc_in_10th_share": pct(south["tropical"]["hit"][i], south["tropical"]["rising"][i]),
             "north_opposite_sign": SIGNS[(i + 6) % 12],
             "north_opposite_share": north["by_rising_sign"][(i + 6) % 12]["mc_in_10th_share"]}
            for i in range(12)
        ],
    }

    # Ayanamsa epoch: the same Lahiri ayanamsa taken for a much earlier date. It moves
    # the sign boundaries, so the shares by rising sign move far more than the totals.
    ayanamsa_sensitivity = []
    for row in rows:
        epoch = epoch_counts[row["latitude"]]
        sign_shift = [
            abs(pct(epoch["hit"][i], epoch["rising"][i]) - row["by_rising_sign"][i]["sidereal_mc_in_10th_share"])
            for i in range(12)
        ]
        worst = max(range(12), key=lambda i: sign_shift[i])
        ayanamsa_sensitivity.append({
            "latitude": row["latitude"],
            "sidereal_lahiri_share": row["sidereal_lahiri_share"],
            "sidereal_share_at_epoch": pct(sum(epoch["hit"]), row["samples"]),
            "max_rising_sign_shift": round(sign_shift[worst], 2),
            "max_rising_sign_shift_sign": SIGNS[worst],
        })

    payload = {
        "generated_by": "scripts/research/mc_whole_sign_10th.py",
        "reference_date": "%04d-%02d-%02d" % REFERENCE_DATE,
        "obliquity_deg": round(eps_true, 6),
        "ayanamsa_lahiri_deg": round(ayanamsa, 6),
        "armc_step_deg": STEP_DEG,
        "other_systems_step_deg": OTHER_SYSTEMS_STEP_DEG,
        "samples_per_latitude": int(round(360.0 / STEP_DEG)),
        "latitude_range": [LATITUDES[0], LATITUDES[-1]],
        "swisseph_version": swe.version,
        "theorem_mismatches_total": total_mismatch,
        "theorem_samples_total": int(round(360.0 / STEP_DEG)) * len(LATITUDES),
        "forward_direction_violations_other_systems": forward_violations,
        "exact_check": exact_check,
        "southern_check": southern_check,
        "ayanamsa_epoch_check": {
            "date": "%04d-%02d-%02d" % AYANAMSA_EPOCH_CHECK,
            "ayanamsa_lahiri_deg": round(ayanamsa_epoch, 6),
            "latitudes": ayanamsa_sensitivity,
        },
        "obliquity_sensitivity": sensitivity,
        "latitudes": rows,
        "other_systems": other_systems,
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # Columns (documented on the page): rising_share_pct is the share of ALL
        # charts at the latitude with that rising sign (100 for "all");
        # mc_in_whole_sign_10th_pct and mc_house_<n>_pct are shares of the charts
        # in that row (all charts, or charts with that rising sign).
        w.writerow(["latitude_deg", "zodiac", "rising_sign", "rising_share_pct",
                    "mc_in_whole_sign_10th_pct", "porphyry_no_interception_pct"]
                   + [f"mc_house_{h}_pct" for h in range(1, 13)])

        def houses(shares: dict[str, float]) -> list[float]:
            return [shares.get(str(h), 0.0) for h in range(1, 13)]

        for row in rows:
            w.writerow([row["latitude"], "tropical", "all", 100.0,
                        row["tropical_share"], row["porphyry_no_interception_share"]]
                       + houses(row["mc_house_shares"]))
            w.writerow([row["latitude"], "sidereal_lahiri", "all", 100.0,
                        row["sidereal_lahiri_share"], ""] + houses(row["sidereal_mc_house_shares"]))
            for s in row["by_rising_sign"]:
                w.writerow([row["latitude"], "tropical", s["sign"], s["rising_share"],
                            s["mc_in_10th_share"], ""] + houses(s["mc_house_shares"]))
                w.writerow([row["latitude"], "sidereal_lahiri", s["sign"],
                            s["sidereal_rising_share"], s["sidereal_mc_in_10th_share"], ""]
                           + houses(s["sidereal_mc_house_shares"]))

    if SCRIPT_COPY is not None:
        SCRIPT_COPY.write_bytes(Path(__file__).read_bytes())

    print(f"theorem mismatches: {total_mismatch} of {payload['theorem_samples_total']}; "
          f"forward-direction violations in other systems: {forward_violations}", file=sys.stderr)
    print(f"wrote {JSON_OUT} and {CSV_OUT}", file=sys.stderr)
    return 0 if total_mismatch == 0 and forward_violations == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
