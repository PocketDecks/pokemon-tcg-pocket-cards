"""Tests for the packed-artifact gate and the manifest-driven publisher.

Nothing here touches the live npm registry: tarballs are packed with the
real ``npm pack`` from local staging dirs, and publish calls run through
an injected fake runner.
"""
import base64
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

from build_packages import build_package
from npm_release_shapes import enabled_shapes
from publish_packages import PublishPlan, plan_from_manifest
from verify_package_artifacts import build_artifacts, verify_manifest

@pytest.fixture(scope="module")
def staged(tmp_path_factory):
    root = tmp_path_factory.mktemp("staging")
    for shape in ("core", "full"):
        build_package(shape, "5.5.0+c1", root)
    return root


@pytest.fixture(scope="module")
def artifacts(staged, tmp_path_factory):
    out = tmp_path_factory.mktemp("artifacts")
    manifest = build_artifacts(staged, ["core", "full"], "5.5.0+c1", "abc123", out)
    return out, manifest, staged


def test_enabled_shapes_file_ships_empty():
    assert list(enabled_shapes()) == []


def test_build_artifacts_packs_the_enabled_shapes(artifacts):
    out, manifest, _ = artifacts
    names = {p["name"] for p in manifest["packages"]}
    assert names == {"pokemon-tcg-pocket-cards-core", "pokemon-tcg-pocket-cards-full"}
    for pkg in manifest["packages"]:
        assert Path(pkg["tarball"]).is_file()
        assert pkg["integrity"].startswith("sha512-")
        assert pkg["version"] == "5.5.0+c1"
    assert manifest["version"] == "5.5.0+c1"
    assert manifest["commit"] == "abc123"


def test_verify_manifest_accepts_good_artifacts(artifacts):
    out, manifest, staged = artifacts
    verify_manifest(out / "manifest.json", staging_root=staged)


def _repacked_from(tarball, tmp_path, drop=None, mutate=None):
    """Rebuild a tarball from its own contents, optionally dropping a
    member or mutating a JSON payload. Returns the new tarball path."""
    extract = tmp_path / "extract"
    with tarfile.open(tarball) as tar:
        tar.extractall(extract, filter="data")
    package = extract / "package"
    if drop:
        (package / drop).unlink()
    if mutate:
        target = package / mutate
        data = json.loads(target.read_text(encoding="utf-8"))
        data[0]["name"] = "Tamperedmon"
        target.write_text(json.dumps(data), encoding="utf-8")
    new = tmp_path / "repacked.tgz"
    with tarfile.open(new, "w:gz") as tar:
        tar.add(package, arcname="package")
    return new


def test_verify_detects_a_missing_tar_member(artifacts, tmp_path):
    out, manifest, staged = artifacts
    manifest = json.loads(json.dumps(manifest))
    pkg = next(p for p in manifest["packages"] if p["shape"] == "core")
    pkg["tarball"] = str(_repacked_from(pkg["tarball"], tmp_path, drop="LICENSE-MIT"))
    pkg["integrity"] = integrity_of(pkg["tarball"])
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AssertionError, match="LICENSE-MIT"):
        verify_manifest(manifest_path, staging_root=staged)


def test_verify_detects_corrupt_payload_bytes(artifacts, tmp_path):
    out, manifest, staged = artifacts
    manifest = json.loads(json.dumps(manifest))
    pkg = next(p for p in manifest["packages"] if p["shape"] == "core")
    pkg["tarball"] = str(_repacked_from(
        pkg["tarball"], tmp_path, mutate="data/v5/cards.core.min.json"))
    pkg["integrity"] = integrity_of(pkg["tarball"])
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(AssertionError, match="byte"):
        verify_manifest(manifest_path, staging_root=staged)


class FakeRunner:
    def __init__(self, view_results=None):
        self.calls = []
        self.view_results = view_results or {}

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        if cmd[:2] == ["npm", "view"]:
            spec = cmd[2]
            if spec not in self.view_results:
                # npm exits 1 with E404 for an absent name@version
                raise subprocess.CalledProcessError(1, cmd, output="npm error code E404")
            value = self.view_results[spec]
            if value == "ERR":
                raise subprocess.CalledProcessError(1, cmd, output="npm error ECONNRESET")
            return value
        return ""

    def run(self, cmd, **kwargs):
        return self(cmd, **kwargs)


def integrity_of(path):
    digest = hashlib.sha512(Path(path).read_bytes()).digest()
    return "sha512-" + base64.b64encode(digest).decode()


def write_manifest(path, packages, version="5.5.0+c1", commit="abc123"):
    manifest = {"version": version, "commit": commit, "packages": packages}
    Path(path).write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


def two_package_manifest(tmp_path):
    parent = tmp_path / "parent.tgz"
    child = tmp_path / "child.tgz"
    parent.write_bytes(b"p")
    child.write_bytes(b"c")
    manifest = write_manifest(tmp_path / "manifest.json", [
        {"shape": "core", "name": "pkg-core", "version": "5.5.0+c1",
         "tarball": str(child), "integrity": integrity_of(child)},
        {"shape": "parent", "name": "pkg-parent", "version": "5.5.0+c1",
         "tarball": str(parent), "integrity": integrity_of(parent)},
    ])
    return manifest, parent, child


def test_publisher_plans_parent_first_and_needs_execute(tmp_path):
    manifest, parent, child = two_package_manifest(tmp_path)
    plan = plan_from_manifest(manifest)
    assert [p["name"] for p in plan.entries] == ["pkg-parent", "pkg-core"]

    runner = FakeRunner()
    PublishPlan(plan, runner=runner).run(execute=False)
    assert not any("publish" in c for c in runner.calls)


def test_publisher_publishes_missing_and_skips_matching_existing(tmp_path):
    manifest, parent, child = two_package_manifest(tmp_path)
    runner = FakeRunner(view_results={"pkg-core@5.5.0+c1": integrity_of(child)})
    PublishPlan(plan_from_manifest(manifest), runner=runner).run(execute=True, recovery=True)
    published = [c for c in runner.calls if c[:2] == ["npm", "publish"]]
    assert len(published) == 1 and str(parent) in published[0] and str(child) not in published[0]


def test_publisher_aborts_on_integrity_mismatch(tmp_path):
    manifest, parent, child = two_package_manifest(tmp_path)
    runner = FakeRunner(view_results={"pkg-core@5.5.0+c1": "sha512-DIFFERENT"})
    with pytest.raises(AssertionError, match="integrity"):
        PublishPlan(plan_from_manifest(manifest), runner=runner).run(execute=True, recovery=True)
    published = [c for c in runner.calls if c[:2] == ["npm", "publish"]]
    assert len(published) == 1 and str(parent) in published[0] and str(child) not in published[0]


def test_publisher_aborts_on_registry_lookup_failure(tmp_path):
    manifest, parent, child = two_package_manifest(tmp_path)
    runner = FakeRunner(view_results={"pkg-core@5.5.0+c1": "ERR"})
    with pytest.raises(RuntimeError, match="lookup"):
        PublishPlan(plan_from_manifest(manifest), runner=runner).run(execute=True, recovery=True)
    published = [c for c in runner.calls if c[:2] == ["npm", "publish"]]
    assert len(published) == 1 and str(parent) in published[0] and str(child) not in published[0]


def test_publisher_stops_after_the_first_failure(tmp_path):
    manifest, parent, child = two_package_manifest(tmp_path)
    calls = []

    def failing_runner(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:2] == ["npm", "publish"] and str(parent) in cmd:
            raise subprocess.CalledProcessError(1, cmd)
        return ""

    manifest = write_manifest(tmp_path / "manifest.json", [
        {"shape": "parent", "name": "pkg-parent", "version": "5.5.0+c1",
         "tarball": str(parent), "integrity": integrity_of(parent)},
        {"shape": "core", "name": "pkg-core", "version": "5.5.0+c1",
         "tarball": str(child), "integrity": integrity_of(child)},
    ])
    with pytest.raises(subprocess.CalledProcessError):
        PublishPlan(plan_from_manifest(manifest), runner=failing_runner).run(execute=True)
    published = [c for c in calls if c[:2] == ["npm", "publish"]]
    assert len(published) == 1 and str(parent) in published[0] and str(child) not in published[0]


def test_publisher_verifies_retained_integrity_before_publishing(tmp_path):
    manifest, parent, child = two_package_manifest(tmp_path)
    bad = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    bad["packages"][1]["integrity"] = "sha512-WRONG"
    runner = FakeRunner()
    with pytest.raises(AssertionError, match="integrity"):
        PublishPlan(plan_from_manifest(bad), runner=runner).run(execute=True)
    assert not any("publish" in c for c in runner.calls)
