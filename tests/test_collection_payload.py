"""The collection payload is one sparse record per printed card, carrying
collection fields plus the derived trading fields."""
import json

import jsonschema

from constants import (
    CARDS_JSON_PATH, TRADE_RULES, V5_COLLECTION_CARDS_SCHEMA_PATH, V5_COLLECTION_NO_IMAGE_CARDS_SCHEMA_PATH)
import projections as P

GAMEPLAY_ONLY_FIELDS = {"attacks", "ability", "health"}

TRADE_SPOT_CHECKS = {
    ("◊", False, None): (True, True, 0),
    ("◊◊", False, None): (True, True, 0),
    ("◊◊◊", False, None): (True, True, 1200),
    ("◊◊◊◊", False, None): (True, True, 5000),
    ("☆", False, "Illustration Art"): (True, False, 4000),
    ("☆☆", False, "Full Art"): (True, False, 25000),
    ("☆☆", True, "Shiny Full Art"): (True, False, 30000),
    ("☆☆☆", False, "Immersive Art"): (False, False, None),
    ("Crown Rare", False, None): (False, False, None),
    ("Promo", False, None): (False, False, None),
}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_collection_has_one_record_per_printed_card():
    full = _load(CARDS_JSON_PATH)
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    assert len(full) == 4317
    assert len(collection) == 4317
    assert {card["id"] for card in full} == {card["id"] for card in collection}


def test_collection_records_all_carry_trading_fields():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    assert collection
    for record in collection:
        assert "tradable" in record
        assert "sharable" in record
        assert "trade_cost" in record


def test_collection_trade_rules_cover_every_record():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    for record in collection:
        key = (record["rarity"], record.get("shiny", False), record.get("art_style"))
        assert key in TRADE_RULES, key


def test_collection_trade_values_match_the_rule_table():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    seen = set()
    for record in collection:
        key = (record["rarity"], record.get("shiny", False), record.get("art_style"))
        if key in seen:
            continue
        seen.add(key)
        expected = TRADE_RULES[key]
        assert (record["tradable"], record["sharable"], record["trade_cost"]) == expected


def test_collection_trade_spot_checks_per_bucket():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    for key, expected in TRADE_SPOT_CHECKS.items():
        rarity, shiny, art_style = key
        matches = [
            record for record in collection
            if record["rarity"] == rarity
            and record.get("shiny", False) == shiny
            and record.get("art_style") == art_style
        ]
        assert matches, key
        assert (matches[0]["tradable"], matches[0]["sharable"],
                matches[0]["trade_cost"]) == expected


def test_collection_crown_and_promo_are_not_tradable():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    for record in collection:
        if record["rarity"] in ("Crown Rare", "Promo"):
            assert record["tradable"] is False
            assert record["sharable"] is False
            assert record["trade_cost"] is None


def test_collection_records_carry_no_gameplay_only_fields():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    assert collection
    for record in collection:
        assert GAMEPLAY_ONLY_FIELDS.isdisjoint(record)


def test_collection_matches_its_schema():
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    schema = _load(V5_COLLECTION_CARDS_SCHEMA_PATH)
    jsonschema.validate(instance=collection, schema=schema)


def test_collection_no_image_has_one_record_per_printed_card():
    full = _load(CARDS_JSON_PATH)
    collection = _load(P.V5_COLLECTION_CARDS_PATH)
    no_image = _load(P.V5_COLLECTION_NO_IMAGE_CARDS_PATH)
    assert len(full) == 4317
    assert len(no_image) == 4317
    assert len(collection) == len(no_image)
    assert {card["id"] for card in collection} == {card["id"] for card in no_image}


def test_collection_no_image_records_carry_no_image_urls():
    no_image = _load(P.V5_COLLECTION_NO_IMAGE_CARDS_PATH)
    assert no_image
    for record in no_image:
        assert "image" not in record
        assert "image_png" not in record


def test_collection_no_image_records_carry_trading_fields():
    no_image = _load(P.V5_COLLECTION_NO_IMAGE_CARDS_PATH)
    for record in no_image:
        assert "tradable" in record
        assert "sharable" in record
        assert "trade_cost" in record


def test_collection_no_image_matches_its_schema():
    no_image = _load(P.V5_COLLECTION_NO_IMAGE_CARDS_PATH)
    schema = _load(V5_COLLECTION_NO_IMAGE_CARDS_SCHEMA_PATH)
    jsonschema.validate(instance=no_image, schema=schema)
