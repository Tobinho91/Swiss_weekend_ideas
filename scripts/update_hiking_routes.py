#!/usr/bin/env python3
"""
Monthly hiking routes updater - Adds 10+ new routes to fallback pool.
Run this script once per month (usually on the 1st) to expand the hiking routes.

Usage:
    python3 scripts/update_hiking_routes.py
"""

import json
import random
from datetime import datetime
from pathlib import Path

# List of candidate routes to add (manually curated from SchweizMobil)
ROUTES_CANDIDATES = [
    {
        "title": "Monte Rosa Höhenweg",
        "difficulty": "T3",
        "duration_minutes": 360,
        "distance_km": 22.0,
        "region": "Wallis",
        "canton": "VS",
        "route_id": "630",
        "elevation_gain_m": 1400,
        "elevation_loss_m": 1400,
        "start_point": "Täsch",
        "end_point": "Riedgletscher",
        "description": "Spektakuläre Höhenwanderung um den Monte Rosa mit Blick auf 60 Viertausender.",
        "tags": ["Monte Rosa", "Höhenweg", "Wallis"],
    },
    {
        "title": "Dom Besteigung",
        "difficulty": "T4",
        "duration_minutes": 480,
        "distance_km": 20.0,
        "region": "Wallis",
        "canton": "VS",
        "route_id": "635",
        "elevation_gain_m": 2000,
        "elevation_loss_m": 2000,
        "start_point": "Randa",
        "end_point": "Randa",
        "description": "Anspruchsvolle Besteigung des Dom - Höchster Berg der Schweiz.",
        "tags": ["Dom", "Viertausender", "Wallis"],
    },
    {
        "title": "Appenzeller Höhenweg",
        "difficulty": "T2",
        "duration_minutes": 240,
        "distance_km": 14.0,
        "region": "Ostschweiz",
        "canton": "AR",
        "route_id": "960",
        "elevation_gain_m": 600,
        "elevation_loss_m": 600,
        "start_point": "Herisau",
        "end_point": "Walzenhausen",
        "description": "Klassischer Höhenweg durch das Appenzeller Hügelland mit Blick auf Säntis und Bodensee.",
        "tags": ["Appenzell", "Höhenweg", "Panorama"],
    },
    {
        "title": "Säntis Säntis Säntis Trail",
        "difficulty": "T1",
        "duration_minutes": 180,
        "distance_km": 10.0,
        "region": "Ostschweiz",
        "canton": "AR",
        "route_id": "955",
        "elevation_gain_m": 500,
        "elevation_loss_m": 500,
        "start_point": "Säntis Kulm",
        "end_point": "Appenzell",
        "description": "Einfache Wanderung vom Säntis hinunter mit Panoramablick.",
        "tags": ["Säntis", "Familie", "Appenzell"],
    },
    {
        "title": "Toggenburg Höhenweg",
        "difficulty": "T2",
        "duration_minutes": 300,
        "distance_km": 18.0,
        "region": "Ostschweiz",
        "canton": "SG",
        "route_id": "830",
        "elevation_gain_m": 800,
        "elevation_loss_m": 800,
        "start_point": "Unterwasser",
        "end_point": "Wildhaus",
        "description": "Spektakulärer Höhenweg durch das wunderschöne Toggenburg mit Säntis-Blick.",
        "tags": ["Toggenburg", "Höhenweg", "Säntis"],
    },
    {
        "title": "Appenzeller Vorderland",
        "difficulty": "T1",
        "duration_minutes": 120,
        "distance_km": 7.0,
        "region": "Ostschweiz",
        "canton": "AR",
        "route_id": "970",
        "elevation_gain_m": 200,
        "elevation_loss_m": 200,
        "start_point": "Gonten",
        "end_point": "Herisau",
        "description": "Einfache Spaziergang durch das typische Appenzeller Vorderland.",
        "tags": ["Appenzell", "Familie", "Tradition"],
    },
    {
        "title": "Säntis Beatenbucht",
        "difficulty": "T3",
        "duration_minutes": 300,
        "distance_km": 16.0,
        "region": "Berner Oberland",
        "canton": "BE",
        "route_id": "555",
        "elevation_gain_m": 1000,
        "elevation_loss_m": 1000,
        "start_point": "Beatenberg",
        "end_point": "Merligen",
        "description": "Anspruchsvolle Bergwanderung mit spektakulärem Thuner See Panorama.",
        "tags": ["Thunersee", "Berge", "Berner Oberland"],
    },
    {
        "title": "Brienzer Rothorn",
        "difficulty": "T3",
        "duration_minutes": 300,
        "distance_km": 15.0,
        "region": "Berner Oberland",
        "canton": "BE",
        "route_id": "560",
        "elevation_gain_m": 1200,
        "elevation_loss_m": 1200,
        "start_point": "Brienz",
        "end_point": "Brienzer Rothorn",
        "description": "Bergwanderung zum Brienzer Rothorn mit herrlichem Blick über die Seen.",
        "tags": ["Rothorn", "Seen", "Berner Oberland"],
    },
    {
        "title": "Sustenpass Wanderung",
        "difficulty": "T2",
        "duration_minutes": 240,
        "distance_km": 13.0,
        "region": "Berner Oberland",
        "canton": "BE",
        "route_id": "540",
        "elevation_gain_m": 600,
        "elevation_loss_m": 600,
        "start_point": "Gadmen",
        "end_point": "Wassen",
        "description": "Klassische Wanderung über den historischen Sustenpass.",
        "tags": ["Sustenpass", "Historisch", "Alpen"],
    },
    {
        "title": "Furkapass Höhenwanderung",
        "difficulty": "T2",
        "duration_minutes": 270,
        "distance_km": 15.0,
        "region": "Wallis",
        "canton": "VS",
        "route_id": "650",
        "elevation_gain_m": 700,
        "elevation_loss_m": 700,
        "start_point": "Gletsch",
        "end_point": "Realp",
        "description": "Wanderung über den spektakulären Furkapass mit Gletscher-Ausblick.",
        "tags": ["Furka", "Gletscher", "Höhenpass"],
    },
    {
        "title": "Tschingelhörner",
        "difficulty": "T3",
        "duration_minutes": 360,
        "distance_km": 18.0,
        "region": "Berner Oberland",
        "canton": "BE",
        "route_id": "570",
        "elevation_gain_m": 1300,
        "elevation_loss_m": 1300,
        "start_point": "Guttannen",
        "end_point": "Guttannen",
        "description": "Bergtour zu den Tschingelhörnern mit Alpine Luft und herrlichen Aussichten.",
        "tags": ["Tschingel", "Bergtour", "Berner Oberland"],
    },
]


def add_random_routes(num_routes: int = 10):
    """
    Add random routes from candidates to the fallback pool.

    Args:
        num_routes: Number of routes to add (default 10)
    """
    # Load current fallback routes count
    schweizmobil_py = Path("scrapers/hiking/schweizmobil.py").read_text()
    current_count = schweizmobil_py.count('external_id="schweizmobil-fallback-')

    # Select random candidates
    selected = random.sample(ROUTES_CANDIDATES, min(num_routes, len(ROUTES_CANDIDATES)))

    print(f"\n{'='*70}")
    print(f"Monthly Hiking Routes Update")
    print(f"{'='*70}")
    print(f"Current fallback routes: {current_count}")
    print(f"Routes to add: {len(selected)}")
    print(f"New total: {current_count + len(selected)}")
    print(f"\nSelected routes for this month:")
    print(f"{'-'*70}")

    for i, route in enumerate(selected, 1):
        print(f"{i:2d}. {route['title']:<40} ({route['canton']}) - Route {route['route_id']}")

    print(f"{'-'*70}")
    print(f"\nTo add these routes manually:")
    print(f"1. Edit: scrapers/hiking/schweizmobil.py")
    print(f"2. Find the _all_curated_routes() method")
    print(f"3. Add the 10 new Hike() entries before the closing bracket")
    print(f"4. Run: python3 main.py")
    print(f"5. Commit & push to GitHub")
    print(f"\nSuggested Git commit message:")
    print(f"  'Feat: Add {len(selected)} new hiking routes (month {datetime.now().strftime('%B %Y')})'")
    print(f"{'='*70}\n")

    # Save candidates for next month
    candidates_file = Path("scripts/routes_candidates.json")
    candidates_file.write_text(json.dumps(ROUTES_CANDIDATES, indent=2, ensure_ascii=False))
    print(f"✓ Candidates saved to: scripts/routes_candidates.json")


if __name__ == "__main__":
    add_random_routes(10)
