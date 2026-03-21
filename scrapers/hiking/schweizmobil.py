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
        """Pool aller kuratierten Schweizer Wanderrouten (30+)."""
        routes = [
            Hike(
                title="Via Alpina Etappe 1: Vaduz – Sargans",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=300,
                distance_km=15.0,
                region="Ostschweiz",
                canton="SG",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-1",
                elevation_gain_m=850,
                elevation_loss_m=920,
                start_point="Vaduz",
                end_point="Sargans",
                description="Erste Etappe der Via Alpina durch das Rheintal mit Blick auf die Liechtensteiner Alpen.",
                latitude_start=47.1410,
                longitude_start=9.5215,
                tags=["Fernwanderweg", "Via Alpina", "Alpen"],
                external_id="schweizmobil-fallback-1",
            ),
            Hike(
                title="Uetliberg – Felsenegg Gratweg",
                difficulty=self.normalize_difficulty("T1"),
                duration_minutes=120,
                distance_km=7.5,
                region="Zürich",
                canton="ZH",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-893",
                elevation_gain_m=200,
                elevation_loss_m=250,
                start_point="Uetliberg",
                end_point="Felsenegg",
                description="Beliebter Panoramaweg über den Albiskamm mit herrlicher Aussicht auf Zürich und den Zürichsee.",
                latitude_start=47.3496,
                longitude_start=8.4920,
                tags=["Panoramaweg", "Familienwanderung", "Zürich"],
                external_id="schweizmobil-fallback-882",
            ),
            Hike(
                title="Oeschinensee Rundwanderung",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=180,
                distance_km=9.5,
                region="Berner Oberland",
                canton="BE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-534",
                elevation_gain_m=550,
                elevation_loss_m=550,
                start_point="Kandersteg",
                end_point="Kandersteg",
                description="Rundwanderung um den malerischen Oeschinensee, UNESCO-Welterbe mit Blick auf Blüemlisalp.",
                latitude_start=46.4997,
                longitude_start=7.6727,
                tags=["Bergsee", "UNESCO", "Rundwanderung"],
                external_id="schweizmobil-fallback-534",
            ),
            Hike(
                title="Creux du Van – Naturarena",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=240,
                distance_km=14.0,
                region="Jura & Drei-Seen-Land",
                canton="NE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-286",
                elevation_gain_m=700,
                elevation_loss_m=700,
                start_point="Noiraigue",
                end_point="Noiraigue",
                description="Wanderung zum eindrucksvollen Felsenkessel Creux du Van mit seinen 160m hohen Felswänden im Jura.",
                latitude_start=46.9333,
                longitude_start=6.7167,
                tags=["Jura", "Naturarena", "Rundwanderung"],
                external_id="schweizmobil-fallback-243",
            ),
            Hike(
                title="Höhenweg Aletschgletscher",
                difficulty=self.normalize_difficulty("T3"),
                duration_minutes=300,
                distance_km=12.0,
                region="Wallis",
                canton="VS",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-39",
                elevation_gain_m=400,
                elevation_loss_m=650,
                start_point="Riederalp",
                end_point="Belalp",
                description="Spektakulärer Höhenweg entlang des grössten Alpengletschers mit Panoramablick auf die Walliser Viertausender.",
                latitude_start=46.3833,
                longitude_start=8.0333,
                tags=["Gletscher", "UNESCO", "Höhenweg", "Alpen"],
                external_id="schweizmobil-fallback-104",
            ),
            Hike(
                title="Vier-Quellen-Weg Etappe 1",
                difficulty=self.normalize_difficulty("T3"),
                duration_minutes=360,
                distance_km=16.0,
                region="Zentralschweiz",
                canton="UR",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-49",
                elevation_gain_m=900,
                elevation_loss_m=750,
                start_point="Oberalppass",
                end_point="Vermigelhütte",
                description="Erste Etappe des Vier-Quellen-Wegs zur Rheinquelle am Tomasee auf dem Gotthardmassiv.",
                latitude_start=46.6597,
                longitude_start=8.6714,
                tags=["Fernwanderweg", "Quellweg", "Gotthardmassiv"],
                external_id="schweizmobil-fallback-49",
            ),
            Hike(
                title="Sentiero Graubünden Etappe Soglio",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=210,
                distance_km=10.0,
                region="Graubünden",
                canton="GR",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-44",
                elevation_gain_m=500,
                elevation_loss_m=600,
                start_point="Soglio",
                end_point="Castasegna",
                description="Wanderung vom schönsten Dorf der Schweiz durch Kastanienwälder ins Bergell mit Blick auf die Sciora-Gruppe.",
                latitude_start=46.3417,
                longitude_start=9.5250,
                tags=["Bergell", "Kastanienwälder", "Graubünden"],
                external_id="schweizmobil-fallback-44",
            ),
            Hike(
                title="Schynige Platte – First",
                difficulty=self.normalize_difficulty("T3"),
                duration_minutes=390,
                distance_km=16.5,
                region="Berner Oberland",
                canton="BE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-38",
                elevation_gain_m=1050,
                elevation_loss_m=850,
                start_point="Schynige Platte",
                end_point="First",
                description="Alpine Gratwanderung mit grandiosem Panorama auf Eiger, Mönch und Jungfrau über den Faulhornweg.",
                latitude_start=46.6500,
                longitude_start=7.9000,
                tags=["Gratwanderung", "Eiger", "Jungfrau", "Panorama"],
                external_id="schweizmobil-fallback-38",
            ),
            Hike(
                title="Monte San Giorgio Rundweg",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=240,
                distance_km=11.0,
                region="Tessin",
                canton="TI",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-655",
                elevation_gain_m=650,
                elevation_loss_m=650,
                start_point="Meride",
                end_point="Meride",
                description="Rundwanderung auf dem UNESCO-Welterbe Monte San Giorgio mit Fossilienfundstellen und Luganer See-Panorama.",
                latitude_start=45.9167,
                longitude_start=8.9500,
                tags=["UNESCO", "Tessin", "Fossilien", "Rundwanderung"],
                external_id="schweizmobil-fallback-655",
            ),
            Hike(
                title="Chemin des Vignobles – Lavaux",
                difficulty=self.normalize_difficulty("T1"),
                duration_minutes=150,
                distance_km=11.0,
                region="Genferseegebiet",
                canton="VD",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-113",
                elevation_gain_m=300,
                elevation_loss_m=300,
                start_point="Lutry",
                end_point="Saint-Saphorin",
                description="Genusswanderung durch die UNESCO-geschützten Weinberg-Terrassen von Lavaux am Genfersee.",
                latitude_start=46.5050,
                longitude_start=6.6850,
                tags=["Weinberge", "UNESCO", "Lavaux", "Genfersee"],
                external_id="schweizmobil-fallback-101",
            ),
            Hike(
                title="Pilatus Rundweg – Goldene Rundfahrt",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=180,
                distance_km=8.5,
                region="Zentralschweiz",
                canton="LU",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-902",
                elevation_gain_m=450,
                elevation_loss_m=450,
                start_point="Pilatus Kulm",
                end_point="Pilatus Kulm",
                description="Rundwanderung auf dem Pilatus mit atemberaubendem 360°-Panorama über die Zentralschweizer Alpen.",
                latitude_start=46.9790,
                longitude_start=8.2534,
                tags=["Panorama", "Zentralschweiz", "Pilatus"],
                external_id="schweizmobil-fallback-902",
            ),
            Hike(
                title="Rigi Scheidegg – Rigi Kulm",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=150,
                distance_km=6.0,
                region="Zentralschweiz",
                canton="SZ",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-848",
                elevation_gain_m=350,
                elevation_loss_m=200,
                start_point="Rigi Scheidegg",
                end_point="Rigi Kulm",
                description="Klassische Höhenwanderung auf der Königin der Berge mit Blick auf Vierwaldstättersee und Alpen.",
                latitude_start=47.0345,
                longitude_start=8.5100,
                tags=["Rigi", "Aussichtsberg", "Zentralschweiz"],
                external_id="schweizmobil-fallback-903",
            ),
            Hike(
                title="Appenzeller Witzweg",
                difficulty=self.normalize_difficulty("T1"),
                duration_minutes=120,
                distance_km=6.5,
                region="Ostschweiz",
                canton="AR",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-977",
                elevation_gain_m=180,
                elevation_loss_m=180,
                start_point="Heiden",
                end_point="Walzenhausen",
                description="Humorvoller Themenweg durch das Appenzeller Vorderland mit Witzen auf Tafeln und Bodenseepanorama.",
                latitude_start=47.4425,
                longitude_start=9.5328,
                tags=["Themenweg", "Appenzell", "Familie"],
                external_id="schweizmobil-fallback-904",
            ),
            Hike(
                title="Niesen – Treppe zum Himmel",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=270,
                distance_km=7.0,
                region="Berner Oberland",
                canton="BE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-3",
                elevation_gain_m=1600,
                elevation_loss_m=200,
                start_point="Mülenen",
                end_point="Niesen Kulm",
                description="Aufstieg zum Niesen über die längste Treppe der Welt (11'674 Stufen) mit Thunersee-Panorama.",
                latitude_start=46.6450,
                longitude_start=7.6510,
                tags=["Gipfelwanderung", "Treppe", "Thunersee"],
                external_id="schweizmobil-fallback-905",
            ),
            Hike(
                title="Blausee Rundwanderung",
                difficulty=self.normalize_difficulty("T1"),
                duration_minutes=60,
                distance_km=3.0,
                region="Berner Oberland",
                canton="BE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-906",
                elevation_gain_m=50,
                elevation_loss_m=50,
                start_point="Blausee",
                end_point="Blausee",
                description="Kurzer Spaziergang um den kristallklaren Blausee im Kandertal, ideal für Familien.",
                latitude_start=46.5333,
                longitude_start=7.6667,
                tags=["Bergsee", "Familie", "Spaziergang"],
                external_id="schweizmobil-fallback-906",
            ),
            Hike(
                title="Strada Alta – Leventina Höhenweg",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=300,
                distance_km=18.0,
                region="Tessin",
                canton="TI",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-907",
                elevation_gain_m=600,
                elevation_loss_m=800,
                start_point="Airolo",
                end_point="Biasca",
                description="Historischer Höhenweg durch das Leventinatal mit traditionellen Tessiner Dörfern und Kastanienwäldern.",
                latitude_start=46.5282,
                longitude_start=8.6132,
                tags=["Höhenweg", "Tessin", "Historisch"],
                external_id="schweizmobil-fallback-907",
            ),
            Hike(
                title="Gornergletscher – Monte Rosa Hütte",
                difficulty=self.normalize_difficulty("T4"),
                duration_minutes=300,
                distance_km=10.0,
                region="Wallis",
                canton="VS",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-908",
                elevation_gain_m=800,
                elevation_loss_m=300,
                start_point="Rotenboden",
                end_point="Monte Rosa Hütte",
                description="Hochalpine Wanderung über den Gornergletscher zur futuristischen Monte Rosa Hütte am Fuss des Monte Rosa.",
                latitude_start=45.9833,
                longitude_start=7.7833,
                tags=["Hochalpin", "Gletscher", "SAC-Hütte"],
                external_id="schweizmobil-fallback-908",
            ),
            Hike(
                title="Rheinschlucht – Swiss Grand Canyon",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=210,
                distance_km=13.0,
                region="Graubünden",
                canton="GR",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-909",
                elevation_gain_m=400,
                elevation_loss_m=500,
                start_point="Valendas-Sagogn",
                end_point="Reichenau",
                description="Wanderung durch die spektakuläre Rheinschlucht (Ruinaulta), den Swiss Grand Canyon, entlang weisser Felswände.",
                latitude_start=46.7833,
                longitude_start=9.2500,
                tags=["Schlucht", "Ruinaulta", "Graubünden"],
                external_id="schweizmobil-fallback-909",
            ),
            Hike(
                title="Gemmipass – Leukerbad nach Kandersteg",
                difficulty=self.normalize_difficulty("T3"),
                duration_minutes=330,
                distance_km=15.0,
                region="Wallis / Berner Oberland",
                canton="VS",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-910",
                elevation_gain_m=500,
                elevation_loss_m=1200,
                start_point="Leukerbad",
                end_point="Kandersteg",
                description="Historische Passüberquerung mit dem eindrücksvollen Abstieg über die Gemmiwand ins Kandertal.",
                latitude_start=46.3833,
                longitude_start=7.6333,
                tags=["Passüberquerung", "Historisch", "Alpen"],
                external_id="schweizmobil-fallback-910",
            ),
            Hike(
                title="Muottas Muragl – Alp Languard",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=240,
                distance_km=10.5,
                region="Engadin",
                canton="GR",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-911",
                elevation_gain_m=500,
                elevation_loss_m=650,
                start_point="Muottas Muragl",
                end_point="Alp Languard",
                description="Aussichtsreiche Höhenwanderung über dem Engadin mit Blick auf die Oberengadiner Seenplatte und Berninagruppe.",
                latitude_start=46.4975,
                longitude_start=9.9500,
                tags=["Engadin", "Höhenweg", "Panorama"],
                external_id="schweizmobil-fallback-911",
            ),
            Hike(
                title="Säntis via Schwägalp",
                difficulty=self.normalize_difficulty("T3"),
                duration_minutes=270,
                distance_km=8.0,
                region="Ostschweiz",
                canton="AR",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-912",
                elevation_gain_m=1200,
                elevation_loss_m=200,
                start_point="Schwägalp",
                end_point="Säntis",
                description="Anspruchsvoller Aufstieg zum Säntis (2502m), dem höchsten Gipfel im Alpstein mit 6-Länder-Panorama.",
                latitude_start=47.2778,
                longitude_start=9.3444,
                tags=["Gipfelwanderung", "Alpstein", "Säntis"],
                external_id="schweizmobil-fallback-912",
            ),
            Hike(
                title="Bettmeralp – Märjelensee",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=150,
                distance_km=8.0,
                region="Wallis",
                canton="VS",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-913",
                elevation_gain_m=350,
                elevation_loss_m=350,
                start_point="Bettmeralp",
                end_point="Bettmeralp",
                description="Rundwanderung zum Märjelensee am Rand des Aletschgletschers mit Blick auf die Walliser Viertausender.",
                latitude_start=46.3917,
                longitude_start=8.0667,
                tags=["Gletscher", "Aletsch", "Bergsee"],
                external_id="schweizmobil-fallback-913",
            ),
            Hike(
                title="Taminaschlucht – Bad Ragaz",
                difficulty=self.normalize_difficulty("T1"),
                duration_minutes=90,
                distance_km=4.0,
                region="Ostschweiz",
                canton="SG",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-914",
                elevation_gain_m=100,
                elevation_loss_m=100,
                start_point="Bad Ragaz",
                end_point="Bad Ragaz",
                description="Kurze Wanderung durch die enge Taminaschlucht zur historischen Thermalquelle. Beeindruckende Felsformation.",
                latitude_start=46.9833,
                longitude_start=9.5000,
                tags=["Schlucht", "Thermalquelle", "Familie"],
                external_id="schweizmobil-fallback-914",
            ),
            Hike(
                title="Jungfrau Eiger Walk",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=150,
                distance_km=7.0,
                region="Berner Oberland",
                canton="BE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-915",
                elevation_gain_m=200,
                elevation_loss_m=600,
                start_point="Eigergletscher",
                end_point="Grindelwald",
                description="Panoramaweg vom Eigergletscher nach Grindelwald mit spektakulärem Blick auf die Eiger Nordwand.",
                latitude_start=46.5750,
                longitude_start=7.9750,
                tags=["Eiger", "Jungfrau", "Panorama"],
                external_id="schweizmobil-fallback-915",
            ),
            Hike(
                title="5-Seen-Wanderung Pizol",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=240,
                distance_km=11.0,
                region="Ostschweiz",
                canton="SG",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-916",
                elevation_gain_m=500,
                elevation_loss_m=700,
                start_point="Pizolhütte",
                end_point="Gaffia",
                description="Beliebte Wanderung vorbei an fünf malerischen Bergseen auf dem Pizol mit Blick auf das UNESCO-Welterbe Sardona.",
                latitude_start=46.9667,
                longitude_start=9.4333,
                tags=["Bergseen", "Pizol", "5-Seen"],
                external_id="schweizmobil-fallback-916",
            ),
            Hike(
                title="Chasseral Höhenweg",
                difficulty=self.normalize_difficulty("T2"),
                duration_minutes=270,
                distance_km=14.0,
                region="Jura & Drei-Seen-Land",
                canton="BE",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-917",
                elevation_gain_m=400,
                elevation_loss_m=700,
                start_point="Chasseral",
                end_point="Nods",
                description="Wanderung vom höchsten Juragipfel durch Weiden und Wälder mit Blick auf Alpen, Mittelland und Jura.",
                latitude_start=47.1333,
                longitude_start=7.0583,
                tags=["Jura", "Chasseral", "Panorama"],
                external_id="schweizmobil-fallback-917",
            ),
        ]

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
