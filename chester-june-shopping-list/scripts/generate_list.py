#!/usr/bin/env python3
"""Generate shopping lists from budget, recipes, and inventory."""

import csv
import yaml
import argparse
from pathlib import Path
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Item:
    item_id: str
    quantity: float
    unit: str
    estimated_cost: float
    shop: str
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

def load_recipes():
    recipes = {}
    for recipe_file in Path('data/recipes').rglob('*.yml'):
        data = load_yaml(recipe_file)
        name = data['recipe']['name']
        recipes[name] = data
    return recipes

def generate_list(date: str, staples_budget: float, brook_budget: float, hero_recipe: str = None):
    shops = load_yaml('data/shops.yml')['shops']
    prices = load_prices('data/prices/observations.csv')
    recipes = load_recipes()
    
    # Default staples items (would be expanded with actual logic)
    staples_items = [
        Item('potatoes_white', 2.5, 'kg', 4.75, 'discount_primary', 'pierogi, bigos base'),
        Item('onions_white', 1, 'kg', 0.99, 'discount_primary', 'everything base'),
        Item('cabbage_white', 1, 'head', 1.30, 'discount_primary', 'bigos, gołąbki'),
        Item('flour_plain', 1.5, 'kg', 1.50, 'discount_primary', 'pierogi dough'),
        Item('rice_white', 1, 'kg', 1.60, 'discount_primary', 'bowls, gołąbki'),
        Item('eggs_large', 12, 'pieces', 2.50, 'discount_primary', 'pierogi, żurek'),
        Item('chicken_thighs', 1, 'kg', 3.25, 'discount_primary', 'stock, protein'),
    ]
    
    # Brook Street specialty items
    brook_items = [
        Item('tworog_polish', 500, 'g', 3.49, 'brook_polish', 'pierogi ruskie filling'),
        Item('kielbasa', 500, 'g', 4.50, 'brook_polish', 'bigos, żurek'),
        Item('sauerkraut', 1, 'kg', 2.25, 'brook_polish', 'bigos authenticity'),
    ]
    
    staples_total = sum(i.estimated_cost for i in staples_items)
    brook_total = sum(i.estimated_cost for i in brook_items)
    
    return {
        'date': date,
        'staples_budget': staples_budget,
        'brook_budget': brook_budget,
        'staples_total': round(staples_total, 2),
        'brook_total': round(brook_total, 2),
        'staples_list': [vars(i) for i in staples_items],
        'brook_list': [vars(i) for i in brook_items]
    }

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Generate shopping lists')
    parser.add_argument('date', help='Date in YYYY-MM-DD format')
    parser.add_argument('--staples', type=float, default=50, help='Staples budget')
    parser.add_argument('--brook', type=float, default=20, help='Brook Street budget')
    parser.add_argument('--hero', type=str, default=None, help='Hero recipe name')
    args = parser.parse_args()
    
    result = generate_list(args.date, args.staples, args.brook, args.hero)
    print(yaml.dump(result, default_flow_style=False))
