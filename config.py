"""Konfiguration: Datums-Logik, Umgebungsvariablen, Regionen."""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

# Zeitzone
TZ = ZoneInfo("Europe/Zurich")

# HTTP
HTTP_TIMEOUT_SECONDS = 30
MAX_EVENTS_PER_SOURCE = 100
MAX_HIKES_PER_SOURCE = 30
REQUEST_DELAY_SECONDS = 1.0
USER_AGENT = "WeekendEventsBot/1.0"

# API-Keys
EVENTFROG_API_KEY = os.getenv("EVENTFROG_API_KEY")
MYSWITZERLAND_API_KEY = os.getenv("MYSWITZERLAND_API_KEY")
OUTDOORACTIVE_API_KEY = os.getenv("OUTDOORACTIVE_API_KEY")
KOMOOT_EMAIL = os.getenv("KOMOOT_EMAIL")
KOMOOT_PASSWORD = os.getenv("KOMOOT_PASSWORD")

# Schweizer Kantone
CH_CANTONS = [
    "ZH", "BE", "LU", "UR", "SZ", "OW", "NW", "GL",
    "ZG", "FR", "SO", "BS", "BL", "SH", "AR", "AI",
    "SG", "GR", "AG", "TG", "TI", "VD", "VS", "NE", "GE", "JU",
]

# Bounding Box Schweiz (WGS84): lon_min, lat_min, lon_max, lat_max
CH_BBOX = (5.96, 45.82, 10.49, 47.81)


def get_next_weekend(reference: date | None = None) -> tuple[date, date]:
    """Berechnet das nächste Wochenende (Samstag + Sonntag).

    - Mo–Do: nächster Sa/So
    - Fr: aktuelles Wochenende (Sa/So)
    - Sa: aktuelles Wochenende (Sa/So)
    - So: aktueller Sonntag + nächster Samstag wäre komisch → aktueller So noch
    """
    if reference is None:
        reference = datetime.now(TZ).date()

    weekday = reference.weekday()  # 0=Mo, 6=So

    if weekday == 5:  # Samstag
        saturday = reference
    elif weekday == 6:  # Sonntag
        saturday = reference - timedelta(days=1)
    else:
        # Mo(0)–Fr(4): nächster Samstag
        days_until_saturday = 5 - weekday
        saturday = reference + timedelta(days=days_until_saturday)

    sunday = saturday + timedelta(days=1)
    return saturday, sunday


def weekend_start_datetime(saturday: date) -> datetime:
    return datetime(saturday.year, saturday.month, saturday.day, 0, 0, 0, tzinfo=TZ)


def weekend_end_datetime(sunday: date) -> datetime:
    return datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=TZ)
