#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parse raw Cricsheet match files into full structured scorecards.

Pure data layer for the per-match scorecard pages (/matches/<id>/). No HTML
rendering here — generate.py imports parse_match()/iter_matches() and does the
page building so it can reuse the shared chrome + player/team linking helpers.

Each match becomes a dict of compact JSON-friendly values: match meta (teams,
date, venue, toss, result) plus one entry per innings carrying the full batting
and bowling tables, the fall of wickets and the extras breakdown.
"""
import json
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# directory -> format key (matches templates.FMT keys)
DIRS = {
    "tests_json": "Test",
    "odis_json":  "ODI",
    "t20s_json":  "T20I",
    "ipl_json":   "IPL",
}

# dismissals credited to the bowler
WICKET_TO_BOWLER = {"bowled", "caught", "lbw", "stumped",
                    "caught and bowled", "hit wicket"}

# Hindi names for the dismissal "kind" field
KIND_HI = {
    "bowled": "बोल्ड", "lbw": "एलबीडब्ल्यू", "caught": "कैच",
    "stumped": "स्टंप", "run out": "रन आउट", "hit wicket": "हिट विकेट",
    "caught and bowled": "कैच व बोल्ड", "retired hurt": "रिटायर्ड हर्ट",
    "retired out": "रिटायर्ड आउट", "retired not out": "रिटायर्ड नाबाद",
    "obstructing the field": "क्षेत्ररक्षण में बाधा",
    "handled the ball": "गेंद को हाथ लगाया",
    "hit the ball twice": "गेंद को दो बार मारा",
    "timed out": "टाइम्ड आउट",
}


def _fielders(w):
    return [f.get("name", "") for f in w.get("fielders", []) if f.get("name")]


def _dismissal_hi(w):
    """Human Hindi dismissal string from a wicket dict (player names in Latin)."""
    if not w:
        return "नाबाद"
    kind = w.get("kind", "")
    bowler = w.get("bowler", "")
    fld = ", ".join(_fielders(w))
    if kind == "bowled":
        return f"बोल्ड {bowler}".strip()
    if kind == "lbw":
        return f"एलबीडब्ल्यू बो. {bowler}".strip()
    if kind == "caught and bowled":
        return f"कै. व बो. {bowler}".strip()
    if kind == "caught":
        return f"कै. {fld} बो. {bowler}".strip() if fld else f"कैच बो. {bowler}".strip()
    if kind == "stumped":
        return f"स्टं. {fld} बो. {bowler}".strip() if fld else f"स्टंप बो. {bowler}".strip()
    if kind == "run out":
        return f"रन आउट ({fld})" if fld else "रन आउट"
    if kind == "hit wicket":
        return f"हिट विकेट बो. {bowler}".strip()
    return KIND_HI.get(kind, kind or "आउट")


def margin_hi(outcome):
    """(winner_or_None, Hindi result phrase) for the outcome block."""
    if not outcome:
        return None, "कोई परिणाम नहीं"
    suf = " (डी/एल)" if outcome.get("method") == "D/L" else ""
    winner = outcome.get("winner")
    if not winner:
        res = (outcome.get("result") or "").lower()
        if res == "tie":
            elim = outcome.get("eliminator")
            if elim:
                return elim, "सुपर ओवर में विजयी"
            return None, "मुक़ाबला टाई"
        if res == "draw":
            return None, "मैच ड्रॉ"
        return None, "कोई परिणाम नहीं"
    by = outcome.get("by", {})
    if "innings" in by:
        runs = by.get("runs")
        return winner, (f"एक पारी और {runs} रन से विजयी{suf}" if runs
                        else f"एक पारी से विजयी{suf}")
    if "runs" in by:
        return winner, f"{by['runs']} रन से विजयी{suf}"
    if "wickets" in by:
        return winner, f"{by['wickets']} विकेट से विजयी{suf}"
    return winner, f"विजयी{suf}"


def _parse_innings(inn, bpo):
    """Return one structured innings dict from a raw innings object."""
    team = inn.get("team", "")
    bat = {}      # name -> [runs, balls, 4s, 6s]
    order = []
    how = {}      # name -> dismissal dict (None => not out)
    bowl = {}     # name -> [legal_balls, runs_charged, wkts, maidens]
    border = []
    fow = []
    extras = {"byes": 0, "legbyes": 0, "wides": 0, "noballs": 0, "penalty": 0}
    total = wkts = legal = 0

    def reg_bat(name):
        if name is not None and name not in bat:
            bat[name] = [0, 0, 0, 0]
            how[name] = None
            order.append(name)

    for ov in inn.get("overs", []):
        over_bowler = None
        over_charged = 0
        over_balls = 0
        for de in ov.get("deliveries", []):
            ex = de.get("extras", {})
            wide = "wides" in ex
            nb = "noballs" in ex
            for k in extras:
                if k in ex:
                    extras[k] += ex[k]
            rb = de.get("runs", {})
            total += rb.get("total", 0)
            # batting
            bt = de.get("batter")
            reg_bat(bt)
            reg_bat(de.get("non_striker"))
            bat[bt][0] += rb.get("batter", 0)
            if not wide:
                bat[bt][1] += 1
            if rb.get("batter") == 4:
                bat[bt][2] += 1
            elif rb.get("batter") == 6:
                bat[bt][3] += 1
            # bowling
            bw = de.get("bowler")
            if bw not in bowl:
                bowl[bw] = [0, 0, 0, 0]
                border.append(bw)
            charged = rb.get("batter", 0) + ex.get("wides", 0) + ex.get("noballs", 0)
            bowl[bw][1] += charged
            over_bowler = bw
            over_charged += charged
            if not (wide or nb):
                bowl[bw][0] += 1
                legal += 1
                over_balls += 1
            # wickets
            for w in de.get("wickets", []):
                wkts += 1
                po = w.get("player_out")
                reg_bat(po)
                w = {**w, "bowler": w.get("bowler", bw)}
                how[po] = w
                if w.get("kind") in WICKET_TO_BOWLER:
                    bowl[bw][2] += 1
                fow.append({
                    "n": wkts,
                    "score": total,
                    "player": po,
                    "over": f"{legal // bpo}.{legal % bpo}",
                })
        # maiden: full-ish over with nothing charged to the bowler
        if over_bowler is not None and over_charged == 0 and over_balls >= bpo:
            bowl[over_bowler][3] += 1

    batsmen = []
    for n in order:
        r, b, f4, f6 = bat[n]
        w = how[n]
        out = w is not None and w.get("kind") not in (
            "retired hurt", "retired not out")
        batsmen.append({
            "name": n, "r": r, "b": b, "4s": f4, "6s": f6,
            "sr": round(r / b * 100, 1) if b else 0.0,
            "out": out, "how": _dismissal_hi(w),
        })
    bowlers = []
    for n in border:
        lb, rc, wk, md = bowl[n]
        bowlers.append({
            "name": n,
            "overs": f"{lb // bpo}.{lb % bpo}",
            "balls": lb, "m": md, "r": rc, "w": wk,
            "econ": round(rc / (lb / bpo), 2) if lb else 0.0,
        })

    batted = set(order)
    dnb = [p for p in inn.get("__squad__", []) if p not in batted]

    return {
        "team": team,
        "super_over": bool(inn.get("super_over")),
        "runs": total, "wkts": wkts,
        "overs": f"{legal // bpo}.{legal % bpo}", "legal_balls": legal,
        "extras": extras,
        "extras_total": sum(extras.values()),
        "batsmen": batsmen, "bowlers": bowlers, "fow": fow,
        "did_not_bat": dnb,
    }


def parse_match(path):
    """Parse one raw file into a structured scorecard dict (or None to skip)."""
    try:
        d = json.load(open(path))
    except Exception:
        return None
    info = d.get("info", {})
    if info.get("gender") != "male":
        return None
    dates = info.get("dates") or []
    if not dates:
        return None
    date0 = str(dates[0])
    try:
        year = int(date0.split("-")[0])
    except (ValueError, IndexError):
        return None
    teams = info.get("teams", [])
    if len(teams) != 2:
        return None

    bpo = info.get("balls_per_over", 6) or 6
    ev = info.get("event") or {}
    if not isinstance(ev, dict):
        ev = {"name": str(ev)}
    toss = info.get("toss", {}) or {}
    winner, result = margin_hi(info.get("outcome", {}))

    squads = info.get("players", {}) or {}
    innings = []
    seen_team_count = {}
    for inn in d.get("innings", []):
        inn["__squad__"] = squads.get(inn.get("team", ""), [])
        parsed = _parse_innings(inn, bpo)
        t = parsed["team"]
        seen_team_count[t] = seen_team_count.get(t, 0) + 1
        parsed["inn_no"] = seen_team_count[t]
        innings.append(parsed)

    return {
        "id": Path(path).stem,
        "fmt": DIRS_OF.get(Path(path).parent.name, ""),
        "date": date0,
        "year": year,
        "season": str(info.get("season", "")),
        "event": ev.get("name", "") or "",
        "stage": str(ev.get("stage", "") or ""),
        "match_number": ev.get("match_number", ""),
        "teams": teams,
        "venue": info.get("venue", "") or "",
        "city": info.get("city", "") or "",
        "toss_winner": toss.get("winner", ""),
        "toss_decision": toss.get("decision", ""),
        "outcome": info.get("outcome", {}) or {},
        "winner": winner,
        "result": result,
        "pom": info.get("player_of_match", []) or [],
        "registry": (info.get("registry", {}) or {}).get("people", {}),
        "innings": innings,
        # whether any team batted twice (Test) -> show innings numbers
        "multi_innings": any(v > 1 for v in seen_team_count.values()),
    }


# directory name -> format key, used inside parse_match (path-based)
DIRS_OF = {sub: fkey for sub, fkey in DIRS.items()}


def iter_matches():
    """Yield parsed scorecard dicts for every men's match, format by format."""
    for sub in DIRS:
        for fn in sorted(glob.glob(str(RAW / sub / "*.json"))):
            m = parse_match(fn)
            if m:
                yield m


if __name__ == "__main__":
    import time
    import sys
    t0 = time.time()
    n = 0
    by_fmt = {}
    for m in iter_matches():
        n += 1
        by_fmt[m["fmt"]] = by_fmt.get(m["fmt"], 0) + 1
    print(f"parsed {n} men's matches in {time.time()-t0:.1f}s", file=sys.stderr)
    print(by_fmt, file=sys.stderr)
