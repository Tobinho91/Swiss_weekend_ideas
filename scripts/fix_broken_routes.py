#!/usr/bin/env python3
"""
Remove broken routes from the routes JSON file.

Reads the current routes, identifies broken ones, and removes them,
keeping only verified working routes.

Usage:
    python3 scripts/fix_broken_routes.py
"""

import json
import sys
from pathlib import Path

# The 10 broken routes identified by validation
BROKEN_ROUTE_IDS = {
    175,  # Gemmipass
    450,  # Linth-Limmern
    480,  # Piz Segnas
    500,  # Schanfigg Rundweg
    534,  # Oeschinensee
    580,  # Wetterhorn Panorama
    585,  # Jungfrau Besteigung
    610,  # Rhone-Gletscher
    620,  # Zermatt Gornergrat
    659,  # Rheinschlucht Grand Canyon
}

def main():
    routes_file = Path("data/schweizmobil_routes.json")

    if not routes_file.exists():
        print(f"[ERROR] Routes file not found: {routes_file}")
        sys.exit(1)

    # Load current routes
    routes = json.loads(routes_file.read_text(encoding="utf-8"))
    original_count = len(routes)

    # Filter out broken routes
    valid_routes = [r for r in routes if r['id'] not in BROKEN_ROUTE_IDS]
    removed_count = original_count - len(valid_routes)

    # Write back
    routes_file.write_text(
        json.dumps(valid_routes, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )

    print(f"[OK] Routes updated:")
    print(f"    Before: {original_count} routes")
    print(f"    After:  {len(valid_routes)} routes")
    print(f"    Removed: {removed_count} broken routes")
    print(f"\nRemoved routes:")
    for route in routes:
        if route['id'] in BROKEN_ROUTE_IDS:
            print(f"  - Route {route['id']}: {route['title']}")

if __name__ == "__main__":
    main()
