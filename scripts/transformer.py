# QR encoding logic ported from [Nirostar/ptcgp-deck-qr/](https://github.com/Nirostar/ptcgp-deck-qr) (MIT License) @ 2026 Nirostar
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
r"""Transform raw scraped card data into the output JSON format.

This module takes the card dicts produced by the scraper and enriches
them with art-style classification, pack points, promo volume grouping,
deck-builder numbers, special tags, and canonical image URLs. It
supports two output formats: ``v5`` (the full enriched schema) and
``v4`` (a reduced schema for backward compatibility).
"""

import re
import requests
from functools import lru_cache
from constants import (SESSION, FLIBUSTIER_PTCGP_DB_URL, GITHUB_BASE_URL, PACK_POINTS, SHINY_PACK_POINTS, TAG_DEFINITIONS, DEFAULT_TIMEOUT, TRADE_RULES)
from utils import set_code_to_prefix, compile_tag_matchers
from deck_code import get_deck_builder_nr
from art_style import ArtStyleClassifier
from pack_resolver import PackResolver

@lru_cache(maxsize=1)
def fetch_datamine_lookup():
    r"""fetch_datamine_lookup() -> dict

    Download the Flibustier PTCGP card database and build a lookup
    table mapping ``(set_code, card_number)`` tuples to deck-builder
    numbers.

    The set codes from the database are normalised to match the
    prefixes used in card IDs: promo codes like ``"promo-a"`` become
    ``"pa"``, and regular codes have hyphens stripped.

    The result is cached for the lifetime of the process, so a run
    that processes many sets downloads the database once.

    Returns:
        dict: keys are ``(str, int)`` tuples of (set prefix, card
        number). Values are deck-builder numbers (int).

    Raises:
        RuntimeError: if the database cannot be downloaded, does not
            return HTTP 200, or parses to an empty lookup.

    .. note::

        This deliberately fails loudly. Returning an empty lookup
        would silently write ``deckBuilderNr: 0`` for every card in
        the run, which passes both the JSON schema and the test
        suite, so a transient network error would poison the dataset
        with no visible symptom.
    """
    lookup = {}
    try:
        resp = SESSION.get(FLIBUSTIER_PTCGP_DB_URL, timeout=DEFAULT_TIMEOUT)
        resp.raise_for_status()
        for card in resp.json():
            c_set = str(card.get("set", "")).lower()
            c_set = f"p{c_set.split('-')[-1]}" if c_set.startswith("promo-") else c_set.replace("-", "")
            c_num = re.sub(r"\D", "", str(card.get("number", "")))
            if c_set and c_num:
                nr = get_deck_builder_nr(card.get("image", ""))  # memoize this if dataset gets huge
                if nr: lookup[(c_set, int(c_num))] = nr
    except (requests.RequestException, ValueError) as e:
        raise RuntimeError(
            f"Could not build the deck-builder lookup from {FLIBUSTIER_PTCGP_DB_URL}: {e}"
        ) from e

    if not lookup:
        raise RuntimeError(
            f"The deck-builder lookup from {FLIBUSTIER_PTCGP_DB_URL} parsed to zero entries. "
            "Refusing to continue, as every card would be written with deckBuilderNr 0."
        )
    return lookup

def _to_v4(card):
    r"""_to_v4(card) -> dict

    Convert a single v5 card dict into the v4 JSON format. Maps v5
    field names to their v4 equivalents and flattens some fields:
    ``art_style`` is reduced to a ``"Yes"``/``"No"`` ``fullart`` flag,
    and ``hp`` is stringified.

    Args:
        card (dict): a card dict in v5 format, as produced by
            :func:`transform_cards`

    Returns:
        dict: the card in v4 format, with keys ``id``, ``name``,
        ``rarity``, ``pack``, ``health``, ``image``, ``fullart``,
        ``ex``, ``artist``, and ``type``
    """
    # v4 has no second-type field, so dual-type Pokemon carry the full
    # "Water/Darkness" string they print on Limitless.
    card_type = card["subtype"] if card["type"] == "Pokémon" else "Trainer"
    if card["type"] == "Pokémon" and card.get("subtype_2"):
        card_type = f"{card['subtype']}/{card['subtype_2']}"
    return {
        "id": card["id"],
        "name": card["name"],
        "rarity": card["rarity"],
        "pack": card["pack"],
        "health": str(card["health"]) if card["health"] else "",
        "image": card["image_png"],
        "fullart": "Yes" if card["rarity"] in {"☆", "☆☆", "☆☆☆", "♕", "Crown Rare"} else "No",
        "ex": "Yes" if card["ex"] else "No",
        "artist": card["artist"],
        "type": card_type
    }


def downgrade_to_v4(cards):
    r"""downgrade_to_v4(cards) -> list of dict

    Convert a list of v5 card dicts to the legacy v4 format.

    Call this *after* the pipeline stages that need v5-only fields.
    In particular :func:`downloader.download_images` reads
    ``source_url``, which :func:`_to_v4` does not carry over, so
    downgrading too early leaves the downloader with nothing to fetch.

    Args:
        cards (list of dict): cards in v5 format

    Returns:
        list of dict: the same cards in v4 format
    """
    return [_to_v4(c) for c in cards]


def strip_source_urls(cards):
    r"""strip_source_urls(cards)

    Remove the in-memory-only ``source_url`` key from every card, in place.

    ``source_url`` is the Limitless artwork URL the downloader fetches from.
    It is not part of the published schema, and ``cards.schema.json`` sets
    ``additionalProperties: false``, so it must be gone before validation.

    Args:
        cards (list of dict): transformed cards, mutated in place
    """
    for card in cards:
        card.pop("source_url", None)


def _trade_rule(rarity, shiny, art_style, card):
    r"""_trade_rule(rarity, shiny, art_style, card) -> tuple

    Look a card up in :data:`TRADE_RULES`. An unknown combination raises
    with the card identified, so a new rarity fails the scrape naming
    the print that caused it rather than with a bare KeyError carrying
    only the tuple.

    Args:
        rarity (str): the card's rarity
        shiny (bool): whether the classifier marked it shiny
        art_style (str | None): the card's art style
        card (dict): the raw card, used only to name it on failure

    Returns:
        tuple: ``(tradable, sharable, trade_cost)``

    Raises:
        KeyError: the combination is not in ``TRADE_RULES``
    """
    key = (rarity, shiny, art_style)
    try:
        return TRADE_RULES[key]
    except KeyError:
        raise KeyError(
            f"no trade rule for {key} "
            f"(card {card.get('name')!r}, number {card.get('number')!r})"
        ) from None


def transform_cards(raw_cards, set_profile, expansion_name, release_date=None):
    r"""transform_cards(raw_cards, set_profile, expansion_name, release_date=None) -> list of dict

    Transform raw scraped card dicts into the output format used by
    the API. Each card is enriched with:

    - Art style (Illustration Art, Full Art, Special Illustration
      Art, Immersive Art, Shiny, Shiny Full Art, Parallel Foil).
      Classification is inferred from rarity sequences and raw text
      duplication between consecutive cards.
    - Pack points from ``PACK_POINTS`` or ``SHINY_PACK_POINTS``
      depending on whether the card is shiny. Promo cards get None.
    - Promo pack volume grouping for ``P-A`` cards, using
      ``PROMO_CARDS_PER_VOLUME`` to split cards into numbered volumes.
    - Deck-builder numbers from the Flibustier datamine lookup.
    - Special tags (ancient, future, ultra beasts) matched against
      card names using compiled regex patterns.
    - Image URLs pointing to the GitHub raw content CDN, in both
      WebP and PNG formats.

    Args:
        raw_cards (list of dict): cards as returned by
            :func:`scrape_cards`, in card-number order, since the
            art-style classifier reads the sequence
        set_profile (SetProfile): the set the cards belong to
        expansion_name (str): human-readable expansion name
            (e.g. ``"Genetic Apex"``)
        release_date (str or None): release date in ``"YYYY-MM-DD"``
            format, included in each card's output. Default: ``None``

    Returns:
        list of dict: one transformed card dict per input card, each
        with about 30 keys spanning identity, classification,
        gameplay, deck-builder, and media fields.

    .. note::

        This function calls :func:`fetch_datamine_lookup` internally.
        That call is cached, so transforming several sets in one run
        downloads the datamine database once. If the download fails
        the lookup raises rather than returning empty, so a network
        error aborts the run instead of writing zeroed
        ``deckBuilderNr`` values.

    .. note::

        ``transform_cards(scrape_cards(SetProfile.of("a1")), SetProfile.of("a1"), "Genetic Apex")``
        gives a first card with ``id`` ``"a1-001"`` and ``name`` ``"Bulbasaur"``.
    """
    specific_packs = {c["pack"] for c in raw_cards if c["pack"] != "Every pack"}
    packs = PackResolver(set_profile, expansion_name, specific_packs)
    art_styles = ArtStyleClassifier()
    datamine_lookup = fetch_datamine_lookup()
    tag_matchers = compile_tag_matchers(TAG_DEFINITIONS)
    missing_deck_nrs = []

    transformed = []
    for card in raw_cards:
        num_zfill = card["number"].zfill(3)
        rarity = card["rarity"]
        art_style, shiny = art_styles.classify(card)

        pack_points = None if set_profile.is_promo else (SHINY_PACK_POINTS if shiny else PACK_POINTS).get(rarity)
        if set_profile.is_promo:
            rarity = "Promo"
            art_style = None
            shiny = False

        pack = packs.resolve(card)

        try:
            deck_builder_nr = datamine_lookup.get((set_profile.prefix.lower(), int(re.sub(r"\D", "", card["number"]))))
        except ValueError:
            deck_builder_nr = None
        if not deck_builder_nr:
            missing_deck_nrs.append(f"{set_profile.prefix}-{num_zfill}")
            deck_builder_nr = 0
        matched_tags = [tag for tag, regex in tag_matchers.items() if regex.search(card["name"])]
        if card.get("subtype_2"):
            matched_tags = ["dual_type"] + matched_tags
        special_tags = matched_tags if matched_tags else None
        tradable, sharable, card_trade_cost = _trade_rule(
            rarity, shiny, art_style, card)

        record_dict = {
            # Core identifiers
            "id": f"{set_profile.prefix}-{num_zfill}",
            "name": card["name"],
            "set_code": set_profile.prefix,
            "set_name": expansion_name,
            "pack": pack,
            "release_date": release_date,

            # Classification
            "type": card["type"],
            "subtype": card["subtype"] or "Unknown",
            "stage": card["stage"],
            "evolves_from": card["evolves_from"],
            "rarity": rarity,
            "pack_points": pack_points,
            # Special properties
            "ex": card["ex"],
            "mega": card["mega"],
            "shiny": shiny,
            "special_tags": special_tags,
            "art_style": art_style,

            # Gameplay mechanics
            "health": card["hp"],
            "retreat": card["retreat"],
            "weakness": card["weakness"],
            "ability": card["ability"],
            "card_text": card["card_text"],
            "attacks": card["attacks"],
            "points": card["points"],

            # Trade rules
            "tradable": tradable,
            "sharable": sharable,
            "trade_cost": card_trade_cost,

            # Deck builder reference
            "deckBuilderNr": deck_builder_nr,

            # Media & Metadata
            "artist": card["artist"],
            "source_url": card["image"],
            "image": f"{GITHUB_BASE_URL}/webp/cards/{set_profile.prefix}/{num_zfill}.webp",
            "image_png": f"{GITHUB_BASE_URL}/png/cards/{set_profile.prefix}/{num_zfill}.png",
            "flavour_text": card["flavour_text"],
            "alternate_versions": [
                {**alt, "set_code": set_code_to_prefix(alt["set_code"].upper())}
                for alt in card["alternate_versions"]
                if f"{set_code_to_prefix(alt['set_code'].upper())}-{str(alt['id']).zfill(3)}" != f"{set_profile.prefix}-{num_zfill}"
            ],
        }
        # Optional second energy type (dual-type Pokemon only); the key is
        # omitted on every other card rather than written as null, and sits
        # in the published position straight after ``subtype``.
        if card.get("subtype_2"):
            record = {}
            for key, value in record_dict.items():
                record[key] = value
                if key == "subtype":
                    record["subtype_2"] = card["subtype_2"]
            record_dict = record
        transformed.append(record_dict)

    if missing_deck_nrs:
        print(f"    WARNING: {len(missing_deck_nrs)} card(s) are not in the deck-builder "
              f"datamine and were written with deckBuilderNr 0: "
              f"{', '.join(missing_deck_nrs[:10])}"
              f"{' ...' if len(missing_deck_nrs) > 10 else ''}")

    return transformed