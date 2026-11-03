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
r"""Pack the enabled child shapes and gate them behind content checks.

``build_artifacts`` packs each staging directory with the real ``npm
pack``, records tarball/integrity/version facts in a manifest, and is
the only place release artifacts are created. ``verify_manifest`` opens
the packed tarballs and checks them against the staging directories:
exact member inventory, licence notices, metadata and byte-identical
payloads. Both are local-only; neither talks to the registry.
"""

import base64
import hashlib
import json
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

NPM = shutil.which("npm") or "npm"
EXPECTED_PACKAGE_NAMES = {
    "parent": "pokemon-tcg-pocket-cards",
    "core": "pokemon-tcg-pocket-cards-core",
    "gameplay": "pokemon-tcg-pocket-cards-gameplay",
    "collection": "pokemon-tcg-pocket-cards-collection",
    "full": "pokemon-tcg-pocket-cards-full",
}


def _validate_manifest_packages(packages, version):
    seen = set()
    for package in packages:
        shape = package.get("shape")
        expected_name = EXPECTED_PACKAGE_NAMES.get(shape)
        if expected_name is None:
            raise AssertionError(f"unknown package shape {shape!r}")
        if shape in seen:
            raise AssertionError(f"duplicate package shape {shape!r}")
        seen.add(shape)
        if package.get("name") != expected_name:
            raise AssertionError(
                f"{shape}: manifest name {package.get('name')!r} does not match {expected_name!r}")
        if package.get("version") != version:
            raise AssertionError(
                f"{shape}: manifest version {package.get('version')!r} does not match {version!r}")


def _run(cmd, cwd=None):
    if cmd and cmd[0] == "npm":
        cmd = [NPM, *cmd[1:]]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"command failed ({result.returncode}): {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def _integrity(path):
    digest = hashlib.sha512(Path(path).read_bytes()).digest()
    return "sha512-" + base64.b64encode(digest).decode()


def _pack_info(stdout):
    packed = json.loads(stdout)
    if isinstance(packed, list):
        if len(packed) != 1:
            raise ValueError("npm pack returned an unexpected package count")
        return packed[0]
    if isinstance(packed, dict) and len(packed) == 1:
        return next(iter(packed.values()))
    raise ValueError("npm pack returned an unexpected JSON shape")


def _pack_package(root, shape, version, out_dir):
    stdout = _run(["npm", "pack", "--json", "./"], cwd=str(root))
    info = _pack_info(stdout)
    if info["version"] != version:
        raise AssertionError(
            f"{shape}: staged package version {info['version']!r} does not "
            f"match the release version {version!r}; rejecting stale package")
    tarball = Path(out_dir) / Path(info["filename"]).name
    source = Path(root) / info["filename"]
    shutil.move(str(source), tarball)
    if info["integrity"] != _integrity(tarball):
        raise AssertionError(f"{shape}: npm pack integrity does not match the packed file")
    return {
        "shape": shape,
        "name": info["name"],
        "version": info["version"],
        "tarball": tarball.name,
        "integrity": info["integrity"],
    }


def build_artifacts(staging_root, shapes, version, commit, out_dir, parent_root=None):
    """Pack release packages and write the manifest."""
    staging_root, out_dir = Path(staging_root), Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    packages = []
    if parent_root is not None:
        packages.append(_pack_package(parent_root, "parent", version, out_dir))
    for shape in shapes:
        staging = staging_root / shape
        if not staging.is_dir():
            raise FileNotFoundError(f"no staging directory for shape {shape!r}: {staging}")
        packages.append(_pack_package(staging, shape, version, out_dir))
    manifest = {"version": version, "commit": commit, "packages": packages}
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _check(condition, message, failures):
    if not condition:
        failures.append(message)


def _export_targets(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _export_targets(child)


def _export_exists(package, target):
    target_path = target.removeprefix("./")
    if "*" in target_path:
        return any(package.glob(target_path))
    return (package / target_path).is_file()


def _check_exports(package, metadata, name):
    failures = []
    for target in _export_targets(metadata.get("exports", {})):
        _check(_export_exists(package, target),
               f"{name}: export target {target} missing from tarball", failures)
    return failures


def verify_manifest(manifest_path, staging_root, parent_root=None):
    """Verify every packed tarball named in the manifest.

    A child package must hold exactly the members its staging directory
    holds, byte for byte; a parent package (no staging dir) must hold
    every fixed export target its ``package.json`` declares plus the
    licence notices. Verification is read-only and raises on the first
    defect.

    Args:
        manifest_path (Path): the manifest written by :func:`build_artifacts`
        staging_root (Path | None): staging dirs to compare children
            against; ``None`` skips per-shape comparisons

    Raises:
        AssertionError: naming the first defect found
    """
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    _validate_manifest_packages(manifest["packages"], manifest["version"])
    manifest_root = Path(manifest_path).resolve().parent
    for pkg in manifest["packages"]:
        tarball = Path(pkg["tarball"])
        if not tarball.is_absolute():
            tarball = manifest_root / tarball
        if _integrity(tarball) != pkg["integrity"]:
            raise AssertionError(f"{pkg['name']}: retained integrity does not match the tarball")
        expected_root = (
            Path(staging_root) / pkg["shape"]
            if staging_root and pkg["shape"] != "parent" else None
        )
        if staging_root and expected_root is not None and not expected_root.is_dir():
            raise AssertionError(
                f"{pkg['name']}: no staging directory to verify against: {expected_root}")
        with tempfile.TemporaryDirectory() as tmp:
            extract = Path(tmp)
            with tarfile.open(tarball) as tar:
                tar.extractall(extract, filter="data")
            package = extract / "package"
            if expected_root is not None:
                staged_files = {p.relative_to(expected_root).as_posix()
                                for p in expected_root.rglob("*") if p.is_file()}
                packed_files = {p.relative_to(package).as_posix()
                                for p in package.rglob("*") if p.is_file()}
                if packed_files != staged_files:
                    raise AssertionError(
                        f"{pkg['name']}: packed inventory differs from staging; "
                        f"missing={sorted(staged_files - packed_files)} "
                        f"extra={sorted(packed_files - staged_files)}")
                for rel in sorted(staged_files):
                    if (package / rel).read_bytes() != (expected_root / rel).read_bytes():
                        raise AssertionError(f"{pkg['name']}: payload byte mismatch at {rel}")
            if pkg["shape"] == "parent" and parent_root is not None:
                source_root = Path(parent_root)
                expected_files = {p.relative_to(source_root).as_posix()
                                  for p in source_root.rglob("*") if p.is_file()}
                packed_files = {p.relative_to(package).as_posix()
                                for p in package.rglob("*") if p.is_file()}
                if packed_files != expected_files:
                    raise AssertionError(
                        f"{pkg['name']}: parent inventory differs from source; "
                        f"missing={sorted(expected_files - packed_files)} "
                        f"extra={sorted(packed_files - expected_files)}")
                for rel in sorted(expected_files):
                    if (package / rel).read_bytes() != (source_root / rel).read_bytes():
                        raise AssertionError(f"{pkg['name']}: parent byte mismatch at {rel}")
            meta = json.loads((package / "package.json").read_text(encoding="utf-8"))
            failures = _check_exports(package, meta, pkg["name"])
            required_notices = ("LICENSE", "README.md")
            if pkg["shape"] != "parent":
                required_notices += ("LICENSE-MIT",)
            for notice in required_notices:
                _check((package / notice).is_file(), f"{pkg['name']}: missing {notice}", failures)
            if failures:
                raise AssertionError("; ".join(failures))


def main(argv=None):
    import argparse

    from npm_release_shapes import enabled_shapes

    parser = argparse.ArgumentParser(
        description="Pack, manifest and verify the enabled child packages")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="pack the enabled shapes and verify them")
    build.add_argument("--version", required=True)
    build.add_argument("--staging", required=True,
                       help="staging root produced by build_packages.py")
    build.add_argument("--out", required=True, help="artifact output directory")
    build.add_argument("--commit", required=True,
                       help="immutable source commit recorded in the manifest")
    build.add_argument("--parent", default=None,
                       help="parent package root to pack alongside child shapes")

    verify = sub.add_parser("verify", help="verify artifacts against an existing manifest")
    verify.add_argument("--manifest", required=True)
    verify.add_argument("--staging", required=True)

    args = parser.parse_args(argv)
    if args.command == "build":
        shapes = enabled_shapes()
        manifest = build_artifacts(args.staging, shapes, args.version,
                                   args.commit, args.out, parent_root=args.parent)
        verify_manifest(Path(args.out) / "manifest.json", staging_root=args.staging,
                        parent_root=args.parent)
        print(f"verified {len(manifest['packages'])} package(s); "
              f"manifest at {Path(args.out) / 'manifest.json'}")
    else:
        verify_manifest(args.manifest, staging_root=args.staging)
        print("artifacts verified")


if __name__ == "__main__":
    main()
