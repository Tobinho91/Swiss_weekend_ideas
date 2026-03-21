# Swiss Weekend Ideas

**[Live Site](https://tobinho91.github.io/Swiss_weekend_ideas/)**

Weekend events and hiking routes in Switzerland — automatically aggregated into a single HTML page every Thursday.

## What it does

- Scrapes **events** from Eventfrog.ch (concerts, culture, sports, markets, family, gastro)
- Collects **hiking routes** from SchweizMobil (rotating selection of 10 from a curated pool of 44+)
- **Automatically expands the route pool** — adds 10 new curated routes on the 1st of each month
- Generates a static HTML page with:
  - Tab navigation (Events / Wanderrouten / Favoriten)
  - Filters: category, canton, day, price, difficulty, duration, distance
  - Save/favorite system with heart buttons (persists via localStorage)
- Deploys automatically to GitHub Pages via GitHub Actions

## Local usage

```bash
pip install -r requirements.txt
python main.py
# → output/events_this_weekend.html
```

Open the generated file in your browser.

## Architecture

```
main.py                     # Entry point, orchestration
models.py                   # Event + Hike dataclasses
config.py                   # Timezone, weekend logic, env vars
scrapers/
  events/
    base.py                 # Abstract EventScraper
    eventfrog.py            # Eventfrog.ch scraper
  hiking/
    base.py                 # Abstract HikingScraper
    komoot.py               # Komoot (currently not working)
    schweizmobil.py         # SchweizMobil curated routes
templates/
  weekend.html              # Jinja2 template (CSS + JS inline)
.github/workflows/
  update.yml                # Cron: Thursdays 17:00 UTC (regenerate website)
  update-routes.yml         # Cron: 1st of month 08:57 UTC (add 10 new routes)
scripts/
  auto_add_routes.py        # Automated route addition script (run by update-routes.yml)
```

## Deployment

### Weekly Website Update (Thursdays)
The **Update Weekend Events** workflow runs every Thursday at 17:00 UTC:
1. Runs `python main.py` to scrape events and select 10 random hiking routes
2. Deploys `output/index.html` to the `gh-pages` branch via GitHub Pages

To trigger manually: **Actions → Update Weekend Events → Run workflow**.

### Monthly Route Pool Expansion (1st of month)
The **Monthly Hiking Routes Update** workflow runs on the 1st of each month at 08:57 UTC:
1. Runs `scripts/auto_add_routes.py` to add 10 new curated hiking routes
2. Regenerates the website with the expanded pool
3. Auto-commits and pushes changes to main branch

**Route pool growth:**
- March 2026: 44 routes
- April 2026: 54 routes
- Target: 100+ routes by end of 2026

To trigger manually: **Actions → Monthly Hiking Routes Update → Run workflow**.

To set up: go to **Settings → Pages → Source: `gh-pages` branch**.

## Data sources

| Source | Type | Status | Notes |
|---|---|---|---|
| Eventfrog.ch | Events | Working | Scraped weekly |
| SchweizMobil | Hiking | Working | 44+ curated routes, +10/month automated expansion |
| Komoot | Hiking | Not working | API returns 405 |

## Tech stack

Python 3.11+ · httpx · BeautifulSoup4 · Jinja2 · GitHub Actions · GitHub Pages
