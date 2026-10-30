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
r"""Publish verified release artifacts from the manifest, never a glob.

The parent goes first; children follow in enabled-shapes order. Every
run checks each retained tarball's sha512 against the manifest before
touching the registry. Recovery mode consults the registry for each
exact ``name@version``: a matching published version is skipped, a
mismatch aborts, and a lookup failure is a diagnostic stop, never
treated as "missing". Publication stops at the first error; nothing
falls back to a retry or a rebuild.
"""

import base64
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

NPM = shutil.which("npm") or "npm"


def run(cmd, **kwargs):
    """Execute one command, raising with its output on failure."""
    if cmd and cmd[0] == "npm":
        cmd = [NPM, *cmd[1:]]
    result = subprocess.run(cmd, capture_output=True, text=True, **kwargs)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(result.returncode, cmd, output=result.stderr)
    return result.stdout


def plan_from_manifest(manifest):
    """Return the publish plan: manifest entries, parent first.

    Args:
        manifest (dict): the release manifest written by
            :func:`verify_package_artifacts.build_artifacts`

    Returns:
        PublishPlan: entries ordered parent-first, children in list order
    """
    entries = list(manifest["packages"])
    entries.sort(key=lambda p: 0 if p["shape"] == "parent" else 1)
    return PublishPlan(entries, manifest=manifest)


class PublishPlan:
    """A ready-to-execute publish sequence over verified artifacts."""

    def __init__(self, entries, manifest=None, runner=run):
        if isinstance(entries, PublishPlan):
            entries = entries.entries
        self.entries = list(entries)
        self.manifest = manifest
        self._runner = runner

    def _retained_integrity_check(self):
        for entry in self.entries:
            path = Path(entry["tarball"])
            digest = hashlib.sha512(path.read_bytes()).digest()
            actual = "sha512-" + base64.b64encode(digest).decode()
            if actual != entry["integrity"]:
                raise AssertionError(
                    f"{entry['name']}: retained integrity does not match {entry['tarball']}")

    def _registry_integrity(self, name, version):
        spec = f"{name}@{version}"
        try:
            stdout = self._runner(["npm", "view", spec, "dist.integrity"])
        except subprocess.CalledProcessError as error:
            if "E404" in (error.stderr or error.output or ""):
                return None  # confirmed absent: eligible to publish
            raise RuntimeError(
                f"{spec}: registry lookup failed; this is not evidence the "
                "version is missing. Inspect auth/network before any retry") from error
        return stdout.strip().strip('"') or None

    def run(self, execute=False, recovery=False, provenance=True):
        """Publish the plan, or only print it when ``execute`` is false.

        Args:
            execute (bool): actually publish; without it the plan is dry
            recovery (bool): query the registry per entry and skip
                versions already published with matching integrity
            provenance (bool): pass ``--provenance`` to npm publish
        """
        self._retained_integrity_check()
        for entry in self.entries:
            spec = f"{entry['name']}@{entry['version']}"
            print(f"plan: {spec} <- {entry['tarball']}")
            if not execute:
                continue
            if recovery:
                registry = self._registry_integrity(entry["name"], entry["version"])
                if registry == entry["integrity"]:
                    print(f"skip: {spec} already published with matching integrity")
                    continue
                if registry:
                    raise AssertionError(
                        f"{spec}: registry integrity {registry} does not match the "
                        "retained tarball; refusing to publish or overwrite")
            cmd = ["npm", "publish", entry["tarball"], "--access", "public"]
            if provenance:
                cmd.append("--provenance")
            print(f"publishing {spec}")
            self._runner(cmd)


def main(argv=None):
    import argparse
    parser = argparse.ArgumentParser(
        description="Publish the manifest's verified tarballs, parent first")
    parser.add_argument("--manifest", required=True, help="path to manifest.json")
    parser.add_argument("--execute", action="store_true",
                        help="actually publish; omit for a dry plan")
    parser.add_argument("--recovery", action="store_true",
                        help="skip versions already published with matching integrity")
    parser.add_argument("--no-provenance", action="store_true",
                        help="omit --provenance (local diagnostics only)")
    args = parser.parse_args(argv)
    manifest = json.loads(Path(args.manifest).read_text(encoding="utf-8"))
    PublishPlan(plan_from_manifest(manifest).entries, manifest).run(
        execute=args.execute, recovery=args.recovery,
        provenance=not args.no_provenance)


if __name__ == "__main__":
    main()
