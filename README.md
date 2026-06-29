# क्रिकेट आँकड़े — CricketStatsHindi.com

A comprehensive **Hindi-language cricket statistics** website. Static HTML on
GitHub Pages + Cloudflare. Light, cricket-pitch themed, data-rich.

Covers **Test, ODI, T20I and IPL** — player career stats, head-to-head
comparisons, team records, records leaderboards, IPL season summaries and
match scorecards. All UI in Devanagari (`lang="hi"`).

## Data

All data comes from [Cricsheet.org](https://cricsheet.org) — free, open
ball-by-ball cricket data. ~10,720 matches processed.

## Architecture

```
data/raw/          downloaded Cricsheet JSON (gitignored, 1.7GB)
data/processed/    aggregated stats (committed): players, teams, records, ipl
scripts/
  aggregate.py     ball-by-ball JSON → career/team/records JSON
  templates.py     shared chrome (head/nav/footer), Hindi strings, theme
  generate.py      processed JSON → static HTML at repo root
```

Players are keyed by Cricsheet's stable people-registry id, so a player's
record is merged across all four formats automatically.

## Rebuild from scratch

```bash
# 1. Download Cricsheet data
mkdir -p data/raw && cd data/raw
for f in ipl t20s odis tests; do
  curl -sLO https://cricsheet.org/downloads/${f}_json.zip
  unzip -q -o ${f}_json.zip -d ${f}_json
done
cd ../..

# 2. Aggregate + generate
python3 scripts/aggregate.py
python3 scripts/generate.py

# 3. Preview locally
python3 -m http.server 8788
```

## SEO

Every page ships self-referential canonical, full OG + Twitter cards, Hindi
meta descriptions (150–160 chars), JSON-LD (`WebSite` / `Person` /
`SportsTeam` / `BreadcrumbList`), plus `sitemap.xml`, `robots.txt` and a
client-side search index (`search-index.json` + `search.js`).

## Deploy

GitHub Pages serves from repo root. `CNAME` → `cricketstatshindi.com`
(proxied through Cloudflare).

---
Not affiliated with the BCCI, ICC, IPL or any cricket board. Data © Cricsheet
contributors.
