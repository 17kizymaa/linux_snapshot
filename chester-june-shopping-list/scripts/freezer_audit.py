#!/usr/bin/env python3
"""Audit freezer inventory to prevent overbuying."""

import yaml
import sys
from pathlib import Path

def load_freezer():
    with open('data/inventory/freezer.yml') as f:
        return yaml.safe_load(f) or {'items': []}

def load_prices():
    import csv
    items = {}
    with open('data/prices/observations.csv') as f:
        reader = csv.DictReader(f)
        for row in reader:
            items[row['item_id']] = row['item_id']
    return items

def audit():
    freezer = load_freezer()
    prices = load_prices()
    
    if not freezer['items']:
        print("Freezer is empty - safe to buy!")
        return
    
    print("=== Freezer Audit ===")
    print()
    
    # Group by item_id
    counts = {}
    for item in freezer['items']:
        iid = item['item_id']
        counts[iid] = counts.get(iid, 0) + 1
    
    for item_id, count in sorted(counts.items()):
        status = "⚠️  Overstock" if count > 2 else "✓ OK"
        print(f"{status} {item_id}: {count} portion(s)")
    
    print()
    print("Recommendation: Check freezer before buying more.")

if __name__ == '__main__':
    audit()
