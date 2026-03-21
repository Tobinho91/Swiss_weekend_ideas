"""Abstrakte Basisklasse für Event-Scraper."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import date

from models import Event, EventCategory

logger = logging.getLogger(__name__)

# Mapping von gängigen Rohkategorien auf normalisierte Kategorien
_CATEGORY_KEYWORDS: dict[EventCategory, list[str]] = {
    "Konzerte": ["concert", "konzert", "music", "musik", "live", "festival", "dj"],
    "Kultur & Kunst": ["culture", "kultur", "art", "kunst", "theater", "theatre", "exhibition", "ausstellung", "museum", "kino", "film", "cinema"],
    "Sport": ["sport", "running", "marathon", "fussball", "football", "tennis", "yoga", "fitness"],
    "Märkte & Feste": ["markt", "market", "fest", "fair", "messe", "weihnachtsmarkt", "flohmarkt", "street food", "volksfest"],
    "Natur & Outdoor": ["outdoor", "natur", "nature", "wandern", "hiking", "bike", "velo"],
    "Familie": ["family", "familie", "kinder", "kids", "children"],
    "Gastronomie": ["food", "essen", "wein", "wine", "degustation", "brunch", "gastro"],
}


class EventScraper(ABC):
    """Abstrakte Basisklasse die alle Event-Scraper implementieren müssen."""

    name: str = "base"

    @abstractmethod
    async def fetch(self, weekend_start: date, weekend_end: date) -> list[Event]:
        """Holt Events für das angegebene Wochenende.

        Muss von Subklassen implementiert werden.
        Bei Fehlern: leere Liste zurückgeben und loggen, nie eine Exception werfen.
        """

    def normalize_category(self, raw: str) -> EventCategory:
        """Mappt eine Rohkategorie auf eine normalisierte EventCategory."""
        raw_lower = raw.lower()
        for category, keywords in _CATEGORY_KEYWORDS.items():
            if any(kw in raw_lower for kw in keywords):
                return category
        return "Sonstiges"

    async def safe_fetch(self, weekend_start: date, weekend_end: date) -> list[Event]:
        """Wrapper der Exceptions abfängt und leere Liste zurückgibt."""
        try:
            events = await self.fetch(weekend_start, weekend_end)
            logger.info("%s: %d Events gefunden", self.name, len(events))
            return events
        except Exception:
            logger.exception("%s: Fehler beim Abrufen der Events", self.name)
            return []
