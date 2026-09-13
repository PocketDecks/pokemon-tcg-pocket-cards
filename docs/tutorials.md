# Tutorials

## Fetch the API for the first time
You can pull the JSON data directly into your application without running the scraper. The [V5](../data/v5/cards.min.json) dataset is served straight from the repository. Use a standard HTTP GET request to retrieve it.


```javascript
async function loadCardData() {
  const response = await fetch(
    "https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/data/v5/cards.min.json"
  );
  const cards = await response.json();

  console.log(cards[0].name, cards[0].deckBuilderNr);
}
```

If you are on npm, install the package instead and skip the fetch entirely:

```bash
npm install pokemon-tcg-pocket-cards
```

```javascript
import cards from "pokemon-tcg-pocket-cards";
import expansions from "pokemon-tcg-pocket-cards/expansions";
```

For a lighter download, import the core payload instead. It keeps the gameplay-essential fields (identity, set, combat stats, deck builder number, image) and drops the rest, which cuts the transfer from about 4.6 MB to about 0.9 MB:

```javascript
import core from "pokemon-tcg-pocket-cards/v5/core";
```

If you run a battle simulator, import the gameplay payload for attacks, abilities, and combat stats including the card image (about 1.6 MB):

```javascript
import gameplay from "pokemon-tcg-pocket-cards/v5/gameplay";
```

If you serve card data over a narrow connection, import the gameplay payload without the image URL (about 1.2 MB):

```javascript
import gameplayNoImage from "pokemon-tcg-pocket-cards/v5/gameplay/no-image";
```

If you build a collection tracker or set browser, import the collection payload for one record per printed card with trading fields (about 3.0 MB):

```javascript
import collection from "pokemon-tcg-pocket-cards/v5/collection";
```

If you serve card data over a narrow connection, import the core payload without the image URL (about 0.6 MB):

```javascript
import coreNoImage from "pokemon-tcg-pocket-cards/v5/core/no-image";
```

To load a single expansion instead of the whole dataset, fetch a per-set shard. Each entry in the expansions index carries `cards_gameplay_url` and its `_min` sibling, so you can pull just the gameplay cards for one set at a fraction of the full download:

```javascript
const expansions = await (
  await fetch("https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/data/v5/expansions.min.json")
).json();
const apex = expansions.find((entry) => entry.id === "a1");
const cards = await (await fetch(apex.cards_gameplay_url_min)).json();
console.log(cards.length, cards[0].name);
```


## Set up the local environment

To run the scraper yourself, you need Python 3.9+ installed on your machine.

1. Clone the repository to your local machine.
2. Open a terminal and navigate to the project directory.
3. Install the required dependencies.
```pip install -r requirements.txt```
4. Run the scraper against a set code. Preferably, one that is either incomplete or doesn't exist within the current [cards.json](../data/v5/cards.min.json).
```bash
python3 scripts/add_expansion.py b4a
```