"""Event-Scraper für Eventfrog.ch — nutzt den internen event-list Endpoint."""

from __future__ import annotations

import logging
import re
from datetime import date, datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from config import (
    HTTP_TIMEOUT_SECONDS,
    MAX_EVENTS_PER_SOURCE,
    TZ,
    USER_AGENT,
)
from models import Event
from scrapers.events.base import EventScraper

logger = logging.getLogger(__name__)

# Mapping von URL-Pfad-Segmenten auf Event-Kategorien
_URL_CATEGORY_MAP: dict[str, str] = {
    # Musik & Konzerte
    "konzerte": "concert",
    "musik": "music",
    "festival": "festival",
    "party": "concert",
    "clubbing": "concert",
    "dj": "concert",
    # Kultur & Kunst
    "theater": "culture",
    "comedy": "culture",
    "ausstellung": "exhibition",
    "kunst": "exhibition",
    "museum": "culture",
    "kino": "culture",
    "film": "culture",
    "fuehrung": "culture",
    "fuehrungen": "culture",
    "vortraege": "culture",
    "vortrag": "culture",
    "lesung": "culture",
    # Sport
    "sport": "sport",
    "fitness": "sport",
    "wandern": "outdoor",
    "outdoor": "outdoor",
    "natur": "outdoor",
    "tier": "outdoor",
    "ausflug": "outdoor",
    "freizeit-ausfluege": "outdoor",
    # Märkte & Feste
    "maerkte": "market",
    "second-hand": "market",
    "flohmarkt": "market",
    "messe": "market",
    "volksfest": "market",
    "volksfeste": "market",
    "weihnachtsmarkt": "market",
    # Familie
    "kinderveranstaltungen": "family",
    "kinderfest": "family",
    "kinder": "family",
    "familie": "family",
    # Gastronomie
    "food": "gastro",
    "gastro": "gastro",
    "essen-trinken": "gastro",
    "essen": "gastro",
    "trinken": "gastro",
    # Bildung & Kurse → Kultur
    "kurse-seminare": "culture",
    "kurse": "culture",
    "seminar": "culture",
    "bildung": "culture",
    "wirtschaft": "culture",
    "berufliche": "culture",
    "hobby": "culture",
}


class EventfrogScraper(EventScraper):
    """Scraper für Eventfrog.ch — nutzt den internen HTML-Fragment-Endpoint."""

    name = "Eventfrog.ch"

    EVENT_LIST_URL = "https://eventfrog.ch/de/event-list.html"
    BASE_URL = "https://eventfrog.ch"

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": USER_AGENT,
            "Accept": "text/html",
            "Accept-Language": "de-CH,de;q=0.9",
            "X-Requested-With": "XMLHttpRequest",
        }

    async def fetch(self, weekend_start: date, weekend_end: date) -> list[Event]:
        """Holt Events für das angegebene Wochenende."""
        try:
            async with httpx.AsyncClient(
                timeout=HTTP_TIMEOUT_SECONDS,
                headers=self._headers(),
                follow_redirects=True,
            ) as client:
                resp = await client.get(self.EVENT_LIST_URL)

                if resp.status_code != 200:
                    logger.warning(
                        "%s: event-list Endpoint gab Status %d",
                        self.name,
                        resp.status_code,
                    )
                    return []

                soup = BeautifulSoup(resp.text, "lxml")
                cards = soup.select("a.event-list__events__tile")

                if not cards:
                    logger.warning("%s: Keine Event-Karten gefunden", self.name)
                    return []

                events: list[Event] = []
                for card in cards:
                    event = self._parse_card(card, weekend_start, weekend_end)
                    if event:
                        events.append(event)

                return events[:MAX_EVENTS_PER_SOURCE]

        except Exception:
            logger.exception("%s: Fehler beim Abrufen", self.name)
            return []

    def _parse_card(self, card: Any, weekend_start: date, weekend_end: date) -> Event | None:
        """Parst eine Event-Karte aus dem event-list HTML-Fragment."""
        try:
            # Titel
            title_el = card.select_one(
                ".event-list__events__tile__content__infos__title"
            )
            title = title_el.get_text(strip=True) if title_el else ""
            if not title:
                return None

            # Datum
            month_el = card.select_one(
                ".event-list__events__tile__content__date__month"
            )
            day_el = card.select_one(
                ".event-list__events__tile__content__date__day"
            )
            month_text = month_el.get_text(strip=True) if month_el else ""
            day_text = day_el.get_text(strip=True) if day_el else ""

            start_dt = self._parse_eventfrog_date(month_text, day_text)

            # Wenn wir kein Datum parsen konnten, nehmen wir den Wochenend-Start
            if start_dt is None:
                start_dt = datetime(
                    weekend_start.year, weekend_start.month, weekend_start.day,
                    0, 0, tzinfo=TZ,
                )

            # Zeit-Info
            time_el = card.select_one(
                ".event-list__events__tile__content__infos__time"
            )
            time_text = time_el.get_text(strip=True) if time_el else ""

            # Extrahiere Uhrzeit aus dem time_text (z.B. "19:30 Uhr" oder "14:00")
            time_match = re.search(r"(\d{1,2})[:\.](\d{2})", time_text)
            if time_match and start_dt.hour == 0 and start_dt.minute == 0:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2))
                if 0 <= hour < 24 and 0 <= minute < 60:
                    start_dt = start_dt.replace(hour=hour, minute=minute)

            # Ort
            location_el = card.select_one(
                ".event-list__events__tile__content__infos__location"
            )
            location_text = location_el.get_text(strip=True) if location_el else ""

            # Parse "Markthalle Aarau, Aarau (CH)" or "Büchel 4, St. Gallen (CH)"
            location_name, city, canton = self._parse_location(location_text)

            # Bild
            img = card.select_one(".event-list__events__tile__image img")
            image_url = None
            if img:
                src = img.get("src") or img.get("data-src") or ""
                if src and not src.startswith("http"):
                    src = f"{self.BASE_URL}{src}"
                if src:
                    image_url = src

            # URL
            href = card.get("href", "")
            if href and not href.startswith("http"):
                href = f"{self.BASE_URL}{href}"
            source_url = href or self.EVENT_LIST_URL

            # Kategorie aus URL-Pfad extrahieren
            raw_category = self._extract_category_from_url(href)

            # Event-ID aus URL extrahieren (letzte Zahlenfolge)
            external_id = None
            id_match = re.search(r"-(\d{10,})\.html", href)
            if id_match:
                external_id = id_match.group(1)

            return Event(
                title=title,
                start_datetime=start_dt,
                location_name=location_name,
                city=city,
                canton=canton,
                category=self.normalize_category(raw_category),
                source="eventfrog",
                source_url=source_url,
                image_url=image_url,
                external_id=external_id,
            )
        except Exception:
            logger.debug("%s: Konnte Karte nicht parsen", self.name)
            return None

    def _parse_eventfrog_date(self, month_text: str, day_text: str) -> datetime | None:
        """Parst Eventfrog-Datumsformat wie 'Mär 21' oder 'bis Dez 26'."""
        # Entferne Präfixe wie "bis"
        month_text = re.sub(r"^(bis|ab)\s+", "", month_text.strip(), flags=re.IGNORECASE)

        month_map = {
            "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4,
            "mai": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "okt": 10, "nov": 11, "dez": 12,
        }

        month_lower = month_text.lower().strip()
        month = None
        for key, val in month_map.items():
            if month_lower.startswith(key):
                month = val
                break

        if month is None:
            return None

        try:
            day = int(day_text.strip())
        except (ValueError, TypeError):
            return None

        # Jahr: aktuelles oder nächstes
        now = datetime.now(TZ)
        year = now.year
        try:
            dt = datetime(year, month, day, 0, 0, tzinfo=TZ)
        except ValueError:
            return None

        # Wenn das Datum in der Vergangenheit liegt (>30 Tage), nächstes Jahr
        if dt < now - __import__("datetime").timedelta(days=30):
            dt = dt.replace(year=year + 1)

        return dt

    def _parse_location(self, text: str) -> tuple[str, str, str]:
        """Parst 'Venue Name, City (CH)' in (location_name, city, canton)."""
        if not text:
            return "Unbekannt", "Unbekannt", ""

        # Entferne "(CH)" am Ende
        text = re.sub(r"\s*\(CH\)\s*$", "", text).strip()

        # Teile bei letztem Komma
        parts = text.rsplit(",", 1)
        if len(parts) == 2:
            location_name = parts[0].strip()
            city = parts[1].strip()
        else:
            location_name = text
            city = text

        # Versuche Kanton aus Stadtnamen zu erraten
        canton = self._guess_canton(city)

        return location_name, city, canton

    @staticmethod
    def _guess_canton(city: str) -> str:
        """Grobe Zuordnung bekannter Schweizer Städte zu Kantonen."""
        city_canton_map = {
            "zürich": "ZH", "winterthur": "ZH", "uster": "ZH", "dübendorf": "ZH",
            "bern": "BE", "thun": "BE", "biel": "BE", "burgdorf": "BE",
            "basel": "BS", "riehen": "BS",
            "luzern": "LU", "emmen": "LU", "kriens": "LU",
            "st. gallen": "SG", "rapperswil": "SG", "wil": "SG",
            "lausanne": "VD", "nyon": "VD", "montreux": "VD",
            "genf": "GE", "genève": "GE",
            "lugano": "TI", "bellinzona": "TI", "locarno": "TI",
            "aarau": "AG", "baden": "AG", "wettingen": "AG",
            "zug": "ZG", "baar": "ZG",
            "chur": "GR", "davos": "GR",
            "schaffhausen": "SH",
            "solothurn": "SO",
            "olten": "SO",
            "frauenfeld": "TG",
            "fribourg": "FR", "freiburg": "FR",
            "sion": "VS", "sitten": "VS", "brig": "VS", "visp": "VS",
            "neuchâtel": "NE", "neuenburg": "NE",
            "delémont": "JU",
            "schwyz": "SZ",
            "altdorf": "UR",
            "sarnen": "OW",
            "stans": "NW",
            "glarus": "GL",
            "appenzell": "AI",
            "herisau": "AR",
            "liestal": "BL", "allschwil": "BL",
        }
        return city_canton_map.get(city.lower().strip(), "")

    @staticmethod
    def _extract_category_from_url(url: str) -> str:
        """Extrahiert die Kategorie aus dem URL-Pfad eines Eventfrog-Events."""
        # URL: /de/p/maerkte/second-hand/veloboerse-...html
        # URL: /de/p/konzerte/rock-pop/event-name-...html
        match = re.search(r"/p/([^/]+)(?:/([^/]+))?/", url)
        if match:
            main_cat = match.group(1)
            sub_cat = match.group(2) or ""

            # Versuche Sub-Kategorie zuerst, dann Haupt-Kategorie
            for segment in (sub_cat, main_cat):
                for key, value in _URL_CATEGORY_MAP.items():
                    if key in segment:
                        return value
            return main_cat  # Roh-Kategorie zurückgeben

        # Fallback für Gruppen-URLs: /de/p/gruppen/...
        if "/gruppen/" in url:
            return "Sonstiges"

        return "Sonstiges"
