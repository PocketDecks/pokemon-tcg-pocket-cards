"""Unit tests for the raw-card -> v5 transform.

These run without network access: ``fetch_datamine_lookup`` is replaced by a
fixture, so every test here exercises pure transform logic on synthetic
scraper output.
"""
import pytest

import transformer
from tests.contract import CARD_KEYS
from transformer import downgrade_to_v4, transform_cards
from set_profile import SetProfile


def raw(number, name="Pikachu", rarity="◊", **overrides):
    """A scraper-shaped card dict. Overrides win."""
    card = {
        "number": str(number),
        "name": name,
        "hp": 60,
        "type": "Pokémon",
        "subtype": "Lightning",
        "card_text": None,
        "flavour_text": None,
        "image": f"https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/a1/{number}.webp",
        "rarity": rarity,
        "alternate_versions": [],
        "ex": False,
        "mega": False,
        "points": 1,
        "pack": "Every pack",
        "artist": "Mitsuhiro Arita",
        "stage": "Basic",
        "evolves_from": None,
        "retreat": 1,
        "weakness": "Fighting",
        "ability": {"exists": False, "name": None, "effect": None},
        "attacks": {str(n): {"cost": None, "name": None, "damage": None, "effect": None}
                    for n in (1, 2)},
        "raw_text": f"Pikachu {number}",
    }
    card.update(overrides)
    return card


def trainer(number, name="Potion", rarity="◊", **overrides):
    defaults = {"type": "Trainer", "subtype": "Item", "hp": None, "stage": None,
                "retreat": None, "weakness": None, "points": None,
                "card_text": "Heal 20 damage."}
    defaults.update(overrides)
    return raw(number, name, rarity, **defaults)


@pytest.fixture(autouse=True)
def stub_datamine(monkeypatch):
    """Every card resolves to a deck-builder number of 100 + card number."""
    monkeypatch.setattr(transformer, "fetch_datamine_lookup",
                        lambda: _AutoLookup())
    return None


class _AutoLookup(dict):
    def get(self, key, default=None):
        prefix, number = key
        return 100 + number


def art_styles(cards):
    return [c["art_style"] for c in cards]


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------

class TestOutputShape:
    def test_exact_keys_and_order(self):
        """Published order, once the downloader has popped source_url.

        ``subtype_2`` is the one optional key: dual-type Pokemon carry it
        between ``subtype`` and ``stage``, every other card omits it.
        """
        card = transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex")[0]
        card.pop("source_url")
        assert tuple(card) == tuple(k for k in CARD_KEYS if k != "subtype_2")

    def test_ids_are_zero_padded_and_prefixed(self):
        cards = transform_cards([raw(1), raw(23), raw(105)], SetProfile.of("A1"), "Genetic Apex")
        assert [c["id"] for c in cards] == ["a1-001", "a1-023", "a1-105"]

    def test_promo_set_code_becomes_a_prefix(self):
        card = transform_cards([raw(1)], SetProfile.of("P-A"), "Promo-A")[0]
        assert card["id"] == "pa-001" and card["set_code"] == "pa"

    def test_image_urls_follow_the_id(self):
        card = transform_cards([raw(7)], SetProfile.of("A1"), "Genetic Apex")[0]
        assert card["image"].endswith("/webp/cards/a1/007.webp")
        assert card["image_png"].endswith("/png/cards/a1/007.png")

    def test_source_url_is_carried_for_the_downloader(self):
        card = transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex")[0]
        assert card["source_url"].startswith("https://")

    def test_release_date_is_copied_onto_every_card(self):
        cards = transform_cards([raw(1), raw(2)], SetProfile.of("A1"), "Genetic Apex",
                                release_date="2024-10-30")
        assert {c["release_date"] for c in cards} == {"2024-10-30"}

    def test_missing_subtype_becomes_unknown(self):
        card = transform_cards([trainer(1, subtype=None)], SetProfile.of("A1"), "Genetic Apex")[0]
        assert card["subtype"] == "Unknown"


class TestDualType:
    """Dual-type Pokemon: subtype keeps the first type, subtype_2 the second."""

    def dual(self, **overrides):
        return transform_cards(
            [raw(1, subtype="Water", subtype_2="Darkness", **overrides)],
            SetProfile.of("C1"), "Dual Fusion")[0]

    def test_subtype_stays_the_first_type(self):
        assert self.dual()["subtype"] == "Water"

    def test_subtype_2_carries_the_second_type(self):
        assert self.dual()["subtype_2"] == "Darkness"

    def test_subtype_2_sits_between_subtype_and_stage(self):
        card = self.dual()
        card.pop("source_url")
        assert tuple(card) == CARD_KEYS

    def test_dual_type_is_the_first_special_tag(self):
        card = self.dual(name="Great Tusk")
        assert card["special_tags"] == ["dual_type", "ancient"]

    def test_single_type_cards_omit_the_key_entirely(self):
        card = transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex")[0]
        assert "subtype_2" not in card

    def test_v4_type_joins_both_types(self):
        card = downgrade_to_v4([self.dual()])[0]
        assert card["type"] == "Water/Darkness"

    def test_v4_type_stays_single_for_other_cards(self):
        card = downgrade_to_v4([transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex")[0]])[0]
        assert card["type"] == "Lightning"


# ---------------------------------------------------------------------------
# Art style state machine
# ---------------------------------------------------------------------------

class TestArtStyle:
    def test_plain_star_is_illustration_art(self):
        cards = transform_cards([raw(1), raw(2, rarity="☆")], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == [None, "Illustration Art"]

    def test_star_run_then_two_star_is_full_art(self):
        cards = transform_cards(
            [raw(1, rarity="☆"), raw(2, rarity="☆☆")], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == ["Illustration Art", "Full Art"]

    def test_sia_starts_after_the_trainer_full_art(self):
        cards = transform_cards([
            raw(1, rarity="☆"),
            raw(2, rarity="☆☆"),
            trainer(3, "Erika", rarity="☆☆", subtype="Supporter"),
            raw(4, "Charizard ex", rarity="☆☆", ex=True),
        ], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == [
            "Illustration Art", "Full Art", "Full Art", "Special Illustration Art"]

    def test_two_star_block_without_a_star_block_falls_back_to_full_art(self):
        """A set that jumps ◊◊◊◊ -> ☆☆ still classifies its ☆☆ block."""
        cards = transform_cards(
            [raw(1, rarity="◊◊◊◊"), raw(2, rarity="☆☆"), raw(3, rarity="☆☆")],
            SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == [None, "Full Art", "Full Art"]

    def test_three_star_is_immersive(self):
        cards = transform_cards([raw(1, rarity="☆☆☆")], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == ["Immersive Art"]

    def test_crown_rare_stays_unclassified(self):
        cards = transform_cards([raw(1, rarity="Crown Rare")], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == [None] and cards[0]["shiny"] is False

    def test_parallel_foil_needs_identical_raw_text_and_a_diamond_rarity(self):
        cards = transform_cards([
            raw(1, raw_text="Same body"),
            raw(2, raw_text="Same body"),
            raw(3, raw_text="Other body"),
        ], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == [None, "Parallel Foil", None]

    def test_parallel_foil_is_not_applied_to_star_rarities(self):
        cards = transform_cards([
            raw(1, rarity="☆", raw_text="Same body"),
            raw(2, rarity="☆", raw_text="Same body"),
        ], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == ["Illustration Art", "Illustration Art"]


class TestShinyDetection:
    """Shinies sit between the Immersive block and the end of the set."""

    def test_star_after_immersive_is_shiny(self):
        cards = transform_cards(
            [raw(1, rarity="☆☆☆"), raw(2, rarity="☆")], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == ["Immersive Art", "Shiny"]
        assert [c["shiny"] for c in cards] == [False, True]

    def test_two_star_after_immersive_is_shiny_full_art(self):
        cards = transform_cards(
            [raw(1, rarity="☆☆☆"), raw(2, rarity="☆☆")], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == ["Immersive Art", "Shiny Full Art"]
        assert cards[1]["shiny"] is True

    def test_full_shiny_block_after_a_complete_star_run(self):
        cards = transform_cards([
            raw(1, rarity="☆"),
            raw(2, rarity="☆☆"),
            trainer(3, "Erika", rarity="☆☆", subtype="Supporter"),
            raw(4, "Charizard ex", rarity="☆☆", ex=True),
            raw(5, rarity="☆☆☆"),
            raw(6, rarity="☆"),
            raw(7, rarity="☆"),
            raw(8, "Mewtwo ex", rarity="☆☆", ex=True),
            raw(9, rarity="Crown Rare"),
        ], SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == [
            "Illustration Art", "Full Art", "Full Art", "Special Illustration Art",
            "Immersive Art", "Shiny", "Shiny", "Shiny Full Art", None]
        assert [c["shiny"] for c in cards] == [False] * 5 + [True, True, True, False]

    def test_shiny_ex_card_keeps_its_shiny_classification(self):
        """An ex card in the shiny block must not fall through to Illustration Art."""
        cards = transform_cards(
            [raw(1, rarity="☆☆☆"), raw(2, "Pikachu ex", rarity="☆", ex=True)],
            SetProfile.of("A1"), "Genetic Apex")
        assert art_styles(cards) == ["Immersive Art", "Shiny"]
        assert cards[1]["shiny"] is True

    def test_shiny_pack_points_replace_the_normal_table(self):
        cards = transform_cards(
            [raw(1, rarity="☆☆☆"), raw(2, rarity="☆"), raw(3, rarity="☆☆")],
            SetProfile.of("A1"), "Genetic Apex")
        assert [c["pack_points"] for c in cards] == [1500, 1000, 1350]

    def test_trainer_in_the_shiny_block_is_not_shiny(self):
        cards = transform_cards(
            [raw(1, rarity="☆☆☆"), trainer(2, "Erika", rarity="☆", subtype="Supporter")],
            SetProfile.of("A1"), "Genetic Apex")
        assert cards[1]["shiny"] is False and cards[1]["art_style"] is None

    def test_trainers_are_never_shiny(self):
        cards = transform_cards(
            [raw(1, rarity="☆☆☆"), trainer(2, rarity="☆☆")], SetProfile.of("A1"), "Genetic Apex")
        assert cards[1]["shiny"] is False


# ---------------------------------------------------------------------------
# Packs, points and promos
# ---------------------------------------------------------------------------

class TestPacks:
    def test_pack_suffix_is_stripped(self):
        cards = transform_cards([raw(1, pack="Mewtwo pack")], SetProfile.of("A1"), "Genetic Apex")
        assert cards[0]["pack"] == "Mewtwo"

    def test_every_pack_becomes_shared_when_named_packs_exist(self):
        cards = transform_cards(
            [raw(1, pack="Mewtwo pack"), raw(2, pack="Every pack")], SetProfile.of("A1"), "Genetic Apex")
        assert [c["pack"] for c in cards] == ["Mewtwo", "Shared(Genetic Apex)"]

    def test_every_pack_becomes_the_expansion_when_it_is_the_only_pack(self):
        cards = transform_cards([raw(1, pack="Every pack")], SetProfile.of("B3b"), "Everyday Wonders")
        assert cards[0]["pack"] == "Everyday Wonders"

    def test_scraper_sentinel_never_survives(self):
        for set_code, name in (("A1", "Genetic Apex"), ("P-A", "Promo-A"), ("P-B", "Promo-B")):
            cards = transform_cards([raw(1, pack="Every pack")], SetProfile.of(set_code), name)
            assert cards[0]["pack"] != "Every pack"

    def test_promo_a_groups_promo_packs_into_volumes_of_five(self):
        cards = transform_cards([raw(n, pack="Promo pack") for n in range(1, 12)],
                                SetProfile.of("P-A"), "Promo-A")
        assert [c["pack"] for c in cards] == ["Promo V1"] * 5 + ["Promo V2"] * 5 + ["Promo V3"]

    def test_promo_a_keeps_named_promo_packs(self):
        cards = transform_cards([raw(1, pack="Premium Missions"), raw(2, pack="Shop")],
                                SetProfile.of("P-A"), "Promo-A")
        assert [c["pack"] for c in cards] == ["Premium Missions", "Shop"]

    def test_promo_b_cards_land_on_the_expansion_name(self):
        cards = transform_cards([raw(1, pack="Every pack"), raw(2, pack="Wonder Pick")],
                                SetProfile.of("P-B"), "Promo-B")
        assert [c["pack"] for c in cards] == ["Promo-B", "Promo-B"]


class TestRarityAndPoints:
    def test_promo_sets_are_rewritten_to_promo_rarity_without_pack_points(self):
        cards = transform_cards([raw(1, rarity="☆☆"), raw(2, rarity="◊")], SetProfile.of("P-A"), "Promo-A")
        assert {c["rarity"] for c in cards} == {"Promo"}
        assert {c["pack_points"] for c in cards} == {None}

    @pytest.mark.parametrize("rarity,points", [
        ("◊", 35), ("◊◊", 70), ("◊◊◊", 150), ("◊◊◊◊", 500),
        ("☆", 400), ("☆☆", 1250), ("☆☆☆", 1500), ("Crown Rare", 2500),
    ])
    def test_pack_points_come_from_the_rarity_table(self, rarity, points):
        cards = transform_cards([raw(1, rarity=rarity)], SetProfile.of("A1"), "Genetic Apex")
        assert cards[0]["pack_points"] == points


# ---------------------------------------------------------------------------
# Tags, deck builder numbers, alternate versions
# ---------------------------------------------------------------------------

class TestSpecialTags:
    def test_tag_is_matched_on_a_word_boundary(self):
        cards = transform_cards([
            raw(1, name="Great Tusk ex"),
            raw(2, name="Iron Hands"),
            raw(3, name="Naganadel"),
            raw(4, name="Pikachu"),
        ], SetProfile.of("A1"), "Genetic Apex")
        assert [c["special_tags"] for c in cards] == [
            ["ancient"], ["future"], ["ultra_beasts"], None]

    def test_a_longer_name_does_not_match_a_shorter_tag(self):
        cards = transform_cards([raw(1, name="Turonator")], SetProfile.of("A1"), "Genetic Apex")
        assert cards[0]["special_tags"] is None

    def test_possessive_trainer_names_are_tagged(self):
        cards = transform_cards([trainer(1, name="Sada's Vitality", subtype="Supporter")],
                                SetProfile.of("A1"), "Genetic Apex")
        assert cards[0]["special_tags"] == ["ancient"]


class TestDeckBuilderNr:
    def test_number_comes_from_the_datamine_lookup(self):
        cards = transform_cards([raw(4)], SetProfile.of("A1"), "Genetic Apex")
        assert cards[0]["deckBuilderNr"] == 104

    def test_missing_number_falls_back_to_zero_and_warns(self, monkeypatch, capsys):
        monkeypatch.setattr(transformer, "fetch_datamine_lookup", lambda: {})
        cards = transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex")
        assert cards[0]["deckBuilderNr"] == 0
        assert "deckBuilderNr 0" in capsys.readouterr().out

    def test_unparsable_card_number_still_yields_an_int(self, monkeypatch):
        monkeypatch.setattr(transformer, "fetch_datamine_lookup", lambda: {})
        card = raw(1)
        card["number"] = "abc"
        cards = transform_cards([card], SetProfile.of("A1"), "Genetic Apex")
        assert type(cards[0]["deckBuilderNr"]) is int


class TestAlternateVersions:
    def test_self_reference_is_dropped_and_set_codes_normalised(self):
        card = transform_cards([raw(1, alternate_versions=[
            {"set_code": "a1", "set_name": "Genetic Apex", "id": 1, "rarity": "◊"},
            {"set_code": "p-a", "set_name": "Promo-A", "id": 23, "rarity": "Promo"},
        ])], SetProfile.of("A1"), "Genetic Apex")[0]
        assert card["alternate_versions"] == [
            {"set_code": "pa", "set_name": "Promo-A", "id": 23, "rarity": "Promo"}]

    def test_same_number_in_another_set_is_kept(self):
        card = transform_cards([raw(1, alternate_versions=[
            {"set_code": "a2", "set_name": "Space-Time Smackdown", "id": 1, "rarity": "◊"},
        ])], SetProfile.of("A1"), "Genetic Apex")[0]
        assert [a["set_code"] for a in card["alternate_versions"]] == ["a2"]


# ---------------------------------------------------------------------------
# v4 downgrade
# ---------------------------------------------------------------------------

class TestDowngradeToV4:
    def test_key_set(self):
        v4 = downgrade_to_v4(transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex"))[0]
        assert set(v4) == {"id", "name", "rarity", "pack", "health", "image",
                           "fullart", "ex", "artist", "type"}

    def test_pokemon_type_is_the_energy_type(self):
        v4 = downgrade_to_v4(transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex"))[0]
        assert v4["type"] == "Lightning"

    def test_every_trainer_collapses_to_the_trainer_type(self):
        cards = transform_cards([trainer(1, subtype="Item"), trainer(2, subtype="Supporter")],
                                SetProfile.of("A1"), "Genetic Apex")
        assert {c["type"] for c in downgrade_to_v4(cards)} == {"Trainer"}

    def test_missing_values_become_empty_strings_not_null(self):
        v4 = downgrade_to_v4(transform_cards([trainer(1)], SetProfile.of("A1"), "Genetic Apex"))[0]
        assert v4["health"] == ""

    def test_flags_are_yes_no_strings(self):
        cards = transform_cards([raw(1, name="Pikachu ex", ex=True, rarity="☆☆")],
                                SetProfile.of("A1"), "Genetic Apex")
        v4 = downgrade_to_v4(cards)[0]
        assert v4["ex"] == "Yes" and v4["fullart"] == "Yes"

    def test_image_is_the_png_url(self):
        cards = transform_cards([raw(1)], SetProfile.of("A1"), "Genetic Apex")
        assert downgrade_to_v4(cards)[0]["image"] == cards[0]["image_png"]
