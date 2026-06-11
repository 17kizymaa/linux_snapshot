#!/usr/bin/env python3
"""Validate data files for consistency and completeness."""

import yaml
import csv
import sys
from pathlib import Path

def validate_prices():
    required_units = ['kg', 'g', 'l', 'ml', 'pieces', 'pack', 'bag', 'head', 'each', 'tin', 'tins', 'jar']
    errors = []
    
    with open('data/prices/observations.csv') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, 2):
            if row['unit'] not in required_units:
                errors.append(f"Line {i}: Unknown unit '{row['unit']}' for {row['item_id']}")
            if float(row['price_gbp']) <= 0:
                errors.append(f"Line {i}: Invalid price for {row['item_id']}")
    
    return errors

def validate_recipes():
    errors = []
    for recipe_file in Path('data/recipes').rglob('*.yml'):
        with open(recipe_file) as f:
            data = yaml.safe_load(f)
        if 'recipe' not in data:
            errors.append(f"{recipe_file}: Missing 'recipe' key")
    return errors

if __name__ == '__main__':
    all_errors = []
    all_errors.extend(validate_prices())
    all_errors.extend(validate_recipes())
    
    if all_errors:
        for err in all_errors:
            print(f"ERROR: {err}")
        sys.exit(1)
    else:
        print("All validations passed")
