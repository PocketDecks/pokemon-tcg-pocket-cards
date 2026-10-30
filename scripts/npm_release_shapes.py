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
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License v3.0 for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
r"""The checked-in list of child package shapes allowed to publish.

Starts empty: the parent is the only publish candidate until a shape has
been bootstrapped and its trusted-publisher relationship validated. Edit
this file by hand, one shape per element, never via a glob or a workflow
expression.
"""

import json
from pathlib import Path

SHAPES_FILE = Path(__file__).resolve().parent / "npm_release_shapes.json"
KNOWN_SHAPES = ("core", "gameplay", "collection", "full")


def enabled_shapes():
    """Return the enabled child shapes as an ordered tuple.

    Raises:
        ValueError: the file lists an unknown shape or a duplicate
    """
    shapes = tuple(json.loads(SHAPES_FILE.read_text(encoding="utf-8")))
    unknown = [s for s in shapes if s not in KNOWN_SHAPES]
    if unknown:
        raise ValueError(f"unknown shape(s) in {SHAPES_FILE.name}: {unknown}")
    if len(set(shapes)) != len(shapes):
        raise ValueError(f"duplicate shape(s) in {SHAPES_FILE.name}")
    return shapes
