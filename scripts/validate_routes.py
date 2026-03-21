#!/usr/bin/env python3
"""
Route ID Validation Script

Validates that all routes in data/schweizmobil_routes.json actually exist
on schweizmobil.ch and load correctly. Prevents invalid route IDs from
being committed or deployed.

Usage:
    python3 scripts/validate_routes.py              # Validate all routes
    python3 scripts/validate_routes.py --strict     # Fail on ANY broken route
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Tuple, List
import logging

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def validate_route_id(route_id: int, route_title: str, timeout: int = 6000) -> Tuple[bool, str]:
    """
    Validate a single route ID by checking if it loads correctly on schweizmobil.ch

    Returns:
        (is_valid, status_message)
    """
    from playwright.async_api import async_playwright

    url = f"https://www.schweizmobil.ch/de/wanderland/route-{route_id}"

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            await page.goto(url, wait_until="domcontentloaded", timeout=timeout)

            # Get heading to detect error pages
            h1_text = ""
            try:
                h1_text = (await page.locator("h1").first.text_content(timeout=1500)) or ""
            except:
                pass

            await browser.close()

            # Check for error indicator
            if "falsche Richtung" in h1_text:
                return False, "Page returned 'wrong direction' error"

            if not h1_text:
                return False, "No heading found (page may not have loaded)"

            return True, f"Valid: {h1_text.strip()[:60]}"

    except asyncio.TimeoutError:
        return False, "Timeout loading page"
    except Exception as e:
        return False, f"Error: {str(e)[:50]}"


async def validate_all_routes(strict: bool = False) -> Tuple[int, int, List]:
    """
    Validate all routes in the JSON file

    Returns:
        (valid_count, broken_count, broken_routes_list)
    """
    routes_file = Path("data/schweizmobil_routes.json")

    if not routes_file.exists():
        logger.error(f"Routes file not found: {routes_file}")
        return 0, 0, []

    routes = json.loads(routes_file.read_text(encoding="utf-8"))
    logger.info(f"Validating {len(routes)} routes...\n")

    valid = []
    broken = []

    for i, route in enumerate(routes, 1):
        route_id = route['id']
        title = route['title']

        is_valid, status = await validate_route_id(route_id, title)

        if is_valid:
            valid.append((route_id, title))
            logger.info(f"{i:2d}. [OK]     Route {route_id:3d}: {title[:50]}")
        else:
            broken.append((route_id, title, status))
            logger.info(f"{i:2d}. [BROKEN] Route {route_id:3d}: {title[:50]} - {status}")

    return len(valid), len(broken), broken


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Validate hiking route IDs")
    parser.add_argument("--strict", action="store_true",
                       help="Fail if ANY routes are broken (exit code 1)")

    args = parser.parse_args()

    valid_count, broken_count, broken_routes = await validate_all_routes(args.strict)

    logger.info(f"\n{'='*70}")
    logger.info(f"SUMMARY: {valid_count} valid, {broken_count} broken")
    logger.info(f"{'='*70}")

    if broken_routes:
        logger.warning(f"\nBROKEN ROUTES ({broken_count}):")
        for route_id, title, status in broken_routes:
            logger.warning(f"  - Route {route_id}: {title}")
            logger.warning(f"    └─ {status}")

    # Exit with error code if strict mode and routes are broken
    if args.strict and broken_count > 0:
        logger.error(f"\n[STRICT MODE] Failing due to {broken_count} broken route(s)")
        sys.exit(1)

    if broken_count > 0:
        logger.warning(f"\n[WARNING] {broken_count} broken route(s) found but not failing (use --strict to fail)")
        sys.exit(0)

    logger.info("\n[OK] All routes validated successfully!")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
