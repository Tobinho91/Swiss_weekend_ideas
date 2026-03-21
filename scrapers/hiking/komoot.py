"""Komoot Hiking-Scraper für populäre Wanderrouten in der Schweiz."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from config import CH_BBOX, HTTP_TIMEOUT_SECONDS, MAX_HIKES_PER_SOURCE, REQUEST_DELAY_SECONDS, USER_AGENT
from models import Hike
from scrapers.hiking.base import HikingScraper

logger = logging.getLogger(__name__)

# Komoot sport types that count as hiking/walking
HIKING_SPORT_TYPES = {"hike", "hiking", "mountaineering", "wandern"}

# Komoot difficulty mapping
DIFFICULTY_MAP: dict[str, str] = {
    "easy": "easy",
    "moderate": "intermediate",
    "intermediate": "intermediate",
    "difficult": "hard",
    "hard": "hard",
    "expert": "expert",
}

# Discover page URL for hiking in Switzerland
DISCOVER_URL = "https://www.komoot.com/de-ch/guide/wandern/schweiz"

# API endpoint for tour discovery
API_URL = "https://www.komoot.com/api/v007/tours/"


class KomootScraper(HikingScraper):
    """Scraper für Komoot Wanderrouten in der Schweiz."""

    name = "Komoot"

    def _build_headers(self) -> dict[str, str]:
        """Erstellt HTTP-Headers für Anfragen."""
        return {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
            "Accept-Language": "de-CH,de;q=0.9,en;q=0.5",
        }

    def _extract_json_from_html(self, html: str) -> list[dict[str, Any]]:
        """Extrahiert Tour-Daten aus eingebettetem JSON in der HTML-Seite."""
        tours: list[dict[str, Any]] = []

        # Komoot embeds data in __NEXT_DATA__ or similar JSON script tags
        patterns = [
            r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>',
            r'<script[^>]*type="application/json"[^>]*>(.*?)</script>',
            r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, html, re.DOTALL)
            for match in matches:
                try:
                    data = json.loads(match)
                    found = self._find_tours_in_data(data)
                    tours.extend(found)
                except (json.JSONDecodeError, ValueError):
                    continue

        return tours

    def _find_tours_in_data(self, data: Any, depth: int = 0) -> list[dict[str, Any]]:
        """Durchsucht verschachtelte JSON-Daten rekursiv nach Tour-Objekten."""
        tours: list[dict[str, Any]] = []

        if depth > 10:
            return tours

        if isinstance(data, dict):
            # Check if this dict looks like a tour object
            if self._is_tour_object(data):
                tours.append(data)
            else:
                for value in data.values():
                    tours.extend(self._find_tours_in_data(value, depth + 1))
        elif isinstance(data, list):
            for item in data:
                tours.extend(self._find_tours_in_data(item, depth + 1))

        return tours

    def _is_tour_object(self, obj: dict[str, Any]) -> bool:
        """Prüft ob ein Dict ein Komoot-Tour-Objekt ist."""
        # A tour typically has: name/title, distance, duration, sport
        has_name = "name" in obj or "title" in obj
        has_distance = "distance" in obj
        has_duration = "duration" in obj or "time_in_motion" in obj
        has_sport = "sport" in obj or "type" in obj

        return has_name and has_distance and (has_duration or has_sport)

    def _is_in_switzerland(self, tour: dict[str, Any]) -> bool:
        """Prüft ob eine Tour in der Schweiz liegt anhand der Koordinaten."""
        lon_min, lat_min, lon_max, lat_max = CH_BBOX

        # Check start_point coordinates
        start = tour.get("start_point") or tour.get("startPoint") or {}
        lat = start.get("lat") or start.get("latitude")
        lng = start.get("lng") or start.get("lon") or start.get("longitude")

        if lat is not None and lng is not None:
            try:
                lat_f = float(lat)
                lng_f = float(lng)
                return lat_min <= lat_f <= lat_max and lon_min <= lng_f <= lon_max
            except (ValueError, TypeError):
                pass

        # Check location info
        location = tour.get("location") or {}
        if isinstance(location, dict):
            country = str(location.get("country", "")).upper()
            if country in ("CH", "SWITZERLAND", "SCHWEIZ", "SUISSE"):
                return True

        # If we fetched from the Swiss guide page, assume Swiss
        return True

    def _is_hiking_tour(self, tour: dict[str, Any]) -> bool:
        """Prüft ob eine Tour eine Wanderung ist."""
        sport = str(tour.get("sport", "")).lower()
        tour_type = str(tour.get("type", "")).lower()

        for val in (sport, tour_type):
            if val in HIKING_SPORT_TYPES:
                return True
            if "hik" in val or "wander" in val:
                return True

        return False

    def _extract_difficulty(self, tour: dict[str, Any]) -> str:
        """Extrahiert und normalisiert den Schwierigkeitsgrad."""
        raw = ""

        # Try different field names
        for key in ("difficulty", "difficulty_level", "technical_difficulty"):
            val = tour.get(key)
            if val is not None:
                if isinstance(val, dict):
                    raw = str(val.get("grade", val.get("level", "")))
                else:
                    raw = str(val)
                break

        mapped = DIFFICULTY_MAP.get(raw.lower().strip(), raw)
        return self.normalize_difficulty(mapped) if mapped else self.normalize_difficulty("intermediate")

    def _extract_region_canton(self, tour: dict[str, Any]) -> tuple[str, str]:
        """Extrahiert Region und Kanton aus Tour-Daten."""
        region = "Schweiz"
        canton = ""

        location = tour.get("location") or {}
        if isinstance(location, dict):
            region = location.get("region") or location.get("name") or region
            canton = location.get("state") or location.get("canton") or ""

        # Try to extract from summary or map_image location
        if not canton:
            summary = tour.get("summary") or tour.get("constitution_summary") or ""
            if isinstance(summary, dict):
                canton = summary.get("canton", "")

        return str(region), str(canton)

    def _tour_to_hike(self, tour: dict[str, Any]) -> Hike | None:
        """Konvertiert ein Komoot-Tour-Objekt in ein Hike-Objekt."""
        try:
            title = tour.get("name") or tour.get("title") or ""
            if not title:
                return None

            # Distance: meters → km
            distance_m = tour.get("distance", 0)
            distance_km = round(float(distance_m) / 1000, 1) if distance_m else 0.0

            # Duration: seconds → minutes
            duration_s = tour.get("duration", 0) or tour.get("time_in_motion", 0)
            duration_min = int(float(duration_s) / 60) if duration_s else 0

            if distance_km <= 0 or duration_min <= 0:
                return None

            # Difficulty
            difficulty = self._extract_difficulty(tour)

            # Region and canton
            region, canton = self._extract_region_canton(tour)

            # Tour ID and URL
            tour_id = tour.get("id") or tour.get("_id") or ""
            source_url = f"https://www.komoot.com/tour/{tour_id}" if tour_id else ""

            # Elevation
            elevation_gain = tour.get("elevation_up") or tour.get("elevationUp")
            elevation_loss = tour.get("elevation_down") or tour.get("elevationDown")

            # Start point coordinates
            start = tour.get("start_point") or tour.get("startPoint") or {}
            lat_start = None
            lon_start = None
            start_name = None
            if isinstance(start, dict):
                lat_start = start.get("lat") or start.get("latitude")
                lon_start = start.get("lng") or start.get("lon") or start.get("longitude")
                start_name = start.get("name")

            if lat_start is not None:
                lat_start = float(lat_start)
            if lon_start is not None:
                lon_start = float(lon_start)

            # Description (max 500 chars)
            description = tour.get("description") or tour.get("summary") or ""
            if isinstance(description, dict):
                description = description.get("text", "")
            description = str(description).strip()
            if len(description) > 500:
                description = description[:497] + "..."

            # Image URL
            image_url = None
            cover = tour.get("cover_image") or tour.get("map_image") or tour.get("image") or {}
            if isinstance(cover, dict):
                image_url = cover.get("src") or cover.get("url") or cover.get("templated_url")
            elif isinstance(cover, str):
                image_url = cover

            # Tags
            tags: list[str] = []
            sport = tour.get("sport", "")
            if sport:
                tags.append(str(sport))

            return Hike(
                title=str(title),
                difficulty=difficulty,
                duration_minutes=duration_min,
                distance_km=distance_km,
                region=region,
                canton=canton,
                source="komoot",
                source_url=source_url,
                elevation_gain_m=int(float(elevation_gain)) if elevation_gain else None,
                elevation_loss_m=int(float(elevation_loss)) if elevation_loss else None,
                start_point=str(start_name) if start_name else None,
                end_point=None,
                description=description or None,
                image_url=str(image_url) if image_url else None,
                latitude_start=lat_start,
                longitude_start=lon_start,
                gpx_url=None,
                tags=tags,
                external_id=str(tour_id) if tour_id else None,
            )
        except Exception:
            logger.debug("Fehler beim Konvertieren einer Komoot-Tour: %s", tour.get("name", "?"))
            return None

    async def _fetch_from_discover_page(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """Lädt Tour-Daten von der Komoot Discover-Seite."""
        logger.info("Lade Komoot Discover-Seite: %s", DISCOVER_URL)
        response = await client.get(DISCOVER_URL, follow_redirects=True)
        response.raise_for_status()

        html = response.text
        tours = self._extract_json_from_html(html)
        logger.info("Komoot Discover-Seite: %d Tour-Objekte gefunden", len(tours))
        return tours

    async def _fetch_from_api(self, client: httpx.AsyncClient) -> list[dict[str, Any]]:
        """Lädt Tour-Daten von der Komoot API."""
        lon_min, lat_min, lon_max, lat_max = CH_BBOX
        center_lat = (lat_min + lat_max) / 2
        center_lng = (lon_min + lon_max) / 2

        params = {
            "sport_types": "hike,hiking,mountaineering",
            "center": f"{center_lat},{center_lng}",
            "max_distance": 200000,  # 200km radius from center
            "limit": MAX_HIKES_PER_SOURCE,
            "page": 0,
            "sort_field": "popularity",
            "sort_order": "desc",
        }

        logger.info("Lade Komoot API: %s", API_URL)
        response = await client.get(
            API_URL,
            params=params,
            follow_redirects=True,
        )
        response.raise_for_status()

        data = response.json()

        # API usually returns tours under a "tours", "_embedded.tours", or "items" key
        tours: list[dict[str, Any]] = []
        if isinstance(data, list):
            tours = data
        elif isinstance(data, dict):
            tours = (
                data.get("tours")
                or data.get("items")
                or data.get("_embedded", {}).get("tours")
                or data.get("page", {}).get("_embedded", {}).get("tours")
                or []
            )

        logger.info("Komoot API: %d Tour-Objekte gefunden", len(tours))
        return tours

    async def fetch(self, region: str | None = None) -> list[Hike]:
        """Holt Wanderrouten von Komoot für die Schweiz."""
        try:
            hikes: list[Hike] = []
            tours: list[dict[str, Any]] = []

            async with httpx.AsyncClient(
                headers=self._build_headers(),
                timeout=HTTP_TIMEOUT_SECONDS,
            ) as client:
                # Try API first, fall back to discover page
                try:
                    tours = await self._fetch_from_api(client)
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    logger.warning("Komoot API fehlgeschlagen (%s), versuche Discover-Seite", exc)

                if not tours:
                    await asyncio.sleep(REQUEST_DELAY_SECONDS)
                    try:
                        tours = await self._fetch_from_discover_page(client)
                    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                        logger.warning("Komoot Discover-Seite fehlgeschlagen: %s", exc)

            if not tours:
                logger.warning("Komoot: Keine Touren gefunden")
                return []

            # Filter and convert tours
            for tour in tours:
                if len(hikes) >= MAX_HIKES_PER_SOURCE:
                    break

                # Filter for hiking sport type
                if not self._is_hiking_tour(tour):
                    continue

                # Filter for Switzerland
                if not self._is_in_switzerland(tour):
                    continue

                hike = self._tour_to_hike(tour)
                if hike is not None:
                    hikes.append(hike)

            logger.info("Komoot: %d Wanderungen nach Filterung", len(hikes))
            return hikes

        except Exception:
            logger.exception("Komoot: Unerwarteter Fehler beim Abrufen der Wanderungen")
            return []
