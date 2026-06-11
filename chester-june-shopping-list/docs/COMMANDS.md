# Commands Reference

## Shopping List Generation

### Generate Weekly List
```bash
python scripts/generate_list.py 2026-06-15 --staples 200 --brook 80 --scale 4
```

### Create Markdown Outputs
```bash
python scripts/output_markdown.py 2026-06-15 --scale 4
```

## Data Management

### Validate Data
```bash
python scripts/validate_data.py
```

### Freezer Audit
```bash
python scripts/freezer_audit.py
```

## Testing

```bash
pytest
```

## GSD Commands

- `.gsd/commands/plan-monday.md` - Generate Monday shopping plan
