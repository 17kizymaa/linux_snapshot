---
description: Generate the Chester Monday grocery plan
argument-hint: "YYYY-MM-DD staples_budget brook_budget hero_recipe"
---

You are maintaining the chester-june-shopping-list project.

Inputs:
- Date, staples budget, Brook Street budget, optional hero recipe from $ARGUMENTS.

Read:
- CLAUDE.md
- docs/monday-route.md
- data/shops.yml
- data/budgets.yml
- data/prices/current-estimates.yml
- data/prices/observations.csv
- data/inventory/freezer.yml
- data/recipes/**/*.yml
- data/rotations/four-week-cycle.yml

Tasks:
1. Generate a separated Staples & Freezer Fill list and Brook Street Culinary list.
2. Keep budgets separate.
3. Prefer discount-shop basics and Brook Street specialty items.
4. Avoid buying items already overstocked in freezer.yml.
5. Include recipe reasons for each item.
6. Include estimated totals and uncertainty notes.
7. Write outputs to outputs/weekly/{ISO_WEEK}/:
   - monday-shopping-list.md
   - brook-street-list.md
   - freezer-labels.md
   - prep-plan.md
   - budget-summary.md
8. Run validation/tests if available.
9. Show git diff summary.
10. Commit with message:
    plan: generate Chester Monday list for {date}

Acceptance criteria:
- Staples and Brook Street budgets are separated.
- Each item has shop target, estimate, and recipe/use reason.
- Total expected spend does not exceed budget unless explicitly marked.
- Freezer inventory is respected.
- Output is usable on a phone while walking.
