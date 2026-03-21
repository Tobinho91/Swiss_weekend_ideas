# Route Validation Process

This document explains how to prevent and catch route ID mismatches.

## Problem

Previously, hiking routes were added with incorrect route IDs, causing links to point to wrong content on schweizmobil.ch.

Example:
- Route titled "Monte San Giorgio Rundweg" had route ID 655
- But route-655 on schweizmobil.ch is actually a different route

## Solution: Validation Script

### Running Validation Locally

Before committing route changes, always run the validation script:

```bash
python3 scripts/validate_routes.py
```

This script:
- Extracts all routes from `scrapers/hiking/schweizmobil.py`
- Checks that each route ID (route-XXX) actually exists on schweizmobil.ch
- Verifies HTTP 200 status for each route URL
- Reports any missing or invalid routes

**Exit codes:**
- `0` = All routes valid ✓
- `1` = One or more routes invalid ✗

### Example Output

```
INFO: Extracting routes from schweizmobil.py...
INFO: Found 38 routes

INFO: Validating routes (this may take a minute)...
INFO: [1/38] Checking Via Alpina Etappe 1: Vaduz – Sargans... (route-1)
INFO:   ✓ Page found
...
INFO: All routes validated successfully!
```

### Known Issues

Some routes don't have numbered routes on schweizmobil.ch and are listed in `KNOWN_ISSUES`:
- Blausee Rundwanderung (not a numbered route)

These routes are skipped but marked as OK since they're documented limitations.

## Workflow: Adding New Routes

### Step 1: Research the Route

When adding a new route to `ROUTES_CANDIDATES` in `scripts/auto_add_routes.py`:

1. Visit https://www.schweizmobil.ch/de/wanderland/routen.html
2. Search for your route (e.g., "Monte Rosa")
3. Find the route in results
4. Click to open the route detail page
5. **Copy the route number from the URL**: `https://www.schweizmobil.ch/de/wanderland/route-**636**`

### Step 2: Add Route with Correct ID

Update `ROUTES_CANDIDATES` with the correct route ID:

```python
{
    "title": "Monte San Giorgio Rundweg",  # Exact title from schweizmobil.ch
    "route_id": "636",  # ← Extract from URL
    "difficulty": "T2",
    # ... other fields
}
```

### Step 3: Validate Before Commit

```bash
# Run validation
python3 scripts/validate_routes.py

# If all routes pass, commit your changes
git add scrapers/hiking/schweizmobil.py scripts/auto_add_routes.py
git commit -m "Add new hiking routes"
```

### Step 4: Push and Deploy

```bash
git push origin main
```

## Automated Validation

Future enhancement: Add validation as a GitHub Actions check before merging PRs.

```yaml
# .github/workflows/validate-routes.yml
- name: Validate hiking routes
  run: python3 scripts/validate_routes.py
```

This would automatically catch mismatches before code is merged.

## Troubleshooting

### "Route ID not found (404)"
- The route number doesn't exist on schweizmobil.ch
- **Solution**: Search schweizmobil.ch to find the correct route ID
- Example: If you think it's route-999 but get 404, search the site for the correct number

### "Title mismatch: expected X, found Y"
- The route ID exists but has a different title
- **Solution**: Update your route title to match what's on the website
- OR update the route ID to match the correct route

### Timeout errors
- Network issue or schweizmobil.ch is slow
- **Solution**: Run validation again (usually temporary)

## Best Practices

✅ **DO:**
- Always validate routes before committing
- Copy route IDs directly from schweizmobil.ch URLs
- Use exact titles from the website
- Test on a small batch of routes first

❌ **DON'T:**
- Guess or assume route IDs
- Manually invent route numbers
- Skip validation to save time
- Commit unvalidated routes to main branch

## Reference

- **Schweizmobil**: https://www.schweizmobil.ch/de/wanderland/routen.html
- **Route format**: https://www.schweizmobil.ch/de/wanderland/route-{ID}
- **Validation script**: `scripts/validate_routes.py`
