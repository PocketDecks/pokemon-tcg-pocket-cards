import os
import re

import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PNG_CARDS_DIR = os.path.join(ROOT_DIR, "images", "png", "cards")

from tests.contract import V4_CARD_KEYS as REQUIRED_FIELDS

TRAINER_TYPES = {"Trainer", "Item", "Stadium", "Supporter", "Tool"}

VALID_TYPES = {
    "Grass", "Fire", "Water", "Lightning", "Psychic",
    "Fighting", "Darkness", "Metal", "Dragon", "Colorless", "Fairy",
} | TRAINER_TYPES

FULLART_RARITIES = {"☆☆", "☆☆☆"}

VALID_RARITIES = {"◊", "◊◊", "◊◊◊", "◊◊◊◊", "☆", "☆☆", "☆☆☆", "♕", "Promo", "Crown Rare"}
FULLART_RARITIES = {"☆", "☆☆", "☆☆☆", "♕", "Crown Rare"}

IMAGE_URL_PREFIX = "https://raw.githubusercontent.com/PocketDecks/pokemon-tcg-pocket-cards/refs/heads/main/images/png/cards/"

ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*-\d{1,3}$")

FOSSIL_NAMES = {"Helix Fossil", "Dome Fossil", "Old Amber", "Jaw Fossil", "Sail Fossil"}


class TestV4Structure:
    def test_is_non_empty_list(self, v4_cards):
        assert isinstance(v4_cards, list) and len(v4_cards) > 0


    def test_all_entries_are_dicts(self, v4_cards):
        for i, card in enumerate(v4_cards):
            assert isinstance(card, dict)


class TestCardFields:
    def test_all_required_fields_present(self, v4_cards):
        for card in v4_cards:
            for field in REQUIRED_FIELDS:
                assert field in card

    def test_no_extra_fields(self, v4_cards):
        expected = set(REQUIRED_FIELDS)
        for card in v4_cards:
            extra = set(card.keys()) - expected
            assert not extra, f"Card {card['id']} has unexpected fields: {extra}"

    def test_no_none_values(self, v4_cards):
        for card in v4_cards:
            for field in REQUIRED_FIELDS:
                assert card[field] is not None, f"Card {card['id']} has None for '{field}'"

    def test_all_values_are_strings(self, v4_cards):
        for card in v4_cards:
            for field in REQUIRED_FIELDS:
                assert isinstance(card[field], str), (
                    f"Card {card['id']} field '{field}' is {type(card[field]).__name__}, expected str"
                )


class TestCardId:
    def test_id_format(self, v4_cards):
        for card in v4_cards:
            assert ID_PATTERN.match(card["id"]), (
                f"Card ID '{card['id']}' doesn't match expected format (e.g. 'a1-001')"
            )

    def test_no_duplicate_ids(self, v4_cards):
        ids = [card["id"] for card in v4_cards]
        seen = set()
        duplicates = []
        for card_id in ids:
            if card_id in seen:
                duplicates.append(card_id)
            seen.add(card_id)
        assert not duplicates, f"Duplicate card IDs found: {duplicates}"

    def test_ids_are_sorted_within_expansion(self, v4_cards):
        """Cards from the same expansion should appear in numerical order."""
        from collections import defaultdict

        by_prefix = defaultdict(list)
        for card in v4_cards:
            prefix = card["id"].rsplit("-", 1)[0]
            number = int(card["id"].rsplit("-", 1)[1])
            by_prefix[prefix].append(number)

        for prefix, numbers in by_prefix.items():
            assert numbers == sorted(numbers), (
                f"Cards with prefix '{prefix}' are not in sorted order"
            )


class TestCardName:
    def test_name_not_empty(self, v4_cards):
        for card in v4_cards:
            assert card["name"].strip(), f"Card {card['id']} has empty name"

    def test_name_reasonable_length(self, v4_cards):
        for card in v4_cards:
            assert len(card["name"]) <= 60, (
                f"Card {card['id']} name is suspiciously long: '{card['name']}'"
            )
            assert len(card["name"]) >= 2, (
                f"Card {card['id']} name is suspiciously short: '{card['name']}'"
            )

    def test_name_no_html_tags(self, v4_cards):
        for card in v4_cards:
            assert "<" not in card["name"] and ">" not in card["name"], (
                f"Card {card['id']} name contains HTML: '{card['name']}'"
            )


class TestCardRarity:
    def test_rarity_is_valid(self, v4_cards):
        for card in v4_cards:
            assert card["rarity"] in VALID_RARITIES, (
                f"Card {card['id']} has invalid rarity: '{card['rarity']}'"
            )

    def test_promo_rarity_only_on_promo_v4_cards(self, v4_cards):
        for card in v4_cards:
            if card["rarity"] == "Promo":
                prefix = card["id"].rsplit("-", 1)[0]
                assert prefix.startswith("p"), (
                    f"Card {card['id']} has Promo rarity but is not a promo card"
                )


class TestCardType:
    def test_type_is_valid(self, v4_cards):
        for card in v4_cards:
            assert card["type"] in VALID_TYPES, (
                f"Card {card['id']} has invalid type: '{card['type']}'"
            )


class TestCardHealth:
    def test_pokemon_have_numeric_health(self, v4_cards):
        for card in v4_cards:
            if card["type"] not in TRAINER_TYPES:
                assert card["health"].isdigit(), (
                    f"Pokemon card {card['id']} ({card['name']}) has non-numeric health: '{card['health']}'"
                )

    def test_health_in_reasonable_range(self, v4_cards):
        for card in v4_cards:
            if card["health"] and card["health"].isdigit():
                hp = int(card["health"])
                assert 10 <= hp <= 400, (
                    f"Card {card['id']} has health {hp} outside reasonable range"
                )

    def test_trainer_health_empty_unless_fossil(self, v4_cards):
        """Trainers should have empty health, except fossils which have HP."""
        for card in v4_cards:
            if card["type"] in TRAINER_TYPES and card["health"] != "":
                assert card["name"] in FOSSIL_NAMES, (
                    f"Trainer card {card['id']} ({card['name']}) has health '{card['health']}' "
                    f"but is not a known fossil card"
                )


class TestCardImage:
    def test_image_url_format(self, v4_cards):
        for card in v4_cards:
            prefix, num = card["id"].rsplit("-", 1)
            expected = f"{IMAGE_URL_PREFIX}{prefix}/{num}.png"
            assert card["image"] == expected


    def test_image_file_exists(self, v4_cards):
        missing = []
        for card in v4_cards:
            if card["id"].startswith("p"): continue
            prefix, num = card["id"].rsplit("-", 1)
            path = os.path.join(PNG_CARDS_DIR, prefix, f"{num}.png")
            if not os.path.exists(path):
                missing.append(card["id"])
        assert not missing, (
            f"{len(missing)} card images missing locally: {missing[:20]}"
        )


class TestCardFlags:
    def test_fullart_is_yes_or_no(self, v4_cards):
        for card in v4_cards:
            assert card["fullart"] in ("Yes", "No"), (
                f"Card {card['id']} has invalid fullart value: '{card['fullart']}'"
            )

    def test_ex_is_yes_or_no(self, v4_cards):
        for card in v4_cards:
            assert card["ex"] in ("Yes", "No"), (
                f"Card {card['id']} has invalid ex value: '{card['ex']}'"
            )

    def test_ex_flag_matches_name(self, v4_cards):
        """If ex='Yes', the name should contain 'ex' as a word."""
        for card in v4_cards:
            has_ex_in_name = "ex" in card["name"].split(" ")
            if card["ex"] == "Yes":
                assert has_ex_in_name, (
                    f"Card {card['id']} has ex='Yes' but name '{card['name']}' doesn't contain 'ex'"
                )
            if has_ex_in_name:
                assert card["ex"] == "Yes", (
                    f"Card {card['id']} name '{card['name']}' contains 'ex' but ex='{card['ex']}'"
                )

    def test_fullart_matches_rarity(self, v4_cards):
        """Fullart v4_cards should have a fullart rarity (star/crown), except promos."""
        for card in v4_cards:
            if card["rarity"] == "Promo":
                continue
            if card["fullart"] == "Yes":
                assert card["rarity"] in FULLART_RARITIES, (
                    f"Card {card['id']} is fullart but has rarity '{card['rarity']}'"
                )
            if card["rarity"] in FULLART_RARITIES:
                assert card["fullart"] == "Yes", (
                    f"Card {card['id']} has fullart rarity '{card['rarity']}' but fullart='No'"
                )


class TestCardPack:
    def test_pack_not_empty(self, v4_cards):
        for card in v4_cards:
            assert card["pack"].strip(), f"Card {card['id']} has empty pack"

    def test_pack_not_error(self, v4_cards):
        errors = [c for c in v4_cards if c["pack"] == "Error"]
        assert not errors, (
            f"{len(errors)} card(s) have pack='Error': "
            + ", ".join(f"{c['id']} ({c['name']})" for c in errors)
        )


class TestCardArtist:
    def test_artist_not_empty(self, v4_cards):
        for card in v4_cards:
            assert card["artist"].strip(), f"Card {card['id']} has empty artist"

    def test_artist_not_unknown(self, v4_cards):
        unknowns = [c for c in v4_cards if c["artist"] == "Unknown"]
        assert not unknowns, (
            f"{len(unknowns)} card(s) have artist='Unknown': "
            + ", ".join(f"{c['id']} ({c['name']})" for c in unknowns[:20])
        )

    def test_artist_reasonable_length(self, v4_cards):
        for card in v4_cards:
            assert len(card["artist"]) <= 80, (
                f"Card {card['id']} artist is suspiciously long: '{card['artist']}'"
            )
