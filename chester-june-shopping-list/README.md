# Chester Monday Shopping List System

A grocery logistics system for structured Monday shopping in Chester.

## Overview

This project turns Monday groceries into a repeatable creative ritual:
1. Cheap heavy staples first (Aldi/Lidl/Iceland style)
2. Brook Street magic second (Polish/Eastern European, African/Caribbean, Asian shops)
3. Clean freezer/recipe/coding-fuel landing at home

## Budget (4 People)

- **Weekly: £280**
  - Staples & Freezer Fill: £200
  - Brook Street Culinary: £80

- **Monthly: ~£1120**
  - Target: £800 staples, £320 Brook Street

- **Budget modes:**
  - Lean week: £120/£40 (freezer full)
  - Default week: £200/£80 (normal)
  - Freezer-build: £260/£96 (stock up)
  - Celebration/Dad: £300/£140 (bigos/pierogi treats)

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Validate data
python scripts/validate_data.py

# Generate 4-person list
python scripts/generate_list.py 2026-06-15 --scale 4

# Create markdown outputs
python scripts/output_markdown.py 2026-06-15 --scale 4

# Run tests
pytest
```

## Data Structure

- `data/shops.yml` - Shop configuration
- `data/prices/observations.csv` - Receipt-backed price log
- `data/inventory/` - Freezer/pantry/fridge inventory
- `data/recipes/` - Polish recipes and crossovers
- `data/budgets.yml` - Weekly budget modes

## Key Recipes

- **Pierogi ruskie** - potato/twaróg filling
- **Bigos** - hunter's stew with sauerkraut
- **Żurek** - sour rye soup with sausage
- **Gołąbki** - cabbage rolls with mince

## License

MIT
