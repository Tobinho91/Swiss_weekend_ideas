"""Datenmodelle für Events und Wanderungen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

EventCategory = Literal[
    "Konzerte",
    "Kultur & Kunst",
    "Sport",
    "Märkte & Feste",
    "Natur & Outdoor",
    "Familie",
    "Gastronomie",
    "Sonstiges",
]

HikeDifficulty = Literal["Leicht", "Mittel", "Schwer", "Sehr schwer"]


@dataclass
class Event:
    """Ein normalisiertes Event aus einer beliebigen Quelle."""

    title: str
    start_datetime: datetime  # timezone-aware, Europe/Zurich
    location_name: str
    city: str
    canton: str  # z.B. "ZH", "BE"
    category: EventCategory
    source: str  # z.B. "eventfrog", "myswitzerland"
    source_url: str
    end_datetime: Optional[datetime] = None
    description: Optional[str] = None  # max. 500 Zeichen
    image_url: Optional[str] = None
    price: Optional[str] = None  # z.B. "CHF 20", "Gratis"
    is_free: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    external_id: Optional[str] = None  # für Deduplication

    @property
    def day_label(self) -> str:
        """Gibt 'Samstag' oder 'Sonntag' zurück."""
        days = {5: "Samstag", 6: "Sonntag"}
        return days.get(self.start_datetime.weekday(), self.start_datetime.strftime("%A"))

    @property
    def time_label(self) -> str:
        return self.start_datetime.strftime("%H:%M")

    @property
    def price_label(self) -> str:
        if self.is_free:
            return "Gratis"
        return self.price or ""


@dataclass
class Hike:
    """Eine normalisierte Wanderroute aus einer beliebigen Quelle."""

    title: str
    difficulty: HikeDifficulty
    duration_minutes: int
    distance_km: float
    region: str
    canton: str
    source: str  # z.B. "komoot", "schweizmobil"
    source_url: str
    elevation_gain_m: Optional[int] = None
    elevation_loss_m: Optional[int] = None
    start_point: Optional[str] = None
    end_point: Optional[str] = None
    description: Optional[str] = None  # max. 500 Zeichen
    image_url: Optional[str] = None
    latitude_start: Optional[float] = None
    longitude_start: Optional[float] = None
    gpx_url: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    external_id: Optional[str] = None

    @property
    def duration_label(self) -> str:
        hours, minutes = divmod(self.duration_minutes, 60)
        if hours and minutes:
            return f"{hours}h{minutes:02d}"
        if hours:
            return f"{hours}h"
        return f"{minutes}min"

    @property
    def duration_bucket(self) -> str:
        if self.duration_minutes < 120:
            return "lt2h"
        if self.duration_minutes <= 240:
            return "2to4h"
        return "gt4h"

    @property
    def distance_bucket(self) -> str:
        if self.distance_km < 5:
            return "lt5km"
        if self.distance_km <= 15:
            return "5to15km"
        return "gt15km"
