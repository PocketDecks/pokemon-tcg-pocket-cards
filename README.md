# 🎴 Pokémon TCG Pocket Cards

<p align="center">
  <img alt="npm version" src="https://img.shields.io/npm/v/pokemon-tcg-pocket-cards">
  <img alt="npm downloads" src="https://img.shields.io/npm/dm/pokemon-tcg-pocket-cards">
  <img alt="licence" src="https://img.shields.io/npm/l/pokemon-tcg-pocket-cards">
  <img alt="last commit" src="https://img.shields.io/github/last-commit/chase-mew/pokemon-tcg-pocket-cards">
  <a href="https://bundlephobia.com/package/pokemon-tcg-pocket-cards@5.3.1"><img alt="npm bundle size" src="https://img.shields.io/bundlephobia/min/pokemon-tcg-pocket-cards"></a>
</p>

This open-source repository holds data on Pokémon TCG Pocket cards. You can use it to build websites, collection trackers, and fan tools.

Or install it from npm, which ships the minified data plus TypeScript definitions:

```bash
npm install pokemon-tcg-pocket-cards
```

Every file also works as a plain JSON API without npm. The nine payloads are
linked with sizes and descriptions in the [schema comparison](#-schema-comparison)
below. Every payload is also split one file per set under `data/v5/<set>/`,
linked from each **[expansions](https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/data/v5/expansions.json)** entry via its shard URLs.

## 📥 npm entry points

Every card payload ships as a versioned import (`/v5/...`), a short alias for the current version, and a `/no-image` variant without the image URLs. All imports are minified JSON with TypeScript types where shown.

**Full dataset**: every field, all 3,879 prints, images included.

| Import | Notes |
| --- | --- |
| `pokemon-tcg-pocket-cards` | Full v5 dataset (latest) |
| `pokemon-tcg-pocket-cards/v5` | Pinned to v5 |
| `pokemon-tcg-pocket-cards/v5/no-image` | Full dataset, image URLs dropped |

**Core**: slim flat summary, diamonds and promos only, sparse records.

| Import | Notes |
| --- | --- |
| `pokemon-tcg-pocket-cards/v5/core` | Core payload |
| `pokemon-tcg-pocket-cards/v5/core/no-image` | Without the image URL |

**Gameplay**: combat data for simulators, attacks, abilities and stats, no collection metadata.

| Import | Notes |
| --- | --- |
| `pokemon-tcg-pocket-cards/v5/gameplay` | Gameplay payload |
| `pokemon-tcg-pocket-cards/v5/gameplay/no-image` | Without the image URL |

**Collection**: one record per printed card, trading fields derived.

| Import | Notes |
| --- | --- |
| `pokemon-tcg-pocket-cards/v5/collection` | Collection view |
| `pokemon-tcg-pocket-cards/v5/collection/no-image` | Without the image URLs |

**Other**

| Import | Notes |
| --- | --- |
| `pokemon-tcg-pocket-cards/v5/expansions` | Expansions and packs |
| `pokemon-tcg-pocket-cards/expansions` | Alias of `/v5/expansions` |
| `pokemon-tcg-pocket-cards/v4`, `/v4/expansions` | Legacy v4 dataset and expansions |
| `pokemon-tcg-pocket-cards/v1`, `/v2`, `/v3` | Legacy datasets, JSON only |

The bare aliases (`.../core`, `.../gameplay`, `.../collection`, with their `/no-image` siblings) work too and always track the latest version, same data as their `/v5/...` counterpart.

```js
import cards from "pokemon-tcg-pocket-cards";
import core from "pokemon-tcg-pocket-cards/v5/core";
import gameplay from "pokemon-tcg-pocket-cards/v5/gameplay";
import coreNoImage from "pokemon-tcg-pocket-cards/v5/core/no-image";

// Full payload: every field, nested attacks and abilities.
console.log(cards[0].attacks);

// Core payload: gameplay rarities only, about 0.9 MB, suited to web clients.
console.log(core[0].deckBuilderNr);

// Gameplay payload: combat data for simulators, about 1.6 MB minified.
console.log(gameplay[0].attacks);

// Core no-image: the core payload minus image URLs, about 0.6 MB minified.
console.log(coreNoImage[0].deckBuilderNr);

// Full no-image: every field, every print, image URLs dropped (~3.8 MB minified).
import fullNoImage from "pokemon-tcg-pocket-cards/v5/no-image";
console.log(fullNoImage[0].alternate_versions);
```

The pinned imports (`/v5`, `/v5/core`, `/v5/expansions`) keep their resolution when a future major version replaces the root import, so existing consumers can upgrade on their own schedule

For a guide to choosing between the files, see [docs/payloads.md](docs/payloads.md)

Open a pull request if you find missing cards or errors.

### 📦 Moved files

Every dataset now lives under [data/](data/). If you link to a raw file at the repository root, update the URL:

| Old (removed)          | New                                                                    |
|------------------------|------------------------------------------------------------------------|
| `/v1.json`             | [data/v1/cards.json](data/v1/cards.json) ([minified](data/v1/cards.min.json))   |
| `/v2.json`             | [data/v2/cards.json](data/v2/cards.json) ([minified](data/v2/cards.min.json))   |
| `/v3.json`             | [data/v3/cards.json](data/v3/cards.json) ([minified](data/v3/cards.min.json))   |
| `/v4.json`             | [data/v4/cards.json](data/v4/cards.json) ([minified](data/v4/cards.min.json))   |

## 📊 Schema comparison

The full per-payload field comparison lives in
[docs/payloads.md](docs/payloads.md#field-comparison-across-payloads). In
short, all v5 projections share the same card range (2,822 gameplay-rarity
cards); full and collection additionally keep all 3,879 printed cards.

| Payload | Minified size | Purpose |
| --- | --- | --- |
| core | 0.96 MB | Slim summary per gameplay card, webp image included |
| core no-image | 0.59 MB | Core with the image URL dropped |
| gameplay | 1.61 MB | Combat model: attacks, abilities, combat stats |
| gameplay no-image | 1.24 MB | Gameplay with the image URL dropped |
| collection | 2.99 MB | One record per printed card, trading fields derived |
| collection no-image | 1.98 MB | Collection with the image URL dropped |
| full no-image | 3.76 MB | Full payload with both image URLs dropped |
| full | 4.77 MB | Everything the scraper extracts, all 3,879 cards, trading fields included |

### 💼 Support schedule

[💚 V5](data/v5/cards.json) is the actively maintained data model.
[💛 V4](data/v4/cards.min.json) receives updates until the end of the "B" block (its final expansion).
Versions [V3](data/v3/cards.json) and earlier are fully deprecated and no longer updated.

## ⚡ Adding a new expansion

When a new expansion drops, run the script to scrape card data, download card art, and update the JSON files.

```bash
pip install -r requirements.txt
python3 scripts/add_expansion.py <SET_CODE>
```

You can also scrape a chronological range of sets by linking them with an arrow.
```bash
python3 scripts/add_expansion.py a1->b4
```

The script handles these tasks:
1. Detects the expansion name and release date.
2. Scrapes all cards in the specified set or range.
3. Maps internal game asset IDs to `deckBuilderNr`.
4. Downloads [pack and card images](images/).
5. Appends new card records to the target **[JSON](data/v5/cards.json)** database.
6. Adds the expansion entry to the **[expansions](data/v5/expansions.json)** index.

### 🔄 Updating promo sets

Promo sets like P-A and P-B gain cards over time. Run the same command to pull new cards without duplicating existing ones:

```bash
python3 scripts/add_expansion.py PB
```

### ⚙️ Options

- Pass `--name "Custom Name"` to override the expansion name.
- Pass `--skip-images` to skip downloading images.
- Pass `--mode v4` to format the output for the legacy schema.

## 🤝 Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for how to add
card data and the licensing split, the [Code of Conduct](CODE_OF_CONDUCT.md)
before opening a pull request, and [SECURITY.md](SECURITY.md) if you have found a
vulnerability rather than a bug.

## 🛠️ Projects using this API

- **[Pocket Decks Top](https://pocketdecks.top/)** A site that ranks top tournament decks every Monday.
- [Pocket Card Collection](https://github.com/rhuangabrielsantos/pokemon-tcg-pocket-cards) A progress tracker that saves collection data across devices with Google Sign in.
- [PTCGP Pack Opener](https://github.com/rohannishant/ptcgp-pack-opener) A pack opening simulator.
- [All Your Poke Cards](https://github.com/manelbrioude/allyourpokecards) A card information viewer.
- [Pokemon Pocket Card Data](https://github.com/nathanrboyer/PokemonPocketCardData) A notebook that helps you pick packs based on target pulls.
- [Pokemon TCG Pocket Trade Dex](https://github.com/bitmaybewise/pokemon-tcg-pocket-tradedex) A tool to compare card collections between players.

Submit a pull request to list your project here if you build something with this data!

## 💾 Data Source

Card data is scraped from **[Limitless TCG](https://pocket.limitlesstcg.com/cards).**
Deck builder numbers are derived using game asset mappings from the community **[pokemon-tcg-pocket-database](https://github.com/flibustier/pokemon-tcg-pocket-database)**, provided under the MIT License, Copyright (c) 2025 **[Jon (flibustier)](https://github.com/flibustier)**.

## 📜 Licence

- **💚 Version 5** (**[cards.json](data/v5/cards.json)**), **[expansions.json](data/v5/expansions.json)**, and code additions created for **version 5 or later** are licensed under the [GNU Affero General Public License v3.0](https://www.gnu.org/licenses/agpl-3.0.en.html#license-text) (`AGPL-3.0-or-later`).
See **[LICENSE](LICENSE)** for the full license text.
- Legacy card datasets (**[v1.json](data/v1/cards.json), [v2.json](data/v2/cards.json), [v3.json](data/v3/cards.json), [v4.json](data/v4/cards.min.json)**) remain available under the original [MIT License](https://spdx.org/licenses/MIT.html).
See **[LICENSE-MIT](LICENSE-MIT)** for details.
- Third-party components and their notices: **[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)**.
