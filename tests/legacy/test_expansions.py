import os
import re

import pytest
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PNG_PACKS_DIR = os.path.join(ROOT_DIR, "images", "png", "packs")

IMAGE_URL_PREFIX = "https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/images/png/packs/"


# v4 expansion entries carry three fields. release_date, total_cards,
# cards_url and cards_url_min are v5 additions written by
# database.build_expansion_entry and are asserted in tests/test_v5_files.py.
EXPANSION_REQUIRED_FIELDS = ["id", "name", "packs"]
PACK_REQUIRED_FIELDS = ["id", "name", "image", "image_png"]

EXPANSION_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*$")


class TestExpansionsStructure:
    def test_is_non_empty_list(self, expansions):
        assert isinstance(expansions, list) and len(expansions) > 0


    def test_all_entries_are_dicts(self, expansions):
        for i, exp in enumerate(expansions):
            assert isinstance(exp, dict)



class TestExpansionFields:
    def test_all_required_fields_present(self, expansions):
        for exp in expansions:
            for field in EXPANSION_REQUIRED_FIELDS:
                assert field in exp


    def test_no_extra_fields(self, expansions):
        expected = set(EXPANSION_REQUIRED_FIELDS)
        for exp in expansions:
            assert not set(exp.keys()) - expected



class TestExpansionId:
    def test_id_format(self, expansions):
        for exp in expansions:
            assert EXPANSION_ID_PATTERN.match(exp["id"])

    def test_no_duplicate_ids(self, expansions):
        ids = [exp["id"] for exp in expansions]
        assert len(ids) == len(set(ids))


class TestExpansionName:
    def test_name_not_empty(self, expansions):
        for exp in expansions:
            assert exp["name"].strip(), f"Expansion {exp['id']} has empty name"

    def test_name_is_string(self, expansions):
        for exp in expansions:
            assert isinstance(exp["name"], str), (
                f"Expansion {exp['id']} name is not a string"
            )

    def test_name_reasonable_length(self, expansions):
        for exp in expansions:
            assert 2 <= len(exp["name"]) <= 60


class TestExpansionPacks:
    def test_packs_is_non_empty_list(self, expansions):
        for exp in expansions:
            assert isinstance(exp["packs"], list) and len(exp["packs"]) > 0


    def test_pack_has_required_fields(self, expansions):
        for exp in expansions:
            for pack in exp["packs"]:
                for field in PACK_REQUIRED_FIELDS:
                    assert field in pack, (
                        f"Pack in expansion {exp['id']} missing field '{field}'"
                    )

    def test_pack_no_extra_fields(self, expansions):
        expected = set(PACK_REQUIRED_FIELDS)
        for exp in expansions:
            for pack in exp["packs"]:
                extra = set(pack.keys()) - expected
                assert not extra, (
                    f"Pack {pack['id']} has unexpected fields: {extra}"
                )

    def test_pack_id_starts_with_expansion_id(self, expansions):
        for exp in expansions:
            for pack in exp["packs"]:
                assert pack["id"].startswith(exp["id"]), (
                    f"Pack '{pack['id']}' doesn't start with expansion ID '{exp['id']}'"
                )

    def test_no_duplicate_pack_ids(self, expansions):
        all_ids = [pack["id"] for exp in expansions for pack in exp["packs"]]
        assert len(all_ids) == len(set(all_ids))


    def test_pack_name_not_empty(self, expansions):
        for exp in expansions:
            for pack in exp["packs"]:
                assert pack["name"].strip(), (
                    f"Pack {pack['id']} has empty name"
                )

    def test_pack_values_are_strings(self, expansions):
        for exp in expansions:
            for pack in exp["packs"]:
                for field in PACK_REQUIRED_FIELDS:
                    if field in ("image", "image_png") and exp["id"].startswith(("pa", "pb")):
                        assert pack[field] is None, f"Promo pack {pack['id']} field '{field}' should be None"
                    else:
                        assert isinstance(pack[field], str), f"Pack {pack['id']} field '{field}' is not a string"

class TestPackImages:
    def test_pack_image_url_format(self, expansions):
        for exp in expansions:
            for pack in exp["packs"]:
                if pack["image_png"] is not None:
                    assert pack["image_png"].startswith(IMAGE_URL_PREFIX)


    def test_pack_image_url_matches_id(self, expansions):
        for exp in expansions:
            for pack in exp["packs"]:
                if pack["image"] is not None:
                    filename = pack["image"].split("/")[-1]
                    name_without_ext = filename.rsplit(".", 1)[0]
                    assert name_without_ext == pack["id"], (
                        f"Pack {pack['id']} image filename '{filename}' doesn't match pack ID"
                    )

    def test_pack_image_file_exists(self, expansions):
        missing = []
        for exp in expansions:
            for pack in exp["packs"]:
                if pack["id"].startswith(("pa-", "pb-")):
                    continue
                path = os.path.join(PNG_PACKS_DIR, f"{pack['id']}.png")
                if not os.path.exists(path):
                    missing.append(pack["id"])
        assert not missing, f"Missing pack image files: {missing}"