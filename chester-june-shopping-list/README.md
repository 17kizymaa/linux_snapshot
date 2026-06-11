# Chester Monday Shopping List System

A grocery logistics system for structured Monday shopping in Chester.

## Overview

This project turns Monday groceries into a repeatable creative ritual:
1. Cheap heavy staples first (Aldi/Lidl/Iceland style)
2. Brook Street magic second (Polish/Eastern European, African/Caribbean, Asian shops)
3. Clean freezer/recipe/coding-fuel landing at home

## Budget

- **Default weekly: £70**
  - Staples & Freezer Fill: £50
  - Brook Street Culinary: £20

- **Budget modes:**
  - Lean week: £30/£10 (freezer full)
  - Default week: £50/£20 (normal)
  - Freezer-build: £65/£24 (stock up)
  - Celebration/Dad: £75/£35 (bigos/pierogi treats)

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Validate data
python scripts/validate_data.py

# Generate list for 2026-06-15
python scripts/generate_list.py 2026-06-15

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
