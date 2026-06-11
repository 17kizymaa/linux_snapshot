---
derived_from: PROJECT.md
---

# Requirements

## Core Requirements

### Data Model
- [ ] Shops configuration (`data/shops.yml`) with tier pricing and roles
- [ ] Price observations (`data/prices/observations.csv`) as append-only log
- [ ] Current estimates (`data/prices/current-estimates.yml`) derived from observations
- [ ] Freezer inventory (`data/inventory/freezer.yml`) with dates, portions, tags
- [ ] Pantry inventory (`data/inventory/pantry.yml`)
- [ ] Fridge inventory (`data/inventory/fridge.yml`)
- [ ] Recipe files (`data/recipes/*.yml`) with ingredients, cost, scaling rules

### Scripts
- [ ] `generate_list.py` - Create shopping lists from budget, recipes, inventory
- [ ] `freezer_audit.py` - Show what to use before buying
- [ ] `scale_recipe.py` - Scale recipes by portions
- [ ] `generate_labels.py` - Produce freezer labels
- [ ] `validate_data.py` - Catch bad units, missing prices, duplicate IDs

### Budget System
- [ ] Default weekly budget: £70 (£50 staples, £20 Brook Street)
- [ ] Budget modes: Lean, Default, Freezer-build, Celebration
- [ ] One curiosity token: £3-5 per week

### Recipe System
- [ ] Polish heroes: Pierogi, Bigos, Żurek, Gołąbki, Placki, Zapiekanka
- [ ] Crossover recipes: West Indian fry-up, Asian broth bowl
- [ ] 4-week rotation schedule
- [ ] Dad delight scoring and skill-building notes

## Nice-to-Have Requirements

- [ ] `ingest_receipt.py` - Parse receipt notes/photo transcription
- [ ] `update_prices.py` - Compute current low/median/high price estimates
- [ ] `match_recipes.py` - Suggest recipes from freezer/pantry stock
- [ ] `budget_optimizer.py` - Fit list to staples/Brook budgets
- [ ] Price trend dashboard
- [ ] Calendar integration via MCP
- [ ] Receipt OCR pipeline