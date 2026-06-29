#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static site generator for cricketstatshindi.com.

Reads data/processed/*.json (from aggregate.py) and writes HTML to the repo
root (GitHub Pages serves from there). Run after aggregate.py.
"""
import json, os, glob, shutil, subprocess
from pathlib import Path
from datetime import date
import templates as TPL
from templates import (T, FMT, FMT_DESC, SITE, BRAND_EN, esc, slug, hindi_name,
                       fmt_badge, page, icon)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
OUT = ROOT                       # publish to repo root

# how many to generate for the initial launch
N_PLAYERS = 500                  # top players by impact get full profiles
N_LIST = 300                     # rows shown on /players/ listing
TODAY = date.today().isoformat()

urls = []        # (path, priority) for sitemap
search_rows = [] # [title, url, section, keywords]


def load(name):
    return json.loads((DATA / name).read_text())


def write(relpath, htmltext, priority="0.6"):
    p = OUT / relpath
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(htmltext, encoding="utf-8")
    url = "/" + str(Path(relpath).parent).replace("\\", "/").rstrip(".")
    url = "/" + relpath[:-len("index.html")] if relpath.endswith("index.html") else "/" + relpath
    urls.append((url if url != "/index.html"[:0] else "/", priority))


def player_url(pid, depth):
    return "../" * depth + f"players/{pid}/"

# ============================================================ UI fragments ===
def stat(label, value, sub=""):
    sub = f'<div class="text-xs text-cr-text hi mt-0.5">{sub}</div>' if sub else ""
    return (f'<div class="bg-cr-card border border-cr-border rounded-xl px-4 py-3">'
            f'<div class="text-2xl font-heading font-extrabold text-cr-ink tnum">{value}</div>'
            f'<div class="text-xs font-semibold text-cr-green hi uppercase tracking-wide">{label}</div>{sub}</div>')


def section_title(txt, sub=""):
    s = f'<p class="hi text-cr-text mt-1">{sub}</p>' if sub else ""
    return (f'<div class="mb-4"><h2 class="hi font-heading font-bold text-xl sm:text-2xl '
            f'text-cr-ink flex items-center gap-2"><span class="w-1.5 h-6 rounded pitch-stripe inline-block"></span>{txt}</h2>{s}</div>')


def table(headers, rows, align_right=None):
    align_right = align_right or set()
    thead = "".join(
        f'<th class="hi px-3 py-2 text-{("right" if i in align_right else "left")} '
        f'text-xs font-bold text-cr-text uppercase tracking-wide whitespace-nowrap">{h}</th>'
        for i, h in enumerate(headers))
    body = ""
    for r in rows:
        tds = ""
        for i, c in enumerate(r):
            a = "right tnum" if i in align_right else "left"
            tds += f'<td class="px-3 py-2 text-{a} text-sm whitespace-nowrap">{c}</td>'
        body += f"<tr class='border-t border-cr-border'>{tds}</tr>"
    return (f'<div class="overflow-x-auto bg-cr-card border border-cr-border rounded-xl">'
            f'<table class="w-full min-w-full"><thead class="bg-cr-bg">'
            f'<tr>{thead}</tr></thead><tbody>{body}</tbody></table></div>')


def plink(pid, name, depth, extra=""):
    hn = hindi_name(name)
    sub = f'<span class="hi text-cr-text text-xs ml-1">{hn}</span>' if hn else ""
    return f'<a href="{player_url(pid, depth)}" class="font-medium text-cr-ink hover:text-cr-green">{esc(name)}</a>{sub}{extra}'


def team_link(name, depth):
    return f'<a href="{"../"*depth}teams/{slug(name)}/" class="text-cr-ink hover:text-cr-green hi">{esc(name)}</a>'


# ================================================================ HOMEPAGE ===
def build_home(index, records, ipl, teams_d):
    depth = 0
    top = index[:8]
    cards = ""
    for p in top:
        hn = hindi_name(p["name"])
        badges = "".join(fmt_badge(f) for f in p["formats"])
        cards += f"""<a href="players/{p['id']}/" class="group bg-cr-card border border-cr-border rounded-xl p-4 hover:border-cr-green hover:shadow-md transition">
          <div class="font-heading font-bold text-cr-ink group-hover:text-cr-green">{esc(p['name'])}</div>
          {f'<div class="hi text-sm text-cr-text">{hn}</div>' if hn else ''}
          <div class="flex flex-wrap gap-1 my-2">{badges}</div>
          <div class="flex gap-4 text-sm"><span class="tnum"><b class="text-cr-ink">{p['runs']:,}</b> <span class="hi text-cr-text">रन</span></span>
          <span class="tnum"><b class="text-cr-ink">{p['wkts']}</b> <span class="hi text-cr-text">विकेट</span></span></div></a>"""

    fmt_cards = ""
    for fkey, (label, fslug) in FMT.items():
        fmt_cards += f"""<a href="{fslug}/" class="block bg-cr-card border border-cr-border rounded-xl p-5 hover:border-cr-green hover:shadow-md transition">
          <div class="flex items-center justify-between mb-2"><span class="font-heading font-extrabold text-lg text-cr-ink hi">{label}</span>{fmt_badge(fkey)}</div>
          <p class="hi text-sm text-cr-text leading-relaxed">{FMT_DESC[fkey]}</p></a>"""

    def mini(title, items, fkey, valsuffix=""):
        rows = ""
        for i, r in enumerate(items[:5]):
            rows += (f'<div class="flex items-center justify-between py-1.5 border-t border-cr-border first:border-0">'
                     f'<div class="truncate"><span class="text-cr-text text-xs mr-2 tnum">{i+1}</span>'
                     f'<a href="players/{r["id"]}/" class="text-sm font-medium text-cr-ink hover:text-cr-green">{esc(r["name"])}</a></div>'
                     f'<span class="tnum font-bold text-cr-green text-sm">{r["v"]}{valsuffix}</span></div>')
        return (f'<div class="bg-cr-card border border-cr-border rounded-xl p-4">'
                f'<div class="flex items-center justify-between mb-2"><h3 class="hi font-heading font-bold text-cr-ink">{title}</h3>{fmt_badge(fkey)}</div>{rows}</div>')

    champ = ipl[-1] if ipl else None
    champ_html = ""
    if champ and champ.get("champion"):
        champ_html = f"""<div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-8">
          <div class="hi text-sm font-semibold opacity-90 mb-1">आईपीएल {champ['season']} चैंपियन</div>
          <div class="font-heading font-extrabold text-2xl sm:text-3xl mb-3 hi flex items-center gap-2.5">{icon('trophy','w-7 h-7')}{esc(champ['champion'])}</div>
          <div class="flex flex-wrap gap-x-8 gap-y-2 text-sm">
            <div><span class="hi opacity-80">सर्वाधिक रन:</span> <b>{esc(champ['top_run']['name'])}</b> ({champ['top_run']['runs']})</div>
            <div><span class="hi opacity-80">सर्वाधिक विकेट:</span> <b>{esc(champ['top_wkt']['name'])}</b> ({champ['top_wkt']['wkts']})</div>
          </div>
          <a href="ipl/" class="hi inline-block mt-4 bg-white text-cr-green font-semibold text-sm px-4 py-2 rounded-lg hover:bg-cr-bg transition">सभी आईपीएल सीज़न →</a></div>"""

    total_runs = sum(p["runs"] for p in index)
    body = f"""
    <section class="text-center py-8 sm:py-12">
      <h1 class="hi font-heading font-extrabold text-3xl sm:text-5xl text-cr-ink leading-tight">हिंदी में <span class="text-cr-green">क्रिकेट आँकड़े</span></h1>
      <p class="hi text-cr-text text-base sm:text-lg mt-3 max-w-2xl mx-auto">टेस्ट, वनडे, टी20आई और आईपीएल के विस्तृत आँकड़े — खिलाड़ी प्रोफ़ाइल, रिकॉर्ड, टीम रिकॉर्ड और हेड-टू-हेड तुलना, सब एक जगह।</p>
      <div class="mt-5 flex flex-wrap items-center justify-center gap-3">
        <button onclick="CSH_search()" class="hi px-5 py-2.5 rounded-lg bg-cr-green text-white font-semibold hover:bg-cr-dark transition">खिलाड़ी खोजें</button>
        <a href="records/" class="hi px-5 py-2.5 rounded-lg border border-cr-border bg-white text-cr-ink font-semibold hover:border-cr-green transition">रिकॉर्ड देखें</a>
      </div>
    </section>
    <section class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-10">
      {stat('खिलाड़ी', f'{len(index):,}')}
      {stat('मैच', '10,700+')}
      {stat('कुल रन', f'{total_runs/1_000_000:.1f}M')}
      {stat('प्रारूप', '4', 'टेस्ट · वनडे · टी20 · आईपीएल')}
    </section>
    {champ_html}
    {section_title('प्रारूप', 'अपने पसंदीदा प्रारूप के आँकड़े देखें')}
    <section class="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-10">{fmt_cards}</section>
    {section_title('चर्चित खिलाड़ी', 'करियर प्रदर्शन के आधार पर शीर्ष खिलाड़ी')}
    <section class="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-2">{cards}</section>
    <div class="text-center mb-10"><a href="players/" class="hi text-cr-green font-semibold hover:underline">सभी खिलाड़ी देखें →</a></div>
    {section_title('रिकॉर्ड की झलक', 'सभी प्रारूपों के सर्वकालिक रिकॉर्ड')}
    <section class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3 mb-4">
      {mini('सर्वाधिक रन (वनडे)', records['ODI']['most_runs'], 'ODI')}
      {mini('सर्वाधिक विकेट (टेस्ट)', records['Test']['most_wkts'], 'Test')}
      {mini('सर्वाधिक रन (आईपीएल)', records['IPL']['most_runs'], 'IPL')}
      {mini('सर्वाधिक छक्के (आईपीएल)', records['IPL']['most_sixes'], 'IPL')}
      {mini('सर्वाधिक विकेट (वनडे)', records['ODI']['most_wkts'], 'ODI')}
      {mini('सर्वाधिक रन (टी20आई)', records['T20I']['most_runs'], 'T20I')}
    </section>
    <div class="text-center"><a href="records/" class="hi text-cr-green font-semibold hover:underline">सभी रिकॉर्ड देखें →</a></div>
    """
    jsonld = {"@context": "https://schema.org", "@type": "WebSite", "name": BRAND_EN,
              "alternateName": "क्रिकेट आँकड़े", "url": SITE, "inLanguage": "hi",
              "description": "हिंदी में क्रिकेट सांख्यिकी और रिकॉर्ड",
              "potentialAction": {"@type": "SearchAction",
                                  "target": SITE + "/players/?q={search_term_string}",
                                  "query-input": "required name=search_term_string"}}
    desc = "हिंदी में क्रिकेट के विस्तृत आँकड़े — टेस्ट, वनडे, टी20आई और आईपीएल के खिलाड़ी रिकॉर्ड, बल्लेबाज़ी-गेंदबाज़ी औसत, रिकॉर्ड और तुलना।"
    write("index.html", page("क्रिकेट आँकड़े — हिंदी में क्रिकेट सांख्यिकी | CricketStatsHindi",
                             desc, "/", depth, body, active="home", jsonld=jsonld), "1.0")


# =========================================================== PLAYER PROFILE ==
def bat_card(fkey, b):
    label = FMT[fkey][0]
    rows = [
        (T['m'], b['m']), (T['inn'], b['inn']), (T['runs'], f"{b['runs']:,}"),
        (T['avg'], b['avg'] if b['avg'] is not None else '—'),
        (T['sr'], b['sr'] if b['sr'] is not None else '—'),
        (T['hs'], f"{b['hs']}{'*' if b['hs_no'] else ''}"),
        (T['100s'], b['hundreds']), (T['50s'], b['fifties']),
        (T['4s'], b['fours']), (T['6s'], b['sixes']), (T['no'], b['no']),
    ]
    cells = "".join(
        f'<div class="px-3 py-2"><div class="text-xs text-cr-text hi">{l}</div>'
        f'<div class="font-heading font-bold text-cr-ink tnum">{v}</div></div>' for l, v in rows)
    return f"""<div class="bg-cr-card border border-cr-border rounded-xl overflow-hidden">
      <div class="flex items-center justify-between px-4 py-2.5 bg-cr-bg border-b border-cr-border">
        <span class="hi font-heading font-bold text-cr-ink">{T['batting']}</span>{fmt_badge(fkey)}</div>
      <div class="grid grid-cols-3 sm:grid-cols-4 divide-x divide-y divide-cr-border">{cells}</div></div>"""


def bowl_card(fkey, b):
    rows = [
        (T['m'], b['m']), (T['inn'], b['inn']), (T['wkts'], b['wkts']),
        (T['avg'], b['avg'] if b['avg'] is not None else '—'),
        (T['econ'], b['econ'] if b['econ'] is not None else '—'),
        (T['sr'], b['sr'] if b['sr'] is not None else '—'),
        (T['bbi'], b['bbi'] or '—'), (T['runs'], f"{b['runs']:,}"),
        (T['5w'], b['five_w']),
    ]
    cells = "".join(
        f'<div class="px-3 py-2"><div class="text-xs text-cr-text hi">{l}</div>'
        f'<div class="font-heading font-bold text-cr-ink tnum">{v}</div></div>' for l, v in rows)
    return f"""<div class="bg-cr-card border border-cr-border rounded-xl overflow-hidden">
      <div class="flex items-center justify-between px-4 py-2.5 bg-cr-bg border-b border-cr-border">
        <span class="hi font-heading font-bold text-cr-ink">{T['bowling']}</span>{fmt_badge(fkey)}</div>
      <div class="grid grid-cols-3 sm:grid-cols-4 divide-x divide-y divide-cr-border">{cells}</div></div>"""


def build_player(p, depth=2):
    name = p["name"]
    hn = hindi_name(name)
    badges = "".join(fmt_badge(f) for f in p["formats"])
    teamhtml = " · ".join(team_link(t, depth) for t in p["teams"][:4])

    blocks = ""
    for fkey in ["Test", "ODI", "T20I", "IPL"]:
        has_bat = fkey in p["bat"]
        has_bowl = fkey in p["bowl"]
        if not (has_bat or has_bowl):
            continue
        inner = ""
        if has_bat:
            inner += bat_card(fkey, p["bat"][fkey])
        if has_bowl:
            inner += bowl_card(fkey, p["bowl"][fkey])
        blocks += f'<div class="grid lg:grid-cols-2 gap-3 mb-3">{inner}</div>'

    # career summary tiles
    tiles = f"""<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
      {stat('कुल रन', f"{p['total_runs']:,}")}
      {stat('कुल विकेट', p['total_wkts'])}
      {stat('मैच', p['total_m'])}
      {stat('मैन ऑफ़ मैच', p['pom'])}</div>"""

    body = f"""
    <div class="bg-cr-card border border-cr-border rounded-2xl p-5 sm:p-6 mb-6">
      <div class="flex items-start gap-4">
        <div class="w-14 h-14 rounded-xl pitch-stripe text-white flex items-center justify-center font-heading font-extrabold text-2xl shrink-0">{esc(name[0])}</div>
        <div class="min-w-0">
          <h1 class="font-heading font-extrabold text-2xl sm:text-3xl text-cr-ink leading-tight">{esc(name)}</h1>
          {f'<div class="hi text-lg text-cr-green font-semibold">{hn}</div>' if hn else ''}
          <div class="hi text-sm text-cr-text mt-1">{teamhtml}</div>
          <div class="flex flex-wrap gap-1.5 mt-2">{badges}</div>
        </div>
      </div>
    </div>
    {tiles}
    {section_title('प्रारूप अनुसार करियर आँकड़े')}
    {blocks}
    <div class="mt-6 flex flex-wrap gap-3">
      <a href="{"../"*depth}compare/" class="hi px-4 py-2 rounded-lg bg-cr-green text-white text-sm font-semibold hover:bg-cr-dark">किसी से तुलना करें →</a>
      <a href="{"../"*depth}players/" class="hi px-4 py-2 rounded-lg border border-cr-border bg-white text-sm font-semibold hover:border-cr-green">सभी खिलाड़ी</a>
    </div>
    """
    fmts_hi = ", ".join(FMT[f][0] for f in p["formats"])
    desc = (f"{name}{(' ('+hn+')') if hn else ''} के क्रिकेट आँकड़े — {fmts_hi} में "
            f"{p['total_runs']:,} रन और {p['total_wkts']} विकेट। बल्लेबाज़ी व गेंदबाज़ी औसत, स्ट्राइक रेट और करियर रिकॉर्ड हिंदी में।")[:300]
    title = f"{name}{(' '+hn) if hn else ''} — क्रिकेट आँकड़े व करियर रिकॉर्ड"
    jsonld = {"@context": "https://schema.org", "@type": "Person", "name": name,
              "url": f"{SITE}/players/{p['id']}/", "jobTitle": "Cricketer",
              "nationality": p["teams"][0] if p["teams"] else None}
    trail = [("होम", "../" * depth), (T['players'], "../" * depth + "players/"), (name, None)]
    write(f"players/{p['id']}/index.html",
          page(title, desc, f"/players/{p['id']}/", depth, body,
               active="players", trail=trail, jsonld=jsonld, og_type="profile"), "0.7")
    search_rows.append([name, f"/players/{p['id']}/", "खिलाड़ी",
                        f"{name} {hn or ''} {' '.join(p['teams'][:2])} cricket stats khiladi".lower()])


def build_players_index(index):
    depth = 1
    rows = []
    for i, p in enumerate(index[:N_LIST]):
        hn = hindi_name(p["name"])
        nm = plink(p["id"], p["name"], depth)
        badges = " ".join(FMT[f][0] for f in p["formats"])
        rows.append([f'<span class="text-cr-text tnum">{i+1}</span>', nm,
                     f'<span class="hi text-xs text-cr-text">{esc(p["teams"][0]) if p["teams"] else ""}</span>',
                     f'<span class="hi text-xs">{badges}</span>',
                     f'{p["runs"]:,}', p["wkts"], p["m"]])
    body = f"""
    {section_title('सभी खिलाड़ी', f'करियर प्रदर्शन के अनुसार शीर्ष {N_LIST} खिलाड़ी — किसी भी नाम पर क्लिक करें')}
    <div class="mb-4"><button onclick="CSH_search()" class="hi w-full sm:w-auto inline-flex items-center gap-2 px-4 py-2.5 rounded-lg border border-cr-border bg-white text-cr-text text-left hover:border-cr-green">{icon('search','w-4 h-4')}खिलाड़ी का नाम खोजें…</button></div>
    {table([T['rank'], T['player'], T['team'], T['format'], T['runs'], T['wkts'], T['m']], rows, align_right={4,5,6})}
    """
    desc = "क्रिकेट खिलाड़ियों की पूरी सूची — टेस्ट, वनडे, टी20आई और आईपीएल के बल्लेबाज़ी व गेंदबाज़ी आँकड़े, औसत और करियर रिकॉर्ड हिंदी में।"
    trail = [("होम", "../"), (T['players'], None)]
    write("players/index.html", page("सभी क्रिकेट खिलाड़ी — आँकड़े व रिकॉर्ड | क्रिकेट आँकड़े",
                                      desc, "/players/", depth, body, active="players", trail=trail), "0.8")
    search_rows.append(["सभी खिलाड़ी", "/players/", "पेज", "players khiladi list sabhi"])


# ================================================================= RECORDS ===
REC_ORDER = [
    ("most_runs", "रन", False), ("most_wkts", "विकेट", False),
    ("highest_score", "", False), ("most_hundreds", "", False),
    ("most_sixes", "", False), ("best_avg", "", False),
    ("best_sr", "", False), ("best_econ", "", False),
    ("best_bowling_avg", "", False),
]


def build_records(records):
    depth = 1
    # index
    cards = ""
    for fkey, (label, fslug) in FMT.items():
        cards += f"""<a href="{fslug}/" class="block bg-cr-card border border-cr-border rounded-xl p-5 hover:border-cr-green hover:shadow-md transition">
          <div class="flex items-center justify-between mb-1"><span class="hi font-heading font-extrabold text-lg text-cr-ink">{label} रिकॉर्ड</span>{fmt_badge(fkey)}</div>
          <p class="hi text-sm text-cr-text">सर्वाधिक रन, विकेट, सर्वोच्च स्कोर, औसत और बहुत कुछ।</p></a>"""
    body = f"""{section_title('क्रिकेट रिकॉर्ड', 'प्रारूप चुनें — सभी सर्वकालिक रिकॉर्ड और लीडरबोर्ड')}
      <div class="grid sm:grid-cols-2 gap-3">{cards}</div>"""
    desc = "क्रिकेट के सर्वकालिक रिकॉर्ड हिंदी में — सर्वाधिक रन, सर्वाधिक विकेट, सर्वोच्च स्कोर, श्रेष्ठ औसत, सर्वाधिक शतक व छक्के (टेस्ट, वनडे, टी20आई, आईपीएल)।"
    write("records/index.html", page("क्रिकेट रिकॉर्ड — सर्वकालिक लीडरबोर्ड | क्रिकेट आँकड़े",
                                      desc, "/records/", depth, body, active="records",
                                      trail=[("होम", "../"), (T['records'], None)]), "0.8")
    search_rows.append(["रिकॉर्ड", "/records/", "पेज", "records record sarvkalik leaderboard"])

    # per-format
    for fkey, (label, fslug) in FMT.items():
        build_records_format(fkey, label, fslug, records[fkey])


def build_records_format(fkey, label, fslug, rec):
    depth = 2
    keys = ["most_runs", "most_wkts", "highest_score", "most_hundreds",
            "most_sixes", "best_avg", "best_sr", "best_econ", "best_bowling_avg"]
    blocks = ""
    for k in keys:
        items = rec.get(k, [])
        if not items:
            continue
        rows = []
        for i, r in enumerate(items[:25]):
            extra = ""
            if "avg" in r and r.get("avg") is not None and k in ("most_runs",):
                extra = f'<span class="text-cr-text text-xs ml-1">(औसत {r["avg"]})</span>'
            rows.append([f'<span class="text-cr-text tnum">{i+1}</span>',
                         plink(r["id"], r["name"], depth),
                         r.get("m", "—"),
                         f'<b class="text-cr-green">{r["v"]}</b>{extra}'])
        blocks += f'<div class="mb-8"><h3 class="hi font-heading font-bold text-lg text-cr-ink mb-3 flex items-center gap-2"><span class="w-1.5 h-5 rounded pitch-stripe inline-block"></span>{T[k]}</h3>{table([T["rank"], T["player"], T["m"], T[k]], rows, align_right={2,3})}</div>'

    body = f"""{section_title(f'{label} रिकॉर्ड', FMT_DESC[fkey])}
      <div class="flex flex-wrap gap-2 mb-6">{_fmt_pills(fslug, depth, 'records')}</div>
      {blocks}"""
    desc = f"{label} क्रिकेट के सर्वकालिक रिकॉर्ड हिंदी में — सर्वाधिक रन, सर्वाधिक विकेट, सर्वोच्च स्कोर, श्रेष्ठ बल्लेबाज़ी व गेंदबाज़ी औसत और सर्वाधिक छक्के।"
    write(f"records/{fslug}/index.html",
          page(f"{label} रिकॉर्ड — सर्वाधिक रन, विकेट व अधिक | क्रिकेट आँकड़े",
               desc, f"/records/{fslug}/", depth, body, active="records",
               trail=[("होम", "../../"), (T['records'], "../"), (label, None)]), "0.7")
    search_rows.append([f"{label} रिकॉर्ड", f"/records/{fslug}/", "रिकॉर्ड",
                        f"{label} records most runs wickets {fslug}".lower()])


def _fmt_pills(active_slug, depth, base):
    up = "../" * depth
    out = ""
    for fkey, (label, fslug) in FMT.items():
        on = "bg-cr-green text-white" if fslug == active_slug else "bg-white text-cr-text border border-cr-border hover:border-cr-green"
        out += f'<a href="{up}{base}/{fslug}/" class="hi px-3 py-1.5 rounded-lg text-sm font-semibold {on}">{label}</a>'
    return out


# ========================================================== FORMAT SECTIONS ==
def build_format_section(fkey, records, teams_d, index):
    label, fslug = FMT[fkey]
    depth = 1
    rec = records[fkey]

    def lead(title, items, suffix=""):
        rows = []
        for i, r in enumerate(items[:10]):
            rows.append([f'<span class="text-cr-text tnum">{i+1}</span>',
                         plink(r["id"], r["name"], depth), r.get("m", "—"),
                         f'<b class="text-cr-green">{r["v"]}{suffix}</b>'])
        return f'<div><h3 class="hi font-heading font-bold text-lg text-cr-ink mb-3">{title}</h3>{table([T["rank"],T["player"],T["m"],""], rows, align_right={2,3})}</div>'

    # teams active in this format
    trows = []
    tl = [t for t in teams_d.values() if fkey in t["formats"]]
    tl.sort(key=lambda t: t["formats"][fkey]["played"], reverse=True)
    for t in tl[:15]:
        f = t["formats"][fkey]
        trows.append([team_link(t["name"], depth), f["played"], f["won"],
                      f["lost"], f'<b>{f["win_pct"]}%</b>'])

    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="flex items-center gap-3 mb-2">{fmt_badge(fkey)}<h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">{label} क्रिकेट आँकड़े</h1></div>
      <p class="hi opacity-90 max-w-2xl">{FMT_DESC[fkey]}</p>
      <a href="{'../records/'+fslug+'/'}" class="hi inline-block mt-4 bg-white text-cr-green font-semibold text-sm px-4 py-2 rounded-lg hover:bg-cr-bg">सभी {label} रिकॉर्ड →</a>
    </div>
    {section_title('शीर्ष प्रदर्शनकर्ता')}
    <div class="grid lg:grid-cols-2 gap-6 mb-8">
      {lead('सर्वाधिक रन', rec['most_runs'])}
      {lead('सर्वाधिक विकेट', rec['most_wkts'])}
    </div>
    {section_title('टीम रिकॉर्ड')}
    {table([T['team'], T['played'], T['won'], T['lost'], T['winpct']], trows, align_right={1,2,3,4})}
    """
    desc = f"{label} क्रिकेट के आँकड़े हिंदी में — शीर्ष बल्लेबाज़, गेंदबाज़, टीम रिकॉर्ड और सर्वकालिक रिकॉर्ड। {FMT_DESC[fkey]}"[:300]
    write(f"{fslug}/index.html",
          page(f"{label} क्रिकेट आँकड़े — रिकॉर्ड, खिलाड़ी व टीमें | क्रिकेट आँकड़े",
               desc, f"/{fslug}/", depth, body, active=fslug,
               trail=[("होम", "../"), (label, None)]), "0.8")
    search_rows.append([f"{label} आँकड़े", f"/{fslug}/", "प्रारूप", f"{label} {fslug} cricket stats format"])


# =================================================================== TEAMS ===
def build_teams(teams_d, full):
    depth = 1
    tl = sorted(teams_d.values(), key=lambda t: t["total_played"], reverse=True)
    rows = []
    for t in tl:
        rows.append([team_link(t["name"], depth), t["total_played"], t["total_won"],
                     f'<b class="text-cr-green">{t["win_pct"]}%</b>',
                     " ".join(FMT[f][0] for f in t["formats"])])
    body = f"""{section_title('टीमें', 'सभी अंतरराष्ट्रीय व आईपीएल टीमें — जीत प्रतिशत सहित')}
      {table([T['team'], T['played'], T['won'], T['winpct'], T['format']], rows, align_right={1,2,3})}"""
    desc = "क्रिकेट टीमों के रिकॉर्ड हिंदी में — टेस्ट, वनडे, टी20आई और आईपीएल में जीत-हार, जीत प्रतिशत और प्रारूप-वार प्रदर्शन।"
    write("teams/index.html", page("क्रिकेट टीमें — रिकॉर्ड व जीत प्रतिशत | क्रिकेट आँकड़े",
                                    desc, "/teams/", depth, body, active="teams",
                                    trail=[("होम", "../"), (T['teams'], None)]), "0.8")
    search_rows.append(["सभी टीमें", "/teams/", "पेज", "teams team list sabhi"])

    # roster: players whose primary team is this
    roster = {}
    for p in full.values():
        if p["teams"]:
            roster.setdefault(p["teams"][0], []).append(p)
    for t in tl:
        build_team(t, roster.get(t["name"], []))


def build_team(t, players_list):
    depth = 2
    name = t["name"]
    frows = []
    for fkey in ["Test", "ODI", "T20I", "IPL"]:
        if fkey in t["formats"]:
            f = t["formats"][fkey]
            frows.append([f'<span class="hi">{FMT[fkey][0]}</span>', f["played"], f["won"],
                          f["lost"], f["tied"] + f["nr"], f'<b class="text-cr-green">{f["win_pct"]}%</b>'])
    # notable players
    players_list = sorted(players_list, key=lambda p: p["total_runs"] + p["total_wkts"] * 20, reverse=True)[:15]
    prows = []
    for p in players_list:
        prows.append([plink(p["id"], p["name"], depth),
                      f'{p["total_runs"]:,}', p["total_wkts"], p["total_m"]])
    pblock = (section_title('मुख्य खिलाड़ी') + table([T['player'], T['runs'], T['wkts'], T['m']], prows, align_right={1,2,3})) if prows else ""

    body = f"""
    <div class="bg-cr-card border border-cr-border rounded-2xl p-5 sm:p-6 mb-6 flex items-center gap-4">
      <div class="w-14 h-14 rounded-xl pitch-stripe text-white flex items-center justify-center font-heading font-extrabold text-2xl">{esc(name[0])}</div>
      <div><h1 class="font-heading font-extrabold text-2xl sm:text-3xl text-cr-ink hi">{esc(name)}</h1>
      <div class="hi text-sm text-cr-text mt-1">{t['total_played']} मैच · {t['total_won']} जीत · {t['win_pct']}% जीत दर</div></div>
    </div>
    {section_title('प्रारूप अनुसार रिकॉर्ड')}
    {table([T['format'], T['played'], T['won'], T['lost'], T['tied'], T['winpct']], frows, align_right={1,2,3,4,5})}
    <div class="mt-8">{pblock}</div>
    """
    desc = f"{name} का क्रिकेट रिकॉर्ड हिंदी में — {t['total_played']} मैचों में {t['total_won']} जीत ({t['win_pct']}%)। प्रारूप-वार जीत-हार और मुख्य खिलाड़ी।"
    write(f"teams/{slug(name)}/index.html",
          page(f"{name} — टीम रिकॉर्ड व आँकड़े | क्रिकेट आँकड़े", desc,
               f"/teams/{slug(name)}/", depth, body, active="teams",
               trail=[("होम", "../../"), (T['teams'], "../"), (name, None)],
               jsonld={"@context": "https://schema.org", "@type": "SportsTeam", "name": name,
                       "sport": "Cricket", "url": f"{SITE}/teams/{slug(name)}/"}), "0.6")
    search_rows.append([name, f"/teams/{slug(name)}/", "टीम", f"{name} team cricket".lower()])


# ===================================================================== IPL ===
def build_ipl(ipl, records, teams_d):
    depth = 1
    rows = []
    for s in reversed(ipl):
        if not s.get("season"):
            continue
        ch = s.get("champion") or "—"
        tr = s.get("top_run") or {}
        tw = s.get("top_wkt") or {}
        rows.append([f'<a href="{s["season"]}/" class="font-bold text-cr-ink hover:text-cr-green tnum">{s["season"]}</a>',
                     f'<span class="hi">{esc(ch)}</span>',
                     plink(tr.get("id",""), tr.get("name","—"), depth) + f' <span class="text-cr-text text-xs tnum">({tr.get("runs","")})</span>' if tr else "—",
                     plink(tw.get("id",""), tw.get("name","—"), depth) + f' <span class="text-cr-text text-xs tnum">({tw.get("wkts","")})</span>' if tw else "—"])
    rec = records["IPL"]
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="flex items-center gap-3 mb-2">{fmt_badge('IPL')}<h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">इंडियन प्रीमियर लीग</h1></div>
      <p class="hi opacity-90 max-w-2xl">{FMT_DESC['IPL']} — सीज़न-दर-सीज़न चैंपियन, शीर्ष रन-स्कोरर और विकेट-टेकर।</p>
      <a href="../records/ipl/" class="hi inline-block mt-4 bg-white text-cr-green font-semibold text-sm px-4 py-2 rounded-lg hover:bg-cr-bg">सभी आईपीएल रिकॉर्ड →</a>
    </div>
    {section_title('सीज़न-वार सारांश', 'किसी भी सीज़न पर क्लिक करके विवरण देखें')}
    {table([T['season'], T['champion'], 'ऑरेंज कैप', 'पर्पल कैप'], rows)}
    """
    desc = "आईपीएल आँकड़े हिंदी में — सभी सीज़न के चैंपियन, ऑरेंज कैप (सर्वाधिक रन), पर्पल कैप (सर्वाधिक विकेट), टीम रिकॉर्ड और सर्वकालिक रिकॉर्ड।"
    write("ipl/index.html", page("आईपीएल आँकड़े — सीज़न, चैंपियन व रिकॉर्ड | क्रिकेट आँकड़े",
                                  desc, "/ipl/", depth, body, active="ipl",
                                  trail=[("होम", "../"), ("आईपीएल", None)]), "0.9")
    search_rows.append(["आईपीएल", "/ipl/", "प्रारूप", "ipl indian premier league season champion"])

    for s in ipl:
        if s.get("season"):
            build_ipl_season(s)


def build_ipl_season(s):
    depth = 2
    season = s["season"]
    tr = s.get("top_run") or {}
    tw = s.get("top_wkt") or {}
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="hi text-sm font-semibold opacity-90">आईपीएल</div>
      <h1 class="hi font-heading font-extrabold text-3xl sm:text-4xl">सीज़न {season}</h1>
      {f'<div class="hi text-xl mt-2 flex items-center gap-2">{icon("trophy","w-6 h-6")}<span>चैंपियन: <b>{esc(s["champion"])}</b></span></div>' if s.get("champion") else ''}
    </div>
    <div class="grid sm:grid-cols-2 gap-3 mb-6">
      <div class="bg-cr-card border border-cr-border rounded-xl p-5">
        <div class="hi text-sm font-semibold text-cr-green mb-1 flex items-center gap-1.5">{icon('cap','w-4 h-4','#f97316')}ऑरेंज कैप — सर्वाधिक रन</div>
        <div class="font-heading font-bold text-xl text-cr-ink">{plink(tr.get("id",""), tr.get("name","—"), depth)}</div>
        <div class="tnum text-2xl font-extrabold text-cr-ink mt-1">{tr.get("runs","—")} <span class="hi text-sm font-normal text-cr-text">रन</span></div>
      </div>
      <div class="bg-cr-card border border-cr-border rounded-xl p-5">
        <div class="hi text-sm font-semibold text-cr-ball mb-1 flex items-center gap-1.5">{icon('cap','w-4 h-4','#7c3aed')}पर्पल कैप — सर्वाधिक विकेट</div>
        <div class="font-heading font-bold text-xl text-cr-ink">{plink(tw.get("id",""), tw.get("name","—"), depth)}</div>
        <div class="tnum text-2xl font-extrabold text-cr-ink mt-1">{tw.get("wkts","—")} <span class="hi text-sm font-normal text-cr-text">विकेट</span></div>
      </div>
    </div>
    <div class="bg-cr-card border border-cr-border rounded-xl p-4 hi text-cr-text">इस सीज़न में कुल <b class="text-cr-ink tnum">{s.get("matches","—")}</b> मैच खेले गए।</div>
    <div class="mt-6"><a href="../" class="hi text-cr-green font-semibold hover:underline">← सभी आईपीएल सीज़न</a></div>
    """
    desc = f"आईपीएल {season} आँकड़े हिंदी में — चैंपियन {s.get('champion','—')}, ऑरेंज कैप {tr.get('name','—')} ({tr.get('runs','—')} रन), पर्पल कैप {tw.get('name','—')} ({tw.get('wkts','—')} विकेट)।"
    write(f"ipl/{season}/index.html",
          page(f"आईपीएल {season} — चैंपियन, ऑरेंज व पर्पल कैप | क्रिकेट आँकड़े",
               desc, f"/ipl/{season}/", depth, body, active="ipl",
               trail=[("होम", "../../"), ("आईपीएल", "../"), (season, None)]), "0.6")
    search_rows.append([f"आईपीएल {season}", f"/ipl/{season}/", "आईपीएल सीज़न", f"ipl {season} season champion"])


# ============================================================== COMPARE/H2H ==
MARQUEE_PAIRS = [
    ("ba607b88", "Rohit"), # placeholders replaced below by name lookup
]


def build_compare(full, index, pairs):
    depth = 1
    cards = ""
    for a, b in pairs:
        pa, pb = full.get(a), full.get(b)
        if not pa or not pb:
            continue
        cards += f"""<a href="{slug(pa['name'])}-vs-{slug(pb['name'])}/" class="block bg-cr-card border border-cr-border rounded-xl p-4 hover:border-cr-green hover:shadow-md transition">
          <div class="flex items-center justify-between"><span class="font-heading font-bold text-cr-ink">{esc(pa['name'])}</span>
          <span class="hi text-cr-green font-bold text-sm">बनाम</span>
          <span class="font-heading font-bold text-cr-ink">{esc(pb['name'])}</span></div></a>"""
    body = f"""{section_title('खिलाड़ी तुलना (हेड-टू-हेड)', 'दो खिलाड़ियों के करियर आँकड़ों की आमने-सामने तुलना')}
      <div class="grid sm:grid-cols-2 gap-3">{cards}</div>"""
    desc = "क्रिकेट खिलाड़ियों की हेड-टू-हेड तुलना हिंदी में — दो खिलाड़ियों के रन, औसत, स्ट्राइक रेट, विकेट और करियर आँकड़ों की आमने-सामने तुलना।"
    write("compare/index.html", page("खिलाड़ी तुलना — हेड-टू-हेड आँकड़े | क्रिकेट आँकड़े",
                                      desc, "/compare/", depth, body, active="compare",
                                      trail=[("होम", "../"), (T['compare'], None)]), "0.8")
    search_rows.append(["खिलाड़ी तुलना", "/compare/", "पेज", "compare h2h head to head tulna"])

    for a, b in pairs:
        if full.get(a) and full.get(b):
            build_h2h(full[a], full[b])


def build_h2h(pa, pb):
    depth = 2
    s = f"{slug(pa['name'])}-vs-{slug(pb['name'])}"

    def cmp_row(label, va, vb, higher_better=True):
        va_n = va if isinstance(va, (int, float)) else None
        vb_n = vb if isinstance(vb, (int, float)) else None
        la = lb = ""
        if va_n is not None and vb_n is not None and va_n != vb_n:
            a_better = (va_n > vb_n) == higher_better
            la = "text-cr-green font-bold" if a_better else "text-cr-text"
            lb = "text-cr-green font-bold" if not a_better else "text-cr-text"
        return (f'<tr class="border-t border-cr-border">'
                f'<td class="px-3 py-2 text-right tnum {la}">{va if va is not None else "—"}</td>'
                f'<td class="px-3 py-2 text-center hi text-xs font-semibold text-cr-text whitespace-nowrap">{label}</td>'
                f'<td class="px-3 py-2 text-left tnum {lb}">{vb if vb is not None else "—"}</td></tr>')

    blocks = ""
    for fkey in ["Test", "ODI", "T20I", "IPL"]:
        ba, bb = pa["bat"].get(fkey), pb["bat"].get(fkey)
        wa, wb = pa["bowl"].get(fkey), pb["bowl"].get(fkey)
        if not (ba or bb or wa or wb):
            continue
        rows = ""
        if ba or bb:
            g = lambda d, k: (d or {}).get(k)
            rows += cmp_row("मैच", g(ba,'m'), g(bb,'m'))
            rows += cmp_row("रन", g(ba,'runs'), g(bb,'runs'))
            rows += cmp_row("औसत", g(ba,'avg'), g(bb,'avg'))
            rows += cmp_row("स्ट्राइक रेट", g(ba,'sr'), g(bb,'sr'))
            rows += cmp_row("शतक", g(ba,'hundreds'), g(bb,'hundreds'))
            rows += cmp_row("अर्धशतक", g(ba,'fifties'), g(bb,'fifties'))
            rows += cmp_row("छक्के", g(ba,'sixes'), g(bb,'sixes'))
        if wa or wb:
            g = lambda d, k: (d or {}).get(k)
            rows += cmp_row("विकेट", g(wa,'wkts'), g(wb,'wkts'))
            rows += cmp_row("गेंदबाज़ी औसत", g(wa,'avg'), g(wb,'avg'), higher_better=False)
            rows += cmp_row("इकॉनमी", g(wa,'econ'), g(wb,'econ'), higher_better=False)
        blocks += f"""<div class="mb-6"><div class="flex items-center gap-2 mb-2">{fmt_badge(fkey)}<h3 class="hi font-heading font-bold text-cr-ink">{FMT[fkey][0]}</h3></div>
          <div class="bg-cr-card border border-cr-border rounded-xl overflow-hidden"><table class="w-full"><thead class="bg-cr-bg"><tr>
          <th class="px-3 py-2 text-right text-xs font-bold text-cr-ink">{esc(pa['name'])}</th>
          <th class="px-3 py-2 text-center text-xs font-bold text-cr-text hi">आँकड़ा</th>
          <th class="px-3 py-2 text-left text-xs font-bold text-cr-ink">{esc(pb['name'])}</th></tr></thead>
          <tbody>{rows}</tbody></table></div></div>"""

    body = f"""
    <div class="grid grid-cols-2 gap-3 mb-6">
      <a href="../../players/{pa['id']}/" class="bg-cr-card border border-cr-border rounded-xl p-4 text-center hover:border-cr-green">
        <div class="w-12 h-12 mx-auto rounded-xl pitch-stripe text-white flex items-center justify-center font-heading font-extrabold text-xl mb-2">{esc(pa['name'][0])}</div>
        <div class="font-heading font-bold text-cr-ink">{esc(pa['name'])}</div>
        {f'<div class="hi text-sm text-cr-text">{hindi_name(pa["name"])}</div>' if hindi_name(pa['name']) else ''}</a>
      <a href="../../players/{pb['id']}/" class="bg-cr-card border border-cr-border rounded-xl p-4 text-center hover:border-cr-green">
        <div class="w-12 h-12 mx-auto rounded-xl pitch-stripe text-white flex items-center justify-center font-heading font-extrabold text-xl mb-2">{esc(pb['name'][0])}</div>
        <div class="font-heading font-bold text-cr-ink">{esc(pb['name'])}</div>
        {f'<div class="hi text-sm text-cr-text">{hindi_name(pb["name"])}</div>' if hindi_name(pb['name']) else ''}</a>
    </div>
    {section_title('प्रारूप अनुसार तुलना', 'हरे रंग में बेहतर आँकड़ा')}
    {blocks}"""
    title = f"{pa['name']} बनाम {pb['name']} — तुलना | क्रिकेट आँकड़े"
    desc = f"{pa['name']} बनाम {pb['name']} की हेड-टू-हेड तुलना हिंदी में — रन, औसत, स्ट्राइक रेट, विकेट और करियर आँकड़ों की आमने-सामने तुलना सभी प्रारूपों में।"
    write(f"compare/{s}/index.html",
          page(title, desc, f"/compare/{s}/", depth, body, active="compare",
               trail=[("होम", "../../"), (T['compare'], "../"), (f"{pa['name']} बनाम {pb['name']}", None)]), "0.6")
    search_rows.append([f"{pa['name']} बनाम {pb['name']}", f"/compare/{s}/", "तुलना",
                        f"{pa['name']} vs {pb['name']} compare h2h".lower()])


# =============================================================== SCORECARDS ===
def build_matches():
    """Generate scorecards for IPL finals (one per season)."""
    depth = 1
    finals = []
    for fn in glob.glob(str(RAW / "ipl_json" / "*.json")):
        try:
            d = json.load(open(fn))
        except Exception:
            continue
        ev = d["info"].get("event", {})
        if isinstance(ev, dict) and str(ev.get("stage", "")).lower() == "final":
            finals.append((fn, d))
    finals.sort(key=lambda x: x[1]["info"].get("dates", [""])[0])
    listed = []
    for fn, d in finals:
        mid = Path(fn).stem
        info = d["info"]
        season = str(info.get("season", "")).split("/")[0]
        listed.append((mid, season, info))
        build_scorecard(mid, d)
    # index
    rows = []
    for mid, season, info in reversed(listed):
        teams = " बनाम ".join(info.get("teams", []))
        oc = info.get("outcome", {})
        res = oc.get("winner", "—")
        rows.append([f'<a href="{mid}/" class="font-bold text-cr-ink hover:text-cr-green tnum">{season}</a>',
                     f'<span class="hi">{esc(teams)}</span>',
                     f'<span class="hi text-cr-green font-semibold">{esc(res)}</span>'])
    body = f"""{section_title('आईपीएल फ़ाइनल — स्कोरकार्ड', 'हर सीज़न के फ़ाइनल मैच का पूरा स्कोरकार्ड')}
      {table([T['season'], T['team'], 'विजेता'], rows)}"""
    desc = "आईपीएल फ़ाइनल मैचों के स्कोरकार्ड हिंदी में — हर सीज़न के फ़ाइनल का पूरा बल्लेबाज़ी व गेंदबाज़ी विवरण और परिणाम।"
    write("matches/index.html", page("मैच स्कोरकार्ड — आईपीएल फ़ाइनल | क्रिकेट आँकड़े",
                                      desc, "/matches/", depth, body, active="matches",
                                      trail=[("होम", "../"), (T['matches'], None)]), "0.7")
    search_rows.append(["मैच स्कोरकार्ड", "/matches/", "पेज", "matches scorecard final ipl"])


def build_scorecard(mid, d):
    depth = 2
    info = d["info"]
    season = str(info.get("season", "")).split("/")[0]
    teams = info.get("teams", [])
    venue = info.get("venue", "")
    oc = info.get("outcome", {})
    pom = ", ".join(info.get("player_of_match", []) or [])
    winner = oc.get("winner", "")
    by = oc.get("by", {})
    margin = ""
    if "runs" in by:
        margin = f"{by['runs']} रन से"
    elif "wickets" in by:
        margin = f"{by['wickets']} विकेट से"

    innings_html = ""
    for inn in d.get("innings", []):
        team = inn.get("team", "")
        bat = {}      # batter -> [runs, balls, 4s, 6s, out?]
        bowl = {}     # bowler -> [balls, runs, wkts]
        order = []
        total = 0; wkts = 0; legal = 0
        for ov in inn.get("overs", []):
            for de in ov.get("deliveries", []):
                ex = de.get("extras", {})
                wide = "wides" in ex; nb = "noballs" in ex
                bye = ex.get("byes", 0) + ex.get("legbyes", 0)
                rb = de["runs"]; total += rb.get("total", 0)
                bt = de.get("batter")
                if bt not in bat:
                    bat[bt] = [0, 0, 0, 0, False]; order.append(bt)
                bat[bt][0] += rb.get("batter", 0)
                if not wide:
                    bat[bt][1] += 1
                if rb.get("batter") == 4: bat[bt][2] += 1
                elif rb.get("batter") == 6: bat[bt][3] += 1
                bw = de.get("bowler")
                bowl.setdefault(bw, [0, 0, 0])
                if not (wide or nb):
                    bowl[bw][0] += 1; legal += 1
                bowl[bw][1] += rb.get("total", 0) - bye - ex.get("penalty", 0)
                for w in de.get("wickets", []):
                    wkts += 1
                    po = w.get("player_out")
                    if po in bat:
                        bat[po][4] = True
                    if w.get("kind") in {"bowled","caught","lbw","stumped","caught and bowled","hit wicket"}:
                        bowl[bw][2] += 1
        batrows = []
        for b in order:
            r = bat[b]
            sr = round(r[0] / r[1] * 100, 1) if r[1] else 0
            status = "नाबाद" if not r[4] else ""
            batrows.append([f'{esc(b)} <span class="text-cr-text text-xs hi">{status}</span>',
                            r[0], r[1], r[2], r[3], f'{sr}'])
        bowlrows = []
        for b, r in bowl.items():
            ov_str = f"{r[0]//6}.{r[0]%6}"
            econ = round(r[1] / (r[0] / 6), 2) if r[0] else 0
            bowlrows.append([esc(b), ov_str, r[1], r[2], f'{econ}'])
        ov_total = f"{legal//6}.{legal%6}"
        innings_html += f"""<div class="mb-6">
          <div class="flex items-center justify-between bg-cr-green text-white rounded-t-xl px-4 py-2.5">
            <span class="hi font-heading font-bold">{esc(team)}</span>
            <span class="tnum font-bold">{total}/{wkts} <span class="text-sm font-normal opacity-90">({ov_total} ओवर)</span></span></div>
          {table(['बल्लेबाज़', 'रन', 'गेंद', '4s', '6s', 'SR'], batrows, align_right={1,2,3,4,5})}
          <div class="mt-2">{table(['गेंदबाज़', 'ओवर', 'रन', 'विकेट', 'इको'], bowlrows, align_right={1,2,3,4})}</div>
        </div>"""

    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 mb-6">
      <div class="hi text-sm opacity-90">आईपीएल {season} · फ़ाइनल</div>
      <h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">{esc(' बनाम '.join(teams))}</h1>
      <div class="hi mt-2 opacity-90">{esc(venue)}</div>
      {f'<div class="hi text-lg font-bold mt-2 flex items-center gap-2">{icon("trophy","w-5 h-5")}<span>{esc(winner)} {margin} विजयी</span></div>' if winner else ''}
      {f'<div class="hi text-sm mt-1 opacity-90">मैन ऑफ़ द मैच: <b>{esc(pom)}</b></div>' if pom else ''}
    </div>
    {innings_html}
    <div class="mt-4"><a href="../" class="hi text-cr-green font-semibold hover:underline">← सभी स्कोरकार्ड</a></div>
    """
    title = f"{' बनाम '.join(teams)} — आईपीएल {season} फ़ाइनल स्कोरकार्ड | क्रिकेट आँकड़े"
    desc = f"आईपीएल {season} फ़ाइनल स्कोरकार्ड हिंदी में — {' बनाम '.join(teams)}। {winner} {margin} विजयी। पूरा बल्लेबाज़ी व गेंदबाज़ी विवरण।"[:300]
    write(f"matches/{mid}/index.html",
          page(title, desc, f"/matches/{mid}/", depth, body, active="matches",
               trail=[("होम", "../../"), (T['matches'], "../"), (f"{season} फ़ाइनल", None)]), "0.5")
    search_rows.append([f"आईपीएल {season} फ़ाइनल", f"/matches/{mid}/", "स्कोरकार्ड",
                        f"ipl {season} final scorecard {' '.join(teams)}".lower()])


# ============================================================ STATIC ASSETS ==
def write_favicons():
    """Rasterize favicon.svg into the full favicon pack + webmanifest.

    Needs `rsvg-convert` (SVG→PNG) and Pillow (multi-size .ico). The .svg must
    already be written by write_static() before this runs.
    """
    from PIL import Image
    svg = OUT / "favicon.svg"
    # transparent-corner PNGs straight from the SVG
    png_sizes = {
        "favicon-16x16.png": 16,
        "favicon-32x32.png": 32,
        "favicon-192x192.png": 192,
        "favicon-512x512.png": 512,
        "apple-touch-icon.png": 180,
    }
    for name, size in png_sizes.items():
        subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size),
                        str(svg), "-o", str(OUT / name)], check=True)
    # apple-touch-icon: iOS dislikes transparency — flatten onto white
    apple = Image.open(OUT / "apple-touch-icon.png").convert("RGBA")
    bg = Image.new("RGBA", apple.size, (255, 255, 255, 255))
    bg.alpha_composite(apple)
    bg.convert("RGB").save(OUT / "apple-touch-icon.png")
    # multi-resolution favicon.ico (16 + 32)
    Image.open(OUT / "favicon-32x32.png").convert("RGBA").save(
        OUT / "favicon.ico", sizes=[(16, 16), (32, 32)])
    # web app manifest
    manifest = {
        "name": "क्रिकेट आँकड़े",
        "short_name": "क्रिकेट आँकड़े",
        "icons": [
            {"src": "/favicon-192x192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/favicon-512x512.png", "sizes": "512x512", "type": "image/png"},
        ],
        "theme_color": "#15803d",
        "background_color": "#ffffff",
        "display": "standalone",
    }
    (OUT / "site.webmanifest").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def write_static():
    # favicon
    (OUT / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 64 64">'
        '<defs><radialGradient id="s" cx="40%" cy="35%" r="60%">'
        '<stop offset="0%" stop-color="#A52A2A" stop-opacity="0.3"/>'
        '<stop offset="100%" stop-color="#4A0E0E" stop-opacity="0.3"/></radialGradient></defs>'
        '<circle cx="32" cy="32" r="28" fill="#8B1A1A"/>'
        '<circle cx="32" cy="32" r="28" fill="url(#s)"/>'
        '<line x1="29" y1="6" x2="58" y2="35" stroke="#F5E6D0" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="18" y1="10" x2="54" y2="46" stroke="#F5E6D0" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="10" y1="18" x2="46" y2="54" stroke="#F5E6D0" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="6" y1="29" x2="35" y2="58" stroke="#F5E6D0" stroke-width="2" stroke-linecap="round"/></svg>')
    # favicon raster pack (PNG + ICO + webmanifest) rendered from favicon.svg
    write_favicons()
    # search.js
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    # search index
    (OUT / "search-index.json").write_text(
        json.dumps(search_rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # robots
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    # CNAME
    (OUT / "CNAME").write_text("cricketstatshindi.com\n")
    # 404
    body404 = ('<div class="text-center py-20"><div class="hi font-heading font-extrabold text-6xl text-cr-green">404</div>'
               '<p class="hi text-xl text-cr-ink mt-4">यह पेज नहीं मिला</p>'
               '<a href="/" class="hi inline-block mt-6 px-5 py-2.5 rounded-lg bg-cr-green text-white font-semibold">होम पर लौटें</a></div>')
    (OUT / "404.html").write_text(page("पेज नहीं मिला (404) | क्रिकेट आँकड़े",
        "यह पेज उपलब्ध नहीं है।", "/404.html", 0, body404, active=""), encoding="utf-8")


def write_sitemap():
    seen = set(); items = []
    for url, prio in urls:
        if url in seen:
            continue
        seen.add(url)
        items.append(f"  <url><loc>{SITE}{url}</loc><lastmod>{TODAY}</lastmod>"
                     f"<priority>{prio}</priority></url>")
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           + "\n".join(items) + "\n</urlset>\n")
    (OUT / "sitemap.xml").write_text(xml, encoding="utf-8")
    return len(items)


SEARCH_JS = r"""
let CSH_idx=null,CSH_box=null;
async function CSH_load(){if(CSH_idx)return CSH_idx;
  const base=location.pathname.includes('/players/')||location.pathname.split('/').filter(Boolean).length>0?
    location.origin+'/':'/';
  const r=await fetch(location.origin+'/search-index.json');CSH_idx=await r.json();return CSH_idx;}
function CSH_search(){if(CSH_box){CSH_box.remove();CSH_box=null;return;}
  CSH_box=document.createElement('div');
  CSH_box.style.cssText='position:fixed;inset:0;z-index:200;background:rgba(20,40,25,.45);backdrop-filter:blur(3px);display:flex;align-items:flex-start;justify-content:center;padding-top:10vh';
  CSH_box.innerHTML='<div onclick="event.stopPropagation()" style="width:92%;max-width:560px;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 20px 60px rgba(0,0,0,.3)">'+
    '<input id="cshq" placeholder="खिलाड़ी, टीम, रिकॉर्ड खोजें…" style="width:100%;padding:16px 18px;border:0;outline:0;font-size:16px;border-bottom:1px solid #e2e8e0;font-family:Inter,Noto Sans Devanagari,sans-serif">'+
    '<div id="cshr" style="max-height:60vh;overflow:auto"></div></div>';
  CSH_box.onclick=()=>CSH_search();
  document.body.appendChild(CSH_box);
  const q=document.getElementById('cshq');q.focus();
  CSH_load().then(()=>CSH_render(''));
  q.addEventListener('input',e=>CSH_render(e.target.value));
  q.addEventListener('keydown',e=>{if(e.key==='Escape')CSH_search();
    if(e.key==='Enter'){const a=document.querySelector('#cshr a');if(a)location.href=a.href;}});}
function CSH_render(q){const box=document.getElementById('cshr');if(!box)return;
  q=q.trim().toLowerCase();let res;
  if(!q){res=CSH_idx.slice(0,8);}
  else{res=[];for(const row of CSH_idx){const hay=(row[0]+' '+row[3]).toLowerCase();
    let i=0,ok=true;for(const ch of q){i=hay.indexOf(ch,i);if(i<0){ok=false;break;}i++;}
    if(hay.includes(q)){res.push([0,row]);}else if(ok){res.push([1,row]);}}
    res.sort((a,b)=>a[0]-b[0]);res=res.slice(0,20).map(x=>x[1]);}
  if(!res.length){box.innerHTML='<div style="padding:20px;color:#52635a;font-family:Noto Sans Devanagari">कोई परिणाम नहीं</div>';return;}
  box.innerHTML=res.map(r=>'<a href="'+location.origin+r[1]+'" style="display:flex;justify-content:space-between;gap:10px;padding:11px 18px;text-decoration:none;border-bottom:1px solid #f0f3f0;color:#16241b">'+
    '<span style="font-weight:600">'+r[0]+'</span><span style="font-size:12px;color:#15803d;font-family:Noto Sans Devanagari;align-self:center">'+r[2]+'</span></a>').join('');}
document.addEventListener('keydown',e=>{if((e.key==='/'||((e.metaKey||e.ctrlKey)&&e.key==='k'))&&!/INPUT|TEXTAREA/.test(document.activeElement.tagName)){e.preventDefault();CSH_search();}});
"""


# ===================================================================== MAIN ===
def main():
    print("Loading processed data…")
    index = load("players_index.json")
    full = load("players_full.json")
    records = load("records.json")
    ipl = load("ipl.json")
    teams_d = load("teams.json")

    # build name->id for marquee pairs
    name2id = {}
    for pid, p in full.items():
        name2id.setdefault(p["name"], pid)
    def pid_of(n): return name2id.get(n)
    marquee = [
        ("V Kohli", "RG Sharma"), ("V Kohli", "Babar Azam"),
        ("V Kohli", "SPD Smith"), ("V Kohli", "KS Williamson"),
        ("RG Sharma", "DA Warner"), ("Babar Azam", "KS Williamson"),
        ("JJ Bumrah", "Rashid Khan"), ("R Ashwin", "RA Jadeja"),
        ("JM Anderson", "SCJ Broad"), ("MA Starc", "PJ Cummins"),
        ("AB de Villiers", "CH Gayle"), ("MS Dhoni", "JC Buttler"),
        ("KL Rahul", "Shubman Gill"), ("HH Pandya", "RA Jadeja"),
        ("AD Russell", "KA Pollard"), ("SP Narine", "Rashid Khan"),
        ("V Kohli", "AB de Villiers"), ("RG Sharma", "Q de Kock"),
    ]
    pairs = [(pid_of(a), pid_of(b)) for a, b in marquee]
    pairs = [(a, b) for a, b in pairs if a and b]

    print("Building homepage…")
    build_home(index, records, ipl, teams_d)
    print(f"Building {N_PLAYERS} player profiles…")
    for p in index[:N_PLAYERS]:
        build_player(full[p["id"]])
    build_players_index(index)
    print("Building records…")
    build_records(records)
    print("Building format sections…")
    for fkey in ["Test", "ODI", "T20I", "IPL"]:
        build_format_section(fkey, records, teams_d, index)
    print("Building teams…")
    build_teams(teams_d, full)
    print("Building IPL…")
    build_ipl(ipl, records, teams_d)
    print("Building compare/H2H…")
    build_compare(full, index, pairs)
    print("Building scorecards…")
    build_matches()
    print("Writing static assets + sitemap…")
    write_static()
    n = write_sitemap()
    print(f"DONE. {n} URLs, {len(search_rows)} search entries.")


if __name__ == "__main__":
    main()
