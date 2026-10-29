"""Artifact-level checks on the committed v5 files.

test_v5_schema.py validates card *fields*; this module validates the *files*:
that the published schemas accept the data, that every derived file agrees
with its source, and that the on-disk layout matches what expansions.json and
package.json promise consumers.
"""
import json
import os

import jsonschema
import pytest

from constants import CARDS_SCHEMA_PATH, DATA_DIR, EXPANSIONS_SCHEMA_PATH, ROOT_DIR, V5_DIR
from database import _set_sort_key
from projections import SHARD_VARIANTS
from utils import minified_path
from tests.contract import CARD_KEYS, V4_CARD_KEYS
from tests.utils import _load, report

CARDS_DTS_PATH = os.path.join(V5_DIR, "cards.d.ts")


def data_json_files():
    """Every .json under data/, excluding the .min.json siblings."""
    return [os.path.join(root, name)
            for root, _, names in os.walk(DATA_DIR)
            for name in names
            if name.endswith(".json") and not name.endswith(".min.json")]


def set_dirs():
    return sorted(name for name in os.listdir(V5_DIR)
                  if os.path.isdir(os.path.join(V5_DIR, name)))


@pytest.fixture(scope="session")
def cards_schema():
    return _load(CARDS_SCHEMA_PATH)


@pytest.fixture(scope="session")
def expansions_schema():
    return _load(EXPANSIONS_SCHEMA_PATH)


@pytest.fixture(scope="session")
def per_set_cards():
    """{set: cards as stored in data/v5/<set>/<set>.json}"""
    return {name: _load(os.path.join(V5_DIR, name, f"{name}.json")) for name in set_dirs()}


# ---------------------------------------------------------------------------
# Published schemas
# ---------------------------------------------------------------------------

class TestSchemaValidation:
    def test_cards_json_matches_its_schema(self, cards, cards_schema):
        jsonschema.validate(instance=cards, schema=cards_schema)

    def test_expansions_json_matches_its_schema(self, expansions, expansions_schema):
        jsonschema.validate(instance=expansions, schema=expansions_schema)

    def test_every_set_file_matches_the_card_schema(self, per_set_cards, cards_schema):
        validator = jsonschema.Draft7Validator(cards_schema)
        fails = [f"{name}: {error.json_path} {error.message}"
                 for name, group in per_set_cards.items()
                 for error in list(validator.iter_errors(group))[:1]]
        assert not fails, report(fails)

    def test_schema_rejects_an_unknown_field(self, cards, cards_schema):
        """additionalProperties:false is what keeps source_url out of the output."""
        leaked = [{**cards[0], "source_url": "https://example.invalid/1.webp"}]
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(instance=leaked, schema=cards_schema)

    def test_the_contract_matches_the_published_data(self, cards):
        """CARD_KEYS is derived from the schema, so this is what pins it to reality.

        subtype_2 is the one optional key: only dual-type Pokemon carry it."""
        assert tuple(cards[0]) == tuple(k for k in CARD_KEYS if k != "subtype_2")
        assert all(set(c) <= set(CARD_KEYS) for c in cards)
        dual = [c for c in cards if "subtype_2" in c]
        assert dual and all("dual_type" in c["special_tags"] for c in dual)

    def test_the_v4_contract_matches_the_published_v4_data(self, v4_cards):
        """V4_CARD_KEYS is derived from the v4 schema, so this pins it to reality."""
        from tests.contract import V4_CARD_KEYS
        assert all(set(c) == set(V4_CARD_KEYS) for c in v4_cards)

    def test_every_field_is_required(self, cards_schema):
        """Consumers can index any key without a guard, with one documented
        exception: subtype_2 is optional and only dual-type Pokemon carry it."""
        assert set(cards_schema["items"]["required"]) == (
            set(cards_schema["items"]["properties"]) - {"subtype_2"})

    def test_schema_id_points_at_its_own_filename(self, cards_schema, expansions_schema):
        assert cards_schema["$id"].endswith("/data/v5/cards.schema.json")
        assert expansions_schema["$id"].endswith("/data/v5/expansions.schema.json")


class TestTypeScriptDefinitions:
    def test_types_are_generated_from_the_current_schema(self):
        """Every field is declared; subtype_2 is the one optional field."""
        declarations = open(CARDS_DTS_PATH, encoding="utf-8").read()
        missing = [key for key in CARD_KEYS if f"  {key}: " not in declarations
                   and f"  {key}?: " not in declarations]
        optional = [key for key in CARD_KEYS if f"  {key}?: " in declarations]
        assert not missing, f"cards.d.ts is stale, missing: {missing}"
        assert optional == ["subtype_2"], f"unexpected optional fields: {optional}"


# ---------------------------------------------------------------------------
# Derived files
# ---------------------------------------------------------------------------

class TestDerivedFiles:
    def test_every_json_file_has_a_minified_sibling(self):
        missing = [os.path.relpath(path, ROOT_DIR) for path in data_json_files()
                   if "schema" not in os.path.basename(path)
                   and not os.path.exists(minified_path(path))]
        assert not missing, f"Files with no .min.json sibling: {missing}"

    def test_minified_files_parse_to_the_same_data(self):
        fails = []
        for path in data_json_files():
            minified = minified_path(path)
            if not os.path.exists(minified):
                continue
            if _load(path) != _load(minified):
                fails.append(os.path.relpath(path, ROOT_DIR))
        assert not fails, f"Minified files out of sync: {fails}"

    def test_minified_files_are_actually_compact(self):
        fat = [os.path.relpath(minified_path(path), ROOT_DIR) for path in data_json_files()
               if os.path.exists(minified_path(path))
               and "\n" in open(minified_path(path), encoding="utf-8").read()]
        assert not fat, f"Minified files containing newlines: {fat}"

    def test_data_files_are_lf_only(self):
        crlf = [os.path.relpath(os.path.join(root, name), ROOT_DIR)
                for root, _, names in os.walk(DATA_DIR)
                for name in names
                if name.endswith((".json", ".ts"))
                and b"\r\n" in open(os.path.join(root, name), "rb").read()]
        assert not crlf, f"Files with CRLF line endings: {crlf}"

    def test_data_files_are_utf8_without_a_bom(self):
        bom = [os.path.relpath(path, ROOT_DIR) for path in data_json_files()
               if open(path, "rb").read(3) == b"\xef\xbb\xbf"]
        assert not bom, f"Files with a UTF-8 BOM: {bom}"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

class TestLayout:
    def test_master_file_is_the_union_of_the_set_files(self, cards, per_set_cards):
        from_sets = [card for group in per_set_cards.values() for card in group]
        assert sorted(c["id"] for c in cards) == sorted(c["id"] for c in from_sets)

    def test_set_files_hold_the_same_records_as_the_master_file(self, cards, per_set_cards):
        by_id = {c["id"]: c for c in cards}
        fails = [card["id"] for group in per_set_cards.values() for card in group
                 if by_id.get(card["id"]) != card]
        assert not fails, f"{len(fails)} records differ between cards.json and the set file: {fails[:10]}"

    def test_each_set_file_holds_only_its_own_set(self, per_set_cards):
        fails = [f"{name}: {sorted({c['set_code'] for c in group})}"
                 for name, group in per_set_cards.items()
                 if {c["set_code"] for c in group} != {name}]
        assert not fails, f"Set files holding foreign cards: {fails}"

    def test_set_files_are_sorted_by_card_number(self, per_set_cards):
        unsorted_sets = [name for name, group in per_set_cards.items()
                         if [int(c["id"].rsplit("-", 1)[1]) for c in group]
                         != sorted(int(c["id"].rsplit("-", 1)[1]) for c in group)]
        assert not unsorted_sets, f"Set files not in card order: {unsorted_sets}"

    def test_master_file_is_in_natural_set_order(self, cards):
        keys = [(_set_sort_key(c["set_code"]), int(c["id"].rsplit("-", 1)[1])) for c in cards]
        assert keys == sorted(keys), "cards.json is not sorted by set then card number"

    def test_every_set_directory_has_an_expansion_entry(self, expansions):
        assert set(set_dirs()) == {e["id"] for e in expansions}

    def test_cards_url_resolves_to_a_file_that_exists(self, expansions):
        missing = []
        for exp in expansions:
            for key, suffix in (("cards_url", ".json"), ("cards_url_min", ".min.json")):
                relative = exp[key].split("/refs/heads/main/", 1)[1]
                if not os.path.exists(os.path.join(ROOT_DIR, relative)):
                    missing.append(f"{exp['id']}: {relative}")
        assert not missing, report(missing)

    def test_total_cards_matches_the_set_file(self, expansions, per_set_cards):
        wrong = {e["id"]: (e["total_cards"], len(per_set_cards.get(e["id"], [])))
                 for e in expansions
                 if e["total_cards"] != len(per_set_cards.get(e["id"], []))}
        assert not wrong, f"total_cards out of date (declared, actual): {wrong}"

    def test_expansion_release_date_is_the_earliest_card_date(self, expansions, per_set_cards):
        wrong = []
        for exp in expansions:
            dates = [c["release_date"] for c in per_set_cards.get(exp["id"], []) if c["release_date"]]
            expected = min(dates) if dates else None
            if exp["release_date"] != expected:
                wrong.append(f"{exp['id']}: {exp['release_date']} != {expected}")
        assert not wrong, report(wrong)

    def test_expansion_and_pack_ids_are_unique(self, expansions):
        exp_ids = [e["id"] for e in expansions]
        pack_ids = [p["id"] for e in expansions for p in e["packs"]]
        assert len(exp_ids) == len(set(exp_ids)), "duplicate expansion ids"
        assert len(pack_ids) == len(set(pack_ids)), "duplicate pack ids"

    def test_pack_ids_are_prefixed_with_their_expansion(self, expansions):
        stray = [p["id"] for e in expansions for p in e["packs"]
                 if not p["id"].startswith(f"{e['id']}-")]
        assert not stray, f"Pack ids not prefixed by their expansion: {stray}"


# ---------------------------------------------------------------------------
# Per-set shards
# ---------------------------------------------------------------------------

class TestPerSetShards:
    def test_shard_record_counts_sum_to_payload_totals(self):
        for variant, _url_stem, filename, _builder in SHARD_VARIANTS:
            total = len(_load(os.path.join(V5_DIR, filename)))
            from_shards = sum(
                len(_load(os.path.join(V5_DIR, prefix, f"{prefix}.{variant}.json")))
                for prefix in set_dirs())
            assert from_shards == total, f"{variant}: {from_shards} != {total}"

    def test_shard_records_match_the_root_payload_records(self):
        for variant, _url_stem, filename, _builder in SHARD_VARIANTS:
            root = {record["id"]: record
                    for record in _load(os.path.join(V5_DIR, filename))}
            for prefix in set_dirs():
                for record in _load(os.path.join(V5_DIR, prefix, f"{prefix}.{variant}.json")):
                    assert record == root[record["id"]], \
                        f"{variant} {prefix} {record['id']} differs from its root payload record"

    def test_every_index_entry_carries_all_twelve_variant_urls(self, expansions):
        keys = [f"{url_stem}{suffix}"
                for _variant, url_stem, _root_path, _builder in SHARD_VARIANTS
                for suffix in ("_url", "_url_min")]
        missing = [f"{exp['id']}: {key}" for exp in expansions for key in keys
                   if key not in exp]
        assert not missing, report(missing)

    def test_variant_urls_resolve_to_files_on_disk(self, expansions):
        missing = []
        for exp in expansions:
            for _variant, url_stem, _root_path, _builder in SHARD_VARIANTS:
                for suffix in ("_url", "_url_min"):
                    relative = exp[f"{url_stem}{suffix}"].split("/refs/heads/main/", 1)[1]
                    if not os.path.exists(os.path.join(ROOT_DIR, relative)):
                        missing.append(f"{exp['id']}: {relative}")
        assert not missing, report(missing)


# ---------------------------------------------------------------------------
# npm package
# ---------------------------------------------------------------------------

class TestPackagedFiles:
    @pytest.fixture(scope="session")
    def package_json(self):
        return _load(os.path.join(ROOT_DIR, "package.json"))

    def test_every_export_target_exists(self, package_json):
        targets = []
        for value in package_json["exports"].values():
            targets.extend(value.values() if isinstance(value, dict) else [value])
        missing = [t for t in targets
                   if "*" not in t and not os.path.exists(os.path.join(ROOT_DIR, t))]
        assert not missing, f"package.json exports missing from disk: {missing}"

    def test_exports_ship_the_minified_data(self, package_json):
        default = package_json["exports"]["."]["default"]
        assert default == "./data/v5/cards.min.json"

    def test_types_entry_points_at_the_generated_declarations(self, package_json):
        assert package_json["types"] == "./data/v5/cards.d.ts"
        assert os.path.exists(os.path.join(ROOT_DIR, package_json["types"]))

    def test_published_files_cover_every_export(self, package_json):
        """files: ["data"] is what the tarball contains."""
        assert package_json["files"] == ["data"]
        outside = [value for value in package_json["exports"].values()
                   if isinstance(value, str) and not value.startswith("./data/")
                   and value != "./package.json"]
        assert not outside, f"Exports outside the published files list: {outside}"

    def test_no_legacy_dataset_is_left_at_the_repository_root(self):
        stray = [name for name in os.listdir(ROOT_DIR)
                 if name.endswith(".json") and name not in {"package.json", "package-lock.json",
                                                            "tsconfig.json"}]
        assert not stray, f"Datasets still at the repo root, not under data/: {stray}"
