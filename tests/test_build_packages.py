"""Tests for the per-shape npm staging-dir builder.

The builder stages one payload shape per child package under /build:
its base payload, the no-image twin, the four expansions files, and
metadata/licence notices. No test here touches the network or the npm
registry; everything runs against the committed dataset.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from build_packages import SHAPES, build_package

EXPECTED = {
    "core": ("cards.core", "cards.core.no-image"),
    "gameplay": ("cards.gameplay", "cards.gameplay.no-image"),
    "collection": ("cards.collection", "cards.collection.no-image"),
    "full": ("cards", "cards.no-image"),
}

V5 = Path(__file__).resolve().parents[1] / "data" / "v5"

CORE_STAGING = {
    "package.json",
    "README.md",
    "LICENSE",
    "LICENSE-MIT",
    "data/v5/cards.core.min.json",
    "data/v5/cards.core.d.ts",
    "data/v5/cards.core-wrapper.d.ts",
    "data/v5/cards.core.schema.json",
    "data/v5/cards.core.no-image.min.json",
    "data/v5/cards.core.no-image.d.ts",
    "data/v5/cards.core.no-image-wrapper.d.ts",
    "data/v5/cards.core.no-image.schema.json",
    "data/v5/expansions.min.json",
    "data/v5/expansions.d.ts",
    "data/v5/expansions-wrapper.d.ts",
    "data/v5/expansions.schema.json",
}


def staging_files(root):
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def test_every_shape_has_the_declared_bases():
    assert SHAPES == EXPECTED


def test_staging_dir_holds_exactly_the_payload_set(tmp_path):
    root = build_package("core", "1.2.3", tmp_path)
    assert staging_files(root) == CORE_STAGING


def test_exports_resolve_to_files_on_disk(tmp_path):
    for shape, (base, no_image) in SHAPES.items():
        root = build_package(shape, "1.2.3", tmp_path)
        pkg = json.loads((root / "package.json").read_text(encoding="utf-8"))
        assert pkg["name"] == f"pokemon-tcg-pocket-cards-{shape}"
        assert pkg["version"] == "1.2.3"
        assert pkg["files"] == ["data", "LICENSE", "LICENSE-MIT", "README.md"]
        assert pkg["license"] == "AGPL-3.0-or-later"
        assert pkg["repository"]["url"] == (
            "git+https://github.com/PocketDecks/pokemon-tcg-pocket-cards.git")
        assert pkg["author"]
        for subpath in (".", "./no-image", "./expansions"):
            entry = pkg["exports"][subpath]
            assert list(entry) == ["types", "default"]
            for target in entry.values():
                assert target.startswith("./data/v5/")
                assert (root / target).is_file(), f"{shape}: missing {target}"


def test_payload_copies_are_byte_identical(tmp_path):
    for shape, (base, no_image) in SHAPES.items():
        root = build_package(shape, "1.2.3", tmp_path)
        for name in (base, no_image, "expansions"):
            for suffix in (".min.json", ".d.ts", "-wrapper.d.ts", ".schema.json"):
                src = V5 / f"{name}{suffix}"
                assert (root / "data" / "v5" / f"{name}{suffix}").read_bytes() == src.read_bytes()


def test_export_targets_point_at_the_right_payloads(tmp_path):
    for shape, (base, no_image) in SHAPES.items():
        pkg = json.loads((build_package(shape, "1.2.3", tmp_path) / "package.json").read_text(encoding="utf-8"))
        assert pkg["exports"]["."]["default"] == f"./data/v5/{base}.min.json"
        assert pkg["exports"]["."]["types"] == f"./data/v5/{base}-wrapper.d.ts"
        assert pkg["exports"]["./no-image"]["default"] == f"./data/v5/{no_image}.min.json"
        assert pkg["exports"]["./expansions"]["default"] == "./data/v5/expansions.min.json"
        assert pkg["main"] == f"./data/v5/{base}.min.json"
        assert pkg["types"] == f"./data/v5/{base}-wrapper.d.ts"


def test_wrapper_dependencies_reference_the_sibling_declaration(tmp_path):
    for shape, (base, _) in SHAPES.items():
        root = build_package(shape, "1.2.3", tmp_path)
        wrapper = (root / "data" / "v5" / f"{base}-wrapper.d.ts").read_text(encoding="utf-8")
        assert f"./{base}" in wrapper


def test_missing_source_fails_without_a_partial_output(tmp_path, monkeypatch):
    import build_packages
    monkeypatch.setattr(
        build_packages, "v5_file",
        lambda name, suffix: (V5 / "missing.json" if name == "cards.core.no-image"
                              else V5 / f"{name}{suffix}"))
    with pytest.raises(FileNotFoundError, match="cards.core.no-image"):
        build_package("core", "1.2.3", tmp_path)
    assert not (tmp_path / "core").exists()
    assert not list(tmp_path.glob(".core-*"))


def test_rebuild_replaces_output_without_stale_files(tmp_path):
    root = build_package("core", "1.2.3", tmp_path)
    stale = root / "data" / "v5" / "stale.json"
    stale.write_text("{}", encoding="utf-8")
    root = build_package("core", "1.2.4", tmp_path)
    assert not stale.exists()
    assert pkg_version(root) == "1.2.4"
    assert staging_files(root) == CORE_STAGING


def pkg_version(root):
    return json.loads((root / "package.json").read_text(encoding="utf-8"))["version"]


def test_invalid_shape_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="unknown shape"):
        build_package("bogus", "1.2.3", tmp_path)


def test_invalid_version_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="version"):
        build_package("core", "not-semver", tmp_path)


@pytest.mark.parametrize("bad", ["01.2.3", "1.02.3", "1.2.3-alpha..1", "1.2.3+"])
def test_versions_with_leading_zeros_or_empty_idents_are_rejected(bad, tmp_path):
    with pytest.raises(ValueError, match="version"):
        build_package("core", bad, tmp_path)


@pytest.mark.parametrize("good", ["0.0.0", "1.2.3+c1", "1.2.3-alpha.1", "10.20.30"])
def test_valid_semver_including_build_metadata_is_accepted(good, tmp_path):
    assert build_package("core", good, tmp_path).name == "core"


def test_only_flag_selects_shapes(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_packages.py"
    result = subprocess.run(
        [sys.executable, str(script), "--version", "5.5.0+c1",
         "--out", str(tmp_path / "pkg"), "--only", "core"],
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    built = {p.name for p in (tmp_path / "pkg").iterdir()}
    assert built == {"core"}


def test_cli_rejects_a_missing_version():
    script = Path(__file__).resolve().parents[1] / "scripts" / "build_packages.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode != 0
