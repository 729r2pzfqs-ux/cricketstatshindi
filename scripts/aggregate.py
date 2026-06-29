#!/usr/bin/env python3
"""
Cricsheet aggregation engine for cricketstatshindi.com

Reads ball-by-ball match JSON from data/raw/<format>_json/ and produces
aggregated, presentation-ready stats in data/processed/:

  players_full.json   id -> full career stats (per-format batting + bowling)
  players_index.json  lightweight list for search / listing
  teams.json          per-team win/loss records by format
  ipl.json            IPL season-by-season summaries
  records.json        precomputed leaderboards per format

Players are keyed by Cricsheet's stable people-registry id, so a player's
record is merged across IPL / T20I / ODI / Test automatically.
"""
import json, os, glob, collections
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed"
OUT.mkdir(parents=True, exist_ok=True)

# format folder -> internal format key
SOURCES = {
    "ipl_json":   "IPL",
    "t20s_json":  "T20I",
    "odis_json":  "ODI",
    "tests_json": "Test",
}
FORMATS = ["Test", "ODI", "T20I", "IPL"]

# IPL franchises that were renamed / re-spelled -> canonical name
TEAM_ALIASES = {
    "Royal Challengers Bangalore": "Royal Challengers Bengaluru",
    "Delhi Daredevils": "Delhi Capitals",
    "Kings XI Punjab": "Punjab Kings",
    "Rising Pune Supergiants": "Rising Pune Supergiant",
}


def canon_team(t):
    return TEAM_ALIASES.get(t, t)


# wicket kinds credited to the bowler
BOWLER_WICKETS = {"bowled", "caught", "lbw", "stumped", "caught and bowled", "hit wicket"}
# dismissals that do NOT count against a batting average
NON_DISMISSAL = {"retired hurt", "retired not out", "retired"}


def new_bat():
    return dict(matches=0, innings=0, runs=0, balls=0, outs=0, not_outs=0,
                fours=0, sixes=0, fifties=0, hundreds=0, hs=0, hs_not_out=False)


def new_bowl():
    return dict(matches=0, innings=0, balls=0, runs=0, wickets=0,
                four_w=0, five_w=0, best_w=-1, best_r=0, maidens=0)


class Player:
    __slots__ = ("id", "names", "bat", "bowl", "teams", "formats", "pom")

    def __init__(self, pid):
        self.id = pid
        self.names = collections.Counter()
        self.bat = {f: new_bat() for f in FORMATS}
        self.bowl = {f: new_bowl() for f in FORMATS}
        self.teams = collections.Counter()
        self.formats = set()
        self.pom = 0  # player-of-match awards


players = {}          # id -> Player
name_to_id = {}       # last-seen name -> id (per match registry handles this)
teams = {}            # (team) -> per-format records
ipl_seasons = {}      # season -> aggregation
match_index = []      # lightweight list of notable matches


def get_player(pid, name):
    p = players.get(pid)
    if p is None:
        p = players[pid] = Player(pid)
    if name:
        p.names[name] += 1
    return p


def team_rec(team):
    r = teams.get(team)
    if r is None:
        r = teams[team] = {f: dict(played=0, won=0, lost=0, tied=0, nr=0) for f in FORMATS}
        r["_name"] = team
    return r


def process_match(d, fmt):
    info = d["info"]
    reg = info.get("registry", {}).get("people", {})

    # --- team result accounting -------------------------------------------
    mteams = [canon_team(t) for t in info.get("teams", [])]
    outcome = info.get("outcome", {})
    winner = canon_team(outcome.get("winner")) if outcome.get("winner") else None
    result = outcome.get("result")  # 'tie','no result','draw'
    for t in mteams:
        rec = team_rec(t)[fmt]
        rec["played"] += 1
        if winner == t:
            rec["won"] += 1
        elif winner:
            rec["lost"] += 1
        elif result == "tie":
            rec["tied"] += 1
        else:
            rec["nr"] += 1

    # --- player of match ---------------------------------------------------
    for pom in info.get("player_of_match", []) or []:
        pid = reg.get(pom)
        if pid:
            get_player(pid, pom).pom += 1

    # --- squads: who appears, which team -----------------------------------
    appeared = {}  # pid -> team
    for team, names in info.get("players", {}).items():
        team = canon_team(team)
        for nm in names:
            pid = reg.get(nm)
            if pid:
                p = get_player(pid, nm)
                p.teams[team] += 1
                p.formats.add(fmt)
                appeared[pid] = team

    # per-match per-player innings accumulators
    bat_match = collections.defaultdict(lambda: dict(runs=0, balls=0, out=False,
                                                     fours=0, sixes=0, batted=False))
    bowl_match = collections.defaultdict(lambda: dict(balls=0, runs=0, wickets=0))

    for inn in d.get("innings", []):
        # reset per-innings (T20/ODI = one bat innings each; Test up to 2)
        bat_inn = collections.defaultdict(lambda: dict(runs=0, balls=0, out=False,
                                                       fours=0, sixes=0, batted=False))
        bowl_inn = collections.defaultdict(lambda: dict(balls=0, runs=0, wickets=0))
        for ov in inn.get("overs", []):
            for de in ov.get("deliveries", []):
                extras = de.get("extras", {})
                wide = "wides" in extras
                noball = "noballs" in extras
                bye = extras.get("byes", 0) + extras.get("legbyes", 0)
                penalty = extras.get("penalty", 0)
                rb = de["runs"]

                batter = de.get("batter")
                bowler = de.get("bowler")
                bpid = reg.get(batter)
                wpid = reg.get(bowler)

                # batting
                if bpid:
                    b = bat_inn[bpid]
                    b["batted"] = True
                    b["runs"] += rb.get("batter", 0)
                    if not wide:
                        b["balls"] += 1
                    if rb.get("batter") == 4:
                        b["fours"] += 1
                    elif rb.get("batter") == 6:
                        b["sixes"] += 1
                # non-striker may also need an innings record (handled at dismissal/squad)
                ns = de.get("non_striker")
                nspid = reg.get(ns)
                if nspid:
                    bat_inn[nspid]["batted"] = True

                # bowling: charged runs = total - byes/legbyes - penalty
                if wpid:
                    bw = bowl_inn[wpid]
                    if not (wide or noball):
                        bw["balls"] += 1
                    bw["runs"] += rb.get("total", 0) - bye - penalty

                # wickets
                for w in de.get("wickets", []):
                    po = w.get("player_out")
                    kind = w.get("kind")
                    popid = reg.get(po)
                    if popid and kind not in NON_DISMISSAL:
                        bat_inn[popid]["out"] = True
                        bat_inn[popid]["batted"] = True
                    if wpid and kind in BOWLER_WICKETS:
                        bowl_inn[wpid]["wickets"] += 1

        # fold innings -> career
        for pid, b in bat_inn.items():
            if not b["batted"]:
                continue
            agg = get_player(pid, None).bat[fmt]
            agg["innings"] += 1
            agg["runs"] += b["runs"]
            agg["balls"] += b["balls"]
            agg["fours"] += b["fours"]
            agg["sixes"] += b["sixes"]
            if b["out"]:
                agg["outs"] += 1
            else:
                agg["not_outs"] += 1
            if b["runs"] >= 100:
                agg["hundreds"] += 1
            elif b["runs"] >= 50:
                agg["fifties"] += 1
            if b["runs"] > agg["hs"] or (b["runs"] == agg["hs"] and not b["out"]):
                agg["hs"] = b["runs"]
                agg["hs_not_out"] = not b["out"]
            bat_match[pid]  # ensure played counted later

        for pid, bw in bowl_inn.items():
            if bw["balls"] == 0 and bw["wickets"] == 0:
                continue
            agg = get_player(pid, None).bowl[fmt]
            agg["innings"] += 1
            agg["balls"] += bw["balls"]
            agg["runs"] += bw["runs"]
            agg["wickets"] += bw["wickets"]
            if bw["wickets"] >= 5:
                agg["five_w"] += 1
            elif bw["wickets"] >= 4:
                agg["four_w"] += 1
            # best bowling figures (most wkts, then fewest runs)
            if bw["wickets"] > agg["best_w"] or \
               (bw["wickets"] == agg["best_w"] and bw["runs"] < agg["best_r"]):
                agg["best_w"] = bw["wickets"]
                agg["best_r"] = bw["runs"]
            bowl_match[pid]

    # matches played (distinct, per format) for those who batted/bowled
    for pid in set(bat_match) | set(appeared):
        get_player(pid, None).bat[fmt]["matches"] += 1
    for pid in set(bowl_match):
        get_player(pid, None).bowl[fmt]["matches"] += 1

    # --- IPL season aggregation -------------------------------------------
    if fmt == "IPL":
        season = str(info.get("season", "")).split("/")[0]
        s = ipl_seasons.setdefault(season, dict(
            season=season, matches=0, final_winner=None,
            runs=collections.Counter(), wkts=collections.Counter(),
            names={}))
        s["matches"] += 1
        ev = info.get("event", {})
        if isinstance(ev, dict) and str(ev.get("stage", "")).lower() == "final" and winner:
            s["final_winner"] = winner
        # tally top performers in this match
        for inn in d.get("innings", []):
            for ov in inn.get("overs", []):
                for de in ov.get("deliveries", []):
                    bpid = reg.get(de.get("batter"))
                    if bpid:
                        s["runs"][bpid] += de["runs"].get("batter", 0)
                        s["names"][bpid] = de.get("batter")
                    for w in de.get("wickets", []):
                        if w.get("kind") in BOWLER_WICKETS:
                            wpid = reg.get(de.get("bowler"))
                            if wpid:
                                s["wkts"][wpid] += 1
                                s["names"][wpid] = de.get("bowler")


def main():
    total = 0
    for folder, fmt in SOURCES.items():
        files = glob.glob(str(RAW / folder / "*.json"))
        print(f"Processing {fmt}: {len(files)} files")
        for i, fn in enumerate(files):
            try:
                with open(fn) as fh:
                    d = json.load(fh)
            except Exception as e:
                continue
            if not d.get("innings"):
                continue
            process_match(d, fmt)
            total += 1
            if i and i % 1000 == 0:
                print(f"   ... {i}")
    print(f"Processed {total} matches, {len(players)} players")
    write_outputs()


def primary_name(p):
    return p.names.most_common(1)[0][0] if p.names else p.id


def avg(r, w):
    return round(r / w, 2) if w else None


def player_dict(p):
    name = primary_name(p)
    out = dict(id=p.id, name=name, pom=p.pom,
               teams=[t for t, _ in p.teams.most_common()],
               formats=sorted(p.formats, key=lambda f: FORMATS.index(f)),
               bat={}, bowl={})
    for f in FORMATS:
        b = p.bat[f]
        if b["innings"]:
            out["bat"][f] = dict(
                m=b["matches"], inn=b["innings"], runs=b["runs"], balls=b["balls"],
                hs=b["hs"], hs_no=b["hs_not_out"], no=b["not_outs"],
                avg=avg(b["runs"], b["outs"]),
                sr=round(b["runs"] / b["balls"] * 100, 2) if b["balls"] else None,
                fours=b["fours"], sixes=b["sixes"],
                fifties=b["fifties"], hundreds=b["hundreds"])
        bw = p.bowl[f]
        if bw["innings"]:
            out["bowl"][f] = dict(
                m=bw["matches"], inn=bw["innings"], balls=bw["balls"], runs=bw["runs"],
                wkts=bw["wickets"],
                avg=avg(bw["runs"], bw["wickets"]),
                econ=round(bw["runs"] / (bw["balls"] / 6), 2) if bw["balls"] else None,
                sr=round(bw["balls"] / bw["wickets"], 2) if bw["wickets"] else None,
                bbi=(f"{bw['best_w']}/{bw['best_r']}" if bw["best_w"] >= 0 else None),
                four_w=bw["four_w"], five_w=bw["five_w"])
    # career totals (sum across formats) for ranking/search
    out["total_runs"] = sum(v["runs"] for v in out["bat"].values())
    out["total_wkts"] = sum(v["wkts"] for v in out["bowl"].values())
    out["total_m"] = sum(v["m"] for v in out["bat"].values()) or \
                     sum(v["m"] for v in out["bowl"].values())
    return out


def write_outputs():
    full = {pid: player_dict(p) for pid, p in players.items()}
    # drop noise: players with no batting innings and no bowling innings
    full = {k: v for k, v in full.items() if v["bat"] or v["bowl"]}
    (OUT / "players_full.json").write_text(json.dumps(full, ensure_ascii=False))

    index = [dict(id=v["id"], name=v["name"], teams=v["teams"][:3],
                  formats=v["formats"], runs=v["total_runs"],
                  wkts=v["total_wkts"], m=v["total_m"])
             for v in full.values()]
    index.sort(key=lambda x: (x["runs"] + x["wkts"] * 20), reverse=True)
    (OUT / "players_index.json").write_text(json.dumps(index, ensure_ascii=False))

    # teams: compute win% and totals
    tout = {}
    for name, rec in teams.items():
        agg = dict(name=name, formats={})
        tp = tw = 0
        for f in FORMATS:
            r = rec[f]
            if r["played"]:
                wp = round(r["won"] / r["played"] * 100, 1)
                agg["formats"][f] = dict(played=r["played"], won=r["won"],
                                         lost=r["lost"], tied=r["tied"], nr=r["nr"],
                                         win_pct=wp)
                tp += r["played"]; tw += r["won"]
        agg["total_played"] = tp
        agg["total_won"] = tw
        agg["win_pct"] = round(tw / tp * 100, 1) if tp else 0
        if tp:
            tout[name] = agg
    (OUT / "teams.json").write_text(json.dumps(tout, ensure_ascii=False))

    # IPL seasons
    iout = []
    for season, s in sorted(ipl_seasons.items()):
        if not season:
            continue
        tr = s["runs"].most_common(1)
        tw = s["wkts"].most_common(1)
        iout.append(dict(
            season=season, matches=s["matches"], champion=s["final_winner"],
            top_run=dict(id=tr[0][0], name=s["names"].get(tr[0][0]), runs=tr[0][1]) if tr else None,
            top_wkt=dict(id=tw[0][0], name=s["names"].get(tw[0][0]), wkts=tw[0][1]) if tw else None,
        ))
    (OUT / "ipl.json").write_text(json.dumps(iout, ensure_ascii=False))

    # records leaderboards per format
    records = {}
    for f in FORMATS:
        bats = [v for v in full.values() if f in v["bat"]]
        bowls = [v for v in full.values() if f in v["bowl"]]
        def topn(items, keyfn, n=25, filt=None):
            xs = [x for x in items if (filt is None or filt(x))]
            xs.sort(key=keyfn, reverse=True)
            return xs[:n]
        records[f] = dict(
            most_runs=[dict(id=v["id"], name=v["name"], v=v["bat"][f]["runs"],
                            m=v["bat"][f]["m"], avg=v["bat"][f]["avg"])
                       for v in topn(bats, lambda v: v["bat"][f]["runs"])],
            most_wkts=[dict(id=v["id"], name=v["name"], v=v["bowl"][f]["wkts"],
                            m=v["bowl"][f]["m"], avg=v["bowl"][f]["avg"])
                       for v in topn(bowls, lambda v: v["bowl"][f]["wkts"])],
            highest_score=[dict(id=v["id"], name=v["name"],
                                v=("%d%s" % (v["bat"][f]["hs"], "*" if v["bat"][f]["hs_no"] else "")),
                                _s=v["bat"][f]["hs"])
                           for v in topn(bats, lambda v: v["bat"][f]["hs"])],
            best_avg=[dict(id=v["id"], name=v["name"], v=v["bat"][f]["avg"],
                           m=v["bat"][f]["m"])
                      for v in topn(bats, lambda v: v["bat"][f]["avg"] or 0,
                                    filt=lambda v: v["bat"][f]["inn"] >= 20)],
            best_sr=[dict(id=v["id"], name=v["name"], v=v["bat"][f]["sr"],
                          m=v["bat"][f]["m"])
                     for v in topn(bats, lambda v: v["bat"][f]["sr"] or 0,
                                   filt=lambda v: v["bat"][f]["balls"] >= 500)],
            most_sixes=[dict(id=v["id"], name=v["name"], v=v["bat"][f]["sixes"],
                             m=v["bat"][f]["m"])
                        for v in topn(bats, lambda v: v["bat"][f]["sixes"])],
            most_hundreds=[dict(id=v["id"], name=v["name"], v=v["bat"][f]["hundreds"],
                                m=v["bat"][f]["m"])
                           for v in topn(bats, lambda v: v["bat"][f]["hundreds"])],
            best_econ=[dict(id=v["id"], name=v["name"], v=v["bowl"][f]["econ"],
                            m=v["bowl"][f]["m"])
                       for v in topn(bowls, lambda v: -(v["bowl"][f]["econ"] or 99),
                                     filt=lambda v: v["bowl"][f]["balls"] >= 500)],
            best_bowling_avg=[dict(id=v["id"], name=v["name"], v=v["bowl"][f]["avg"],
                                   m=v["bowl"][f]["m"])
                              for v in topn(bowls, lambda v: -(v["bowl"][f]["avg"] or 999),
                                            filt=lambda v: v["bowl"][f]["wkts"] >= 25)],
        )
    (OUT / "records.json").write_text(json.dumps(records, ensure_ascii=False))

    print("Wrote:", ", ".join(p.name for p in OUT.glob("*.json")))
    print(f"  players={len(full)} teams={len(tout)} ipl_seasons={len(iout)}")


if __name__ == "__main__":
    main()
