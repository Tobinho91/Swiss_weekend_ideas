# Monthly Hiking Routes Update Process

This document explains how to maintain and expand the hiking routes database monthly.

## Schedule

- **When**: 1st of each month at 8:57 AM (automated reminder)
- **Task**: Add 10+ new curated hiking routes to the fallback pool
- **Effort**: ~20-30 minutes per month

## How It Works

### Automatic Reminders
A monthly cron job reminds you to update routes on the 1st of each month. The reminder includes:
- Current route count
- Suggested routes to add
- Instructions for the update

### The Update Process

#### Step 1: Generate Candidates
```bash
python3 scripts/update_hiking_routes.py
```

This script:
- Displays current route count
- Shows 10 suggested routes from a curated pool
- Provides instructions for manual addition
- Saves candidates to `scripts/routes_candidates.json`

#### Step 2: Add Routes to Code
Edit `scrapers/hiking/schweizmobil.py`:
1. Open the file
2. Find the `_all_curated_routes()` method
3. Locate the closing `]` bracket (end of routes list)
4. Add the 10 new `Hike()` entries before the bracket
5. Update the route ID sequentially (currently at ~920+)

**Template for new routes:**
```python
Hike(
    title="Route Name",
    difficulty=self.normalize_difficulty("T2"),
    duration_minutes=240,
    distance_km=14.0,
    region="Region Name",
    canton="XX",  # 2-letter canton code
    source="schweizmobil",
    source_url="https://www.schweizmobil.ch/de/wanderland/route-XXX",
    elevation_gain_m=600,
    elevation_loss_m=600,
    start_point="Start",
    end_point="End",
    description="Brief description of the route.",
    latitude_start=47.0,
    longitude_start=8.0,
    tags=["Tag1", "Tag2", "Canton"],
    external_id="schweizmobil-fallback-XXX",
),
```

#### Step 3: Test & Deploy
```bash
# Regenerate the website with new routes
python3 main.py

# Verify the output
# Check: output/index.html (should show 10 of the 44+ routes)
```

#### Step 4: Commit & Push
```bash
git add -A
git commit -m "Feat: Add 10 new hiking routes ([Month] [Year])"
git push origin main
```

## Route Sources

Routes are curated from:
- **schweizmobil.ch**: Official Swiss hiking network
- **opendata.swiss**: Swiss government hiking data
- **Personal research**: Popular, well-maintained trails

## Route Difficulty Levels

- **T1**: Easy, suitable for families
- **T2**: Moderate, good fitness required
- **T3**: Difficult, mountain experience needed
- **T4**: Very difficult, technical skills required

## Tracking Progress

Current status:
- **Expansion goal**: 80-100 routes by end of 2026
- **Current count**: ~44 routes
- **Target per month**: +10 routes
- **Estimated completion**: ~4-6 months

## Why Monthly Updates?

1. **User variety**: New routes every week as rotation picks different 10
2. **Sustainable**: 20-30 minutes is manageable monthly
3. **Quality control**: Hand-curated ensures accuracy
4. **No API dependency**: Works without external services
5. **Growth trajectory**: Reaches 100+ routes within a year

## Future Enhancements

Possible improvements:
- Automated route scraping from API (if available)
- Route rating/difficulty crowdsourcing
- Seasonal route recommendations (summer/winter)
- User-submitted routes system
