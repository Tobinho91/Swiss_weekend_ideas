#!/usr/bin/env python3
"""
Validate hiking routes - check that route IDs match their titles on schweizmobil.ch
Run this before committing route changes to catch ID mismatches early.
"""

import re
import logging
from pathlib import Path
import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Routes known to have issues or not be on schweizmobil.ch
KNOWN_ISSUES = {
    "Blausee Rundwanderung",  # Not a numbered route
    "Muottas Muragl – Alp Languard",  # Tour 237, not a numbered route
}


def extract_routes_from_file(file_path):
    """Extract all route titles and IDs from schweizmobil.py"""
    content = file_path.read_text(encoding="utf-8")
    routes = []

    # Find all title and source_url pairs
    title_pattern = r'title="([^"]+)"'
    url_pattern = r'source_url="https://www\.schweizmobil\.ch/de/wanderland/route-(\d+)"'

    # Find all matches
    titles = [(m.start(), m.group(1)) for m in re.finditer(title_pattern, content)]
    urls = [(m.start(), m.group(1)) for m in re.finditer(url_pattern, content)]

    # Match titles with their corresponding route IDs
    # (assuming they appear in order within each Hike block)
    for title_pos, title in titles:
        # Find the next URL that comes after this title
        for url_pos, route_id in urls:
            if url_pos > title_pos:
                # Check if this URL is close enough to be in the same Hike block (within 500 chars)
                if url_pos - title_pos < 500:
                    routes.append({"title": title, "route_id": route_id})
                break

    return routes


def validate_route_id(title, route_id, session):
    """
    Validate that a route ID actually corresponds to the given title.
    Returns (is_valid, actual_title, error_message)
    """
    if title in KNOWN_ISSUES:
        return (True, None, "Known issue (not a numbered route)")

    try:
        url = f"https://www.schweizmobil.ch/de/wanderland/route-{route_id}"
        response = session.get(url, timeout=10, follow_redirects=True)

        if response.status_code == 404:
            return (False, None, "Route ID not found (404)")

        if response.status_code != 200:
            return (False, None, f"HTTP {response.status_code}")

        # Try to extract the title from the page
        # Look for <h1> or <title> tags that might contain the route name
        html = response.text
        title_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if not title_match:
            title_match = re.search(r'<title>([^<]+)</title>', html)

        if title_match:
            actual_title = title_match.group(1).strip()
            # Check if our title is in the page (case-insensitive, partial match OK)
            if title.lower() in actual_title.lower() or actual_title.lower() in title.lower():
                return (True, actual_title, "Match found")
            else:
                return (False, actual_title, f"Title mismatch: expected '{title}', found '{actual_title}'")
        else:
            # Can't extract title from page, but if no 404, assume OK
            return (True, None, "Page found (couldn't extract title to verify)")

    except httpx.TimeoutException:
        return (False, None, "Request timeout")
    except Exception as e:
        return (False, None, f"Error: {str(e)}")


def main():
    file_path = Path("scrapers/hiking/schweizmobil.py")

    if not file_path.exists():
        logger.error(f"File not found: {file_path}")
        return 1

    logger.info("Extracting routes from schweizmobil.py...")
    routes = extract_routes_from_file(file_path)
    logger.info(f"Found {len(routes)} routes")

    logger.info("\nValidating routes (this may take a minute)...")
    errors = []

    with httpx.Client() as session:
        for i, route in enumerate(routes, 1):
            title = route["title"]
            route_id = route["route_id"]

            logger.info(f"[{i}/{len(routes)}] Checking {title}... (route-{route_id})")
            is_valid, actual_title, message = validate_route_id(title, route_id, session)

            if is_valid:
                logger.info(f"  ✓ {message}")
            else:
                logger.warning(f"  ✗ {message}")
                errors.append({
                    "title": title,
                    "route_id": route_id,
                    "error": message,
                    "actual_title": actual_title,
                })

    # Summary
    logger.info(f"\n{'='*70}")
    if errors:
        logger.error(f"Found {len(errors)} validation error(s):")
        for error in errors:
            logger.error(f"\n  Route: {error['title']}")
            logger.error(f"  ID: route-{error['route_id']}")
            logger.error(f"  Error: {error['error']}")
            if error['actual_title']:
                logger.error(f"  Actual title: {error['actual_title']}")
        return 1
    else:
        logger.info("✓ All routes validated successfully!")
        return 0


if __name__ == "__main__":
    exit(main())
