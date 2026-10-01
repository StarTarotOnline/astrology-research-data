#!/usr/bin/env python3
"""Every retrograde period of Mercury–Pluto from 1900 to 2100, and how often each planet is retrograde.

Source of the numbers on https://startarot.online/research/retrograde-planets-1900-2100.
Needs Python 3 and pyswisseph (``pip install pyswisseph``). Run from the repo root:

    python3 scripts/research/retrograde_periods.py

Writes (GENERATED — regenerate, do not hand-edit):
    frontend/src/lib/research/retrograde-periods.json    data the page renders
    frontend/static/research/retrograde-periods.csv      every retrograde period, one row each
    frontend/static/research/retrograde_periods.py       a copy of this script, served next
                                                         to the page (the repository is private)

A copy downloaded from the page runs anywhere and writes retrograde-periods.json and
retrograde-periods.csv next to itself. The independent JPL check (``jpl_check``) runs
only when Skyfield (``pip install skyfield``) and a JPL ephemeris file covering
1900–2100 (de440s.bsp or de440.bsp) are available; otherwise it is recorded as skipped.

Method
------
A planet is retrograde while its apparent geocentric ecliptic longitude decreases.
For each of Mercury, Venus, Mars, Jupiter, Saturn, Uranus, Neptune and Pluto we
take the apparent longitude (true ecliptic and equinox of date) from Swiss
Ephemeris with the built-in Moshier ephemeris (``FLG_MOSEPH``: no data files, so
the script runs anywhere). For Jupiter to Pluto that is the position of the
centre of mass of the planet and its moons, the Swiss Ephemeris default. The speed
is the change of that longitude over ±30 minutes, not the speed returned with
``FLG_SPEED``: for Pluto the latter differs from the derivative of the same
model's longitude enough to move stations by up to ~24 minutes. The speed is
sampled once a day from 1900-01-01 to 2101-01-01 00:00 UT and every change from
positive to negative or back is located by bisection to one second; station times
are rounded to the minute. A change from
direct to retrograde motion is a station retrograde (SR), the reverse a station
direct (SD); a retrograde period runs from an SR to the next SD. Times are UT.

Periods already under way on 1900-01-01 or still running on 2101-01-01 are cut at
the edge of the range and flagged; they count towards the share of time spent
retrograde but not towards period counts, durations or arcs.

"How many planets are retrograde at once" is measured exactly, not by sampling:
all stations of all eight planets are merged into one timeline and the time
between consecutive stations is added to the bucket of the current count. The
Sun and the Moon are never retrograde and are not counted; neither are the lunar
nodes, Chiron or asteroids.

Independent check
-----------------
``jpl_check`` repeats the station search with a different code and a different
ephemeris: Skyfield with the JPL DE440 file, apparent positions in the true
ecliptic and equinox of date, the speed taken as a symmetric difference over
±30 minutes. Every Swiss Ephemeris station is paired with the JPL station of
the same kind nearest in time, and the JSON records the number of stations
found by each and the largest time difference per planet.

Solar-conjunction flicker: when a planet passes almost exactly behind the Sun,
the correction for the Sun's bending of light can make the computed speed flip
sign for up to about an hour (in Skyfield with DE440: about a dozen conjunctions
of Jupiter, Uranus, Neptune and Pluto in 201 years). In both searches a pair of
opposite sign changes less than a day apart is dropped as an artefact and counted
(``swiss_flicker_pairs``, ``solar_conjunction_flicker_pairs``); a daily grid only
catches some of them.
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
    JSON_OUT = REPO_ROOT / "frontend" / "src" / "lib" / "research" / "retrograde-periods.json"
    CSV_OUT = REPO_ROOT / "frontend" / "static" / "research" / "retrograde-periods.csv"
    SCRIPT_COPY = REPO_ROOT / "frontend" / "static" / "research" / "retrograde_periods.py"
else:
    # A copy downloaded from the page: the repository paths do not exist here.
    JSON_OUT = HERE / "retrograde-periods.json"
    CSV_OUT = HERE / "retrograde-periods.csv"
    SCRIPT_COPY = None

PLANETS = [
    ("Mercury", swe.MERCURY, "mercury barycenter"),
    ("Venus", swe.VENUS, "venus barycenter"),
    ("Mars", swe.MARS, "mars barycenter"),
    ("Jupiter", swe.JUPITER, "jupiter barycenter"),
    ("Saturn", swe.SATURN, "saturn barycenter"),
    ("Uranus", swe.URANUS, "uranus barycenter"),
    ("Neptune", swe.NEPTUNE, "neptune barycenter"),
    ("Pluto", swe.PLUTO, "pluto barycenter"),
]
SIGNS = [
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
]
START = (1900, 1, 1)
END = (2101, 1, 1)  # exclusive: the range covers the whole of 2100
UPCOMING_FROM = (2026, 1, 1)
UPCOMING_TO = (2031, 1, 1)  # periods under way on 2026-01-01 or starting by the end of 2030
FLAGS = swe.FLG_MOSEPH
TOLERANCE_DAYS = 1.0 / 86400.0  # one second
SPEED_HALF_STEP_DAYS = 1.0 / 48.0  # ±30 minutes for the speed, in both searches
FLICKER_MAX_DAYS = 1.0  # opposite sign changes closer than this are an artefact, not stations
JPL_FILES = ("de440s.bsp", "de440.bsp")
JPL_HALF_STEP_DAYS = 1.0 / 48.0  # ±30 minutes for the numerical speed


def jd_of(ymd: tuple[int, int, int]) -> float:
    return swe.julday(ymd[0], ymd[1], ymd[2], 0.0)


def iso(jd: float) -> str:
    y, m, d, h = swe.revjul(jd)
    seconds = int(round(h * 60.0)) * 60  # rounded to the nearest minute
    if seconds >= 86400:  # rounding pushed the time to the next day
        y, m, d, _ = swe.revjul(math.floor(jd - 0.5) + 1.5)
        seconds = 0
    hh, rem = divmod(seconds, 3600)
    mm, _ss = divmod(rem, 60)
    return "%04d-%02d-%02dT%02d:%02dZ" % (y, m, d, hh, mm)


def date_of(jd: float) -> str:
    return iso(jd)[:10]


def year_of(jd: float) -> int:
    return swe.revjul(jd)[0]


def lon_of(jd: float, body: int) -> float:
    return swe.calc_ut(jd, body, FLAGS)[0][0]


def lon_speed(jd: float, body: int) -> tuple[float, float]:
    """Longitude and its speed (deg/day) as the symmetric difference over ±30 minutes.

    Not the speed Swiss Ephemeris returns with FLG_SPEED: for Pluto that value differs
    from the derivative of the same model's longitude by up to 0.025"/day, which moves
    Pluto's stations by up to ~24 minutes; the difference of longitudes does not."""
    a = lon_of(jd + SPEED_HALF_STEP_DAYS, body)
    b = lon_of(jd - SPEED_HALF_STEP_DAYS, body)
    return lon_of(jd, body), ((a - b + 180.0) % 360.0 - 180.0) / (2.0 * SPEED_HALF_STEP_DAYS)


def sign_of(lon: float) -> str:
    return SIGNS[int(math.floor((lon % 360.0) / 30.0)) % 12]


def find_stations(body: int, jd0: float, jd1: float) -> tuple[list[dict], int]:
    """Every sign change of the longitude speed in [jd0, jd1), refined to one second,
    and the number of solar-conjunction flicker pairs dropped (see ``drop_flicker``)."""
    stations = []
    t_prev = jd0
    _, v_prev = lon_speed(t_prev, body)
    t = jd0 + 1.0
    while t <= jd1:
        _, v = lon_speed(t, body)
        if (v_prev > 0) != (v > 0):
            lo, hi, v_lo = t_prev, t, v_prev
            while hi - lo > TOLERANCE_DAYS:
                mid = 0.5 * (lo + hi)
                _, v_mid = lon_speed(mid, body)
                if (v_mid > 0) == (v_lo > 0):
                    lo, v_lo = mid, v_mid
                else:
                    hi = mid
            ts = 0.5 * (lo + hi)
            lon, _ = lon_speed(ts, body)
            stations.append({
                "kind": "SR" if v_prev > 0 else "SD",
                "jd": ts,
                "lon": lon,
            })
        t_prev, v_prev = t, v
        t += 1.0
    return drop_flicker(stations)


def drop_flicker(stations: list, key=lambda s: (s["kind"], s["jd"])) -> tuple[list, int]:
    """Remove pairs of opposite sign changes less than a day apart.

    A planet passing almost exactly behind the Sun: the correction for the Sun's
    bending of light, applied to a position hidden by the solar disk, can make the
    speed flip sign for up to about an hour. That is an artefact of the model, not a
    station (a real retrograde lasts weeks to months)."""
    kept = []
    pairs = 0
    k = 0
    while k < len(stations):
        if k + 1 < len(stations):
            (kind_a, t_a), (kind_b, t_b) = key(stations[k]), key(stations[k + 1])
            if kind_a != kind_b and t_b - t_a < FLICKER_MAX_DAYS:
                pairs += 1
                k += 2
                continue
        kept.append(stations[k])
        k += 1
    return kept, pairs


def build_periods(name: str, body: int, stations: list[dict], jd0: float, jd1: float) -> list[dict]:
    """Retrograde periods from the station list; edge periods are cut and flagged."""
    periods = []
    retro_at_start = lon_speed(jd0, body)[1] < 0
    open_sr = None
    if retro_at_start:
        open_sr = {"kind": "SR", "jd": jd0, "lon": lon_speed(jd0, body)[0], "cut": True}
    for st in stations:
        if st["kind"] == "SR":
            open_sr = dict(st, cut=False)
        else:
            if open_sr is None:
                continue
            periods.append(make_period(name, open_sr, st, cut_end=False))
            open_sr = None
    if open_sr is not None:
        end = {"kind": "SD", "jd": jd1, "lon": lon_speed(jd1, body)[0]}
        periods.append(make_period(name, open_sr, end, cut_end=True))
    return periods


def make_period(name: str, sr: dict, sd: dict, cut_end: bool) -> dict:
    arc = (sr["lon"] - sd["lon"]) % 360.0
    return {
        "planet": name,
        "sr_jd": sr["jd"],
        "sd_jd": sd["jd"],
        "sr_utc": iso(sr["jd"]),
        "sd_utc": iso(sd["jd"]),
        "sr_lon": round(sr["lon"], 4),
        "sd_lon": round(sd["lon"], 4),
        "sr_sign": sign_of(sr["lon"]),
        "sd_sign": sign_of(sd["lon"]),
        "duration_days": round(sd["jd"] - sr["jd"], 3),
        "arc_deg": round(arc, 3),
        "cut_start": bool(sr.get("cut")),
        "cut_end": cut_end,
    }


def planet_summary(name: str, periods: list[dict], span_days: float, stations: int) -> dict:
    full = [p for p in periods if not p["cut_start"] and not p["cut_end"]]
    retro_days = sum(p["sd_jd"] - p["sr_jd"] for p in periods)
    durations = [p["sd_jd"] - p["sr_jd"] for p in full]
    arcs = [p["arc_deg"] for p in full]
    longest = max(full, key=lambda p: p["sd_jd"] - p["sr_jd"])
    shortest = min(full, key=lambda p: p["sd_jd"] - p["sr_jd"])
    return {
        "planet": name,
        "stations": stations,
        "periods": len(full),
        "periods_per_year": round(len(full) / (span_days / 365.2425), 3),
        "share_pct": round(100.0 * retro_days / span_days, 3),
        "duration_days": {
            "mean": round(sum(durations) / len(durations), 1),
            "min": round(min(durations), 1),
            "max": round(max(durations), 1),
        },
        "arc_deg": {
            "mean": round(sum(arcs) / len(arcs), 2),
            "min": round(min(arcs), 2),
            "max": round(max(arcs), 2),
        },
        "longest": {"sr_utc": longest["sr_utc"], "sd_utc": longest["sd_utc"],
                    "days": round(longest["sd_jd"] - longest["sr_jd"], 1)},
        "shortest": {"sr_utc": shortest["sr_utc"], "sd_utc": shortest["sd_utc"],
                     "days": round(shortest["sd_jd"] - shortest["sr_jd"], 1)},
    }


def overlap_timeline(all_periods: list[dict], jd0: float, jd1: float) -> dict:
    """Exact time with k planets retrograde, the most at once, and stretches with none."""
    events = []
    for p in all_periods:
        events.append((p["sr_jd"], +1, p["planet"]))
        events.append((p["sd_jd"], -1, p["planet"]))
    events.sort(key=lambda e: (e[0], e[1]))
    count = 0
    active: set[str] = set()
    t_prev = jd0
    time_by_count = [0.0] * 9
    best = {"count": 0, "first_jd": None, "planets": []}
    zero_start = None
    zero_stretches = []
    for t, delta, planet in events:
        t = min(max(t, jd0), jd1)
        time_by_count[count] += t - t_prev
        if count == 0 and zero_start is not None and t > zero_start:
            zero_stretches.append((zero_start, t))
            zero_start = None
        if delta > 0:
            active.add(planet)
        else:
            active.discard(planet)
        count += delta
        if count > best["count"]:
            best = {"count": count, "first_jd": t, "planets": sorted(active, key=planet_order)}
        if count == 0:
            zero_start = t
        t_prev = t
    time_by_count[count] += jd1 - t_prev
    if count == 0 and zero_start is not None and jd1 > zero_start:
        zero_stretches.append((zero_start, jd1))
    span = jd1 - jd0
    longest_zero = max(zero_stretches, key=lambda z: z[1] - z[0])
    # every moment the maximum was reached, as separate episodes
    episodes = max_count_episodes(events, jd0, jd1, best["count"])
    return {
        "share_by_count_pct": [round(100.0 * x / span, 3) for x in time_by_count],
        "share_at_least_one_pct": round(100.0 * (span - time_by_count[0]) / span, 2),
        "mean_count": round(sum(k * x for k, x in enumerate(time_by_count)) / span, 3),
        "max_count": best["count"],
        "max_count_episodes": episodes,
        "zero_stretches": len(zero_stretches),
        "longest_zero": {
            "from_utc": iso(longest_zero[0]), "to_utc": iso(longest_zero[1]),
            "days": round(longest_zero[1] - longest_zero[0], 1),
        },
        "zero_stretches_over_60_days": sum(1 for a, b in zero_stretches if b - a > 60.0),
    }


def planet_order(name: str) -> int:
    return [p[0] for p in PLANETS].index(name)


def max_count_episodes(events, jd0: float, jd1: float, target: int) -> list[dict]:
    count = 0
    active: set[str] = set()
    out = []
    start = None
    for t, delta, planet in events:
        t = min(max(t, jd0), jd1)
        if delta > 0:
            active.add(planet)
        else:
            active.discard(planet)
        prev = count
        count += delta
        if prev < target <= count:
            start = (t, sorted(active, key=planet_order))
        elif prev >= target > count and start is not None:
            out.append({"from_utc": iso(start[0]), "to_utc": iso(t),
                        "days": round(t - start[0], 1), "planets": start[1]})
            start = None
    return out


def mercury_years(periods: list[dict]) -> dict:
    """Mercury retrograde periods counted by the calendar year of the station retrograde."""
    counts: dict[int, int] = {}
    for p in periods:
        if p["planet"] != "Mercury" or p["cut_start"]:
            continue
        y = year_of(p["sr_jd"])
        if START[0] <= y <= END[0] - 1:
            counts[y] = counts.get(y, 0) + 1
    years = list(range(START[0], END[0]))
    dist: dict[str, int] = {}
    for y in years:
        k = counts.get(y, 0)
        dist[str(k)] = dist.get(str(k), 0) + 1
    four = [y for y in years if counts.get(y, 0) == 4]
    return {"distribution": dist, "years_with_four": four,
            "next_year_with_four": next((y for y in four if y >= UPCOMING_FROM[0]), None)}


def mercury_by_sign(periods: list[dict]) -> list[int]:
    """How many Mercury retrograde periods begin (station retrograde) in each sign."""
    counts = [0] * 12
    for p in periods:
        if p["planet"] == "Mercury" and not p["cut_start"]:
            counts[SIGNS.index(p["sr_sign"])] += 1
    return counts


def jpl_check(swiss: dict[str, list[dict]], jd0: float, jd1: float) -> dict:
    """Repeat the station search with Skyfield + JPL DE440 and compare station times."""
    try:
        from skyfield.api import Loader
        from skyfield.framelib import ecliptic_frame
    except ImportError:
        return {"status": "skipped", "reason": "skyfield is not installed"}
    candidates = [HERE / f for f in JPL_FILES] + [Path.home() / ".libephemeris" / f for f in JPL_FILES]
    path = next((c for c in candidates if c.is_file()), None)
    if path is None:
        return {"status": "skipped", "reason": "no de440s.bsp / de440.bsp next to the script"}
    import numpy as np

    load = Loader(str(path.parent), verbose=False)
    eph = load(path.name)
    ts = load.timescale(builtin=True)
    earth = eph["earth"]

    def jd_to_t(jd):
        return ts.ut1_jd(jd)

    def lon(target, jd):
        t = jd_to_t(jd)
        lat_, lon_, _ = earth.at(t).observe(target).apparent().frame_latlon(ecliptic_frame)
        return lon_.degrees

    def speed(target, jd):
        a = np.unwrap(np.radians(np.vstack([lon(target, jd - JPL_HALF_STEP_DAYS),
                                            lon(target, jd + JPL_HALF_STEP_DAYS)])), axis=0)
        return np.degrees(a[1] - a[0]) / (2 * JPL_HALF_STEP_DAYS)

    out = {"status": "ok", "ephemeris": path.name, "speed_step_minutes": 30, "planets": []}
    overall = 0.0
    for name, _body, jpl_name in PLANETS:
        target = eph[jpl_name]
        grid = np.arange(jd0, jd1 + 0.5, 1.0)
        v = np.concatenate([speed(target, grid[i:i + 20000]) for i in range(0, len(grid), 20000)])
        idx = np.nonzero((v[:-1] > 0) != (v[1:] > 0))[0]
        found = []
        for i in idx:
            lo, hi, v_lo = grid[i], grid[i + 1], v[i]
            while hi - lo > TOLERANCE_DAYS:
                mid = 0.5 * (lo + hi)
                v_mid = float(speed(target, np.array([mid]))[0])
                if (v_mid > 0) == (v_lo > 0):
                    lo, v_lo = mid, v_mid
                else:
                    hi = mid
            found.append(("SR" if v[i] > 0 else "SD", 0.5 * (lo + hi)))
        found, flicker = drop_flicker(found, key=lambda s: s)
        ours = [(st["kind"], st["jd"]) for st in swiss[name]]
        diffs = []
        unmatched = 0
        for kind, t in ours:
            same = [tj for kj, tj in found if kj == kind]
            nearest = min(same, key=lambda tj: abs(tj - t)) if same else None
            if nearest is None or abs(nearest - t) > 2.0:
                unmatched += 1
                continue
            diffs.append(abs(nearest - t) * 1440.0)
        worst = max(diffs) if diffs else None
        overall = max(overall, worst or 0.0)
        out["planets"].append({
            "planet": name,
            "stations_swiss": len(ours),
            "stations_jpl": len(found),
            "solar_conjunction_flicker_pairs": flicker,
            "unmatched": unmatched,
            "max_diff_minutes": round(worst, 1) if worst is not None else None,
            "median_diff_minutes": round(sorted(diffs)[len(diffs) // 2], 1) if diffs else None,
        })
        print(f"JPL check {name}: {len(ours)} vs {len(found)} stations, "
              f"max diff {worst:.1f} min", file=sys.stderr)
    out["max_diff_minutes"] = round(overall, 1)
    return out


def main() -> int:
    jd0, jd1 = jd_of(START), jd_of(END)
    span = jd1 - jd0
    stations: dict[str, list[dict]] = {}
    flicker: dict[str, int] = {}
    periods: list[dict] = []
    for name, body, _ in PLANETS:
        st, flicker[name] = find_stations(body, jd0, jd1)
        stations[name] = st
        periods.extend(build_periods(name, body, st, jd0, jd1))
        print(f"{name}: {len(st)} stations", file=sys.stderr)

    summaries = [planet_summary(name, [p for p in periods if p["planet"] == name], span,
                                len(stations[name]))
                 for name, _, _ in PLANETS]
    overlap = overlap_timeline(periods, jd0, jd1)
    up0, up1 = jd_of(UPCOMING_FROM), jd_of(UPCOMING_TO)
    upcoming = [
        {k: p[k] for k in ("planet", "sr_utc", "sd_utc", "sr_sign", "sd_sign",
                           "sr_lon", "sd_lon", "duration_days", "arc_deg")}
        for p in sorted(periods, key=lambda p: p["sr_jd"])
        if p["sd_jd"] >= up0 and p["sr_jd"] < up1 and not p["cut_start"]
    ]
    check = jpl_check(stations, jd0, jd1)

    payload = {
        "generated_by": "scripts/research/retrograde_periods.py",
        "range": {"from": "%04d-%02d-%02d" % START, "to_exclusive": "%04d-%02d-%02d" % END,
                  "days": round(span, 1)},
        "ephemeris": "Swiss Ephemeris, built-in Moshier (FLG_MOSEPH), apparent geocentric longitude",
        "swisseph_version": swe.version,
        "planets": [p[0] for p in PLANETS],
        "signs": SIGNS,
        "summary": summaries,
        "swiss_flicker_pairs": flicker,
        "overlap": overlap,
        "mercury_years": mercury_years(periods),
        "mercury_by_sign": mercury_by_sign(periods),
        "upcoming": {"from": "%04d-%02d-%02d" % UPCOMING_FROM,
                     "to_exclusive": "%04d-%02d-%02d" % UPCOMING_TO, "periods": upcoming},
        "jpl_check": check,
    }
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")

    CSV_OUT.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUT.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # One row per retrograde period. Times UT; longitudes apparent geocentric,
        # tropical, degrees 0–360; arc_deg = how far the planet moves back.
        w.writerow(["planet", "station_retrograde_utc", "station_retrograde_lon_deg",
                    "station_retrograde_sign", "station_direct_utc", "station_direct_lon_deg",
                    "station_direct_sign", "duration_days", "arc_deg",
                    "cut_at_range_start", "cut_at_range_end"])
        for p in sorted(periods, key=lambda p: (planet_order(p["planet"]), p["sr_jd"])):
            w.writerow([p["planet"], p["sr_utc"], p["sr_lon"], p["sr_sign"], p["sd_utc"],
                        p["sd_lon"], p["sd_sign"], p["duration_days"], p["arc_deg"],
                        int(p["cut_start"]), int(p["cut_end"])])

    if SCRIPT_COPY is not None:
        SCRIPT_COPY.write_bytes(Path(__file__).read_bytes())

    for s in summaries:
        print(f"{s['planet']:8s} {s['share_pct']:6.2f}%  {s['periods']:4d} periods  "
              f"mean {s['duration_days']['mean']} d  arc {s['arc_deg']['mean']}°", file=sys.stderr)
    print(f"overlap: {overlap['share_by_count_pct']} max {overlap['max_count']}", file=sys.stderr)
    print(f"jpl check: {check.get('status')} max {check.get('max_diff_minutes')} min", file=sys.stderr)
    print(f"wrote {JSON_OUT} and {CSV_OUT}", file=sys.stderr)
    ok = check.get("status") != "ok" or all(
        p["unmatched"] == 0 and p["stations_jpl"] == p["stations_swiss"] for p in check["planets"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
