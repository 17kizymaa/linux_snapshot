---
name: chester-june-shopping-list
description: Local grocery logistics project for Chester Monday shopping rituals
type: project
---

# Project: Chester Monday Shopping List System

## Mission
Turn Monday groceries into a repeatable creative ritual: cheap heavy staples first, Brook Street magic second, then a clean freezer/recipe/coding-fuel landing at home.

## Context
Weekly Monday shopping in Chester with a structured approach to:
- Budget-separated Staples & Freezer Fill (£50) and Brook Street Culinary (£20)
- Price-intelligence backed by receipt data
- Weekly operational planning with route optimization
- Freezer inventory management and recipe rotation

## Core Workflow
1. **Prep at home** (10 min): Pack bags, budgets, freezer blocks
2. **Budget staples shop** (35-55 min): Heavy, cheap, repeatable core foods
3. **Walk to Brook Street** (15-35 min): Repack before walking
4. **Brook Street culinary lap** (35-55 min): Polish/Eastern European, African/Caribbean, Asian shops
5. **Home landing** (25-45 min): Cold away, meat portioned, freezer logged

## Data Model
- `data/shops.yml` - Shop configuration and roles
- `data/prices/observations.csv` - Receipt-backed price observations
- `data/inventory/freezer.yml` - Freezer inventory with labels
- `data/recipes/*.yml` - Polish recipes and crossover dishes
- `data/rotations/four-week-cycle.yml` - Recipe rotation schedule

## Success Metrics
- Tests pass (`make test`)
- Weekly output generated and phone-readable
- Freezer overbuying prevented
- Receipt observations append-only, no overwrites