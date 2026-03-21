"""Einstiegspunkt: Events und Wanderungen sammeln, HTML generieren."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from config import TZ, get_next_weekend, weekend_end_datetime, weekend_start_datetime
from models import Event, Hike
from scrapers.events.eventfrog import EventfrogScraper
from scrapers.hiking.komoot import KomootScraper
from scrapers.hiking.schweizmobil import SchweizMobilScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).parent
TEMPLATE_DIR = PROJECT_DIR / "templates"
OUTPUT_DIR = PROJECT_DIR / "output"


def get_event_scrapers():
    return [
        EventfrogScraper(),
    ]


def get_hiking_scrapers():
    return [
        KomootScraper(),
        SchweizMobilScraper(),
    ]


def deduplicate_events(events: list[Event]) -> list[Event]:
    """Entfernt Duplikate basierend auf external_id + source oder Titel + Stadt + Datum."""
    seen = set()
    unique = []
    for event in events:
        if event.external_id and event.source:
            key = (event.source, event.external_id)
        else:
            key = (event.title.lower().strip(), event.city.lower().strip(), event.start_datetime.date())
        if key not in seen:
            seen.add(key)
            unique.append(event)
    return unique


def deduplicate_hikes(hikes: list[Hike]) -> list[Hike]:
    """Entfernt Duplikate basierend auf external_id + source oder Titel + Region."""
    seen = set()
    unique = []
    for hike in hikes:
        if hike.external_id and hike.source:
            key = (hike.source, hike.external_id)
        else:
            key = (hike.title.lower().strip(), hike.region.lower().strip())
        if key not in seen:
            seen.add(key)
            unique.append(hike)
    return unique


async def collect_events(weekend_start, weekend_end) -> tuple[list[Event], list[str], list[str]]:
    scrapers = get_event_scrapers()
    tasks = [scraper.safe_fetch(weekend_start, weekend_end) for scraper in scrapers]
    results = await asyncio.gather(*tasks)

    all_events = []
    sources_used = []
    sources_failed = []
    for scraper, events in zip(scrapers, results):
        if events:
            all_events.extend(events)
            sources_used.append(scraper.name)
        else:
            sources_failed.append(scraper.name)

    return deduplicate_events(all_events), sources_used, sources_failed


async def collect_hikes() -> tuple[list[Hike], list[str], list[str]]:
    scrapers = get_hiking_scrapers()
    tasks = [scraper.safe_fetch() for scraper in scrapers]
    results = await asyncio.gather(*tasks)

    all_hikes = []
    sources_used = []
    sources_failed = []
    for scraper, hikes in zip(scrapers, results):
        if hikes:
            all_hikes.extend(hikes)
            sources_used.append(scraper.name)
        else:
            sources_failed.append(scraper.name)

    return deduplicate_hikes(all_hikes), sources_used, sources_failed


def group_events_by_category(events: list[Event]) -> dict[str, list[Event]]:
    grouped = defaultdict(list)
    for event in sorted(events, key=lambda e: e.start_datetime):
        grouped[event.category].append(event)

    # Bestimmte Reihenfolge der Kategorien
    order = ["Konzerte", "Kultur & Kunst", "Sport", "Märkte & Feste", "Natur & Outdoor", "Familie", "Gastronomie", "Sonstiges"]
    ordered = {}
    for cat in order:
        if cat in grouped:
            ordered[cat] = grouped[cat]
    return ordered


def render_html(
    events_by_category: dict[str, list[Event]],
    hikes: list[Hike],
    weekend_start,
    weekend_end,
    sources_used: list[str],
    sources_failed: list[str],
) -> str:
    from datetime import datetime

    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))

    # Deutsche Monatsnamen und Wochentage als Jinja2-Filter
    _DE_MONTHS = {
        1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
        7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
    }
    _DE_DAYS = {
        0: "Montag", 1: "Dienstag", 2: "Mittwoch", 3: "Donnerstag",
        4: "Freitag", 5: "Samstag", 6: "Sonntag",
    }

    def de_date(dt, fmt="%A, %d. %B %Y"):
        """Deutsches Datum-Format."""
        if hasattr(dt, "month"):
            s = fmt
            s = s.replace("%B", _DE_MONTHS.get(dt.month, ""))
            s = s.replace("%A", _DE_DAYS.get(dt.weekday(), ""))
            s = s.replace("%d", str(dt.day))
            s = s.replace("%m", f"{dt.month:02d}")
            s = s.replace("%Y", str(dt.year))
            if hasattr(dt, "hour"):
                s = s.replace("%H", f"{dt.hour:02d}")
                s = s.replace("%M", f"{dt.minute:02d}")
            return s
        return str(dt)

    env.filters["de_date"] = de_date
    template = env.get_template("weekend.html")

    all_events = [e for events in events_by_category.values() for e in events]
    event_cantons = sorted(set(e.canton for e in all_events))
    hike_cantons = sorted(set(h.canton for h in hikes))

    return template.render(
        weekend_start=weekend_start,
        weekend_end=weekend_end,
        events_by_category=events_by_category,
        hikes=sorted(hikes, key=lambda h: h.title),
        total_events=len(all_events),
        total_hikes=len(hikes),
        event_cantons=event_cantons,
        hike_cantons=hike_cantons,
        sources_used=sources_used,
        sources_failed=sources_failed,
        generated_at=datetime.now(TZ),
    )


async def main():
    saturday, sunday = get_next_weekend()
    ws = weekend_start_datetime(saturday)
    we = weekend_end_datetime(sunday)

    logger.info("Wochenende: %s – %s", saturday, sunday)

    events, event_sources, event_failures = await collect_events(saturday, sunday)
    hikes, hike_sources, hike_failures = await collect_hikes()

    logger.info("Gesammelt: %d Events, %d Wanderungen", len(events), len(hikes))

    events_by_category = group_events_by_category(events)
    sources_used = event_sources + hike_sources
    sources_failed = event_failures + hike_failures

    html = render_html(events_by_category, hikes, saturday, sunday, sources_used, sources_failed)

    OUTPUT_DIR.mkdir(exist_ok=True)
    output_path = OUTPUT_DIR / "index.html"
    output_path.write_text(html, encoding="utf-8")
    logger.info("HTML geschrieben: %s", output_path)


if __name__ == "__main__":
    asyncio.run(main())
