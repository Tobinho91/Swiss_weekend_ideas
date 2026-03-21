# How to Add New Hiking Routes

Routes are stored in `data/schweizmobil_routes.json` and loaded dynamically. Here's how to add new routes:

## Automatic Method (Recommended)

GitHub Actions automatically adds 10 random routes on the 1st of each month.

**How it works:**
1. On the 1st of the month at 08:57 UTC
2. `scripts/auto_add_routes.py` runs automatically
3. Selects 10 random routes from `ROUTES_CANDIDATES`
4. Appends them to `data/schweizmobil_routes.json`
5. Regenerates the website
6. Commits and pushes changes

**To test locally:**
```bash
python3 scripts/auto_add_routes.py
```

**To manually trigger on GitHub:**
- Go to **Actions → Monthly Hiking Routes Update → Run workflow**

## Manual Method

Edit `data/schweizmobil_routes.json` directly:

```json
{
  "id": 1000,
  "title": "Route Name Exactly As On Schweizmobil",
  "region": "Region Name",
  "canton": "XX",
  "duration_minutes": 240,
  "distance_km": 15.0
}
```

**Required fields:**
- `id`: Unique number (e.g., 1000, 1001, etc.)
- `title`: Route name from schweizmobil.ch
- `region`: Swiss region name (e.g., "Valais", "Berner Oberland")
- `canton`: 2-letter canton code (e.g., "VS", "BE", "ZH")
- `duration_minutes`: Estimated hiking time in minutes
- `distance_km`: Distance in kilometers (decimal OK)

## Adding New Candidates

To add more routes for the monthly automation, edit `scripts/auto_add_routes.py`:

1. Add to `ROUTES_CANDIDATES` list:
```python
{
    "id": 1000,
    "title": "New Route Name",
    "region": "Region",
    "canton": "XX",
    "duration_minutes": 240,
    "distance_km": 15.0
}
```

2. Commit and push
3. GitHub Actions will use these candidates for next month's automatic update

## Data Structure Reference

**Field meanings:**
- `id`: Unique identifier (should be unique in the JSON)
- `title`: Exact name as shown on schweizmobil.ch
- `region`: Geographic region in Switzerland
- `canton`: Official 2-letter abbreviation (see list below)
- `duration_minutes`: Round-trip hiking time
- `distance_km`: Total distance, can use decimals (e.g., 15.5)

**Canton codes:**
```
AG = Aargau        JU = Jura           TI = Ticino
AI = Appenzell IS  LU = Lucerne        UR = Uri
AR = Appenzell AR  NE = Neuchâtel      VD = Vaud
BE = Bern          OW = Obwalden       VS = Valais
BL = Basel-Land    SG = St. Gallen     ZH = Zürich
BS = Basel-City    SH = Schaffhausen   ZG = Zug
FR = Fribourg      SO = Solothurn
GL = Glarus        SZ = Schwyz
GR = Graubünden    TG = Thurgau
```

## Example JSON Entry

```json
{
  "id": 1000,
  "title": "Säntis-Panoramaweg",
  "region": "Appenzell",
  "canton": "AR",
  "duration_minutes": 300,
  "distance_km": 16.0
}
```

## Validating Routes

**CRITICAL: All route IDs must be valid on schweizmobil.ch before being added.**

Validate routes before committing:

```bash
# Validate all routes (warns if broken, exits with 0)
python3 scripts/validate_routes.py

# Validate strictly (fails if ANY routes are broken)
python3 scripts/validate_routes.py --strict
```

**What validation does:**
- Tests each route ID by accessing https://www.schweizmobil.ch/de/wanderland/route-{ID}
- Confirms the page loads correctly (not a 404 or error page)
- Reports broken routes clearly

**When adding new routes to ROUTES_CANDIDATES:**
1. Test the route ID on schweizmobil.ch first
2. Verify it loads and shows correct content
3. Add to `ROUTES_CANDIDATES` in `scripts/auto_add_routes.py`
4. Run `python3 scripts/validate_routes.py --strict` to verify

**Validation in CI/CD:**
- GitHub Actions automatically validates routes on every push to `main`
- Pull requests are checked automatically
- If validation fails, the workflow will stop and show which routes are broken

## Testing

After adding routes, verify the website still works:

```bash
python3 main.py
```

Check that 10 random routes are displayed and each links to a valid schweizmobil.ch URL.

## Workflow Integration

The monthly GitHub Actions workflow:
1. Checks if `ROUTES_CANDIDATES` in the script has new routes
2. Filters out routes that already exist in the JSON file
3. Selects 10 random new routes
4. Appends to `data/schweizmobil_routes.json`
5. Regenerates website
6. Auto-commits with message: "Feat: Add 10 new hiking routes (Month Year)"

No manual intervention needed!
