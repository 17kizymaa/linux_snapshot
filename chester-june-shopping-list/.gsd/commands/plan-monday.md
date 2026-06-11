---
name: plan-monday
description: Generate the Chester Monday grocery plan
---

## Purpose
Create a weekly shopping plan with budget-separated lists for Staples & Freezer Fill and Brook Street Culinary.

## Inputs
- Date
- Staples budget (default £50)
- Brook Street budget (default £20)
- Hero recipe (optional)

## Context Files
- `data/shops.yml`
- `data/budgets.yml`
- `data/prices/observations.csv`
- `data/inventory/freezer.yml`
- `data/recipes/**/*.yml`

## Steps
1. Load inventory and price data
2. Generate staples list (discount shops)
3. Generate Brook Street list (specialty shops)
4. Apply budget caps
5. Check freezer for overstock
6. Write output files
7. Run tests
8. Commit

## Outputs
- `outputs/weekly/{ISO_WEEK}/monday-shopping-list.md`
- `outputs/weekly/{ISO_WEEK}/brook-street-list.md`
- `outputs/weekly/{ISO_WEEK}/budget-summary.md`

## Acceptance Criteria
- Budgets respected
- Freezer inventory checked
- Phone-readable output
