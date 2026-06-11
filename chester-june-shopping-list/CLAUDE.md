# Chester Monday Shopping List System

## Mission
Turn Monday groceries into a repeatable creative ritual: cheap heavy staples first, Brook Street magic second, then a clean freezer/recipe/coding-fuel landing at home.

## Repository Structure
- `data/` - Core data files (shops, prices, recipes, inventory)
- `scripts/` - Python scripts for automation
- `tests/` - Pytest test suite
- `docs/` - Documentation and research
- `.claude/commands/` - Claude Code slash commands
- `.gsd/commands/` - GSD command specs

## Quick Start
```bash
# Install dependencies
pip install -e ".[dev]"

# Validate data
python scripts/validate_data.py

# Generate a 4-person shopping list
python scripts/generate_list.py 2026-06-15 --staples 200 --brook 80 --scale 4

# Create markdown outputs
python scripts/output_markdown.py 2026-06-15 --scale 4

# Run tests
pytest
```

## Budget System (4 people)
- Weekly: £280 (£200 staples, £80 Brook Street)
- Monthly: £1120 (£800 staples, £320 Brook Street)
- Modes: lean, default, freezer-build, celebration

## Commands
- `scripts/generate_list.py` - Shopping list generation
- `scripts/validate_data.py` - Data validation
