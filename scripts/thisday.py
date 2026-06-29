#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Scan raw Cricsheet match data and aggregate notable events by calendar day.

Pure data layer for the "आज के दिन क्रिकेट में" (This Day in Cricket) pages.
No HTML rendering here — generate.py imports scan_matches/aggregate_by_day and
does the page building so it can reuse the shared chrome + linking helpers.
"""
import json, glob
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# directory -> format key
DIRS = {
    "tests_json": "Test",
    "odis_json":  "ODI",
    "t20s_json":  "T20I",
    "ipl_json":   "IPL",
}

DISMISSAL_TO_BOWLER = {"bowled", "caught", "lbw", "stumped",
                       "caught and bowled", "hit wicket"}


def _innings_perf(d):
    """Return (batting, bowling) standout lists for one match.

    batting: list of (player, runs, balls, team)  for innings >= 50 runs
    bowling: list of (player, wkts, runs, balls, team) for hauls >= 4 wkts
    """
    batting, bowling = [], []
    for inn in d.get("innings", []):
        team = inn.get("team", "")
        bat = {}      # batter -> [runs, balls]
        bowl = {}     # bowler -> [wkts, runs, legal_balls]
        order = []
        for ov in inn.get("overs", []):
            for de in ov.get("deliveries", []):
                ex = de.get("extras", {})
                wide = "wides" in ex
                nb = "noballs" in ex
                bye = ex.get("byes", 0) + ex.get("legbyes", 0)
                rb = de.get("runs", {})
                bt = de.get("batter")
                if bt not in bat:
                    bat[bt] = [0, 0]; order.append(bt)
                bat[bt][0] += rb.get("batter", 0)
                if not wide:
                    bat[bt][1] += 1
                bw = de.get("bowler")
                bowl.setdefault(bw, [0, 0, 0])
                if not (wide or nb):
                    bowl[bw][2] += 1
                bowl[bw][1] += rb.get("total", 0) - bye - ex.get("penalty", 0)
                for w in de.get("wickets", []):
                    if w.get("kind") in DISMISSAL_TO_BOWLER:
                        bowl[bw][0] += 1
        for b in order:
            runs, balls = bat[b]
            if runs >= 50:
                batting.append((b, runs, balls, team))
        for b, (wk, runs, balls) in bowl.items():
            if wk >= 4:
                bowling.append((b, wk, runs, balls, team))
    return batting, bowling


def _margin(outcome):
    """Hindi result margin string + winner (or None for draw/tie/no result)."""
    if not outcome:
        return None, ""
    winner = outcome.get("winner")
    if not winner:
        res = (outcome.get("result") or "").lower()
        if res == "tie":
            return None, "मुक़ाबला टाई"
        if res == "draw":
            return None, "मैच ड्रॉ"
        return None, "कोई परिणाम नहीं"
    by = outcome.get("by", {})
    if "innings" in by:
        runs = by.get("runs")
        return winner, f"एक पारी और {runs} रन से" if runs else "एक पारी से"
    if "runs" in by:
        return winner, f"{by['runs']} रन से"
    if "wickets" in by:
        return winner, f"{by['wickets']} विकेट से"
    return winner, ""


def scan_matches():
    """Scan every raw match file. Returns a list of compact match dicts."""
    out = []
    for sub, fkey in DIRS.items():
        for fn in glob.glob(str(RAW / sub / "*.json")):
            try:
                d = json.load(open(fn))
            except Exception:
                continue
            info = d.get("info", {})
            if info.get("gender") != "male":
                continue
            dates = info.get("dates") or []
            if not dates:
                continue
            date0 = str(dates[0])
            parts = date0.split("-")
            if len(parts) != 3:
                continue
            try:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            except ValueError:
                continue
            ev = info.get("event") or {}
            if not isinstance(ev, dict):
                ev = {"name": str(ev)}
            winner, margin = _margin(info.get("outcome", {}))
            batting, bowling = _innings_perf(d)
            out.append({
                "id": Path(fn).stem,
                "fmt": fkey,
                "year": year, "month": month, "day": day,
                "teams": info.get("teams", []),
                "city": info.get("city", ""),
                "venue": info.get("venue", ""),
                "event": ev.get("name", ""),
                "stage": str(ev.get("stage", "")),
                "season": str(info.get("season", "")),
                "winner": winner,
                "margin": margin,
                "pom": info.get("player_of_match", []) or [],
                "batting": batting,
                "bowling": bowling,
            })
    return out


def aggregate_by_day(matches):
    """Group matches into (month, day) buckets (1..12, 1..31; plus 2/29)."""
    buckets = defaultdict(list)
    for m in matches:
        buckets[(m["month"], m["day"])].append(m)
    return buckets


if __name__ == "__main__":
    import time, sys
    t0 = time.time()
    ms = scan_matches()
    buckets = aggregate_by_day(ms)
    print(f"scanned {len(ms)} male matches in {time.time()-t0:.1f}s", file=sys.stderr)
    print(f"{len(buckets)} distinct days covered", file=sys.stderr)
    # cache for design iteration
    cache = ROOT / "data" / "processed" / "thisday_cache.json"
    cache.write_text(json.dumps(ms, ensure_ascii=False), encoding="utf-8")
    print(f"cached -> {cache}", file=sys.stderr)
