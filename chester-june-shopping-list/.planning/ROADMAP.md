---
derived_from: REQUIREMENTS.md
---

# Roadmap

## Phase 1: Bootstrap Project (Immediate)
- Create repository structure
- Add core YAML/CSV data files for shops, prices, recipes, budgets
- Add basic scripts for list generation and validation
- Add pytest tests
- Add Claude Code slash commands and CLAUDE.md

## Phase 2: Core Scripts Implementation (Week 1)
- Implement `generate_list.py` with budget separation
- Implement `freezer_audit.py`
- Implement `scale_recipe.py`
- Implement `generate_labels.py`
- Implement `validate_data.py`
- All tests passing

## Phase 3: Receipt Ingestion (Week 2)
- Implement `ingest_receipt.py`
- Implement `update_prices.py`
- Price anomaly detection
- Receipt capture workflow

## Phase 4: Weekly Cadence Automation (Week 3)
- Sunday freezer audit automation
- Monday plan generation
- Home landing protocol
- CHANGELOG.md update automation

## Phase 5: Advanced Features (Future)
- Price trend dashboard
- Calendar integration via MCP
- Receipt OCR pipeline
- Curiosity token tracker
- Dad rating tracker