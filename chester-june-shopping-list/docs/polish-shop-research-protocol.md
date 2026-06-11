# Polish Shop Goods Research Protocol

## Purpose
Refine shopping lists for Brook Street Polish/Eastern European shops with receipt-backed pricing and availability data.

## Research Steps

### 1. Shop Identification
- Walk Brook Street, Foregate Street, Eastgate Street
- Identify: Polish delis, Eastern European markets, African/Caribbean shops
- Note: Opening hours, parking, specials boards

### 2. Core Polish Items to Research
| Item | Typical Price Range | Shop Priority |
|------|---------------------|---------------|
| Twaróg / Quark | £1.70-4.00/500g | Polish |
| Kiełbasa | £3.00-6.00/500g | Polish |
| Sauerkraut | £1.50-3.00/kg | Polish |
| Ogórki kiszone | £2.00-3.80/jar | Polish |
| Żurek starter | £1.50-2.80/pack | Polish |
| Dried mushrooms | £2.50-5.50/50g | Polish |
| Kasza gryczana | £1.50-2.80/500g | Polish |
| Marjoram/dill | £0.80-2.00/bunch | Polish |

### 3. Receipt Logging Format
```
date,shop,item,quantity,unit,price_gbp,notes
2026-06-15,brook_polish,twarog_polish,500,g,3.49,"good texture"
```

### 4. Budget Allocation (4 people)
- **Weekly**: £320 total (staples) + £128 (Brook Street)
- **Monthly**: £128 Brook Street for Polish specialties
- **Per shop visit**: £30-40 max

### 5. Stock-Up Strategy
- Buy dried goods in bulk (mushrooms, spices)
- Freeze fresh items (twaróg, kiełbasa)
- Track price trends monthly

## Output
- Updated `data/prices/observations.csv`
- Updated `data/shops.yml` with actual addresses/pricing
- Monthly price comparison report
