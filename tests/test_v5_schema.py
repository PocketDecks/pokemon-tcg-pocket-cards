"""Field-level validation of every card in cards.json."""
import os
import re
from datetime import date, datetime, timedelta

from tests.contract import CARD_KEYS
from tests.utils import collect, report
from constants import (ART_STYLES, ENERGY_TYPES, FIRST_RELEASE, GITHUB_BASE_URL,
                       PACK_POINTS, PNG_CARDS_DIR, PROMO_PREFIXES, RARITIES,
                       SHINY_PACK_POINTS, STAGES, TRAINER_SUBTYPES, WEBP_CARDS_DIR,
                       is_playable_trainer)

ABILITY_KEYS = {"exists", "name", "effect"}
ATTACK_KEYS = {"cost", "name", "damage", "effect"}

ID_RE = re.compile(r"^[a-z][a-z0-9]*-\d{3,4}$")
SET_RE = re.compile(r"^[a-z][a-z0-9]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COST_RE = re.compile(r"^[GRWLPFDMCNY0]{1,5}$")
STAR_RARITIES = {"☆", "☆☆", "☆☆☆"}
CROWN_RARITY = "Crown Rare"


def is_promo(card):
    return card["set_code"] in PROMO_PREFIXES



def walk(value, path=""):
    """Yield (path, scalar) for every leaf in a nested dict/list."""
    if isinstance(value, dict):
        for key, sub in value.items():
            yield from walk(sub, f"{path}.{key}")
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            yield from walk(sub, f"{path}[{i}]")
    else:
        yield path, value


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructure:
    def test_is_non_empty_list(self, cards):
        assert isinstance(cards, list) and cards

    def test_all_entries_are_dicts(self, cards):
        bad = [i for i, c in enumerate(cards) if not isinstance(c, dict)]
        assert not bad, f"Non-dict entries at indices: {bad[:20]}"

    def test_exact_key_set(self, cards):
        """Every schema property is present, except the optional subtype_2,
        which only dual-type Pokemon carry."""
        expected = set(CARD_KEYS)
        optional = {"subtype_2"}
        fails = collect(cards, lambda c: (
            f"missing {expected - set(c) - optional}, extra {set(c) - expected}"
            if not (set(c) - optional <= expected <= set(c) | optional) else None))
        assert not fails, report(fails)

    def test_key_order_is_stable(self, cards):
        """Published order; dual-type cards insert subtype_2 after subtype."""
        def order_ok(card):
            if "subtype_2" not in card:
                return None if tuple(card) == tuple(k for k in CARD_KEYS if k != "subtype_2") else "key order drifted"
            keys = list(card)
            expected = [k for k in CARD_KEYS if k != "subtype_2"]
            return None if keys == sorted(keys, key=lambda k: expected.index(k) if k != "subtype_2" else expected.index("subtype") + 0.5) else "key order drifted"
        fails = collect(cards, order_ok)
        assert not fails, report(fails)

    def test_no_source_url_leaked(self, cards):
        assert not [c["id"] for c in cards if "source_url" in c]

    def test_no_empty_strings_only_nulls(self, cards):
        """The "" -> null transition: empty strings must never appear."""
        fails = collect(cards, lambda c: next(
            (f"empty string at {p}" for p, v in walk(c) if v == "" and not p.endswith(".id")), None))
        assert not fails, report(fails)

    def test_no_untrimmed_strings(self, cards):
        fails = collect(cards, lambda c: next(
            (f"untrimmed value at {p}: {v!r}" for p, v in walk(c)
             if isinstance(v, str) and v != v.strip()), None))
        assert not fails, report(fails)

    def test_no_newlines_or_double_spaces_in_strings(self, cards):
        fails = collect(cards, lambda c: next(
            (f"whitespace noise at {p}: {v!r}" for p, v in walk(c)
             if isinstance(v, str) and ("\n" in v or "\t" in v or "  " in v)), None))
        assert not fails, report(fails)

    def test_no_html_left_in_strings(self, cards):
        fails = collect(cards, lambda c: next(
            (f"HTML at {p}: {v!r}" for p, v in walk(c)
             if isinstance(v, str) and ("<" in v or "&nbsp;" in v or "&amp;" in v)), None))
        assert not fails, report(fails)


# ---------------------------------------------------------------------------
# Identification
# ---------------------------------------------------------------------------

class TestId:
    def test_id_format(self, cards):
        fails = collect(cards, lambda c: None if ID_RE.match(c["id"]) else f"bad id {c['id']!r}")
        assert not fails, report(fails)

    def test_ids_unique(self, cards):
        seen, dupes = set(), []
        for c in cards:
            if c["id"] in seen:
                dupes.append(c["id"])
            seen.add(c["id"])
        assert not dupes, f"Duplicate ids: {dupes[:20]}"

    def test_id_prefix_matches_set(self, cards):
        fails = collect(cards, lambda c: None if c["id"].rsplit("-", 1)[0] == c["set_code"]
                        else f"prefix != set_code {c['set_code']!r}")
        assert not fails, report(fails)

    def test_id_number_is_zero_padded_int(self, cards):
        def check(c):
            num = c["id"].rsplit("-", 1)[1]
            return None if num == str(int(num)).zfill(3) else f"bad number {num!r}"
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_set_code_format(self, cards):
        fails = collect(cards, lambda c: None if SET_RE.match(c["set_code"]) else f"bad set_code {c['set_code']!r}")
        assert not fails, report(fails)


class TestName:
    def test_not_empty(self, cards):
        fails = collect(cards, lambda c: None if isinstance(c["name"], str) and c["name"] else "empty name")
        assert not fails, report(fails)

    def test_reasonable_length(self, cards):
        fails = collect(cards, lambda c: None if 2 <= len(c["name"]) <= 60
                        else f"length {len(c['name'])}")
        assert not fails, report(fails)


class TestArtist:
    def test_not_empty(self, cards):
        fails = collect(cards, lambda c: None if c["artist"] else "empty artist")
        assert not fails, report(fails)

    def test_not_unknown(self, cards):
        fails = collect(cards, lambda c: None if c["artist"] != "Unknown" else "artist not scraped")
        assert not fails, report(fails)

    def test_reasonable_length(self, cards):
        fails = collect(cards, lambda c: None if len(c["artist"]) <= 80 else "artist too long")
        assert not fails, report(fails)


class TestReleaseDate:
    def test_iso_format_or_null(self, cards):
        fails = collect(cards, lambda c: None if c["release_date"] is None
                        or (isinstance(c["release_date"], str) and DATE_RE.match(c["release_date"]))
                        else f"bad release_date {c['release_date']!r}")
        assert not fails, report(fails)

    def test_parses_and_is_in_range(self, cards):
        floor, ceiling = date.fromisoformat(FIRST_RELEASE), date.today() + timedelta(days=365)

        def check(c):
            if not c["release_date"]:
                return None
            parsed = datetime.strptime(c["release_date"], "%Y-%m-%d").date()
            return None if floor <= parsed <= ceiling else f"date out of range: {parsed}"
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_non_promo_sets_have_a_date(self, cards):
        fails = collect(cards, lambda c: None if is_promo(c) or c["release_date"]
                        else "non-promo card without release_date")
        assert not fails, report(fails)

    def test_one_date_per_set(self, by_set):
        bad = {s: sorted({c["release_date"] for c in group})
               for s, group in by_set.items()
               if len({c["release_date"] for c in group}) > 1}
        assert not bad, f"Sets with mixed release dates: {bad}"


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

class TestTypeAndSubtype:
    def test_type_is_valid(self, cards):
        fails = collect(cards, lambda c: None if c["type"] in ("Pokémon", "Trainer")
                        else f"bad type {c['type']!r}")
        assert not fails, report(fails)

    def test_subtype_never_null(self, cards):
        fails = collect(cards, lambda c: None if c["subtype"] else "subtype is null")
        assert not fails, report(fails)

    def test_pokemon_subtype_is_energy_type(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Pokémon"
                        or c["subtype"] in ENERGY_TYPES else f"bad energy type {c['subtype']!r}")
        assert not fails, report(fails)

    def test_trainer_subtype_is_valid(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Trainer"
                        or c["subtype"] in TRAINER_SUBTYPES else f"bad trainer subtype {c['subtype']!r}")
        assert not fails, report(fails)


class TestStageAndEvolution:
    def test_pokemon_stage_is_known(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Pokémon" or c["stage"] in STAGES
                        else f"bad stage {c['stage']!r}")
        assert not fails, report(fails)

    def test_trainer_stage_is_null(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Trainer"
                        or (c["type"] == "Trainer" and is_playable_trainer(c["name"])) or c["stage"] is None
                        else f"trainer has stage {c['stage']!r}")
        assert not fails, report(fails)

    def test_evolves_from_set_only_for_evolutions(self, cards):
        def check(c):
            evolved = c["stage"] in ("Stage 1", "Stage 2")
            if evolved and not c["evolves_from"]:
                return f"{c['stage']} without evolves_from"
            if not evolved and c["evolves_from"] is not None:
                return f"non-evolution with evolves_from {c['evolves_from']!r}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_evolves_from_looks_like_a_name(self, cards):
        def check(c):
            value = c["evolves_from"]
            if value is None:
                return None
            if "Evolves" in value or len(value) > 40:
                return f"scrape leaked into evolves_from: {value!r}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_evolves_from_is_a_known_card_name(self, cards):
        """Pre-evolutions are usually printed somewhere in the database."""
        names = {c["name"].replace(" ", "") for c in cards}
        missing = sorted({c["evolves_from"] for c in cards
                          if c["evolves_from"] and c["evolves_from"].replace(" ", "") not in names})
        assert not missing, f"evolves_from values with no matching card name: {missing[:20]}"


class TestRarityAndPackPoints:
    def test_rarity_is_valid(self, cards):
        """Rarity must be one of the known symbols in constants.RARITIES."""
        fails = collect(cards, lambda c: None if c["rarity"] in RARITIES
                        else f"unknown rarity {c['rarity']!r}")
        assert not fails, report(fails)

    def test_promo_rarity_iff_promo_set(self, cards):
        fails = collect(cards, lambda c: None if (c["rarity"] == "Promo") == is_promo(c)
        else f"rarity {c['rarity']!r} on set {c['set_code']!r}")

        assert not fails, report(fails)

    def test_pack_points_null_iff_promo(self, cards):
        fails = collect(cards, lambda c: None if (c["pack_points"] is None) == (c["rarity"] == "Promo")
                        else f"pack_points {c['pack_points']!r} with rarity {c['rarity']!r}")
        assert not fails, report(fails)

    def test_pack_points_match_rarity_table(self, cards):
        def check(c):
            if c["rarity"] == "Promo":
                return None
            table = SHINY_PACK_POINTS if c["shiny"] else PACK_POINTS
            expected = table.get(c["rarity"])
            return None if c["pack_points"] == expected else (
                f"pack_points {c['pack_points']} != {expected} (rarity {c['rarity']}, shiny {c['shiny']})")
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_pack_points_is_positive_int(self, cards):
        fails = collect(cards, lambda c: None if c["pack_points"] is None
                        or (type(c["pack_points"]) is int and c["pack_points"] > 0)
                        else f"bad pack_points {c['pack_points']!r}")
        assert not fails, report(fails)


# ---------------------------------------------------------------------------
# Special properties
# ---------------------------------------------------------------------------

class TestFlags:
    def test_flags_are_bools(self, cards):
        fails = collect(cards, lambda c: next(
            (f"{f} is {type(c[f]).__name__}" for f in ("ex", "mega", "shiny")
             if type(c[f]) is not bool), None))
        assert not fails, report(fails)

    def test_ex_matches_name(self, cards):
        fails = collect(cards, lambda c: None if c["ex"] == ("ex" in c["name"].split(" "))
                        else f"ex={c['ex']} for name {c['name']!r}")
        assert not fails, report(fails)

    def test_mega_implies_ex_and_pokemon(self, cards):
        fails = collect(cards, lambda c: None if not c["mega"] or (c["ex"] and c["type"] == "Pokémon")
                        else "mega without ex / not a Pokémon")
        assert not fails, report(fails)

    def test_trainers_have_no_pokemon_flags(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Trainer"
                        or not (c["ex"] or c["mega"] or c["shiny"]) else "trainer flagged ex/mega/shiny")
        assert not fails, report(fails)

    def test_shiny_only_on_star_rarities(self, cards):
        fails = collect(cards, lambda c: None if not c["shiny"] or c["rarity"] in ("☆", "☆☆", "☆☆☆", "Promo")
                        else f"shiny with rarity {c['rarity']!r}")
        assert not fails, report(fails)


class TestPoints:
    def test_points_null_iff_trainer(self, cards):
        fails = collect(cards, lambda c: None if (c["points"] is None) == (
            c["type"] == "Trainer" and not (c["type"] == "Trainer" and is_playable_trainer(c["name"])))
            else f"points {c['points']!r} for type {c['type']}")
        assert not fails, report(fails)

    def test_points_match_ex_and_mega(self, cards):
        def check(c):
            if c["type"] == "Trainer":
                return None
            expected = 3 if (c["mega"] and c["ex"]) else 2 if c["ex"] else 1
            return None if c["points"] == expected else f"points {c['points']} != {expected}"
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_points_are_ints_in_range(self, cards):
        fails = collect(cards, lambda c: None if c["points"] is None
                        or (type(c["points"]) is int and 1 <= c["points"] <= 3)
                        else f"bad points {c['points']!r}")
        assert not fails, report(fails)


class TestDeckBuilder:
    # Sets the Flibustier datamine does not cover yet; their cards carry the
    # documented fallback of 0 until a datamine update, then a re-scrape.
    DATAMINE_PENDING_PREFIXES = ("c1", "pc")

    def test_deck_builder_nr_is_a_positive_int(self, cards):
        """A zero here means the datamine lookup silently came back empty.

        transform_cards falls back to 0 when a card is missing from the
        Flibustier datamine. That passes the JSON schema, so this is the only
        thing standing between a transient network error and a dataset full of
        zeroed deck-builder numbers. Sets the datamine does not cover yet are
        exempt; drop them from DATAMINE_PENDING_PREFIXES once it catches up.
        """
        fails = collect(cards, lambda c: None if type(c["deckBuilderNr"]) is int
                        and (c["deckBuilderNr"] > 0
                             or c["set_code"] in self.DATAMINE_PENDING_PREFIXES)
                        else f"deckBuilderNr {c['deckBuilderNr']!r}")
        assert not fails, report(fails)


class TestArtStyle:
    def test_art_style_is_valid_or_null(self, cards):
        fails = collect(cards, lambda c: None if c["art_style"] is None or c["art_style"] in ART_STYLES
                        else f"bad art_style {c['art_style']!r}")
        assert not fails, report(fails)

    def test_diamond_rarities_have_no_special_art(self, cards):
        fails = collect(cards, lambda c: None if not (c["rarity"] or "").startswith("◊")
                        or c["art_style"] in (None, "Parallel Foil")
                        else f"{c['rarity']} card with art_style {c['art_style']!r}")
        assert not fails, report(fails)

    def test_star_rarities_have_art_style(self, cards):
        """Every non-promo star card must be classified."""
        fails = collect(cards, lambda c: None if is_promo(c) or c["rarity"] not in STAR_RARITIES
                        or c["art_style"] else "star rarity without art_style")
        assert not fails, report(fails)

    def test_crown_rares_are_unclassified(self, cards):
        """Asserted explicitly: the previous exemption keyed off "♕", a rarity
        string the scraper never produces, so Crown Rare was silently skipped.
        Change this test if a crown art style is ever added.
        """
        fails = collect(cards, lambda c: None if c["rarity"] != CROWN_RARITY
                        or c["art_style"] is None
                        else f"Crown Rare with art_style {c['art_style']!r}")
        assert not fails, report(fails)

    def test_shiny_art_styles_match_shiny_flag(self, cards):
        fails = collect(cards, lambda c: None if (c["art_style"] in {"Shiny", "Shiny Full Art"}) == c["shiny"]
                        or c["art_style"] in ("Parallel Foil", "Immersive Art")
                        else f"art_style {c['art_style']!r} vs shiny={c['shiny']}")
        assert not fails, report(fails)

    def test_immersive_is_three_star(self, cards):
        fails = collect(cards, lambda c: None if (c["art_style"] == "Immersive Art")
                        == (c["rarity"] == "☆☆☆") or is_promo(c)
                        else f"art_style {c['art_style']!r} with rarity {c['rarity']!r}")
        assert not fails, report(fails)

    def test_full_art_is_two_star(self, cards):
        fails = collect(cards, lambda c: None if c["art_style"] not in ("Full Art", "Special Illustration Art")
                        or c["rarity"] in ("☆☆", "Promo") else f"{c['art_style']} with rarity {c['rarity']!r}")
        assert not fails, report(fails)

    def test_sia_is_ex_or_mega(self, cards):
        fails = collect(cards, lambda c: None if c["art_style"] != "Special Illustration Art"
                        or c["ex"] or c["mega"] else "SIA on a non-ex card")
        assert not fails, report(fails)

    def test_illustration_art_is_one_star(self, cards):
        fails = collect(cards, lambda c: None if c["art_style"] != "Illustration Art"
                        or c["rarity"] in ("☆", "Promo") else f"Illustration Art with rarity {c['rarity']!r}")
        assert not fails, report(fails)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

class TestStats:
    def test_pokemon_health_is_int(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Pokémon"
                        or type(c["health"]) is int else f"health is {c['health']!r}")
        assert not fails, report(fails)

    def test_health_range_and_step(self, cards):
        def check(c):
            hp = c["health"]
            if hp is None:
                return None
            if not 30 <= hp <= 600:
                return f"health {hp} out of range"
            return None if hp % 10 == 0 else f"health {hp} not a multiple of 10"
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_pokemon_retreat_is_int_in_range(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Pokémon"
                        or (type(c["retreat"]) is int and 0 <= c["retreat"] <= 5)
                        else f"bad retreat {c['retreat']!r}")
        assert not fails, report(fails)

    def test_weakness_is_energy_type_or_null(self, cards):
        fails = collect(cards, lambda c: None if c["weakness"] is None
                        or c["weakness"] in ENERGY_TYPES or c["weakness"] == "none" else f"bad weakness {c['weakness']!r}")
        assert not fails, report(fails)

    def test_trainers_have_no_stats(self, cards):
        """Retreat and weakness stay absent on trainers. Health is present
        only on fossil items, which are playable 40-HP basics."""
        def check(c):
            if c["type"] != "Trainer":
                return None
            if (c["type"] == "Trainer" and is_playable_trainer(c["name"])):
                combat = ("retreat",)
            else:
                combat = ("health", "retreat", "weakness")
            return next((f"trainer has {f}={c[f]!r}" for f in combat
                         if c[f] is not None), None)
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_most_pokemon_have_a_weakness(self, cards):
        pokemon = [c for c in cards if c["type"] == "Pokémon"]
        missing = [c["id"] for c in pokemon if c["weakness"] is None]
        assert len(missing) < max(5, len(pokemon) * 0.02), (
            f"{len(missing)} Pokémon without weakness, likely a scrape regression: {missing[:20]}")


# ---------------------------------------------------------------------------
# Ability, card text, attacks
# ---------------------------------------------------------------------------

class TestAbility:
    def test_shape(self, cards):
        fails = collect(cards, lambda c: None if isinstance(c["ability"], dict)
                        and set(c["ability"]) == ABILITY_KEYS else f"bad ability shape {c['ability']!r}")
        assert not fails, report(fails)

    def test_exists_is_bool(self, cards):
        fails = collect(cards, lambda c: None if type(c["ability"]["exists"]) is bool else "exists not bool")
        assert not fails, report(fails)

    def test_populated_iff_exists(self, cards):
        def check(c):
            ability = c["ability"]
            filled = ability["name"] is not None and ability["effect"] is not None
            if ability["exists"] and not filled:
                return "exists=True but name/effect null"
            if not ability["exists"] and (ability["name"] or ability["effect"]):
                return "exists=False but name/effect populated"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_name_has_no_label_leftover(self, cards):
        fails = collect(cards, lambda c: None if not c["ability"]["exists"]
                        or ("Ability" not in c["ability"]["name"] and len(c["ability"]["name"]) <= 60)
                        else f"bad ability name {c['ability']['name']!r}")
        assert not fails, report(fails)

    def test_trainers_have_no_ability(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Trainer"
                        or not c["ability"]["exists"] else "trainer with ability")
        assert not fails, report(fails)


class TestCardText:
    def test_trainers_have_card_text(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Trainer"
                        or (isinstance(c["card_text"], str) and len(c["card_text"]) > 5)
                        else f"trainer card_text {c['card_text']!r}")
        assert not fails, report(fails)

    def test_pokemon_have_no_card_text(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Pokémon" or c["card_text"] is None
                        else "Pokémon with card_text")
        assert not fails, report(fails)

    def test_card_text_has_no_scrape_leftovers(self, cards):
        noise = ("Illustrated by", "Weakness:", "Retreat:", "Versions")
        fails = collect(cards, lambda c: next(
            (f"card_text contains {n!r}" for n in noise
             if c["card_text"] and n in c["card_text"]), None))
        assert not fails, report(fails)


class TestAttacks:
    def test_shape(self, cards):
        def check(c):
            attacks = c["attacks"]
            if not isinstance(attacks, dict) or set(attacks) != {"1", "2"}:
                return f"bad attacks keys {list(attacks)}"
            for slot, attack in attacks.items():
                if set(attack) != ATTACK_KEYS:
                    return f"slot {slot} keys {set(attack)}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_no_gap_between_slots(self, cards):
        fails = collect(cards, lambda c: None if c["attacks"]["1"]["name"]
                        or not c["attacks"]["2"]["name"] else "slot 2 filled while slot 1 empty")
        assert not fails, report(fails)

    def test_empty_slots_are_fully_null(self, cards):
        def check(c):
            for slot, attack in c["attacks"].items():
                if attack["name"] is None and any(attack[k] is not None for k in ATTACK_KEYS):
                    return f"slot {slot} half-populated: {attack}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_cost_is_energy_symbols(self, cards):
        def check(c):
            for slot, attack in c["attacks"].items():
                if attack["name"] and not (attack["cost"] and COST_RE.match(attack["cost"])):
                    return f"slot {slot} bad cost {attack['cost']!r}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_damage_is_int_in_range(self, cards):
        def check(c):
            for slot, attack in c["attacks"].items():
                dmg = attack["damage"]
                if dmg is None:
                    continue
                if type(dmg) is not int or not 10 <= dmg <= 400 or dmg % 5:
                    return f"slot {slot} bad damage {dmg!r}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_attack_name_is_clean(self, cards):
        def check(c):
            for slot, attack in c["attacks"].items():
                name = attack["name"]
                if name and (len(name) > 40 or name[-1].isdigit()):
                    return f"slot {slot} suspicious name {name!r}"
            return None
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_trainers_have_no_attacks(self, cards):
        fails = collect(cards, lambda c: None if c["type"] != "Trainer"
                        or not any(a["name"] for a in c["attacks"].values()) else "trainer with attacks")
        assert not fails, report(fails)

    def test_pokemon_can_act(self, cards):
        """Every Pokémon has an attack or an ability."""
        fails = collect(cards, lambda c: None if c["type"] != "Pokémon"
                        or c["attacks"]["1"]["name"] or c["ability"]["exists"]
                        else "Pokémon with no attack and no ability")
        assert not fails, report(fails)


# ---------------------------------------------------------------------------
# Images
# ---------------------------------------------------------------------------

class TestImages:
    def test_webp_url(self, cards):
        def check(c):
            num = c["id"].rsplit("-", 1)[1]
            expected = f"{GITHUB_BASE_URL}/webp/cards/{c['set_code']}/{num}.webp"
            return None if c["image"] == expected else f"image {c['image']!r} != {expected!r}"
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_png_url(self, cards):
        def check(c):
            num = c["id"].rsplit("-", 1)[1]
            expected = f"{GITHUB_BASE_URL}/png/cards/{c['set_code']}/{num}.png"
            return None if c["image_png"] == expected else f"image_png {c['image_png']!r} != {expected!r}"
        fails = collect(cards, check)
        assert not fails, report(fails)

    def test_webp_files_exist(self, cards):
        missing = [c["id"] for c in cards
                   if not os.path.exists(os.path.join(WEBP_CARDS_DIR, c["set_code"],
                                                      f"{c['id'].rsplit('-', 1)[1]}.webp"))]
        assert not missing, f"{len(missing)} webp files missing: {missing[:20]}"

    def test_png_files_exist(self, cards):
        missing = [c["id"] for c in cards
                   if not os.path.exists(os.path.join(PNG_CARDS_DIR, c["set_code"],
                                                      f"{c['id'].rsplit('-', 1)[1]}.png"))]
        assert not missing, f"{len(missing)} png files missing: {missing[:20]}"

    def test_no_orphan_image_files(self, cards):
        known = {(c["set_code"], c["id"].rsplit("-", 1)[1]) for c in cards}
        orphans = []
        for set_dir in sorted(os.listdir(WEBP_CARDS_DIR)) if os.path.isdir(WEBP_CARDS_DIR) else []:
            path = os.path.join(WEBP_CARDS_DIR, set_dir)
            if not os.path.isdir(path):
                continue
            for filename in os.listdir(path):
                num = filename.rsplit(".", 1)[0]
                if (set_dir, num) not in known:
                    orphans.append(f"{set_dir}/{filename}")
        assert not orphans, f"Images with no card entry: {orphans[:20]}"


class TestFossilTrainers:
    def test_fossil_items_are_playable_40_hp_basics(self, cards):
        fossils = [c for c in cards if (c["type"] == "Trainer" and is_playable_trainer(c["name"]))]
        assert fossils
        for c in fossils:
            assert c["type"] == "Trainer"
            assert c["subtype"] == "Item"
            assert c["health"] == 40
            assert c["points"] == 1
            assert c["stage"] == "Basic"

    def test_fossil_weakness_is_none(self, cards):
        fossils = [c for c in cards if (c["type"] == "Trainer" and is_playable_trainer(c["name"]))]
        assert fossils
        for c in fossils:
            assert c["weakness"] == "none"

    def test_other_trainers_keep_null_gameplay(self, cards):
        others = [c for c in cards if c["type"] == "Trainer" and not (c["type"] == "Trainer" and is_playable_trainer(c["name"]))]
        assert others
        for c in others:
            assert c["health"] is None
            assert c["points"] is None
            assert c["stage"] is None


def test_trade_fields_come_straight_from_the_table(cards):
    """Every published trade triple equals its TRADE_RULES row, with no
    per-rarity special case in between."""
    from constants import TRADE_RULES
    wrong = [
        card["id"] for card in cards
        if (card["tradable"], card["sharable"], card["trade_cost"])
        != TRADE_RULES[(card["rarity"], card["shiny"], card["art_style"])]
    ]
    assert not wrong, f"{len(wrong)} cards disagree with the table: {wrong[:10]}"