# Swiss Weekend Ideas

Weekend events and hiking routes in Switzerland — automatically aggregated into a single HTML page every Thursday.

## What it does

- Scrapes **events** from Eventfrog.ch (concerts, culture, sports, markets, family, gastro)
- Collects **hiking routes** from SchweizMobil (rotating selection of 10 from a curated pool of 26)
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
  update.yml                # Cron: Thursdays 17:00 UTC
```

## Deployment

The GitHub Actions workflow runs every Thursday at 17:00 UTC:
1. Runs `python main.py` to scrape and generate HTML
2. Deploys `output/` to the `gh-pages` branch via GitHub Pages

To set up: go to **Settings → Pages → Source: `gh-pages` branch**.

To trigger manually: **Actions → Update Weekend Events → Run workflow**.

## Data sources

| Source | Type | Status |
|---|---|---|
| Eventfrog.ch | Events | Working |
| SchweizMobil | Hiking | Working (curated fallback) |
| Komoot | Hiking | Not working (API 405) |

## Tech stack

Python 3.11+ · httpx · BeautifulSoup4 · Jinja2 · GitHub Actions · GitHub Pages
