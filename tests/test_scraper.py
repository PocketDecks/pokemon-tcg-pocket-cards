"""Parsing tests for the Limitless TCG card pages.

The markup below mirrors the structure of the real pages (title section,
type line, attack blocks, weakness/retreat block, prints table). Nothing here
makes a network request.
"""
import pytest
from bs4 import BeautifulSoup

from scraper import extract_card
from set_profile import SetProfile

POKEMON_PAGE = """
<div class="card-image"><img src="https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/B3b/B3b_081_EN.webp"></div>
<div class="card-text">
  <div class="card-text-section">
    <p class="card-text-title">
      <span class="card-text-name"><a href="/cards/B3b/81">Mega Sableye ex</a></span>
      - Darkness               - 170 HP
    </p>
    <p class="card-text-type">Pok&eacute;mon
              - Basic</p>
  </div>
  <div class="card-text-section">
    <div class="card-text-attack">
      <p class="card-text-attack-info"><span class="ptcg-symbol">DC</span>Cursed Jewel 80</p>
      <p class="card-text-attack-effect">Do 40 damage to the Attacking Pok&eacute;mon.</p>
    </div>
  </div>
  <div class="card-text-section">
    <p class="card-text-wrr">Weakness: Grass<br>Retreat: 1<br></p>
  </div>
  <div class="card-text-section">
    <p class="card-text-wrr card-text-mega-rule">Mega Evolution
      <span class="ptcg-symbol ex-symbol">e</span><span class="copy-only">x</span>
      rule: When your Mega Evolution Pok&eacute;mon ex is Knocked Out, your opponent gets 3 points.</p>
  </div>
  <div class="card-text-section card-text-artist">Illustrated by <a href="/cards?q=!artist:x">PLANETA Yamashita</a></div>
</div>
<div class="card-prints-current">
  <a href="/cards/B3b"><div class="prints-current-details">
    <span class="text-lg">Everyday Wonders  (B3b)</span><span>#81 &middot; &#9734;&#9734;</span>
  </div></a>
</div>
<table class="card-prints-versions">
  <tr><th colspan="2">Versions</th></tr>
  <tr><td><a href="/cards/B3b/41">Everyday Wonders<span class="prints-table-card-number">#41</span></a></td><td>&#9674;&#9674;&#9674;&#9674;</td></tr>
  <tr class="current"><td><a>Everyday Wonders<span class="prints-table-card-number">#81</span></a></td><td>&#9734;&#9734;</td></tr>
</table>
"""

TRAINER_PAGE = """
<div class="card-image"><img src="https://limitlesstcg.nyc3.cdn.digitaloceanspaces.com/pocket/B3b/B3b_066_EN.webp"></div>
<div class="card-text">
  <div class="card-text-section">
    <p class="card-text-title"><span class="card-text-name"><a href="/cards/B3b/66">Elesa</a></span></p>
    <p class="card-text-type">Trainer
              - Supporter</p>
  </div>
  <div class="card-text-section">Return all Pok&eacute;mon Tools attached to each Pok&eacute;mon
    <span class="reminder-text">(both yours and your opponent's)</span> to their owner's hand.</div>
  <div class="card-text-section card-text-artist">Illustrated by <a href="/cards?q=!artist:y">Nobusawa</a></div>
</div>
<div class="card-prints-current">
  <a href="/cards/B3b"><div class="prints-current-details">
    <span class="text-lg">Everyday Wonders  (B3b)</span><span>#66 &middot; &#9674;&#9674;</span>
  </div></a>
</div>
<table class="card-prints-versions">
  <tr><th colspan="2">Versions</th></tr>
  <tr class="current"><td><a>Everyday Wonders<span class="prints-table-card-number">#66</span></a></td><td>&#9674;&#9674;</td></tr>
</table>
"""


def parse(html, set_code="B3b"):
    return extract_card(BeautifulSoup(html, "html.parser"), SetProfile.of(set_code))

DUAL_TYPE_PAGE = POKEMON_PAGE.replace(
    "Mega Sableye ex</a></span>\n      - Darkness               - 170 HP",
    "Mega Greninja ex</a></span>\n      - Water/Darkness               - 200 HP",
).replace("Mega Sableye ex", "Mega Greninja ex")


@pytest.fixture(scope="module")
def pokemon():
    return parse(POKEMON_PAGE)


@pytest.fixture(scope="module")
def trainer():
    return parse(TRAINER_PAGE)


class TestPokemonCard:
    def test_identity(self, pokemon):
        assert (pokemon["number"], pokemon["name"]) == ("81", "Mega Sableye ex")

    def test_type_and_subtype(self, pokemon):
        assert pokemon["type"] == "Pokémon" and pokemon["subtype"] == "Darkness"

    def test_health_is_an_int(self, pokemon):
        assert pokemon["hp"] == 170

    def test_stage_and_evolution(self, pokemon):
        assert pokemon["stage"] == "Basic" and pokemon["evolves_from"] is None

    def test_weakness_and_retreat(self, pokemon):
        assert pokemon["weakness"] == "Grass" and pokemon["retreat"] == 1

    def test_attack_is_split_into_cost_name_damage_effect(self, pokemon):
        assert pokemon["attacks"]["1"] == {
            "cost": "DC", "name": "Cursed Jewel", "damage": 80,
            "effect": "Do 40 damage to the Attacking Pokémon."}

    def test_second_attack_slot_is_fully_null(self, pokemon):
        assert set(pokemon["attacks"]["2"].values()) == {None}

    def test_flags_and_points(self, pokemon):
        assert (pokemon["ex"], pokemon["mega"], pokemon["points"]) == (True, True, 3)

    def test_rarity_comes_from_the_current_print(self, pokemon):
        assert pokemon["rarity"] == "☆☆"

    def test_alternate_versions_include_the_other_print(self, pokemon):
        assert {(a["set_code"], a["id"]) for a in pokemon["alternate_versions"]} == {
            ("b3b", 41), ("b3b", 81)}

    def test_artist_and_image(self, pokemon):
        assert pokemon["artist"] == "PLANETA Yamashita"
        assert pokemon["image"].endswith("B3b_081_EN.webp")

    def test_pokemon_have_no_trainer_text(self, pokemon):
        assert pokemon["card_text"] is None

    def test_no_ability_block_means_exists_false(self, pokemon):
        assert pokemon["ability"] == {"exists": False, "name": None, "effect": None}


class TestTrainerCard:
    def test_type_and_subtype(self, trainer):
        assert trainer["type"] == "Trainer" and trainer["subtype"] == "Supporter"

    def test_effect_text_is_captured_and_whitespace_collapsed(self, trainer):
        assert trainer["card_text"] == (
            "Return all Pokémon Tools attached to each Pokémon "
            "(both yours and your opponent's) to their owner's hand.")

    def test_pokemon_only_fields_are_null(self, trainer):
        assert all(trainer[field] is None
                   for field in ("hp", "stage", "evolves_from", "retreat", "weakness", "points"))

    def test_trainers_have_no_attacks(self, trainer):
        assert all(slot["name"] is None for slot in trainer["attacks"].values())

    def test_trainers_are_never_ex_or_mega(self, trainer):
        assert trainer["ex"] is False and trainer["mega"] is False


class TestEvolutionLine:
    def test_evolves_from_is_read_off_the_type_line(self):
        card = parse(POKEMON_PAGE.replace(
            'class="card-text-type">Pokémon\n              - Basic',
            'class="card-text-type">Pokémon - Stage 2 - Evolves from Ivysaur').replace(
            "Pok&eacute;mon\n              - Basic",
            "Pok&eacute;mon - Stage 2 - Evolves from Ivysaur"))
        assert card["stage"] == "Stage 2" and card["evolves_from"] == "Ivysaur"

    def test_unknown_stage_does_not_crash(self):
        card = parse(POKEMON_PAGE.replace(
            "Pok&eacute;mon\n              - Basic", "Pok&eacute;mon - Mega Evolution"))
        assert card["stage"] == "Unknown"


class TestAttackParsing:
    def build(self, info, effect="Some effect."):
        return POKEMON_PAGE.replace(
            '<span class="ptcg-symbol">DC</span>Cursed Jewel 80', info).replace(
            "Do 40 damage to the Attacking Pok&eacute;mon.", effect)

    def test_attack_name_ending_in_x_is_not_truncated(self):
        card = parse(self.build('<span class="ptcg-symbol">D</span>Vortex'))
        assert card["attacks"]["1"]["name"] == "Vortex"
        assert card["attacks"]["1"]["damage"] is None

    def test_variable_damage_keeps_the_leading_number(self):
        card = parse(self.build('<span class="ptcg-symbol">D</span>Wild Swing 30x'))
        assert card["attacks"]["1"]["name"] == "Wild Swing"
        assert card["attacks"]["1"]["damage"] == 30

    def test_plus_damage_keeps_the_leading_number(self):
        card = parse(self.build('<span class="ptcg-symbol">DC</span>Crunch 60+'))
        assert card["attacks"]["1"] == {"cost": "DC", "name": "Crunch", "damage": 60,
                                        "effect": "Some effect."}

    def test_attack_with_no_damage_or_effect(self):
        card = parse(self.build('<span class="ptcg-symbol">C</span>Call for Family', ""))
        assert card["attacks"]["1"]["name"] == "Call for Family"
        assert card["attacks"]["1"]["effect"] is None

    def test_only_the_first_two_attacks_are_kept(self):
        extra = ('<div class="card-text-attack"><p class="card-text-attack-info">'
                 '<span class="ptcg-symbol">C</span>Second 20</p></div>'
                 '<div class="card-text-attack"><p class="card-text-attack-info">'
                 '<span class="ptcg-symbol">C</span>Third 30</p></div>')
        card = parse(POKEMON_PAGE.replace("</div>\n  </div>\n  <div class=\"card-text-section\">\n    <p class=\"card-text-wrr\">",
                                          "</div>" + extra + "</div><div class=\"card-text-section\"><p class=\"card-text-wrr\">"))
        assert [slot["name"] for slot in card["attacks"].values()] == ["Cursed Jewel", "Second"]


class TestAbility:
    def test_ability_name_and_effect(self):
        ability = ('<div class="card-text-ability">'
                   '<p class="card-text-ability-info">Ability: Shadow Veil</p>'
                   '<p class="card-text-ability-effect">Prevent all damage.</p></div>')
        card = parse(POKEMON_PAGE.replace('<div class="card-text-attack">', ability + '<div class="card-text-attack">'))
        assert card["ability"] == {"exists": True, "name": "Shadow Veil",
                                   "effect": "Prevent all damage."}


class TestMegaDetection:
    def test_rule_text_flags_a_mega_even_with_an_unusual_name(self):
        card = parse(POKEMON_PAGE.replace("Mega Sableye ex", "Sableye ex"))
        assert card["mega"] is True and card["points"] == 3

    def test_a_plain_ex_is_not_mega(self):
        card = parse(POKEMON_PAGE.replace("Mega Sableye ex", "Sableye ex").replace(
            "Mega Evolution\n      ", "Nothing\n      "))
        assert card["mega"] is False and card["points"] == 2

    def test_a_trainer_quoting_the_rule_is_not_mega(self):
        card = parse(TRAINER_PAGE.replace(
            "to their owner's hand.",
            "Mega Evolution e x rule: your opponent gets 3 points."))
        assert card["mega"] is False


class TestPackDetection:
    def test_named_pack_is_read_from_the_prints_block(self):
        card = parse(POKEMON_PAGE.replace("#81 &middot; &#9734;&#9734;", "#81 &middot; Mewtwo pack"))
        assert card["pack"] == "Mewtwo pack"

    def test_pack_defaults_to_the_every_pack_sentinel(self, pokemon):
        assert pokemon["pack"] == "Every pack"

    def test_promo_a_prefers_the_longest_matching_keyword(self):
        card = parse(POKEMON_PAGE.replace("#81 &middot; &#9734;&#9734;",
                                          "Premium Missions"), set_code="P-A")
        assert card["pack"] == "Premium Missions"

    def test_promo_a_falls_back_to_the_sentinel_when_nothing_matches(self):
        card = parse(POKEMON_PAGE, set_code="P-A")
        assert card["pack"] == "Every pack"


class TestAlternateVersionSetCodes:
    def test_cross_set_href_wins_over_the_current_set(self):
        """The set comes from the link, the number from the #NN span."""
        card = parse(POKEMON_PAGE.replace('href="/cards/B3b/41"', 'href="/cards/P-A/41"'))
        assert ("p-a", 41) in {(a["set_code"], a["id"]) for a in card["alternate_versions"]}

    def test_current_print_without_an_href_uses_the_set_being_scraped(self, pokemon):
        current = [a for a in pokemon["alternate_versions"] if a["id"] == 81][0]
        assert current["set_code"] == "b3b"

    def test_missing_rarity_defaults_to_promo(self):
        card = parse(POKEMON_PAGE.replace("<td>&#9674;&#9674;&#9674;&#9674;</td>", "<td></td>"))
        assert [a["rarity"] for a in card["alternate_versions"] if a["id"] == 41] == ["Promo"]


class TestDualTypePokemon:
    card = parse(DUAL_TYPE_PAGE)

    def test_subtype_is_the_first_type(self):
        assert self.card["subtype"] == "Water"

    def test_subtype_2_is_the_second_type(self):
        assert self.card["subtype_2"] == "Darkness"

    def test_single_type_pokemon_have_no_subtype_2(self, pokemon):
        assert pokemon["subtype_2"] is None

    def test_trainers_have_no_subtype_2(self, trainer):
        assert trainer["subtype_2"] is None
