# Copyright (C) 2024 Chase Manning <chase@manning.dev>
# Copyright (C) 2026 Leonid Dalin <infoLeonid@protonmail.com> & Chase Manning <chase@manning.dev>
#
# Original code by Chase Manning is released under the MIT License.
# Modifications and additions for version 5 onwards are released under
# the GNU Affero General Public License v3.0 (AGPL-3.0-or-later).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
import os
import re

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

BASE_URL = "https://pocket.limitlesstcg.com/cards/"
GITHUB_BASE_URL = (
    "https://raw.githubusercontent.com/PocketDecks/"
    "pokemon-tcg-pocket-cards/refs/heads/main/images"
)
V5_CARDS_URL_BASE = (
    "https://raw.githubusercontent.com/PocketDecks/"
    "pokemon-tcg-pocket-cards/refs/heads/main/data/v5"
)
LIMITLESS_HOST = re.compile(
    r"^limitlesstcg\.com$"
    r"|^[a-z0-9-]+\.limitlesstcg\.com$"
    r"|^limitlesstcg\.[a-z0-9-]+\.cdn\.digitaloceanspaces\.com$"
)
SEREBII_BASE_URL = "https://www.serebii.net/tcgpocket/"
FLIBUSTIER_PTCGP_DB_URL = "https://cdn.jsdelivr.net/npm/pokemon-tcg-pocket-database@latest/dist/cards.json"

# ---------------------------------------------------------------------------
# HTTP Session
# ---------------------------------------------------------------------------

SESSION = requests.Session()
SESSION.headers["User-Agent"] = (
    "pokemon-tcg-pocket-cards/1.0 (+https://github.com/PocketDecks/pokemon-tcg-pocket-cards)"
)
retries = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
)
SESSION.mount("https://", HTTPAdapter(max_retries=retries))
SESSION.mount("http://", HTTPAdapter(max_retries=retries))

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)

# Versioned data
DATA_DIR = os.path.join(ROOT_DIR, "data")
V4_JSON_PATH = os.path.join(DATA_DIR, "v4", "cards.json")
V4_EXPANSIONS_JSON_PATH = os.path.join(DATA_DIR, "v4", "expansions.json")  # frozen v4-era index
V5_DIR = os.path.join(DATA_DIR, "v5")
EXPANSIONS_JSON_PATH = os.path.join(V5_DIR, "expansions.json")
CARDS_JSON_PATH = os.path.join(V5_DIR, "cards.json")
CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.schema.json")
EXPANSIONS_SCHEMA_PATH = os.path.join(V5_DIR, "expansions.schema.json")
V5_CORE_CARDS_PATH = os.path.join(V5_DIR, "cards.core.json")
V5_CORE_CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.core.schema.json")
V5_CORE_NO_IMAGE_CARDS_PATH = os.path.join(V5_DIR, "cards.core.no-image.json")
V5_CORE_NO_IMAGE_CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.core.no-image.schema.json")
V5_GAMEPLAY_CARDS_PATH = os.path.join(V5_DIR, "cards.gameplay.json")
V5_GAMEPLAY_CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.gameplay.schema.json")
V5_GAMEPLAY_NO_IMAGE_CARDS_PATH = os.path.join(V5_DIR, "cards.gameplay.no-image.json")
V5_GAMEPLAY_NO_IMAGE_CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.gameplay.no-image.schema.json")
V5_COLLECTION_CARDS_PATH = os.path.join(V5_DIR, "cards.collection.json")
V5_COLLECTION_CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.collection.schema.json")
V5_COLLECTION_NO_IMAGE_CARDS_PATH = os.path.join(V5_DIR, "cards.collection.no-image.json")
V5_COLLECTION_NO_IMAGE_CARDS_SCHEMA_PATH = os.path.join(V5_DIR, "cards.collection.no-image.schema.json")
V4_CARDS_SCHEMA_PATH = os.path.join(DATA_DIR, "v4", "cards.schema.json")
V4_EXPANSIONS_SCHEMA_PATH = os.path.join(DATA_DIR, "v4", "expansions.schema.json")

# Images
IMAGES_DIR = os.path.join(ROOT_DIR, "images")
WEBP_CARDS_DIR = os.path.join(IMAGES_DIR, "webp", "cards")
PNG_CARDS_DIR = os.path.join(IMAGES_DIR, "png", "cards")
WEBP_PACKS_DIR = os.path.join(IMAGES_DIR, "webp", "packs")
PNG_PACKS_DIR = os.path.join(IMAGES_DIR, "png", "packs")

# ---------------------------------------------------------------------------
# Card Data
# ---------------------------------------------------------------------------

ENERGY_TYPES = (
    "Grass", "Fire", "Water", "Lightning", "Psychic", "Fighting",
    "Darkness", "Metal", "Dragon", "Colorless",
)
STAGES = ("Basic", "Stage 1", "Stage 2")
RARITIES = ("◊", "◊◊", "◊◊◊", "◊◊◊◊", "☆", "☆☆", "☆☆☆", "Crown Rare", "Promo")
CORE_RARITIES = ("◊", "◊◊", "◊◊◊", "◊◊◊◊", "Promo")
GAMEPLAY_FIELDS = (
    "id", "name", "set_code", "type", "subtype", "stage", "evolves_from",
    "special_tags", "health", "retreat", "weakness", "ability", "attacks",
    "card_text", "points", "ex", "mega", "deckBuilderNr", "image",
)
GAMEPLAY_NO_IMAGE_FIELDS = tuple(field for field in GAMEPLAY_FIELDS if field != "image")
COLLECTION_FIELDS = (
    "id", "name", "set_code", "set_name", "pack", "release_date", "rarity",
    "pack_points", "art_style", "artist", "flavour_text", "alternate_versions",
    "image", "image_png", "ex", "mega", "shiny", "special_tags",
    "tradable", "sharable", "trade_cost",
)
TRADE_RULES = {
    ("◊", False, None): (True, True, 0),
    ("◊", False, "Parallel Foil"): (True, True, 0),
    ("◊◊", False, None): (True, True, 0),
    ("◊◊", False, "Parallel Foil"): (True, True, 0),
    ("◊◊◊", False, None): (True, True, 1200),
    ("◊◊◊", False, "Parallel Foil"): (True, True, 1200),
    ("◊◊◊◊", False, None): (True, True, 5000),
    ("☆", False, "Illustration Art"): (True, False, 4000),
    ("☆", True, "Shiny"): (True, False, 10000),
    ("☆☆", False, "Full Art"): (True, False, 25000),
    ("☆☆", False, "Special Illustration Art"): (True, False, 25000),
    ("☆☆", True, "Shiny Full Art"): (True, False, 30000),
    # No print today carries a star rarity without an art style, so these
    # two rows are speculative; they are kept so a future print missing
    # its art style resolves instead of raising.
    ("☆☆", False, None): (True, False, 25000),
    ("☆", False, None): (True, False, 4000),
    ("☆☆☆", False, "Immersive Art"): (False, False, None),
    ("Crown Rare", False, None): (False, False, None),
    ("Promo", False, None): (False, False, None),
}
PARALLEL_FOIL_RARITIES = ("◊", "◊◊", "◊◊◊")
ART_STYLES = (
    "Illustration Art", "Full Art", "Special Illustration Art",
    "Immersive Art", "Shiny", "Shiny Full Art", "Parallel Foil",
)
TRAINER_SUBTYPES = ("Supporter", "Stadium", "Tool", "Item")
PROMO_PREFIXES = ("pa", "pb")


def is_playable_trainer(name):
    """A trainer that plays as a Pokemon: the Fossil family and Old Amber."""
    return name.endswith("Fossil") or name == "Old Amber"
FIRST_RELEASE = "2024-10-30"  # A1

# ---------------------------------------------------------------------------
# Pack Points
# ---------------------------------------------------------------------------

PACK_POINTS = {
    "◊": 35, "◊◊": 70, "◊◊◊": 150, "◊◊◊◊": 500,
    "☆": 400, "☆☆": 1250, "☆☆☆": 1500,
    "♕": 2500, "Crown Rare": 2500,
}
SHINY_PACK_POINTS = {"☆": 1000, "☆☆": 1350, "☆☆☆": 1500}

# ---------------------------------------------------------------------------
# Tag Definitions
# ---------------------------------------------------------------------------

TAG_DEFINITIONS = {
    "ancient": [
        "Great Tusk", "Scream Tail", "Brute Bonnet", "Flutter Mane",
        "Slither Wing", "Sandy Shocks", "Roaring Moon", "Koraidon",
        "Walking Wake", "Gouging Fire", "Raging Bolt", "Sada", "Sada's",
    ],
    "future": [
        "Iron Treads", "Iron Bundle", "Iron Hands", "Iron Jugulis",
        "Iron Moth", "Iron Thorns", "Iron Valiant", "Miraidon",
        "Iron Leaves", "Iron Boulder", "Iron Crown", "Turo", "Turo's",
    ],
    "ultra_beasts": [
        "Nihilego", "Buzzwole", "Pheromosa", "Xurkitree", "Celesteela",
        "Kartana", "Guzzlord", "Poipole", "Naganadel", "Stakataka",
        "Blacephalon", "Dawn Wings Necrozma", "Dusk Mane Necrozma",
        "Necrozma", "Ultra Necrozma", "Lusamine", "Lusamine's",
    ],
}

# ---------------------------------------------------------------------------
# Operational Constants
# ---------------------------------------------------------------------------

MAX_CONSECUTIVE_ERRORS = 5      # missing cards in a row = end of set
MAX_RETRIES = 3                 # network retries per page
DEFAULT_TIMEOUT = 15
IMAGE_TIMEOUT = 30
RATE_LIMIT_DELAY = 0.05

# ---------------------------------------------------------------------------
# Promo
# ---------------------------------------------------------------------------

PROMO_A_PACK_KEYWORDS = [
    "Premium Missions",
    "Missions",
    "Shop",
    "Campaign",
    "Promo pack",
    "Wonder Pick",
]
PROMO_CARDS_PER_VOLUME = 5
