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

def generate_list(date: str, staples_budget: float, brook_budget: float, hero_recipe: str = None, scale: int = 1):
    shops = load_yaml('data/shops.yml')['shops']
    prices = load_prices('data/prices/observations.csv')
    recipes = load_recipes()

    # Scale factors (4 people)
    s = scale

    # Default staples items scaled
    staples_items = [
        Item('potatoes_white', 2.5 * s, 'kg', 4.75 * s, 'discount_primary', 'pierogi, bigos base'),
        Item('onions_white', 1 * s, 'kg', 0.99 * s, 'discount_primary', 'everything base'),
        Item('cabbage_white', 1 * s, 'head', 1.30 * s, 'discount_primary', 'bigos, gołąbki'),
        Item('flour_plain', 1.5 * s, 'kg', 1.50 * s, 'discount_primary', 'pierogi dough'),
        Item('rice_white', 1 * s, 'kg', 1.60 * s, 'discount_primary', 'bowls, gołąbki'),
        Item('eggs_large', 12 * s, 'pieces', 2.50 * s, 'discount_primary', 'pierogi, żurek'),
        Item('chicken_thighs', 1 * s, 'kg', 3.25 * s, 'discount_primary', 'stock, protein'),
        Item('carrots', 1 * s, 'kg', 0.70 * s, 'discount_primary', 'soups, stock'),
        Item('mushrooms_dried', 50 * s, 'g', 3.50 * s, 'brook_polish', 'bigos flavour'),
    ]

    # Brook Street specialty items scaled
    brook_items = [
        Item('tworog_polish', 500 * s, 'g', 3.49 * s, 'brook_polish', 'pierogi ruskie filling'),
        Item('kielbasa', 500 * s, 'g', 4.50 * s, 'brook_polish', 'bigos, żurek'),
        Item('sauerkraut', 1000 * s, 'g', 2.25 * s, 'brook_polish', 'bigos authenticity'),
        Item('ogorki_kiszone', 500 * s, 'g', 2.80 * s, 'brook_polish', "Dad's pickles"),
        Item('zurek_starter', 2 * s, 'pack', 2.15 * s, 'brook_polish', 'żurek base'),
    ]

    staples_total = sum(i.estimated_cost for i in staples_items)
    brook_total = sum(i.estimated_cost for i in brook_items)

    return {
        'date': date,
        'people': scale,
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
    parser.add_argument('--staples', type=float, default=200, help='Staples budget')
    parser.add_argument('--brook', type=float, default=80, help='Brook Street budget')
    parser.add_argument('--hero', type=str, default=None, help='Hero recipe name')
    parser.add_argument('--scale', type=int, default=4, help='Scale factor (people)')
    args = parser.parse_args()

    result = generate_list(args.date, args.staples, args.brook, args.hero, args.scale)
    print(yaml.dump(result, default_flow_style=False))
