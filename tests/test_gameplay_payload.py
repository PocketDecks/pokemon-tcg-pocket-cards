"""The gameplay payload is a sparse subset carrying combat data for gameplay rarities."""
import json

import jsonschema

from tests.contract import GAMEPLAY_KEYS
from constants import (
    CARDS_JSON_PATH, CORE_RARITIES, V5_GAMEPLAY_CARDS_SCHEMA_PATH, is_playable_trainer)
import projections as P

_TRAINER_DROPPED = {"stage", "health", "points", "weakness", "retreat",
                    "evolves_from", "ability", "attacks", "ex", "mega",
                    "special_tags"}
NON_FOSSIL_TRAINER_KEYS = set(GAMEPLAY_KEYS) - _TRAINER_DROPPED - {"subtype_2"}
FOSSIL_TRAINER_KEYS = set(GAMEPLAY_KEYS) - (
    _TRAINER_DROPPED - {"stage", "health", "points", "weakness"}) - {"subtype_2"}


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)



def test_gameplay_covers_the_same_cards_as_core():
    full = _load(CARDS_JSON_PATH)
    core = _load(P.V5_CORE_CARDS_PATH)
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    kept_ids = {card["id"] for card in full if card["rarity"] in CORE_RARITIES}
    assert kept_ids == {card["id"] for card in core}
    assert kept_ids == {card["id"] for card in gameplay}
    assert {card["rarity"] for card in full if card["id"] in kept_ids} == set(CORE_RARITIES)


def test_gameplay_records_carry_image():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    assert gameplay
    assert all(record["image"].startswith("https://raw.githubusercontent.com/")
               for record in gameplay)


def test_gameplay_matches_its_schema():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    schema = _load(V5_GAMEPLAY_CARDS_SCHEMA_PATH)
    jsonschema.validate(instance=gameplay, schema=schema)


def test_gameplay_pokemon_records_match_source_projection():
    """Pokemon records keep the full combat projection, omitting only nulls."""
    full = _load(CARDS_JSON_PATH)
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    by_id = {card["id"]: card for card in full}
    for record in gameplay:
        if record["type"] == "Trainer":
            continue
        source = by_id[record["id"]]
        expected = {field for field in GAMEPLAY_KEYS if source.get(field) is not None}
        assert set(record) == expected


def test_gameplay_trainer_records_omit_combat_keys():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    for record in gameplay:
        if record["type"] != "Trainer":
            continue
        assert "ex" not in record
        assert "mega" not in record
        assert "retreat" not in record
        assert "evolves_from" not in record
        assert "ability" not in record
        assert "attacks" not in record
        if is_playable_trainer(record["name"]):
            assert record["stage"] == "Basic"
            assert record["health"] == 40
            assert record["points"] == 1
            assert record["weakness"] == "none"
        else:
            assert "stage" not in record
            assert "health" not in record
            assert "points" not in record
            assert "weakness" not in record


def test_gameplay_non_fossil_trainer_keeps_only_scalar_keys():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    sabrina = next(record for record in gameplay if record["id"] == "a1-225")
    assert sabrina["name"] == "Sabrina"
    assert set(sabrina) == NON_FOSSIL_TRAINER_KEYS


def test_gameplay_fossil_trainer_keeps_combat_keys():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    helix = next(record for record in gameplay if record["id"] == "a1-216")
    assert helix["name"] == "Helix Fossil"
    assert set(helix) == FOSSIL_TRAINER_KEYS
    assert helix["stage"] == "Basic"
    assert helix["health"] == 40
    assert helix["points"] == 1
    assert helix["weakness"] == "none"


def test_gameplay_trainer_shapes_follow_trim_rule():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    for record in gameplay:
        if record["type"] != "Trainer":
            continue
        if is_playable_trainer(record["name"]):
            assert set(record) == FOSSIL_TRAINER_KEYS
            assert record["weakness"] == "none"
        else:
            assert set(record) == NON_FOSSIL_TRAINER_KEYS


def test_gameplay_schema_accepts_trimmed_trainer_records():
    gameplay = _load(P.V5_GAMEPLAY_CARDS_PATH)
    schema = _load(V5_GAMEPLAY_CARDS_SCHEMA_PATH)
    for record in gameplay:
        if record["type"] == "Trainer":
            jsonschema.validate(instance=record, schema=schema["items"])
