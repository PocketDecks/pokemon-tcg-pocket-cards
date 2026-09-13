"""The full no-image payload: every field of the full dataset minus image URLs."""

import json

import jsonschema

from constants import CARDS_JSON_PATH, V5_DIR
import projections as P


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def test_full_no_image_has_one_record_per_card():
    full = _load(CARDS_JSON_PATH)
    no_image = _load(P.ROOT_PATHS["no-image"])
    assert len(full) == 3879
    assert len(no_image) == 3879
    assert [card["id"] for card in full] == [card["id"] for card in no_image]


def test_full_no_image_drops_only_the_image_keys():
    full = _load(CARDS_JSON_PATH)
    no_image = _load(P.ROOT_PATHS["no-image"])
    for dense, sparse in zip(full, no_image):
        assert {k: v for k, v in dense.items() if k not in ("image", "image_png")} == sparse


def test_full_no_image_records_carry_no_image_urls():
    no_image = _load(P.ROOT_PATHS["no-image"])
    assert no_image
    for record in no_image:
        assert "image" not in record
        assert "image_png" not in record


def test_full_no_image_keeps_the_dense_null_padded_shape():
    no_image = _load(P.ROOT_PATHS["no-image"])
    schema = _load(f"{V5_DIR}/cards.no-image.schema.json")
    keys = set(schema["items"]["properties"])
    for record in no_image:
        assert set(record) == keys, "full no-image records keep nulls, like the full payload"


def test_full_no_image_matches_its_schema():
    no_image = _load(P.ROOT_PATHS["no-image"])
    schema = _load(f"{V5_DIR}/cards.no-image.schema.json")
    jsonschema.validate(instance=no_image, schema=schema)
