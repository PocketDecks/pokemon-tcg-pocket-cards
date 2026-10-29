# Copyright (C) 2024 Chase Manning <chase@manning.dev>
# Copyright (C) 2026 Leonid Dalin <infoLeonid@protonmail.com> & Chase Manning <chase@manning.dev>
#
# Original code by Chase Manning is released under the MIT License.
# Modifications and additions for version 5 onwards are released under
# the GNU Affero General Public License v3.0 (AGPL-3.0-or-later).
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
r"""Scrape Pokemon TCG Pocket card data from the Limitless TCG website.

This module fetches and parses individual card pages from
``https://pocket.limitlesstcg.com/cards/``, extracting name, HP, type,
attacks, ability, rarity, pack, artist, and alternate print versions.
It also discovers set metadata (name and release date) from the index
page and iterates over sequential card numbers to scrape an entire set.
"""

import re
import time
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
from constants import (BASE_URL, MAX_CONSECUTIVE_ERRORS, MAX_RETRIES,
                       PROMO_A_PACK_KEYWORDS, SESSION, DEFAULT_TIMEOUT,
                       RATE_LIMIT_DELAY, is_playable_trainer)
from utils import clean_text, parse_release_date, parse_trainer_subtype, to_int

class NotFound(Exception):
    r"""NotFound

    Raised when a card page returns HTTP 404. The card does not exist,
    so the scraper should not retry it.
    """
    pass


def fetch_page(url):
    r"""fetch_page(url) -> BeautifulSoup

    Fetch a URL and return a parsed BeautifulSoup object. Retries on
    network errors up to ``MAX_RETRIES`` times with ``RATE_LIMIT_DELAY``
    seconds between attempts. Raises :class:`NotFound` immediately on
    HTTP 404 since a missing card is not a transient error.

    Args:
        url (str): the full URL to fetch

    Returns:
        BeautifulSoup: parsed HTML of the page

    Raises:
        NotFound: if the server returns HTTP 404
        requests.RequestException: if all retry attempts fail with a
            network or server error

    .. note::

        Called as ``fetch_page("https://pocket.limitlesstcg.com/cards/a1/1")``.
    """
    retry_delay = RATE_LIMIT_DELAY
    for attempt in range(MAX_RETRIES):
        try:
            response = SESSION.get(url, timeout=DEFAULT_TIMEOUT)
            if response.status_code == requests.codes.not_found:
                raise NotFound(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "html.parser")
        except requests.RequestException:
            if attempt == MAX_RETRIES - 1:
                raise
            time.sleep(retry_delay)
            retry_delay += RATE_LIMIT_DELAY


def get_all_set_codes():
    r"""get_all_set_codes() -> list of str

    Fetch the card index page and return every set code listed in the
    sets table, uppercased.

    Returns:
        list of str: set codes such as ``"A1"``, ``"A2a"``, ``"P-A"``

    .. note::

        Reads the ``sets-table`` at ``BASE_URL``. ``"A1"`` is one of the codes returned.
    """
    return [span.text.strip().upper() for span in fetch_page(BASE_URL).select("table.sets-table span.code")]


def discover_set(set_code):
    r"""discover_set(set_code) -> tuple

    Look up a set's display name and release date from the card index
    table. If the set is not listed on the index page yet, falls back
    to scraping the set page's ``<title>`` tag for the name. The
    release date is ``None`` in that case because the set page does
    not show one.

    Args:
        set_code (str): the set code to look up, case-insensitive
            (e.g. ``"a1"``, ``"p-a"``)

    Returns:
        tuple: ``(name, release_date)`` where name is a str and
        release_date is a str in ``"YYYY-MM-DD"`` format, or None if
        the set is not yet indexed

    .. note::

        ``discover_set("a1")`` returns ``("Genetic Apex", "2024-10-30")``.
    """
    for row in fetch_page(BASE_URL).select("table.sets-table tr"):
        code_el = row.find("span", class_="code")
        if not code_el or code_el.text.strip().lower() != set_code.lower(): continue
        cells = row.find_all("td")
        code_el.extract()
        return clean_text(cells[0].get_text(" ", strip=True)), parse_release_date(cells[1].get_text())
    # not indexed yet: fall back to the set page title, no date
    title = fetch_page(f"{BASE_URL}{set_code}").find("title").text
    return clean_text(title.split(" (")[0].split(" - ")[0]), None


def _parse_title(body):
    r"""_parse_title(body) -> (number, name, energy_type, hp_text)

    Read the card-text title line. Format is
    ``"Caterpie - Grass - 40 HP"``; trainers omit the energy and HP parts,
    so ``energy_type`` is None and ``hp_text`` is the name.
    """
    title_el = body.find("p", class_="card-text-title")
    link = title_el.find("a")
    parts = [p.strip() for p in title_el.get_text(" ", strip=True).split(" - ")]
    return (link["href"].split("/")[-1],
            clean_text(link.text),
            parts[1] if len(parts) > 2 else None,
            parts[-1])


def _parse_prints(soup, set_code):
    r"""_parse_prints(soup, set_code) -> (rarity, alternate_versions)

    Read the versions table: the current print's rarity, and one dict per
    other print with ``set_code``, ``set_name``, ``id`` and ``rarity``.
    Rows whose href is missing fall back to the set being scraped.
    """
    table = soup.find("table", class_="card-prints-versions")
    if not table:
        return None, []

    current = table.find("tr", class_="current")
    rarity = clean_text(current.find_all("td")[-1].text) if current else None

    alt_versions = []
    for row in table.find_all("tr")[1:]:
        tds = row.find_all("td")
        if not tds or not tds[0].find("a"): continue
        a_tag = tds[0].find("a")
        href = a_tag.get("href", "")
        num_span = a_tag.find("span")
        alt_versions.append({
            "set_code": [p for p in href.split("/") if p][-2].lower() if href else set_code.lower(),
            "set_name": clean_text(a_tag.contents[0]),
            "id": to_int(clean_text(num_span.text).replace("#", "") if num_span else ""),
            "rarity": clean_text(tds[1].text) or "Promo",
        })
    return rarity, alt_versions


def _parse_pack(soup, set_profile):
    r"""_parse_pack(soup, set_profile) -> str

    Read the pack from the current-prints block, or return the
    ``"Every pack"`` sentinel the transformer resolves later.

    Promo-A does not name a pack, so its block is matched against
    :data:`constants.PROMO_A_PACK_KEYWORDS`, longest keyword first, so
    ``"Premium Missions"`` wins over ``"Missions"``.
    """
    set_info = soup.find("div", class_="card-prints-current")
    if not set_info:
        return "Every pack"

    if set_profile.is_promo_a:
        text = set_info.get_text()
        return clean_text(next(
            (kw for kw in sorted(PROMO_A_PACK_KEYWORDS, key=len, reverse=True) if kw in text),
            "Every pack",
        ))

    spans = set_info.find_all("span")
    if spans:
        tail = spans[-1].text.strip().split("·")[-1].strip()
        if tail.endswith(" pack"):
            return clean_text(tail)
    return "Every pack"


def _parse_pokemon_stats(type_text, raw_text):
    r"""_parse_pokemon_stats(type_text, raw_text) -> (stage, evolves_from, retreat, weakness)

    Pokémon-only fields. ``stage`` falls back to ``"Unknown"`` rather than
    None so a markup change is visible in the data instead of silent.
    """
    stage_match = re.search(r"(Basic|Stage 1|Stage 2)", type_text)
    stage = stage_match.group(1) if stage_match else "Unknown"

    evolves_from = None
    if stage in ("Stage 1", "Stage 2"):
        evo_match = re.search(r"Evolves from\s*(.+)", type_text)
        evolves_from = evo_match.group(1).strip() if evo_match else None

    retreat_match = re.search(r"Retreat:\s*(\d+)", raw_text)
    weakness_match = re.search(r"Weakness:\s*([A-Za-z]+)", raw_text)
    return (stage,
            evolves_from,
            int(retreat_match.group(1)) if retreat_match else 0,
            weakness_match.group(1) if weakness_match else None)


def _parse_ability(body):
    r"""_parse_ability(body) -> dict

    ``{"exists": bool, "name": str or None, "effect": str or None}``.
    """
    div = body.find("div", class_="card-text-ability")
    if not div:
        return {"exists": False, "name": None, "effect": None}
    return {
        "exists": True,
        "name": clean_text(div.find("p", class_="card-text-ability-info").text.replace("Ability:", "")),
        "effect": clean_text(div.find("p", class_="card-text-ability-effect").text),
    }


def _parse_attacks(body):
    r"""_parse_attacks(body) -> dict

    Keys ``"1"`` and ``"2"``, each
    ``{"cost", "name", "damage", "effect"}``. Slots a card does not use
    stay filled with None. Only the first two attacks are kept.
    """
    attacks = {str(n): {"cost": None, "name": None, "damage": None, "effect": None} for n in (1, 2)}
    for i, atk_div in enumerate(body.find_all("div", class_="card-text-attack")[:2]):
        info_p = atk_div.find("p", class_="card-text-attack-info")
        cost_span = info_p.find("span", class_="ptcg-symbol")
        cost = cost_span.text.strip() if cost_span else None
        info_text = clean_text(info_p.text.replace(cost or "", "", 1))
        dmg_match = re.search(r"(\d[\d+\-xX×]*)$", info_text)
        dmg_raw = dmg_match.group(1) if dmg_match else ""
        effect_p = atk_div.find("p", class_="card-text-attack-effect")
        attacks[str(i + 1)] = {
            "cost": cost or None,
            "name": (clean_text(info_text[: info_text.rfind(dmg_raw)]) if dmg_raw else info_text) or None,
            "damage": to_int(dmg_raw),
            "effect": (clean_text(effect_p.text) if effect_p else None) or None,
        }
    return attacks


def extract_card(soup, set_profile):
    r"""extract_card(soup, set_profile) -> dict

    Parse a single card page and return a dictionary with every card
    attribute needed for the output JSON.

    The function reads the ``card-text`` div for name, HP, energy type,
    attacks, ability, and flavour text. It reads the rarity table for
    the current print's rarity and any alternate versions. It reads the
    ``card-prints-current`` div for the pack the card appears in. For
    Pokemon cards it also extracts stage, evolution source, retreat
    cost, and weakness from the type line and raw body text.

    For trainer cards, ``hp``, ``stage``, ``evolves_from``, ``retreat``,
    and ``weakness`` are all None. The ``card_text`` field holds the
    trainer's effect text; for Pokemon this is None.

    Fossil items (Item subtype cards whose name ends in "Fossil") are the
    exception: they are playable as a 40-HP Basic Colourless Pokemon, so
    they carry ``hp`` 40, ``points`` 1 and ``stage`` "Basic". ``type``
    stays "Trainer" and ``subtype`` stays "Item".

    Args:
        soup (BeautifulSoup): parsed HTML of the card page
        set_profile (SetProfile): the set this card belongs to.
            Supplies the promo test used to resolve pack keywords

    Returns:
        dict: card data with the following keys:

        - ``number`` (str): card number within the set
        - ``name`` (str): card name
        - ``hp`` (int or None): hit points, or None for other trainers
          (fossil items carry 40)
        - ``type`` (str): ``"Pokemon"`` or ``"Trainer"``
        - ``subtype`` (str or None): energy type for Pokemon,
          trainer subtype for trainers
        - ``card_text`` (str or None): trainer effect text,
          None for Pokemon
        - ``flavour_text`` (str or None): flavour text if present
        - ``image`` (str or None): URL of the card image
        - ``rarity`` (str or None): rarity symbol of the current print
        - ``alternate_versions`` (list of dict): other prints of this
          card. Each dict has ``set_code``, ``set_name``, ``id``,
          and ``rarity``.
        - ``ex`` (bool): whether the card is a Pokemon ex
        - ``mega`` (bool): whether the card is a Mega Evolution
        - ``points`` (int or None): prize points when knocked out
          (1, 2, or 3). None for other trainers; fossil items award 1.
        - ``pack`` (str): pack the card appears in
        - ``artist`` (str or None): illustrator name
        - ``stage`` (str or None): ``"Basic"``, ``"Stage 1"``,
          ``"Stage 2"``, or None for other trainers. Fossil items are
          ``"Basic"``.
        - ``evolves_from`` (str or None): name of the pre-evolution
        - ``retreat`` (int or None): retreat cost, None for trainers
        - ``weakness`` (str or None): weakness type, None for trainers
        - ``ability`` (dict): ``{"exists": bool, "name": str or None,
          "effect": str or None}``
        - ``attacks`` (dict): keys ``"1"`` and ``"2"``, each mapping
          to ``{"cost": str or None, "name": str or None,
          "damage": int or None, "effect": str or None}``
        - ``raw_text`` (str): full text of the card body. Used later
          by :func:`transform_cards` to detect parallel foil prints.

    .. note::

        The ``attacks`` dict always has both ``"1"`` and ``"2"`` keys.
        If a card has only one attack, the second entry stays filled
        with None values.

    .. note::

        Called on the soup for ``https://pocket.limitlesstcg.com/cards/a1/1``.
    """
    body = soup.find("div", class_="card-text")
    card_number, name, energy_type, hp_text = _parse_title(body)

    type_text_raw = body.find("p", class_="card-text-type").get_text(" ", strip=True)
    is_trainer = type_text_raw.startswith("Trainer")
    is_fossil = is_trainer and is_playable_trainer(name)

    # card body only: identical between a print and its parallel foil, unlike the full page
    raw_text = clean_text(body.get_text(" ", strip=True))

    # Trainer effect text = the section right after the title section
    card_text = None
    if is_trainer:
        sections = body.find_all("div", class_="card-text-section", recursive=False)
        if len(sections) > 1 and sections[1].get("class") == ["card-text-section"]:
            card_text = clean_text(sections[1].get_text(" ", strip=True))

    flavour_div = body.find("div", class_="card-text-flavor")
    image_div = soup.find("div", class_="card-image")
    artist_div = body.find("div", class_="card-text-artist")

    rarity, alt_versions = _parse_prints(soup, set_profile.code)
    stage, evolves_from, retreat, weakness = (
        (None, None, None, None) if is_trainer else _parse_pokemon_stats(type_text_raw, raw_text))
    if is_fossil:
        stage = "Basic"
        weakness = "none"

    ex = "ex" in name.split(" ")
    mega = not is_trainer and bool(
        name.startswith("Mega ") or re.search(r"Mega Evolution\s*e\s*x\s*rule", raw_text))

    # Dual-type Pokemon print both types on the title line ("Water/Darkness").
    # subtype_2 carries the second type; trainers never have one.
    subtype_2 = None
    if not is_trainer and energy_type and "/" in energy_type:
        energy_type, subtype_2 = (part.strip() for part in energy_type.split("/", 1))

    return {
        "number": card_number,
        "name": name,
        "hp": 40 if is_fossil else None if is_trainer else to_int(hp_text),
        "type": "Trainer" if is_trainer else "Pokémon",
        "subtype": parse_trainer_subtype(type_text_raw) if is_trainer else energy_type,
        "subtype_2": subtype_2,
        "card_text": card_text,
        "flavour_text": clean_text(flavour_div.text) if flavour_div else None,
        "image": image_div.find("img")["src"] if image_div and image_div.find("img") else None,
        "rarity": rarity,
        "alternate_versions": alt_versions,
        "ex": ex,
        "mega": mega,
        "points": 1 if is_fossil else None if is_trainer else (3 if mega and ex else 2 if ex else 1),
        "pack": _parse_pack(soup, set_profile),
        "artist": clean_text(artist_div.find("a").text) if artist_div and artist_div.find("a") else None,
        "stage": stage,
        "evolves_from": evolves_from,
        "retreat": retreat,
        "weakness": weakness,
        "ability": _parse_ability(body),
        "attacks": _parse_attacks(body),
        "raw_text": raw_text,
    }


def scrape_cards(set_profile):
    r"""scrape_cards(set_profile) -> list of dict

    Scrape every card in a set by requesting sequential card numbers
    starting at 1. Stops after ``MAX_CONSECUTIVE_ERRORS`` cards in a
    row return 404, which signals the end of the set.

    Only 404s count toward that limit. Any other failure (network
    error that outlived the retries, or a parse error on a page whose
    markup changed) raises ``RuntimeError`` immediately rather than
    being skipped, because a skipped card leaves a silent hole in the
    set while the run still exits successfully.

    Each successfully scraped card is the dict returned by
    :func:`extract_card`. Cards are returned in card-number order.

    Args:
        set_profile (SetProfile): the set to scrape

    Returns:
        list of dict: one card dict per card found, in ascending
        card-number order

    Raises:
        RuntimeError: if a card page fails for any reason other than
            a 404. The message includes the card number and set code.

    .. note::

        ``scrape_cards(SetProfile.of("a1"))`` returns 286 cards, the first named ``"Bulbasaur"``.
    """
    cards, errors, i = [], 0, 0
    with tqdm(desc=f"Scraping {set_profile.code}", unit=" cards") as pbar:
        while errors < MAX_CONSECUTIVE_ERRORS:
            i += 1
            try:
                cards.append(extract_card(fetch_page(f"{BASE_URL}{set_profile.code}/{i}"), set_profile))
                errors = 0
                pbar.update(1)
                time.sleep(RATE_LIMIT_DELAY)
            except NotFound:
                errors += 1
            except Exception as e:
                raise RuntimeError(
                    f"Failed to scrape card {i} of set {set_profile.code}: {type(e).__name__}: {e}"
                ) from e
    return cards