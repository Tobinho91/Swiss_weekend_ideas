"""Abstrakte Basisklasse für Hiking-Scraper."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from models import Hike, HikeDifficulty

logger = logging.getLogger(__name__)


class HikingScraper(ABC):
    """Abstrakte Basisklasse die alle Hiking-Scraper implementieren müssen."""

    name: str = "base"

    @abstractmethod
    async def fetch(self, region: str | None = None) -> list[Hike]:
        """Holt Wanderrouten, optional gefiltert nach Region.

        Muss von Subklassen implementiert werden.
        Bei Fehlern: leere Liste zurückgeben und loggen, nie eine Exception werfen.
        """

    def normalize_difficulty(self, raw: str) -> HikeDifficulty:
        """Mappt einen Roh-Schwierigkeitsgrad auf HikeDifficulty."""
        raw_lower = raw.lower().strip()

        easy = {"easy", "leicht", "t1", "t2", "1", "facile"}
        medium = {"intermediate", "moderate", "mittel", "t3", "2", "moyen"}
        hard = {"hard", "difficult", "schwer", "t4", "3", "difficile"}
        very_hard = {"expert", "sehr schwer", "t5", "t6", "4", "très difficile"}

        if raw_lower in easy:
            return "Leicht"
        if raw_lower in medium:
            return "Mittel"
        if raw_lower in hard:
            return "Schwer"
        if raw_lower in very_hard:
            return "Sehr schwer"
        return "Mittel"  # Fallback

    async def safe_fetch(self, region: str | None = None) -> list[Hike]:
        """Wrapper der Exceptions abfängt und leere Liste zurückgibt."""
        try:
            hikes = await self.fetch(region)
            logger.info("%s: %d Wanderungen gefunden", self.name, len(hikes))
            return hikes
        except Exception:
            logger.exception("%s: Fehler beim Abrufen der Wanderungen", self.name)
            return []
