# Technical Reference

## V5 Schema

The **[V5](../data/v5/cards.min.json)** dataset is an array of card objects. Every card contains exactly 33 fields, always in this order.

| Field                | Type    | Description                                                                                                                                                     |
|:---------------------|:--------|:----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `id`                 | string  | Set prefix and padded card number (e.g., "a1-001").                                                                                                             |
| `name`               | string  | The printed name of the card.                                                                                                                                   |
| `set_code`           | string  | The normalised lowercase set code.                                                                                                                              |
| `set_name`           | string  | The full name of the expansion.                                                                                                                                 |
| `pack`               | string  | The named pack the card drops from; the expansion name when the set has no named packs; or `Shared(<expansion name>)` when it appears in every pack of a set.    |
| `release_date`       | string  | ISO 8601 formatted release date. Null for promos.                                                                                                               |
| `type`               | string  | "Pokémon" or "Trainer".                                                                                                                                         |
| `subtype`            | string  | Energy type for Pokémon. Item classification for Trainers.                                                                                                      |
| `stage`              | string  | Basic, Stage 1, or Stage 2. Null for Trainers.                                                                                                                  |
| `evolves_from`       | string  | The name of the required pre-evolution Pokémon.                                                                                                                 |
| `rarity`             | string  | The visual rarity indicator. One of `◊`, `◊◊`, `◊◊◊`, `◊◊◊◊`, `☆`, `☆☆`, `☆☆☆`, `Crown Rare`, `Promo`.                                                           |
| `pack_points`        | integer | The cost to craft the card. Null for promos.                                                                                                                    |
| `ex`                 | boolean | True if the card is an "ex" rulebox Pokémon.                                                                                                                    |
| `mega`               | boolean | True if the card is a Mega Evolution.                                                                                                                           |
| `shiny`              | boolean | True if the card depicts a shiny variant.                                                                                                                       |
| `special_tags`       | array   | Tags like "ancient", "future", or "ultra_beasts". Defaults to null.                                                                                             |
| `art_style`          | string  | The visual treatment category. Null for cards with no special treatment, and for all `Crown Rare` cards (see below).                                             |
| `health`             | integer | The maximum hit points. Null for Trainers.                                                                                                                      |
| `retreat`            | integer | The energy cost to retreat. Null for Trainers.                                                                                                                  |
| `weakness`           | string  | The energy type the Pokémon is weak to.                                                                                                                         |
| `ability`            | object  | Contains `exists` (boolean), `name` (string), and `effect` (string).                                                                                            |
| `card_text`          | string  | The mechanical rules text for Trainer cards.                                                                                                                    |
| `attacks`            | object  | Contains keys `1` and `2`. Each holds `cost`, `name`, `damage` (integer), and `effect` (string).                                                                 |
| `points`             | integer | Points awarded to the opponent when knocked out (1, 2, or 3).                                                                                                   |
| `deckBuilderNr`      | integer | The internal integer used by the game client for deck rendering.                                                                                                |
| `artist`             | string  | The credited illustrator.                                                                                                                                       |
| `image`              | string  | URL to the WebP version of the card image.                                                                                                                      |
| `image_png`          | string  | URL to the PNG version of the card image.                                                                                                                       |
| `flavour_text`       | string  | The lore text printed on the card.                                                                                                                              |
| `alternate_versions` | array   | Prints from other sets mapping `set_code`, `set_name`, `id`, and `rarity`.                                                                                      |

`source_url` exists only in memory. The downloader fetches artwork from it, and the orchestrator calls `strip_source_urls` before validation, so it never reaches the published JSON. The schema sets `additionalProperties: false`, which enforces that.

### Known gaps

- **No `share_code`.** The reverse-engineered encoder lives in [deck_code.py](../scripts/deck_code.py) and is covered by tests, but it is not wired into the transformer, so no card carries a share code today. Only `deckBuilderNr` is published.
- **`Crown Rare` has no art style.** `ART_STYLES` has no crown category, so all Crown Rare cards carry `art_style: null`.


## V5 core schema

The **[core payload](../data/v5/cards.core.min.json)** is a slim projection of the V5 dataset for web clients: only the gameplay rarities (diamonds and promos) and no nested objects. Star rares and the Crown Rare are cosmetic duplicates that share a `deckBuilderNr` with a kept card, so they are dropped. Records are sparse: a field that does not apply is omitted, so a null value never appears and Trainer cards always drop the `ex` and `mega` keys. Fossil items are the exception to that trainer rule, because they are playable 40-HP Basic Pokemon, so they keep `stage`, `health` and `points`. Consumers must treat an absent key as not applicable. The payload is about 1.1 MB against 5.4 MB for the full dataset. Import it from `pokemon-tcg-pocket-cards/v5/core`. Field order matches the full schema where a field is present

| Field           | Type            | Description                                                        |
|:----------------|:----------------|:-------------------------------------------------------------------|
| `id`            | string          | Set prefix and padded card number (e.g., "a1-001").                |
| `name`          | string          | The printed name of the card.                                      |
| `set_code`      | string          | The normalised lowercase set code.                                 |
| `pack`          | string          | The named pack the card drops from.                                |
| `type`          | string          | "Pokémon" or "Trainer".                                            |
| `subtype`       | string          | Energy type for Pokémon. Item classification for Trainers.         |
| `stage`         | string, null    | Basic, Stage 1, or Stage 2. Null for Trainers.                     |
| `rarity`        | string          | The visual rarity indicator.                                       |
| `ex`            | boolean         | True if the card is an "ex" rulebox Pokémon.                       |
| `mega`          | boolean         | True if the card is a Mega Evolution.                              |
| `health`        | integer, null   | The maximum hit points. Null for Trainers.                         |
| `points`        | integer, null   | Points awarded to the opponent when knocked out. Null for Trainers.|
| `deckBuilderNr` | integer         | The internal integer used by the game client for deck rendering.   |
| `image`         | string          | URL to the WebP version of the card image.                         |

The **[no-image variant](../data/v5/cards.core.no-image.min.json)** drops `image` for the same 3,233 records, at about 0.7 MB minified. Records are sparse exactly as in the core payload, so an absent key is not applicable. Import it from `pokemon-tcg-pocket-cards/v5/core/no-image`. Field order matches the core schema minus `image` where a field is present

## V5 gameplay schema

The **[gameplay payload](../data/v5/cards.gameplay.min.json)** exists for battle simulators: it keeps the combat and card-effect fields a match needs and drops collection metadata, set and pack context beyond the set code, and all image URLs. It shares the core payload's rarity filter (diamonds and promos, 3,233 records) and is about 1.4 MB minified against 1.1 MB for the core payload and 5.4 MB for the full dataset. Rarity is not present, so each row drops to a single print per card rather than one per cosmetic variant. Records are sparse: null values are omitted and Trainer cards drop the `ex` and `mega` keys, so an absent key is not applicable. Trainer cards are trimmed to the fields the game exposes on them: a non-Fossil Trainer keeps only its identity, subtype, card text and deck number, while a Fossil item additionally carries its playable stage, health, points and weakness. Import it from `pokemon-tcg-pocket-cards/v5/gameplay`. Field order matches the full schema where the field appears

| Field           | Type            | Description                                                       |
|:----------------|:----------------|:------------------------------------------------------------------|
| `id`            | string          | Set prefix and padded card number (e.g., "a1-001").               |
| `name`          | string          | The printed name of the card.                                     |
| `set_code`      | string          | The normalised lowercase set code.                                |
| `type`          | string          | "Pokémon" or "Trainer".                                           |
| `subtype`       | string          | Energy type for Pokémon. Item classification for Trainers.        |
| `stage`         | string, null    | Basic, Stage 1, or Stage 2. Null for Trainers.                    |
| `evolves_from`  | string, null    | The name of the required pre-evolution Pokémon.                   |
| `special_tags`  | array, null     | Tags like "ancient", "future", or "ultra_beasts". Defaults to null.|
| `health`        | integer, null   | The maximum hit points. Null for Trainers.                        |
| `retreat`       | integer, null   | The energy cost to retreat. Null for Trainers.                    |
| `weakness`      | string, null    | The energy type the Pokémon is weak to.                           |
| `ability`       | object          | Contains `exists` (boolean), `name` (string), and `effect` (string). |
| `attacks`       | object          | Contains keys `1` and `2`. Each holds `cost`, `name`, `damage` (integer), and `effect` (string). |
| `card_text`     | string, null    | The mechanical rules text for Trainer cards.                      |
| `points`        | integer, null   | Points awarded to the opponent when knocked out (1, 2, or 3).     |
| `ex`            | boolean         | True if the card is an "ex" rulebox Pokémon.                      |
| `mega`          | boolean         | True if the card is a Mega Evolution.                             |
| `deckBuilderNr` | integer         | The internal integer used by the game client for deck rendering.  |

## V4 Schema

The **[V4](../data/v4/cards.min.json)** payload is frozen at version 5.4.0 and will not receive later set updates. It uses a legacy flat structure without arrays or objects.

| Field     | Type   | Description                                   |
|:----------|:-------|:----------------------------------------------|
| `id`      | string | Set prefix and padded card number.            |
| `name`    | string | The printed name of the card.                 |
| `rarity`  | string | The visual rarity indicator.                  |
| `pack`    | string | The specific pack the card drops from.        |
| `health`  | string | The maximum hit points. Empty string if none. |
| `image`   | string | URL to the PNG version of the card image.     |
| `fullart` | string | "Yes" or "No".                                |
| `ex`      | string | "Yes" or "No".                                |
| `artist`  | string | The credited illustrator.                     |
| `type`    | string | Energy type or Trainer classification.        |

## Command line arguments

The `add_expansion.py` script takes the following parameters:

| Argument        | Description                                                                                                        |
|-----------------|--------------------------------------------------------------------------------------------------------------------|
| `set_code`      | (Required unless `--all`) The set identifier or range string (e.g., `a1->b4`, `a1`, `pb`)                          |
| `--all`         | (Optional) Scrapes every set listed on the Limitless index, oldest first. Cannot be combined with `--name`.        |
| `--name`        | (Optional) Forces a specific expansion name instead of auto-detecting it from the webpage title.                   |
| `--mode`        | (Optional) Sets the output format. Valid options are `v4` or `v5`. The default is `v5`.                            |
| `--skip-images` | (Optional) Disables the downloading of WebP and PNG image assets.                                                  |

## Test suite

The repository uses `pytest` to validate the JSON output. Run the test suite from the root directory.

```bash
pytest tests/
```

The tests cover:
- **Schema compliance:** ensures exact key order, strict null usage over empty strings, and valid data types.
- **Invariants:** verifies that sets are contiguous blocks, numbering has no gaps, and art styles follow the correct ordering (e.g., Full Arts precede Special Illustration Arts).
- **Cross-file consistency:** ensures every set in the JSON has a matching entry in the expansions file, and that pack names align exactly between the two files.
- **Image availability:** Checks that every scraped card has both a WebP and PNG file present in the local [images/](../images) folder.
- **Published artifacts:** validates `cards.json` and `expansions.json` against the committed JSON Schemas, checks every `.min.json` against its source, checks the generated `.d.ts` files for stale or optional fields, and checks that every `package.json` export resolves to a file on disk.
- **Pipeline units:** exercises the scraper's HTML parsing, the art-style state machine (including shiny detection after the Immersive block), the v4 downgrade, the merge and sort logic in `database.py`, the deck-code encoder, and the image downloader's URL allow-list, all without network access.