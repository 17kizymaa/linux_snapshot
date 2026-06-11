#!/usr/bin/env python3
"""Generate markdown output files for weekly shopping."""

import yaml
import argparse
from pathlib import Path
from datetime import datetime
from generate_list import generate_list

def write_outputs(date: str, staples_budget: float, brook_budget: float, hero_recipe: str = None):
    result = generate_list(date, staples_budget, brook_budget, hero_recipe)
    
    # Get ISO week
    dt = datetime.strptime(date, '%Y-%m-%d')
    iso_year, iso_week, _ = dt.isocalendar()
    week_dir = Path(f'outputs/weekly/{iso_year}-W{iso_week:02d}')
    week_dir.mkdir(parents=True, exist_ok=True)
    
    # Write shopping list
    shopping = f"# Monday Shopping List - {date}\n\n"
    shopping += f"## Staples & Freezer Fill (Budget: £{staples_budget})\n"
    shopping += f"**Estimated: £{result['staples_total']}**\n\n"
    shopping += "| Item | Qty | Shop | Reason |\n|---|---|---|---|\n"
    for item in result['staples_list']:
        shopping += f"| {item['item_id']} | {item['quantity']} {item['unit']} | {item['shop']} | {item['recipe_reason']} |\n"
    
    with open(week_dir / 'monday-shopping-list.md', 'w') as f:
        f.write(shopping)
    
    # Write Brook Street list
    brook = f"# Brook Street Culinary - {date}\n\n"
    brook += f"## Specialty Items (Budget: £{brook_budget})\n"
    brook += f"**Estimated: £{result['brook_total']}**\n\n"
    brook += "| Item | Qty | Shop | Reason |\n|---|---|---|---|\n"
    for item in result['brook_list']:
        brook += f"| {item['item_id']} | {item['quantity']} {item['unit']} | {item['shop']} | {item['recipe_reason']} |\n"
    
    with open(week_dir / 'brook-street-list.md', 'w') as f:
        f.write(brook)
    
    # Write budget summary
    budget = f"# Budget Summary - {date}\n\n"
    budget += f"- Staples: £{result['staples_total']}/{result['staples_budget']}\n"
    budget += f"- Brook Street: £{result['brook_total']}/{result['brook_budget']}\n"
    budget += f"- Total: £{result['staples_total'] + result['brook_total']}/{result['staples_budget'] + result['brook_budget']}\n"
    
    with open(week_dir / 'budget-summary.md', 'w') as f:
        f.write(budget)
    
    print(f"Created: {week_dir}")
    return week_dir

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate markdown outputs')
    parser.add_argument('date', help='Date in YYYY-MM-DD format')
    parser.add_argument('--staples', type=float, default=50)
    parser.add_argument('--brook', type=float, default=20)
    parser.add_argument('--hero', type=str, default=None)
    args = parser.parse_args()
    
    write_outputs(args.date, args.staples, args.brook, args.hero)
