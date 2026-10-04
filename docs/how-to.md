# How-to guides

## Add a new expansion

When a new set is released on Limitless TCG, pass the set code to the expansion script.

```bash
python3 scripts/add_expansion.py b4a
```

## Update promo sets

Promo sets add cards over time. Running the command for a promo set re-scrapes the entire set from card 1. Existing entries are overwritten in place, so there is no duplication.

```bash
python3 scripts/add_expansion.py pb
```

## Scrape a chronological range of sets

If you are building the database from scratch or need to backfill multiple sets, use the arrow syntax (`->`). The script resolves the timeline and scrapes every set in chronological order.

```bash
python3 scripts/add_expansion.py a1->b4
```

## Output data for legacy schemas

If your application still relies on the flat v4 schema, you can force the scraper to output v4-formatted data. Add the `--mode v4` flag to format the output for the legacy schema.
```bash
python3 scripts/add_expansion.py b4 --mode v4
```

V4 output is merged into `data/v4/cards.json` and `data/v4/cards.min.json`. The minified file is the one published to npm.

Version 5.4.0 is the final v4 update.