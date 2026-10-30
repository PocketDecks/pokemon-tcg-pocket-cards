"""Runtime contract of an installed child-package tarball.

Packs a real staging dir, installs the tarball into an isolated
consumer prefix without any publish credentials, and exercises the
three subpaths (root, ./no-image, ./expansions) through Node's require.
Record counts come from the source payload, never hard-coded.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from build_packages import build_package
from verify_package_artifacts import build_artifacts

REPO = Path(__file__).resolve().parents[1]
V5 = REPO / "data" / "v5"
NODE = shutil.which("node") or "node"
NPM = shutil.which("npm") or "npm"


def npm(*args, cwd=None):
    result = subprocess.run([NPM, *args], cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result


@pytest.fixture(scope="module")
def tarball(tmp_path_factory):
    staging = tmp_path_factory.mktemp("staging")
    build_package("core", "5.5.0+c1", staging)
    out = tmp_path_factory.mktemp("artifacts")
    manifest = build_artifacts(staging, ["core"], "5.5.0+c1", "test", out)
    return Path(manifest["packages"][0]["tarball"])


def _require(consumer, entry):
    script = (
        "const {createRequire} = require('module');\n"
        f"const req = createRequire({json.dumps(str(consumer / 'index.js'))});\n"
        f"const data = req({json.dumps(entry)});\n"
        "console.log(Array.isArray(data), data.length);\n")
    result = subprocess.run([NODE, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    flag, count = result.stdout.split()
    assert flag.lower() == "true"
    return int(count)


def test_installed_tarball_serves_all_three_subpaths(tarball, tmp_path):
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    npm("install", str(tarball), "--prefix", str(consumer),
        "--no-audit", "--no-fund")
    pkg_root = consumer / "node_modules" / "pokemon-tcg-pocket-cards-core"
    assert (pkg_root / "data" / "v5" / "cards.core.min.json").is_file()

    source_core = len(json.loads((V5 / "cards.core.min.json").read_text(encoding="utf-8")))
    source_no_image = len(json.loads(
        (V5 / "cards.core.no-image.min.json").read_text(encoding="utf-8")))
    source_expansions = len(json.loads(
        (V5 / "expansions.min.json").read_text(encoding="utf-8")))

    assert _require(pkg_root, "pokemon-tcg-pocket-cards-core") == source_core
    assert _require(pkg_root, "pokemon-tcg-pocket-cards-core/no-image") == source_no_image
    assert _require(pkg_root, "pokemon-tcg-pocket-cards-core/expansions") == source_expansions
