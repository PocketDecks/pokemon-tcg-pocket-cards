"""Cross-card, cross-set and cross-file invariants for cards.json."""
import base64
import os

from tests.utils import report
from constants import PNG_PACKS_DIR, PROMO_PREFIXES, WEBP_PACKS_DIR
from deck_code import create_deck_code

def number(card):
    return int(card["id"].rsplit("-", 1)[1])

class TestOrdering:
    def test_sets_are_contiguous_blocks(self, cards):
        """Non-promo sets must not be interleaved (promos are appended over time)."""
        seen, current = [], None
        for card in cards:
            if card["set_code"] in PROMO_PREFIXES:
                continue
            if card["set_code"] != current:
                assert card["set_code"] not in seen, (
                    f"Set {card['set_code']!r} appears in multiple non-contiguous blocks")
                seen.append(card["set_code"])
                current = card["set_code"]

    def test_numbers_ascend_within_set(self, by_set):
        bad = {s: [number(c) for c in group]
               for s, group in by_set.items()
               if [number(c) for c in group] != sorted(number(c) for c in group)}
        assert not bad, f"Sets not in ascending card order: {list(bad)}"

    def test_numbering_has_no_gaps(self, by_set):
        """Limitless numbers sets 1..N with no holes; a gap means a card was dropped."""
        gaps = {}
        for set_id, group in by_set.items():
            numbers = sorted(number(c) for c in group)
            expected = list(range(1, len(numbers) + 1))
            if numbers != expected:
                gaps[set_id] = sorted(set(expected) - set(numbers))[:10]
        assert not gaps, f"Missing card numbers per set: {gaps}"


class TestArtStyleBlocks:
    def test_full_arts_precede_sias(self, by_set):
        bad = {}
        for set_id, group in by_set.items():
            fa = [number(c) for c in group if c["art_style"] == "Full Art"]
            sia = [number(c) for c in group if c["art_style"] == "Special Illustration Art"]
            if fa and sia and max(fa) > min(sia):
                bad[set_id] = (max(fa), min(sia))
        assert not bad, f"Full Art appears after an SIA (state machine broke): {bad}"

    def test_immersive_precedes_shinies(self, by_set):
        bad = {}
        for set_id, group in by_set.items():
            immersive = [number(c) for c in group if c["art_style"] == "Immersive Art"]
            shinies = [number(c) for c in group if c["shiny"]]
            if immersive and shinies and min(shinies) < max(immersive):
                bad[set_id] = (max(immersive), min(shinies))
        assert not bad, f"Shiny card numbered before the Immersive block: {bad}"

    def test_shinies_only_in_sets_with_immersive(self, by_set):
        bad = [s for s, group in by_set.items()
               if any(c["shiny"] for c in group)
               and not any(c["art_style"] == "Immersive Art" for c in group)]
        assert not bad, f"Shiny cards detected without an Immersive Art anchor: {bad}"

    def test_each_art_style_is_one_block(self, by_set):
        """Star art styles come in a single run per set."""
        bad = {}
        for set_id, group in by_set.items():
            for style in ("Illustration Art", "Full Art", "Special Illustration Art",
                          "Immersive Art", "Shiny", "Shiny Full Art"):
                numbers = [number(c) for c in group if c["art_style"] == style]
                if numbers and numbers != list(range(min(numbers), max(numbers) + 1)):
                    bad[f"{set_id}/{style}"] = numbers
        assert not bad, f"Art style split across non-contiguous runs: {list(bad)}"

    def test_parallel_foil_follows_its_twin(self, cards):
        by_id = {c["id"]: c for c in cards}
        fails = []
        for card in cards:
            if card["art_style"] != "Parallel Foil":
                continue
            previous = by_id.get(f"{card['set_code']}-{str(number(card) - 1).zfill(3)}")
            if previous is None or previous["name"] != card["name"]:
                fails.append(f"{card['id']} ({card['name']}): previous card is "
                             f"{previous['name'] if previous else 'missing'}")
        assert not fails, report(fails)


class TestSetConsistency:
    def test_one_release_date_and_name_per_set(self, by_set):
        bad = {s: sorted({c["release_date"] for c in group})
               for s, group in by_set.items() if len({c["release_date"] for c in group}) > 1}
        assert not bad, f"Mixed release dates: {bad}"

    def test_promo_sets_are_all_promo_rarity(self, by_set):
        bad = {s: sorted({c["rarity"] for c in group})
               for s, group in by_set.items()
               if s in PROMO_PREFIXES and {c["rarity"] for c in group} != {"Promo"}}
        assert not bad, f"Promo sets with non-Promo rarities: {bad}"

    def test_every_set_has_cards_and_a_size_floor(self, by_set):
        small = {s: len(group) for s, group in by_set.items() if len(group) < 5}
        assert not small, f"Suspiciously small sets: {small}"

class TestExpansionsCrossFile:
    def test_every_set_has_an_expansion(self, by_set, expansions):
        known = {e["id"] for e in expansions} | set(PROMO_PREFIXES)
        unmapped = set(by_set) - known
        assert not unmapped, f"Card sets with no expansion entry: {unmapped}"

    def test_every_expansion_has_cards(self, by_set, expansions):
        empty = [e["id"] for e in expansions if e["id"] not in by_set and e["id"] != "promo"]
        assert not empty, f"Expansions with no cards: {empty}"

    def test_pack_values_match_expansions(self, by_set, expansions):
        fails = []
        for exp in expansions:
            group = by_set.get(exp["id"], [])
            allowed = {exp["name"], f"Shared({exp['name']})", "Booster"}
            allowed |= {p["name"] for p in exp["packs"]}
            for card in group:
                if card["pack"] not in allowed:
                    fails.append(f"{card['id']}: pack {card['pack']!r} not in {sorted(allowed)}")
        assert not fails, report(fails)

    def test_expansion_packs_cover_all_card_packs(self, by_set, expansions):
        fails = []
        for exp in expansions:
            group = by_set.get(exp["id"], [])
            used = {c["pack"] for c in group if not c["pack"].startswith("Shared(")}
            declared = {p["name"] for p in exp["packs"]}
            missing = used - declared - {exp["name"]}
            if missing and declared != {"Booster"}:
                fails.append(f"{exp['id']}: packs used by cards but not declared: {sorted(missing)}")
        assert not fails, report(fails)

    def test_packs_have_no_stray_whitespace(self, cards):
        bad = sorted({c["pack"] for c in cards if c["pack"] != c["pack"].strip()})
        assert not bad, f"Pack names with stray whitespace: {bad}"

    def test_pack_image_files_exist(self, expansions):
        missing = []
        for exp in expansions:
            for pack in exp["packs"]:
                if pack["id"].startswith(("pa-", "pb-", "pc-")):
                    continue
                for directory, ext in ((WEBP_PACKS_DIR, "webp"), (PNG_PACKS_DIR, "png")):
                    if not os.path.exists(os.path.join(directory, f"{pack['id']}.{ext}")):
                        missing.append(f"{pack['id']}.{ext}")
        assert not missing, f"Missing pack images: {missing[:20]}"


class TestDatabaseSanity:
    def test_minimum_size(self, cards, expansions):
        assert len(cards) >= 500, f"Only {len(cards)} cards"
        assert len(expansions) >= 5, f"Only {len(expansions)} expansions"

    def test_v4_not_overwritten_by_v5_schema(self, v4_cards):
        """cards.json stays on the legacy string schema."""
        assert v4_cards and "fullart" in v4_cards[0], "cards.json looks like it was written with v5 fields"


class TestDeckCodeBinaryParity:
    def test_official_deck_encoding(self):
        # Potion (ID: 1) + Trainer Offset (1,000,000) = 1,000,001
        assert create_deck_code([1000001]) == "AZiWigA="

        # 20 Pokemon cards (no energy)
        assert create_deck_code(list(
            range(1, 21))) == "ABQAAAoAABQAAB4AACgAADIAADwAAEYAAFAAAFoAAGQAAG4AAHgAAIIAAIwAAJYAAKAAAKoAALQAAL4AAMgA"

        # 20 Pokemon cards + Grass Energy (id: 1)
        assert create_deck_code(list(range(1, 21)),
                                [1]) == "ABQAAAoAABQAAB4AACgAADIAADwAAEYAAFAAAFoAAGQAAG4AAHgAAIIAAIwAAJYAAKAAAKoAALQAAL4AAMgBAQ=="

    def test_game_generated_deck_round_trips(self):
        """Byte-identical to a QR the in-game scanner produced and accepted."""
        nrs = [
            2064, 2064, 87, 87, 89, 89, 1233,
            1000002, 1000003, 1000003, 1000048, 1000048, 1000128,
            1000152, 1000152, 1000004, 1000004, 1000032, 1000099, 1000099,
        ]
        assert create_deck_code(nrs, [7]) == (
            "DZiWlJiWnpiWnpiWqJiWqJiXwJiYYJiYYJiaXpiaXpibgJiccJiccAcA"
            "A2YAA2YAA3oAA3oAMCoAUKAAUKABBw=="
        )

    def test_energy_ids_must_be_ascending(self):
        """The game rejected [4, 2] for a deck it accepted as [2, 4]."""
        assert base64.b64decode(create_deck_code([2064], [2, 4]))[-2:] == bytes([2, 4])
        assert create_deck_code([2064], [2, 4]) != create_deck_code([2064], [4, 2])