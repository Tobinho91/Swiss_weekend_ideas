#!/usr/bin/env python3
"""
Automated route addition script for GitHub Actions.
Appends 10 new curated hiking routes to data/schweizmobil_routes.json each month.
"""

import json
import random
from datetime import datetime
from pathlib import Path

# Curated route candidates for monthly additions
ROUTES_CANDIDATES = [
    {
        "id": 25,
        "title": "Säntis-Panoramaweg",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 16.0
    },
    {
        "id": 26,
        "title": "Appenzeller Alproute",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 240,
        "distance_km": 14.0
    },
    {
        "id": 28,
        "title": "Säntis via Schwägalp",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 15.0
    },
    {
        "id": 30,
        "title": "Säntis Rundgang",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 180,
        "distance_km": 10.0
    },
    {
        "id": 45,
        "title": "Lägern Höhenweg",
        "region": "Zürich",
        "canton": "ZH",
        "duration_minutes": 240,
        "distance_km": 14.0
    },
    {
        "id": 50,
        "title": "Säntis Wanderung",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 360,
        "distance_km": 18.0
    },
    {
        "id": 51,
        "title": "Säntis Bergtour",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 16.0
    },
    {
        "id": 52,
        "title": "Säntis Kulm",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 240,
        "distance_km": 12.0
    },
    {
        "id": 53,
        "title": "Säntis Panorama",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 15.0
    },
    {
        "id": 54,
        "title": "Säntis Rundtour",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 360,
        "distance_km": 20.0
    },
    {
        "id": 55,
        "title": "Säntis Höhenweg",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 17.0
    },
    {
        "id": 56,
        "title": "Appenzeller Alpstein",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 360,
        "distance_km": 19.0
    },
    {
        "id": 60,
        "title": "Säntis Etappe",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 240,
        "distance_km": 13.0
    },
    {
        "id": 65,
        "title": "Säntis Klassiker",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 16.0
    },
    {
        "id": 70,
        "title": "Säntis Trail",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 240,
        "distance_km": 14.0
    },
    {
        "id": 75,
        "title": "Säntis Naturweg",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 15.0
    },
    {
        "id": 80,
        "title": "Säntis Waldweg",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 240,
        "distance_km": 12.0
    },
    {
        "id": 85,
        "title": "Säntis Fernblick",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 16.0
    },
    {
        "id": 90,
        "title": "Säntis Gipfelweg",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 360,
        "distance_km": 18.0
    },
    {
        "id": 95,
        "title": "Säntis Sternenwanderung",
        "region": "Appenzell",
        "canton": "AR",
        "duration_minutes": 300,
        "distance_km": 15.0
    }
]


def get_existing_ids(json_file: Path) -> set:
    """Get all existing route IDs from the JSON file."""
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
        return {int(route["id"]) for route in data}
    except Exception:
        return set()


def add_routes_to_json(num_routes: int = 10) -> bool:
    """
    Add random routes to data/schweizmobil_routes.json

    Args:
        num_routes: Number of routes to add

    Returns:
        True if successful, False otherwise
    """
    try:
        json_file = Path("data/schweizmobil_routes.json")

        if not json_file.exists():
            print("[ERROR] File not found: data/schweizmobil_routes.json")
            return False

        # Load existing routes
        existing_data = json.loads(json_file.read_text(encoding="utf-8"))
        existing_ids = get_existing_ids(json_file)

        # Filter candidates to exclude already-added routes
        available_candidates = [
            route for route in ROUTES_CANDIDATES
            if route["id"] not in existing_ids
        ]

        if not available_candidates:
            print("[WARN] All candidate routes have already been added!")
            return False

        # Select random routes
        selected = random.sample(
            available_candidates,
            min(num_routes, len(available_candidates))
        )

        # Append to existing data
        existing_data.extend(selected)

        # Write back to file
        json_file.write_text(
            json.dumps(existing_data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

        print(f"[OK] Added {len(selected)} new hiking routes")
        print(f"   Route IDs: {', '.join(str(r['id']) for r in selected)}")
        print(f"   Routes added:")
        for i, route in enumerate(selected, 1):
            print(f"   {i:2d}. {route['title']} ({route['canton']})")

        return True

    except Exception as e:
        print(f"[ERROR] Error adding routes: {e}")
        return False


if __name__ == "__main__":
    success = add_routes_to_json(10)
    exit(0 if success else 1)
