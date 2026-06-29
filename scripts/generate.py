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
import content as C
import thisday as TD
import tournaments as TT
import scorecards as SC

# merge the extra curated Devanagari player names into the shared dictionary
TPL.HINDI_NAMES.update(C.PLAYER_HI_EXTRA)

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
OUT = ROOT                       # publish to repo root

# how many to generate for the initial launch
N_PLAYERS = 500                  # top players by impact get full profiles
N_LIST = 300                     # rows shown on /players/ listing
TODAY = date.today().isoformat()

# IndexNow key — published at /<key>.txt so Bing/Yandex can verify ownership
# when scripts/indexnow.py submits updated URLs. Keep in sync with that file.
INDEXNOW_KEY = "bec9a8baaba12e5397988c4017e88088"

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


# Player ids that have a generated profile page (top N_PLAYERS). Populated at
# the start of main() so every link helper can gate on it.
_PAGE_PIDS = set()


def plink(pid, name, depth, extra=""):
    """Link to a player's profile if it exists, else render plain text.

    Only the top N_PLAYERS get profile pages, so team rosters and records
    leaderboards reference ~1,600 players without pages. Gating here keeps
    those references as plain text instead of broken links.
    """
    hn = hindi_name(name)
    sub = f'<span class="hi text-cr-text text-xs ml-1">{hn}</span>' if hn else ""
    if not pid or pid not in _PAGE_PIDS:
        return f'<span class="font-medium text-cr-ink">{esc(name)}</span>{sub}{extra}'
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
    <div class="mt-12">{C.prose([
      "<b>क्रिकेट आँकड़े</b> (CricketStatsHindi.com) हिंदी भाषी क्रिकेट प्रेमियों के लिए "
      "एक संपूर्ण आँकड़ा मंच है, जहाँ टेस्ट, वनडे, टी20आई और आईपीएल — चारों प्रमुख "
      "प्रारूपों के विस्तृत रिकॉर्ड एक ही जगह उपलब्ध हैं। यहाँ हज़ारों खिलाड़ियों की "
      "करियर प्रोफ़ाइल, बल्लेबाज़ी और गेंदबाज़ी के आँकड़े, औसत, स्ट्राइक रेट, शतक और "
      "विकेट जैसी हर जानकारी सरल हिंदी में मौजूद है।",
      "विराट कोहली, सचिन तेंदुलकर, रोहित शर्मा, एमएस धोनी और जसप्रीत बुमराह जैसे "
      "दिग्गजों से लेकर उभरते सितारों तक — हर खिलाड़ी के प्रारूप-वार आँकड़े देखें। "
      "इसके अलावा सर्वकालिक रिकॉर्ड, टीम रिकॉर्ड, दो खिलाड़ियों की हेड-टू-हेड तुलना, "
      "आईपीएल के हर सीज़न का ब्योरा और फ़ाइनल मुक़ाबलों के पूरे स्कोरकार्ड भी यहाँ "
      "उपलब्ध हैं। हमारा लक्ष्य है क्रिकेट के समृद्ध आँकड़ों को हिंदी में हर प्रशंसक तक पहुँचाना।",
    ], heading='हिंदी में क्रिकेट सांख्यिकी')}</div>
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
    {C.player_intro_html(p, hn)}
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
    {C.format_intro_html(fkey)}
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
    {C.team_intro_html(t)}
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
    {C.ipl_season_intro_html(s)}
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
def build_compare(full, index, grouped):
    """Render the compare index (grouped by rivalry category) + one H2H page each."""
    depth = 1
    seen = set()
    flat = []
    sections = ""
    total = 0
    for title, pairs in grouped:
        cards = ""
        cnt = 0
        for a, b in pairs:
            pa, pb = full.get(a), full.get(b)
            if not pa or not pb:
                continue
            key = tuple(sorted([a, b]))
            if key in seen:        # skip duplicates / reversed pairs across categories
                continue
            seen.add(key)
            flat.append((a, b))
            cnt += 1
            cards += (f'<a href="{slug(pa["name"])}-vs-{slug(pb["name"])}/" '
                      f'class="block bg-cr-card border border-cr-border rounded-xl p-4 hover:border-cr-green hover:shadow-md transition">'
                      f'<div class="flex items-center justify-between gap-2">'
                      f'<span class="font-heading font-bold text-cr-ink truncate">{esc(pa["name"])}</span>'
                      f'<span class="hi text-cr-green font-bold text-sm shrink-0">बनाम</span>'
                      f'<span class="font-heading font-bold text-cr-ink truncate text-right">{esc(pb["name"])}</span>'
                      f'</div></a>')
        if cards:
            total += cnt
            sections += (f'<div class="mb-8"><h2 class="hi font-heading font-bold text-lg sm:text-xl '
                         f'text-cr-ink mb-3 flex items-center gap-2"><span class="w-1.5 h-6 rounded '
                         f'pitch-stripe inline-block"></span>{title} '
                         f'<span class="text-cr-text text-sm font-normal tnum">({cnt})</span></h2>'
                         f'<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">{cards}</div></div>')
    body = f"""{section_title('खिलाड़ी तुलना (हेड-टू-हेड)', f'{total} चर्चित मुक़ाबले — दो खिलाड़ियों के करियर आँकड़ों की आमने-सामने तुलना')}
      {sections}"""
    desc = ("क्रिकेट खिलाड़ियों की हेड-टू-हेड तुलना हिंदी में — कोहली बनाम बाबर, सचिन बनाम पोंटिंग, "
            f"बुमराह बनाम स्टार्क जैसे {total}+ मुक़ाबले। रन, औसत, स्ट्राइक रेट, विकेट और करियर आँकड़ों की आमने-सामने तुलना।")[:300]
    write("compare/index.html", page("खिलाड़ी तुलना — हेड-टू-हेड आँकड़े | क्रिकेट आँकड़े",
                                      desc, "/compare/", depth, body, active="compare",
                                      trail=[("होम", "../"), (T['compare'], None)]), "0.8")
    search_rows.append(["खिलाड़ी तुलना", "/compare/", "पेज", "compare h2h head to head tulna rivalry"])

    for a, b in flat:
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
    {C.h2h_intro_html(pa, pb)}
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
# Hindi ordinals for Test innings ("पहली पारी" etc.)
_INN_ORD = {1: "पहली", 2: "दूसरी", 3: "तीसरी", 4: "चौथी"}
# extras abbreviations
_EXTRA_HI = [("byes", "बा"), ("legbyes", "लेबा"), ("wides", "वा"),
             ("noballs", "नो"), ("penalty", "पे")]
# module-level link context populated by build_scorecards()
_SC_PIDS = set()
_SC_TEAMSLUGS = set()


def _sc_plink(name, registry, depth):
    """Link a player by name to their profile when one exists, else plain name."""
    pid = registry.get(name)
    hn = hindi_name(name)
    sub = f' <span class="hi text-cr-text text-xs">{hn}</span>' if hn else ""
    if pid and pid in _SC_PIDS:
        return (f'<a href="{"../"*depth}players/{pid}/" '
                f'class="font-medium text-cr-ink hover:text-cr-green">{esc(name)}</a>{sub}')
    return f'<span class="font-medium text-cr-ink">{esc(name)}</span>{sub}'


def _sc_tlink(name, depth):
    if slug(name) in _SC_TEAMSLUGS:
        return (f'<a href="{"../"*depth}teams/{slug(name)}/" '
                f'class="text-cr-ink hover:text-cr-green hi font-medium">{esc(C.team_hi(name))}</a>')
    return f'<span class="text-cr-ink hi font-medium">{esc(C.team_hi(name))}</span>'


def _sc_date_hi(iso):
    """`5 अप्रैल 2017` from an ISO date string."""
    try:
        y, mo, da = (int(x) for x in iso.split("-")[:3])
        return f"{da} {MONTHS_HI[mo]} {y}"
    except (ValueError, IndexError):
        return iso


def _sc_innings_block(inn, registry, multi, depth):
    """Render one innings: header, batting, extras/total, FoW, bowling."""
    team = inn["team"]
    label = esc(C.team_hi(team))
    if inn.get("super_over"):
        label += ' <span class="text-sm font-normal opacity-90">(सुपर ओवर)</span>'
    elif multi:
        label += (f' <span class="text-sm font-normal opacity-90">'
                  f'({_INN_ORD.get(inn["inn_no"], inn["inn_no"])} पारी)</span>')

    batrows = []
    for b in inn["batsmen"]:
        how = ('<span class="text-cr-green">नाबाद</span>' if not b["out"]
               else esc(b["how"]))
        name = (_sc_plink(b["name"], registry, depth) +
                f'<div class="text-xs text-cr-text hi mt-0.5">{how}</div>')
        batrows.append([name, b["r"], b["b"], b["4s"], b["6s"], f'{b["sr"]:g}'])

    ex = inn["extras"]
    ex_detail = ", ".join(f"{lab} {ex[k]}" for k, lab in _EXTRA_HI if ex.get(k))
    ex_line = (f'<div class="flex justify-between px-3 py-2 text-sm border-t border-cr-border">'
               f'<span class="hi text-cr-text">अतिरिक्त</span>'
               f'<span class="tnum font-medium">{inn["extras_total"]}'
               f'{f" <span class=\'text-cr-text text-xs\'>({ex_detail})</span>" if ex_detail else ""}</span></div>')
    total_line = (f'<div class="flex justify-between px-3 py-2 text-sm border-t border-cr-border bg-cr-bg">'
                  f'<span class="hi font-bold text-cr-ink">कुल</span>'
                  f'<span class="tnum font-bold text-cr-ink">{inn["runs"]}/{inn["wkts"]} '
                  f'<span class="font-normal text-cr-text">({inn["overs"]} ओवर)</span></span></div>')

    dnb = ""
    if inn["did_not_bat"]:
        names = ", ".join(_sc_plink(n, registry, depth) for n in inn["did_not_bat"])
        dnb = (f'<div class="px-3 py-2 text-sm border-t border-cr-border">'
               f'<span class="hi text-cr-text">बल्लेबाज़ी नहीं की: </span>{names}</div>')

    fow = ""
    if inn["fow"]:
        parts = ", ".join(
            f'<span class="whitespace-nowrap"><b class="tnum">{w["n"]}-{w["score"]}</b> '
            f'<span class="text-cr-text text-xs">({esc(w["player"])}, {w["over"]})</span></span>'
            for w in inn["fow"])
        fow = (f'<div class="px-3 py-2 text-sm border-t border-cr-border">'
               f'<span class="hi text-cr-text">विकेट पतन: </span>{parts}</div>')

    bowlrows = [[_sc_plink(b["name"], registry, depth), b["overs"], b["m"],
                 b["r"], b["w"], f'{b["econ"]:g}'] for b in inn["bowlers"]]

    bat_table = table(['बल्लेबाज़', T['runs'], T['balls'], '4s', '6s', 'SR'],
                      batrows, align_right={1, 2, 3, 4, 5})
    # splice extras/total/dnb/fow into the batting card (before closing div)
    bat_table = bat_table.replace("</tbody></table></div>",
                                  "</tbody></table>" + ex_line + total_line +
                                  dnb + fow + "</div>")
    bowl_table = table(['गेंदबाज़', 'ओवर', 'मे.', T['runs'], 'वि.', 'इको'],
                       bowlrows, align_right={1, 2, 3, 4, 5})
    return f"""<div class="mb-6">
      <div class="flex items-center justify-between bg-cr-green text-white rounded-t-xl px-4 py-2.5">
        <span class="hi font-heading font-bold">{label}</span>
        <span class="tnum font-bold">{inn["runs"]}/{inn["wkts"]} <span class="text-sm font-normal opacity-90">({inn["overs"]} ओवर)</span></span></div>
      {bat_table}
      <div class="mt-2">{bowl_table}</div>
    </div>"""


def _sc_result_line(m):
    """Hindi one-line result string with the winner in Devanagari."""
    if m["winner"]:
        return f'{C.team_hi(m["winner"])} {m["result"]}'
    return m["result"]


def build_scorecard_page(m):
    """Render a single match scorecard at /matches/<id>/."""
    depth = 2
    fkey = m["fmt"]
    flabel, fslug = FMT[fkey]
    registry = m["registry"]
    teams = m["teams"]
    title_teams = " बनाम ".join(C.team_hi(t) for t in teams)

    # context line under the title (format · event · stage)
    ctx = [flabel]
    if m["event"] and m["event"].lower() not in ("",):
        ctx.append(esc(m["event"]))
    if m["stage"]:
        ctx.append(esc(m["stage"]))
    elif m["match_number"]:
        ctx.append(f'मैच {m["match_number"]}')
    ctx_line = " · ".join(ctx)

    result_html = ""
    if _sc_result_line(m):
        result_html = (f'<div class="hi text-lg font-bold mt-2 flex items-center gap-2">'
                       f'{icon("trophy","w-5 h-5")}<span>{esc(_sc_result_line(m))}</span></div>')
    toss_html = ""
    if m["toss_winner"]:
        dec = {"bat": "पहले बल्लेबाज़ी", "field": "पहले गेंदबाज़ी"}.get(
            m["toss_decision"], m["toss_decision"])
        toss_html = (f'<div class="hi text-sm mt-1 opacity-90">टॉस: '
                     f'{esc(C.team_hi(m["toss_winner"]))} — {dec} चुनी</div>')
    pom_html = ""
    if m["pom"]:
        pom_links = ", ".join(_sc_plink(n, registry, depth) for n in m["pom"])
        pom_html = (f'<div class="hi text-sm mt-2 opacity-90">प्लेयर ऑफ़ द मैच: '
                    f'<b class="text-white">{pom_links}</b></div>')
    venue_bits = " · ".join(x for x in (esc(m["venue"]), esc(m["city"])) if x)

    innings_html = "".join(
        _sc_innings_block(inn, registry, m["multi_innings"], depth)
        for inn in m["innings"])

    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 mb-6">
      <div class="hi text-sm opacity-90">{ctx_line}</div>
      <h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">{esc(title_teams)}</h1>
      <div class="hi mt-2 opacity-90">{venue_bits}{f" · {_sc_date_hi(m['date'])}" if venue_bits else _sc_date_hi(m['date'])}</div>
      {result_html}{toss_html}{pom_html}
    </div>
    {innings_html}
    <div class="mt-4 flex flex-wrap gap-4">
      <a href="../{fslug}/{m['year']}/" class="hi text-cr-green font-semibold hover:underline">← {flabel} {m['year']} मैच</a>
      <a href="../" class="hi text-cr-green font-semibold hover:underline">सभी स्कोरकार्ड</a>
    </div>
    """
    title = f"{title_teams} स्कोरकार्ड — {flabel} {m['year']} | क्रिकेट आँकड़े"
    desc = (f"{title_teams} {flabel} स्कोरकार्ड हिंदी में ({_sc_date_hi(m['date'])})। "
            f"{_sc_result_line(m)}। पूरा बल्लेबाज़ी, गेंदबाज़ी विवरण व विकेट पतन।")[:300]
    ld = {"@context": "https://schema.org", "@type": "SportsEvent",
          "name": f"{' v '.join(teams)} — {m['event'] or fkey} {m['year']}",
          "startDate": m["date"], "sport": "Cricket",
          "location": {"@type": "Place", "name": m["venue"] or m["city"]},
          "competitor": [{"@type": "SportsTeam", "name": t} for t in teams]}
    write(f"matches/{m['id']}/index.html",
          page(title, desc, f"/matches/{m['id']}/", depth, body, active="matches",
               trail=[("होम", "../../"), (T['matches'], "../"),
                      (flabel, f"../{fslug}/"), (f"{m['year']}", f"../{fslug}/{m['year']}/"),
                      (title_teams, None)],
               jsonld=ld, og_type="article"), "0.5")


def _sc_match_row(m, depth):
    """One row for a year index: date, teams (linked to scorecard), result."""
    label = (f'<a href="{"../"*depth}matches/{m["id"]}/" '
             f'class="hi font-medium text-cr-ink hover:text-cr-green">'
             f'{esc(" बनाम ".join(C.team_hi(t) for t in m["teams"]))}</a>')
    stage = ""
    if m["stage"]:
        stage = f' <span class="hi text-cr-text text-xs">({esc(m["stage"])})</span>'
    res = _sc_result_line(m)
    return [f'<span class="hi text-cr-text text-sm whitespace-nowrap">{_sc_date_hi(m["date"])}</span>',
            label + stage,
            f'<span class="hi text-cr-green text-sm">{esc(res)}</span>']


def build_scorecards(index, teams_d):
    """Full per-match scorecards + the /matches/ browse hierarchy.

    Streams every men's match through scorecards.parse_match, writes one page
    per match and accumulates light metadata for the format/year index pages.
    """
    global _SC_PIDS, _SC_TEAMSLUGS
    _SC_PIDS = {p["id"] for p in index[:N_PLAYERS]}
    _SC_TEAMSLUGS = {slug(t) for t in teams_d.keys()}

    # fmt -> year -> list of light meta dicts (kept for index pages)
    buckets = {fk: {} for fk in FMT}
    counts = {fk: 0 for fk in FMT}
    n = 0
    for m in SC.iter_matches():
        build_scorecard_page(m)
        n += 1
        counts[m["fmt"]] += 1
        light = {k: m[k] for k in ("id", "fmt", "date", "year", "teams",
                                   "event", "stage", "winner", "result")}
        buckets[m["fmt"]].setdefault(m["year"], []).append(light)
        if n % 1500 == 0:
            print(f"  … {n} scorecards rendered")
    print(f"  rendered {n} match scorecards")

    # ---- per-year index pages ----
    for fkey in FMT:
        flabel, fslug = FMT[fkey]
        for year, ms in buckets[fkey].items():
            _build_scorecard_year(fkey, flabel, fslug, year, ms)
        _build_scorecard_format(fkey, flabel, fslug, buckets[fkey], counts[fkey])

    # ---- hub /matches/ ----
    _build_scorecard_hub(counts, buckets)


def _build_scorecard_year(fkey, flabel, fslug, year, ms):
    depth = 3
    ms = sorted(ms, key=lambda x: x["date"])
    # group by event/series, keeping first-appearance order
    groups = {}
    for m in ms:
        key = m["event"] or "द्विपक्षीय शृंखला"
        groups.setdefault(key, []).append(m)
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-7 mb-6">
      <div class="flex items-center gap-3 mb-1">{fmt_badge(fkey)}
        <span class="hi text-sm opacity-90 tnum">{len(ms)} मैच</span></div>
      <h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">{flabel} {year} — स्कोरकार्ड</h1>
      <p class="hi mt-2 opacity-90">{year} में खेले गए {flabel} मैचों के पूरे स्कोरकार्ड — बल्लेबाज़ी, गेंदबाज़ी व विकेट पतन।</p>
    </div>
    """
    for gname, gms in groups.items():
        rows = [_sc_match_row(m, depth) for m in gms]
        body += section_title(esc(gname), f"{len(gms)} मैच")
        body += table(['तिथि', 'मैच', 'परिणाम'], rows)
        body += '<div class="mb-6"></div>'
    body += (f'<div class="mt-2"><a href="../" class="hi text-cr-green font-semibold '
             f'hover:underline">← सभी {flabel} सीज़न</a></div>')
    title = f"{flabel} {year} स्कोरकार्ड — सभी मैच | क्रिकेट आँकड़े"
    desc = (f"{flabel} {year} के सभी {len(ms)} मैचों के स्कोरकार्ड हिंदी में — "
            f"पूरा बल्लेबाज़ी व गेंदबाज़ी विवरण, विकेट पतन और परिणाम।")
    write(f"matches/{fslug}/{year}/index.html",
          page(title, desc, f"/matches/{fslug}/{year}/", depth, body, active="matches",
               trail=[("होम", "../../../"), (T['matches'], "../../"),
                      (flabel, "../"), (f"{year}", None)]), "0.5")
    search_rows.append([f"{flabel} {year} स्कोरकार्ड", f"/matches/{fslug}/{year}/",
                        "स्कोरकार्ड", f"{fkey} {year} matches scorecard".lower()])


def _build_scorecard_format(fkey, flabel, fslug, year_map, total):
    depth = 2
    years = sorted(year_map.keys(), reverse=True)
    cards = ""
    for y in years:
        cards += (f'<a href="{y}/" class="bg-cr-card border border-cr-border rounded-xl '
                  f'px-4 py-3 text-center hover:border-cr-green hover:shadow-md transition">'
                  f'<div class="font-heading font-extrabold text-lg text-cr-ink tnum">{y}</div>'
                  f'<div class="hi text-xs text-cr-text tnum">{len(year_map[y])} मैच</div></a>')
    span = f"{years[-1]}–{years[0]}" if len(years) > 1 else (years[0] if years else "")
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="flex items-center gap-3 mb-1">{fmt_badge(fkey)}
        <span class="hi text-sm opacity-90 tnum">{total} मैच · {span}</span></div>
      <h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">{flabel} स्कोरकार्ड</h1>
      <p class="hi mt-2 opacity-90">{FMT_DESC[fkey]} नीचे सीज़न चुनें और हर मैच का पूरा स्कोरकार्ड देखें।</p>
    </div>
    {section_title('सीज़न के अनुसार', 'किसी भी वर्ष के सभी मैच देखें')}
    <div class="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-6 gap-3">{cards}</div>
    <div class="mt-6"><a href="../" class="hi text-cr-green font-semibold hover:underline">← सभी प्रारूप</a></div>
    """
    title = f"{flabel} स्कोरकार्ड — सभी सीज़न व मैच | क्रिकेट आँकड़े"
    desc = (f"{flabel} के {total} मैचों के स्कोरकार्ड हिंदी में — सीज़न के अनुसार ब्राउज़ करें, "
            f"हर मैच का पूरा बल्लेबाज़ी व गेंदबाज़ी विवरण।")
    write(f"matches/{fslug}/index.html",
          page(title, desc, f"/matches/{fslug}/", depth, body, active="matches",
               trail=[("होम", "../../"), (T['matches'], "../"), (flabel, None)]), "0.6")
    search_rows.append([f"{flabel} स्कोरकार्ड", f"/matches/{fslug}/", "स्कोरकार्ड",
                        f"{fkey} matches scorecard season".lower()])


def _build_scorecard_hub(counts, buckets):
    depth = 1
    total = sum(counts.values())
    cards = ""
    for fkey in FMT:
        flabel, fslug = FMT[fkey]
        years = sorted(buckets[fkey].keys())
        span = f"{years[0]}–{years[-1]}" if len(years) > 1 else (years[0] if years else "")
        cards += f"""<a href="{fslug}/" class="group bg-cr-card border border-cr-border rounded-2xl p-6 hover:border-cr-green hover:shadow-md transition">
          <div class="flex items-center justify-between mb-2">{fmt_badge(fkey)}
            <span class="hi text-xs text-cr-text tnum">{span}</span></div>
          <h2 class="hi font-heading font-extrabold text-xl text-cr-ink group-hover:text-cr-green">{flabel}</h2>
          <div class="hi text-sm text-cr-text mt-1 tnum">{counts[fkey]:,} मैच स्कोरकार्ड</div></a>"""
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">मैच स्कोरकार्ड</h1>
      <p class="hi opacity-90 max-w-2xl mt-2">टेस्ट, वनडे, टी20आई और आईपीएल के <b class="tnum">{total:,}</b> मैचों के पूरे स्कोरकार्ड हिंदी में — हर पारी की बल्लेबाज़ी (रन, गेंद, चौके-छक्के, स्ट्राइक रेट), गेंदबाज़ी (ओवर, मेडन, रन, विकेट, इकॉनमी), विकेट पतन, टॉस और परिणाम।</p>
    </div>
    {section_title('प्रारूप चुनें', 'प्रारूप → सीज़न → मैच')}
    <div class="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">{cards}</div>
    """
    desc = (f"मैच स्कोरकार्ड हिंदी में — टेस्ट, वनडे, टी20आई व आईपीएल के {total:,} मैचों का पूरा "
            f"बल्लेबाज़ी, गेंदबाज़ी विवरण, विकेट पतन, टॉस व परिणाम।")
    write("matches/index.html",
          page("मैच स्कोरकार्ड — टेस्ट, वनडे, टी20आई, आईपीएल | क्रिकेट आँकड़े",
               desc, "/matches/", depth, body, active="matches",
               trail=[("होम", "../"), (T['matches'], None)]), "0.8")
    search_rows.append(["मैच स्कोरकार्ड", "/matches/", "पेज",
                        "matches scorecard batting bowling fall of wickets test odi t20i ipl"])


# ====================================================== ICC TOURNAMENTS ======
# Module-level sets populated by build_tournaments() so the small link helpers
# below can decide whether a player/team has a generated page to link to.
_TOUR_PIDS = set()
_TOUR_TEAMS = set()
_TOUR_NAME2ID = {}


def plink_safe(pid, name, depth):
    """Link to a player page if it exists, else show the (Hindi-annotated) name."""
    pid = pid or _TOUR_NAME2ID.get(name)
    if pid and pid in _TOUR_PIDS:
        return plink(pid, name, depth)
    hn = hindi_name(name)
    sub = f' <span class="hi text-cr-text text-xs">{hn}</span>' if hn else ""
    return f'<span class="font-medium text-cr-ink">{esc(name)}</span>{sub}'


def team_link_safe(name, depth):
    """Link to a team page if it exists, else show the Hindi team name."""
    if name in _TOUR_TEAMS:
        return (f'<a href="{"../"*depth}teams/{slug(name)}/" '
                f'class="text-cr-ink hover:text-cr-green hi font-medium">{esc(C.team_hi(name))}</a>')
    return f'<span class="hi font-medium text-cr-ink">{esc(C.team_hi(name))}</span>'


def tour_result(m):
    """Hindi result string for a match (winner in Devanagari)."""
    oc = m["outcome"]
    suf = " (डी/एल)" if oc.get("method") == "D/L" else ""
    if oc.get("result") == "tie":
        elim = oc.get("eliminator")
        return (f'{C.team_hi(elim)} सुपर ओवर में विजयी' if elim else "मैच टाई")
    if oc.get("result") == "no result":
        return "कोई परिणाम नहीं"
    w = m["winner"]
    if not w:
        return "—"
    by = oc.get("by", {})
    if "runs" in by:
        return f"{C.team_hi(w)} {by['runs']} रन से विजयी{suf}"
    if "wickets" in by:
        return f"{C.team_hi(w)} {by['wickets']} विकेट से विजयी{suf}"
    return f"{C.team_hi(w)} विजयी{suf}"


def _inn_score(m, team):
    for inn in m["innings"]:
        if inn["team"] == team:
            return f'{inn["runs"]}/{inn["wkts"]} <span class="text-cr-text text-xs">({inn["overs"]})</span>'
    return "—"


def scorecard_innings_html(d, depth):
    """Render full batting + bowling tables for every innings of a raw match.

    Player names are linked to their profile when one exists (via the match
    registry). Mirrors the delivery accounting used in build_scorecard().
    """
    reg = d["info"].get("registry", {}).get("people", {})
    out = ""
    for inn in d.get("innings", []):
        team = inn.get("team", "")
        bat = {}
        bowl = {}
        order = []
        total = wkts = legal = 0
        for ov in inn.get("overs", []):
            for de in ov.get("deliveries", []):
                ex = de.get("extras", {})
                wide = "wides" in ex
                nb = "noballs" in ex
                bye = ex.get("byes", 0) + ex.get("legbyes", 0)
                rb = de["runs"]
                total += rb.get("total", 0)
                bt = de.get("batter")
                if bt not in bat:
                    bat[bt] = [0, 0, 0, 0, False]
                    order.append(bt)
                bat[bt][0] += rb.get("batter", 0)
                if not wide:
                    bat[bt][1] += 1
                if rb.get("batter") == 4:
                    bat[bt][2] += 1
                elif rb.get("batter") == 6:
                    bat[bt][3] += 1
                bw = de.get("bowler")
                bowl.setdefault(bw, [0, 0, 0])
                if not (wide or nb):
                    bowl[bw][0] += 1
                    legal += 1
                bowl[bw][1] += rb.get("total", 0) - bye - ex.get("penalty", 0)
                for w in de.get("wickets", []):
                    wkts += 1
                    po = w.get("player_out")
                    if po in bat:
                        bat[po][4] = True
                    if w.get("kind") in TT.WICKET_TO_BOWLER:
                        bowl[bw][2] += 1
        batrows = []
        for b in order:
            r = bat[b]
            sr = round(r[0] / r[1] * 100, 1) if r[1] else 0
            status = '<span class="text-cr-text text-xs hi">नाबाद</span>' if not r[4] else ""
            batrows.append([f'{plink_safe(reg.get(b), b, depth)} {status}',
                            r[0], r[1], r[2], r[3], f'{sr}'])
        bowlrows = []
        for b, r in bowl.items():
            ov_str = f"{r[0] // 6}.{r[0] % 6}"
            econ = round(r[1] / (r[0] / 6), 2) if r[0] else 0
            bowlrows.append([plink_safe(reg.get(b), b, depth), ov_str, r[1], r[2], f'{econ}'])
        ov_total = f"{legal // 6}.{legal % 6}"
        out += f"""<div class="mb-6">
          <div class="flex items-center justify-between bg-cr-green text-white rounded-t-xl px-4 py-2.5">
            <span class="hi font-heading font-bold">{esc(C.team_hi(team))}</span>
            <span class="tnum font-bold">{total}/{wkts} <span class="text-sm font-normal opacity-90">({ov_total} ओवर)</span></span></div>
          {table(['बल्लेबाज़', T['runs'], T['balls'], '4s', '6s', T['sr']], batrows, align_right={1, 2, 3, 4, 5})}
          <div class="mt-2">{table(['गेंदबाज़', 'ओवर', T['runs'], T['wkts'], 'इको'], bowlrows, align_right={1, 2, 3, 4})}</div>
        </div>"""
    return out


def _tour_match_label(m, depth):
    """`Team बनाम Team` with both teams linked."""
    ts = m["teams"]
    if len(ts) != 2:
        return " बनाम ".join(C.team_hi(x) for x in ts)
    return (team_link_safe(ts[0], depth) +
            ' <span class="hi text-cr-text text-xs">बनाम</span> ' +
            team_link_safe(ts[1], depth))


def build_tournaments(data, valid_ids, valid_teams, name2id):
    global _TOUR_PIDS, _TOUR_TEAMS, _TOUR_NAME2ID
    _TOUR_PIDS = valid_ids
    _TOUR_TEAMS = valid_teams
    _TOUR_NAME2ID = name2id

    # ---- hub: /tournaments/ ----
    depth = 1
    cards = ""
    for t in data:
        eds = t["editions"]
        years = [e["year"] for e in eds]
        span = f"{years[0]}–{years[-1]}" if len(years) > 1 else (years[0] if years else "")
        latest = eds[-1] if eds else None
        champ = (f'<div class="hi text-sm text-cr-text mt-1">नवीनतम चैंपियन: '
                 f'<b class="text-cr-ink">{esc(C.team_hi(latest["champion"]))}</b> ({latest["year"]})</div>'
                 if latest and latest.get("champion") else "")
        cards += f"""<a href="{t['key']}/" class="group bg-cr-card border border-cr-border rounded-2xl p-6 hover:border-cr-green hover:shadow-md transition">
          <div class="flex items-center gap-3 mb-2">{fmt_badge(t['fmt'])}
            <span class="hi text-xs text-cr-text tnum">{len(eds)} संस्करण · {span}</span></div>
          <h2 class="hi font-heading font-extrabold text-xl text-cr-ink group-hover:text-cr-green flex items-center gap-2">{icon('trophy','w-5 h-5')}{t['title']}</h2>
          {champ}</a>"""
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="flex items-center gap-3 mb-2">{icon('trophy','w-7 h-7')}<h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">आईसीसी टूर्नामेंट</h1></div>
      <p class="hi opacity-90 max-w-2xl">क्रिकेट विश्व कप, टी20 विश्व कप और चैंपियंस ट्रॉफ़ी के सभी संस्करण — चैंपियन, फ़ाइनल स्कोरकार्ड, सर्वाधिक रन व विकेट और प्लेयर ऑफ़ द टूर्नामेंट, सब कुछ हिंदी में।</p>
    </div>
    <div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">{cards}</div>
    """
    desc = ("आईसीसी टूर्नामेंट आँकड़े हिंदी में — क्रिकेट विश्व कप (वनडे), टी20 विश्व कप और "
            "चैंपियंस ट्रॉफ़ी के सभी संस्करण, चैंपियन, फ़ाइनल स्कोरकार्ड व शीर्ष प्रदर्शनकर्ता।")
    write("tournaments/index.html",
          page("आईसीसी टूर्नामेंट — विश्व कप, टी20 विश्व कप, चैंपियंस ट्रॉफ़ी | क्रिकेट आँकड़े",
               desc, "/tournaments/", depth, body, active="tournaments",
               trail=[("होम", "../"), ("टूर्नामेंट", None)]), "0.9")
    search_rows.append(["आईसीसी टूर्नामेंट", "/tournaments/", "पेज",
                        "tournaments world cup t20 champions trophy icc tournament"])

    for t in data:
        build_tournament_index(t)


def build_tournament_index(t):
    depth = 2
    key = t["key"]
    rows = []
    for ed in reversed(t["editions"]):
        tr = ed["top_runs"][0] if ed["top_runs"] else None
        tw = ed["top_wkts"][0] if ed["top_wkts"] else None
        rows.append([
            f'<a href="{ed["year"]}/" class="font-bold text-cr-ink hover:text-cr-green tnum">{ed["year"]}</a>',
            f'<span class="hi">{esc(ed["host"])}</span>',
            f'<span class="hi font-semibold text-cr-green">{esc(C.team_hi(ed["champion"])) if ed["champion"] else "—"}</span>',
            (plink_safe(tr["pid"], tr["name"], depth) +
             f' <span class="text-cr-text text-xs tnum">({tr["runs"]})</span>') if tr else "—",
            (plink_safe(tw["pid"], tw["name"], depth) +
             f' <span class="text-cr-text text-xs tnum">({tw["wkts"]})</span>') if tw else "—",
        ])
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="flex items-center gap-3 mb-2">{fmt_badge(t['fmt'])}<h1 class="hi font-heading font-extrabold text-2xl sm:text-3xl">{t['title']}</h1></div>
      <p class="hi opacity-90 max-w-2xl">{t['intro']}</p>
    </div>
    {section_title('सभी संस्करण', 'किसी भी वर्ष पर क्लिक करके पूरा विवरण देखें')}
    {table(['वर्ष', 'मेज़बान', T['champion'], 'सर्वाधिक रन', 'सर्वाधिक विकेट'], rows)}
    <p class="hi text-xs text-cr-text mt-3">शीर्ष रन व विकेट उपलब्ध मैच डेटा (Cricsheet) के आधार पर।</p>
    """
    write(f"tournaments/{key}/index.html",
          page(f"{t['title']} — सभी संस्करण व चैंपियन | क्रिकेट आँकड़े",
               t["desc"], f"/tournaments/{key}/", depth, body, active="tournaments",
               trail=[("होम", "../../"), ("टूर्नामेंट", "../"), (t["short"], None)]), "0.8")
    search_rows.append([t["title"], f"/tournaments/{key}/", "टूर्नामेंट",
                        f"{t['key'].replace('-', ' ')} {t['short']} icc champion"])

    eds = t["editions"]
    for i, ed in enumerate(eds):
        prev_ed = eds[i - 1] if i > 0 else None
        next_ed = eds[i + 1] if i < len(eds) - 1 else None
        build_tournament_edition(t, ed, prev_ed, next_ed)


def build_tournament_edition(t, ed, prev_ed, next_ed):
    depth = 3
    key = t["key"]
    year = ed["year"]
    up = "../../../"

    # ---- hero + key facts ----
    champ_hi = C.team_hi(ed["champion"]) if ed["champion"] else None
    runner_hi = C.team_hi(ed["runner"]) if ed["runner"] else None
    pot = ed.get("pot")
    pot_html = plink_safe(name2id_lookup(pot), pot, depth) if pot else None

    facts = ""
    if champ_hi:
        facts += stat("चैंपियन", esc(champ_hi))
    if runner_hi:
        facts += stat("उपविजेता", esc(runner_hi))
    facts += stat("मेज़बान", f'<span class="hi text-base">{esc(ed["host"])}</span>')
    if pot:
        facts += (f'<div class="bg-cr-card border border-cr-border rounded-xl px-4 py-3">'
                  f'<div class="text-base font-heading font-bold text-cr-ink">{pot_html}</div>'
                  f'<div class="text-xs font-semibold text-cr-green hi uppercase tracking-wide">प्लेयर ऑफ़ द टूर्नामेंट</div></div>')

    hero = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="hi text-sm font-semibold opacity-90">{t['title']}</div>
      <h1 class="hi font-heading font-extrabold text-3xl sm:text-4xl">{t['short']} {year}</h1>
      <div class="hi mt-2 opacity-90">मेज़बान: {esc(ed['host'])}</div>
      {f'<div class="hi text-xl mt-3 flex items-center gap-2">{icon("trophy","w-6 h-6")}<span>चैंपियन: <b>{esc(champ_hi)}</b></span></div>' if champ_hi else ''}
    </div>"""

    intro = C.prose(ed["story"], heading="टूर्नामेंट की कहानी")
    facts_grid = f'<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">{facts}</div>'

    # ---- knockout cards ----
    ko_html = ""
    if ed["knockouts"]:
        cards = ""
        for m in ed["knockouts"]:
            label = TT.KNOCKOUT[m["stage"]][0]
            is_final = m["stage"] == "Final"
            ts = m["teams"]
            score_rows = ""
            for tm in ts:
                score_rows += (f'<div class="flex items-center justify-between gap-3 py-0.5">'
                               f'<span>{team_link_safe(tm, depth)}</span>'
                               f'<span class="tnum text-cr-ink font-semibold">{_inn_score(m, tm)}</span></div>')
            pom = ", ".join(m["pom"])
            loc = " · ".join(x for x in [m.get("city") or m.get("venue"), m.get("date")] if x)
            border = "border-cr-green ring-1 ring-cr-green/30" if is_final else "border-cr-border"
            cards += f"""<div class="bg-cr-card border {border} rounded-xl p-4">
              <div class="flex items-center gap-2 mb-2">{icon('trophy','w-4 h-4') if is_final else ''}<span class="hi text-xs font-bold uppercase tracking-wide text-cr-green">{label}</span></div>
              <div class="hi text-sm">{score_rows}</div>
              <div class="hi text-sm font-semibold text-cr-ink mt-2">{tour_result(m)}</div>
              {f'<div class="hi text-xs text-cr-text mt-1">{esc(loc)}</div>' if loc else ''}
              {f'<div class="hi text-xs text-cr-text mt-0.5">प्लेयर ऑफ़ द मैच: {plink_safe(None, pom, depth)}</div>' if pom else ''}
            </div>"""
        ko_html = (section_title('नॉकआउट चरण', 'क्वार्टर फ़ाइनल, सेमीफ़ाइनल और फ़ाइनल के नतीजे') +
                   f'<div class="grid sm:grid-cols-2 gap-3 mb-8">{cards}</div>')

    # ---- final scorecard (inline) ----
    final_html = ""
    if ed["final_raw"]:
        final_html = (section_title('फ़ाइनल — पूरा स्कोरकार्ड',
                                    'बल्लेबाज़ी व गेंदबाज़ी का विस्तृत विवरण') +
                      scorecard_innings_html(ed["final_raw"], depth))

    # ---- top performers ----
    trows = []
    for i, p in enumerate(ed["top_runs"][:10], 1):
        hs = f'{p["hs"]}{"*" if p["hs_no"] else ""}'
        trows.append([i, plink_safe(p["pid"], p["name"], depth), p["runs"], p["inns"],
                      p["avg"] if p["avg"] is not None else "—", p["sr"], hs])
    wrows = []
    for i, p in enumerate(ed["top_wkts"][:10], 1):
        wrows.append([i, plink_safe(p["pid"], p["name"], depth), p["wkts"], p["inns"],
                      p["avg"] if p["avg"] is not None else "—", p["econ"], p["best"]])
    perf = ""
    if trows:
        perf += (section_title('सर्वाधिक रन', 'टूर्नामेंट के शीर्ष बल्लेबाज़ (उपलब्ध मैच डेटा)') +
                 table([T['rank'], T['player'], T['runs'], T['inn'], T['avg'], T['sr'], T['hs']],
                       trows, align_right={2, 3, 4, 5, 6}) + '<div class="mb-8"></div>')
    if wrows:
        perf += (section_title('सर्वाधिक विकेट', 'टूर्नामेंट के शीर्ष गेंदबाज़ (उपलब्ध मैच डेटा)') +
                 table([T['rank'], T['player'], T['wkts'], T['inn'], T['avg'], T['econ'], T['bbi']],
                       wrows, align_right={2, 3, 4, 5, 6}) + '<div class="mb-8"></div>')

    # ---- group-stage results ----
    grp_html = ""
    if ed["groups"]:
        grows = []
        for m in ed["groups"]:
            stg = m["stage"]
            stage_lbl = {"First Round": "पहला दौर", "Super 10": "सुपर 10",
                         "Super 8": "सुपर 8", "Super Sixes": "सुपर सिक्स"}.get(stg, "")
            grp = f'ग्रुप {m["group"]}' if m["group"] else (stage_lbl or "लीग")
            if stage_lbl and m["group"]:
                grp = f'{stage_lbl} · {m["group"]}'
            grows.append([f'<span class="hi text-xs text-cr-text">{grp}</span>',
                          _tour_match_label(m, depth),
                          f'<span class="hi text-sm">{tour_result(m)}</span>'])
        grp_html = (section_title('ग्रुप व लीग चरण के नतीजे',
                                  f'{len(ed["groups"])} मैच') +
                    table(['चरण', 'मैच', 'परिणाम'], grows))

    # ---- prev / next ----
    nav_links = '<div class="mt-8 flex items-center justify-between gap-3">'
    nav_links += (f'<a href="../{prev_ed["year"]}/" class="hi text-cr-green font-semibold hover:underline">← {t["short"]} {prev_ed["year"]}</a>'
                  if prev_ed else '<span></span>')
    nav_links += f'<a href="../" class="hi text-cr-text hover:text-cr-green">सभी संस्करण</a>'
    nav_links += (f'<a href="../{next_ed["year"]}/" class="hi text-cr-green font-semibold hover:underline">{t["short"]} {next_ed["year"]} →</a>'
                  if next_ed else '<span></span>')
    nav_links += '</div>'

    body = hero + intro + facts_grid + ko_html + final_html + perf + grp_html + nav_links

    champ_txt = f"चैंपियन {champ_hi}। " if champ_hi else ""
    desc = (f"{t['short']} {year} आँकड़े हिंदी में — मेज़बान {ed['host']}। {champ_txt}"
            f"नॉकआउट नतीजे, फ़ाइनल स्कोरकार्ड, सर्वाधिक रन व विकेट और शीर्ष प्रदर्शनकर्ता।")[:300]
    title = f"{t['short']} {year} — चैंपियन, फ़ाइनल व शीर्ष प्रदर्शन | क्रिकेट आँकड़े"
    jsonld = {"@context": "https://schema.org", "@type": "SportsEvent",
              "name": f"{t['title']} {year}", "sport": "Cricket",
              "url": f"{SITE}/tournaments/{key}/{year}/"}
    if champ_hi:
        jsonld["winner"] = {"@type": "SportsTeam", "name": ed["champion"]}
    write(f"tournaments/{key}/{year}/index.html",
          page(title, desc, f"/tournaments/{key}/{year}/", depth, body,
               active="tournaments",
               trail=[("होम", up), ("टूर्नामेंट", "../../"), (t["short"], "../"),
                      (year, None)], jsonld=jsonld), "0.7")
    search_rows.append([f"{t['short']} {year}", f"/tournaments/{key}/{year}/",
                        t["short"], f"{t['key'].replace('-', ' ')} {year} {ed['host']} "
                        f"{ed['champion'] or ''} final".lower()])


def name2id_lookup(name):
    return _TOUR_NAME2ID.get(name) if name else None


# ========================================================== STATIC CONTENT ===
def build_about():
    depth = 1
    body = C.about_body(section_title)
    desc = ("क्रिकेट आँकड़े (CricketStatsHindi.com) के बारे में जानें — हिंदी भाषी क्रिकेट "
            "प्रेमियों के लिए टेस्ट, वनडे, टी20आई और आईपीएल के विस्तृत आँकड़ों का मुफ़्त मंच।")
    write("about/index.html",
          page("हमारे बारे में — क्रिकेट आँकड़े | CricketStatsHindi",
               desc, "/about/", depth, body, active="",
               trail=[("होम", "../"), ("हमारे बारे में", None)]), "0.5")
    search_rows.append(["हमारे बारे में", "/about/", "पेज", "about hamare bare mein"])


def build_privacy():
    depth = 1
    body = C.privacy_body(section_title)
    desc = ("क्रिकेट आँकड़े (CricketStatsHindi.com) की गोपनीयता नीति — हम आपकी जानकारी "
            "को कैसे एकत्र, उपयोग और सुरक्षित करते हैं, इसकी पूरी जानकारी हिंदी में।")
    write("privacy/index.html",
          page("गोपनीयता नीति — क्रिकेट आँकड़े | CricketStatsHindi",
               desc, "/privacy/", depth, body, active="",
               trail=[("होम", "../"), ("गोपनीयता नीति", None)]), "0.4")
    search_rows.append(["गोपनीयता नीति", "/privacy/", "पेज", "privacy gopniyata niti policy"])


# ============================================================ STATIC ASSETS ==
def write_og_image():
    """Generate the 1200x630 Open Graph share image (og-image.png) with Pillow.

    Cricket-themed: dark maroon (#8B1A1A) background, a stitched cricket ball,
    and the English site name (kept Latin so Pillow needs no complex-script
    shaping). Referenced by every page's <meta property="og:image">.
    """
    from PIL import Image, ImageDraw, ImageFont, ImageFilter

    W, H = 1200, 630
    MAROON = (139, 26, 26)          # #8B1A1A
    MAROON_DARK = (74, 14, 14)      # #4A0E0E
    CREAM = (245, 230, 208)         # #F5E6D0 seam / accent
    GREEN = (34, 197, 94)           # #22c55e brand accent

    img = Image.new("RGB", (W, H), MAROON)
    draw = ImageDraw.Draw(img)

    # --- subtle vertical darkening towards the bottom for depth ---
    grad = Image.new("L", (1, H), 0)
    for y in range(H):
        grad.putpixel((0, y), int(70 * (y / H)))
    grad = grad.resize((W, H))
    img = Image.composite(Image.new("RGB", (W, H), MAROON_DARK), img, grad)
    draw = ImageDraw.Draw(img)

    # --- cricket ball on the right, drawn at 4x then downscaled (anti-alias) ---
    S = 4
    bd = 360 * S                       # ball diameter (hi-res)
    ball = Image.new("RGBA", (bd, bd), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(ball)
    BALL_RED = (124, 18, 18)
    bdraw.ellipse([0, 0, bd, bd], fill=BALL_RED + (255,))
    # glossy highlight, upper-left
    hl = Image.new("RGBA", (bd, bd), (0, 0, 0, 0))
    hd = ImageDraw.Draw(hl)
    hd.ellipse([bd * 0.14, bd * 0.10, bd * 0.62, bd * 0.58],
               fill=(190, 70, 70, 150))
    hl = hl.filter(ImageFilter.GaussianBlur(bd * 0.06))
    ball.alpha_composite(hl)
    # seam: an arc across the ball plus two rows of stitches
    cx = cy = bd // 2
    bdraw.arc([bd * 0.04, bd * 0.04, bd * 0.96, bd * 0.96],
              start=58, end=122, fill=CREAM + (255,), width=int(7 * S))
    import math
    for frac, off in ((0.5, -22 * S), (0.5, 22 * S)):
        for a in range(60, 121, 6):
            rad = math.radians(a)
            r = bd * 0.46
            x = cx + r * math.cos(rad)
            y = cy - r * math.sin(rad) + off
            bdraw.line([x - 9 * S, y, x + 9 * S, y], fill=CREAM + (255,),
                       width=int(3 * S))
    ball = ball.resize((360, 360), Image.LANCZOS)
    # soft drop shadow under the ball
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.ellipse([815, 320, 1165, 560], fill=(0, 0, 0, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    img.paste(Image.alpha_composite(
        img.convert("RGBA"), shadow).convert("RGB"), (0, 0))
    img.paste(ball, (812, 150), ball)
    draw = ImageDraw.Draw(img)

    def font(size, bold=True):
        for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf"
                  if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
                  "/Library/Fonts/Arial Bold.ttf",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()

    # green accent bar above the wordmark
    draw.rectangle([92, 150, 240, 162], fill=GREEN)
    # title (two lines) + tagline + domain
    draw.text((88, 188), "CRICKET", font=font(96), fill=(255, 255, 255))
    draw.text((88, 288), "STATS HINDI", font=font(96), fill=CREAM)
    draw.text((92, 415), "Cricket statistics in Hindi", font=font(42, False),
              fill=(235, 210, 210))
    draw.text((92, 540), "cricketstatshindi.com", font=font(36), fill=GREEN)

    img.save(OUT / "og-image.png", "PNG")


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
    # Open Graph share image (1200x630) for social / WhatsApp previews
    write_og_image()
    # search.js
    (OUT / "search.js").write_text(SEARCH_JS, encoding="utf-8")
    # search index
    (OUT / "search-index.json").write_text(
        json.dumps(search_rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    # robots
    (OUT / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    # IndexNow ownership key file (content must equal the key)
    (OUT / f"{INDEXNOW_KEY}.txt").write_text(INDEXNOW_KEY + "\n")
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


# ====================================================== आज के दिन / THIS DAY ===
MONTHS_HI = ["", "जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई",
             "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
DAYS_IN_MONTH = [0, 31, 29, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _canonical_days():
    """Ordered list of all 366 (month, day) pairs (Feb has 29)."""
    out = []
    for mo in range(1, 13):
        for da in range(1, DAYS_IN_MONTH[mo] + 1):
            out.append((mo, da))
    return out


def _td_dayslug(mo, da):
    return f"{mo:02d}-{da:02d}"


def _td_score(m):
    """Importance score used to pick which matches to surface for a day."""
    s = 0.0
    fmt = m["fmt"]
    s += {"Test": 4, "ODI": 3.5, "IPL": 3, "T20I": 1.5}.get(fmt, 1)
    teams = m.get("teams", [])
    if "India" in teams:
        s += 6
    ev = (m.get("event", "") + " " + m.get("stage", "")).lower()
    stage = m.get("stage", "").lower()
    if "final" in stage and "semi" not in stage:
        s += 8
    elif any(k in stage for k in ("semi", "qualifier", "eliminator")):
        s += 4
    if any(k in ev for k in ("world cup", "world t20", "champions trophy",
                             "world test championship", "asia cup", "t20 world")):
        s += 3
    # standout individual milestones on the day
    best_bat = max((b[1] for b in m.get("batting", [])), default=0)
    best_bowl = max((b[1] for b in m.get("bowling", [])), default=0)
    if best_bat >= 200:
        s += 5
    elif best_bat >= 100:
        s += 2.5
    if best_bowl >= 7:
        s += 4
    elif best_bowl >= 5:
        s += 2.5
    # gentle recency nudge so memorable modern games edge ahead of ties
    s += (m["year"] - 2000) * 0.04
    return s


def build_thisday(index, full):
    """Build the /aaj-ke-din/ index + 366 day pages from raw match data."""
    print("Scanning raw matches for 'आज के दिन'…")
    matches = TD.scan_matches()
    buckets = TD.aggregate_by_day(matches)

    # name -> player id, but only for players that actually have a profile page
    name2id = {}
    for p in index[:N_PLAYERS]:
        name2id.setdefault(p["name"], p["id"])
    team_slugs = {slug(t) for t in load("teams.json").keys()}

    def plink_name(name, depth):
        pid = name2id.get(name)
        hn = hindi_name(name)
        sub = f' <span class="hi text-cr-text text-xs">{hn}</span>' if hn else ""
        if pid:
            return (f'<a href="{"../"*depth}players/{pid}/" '
                    f'class="font-medium text-cr-ink hover:text-cr-green">{esc(name)}</a>{sub}')
        return f'<span class="font-medium text-cr-ink">{esc(name)}</span>{sub}'

    def tlink(name, depth):
        if slug(name) in team_slugs:
            return (f'<a href="{"../"*depth}teams/{slug(name)}/" '
                    f'class="text-cr-ink hover:text-cr-green hi font-medium">{esc(name)}</a>')
        return f'<span class="text-cr-ink hi font-medium">{esc(name)}</span>'

    canon = _canonical_days()
    n_days = len(canon)

    # ---------------- per-day pages ----------------
    for i, (mo, da) in enumerate(canon):
        depth = 2
        day_matches = buckets.get((mo, da), [])
        date_label = f"{da} {MONTHS_HI[mo]}"
        slug_day = _td_dayslug(mo, da)
        prev_mo, prev_da = canon[(i - 1) % n_days]
        next_mo, next_da = canon[(i + 1) % n_days]

        # rank + split
        ranked = sorted(day_matches, key=_td_score, reverse=True)
        years = sorted({m["year"] for m in day_matches})
        n_total = len(day_matches)
        fmt_counts = {}
        for m in day_matches:
            fmt_counts[m["fmt"]] = fmt_counts.get(m["fmt"], 0) + 1

        # ---- standout performances across the whole day ----
        cents = []   # (runs, balls, player, batting_team, opp, year, fmt)
        hauls = []   # (wkts, runs, balls, player, bowling_team, opp, year, fmt)
        for m in day_matches:
            t = m.get("teams", [])
            def opp_of(team):
                others = [x for x in t if x != team]
                return others[0] if others else ""
            for (pl, runs, balls, team) in m.get("batting", []):
                if runs >= 100:
                    cents.append((runs, balls, pl, team, opp_of(team), m["year"], m["fmt"]))
            for (pl, wk, runs, balls, team) in m.get("bowling", []):
                if wk >= 5:
                    hauls.append((wk, runs, balls, pl, team, opp_of(team), m["year"], m["fmt"]))
        cents.sort(reverse=True)
        hauls.sort(key=lambda x: (x[0], -x[1]), reverse=True)

        # ---------- prose intro ----------
        fmt_phrase = "、".join(
            f"{fmt_counts[f]} {FMT[f][0]}" for f in ["Test", "ODI", "T20I", "IPL"]
            if fmt_counts.get(f))
        if years:
            span = (f"{years[0]} से {years[-1]} के बीच"
                    if years[0] != years[-1] else f"{years[0]} में")
        else:
            span = ""
        intro_bits = [
            f"क्रिकेट के इतिहास में <strong>{date_label}</strong> का दिन कई "
            f"यादगार मुक़ाबलों का गवाह रहा है।"]
        if n_total:
            intro_bits.append(
                f"हमारे रिकॉर्ड के अनुसार {span} इस तारीख़ को कुल "
                f"<strong>{n_total}</strong> पुरुष अंतरराष्ट्रीय व आईपीएल मैच खेले गए"
                + (f" — इनमें {fmt_phrase} शामिल हैं।" if fmt_phrase else "।"))
        if cents:
            r, _b, pl, tm, opp, yr, fk = cents[0]
            intro_bits.append(
                f"बल्लेबाज़ी में सबसे बड़ी पारी {yr} में {esc(pl)} ने {tm} की ओर से "
                f"{opp or 'विपक्षी टीम'} के ख़िलाफ़ खेली — <strong>{r}</strong> रन।")
        elif hauls:
            wk, rn, _bl, pl, tm, opp, yr, fk = hauls[0]
            intro_bits.append(
                f"गेंदबाज़ी में सबसे यादगार प्रदर्शन {yr} में {esc(pl)} का रहा — "
                f"<strong>{wk}/{rn}</strong>।")
        intro = " ".join(intro_bits)

        body = f"""
        <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
          <div class="hi text-sm opacity-90 mb-1">आज के दिन क्रिकेट में</div>
          <h1 class="hi font-heading font-extrabold text-3xl sm:text-4xl">{date_label} को क्रिकेट में</h1>
          <p class="hi mt-3 text-white/95 leading-relaxed max-w-3xl">{intro}</p>
        </div>
        """

        # quick stat strip
        if n_total:
            body += '<div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">'
            body += stat("कुल मैच", n_total, "इस तारीख़ को")
            body += stat("शतक", len(cents), "100+ की पारियाँ")
            body += stat("5 विकेट हॉल", len(hauls), "पारी में")
            body += stat("वर्ष", f"{years[0]}–{years[-1]}" if len(years) > 1 else (str(years[0]) if years else "—"), "रिकॉर्ड अवधि")
            body += "</div>"

        # standout performances
        if cents or hauls:
            body += section_title("इस दिन के यादगार प्रदर्शन",
                                  "इस तारीख़ को खेली गई बड़ी पारियाँ और बेहतरीन गेंदबाज़ी")
            body += '<div class="grid md:grid-cols-2 gap-5 mb-8">'
            if cents:
                rows = []
                for (r, b, pl, tm, opp, yr, fk) in cents[:8]:
                    vs = f'{tlink(opp, depth)}' if opp else "—"
                    rows.append([plink_name(pl, depth),
                                 f'<b class="tnum">{r}</b>'
                                 + (f' <span class="text-cr-text text-xs tnum">({b})</span>' if b else ''),
                                 vs, f'<span class="tnum">{yr}</span> {fmt_badge(fk)}'])
                body += ('<div><h3 class="hi font-heading font-bold text-cr-ink mb-2">बड़ी पारियाँ (शतक)</h3>'
                         + table(["बल्लेबाज़", "रन", "बनाम", "वर्ष"], rows, align_right={1}) + "</div>")
            if hauls:
                rows = []
                for (wk, rn, bl, pl, tm, opp, yr, fk) in hauls[:8]:
                    vs = f'{tlink(opp, depth)}' if opp else "—"
                    rows.append([plink_name(pl, depth),
                                 f'<b class="tnum">{wk}/{rn}</b>',
                                 vs, f'<span class="tnum">{yr}</span> {fmt_badge(fk)}'])
                body += ('<div><h3 class="hi font-heading font-bold text-cr-ink mb-2">बेहतरीन गेंदबाज़ी (5+ विकेट)</h3>'
                         + table(["गेंदबाज़", "आँकड़े", "बनाम", "वर्ष"], rows, align_right={1}) + "</div>")
            body += "</div>"

        # notable matches
        if ranked:
            show = ranked[:16]
            body += section_title("उल्लेखनीय मैच",
                                  f"{date_label} को खेले गए चुनिंदा मुक़ाबले" +
                                  (f" — कुल {n_total} में से शीर्ष {len(show)}" if n_total > len(show) else ""))
            body += '<div class="space-y-3 mb-6">'
            for m in show:
                teams = m.get("teams", [])
                if len(teams) == 2:
                    vs = f'{tlink(teams[0], depth)} <span class="hi text-cr-text">बनाम</span> {tlink(teams[1], depth)}'
                else:
                    vs = " बनाम ".join(tlink(t, depth) for t in teams) or "—"
                if m["winner"]:
                    result = f'<span class="hi text-cr-green font-semibold">{tlink(m["winner"], depth)} {esc(m["margin"])} विजयी</span>'
                else:
                    result = f'<span class="hi text-cr-text font-medium">{esc(m["margin"] or "—")}</span>'
                meta = []
                if m.get("event"):
                    ev = m["event"]
                    if m.get("stage"):
                        ev += f' · {m["stage"]}'
                    meta.append(esc(ev))
                loc = m.get("city") or m.get("venue")
                if loc:
                    meta.append(esc(loc))
                meta_line = " · ".join(meta)
                # top perf snippet for this match
                perf = []
                top_bat = max(m.get("batting", []), key=lambda x: x[1], default=None)
                if top_bat and top_bat[1] >= 50:
                    perf.append(f'{plink_name(top_bat[0], depth)} {top_bat[1]}'
                                + (f' ({top_bat[2]})' if top_bat[2] else ''))
                top_bowl = max(m.get("bowling", []), key=lambda x: (x[1], -x[2]), default=None)
                if top_bowl and top_bowl[1] >= 4:
                    perf.append(f'{plink_name(top_bowl[0], depth)} {top_bowl[1]}/{top_bowl[2]}')
                perf_line = (' <span class="hi text-cr-text">·</span> '.join(perf))
                pom = ", ".join(m.get("pom", []))
                pom_line = (f'<div class="hi text-xs text-cr-text mt-1">मैन ऑफ़ द मैच: '
                            f'{plink_name(m["pom"][0], depth) if m.get("pom") else ""}</div>'
                            if pom else "")
                body += f"""<div class="bg-cr-card border border-cr-border rounded-xl p-4 hover:border-cr-green transition">
                  <div class="flex items-center justify-between gap-3 flex-wrap mb-1">
                    <div class="flex items-center gap-2">{fmt_badge(m["fmt"])}<span class="tnum text-sm font-bold text-cr-ink">{m["year"]}</span></div>
                    {f'<div class="hi text-xs text-cr-text">{meta_line}</div>' if meta_line else ''}
                  </div>
                  <div class="hi text-base mb-1">{vs}</div>
                  <div>{result}</div>
                  {f'<div class="hi text-sm text-cr-text mt-1">शीर्ष प्रदर्शन: {perf_line}</div>' if perf_line else ''}
                  {pom_line}
                </div>"""
            body += "</div>"
            if n_total > len(show):
                body += (f'<p class="hi text-sm text-cr-text mb-6">और भी '
                         f'<strong>{n_total - len(show)}</strong> मैच इस तारीख़ को खेले गए। '
                         f'ऊपर महत्व के आधार पर चुनिंदा मुक़ाबले दिखाए गए हैं।</p>')
        else:
            body += ('<p class="hi text-cr-text mb-6">इस तारीख़ के लिए हमारे डेटाबेस में '
                     'अभी कोई मैच दर्ज नहीं है।</p>')

        # prev / next nav
        body += f"""
        <nav class="flex items-center justify-between gap-3 border-t border-cr-border pt-5 mt-4">
          <a href="../{_td_dayslug(prev_mo, prev_da)}/" class="hi inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-cr-border hover:border-cr-green hover:text-cr-green transition">
            <span aria-hidden="true">←</span> {prev_da} {MONTHS_HI[prev_mo]}</a>
          <a href="../" class="hi px-4 py-2 rounded-lg bg-cr-bg border border-cr-border hover:border-cr-green text-cr-ink font-medium">सभी तारीख़ें</a>
          <a href="../{_td_dayslug(next_mo, next_da)}/" class="hi inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-cr-border hover:border-cr-green hover:text-cr-green transition">
            {next_da} {MONTHS_HI[next_mo]} <span aria-hidden="true">→</span></a>
        </nav>
        """

        # SEO
        title = f"{date_label} को क्रिकेट में — आज के दिन क्रिकेट इतिहास | क्रिकेट आँकड़े"
        teams_in_top = []
        for m in ranked[:4]:
            teams_in_top.extend(m.get("teams", []))
        teams_seen = []
        for t in teams_in_top:
            if t not in teams_seen:
                teams_seen.append(t)
        desc = (f"{date_label} को क्रिकेट इतिहास में क्या हुआ? इस तारीख़ को खेले गए "
                f"{n_total} टेस्ट, वनडे, टी20आई व आईपीएल मैच, बड़ी पारियाँ, 5 विकेट हॉल "
                f"और रिकॉर्ड — सब हिंदी में।")[:300]
        jsonld = {
            "@context": "https://schema.org", "@type": "CollectionPage",
            "name": f"{date_label} को क्रिकेट में",
            "inLanguage": "hi", "url": f"{SITE}/aaj-ke-din/{slug_day}/",
            "description": desc,
        }
        write(f"aaj-ke-din/{slug_day}/index.html",
              page(title, desc, f"/aaj-ke-din/{slug_day}/", depth, body,
                   active="thisday",
                   trail=[("होम", "../../"), ("आज के दिन", "../"), (date_label, None)],
                   jsonld=jsonld, og_type="article"), "0.5")

    # search entry (one combined, plus a few marquee dates handled by index)
    search_rows.append(["आज के दिन क्रिकेट में", "/aaj-ke-din/", "फ़ीचर",
                        "aaj ke din this day in cricket history on this day"])

    # ---------------- index / calendar page ----------------
    depth = 1
    total_matches = len(matches)
    body = f"""
    <div class="rounded-2xl pitch-stripe text-white p-6 sm:p-8 mb-6">
      <div class="hi text-sm opacity-90 mb-1">फ़ीचर</div>
      <h1 class="hi font-heading font-extrabold text-3xl sm:text-4xl">आज के दिन क्रिकेट में</h1>
      <p class="hi mt-3 text-white/95 leading-relaxed max-w-3xl">
        साल के हर दिन क्रिकेट के मैदान पर कुछ न कुछ ख़ास घटित हुआ है — कोई यादगार पारी,
        कोई ऐतिहासिक जीत या कोई टूटता हुआ रिकॉर्ड। नीचे किसी भी तारीख़ पर क्लिक करके
        जानिए उस दिन क्रिकेट इतिहास में क्या-क्या हुआ। हमारे डेटाबेस में
        <strong>{total_matches:,}</strong> पुरुष अंतरराष्ट्रीय व आईपीएल मैच शामिल हैं।
      </p>
    </div>
    """
    # today's shortcut
    t = date.today()
    today_slug = _td_dayslug(t.month, t.day)
    body += (f'<div class="mb-8"><a href="{today_slug}/" '
             f'class="hi inline-flex items-center gap-2 px-5 py-3 rounded-xl bg-cr-green text-white font-semibold hover:bg-cr-dark transition">'
             f'{icon("trophy","w-5 h-5")} आज — {t.day} {MONTHS_HI[t.month]} — देखें</a></div>')

    body += section_title("तारीख़ चुनें", "महीने के अनुसार किसी भी दिन की क्रिकेट कहानी पढ़ें")
    body += '<div class="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">'
    for mo in range(1, 13):
        cells = ""
        for da in range(1, DAYS_IN_MONTH[mo] + 1):
            cells += (f'<a href="{_td_dayslug(mo, da)}/" '
                      f'class="tnum flex items-center justify-center h-9 rounded-md border border-cr-border '
                      f'text-sm text-cr-ink hover:bg-cr-green hover:text-white hover:border-cr-green transition">{da}</a>')
        body += (f'<div class="bg-cr-card border border-cr-border rounded-xl p-4">'
                 f'<h3 class="hi font-heading font-bold text-cr-ink mb-3">{MONTHS_HI[mo]}</h3>'
                 f'<div class="grid grid-cols-7 gap-1.5">{cells}</div></div>')
    body += "</div>"

    desc = ("आज के दिन क्रिकेट में — साल के हर दिन क्रिकेट इतिहास में हुई यादगार घटनाएँ, "
            "मैच, बड़ी पारियाँ और रिकॉर्ड हिंदी में। किसी भी तारीख़ पर क्लिक करें।")
    jsonld = {"@context": "https://schema.org", "@type": "CollectionPage",
              "name": "आज के दिन क्रिकेट में", "inLanguage": "hi",
              "url": f"{SITE}/aaj-ke-din/", "description": desc}
    write("aaj-ke-din/index.html",
          page("आज के दिन क्रिकेट में — हर तारीख़ का क्रिकेट इतिहास | क्रिकेट आँकड़े",
               desc, "/aaj-ke-din/", depth, body, active="thisday",
               trail=[("होम", "../"), ("आज के दिन", None)], jsonld=jsonld), "0.8")
    print(f"Built 'आज के दिन': {n_days} day pages + index.")


# ===================================================================== MAIN ===
def main():
    global _PAGE_PIDS
    print("Loading processed data…")
    index = load("players_index.json")
    # Players with generated profile pages — gate every player link on this.
    _PAGE_PIDS = {p["id"] for p in index[:N_PLAYERS]}
    full = load("players_full.json")
    records = load("records.json")
    ipl = load("ipl.json")
    teams_d = load("teams.json")

    # build name->id for matchup pairs (prefer the most-capped namesake)
    name2id = {}
    for pid, p in full.items():
        n = p["name"]
        if n not in name2id or p["total_m"] > full[name2id[n]]["total_m"]:
            name2id[n] = pid
    def pid_of(n): return name2id.get(n)
    # ---- head-to-head rivalry matchups, grouped by theme ----
    H2H_CATEGORIES = [
        ("आधुनिक बल्लेबाज़ी प्रतिद्वंद्विताएँ", [
            ("V Kohli","RG Sharma"),("V Kohli","Babar Azam"),("V Kohli","SPD Smith"),
            ("V Kohli","KS Williamson"),("V Kohli","JE Root"),("V Kohli","DA Warner"),
            ("V Kohli","AB de Villiers"),("V Kohli","Q de Kock"),("V Kohli","HM Amla"),
            ("JE Root","SPD Smith"),("JE Root","KS Williamson"),("JE Root","Babar Azam"),
            ("JE Root","KP Pietersen"),
            ("SPD Smith","KS Williamson"),("SPD Smith","Babar Azam"),("SPD Smith","AB de Villiers"),
            ("KS Williamson","HM Amla"),("Babar Azam","DA Warner"),("Babar Azam","KS Williamson"),
            ("RG Sharma","DA Warner"),("RG Sharma","V Sehwag"),("RG Sharma","HM Amla"),
            ("RG Sharma","Babar Azam"),("RG Sharma","Q de Kock"),
            ("DA Warner","Q de Kock"),("DA Warner","HM Amla"),
            ("S Dhawan","RG Sharma"),("S Dhawan","KL Rahul"),
            ("SA Yadav","Shubman Gill"),("SA Yadav","RG Sharma"),
            ("Mohammad Rizwan","Babar Azam"),("Mohammad Rizwan","Q de Kock"),
            ("Fakhar Zaman","Babar Azam"),
        ]),
        ("दिग्गज बल्लेबाज़ — क्लासिक युग", [
            ("SR Tendulkar","RT Ponting"),("SR Tendulkar","BC Lara"),("SR Tendulkar","JH Kallis"),
            ("SR Tendulkar","R Dravid"),("SR Tendulkar","KC Sangakkara"),("SR Tendulkar","V Sehwag"),
            ("SR Tendulkar","V Kohli"),("SR Tendulkar","AN Cook"),
            ("RT Ponting","BC Lara"),("RT Ponting","JH Kallis"),("RT Ponting","KC Sangakkara"),
            ("RT Ponting","SPD Smith"),
            ("BC Lara","KC Sangakkara"),("BC Lara","DPMD Jayawardene"),("BC Lara","V Kohli"),
            ("KC Sangakkara","DPMD Jayawardene"),("KC Sangakkara","JH Kallis"),("KC Sangakkara","AB de Villiers"),
            ("JH Kallis","R Dravid"),("R Dravid","VVS Laxman"),("R Dravid","KC Sangakkara"),
            ("V Sehwag","CH Gayle"),("V Sehwag","HM Amla"),
            ("HM Amla","GC Smith"),("GC Smith","AN Cook"),("AN Cook","KP Pietersen"),
        ]),
        ("गेंदबाज़ी प्रतिद्वंद्विताएँ", [
            ("JJ Bumrah","MA Starc"),("JJ Bumrah","K Rabada"),("JJ Bumrah","PJ Cummins"),
            ("JJ Bumrah","Mohammed Shami"),("JJ Bumrah","TA Boult"),("JJ Bumrah","Shaheen Shah Afridi"),
            ("JJ Bumrah","Rashid Khan"),("JJ Bumrah","SL Malinga"),("JJ Bumrah","GD McGrath"),
            ("MA Starc","K Rabada"),("MA Starc","TA Boult"),("MA Starc","PJ Cummins"),
            ("PJ Cummins","K Rabada"),("PJ Cummins","TA Boult"),
            ("R Ashwin","NM Lyon"),("R Ashwin","Harbhajan Singh"),("R Ashwin","A Kumble"),
            ("R Ashwin","M Muralitharan"),("R Ashwin","SK Warne"),
            ("JM Anderson","SCJ Broad"),("JM Anderson","DW Steyn"),("JM Anderson","GD McGrath"),
            ("SCJ Broad","DW Steyn"),("DW Steyn","GD McGrath"),("DW Steyn","K Rabada"),
            ("M Muralitharan","SK Warne"),("M Muralitharan","A Kumble"),("M Muralitharan","Harbhajan Singh"),
            ("M Muralitharan","NM Lyon"),
            ("SK Warne","A Kumble"),("SK Warne","NM Lyon"),("A Kumble","Harbhajan Singh"),
            ("Rashid Khan","Imran Tahir"),("Rashid Khan","SP Narine"),("Rashid Khan","YS Chahal"),
            ("Rashid Khan","Kuldeep Yadav"),("Rashid Khan","SL Malinga"),("Rashid Khan","Mustafizur Rahman"),
            ("YS Chahal","Kuldeep Yadav"),
            ("TA Boult","Shaheen Shah Afridi"),
            ("Mohammed Shami","Mohammed Siraj"),("Mohammad Amir","Wahab Riaz"),
            ("Saeed Ajmal","Shakib Al Hasan"),
        ]),
        ("ऑलराउंडर व क्रॉस-डिसिप्लिन तुलना", [
            ("Shakib Al Hasan","RA Jadeja"),("Shakib Al Hasan","R Ashwin"),("Shakib Al Hasan","HH Pandya"),
            ("Shakib Al Hasan","BA Stokes"),("Shakib Al Hasan","JH Kallis"),
            ("BA Stokes","HH Pandya"),("BA Stokes","RA Jadeja"),
            ("HH Pandya","RA Jadeja"),("RA Jadeja","R Ashwin"),
            ("MM Ali","RA Jadeja"),("MM Ali","R Ashwin"),
            ("AD Russell","KA Pollard"),("AD Russell","SP Narine"),("AD Russell","DJ Bravo"),
            ("DJ Bravo","KA Pollard"),
        ]),
        ("आईपीएल सितारों के मुक़ाबले", [
            ("V Kohli","MS Dhoni"),("V Kohli","SK Raina"),
            ("RG Sharma","MS Dhoni"),
            ("MS Dhoni","SK Raina"),("MS Dhoni","AB de Villiers"),("MS Dhoni","RR Pant"),
            ("MS Dhoni","JC Buttler"),("MS Dhoni","KC Sangakkara"),("MS Dhoni","Q de Kock"),
            ("AD Russell","HH Pandya"),("GJ Maxwell","AD Russell"),("GJ Maxwell","HH Pandya"),
            ("KL Rahul","Shubman Gill"),("DA Warner","CH Gayle"),("CH Gayle","AB de Villiers"),
            ("SK Raina","RG Sharma"),("RR Pant","KL Rahul"),("Shubman Gill","RR Pant"),
            ("SA Yadav","RR Pant"),
            ("Yuvraj Singh","SK Raina"),("Yuvraj Singh","MS Dhoni"),
            ("DA Miller","KA Pollard"),
            ("Q de Kock","JC Buttler"),("JC Buttler","DA Warner"),("JC Buttler","RG Sharma"),
            ("Q de Kock","Mohammad Rizwan"),
            ("SP Narine","Rashid Khan"),
        ]),
    ]
    grouped = []
    for title, pl in H2H_CATEGORIES:
        g = []
        for a, b in pl:
            ia, ib = pid_of(a), pid_of(b)
            if ia and ib and ia != ib:
                g.append((ia, ib))
        grouped.append((title, g))

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
    build_compare(full, index, grouped)
    print("Building match scorecards…")
    build_scorecards(index, teams_d)
    print("Building ICC tournaments (World Cup / T20 WC / Champions Trophy)…")
    tour_data = TT.collect(RAW)
    valid_ids = {p["id"] for p in index[:N_PLAYERS]}
    valid_teams = set(teams_d.keys())
    build_tournaments(tour_data, valid_ids, valid_teams, name2id)
    print("Building 'आज के दिन' (This Day in Cricket)…")
    build_thisday(index, full)
    print("Building about + privacy…")
    build_about()
    build_privacy()
    print("Writing static assets + sitemap…")
    write_static()
    n = write_sitemap()
    print(f"DONE. {n} URLs, {len(search_rows)} search entries.")


if __name__ == "__main__":
    main()
