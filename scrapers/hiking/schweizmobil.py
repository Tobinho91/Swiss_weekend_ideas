"""Scraper für SchweizMobil Wanderrouten (schweizmobil.ch)."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import field
from typing import Any

import httpx

from config import HTTP_TIMEOUT_SECONDS, MAX_HIKES_PER_SOURCE, REQUEST_DELAY_SECONDS, USER_AGENT
from models import Hike
from scrapers.hiking.base import HikingScraper

logger = logging.getLogger(__name__)

# SchweizMobil API endpoints
ROUTES_API_URL = "https://map.schweizmobil.ch/api/4/query"
ROUTE_DETAIL_URL = "https://map.schweizmobil.ch/api/4/route/{route_id}"
ROUTES_PAGE_URL = "https://www.schweizmobil.ch/de/wanderland/routen.html"
ROUTE_WEB_BASE = "https://www.schweizmobil.ch/de/wanderland/route-{route_id}"

# SAC-Schwierigkeitsskala Mapping
SAC_DIFFICULTY_MAP: dict[str, str] = {
    "T1": "T1",
    "T2": "T2",
    "T3": "T3",
    "T4": "T4",
    "T5": "T5",
    "T6": "T6",
}

# Bekannte Schweizer Kantone nach Region
REGION_CANTON_MAP: dict[str, str] = {
    "Zürich": "ZH",
    "Bern": "BE",
    "Berner Oberland": "BE",
    "Luzern": "LU",
    "Zentralschweiz": "LU",
    "Uri": "UR",
    "Schwyz": "SZ",
    "Graubünden": "GR",
    "Engadin": "GR",
    "Wallis": "VS",
    "Tessin": "TI",
    "Waadt": "VD",
    "Genf": "GE",
    "St. Gallen": "SG",
    "Appenzell": "AR",
    "Thurgau": "TG",
    "Aargau": "AG",
    "Basel": "BS",
    "Solothurn": "SO",
    "Freiburg": "FR",
    "Jura": "JU",
    "Glarus": "GL",
    "Neuenburg": "NE",
    "Schaffhausen": "SH",
    "Zug": "ZG",
    "Nidwalden": "NW",
    "Obwalden": "OW",
}


def _guess_canton(region: str) -> str:
    """Versucht einen Kanton aus dem Regionsnamen abzuleiten."""
    for key, canton in REGION_CANTON_MAP.items():
        if key.lower() in region.lower():
            return canton
    return "CH"


def _truncate(text: str | None, max_len: int = 500) -> str | None:
    """Kürzt Text auf max_len Zeichen."""
    if not text:
        return text
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


class SchweizMobilScraper(HikingScraper):
    """Scraper für SchweizMobil Wanderland Routen."""

    name = "SchweizMobil"

    async def fetch(self, region: str | None = None) -> list[Hike]:
        """Holt Wanderrouten von SchweizMobil.

        Versucht zuerst die Map-API, dann die Webseite, und fällt
        im Fehlerfall auf kuratierte Schweizer Routen zurück.
        """
        try:
            hikes = await self._fetch_from_api(region)
            if hikes:
                return hikes[:MAX_HIKES_PER_SOURCE]
        except Exception:
            logger.warning(
                "%s: API-Abruf fehlgeschlagen, versuche Webseiten-Scraping",
                self.name,
            )

        try:
            hikes = await self._fetch_from_website(region)
            if hikes:
                return hikes[:MAX_HIKES_PER_SOURCE]
        except Exception:
            logger.warning(
                "%s: Webseiten-Scraping fehlgeschlagen, verwende Fallback-Routen",
                self.name,
            )

        try:
            return self._get_fallback_routes(region)[:MAX_HIKES_PER_SOURCE]
        except Exception:
            logger.exception("%s: Auch Fallback-Routen fehlgeschlagen", self.name)
            return []

    # ------------------------------------------------------------------
    # API-basierter Abruf
    # ------------------------------------------------------------------

    async def _fetch_from_api(self, region: str | None = None) -> list[Hike]:
        """Versucht Routen über die SchweizMobil Map-API zu laden."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
            "Referer": "https://map.schweizmobil.ch/",
            "Origin": "https://map.schweizmobil.ch",
        }

        hikes: list[Hike] = []

        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
            headers=headers,
            follow_redirects=True,
        ) as client:
            # SchweizMobil Wanderland route query
            params: dict[str, Any] = {
                "type": "route",
                "land": "wanderland",
                "lang": "de",
            }
            if region:
                params["region"] = region

            response = await client.get(ROUTES_API_URL, params=params)
            response.raise_for_status()

            data = response.json()
            routes = data if isinstance(data, list) else data.get("routes", data.get("features", []))

            for route_data in routes:
                await asyncio.sleep(REQUEST_DELAY_SECONDS)
                hike = self._parse_api_route(route_data)
                if hike:
                    hikes.append(hike)
                if len(hikes) >= MAX_HIKES_PER_SOURCE:
                    break

        return hikes

    def _parse_api_route(self, route_data: dict[str, Any]) -> Hike | None:
        """Parsed eine einzelne Route aus der API-Antwort."""
        try:
            props = route_data.get("properties", route_data)
            route_id = str(props.get("id", props.get("route_id", "")))
            title = props.get("title", props.get("name", ""))
            if not title:
                return None

            # Schwierigkeit
            raw_difficulty = str(props.get("difficulty", props.get("sac_scale", "T2")))
            difficulty = self.normalize_difficulty(raw_difficulty)

            # Dauer in Minuten
            duration_raw = props.get("duration", props.get("time", 0))
            if isinstance(duration_raw, str):
                # Format "3:30" oder "210"
                if ":" in duration_raw:
                    parts = duration_raw.split(":")
                    duration_minutes = int(parts[0]) * 60 + int(parts[1])
                else:
                    duration_minutes = int(float(duration_raw))
            else:
                # Könnte Minuten oder Stunden sein
                duration_val = float(duration_raw)
                duration_minutes = int(duration_val) if duration_val > 20 else int(duration_val * 60)

            # Distanz
            distance_raw = props.get("distance", props.get("length", 0))
            distance_km = float(distance_raw)
            # Falls in Metern angegeben
            if distance_km > 500:
                distance_km = distance_km / 1000

            region = props.get("region", props.get("area", "Schweiz"))
            canton = props.get("canton", _guess_canton(str(region)))

            source_url = ROUTE_WEB_BASE.format(route_id=route_id) if route_id else ROUTES_PAGE_URL

            return Hike(
                title=title,
                difficulty=difficulty,
                duration_minutes=max(duration_minutes, 1),
                distance_km=round(distance_km, 1),
                region=str(region),
                canton=str(canton),
                source="schweizmobil",
                source_url=source_url,
                elevation_gain_m=_safe_int(props.get("ascent", props.get("elevation_gain"))),
                elevation_loss_m=_safe_int(props.get("descent", props.get("elevation_loss"))),
                start_point=props.get("start", props.get("start_point")),
                end_point=props.get("end", props.get("end_point")),
                description=_truncate(props.get("description", props.get("text"))),
                image_url=props.get("image", props.get("image_url")),
                latitude_start=_safe_float(props.get("lat", props.get("latitude"))),
                longitude_start=_safe_float(props.get("lng", props.get("longitude"))),
                gpx_url=props.get("gpx_url"),
                tags=_build_tags(props),
                external_id=f"schweizmobil-{route_id}" if route_id else None,
            )
        except Exception:
            logger.debug("Konnte Route nicht parsen: %s", route_data, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Webseiten-Scraping als Fallback
    # ------------------------------------------------------------------

    async def _fetch_from_website(self, region: str | None = None) -> list[Hike]:
        """Scrapet Routen von der SchweizMobil-Webseite."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "de-CH,de;q=0.9",
        }

        hikes: list[Hike] = []

        async with httpx.AsyncClient(
            timeout=HTTP_TIMEOUT_SECONDS,
            headers=headers,
            follow_redirects=True,
        ) as client:
            response = await client.get(ROUTES_PAGE_URL)
            response.raise_for_status()
            html = response.text

            # Versuche JSON-Daten aus Script-Tags zu extrahieren
            json_matches = re.findall(
                r'<script[^>]*type=["\']application/(?:ld\+)?json["\'][^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            )

            for json_str in json_matches:
                try:
                    data = json.loads(json_str)
                    items = data if isinstance(data, list) else [data]
                    for item in items:
                        hike = self._parse_web_route(item)
                        if hike:
                            hikes.append(hike)
                except (json.JSONDecodeError, TypeError):
                    continue

            # Versuche auch eingebettete Daten-Attribute zu finden
            route_pattern = re.compile(
                r'data-route=["\'](\{.*?\})["\']',
                re.DOTALL,
            )
            for match in route_pattern.finditer(html):
                try:
                    route_data = json.loads(match.group(1))
                    hike = self._parse_web_route(route_data)
                    if hike:
                        hikes.append(hike)
                except (json.JSONDecodeError, TypeError):
                    continue

        return hikes

    def _parse_web_route(self, data: dict[str, Any]) -> Hike | None:
        """Parsed eine Route aus Webseiten-Daten."""
        try:
            title = data.get("name", data.get("title", ""))
            if not title:
                return None

            difficulty_raw = data.get("difficulty", data.get("sac_scale", "T2"))
            difficulty = self.normalize_difficulty(str(difficulty_raw))

            duration_minutes = _safe_int(data.get("duration", data.get("timeRequired"))) or 120
            distance_km = _safe_float(data.get("distance", data.get("length"))) or 10.0
            if distance_km > 500:
                distance_km /= 1000

            region = data.get("region", data.get("area", "Schweiz"))
            canton = _guess_canton(str(region))

            url = data.get("url", data.get("source_url", ROUTES_PAGE_URL))
            if url and not url.startswith("http"):
                url = f"https://www.schweizmobil.ch{url}"

            return Hike(
                title=title,
                difficulty=difficulty,
                duration_minutes=max(duration_minutes, 1),
                distance_km=round(distance_km, 1),
                region=str(region),
                canton=canton,
                source="schweizmobil",
                source_url=url,
                elevation_gain_m=_safe_int(data.get("ascent")),
                elevation_loss_m=_safe_int(data.get("descent")),
                start_point=data.get("start"),
                end_point=data.get("end"),
                description=_truncate(data.get("description")),
                image_url=data.get("image"),
                tags=_build_tags(data),
                external_id=f"schweizmobil-web-{data.get('id', '')}" if data.get("id") else None,
            )
        except Exception:
            logger.debug("Konnte Webseiten-Route nicht parsen: %s", data, exc_info=True)
            return None

    # ------------------------------------------------------------------
    # Fallback: Kuratierte Schweizer Routen
    # ------------------------------------------------------------------

    def _get_fallback_routes(self, region: str | None = None) -> list[Hike]:
        """Gibt kuratierte Schweizer Wanderrouten als Fallback zurück.

        Der Pool enthält 30+ Routen. Pro Woche werden 10 verschiedene
        ausgewählt, basierend auf der Kalenderwoche (rotierend).
        """
        all_routes = self._all_curated_routes()

        # Optional nach Region filtern
        if region:
            region_lower = region.lower()
            filtered = [
                h for h in all_routes
                if region_lower in h.region.lower()
                or region_lower in h.canton.lower()
                or any(region_lower in tag.lower() for tag in h.tags)
            ]
            pool = filtered if filtered else all_routes
        else:
            pool = all_routes

        # Wöchentliche Rotation: Kalenderwoche als Seed
        from datetime import datetime
        from config import TZ
        week_number = datetime.now(TZ).isocalendar()[1]
        start_idx = (week_number * 7) % len(pool)

        # Rotiere die Liste und nimm die ersten 10
        rotated = pool[start_idx:] + pool[:start_idx]
        return rotated[:10]

    def _all_curated_routes(self) -> list[Hike]:
        """Pool aller kuratierten Schweizer Wanderrouten (geladen aus JSON)."""
        from pathlib import Path

        # Lade Route IDs aus JSON
        data_file = Path(__file__).parent.parent.parent / "data" / "schweizmobil_routes.json"
        try:
            routes_data = json.loads(data_file.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Konnte Routen-JSON nicht laden: {e}")
            return []

        # Erstelle Hike-Objekte aus den Route-Daten
        routes = []
        for route_info in routes_data:
            try:
                hike = Hike(
                    title=route_info.get("title", f"Route {route_info['id']}"),
                    difficulty=self.normalize_difficulty("T2"),
                    duration_minutes=route_info.get("duration_minutes", 240),
                    distance_km=route_info.get("distance_km", 15.0),
                    region=route_info.get("region", "Switzerland"),
                    canton=route_info.get("canton", "CH"),
                    source="schweizmobil",
                    source_url=f"https://www.schweizmobil.ch/de/wanderland/route-{route_info['id']}",
                    external_id=f"schweizmobil-{route_info['id']}",
                )
                routes.append(hike)
            except Exception as e:
                logger.warning(f"Konnte Route {route_info.get('id')} nicht erstellen: {e}")
                continue

        return routes


# ------------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------------


def _safe_int(value: Any) -> int | None:
    """Konvertiert einen Wert sicher zu int oder gibt None zurück."""
    if value is None:
        return None
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _safe_float(value: Any) -> float | None:
    """Konvertiert einen Wert sicher zu float oder gibt None zurück."""
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def _build_tags(props: dict[str, Any]) -> list[str]:
    """Erstellt eine Tag-Liste aus Routeneigenschaften."""
    tags: list[str] = []

    if props.get("type"):
        tags.append(str(props["type"]))
    if props.get("sac_scale"):
        tags.append(f"SAC {props['sac_scale']}")
    if props.get("landscape"):
        tags.append(str(props["landscape"]))
    if props.get("season"):
        tags.append(str(props["season"]))

    # Kategorien/Labels falls vorhanden
    for key in ("categories", "labels", "tags"):
        val = props.get(key)
        if isinstance(val, list):
            tags.extend(str(v) for v in val)
        elif isinstance(val, str):
            tags.append(val)

    return tags
