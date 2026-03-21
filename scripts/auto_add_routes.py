#!/usr/bin/env python3
"""
Automated route addition script for GitHub Actions.
This script adds 10 random curated routes to the fallback pool each month.
"""

import json
import random
import re
from datetime import datetime
from pathlib import Path

# Curated route candidates for monthly additions
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
        "title": "Säntis Säntis Trail",
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
        "title": "Appenzeller Vorderland Spaziergang",
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
        "title": "Beatenbucht Höhenweg",
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
        "title": "Tschingelhörner Bergtour",
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


def generate_hike_code(route: dict, fallback_id: int) -> str:
    """Generate Python code for a Hike object."""
    code = f'''            Hike(
                title="{route['title']}",
                difficulty=self.normalize_difficulty("{route['difficulty']}"),
                duration_minutes={route['duration_minutes']},
                distance_km={route['distance_km']},
                region="{route['region']}",
                canton="{route['canton']}",
                source="schweizmobil",
                source_url="https://www.schweizmobil.ch/de/wanderland/route-{route['route_id']}",
                elevation_gain_m={route['elevation_gain_m']},
                elevation_loss_m={route['elevation_loss_m']},
                start_point="{route['start_point']}",
                end_point="{route['end_point']}",
                description="{route['description']}",
                latitude_start={route.get('latitude_start', 47.0)},
                longitude_start={route.get('longitude_start', 8.0)},
                tags={route['tags']},
                external_id="schweizmobil-fallback-{fallback_id}",
            ),'''
    return code


def get_already_added_routes(content: str) -> set:
    """Extract titles of routes already in the file to avoid duplicates."""
    added_titles = set()
    # Find all route titles in the file
    for candidate in ROUTES_CANDIDATES:
        title = candidate['title']
        # Check if this route title already exists in the file
        if f'title="{title}"' in content:
            added_titles.add(title)
    return added_titles


def add_routes_to_file(num_routes: int = 10) -> bool:
    """
    Add random routes to schweizmobil.py

    Args:
        num_routes: Number of routes to add

    Returns:
        True if successful, False otherwise
    """
    try:
        # Read the current file
        file_path = Path("scrapers/hiking/schweizmobil.py")
        content = file_path.read_text(encoding="utf-8")

        # Find the last external_id to continue the numbering
        match = re.search(r'external_id="schweizmobil-fallback-(\d+)"', content)
        if not match:
            print("❌ Could not find existing routes in file")
            return False

        last_id = int(match.group(1))
        next_id = last_id + 1

        # Filter out routes that have already been added (no duplicates)
        already_added = get_already_added_routes(content)
        available_candidates = [
            route for route in ROUTES_CANDIDATES
            if route['title'] not in already_added
        ]

        if not available_candidates:
            print("⚠️  All candidate routes have already been added!")
            return False

        # Select random routes from available candidates
        selected = random.sample(
            available_candidates,
            min(num_routes, len(available_candidates))
        )

        # Generate code for new routes
        new_routes_code = "\n".join(
            generate_hike_code(route, next_id + i) for i, route in enumerate(selected)
        )

        # Find insertion point: before the closing `]` bracket in _all_curated_routes
        insertion_pattern = r'(            ),\n        \]'
        if not re.search(insertion_pattern, content):
            print("❌ Could not find insertion point in file")
            return False

        # Insert the new routes
        new_content = re.sub(
            r'(            ),\n        \]',
            f'{new_routes_code}\n        ]',
            content
        )

        # Write back to file
        file_path.write_text(new_content, encoding="utf-8")

        print(f"✅ Added {len(selected)} new hiking routes")
        print(f"   Route IDs: {next_id} - {next_id + len(selected) - 1}")
        print(f"   Routes added:")
        for i, route in enumerate(selected, 1):
            print(f"   {i:2d}. {route['title']}")

        return True

    except Exception as e:
        print(f"❌ Error adding routes: {e}")
        return False


if __name__ == "__main__":
    success = add_routes_to_file(10)
    exit(0 if success else 1)
