# 🎴 Pokémon TCG Pocket Cards

<p align="center">
  <img alt="npm version" src="https://img.shields.io/npm/v/pokemon-tcg-pocket-cards">
  <img alt="npm downloads" src="https://img.shields.io/npm/dm/pokemon-tcg-pocket-cards">
  <img alt="licence" src="https://img.shields.io/npm/l/pokemon-tcg-pocket-cards">
</p>

This open-source repository holds data on Pokémon TCG Pocket cards. You can use it to build websites, collection trackers, and fan tools.

**Status:** v5 is actively maintained and tracks new set releases. v4 is frozen and receives no further set updates. v3 and earlier are deprecated.

**Requires Node 20.18.3 or newer** for stable JSON-module imports through the package
exports. Tested on Node 22.14 and newer.

Install from npm, which ships the minified data plus TypeScript definitions:

```bash
npm install pokemon-tcg-pocket-cards
```

For measured payload sizes and a full field breakdown, see [docs/payloads.md](docs/payloads.md).

## 📥 Which file do I need?

Pick the payload that matches what you are building. Every payload ships as a
pinned `/v5/...` import, a bare alias that follows the latest version, and a
`/no-image` sibling without image URLs.

| You are building | Use | Import |
| --- | --- | --- |
| A card browser or tool that needs images | core | `pokemon-tcg-pocket-cards/v5/core` |
| The same, images from your own CDN | core no-image | `pokemon-tcg-pocket-cards/v5/core/no-image` |
| A simulator, damage calculator or deck tool | gameplay | `pokemon-tcg-pocket-cards/v5/gameplay` |
| A collection tracker or set browser | collection | `pokemon-tcg-pocket-cards/v5/collection` |
| Something that needs every field and print | full | `pokemon-tcg-pocket-cards` |
| Anything that must not break while you catch up | v4 (frozen) | `pokemon-tcg-pocket-cards/v4` |

Field lists, measured sizes and the full comparison are in
[docs/payloads.md](docs/payloads.md).

### Every entry point

Every payload ships twice: a pinned `/v5/...` path that keeps resolving when a
future major replaces the root import, and a bare alias that always follows the
latest version. Both carry the same data.

| Payload | Pinned | Alias |
| --- | --- | --- |
| full | `pokemon-tcg-pocket-cards/v5` | `pokemon-tcg-pocket-cards` |
| full no-image | `pokemon-tcg-pocket-cards/v5/no-image` | `pokemon-tcg-pocket-cards/no-image` |
| core | `pokemon-tcg-pocket-cards/v5/core` | `pokemon-tcg-pocket-cards/core` |
| core no-image | `pokemon-tcg-pocket-cards/v5/core/no-image` | `pokemon-tcg-pocket-cards/core/no-image` |
| gameplay | `pokemon-tcg-pocket-cards/v5/gameplay` | `pokemon-tcg-pocket-cards/gameplay` |
| gameplay no-image | `pokemon-tcg-pocket-cards/v5/gameplay/no-image` | `pokemon-tcg-pocket-cards/gameplay/no-image` |
| collection | `pokemon-tcg-pocket-cards/v5/collection` | `pokemon-tcg-pocket-cards/collection` |
| collection no-image | `pokemon-tcg-pocket-cards/v5/collection/no-image` | `pokemon-tcg-pocket-cards/collection/no-image` |
| expansions | `pokemon-tcg-pocket-cards/v5/expansions` | `pokemon-tcg-pocket-cards/expansions` |

Legacy datasets stay importable, untyped where marked:

| Dataset | Import | Notes |
| --- | --- | --- |
| v4 | `pokemon-tcg-pocket-cards/v4` | Frozen, typed |
| v4 expansions | `pokemon-tcg-pocket-cards/v4/expansions` | Frozen, typed |
| v1, v2, v3 | `pokemon-tcg-pocket-cards/v1`, `/v2`, `/v3` | Deprecated, JSON only |

## 🚀 Usage

```js
import cards from "pokemon-tcg-pocket-cards" with { type: "json" };
import core from "pokemon-tcg-pocket-cards/v5/core" with { type: "json" };

console.log(cards[0].attacks);
console.log(core[0].deckBuilderNr);
```

Save it as a `.mjs` file and run it with Node 22.14 or newer. The
`with { type: "json" }` attribute is required for JSON module imports.

Every payload is also a plain JSON URL, with no npm involved:

```js
const cards = await (await fetch(
  "https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/data/v5/cards.core.min.json"
)).json();
```

Each payload is additionally split one file per set under `data/v5/<set>/`,
with URLs listed in each entry of the
[expansions index](https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/data/v5/expansions.json).

## 📊 What it contains

All v5 projections share one card range (3,377 gameplay-rarity cards). The full
and collection payloads additionally keep every printed card (4,547). Each
payload's fields are listed in [docs/payloads.md](docs/payloads.md#field-comparison-across-payloads);
sizes are measured from the shipped files there rather than repeated here.

## 🛠️ Maintaining the data

Scraping a new set, updating promo sets and the legacy v4 output are documented
in [docs/how-to.md](docs/how-to.md).

## 🤝 Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) for how to add
card data and the licensing split, the [Code of Conduct](CODE_OF_CONDUCT.md)
before opening a pull request, and [SECURITY.md](SECURITY.md) if you have found a
vulnerability rather than a bug.

## 🎮 Projects using this API

- **[Pocket Decks Top](https://pocketdecks.top/)** A site that ranks top tournament decks every Monday.
- [Pocket Card Collection](https://github.com/rhuangabrielsantos/pokemon-tcg-pocket-cards) A progress tracker that saves collection data across devices with Google Sign in.
- [PTCGP Pack Opener](https://github.com/rohannishant/ptcgp-pack-opener) A pack opening simulator.
- [All Your Poke Cards](https://github.com/manelbrioude/allyourpokecards) A card information viewer.
- [Pokemon Pocket Card Data](https://github.com/nathanrboyer/PokemonPocketCardData) A notebook that helps you pick packs based on target pulls.
- [Pokemon TCG Pocket Trade Dex](https://github.com/bitmaybewise/pokemon-tcg-pocket-tradedex) A tool to compare card collections between players.
- [Pokémon TCG Card Bot](https://github.com/leonid-dalin/pokemon-tcg-card-bot) A Discord bot that looks up cards from a slash command or an inline `[[card]]` mention.

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

## 📚 Reference

- [docs/payloads.md](docs/payloads.md) - payload choice, field comparison, trading rules, measured sizes, per-set shards.
- [docs/reference.md](docs/reference.md) - every field in every schema.
- [docs/how-to.md](docs/how-to.md) - scraping a set, including promo updates and legacy v4 output.
- [Moved files](docs/moved-files.md) - old root-level dataset paths and where they went.

