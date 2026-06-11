#!/usr/bin/env python3
"""Generate shopping lists from budget, recipes, and inventory."""

import csv
import yaml
import argparse
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Item:
    item_id: str
    quantity: float
    unit: str
    estimated_cost: float
    recipe_reason: str = ""

def load_yaml(path):
    with open(path) as f:
        return yaml.safe_load(f)

def load_prices(path):
    items = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            items[row['item_id']] = {
                'price': float(row['price_gbp']),
                'quantity': float(row['quantity']),
                'unit': row['unit'],
                'notes': row.get('notes', '')
            }
    return items

def generate_list(date: str, staples_budget: float, brook_budget: float):
    shops = load_yaml('data/shops.yml')
    prices = load_prices('data/prices/observations.csv')
    
    # Placeholder logic - expand later
    staples_items = []
    brook_items = []
    
    return {
        'date': date,
        'staples_budget': staples_budget,
        'brook_budget': brook_budget,
        'staples_list': staples_items,
        'brook_list': brook_items
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate shopping lists')
    parser.add_argument('date', help='Date in YYYY-MM-DD format')
    parser.add_argument('--staples', type=float, default=50, help='Staples budget')
    parser.add_argument('--brook', type=float, default=20, help='Brook Street budget')
    args = parser.parse_args()
    
    result = generate_list(args.date, args.staples, args.brook)
    print(yaml.dump(result, default_flow_style=False))
