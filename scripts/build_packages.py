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
r"""Stage one v5 payload shape as a self-contained npm package directory.

Each shape becomes a child package under ``build/pkg/<shape>/`` carrying
its base payload, the no-image twin, the four expansions files, and the
metadata/licence notices. ``data/`` is read-only input; every generated
byte lands under ``/build``, which the repository ignores.

Usage::

    python scripts/build_packages.py --version 5.5.0+c1
    python scripts/build_packages.py --version 5.5.0+c1 --only core --out build/pkg

Publishing is out of scope here: this script only stages directories for
the release pipeline to pack and verify.
"""

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
V5_DIR = REPO_ROOT / "data" / "v5"

SHAPES = {
    "core": ("cards.core", "cards.core.no-image"),
    "gameplay": ("cards.gameplay", "cards.gameplay.no-image"),
    "collection": ("cards.collection", "cards.collection.no-image"),
    "full": ("cards", "cards.no-image"),
}
SUFFIXES = (".min.json", ".d.ts", "-wrapper.d.ts", ".schema.json")
EXTRAS = ("expansions.min.json", "expansions.d.ts",
          "expansions-wrapper.d.ts", "expansions.schema.json")

SEMVER = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$")

DESCRIPTIONS = {
    "core": "Slim flat summary of every Pokémon TCG Pocket gameplay card",
    "gameplay": "Combat data for Pokémon TCG Pocket simulators: attacks, abilities and stats",
    "collection": "One record per printed Pokémon TCG Pocket card with derived trading fields",
    "full": "Every field of every printed Pokémon TCG Pocket card, images included",
}


def v5_file(name, suffix):
    """Return the source path for one payload file."""
    return V5_DIR / f"{name}{suffix}"


def _payload_pairs(shape):
    base, no_image = SHAPES[shape]
    pairs = []
    for name in (base, no_image):
        for suffix in SUFFIXES:
            pairs.append((v5_file(name, suffix), Path("data") / "v5" / f"{name}{suffix}"))
    for extra in EXTRAS:
        pairs.append((V5_DIR / extra, Path("data") / "v5" / extra))
    return pairs


def _package_json(shape, version):
    base, no_image = SHAPES[shape]
    return {
        "name": f"pokemon-tcg-pocket-cards-{shape}",
        "version": version,
        "description": DESCRIPTIONS[shape],
        "license": "AGPL-3.0-or-later",
        "author": "Leonid Dalin & Chase Manning",
        "repository": {
            "type": "git",
            "url": "git+https://github.com/PocketDecks/pokemon-tcg-pocket-cards.git",
        },
        "keywords": ["pokemon", "tcg", "pocket", "ptcgp", "database", "json", "api"],
        "files": ["data", "LICENSE", "LICENSE-MIT", "README.md"],
        "main": f"./data/v5/{base}.min.json",
        "types": f"./data/v5/{base}-wrapper.d.ts",
        "exports": {
            ".": {
                "types": f"./data/v5/{base}-wrapper.d.ts",
                "default": f"./data/v5/{base}.min.json",
            },
            "./no-image": {
                "types": f"./data/v5/{no_image}-wrapper.d.ts",
                "default": f"./data/v5/{no_image}.min.json",
            },
            "./expansions": {
                "types": "./data/v5/expansions-wrapper.d.ts",
                "default": "./data/v5/expansions.min.json",
            },
        },
    }


def build_package(shape, version, out_root, _pairs=None):
    r"""build_package(shape, version, out_root) -> Path

    Stage ``shape`` at ``version`` under ``<out_root>/<shape>/``. Builds
    in a temporary sibling and promotes only when every source file has
    been staged, so a missing payload file never leaves a partial
    package behind. Rebuilding a shape replaces its output without
    stale extra files.

    Args:
        shape (str): one of :data:`SHAPES`
        version (str): a semver version; build metadata is kept as-is
        out_root (Path): directory that receives the ``<shape>/`` folder

    Returns:
        Path: the promoted staging directory

    Raises:
        ValueError: unknown shape or invalid version
        FileNotFoundError: a source payload file is missing
    """
    if shape not in SHAPES:
        raise ValueError(f"unknown shape {shape!r}; expected one of {sorted(SHAPES)}")
    if not SEMVER.match(version):
        raise ValueError(f"invalid version {version!r}; expected semver")

    out_root = Path(out_root)
    final = out_root / shape
    if not str(final).startswith(str(Path(out_root))):
        raise ValueError("output path escapes the output root")
    pairs = _pairs if _pairs is not None else _payload_pairs(shape)

    missing = [f"{dest.as_posix()} ({src})" for src, dest in pairs if not src.is_file()]
    if missing:
        raise FileNotFoundError(f"missing source payload file(s): {', '.join(missing)}")

    out_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{shape}-", dir=out_root))
    try:
        for src, dest in pairs:
            target = staging / dest
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        (staging / "package.json").write_text(
            json.dumps(_package_json(shape, version), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        shutil.copyfile(REPO_ROOT / "README.md", staging / "README.md")
        shutil.copyfile(REPO_ROOT / "LICENSE", staging / "LICENSE")
        shutil.copyfile(REPO_ROOT / "LICENSE-MIT", staging / "LICENSE-MIT")
        if final.exists():
            shutil.rmtree(final)
        staging.rename(final)
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
    return final


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stage per-shape npm packages under build/pkg")
    parser.add_argument("--version", required=True,
                        help="package version, e.g. 5.5.0+c1")
    parser.add_argument("--out", default="build/pkg",
                        help="output directory (default: build/pkg)")
    parser.add_argument("--only", action="append", choices=sorted(SHAPES),
                        help="build only this shape; repeatable")
    args = parser.parse_args(argv)
    shapes = args.only if args.only else sorted(SHAPES)
    for shape in shapes:
        root = build_package(shape, args.version, Path(args.out))
        print(f"staged {root}")


if __name__ == "__main__":
    main(sys.argv[1:])
