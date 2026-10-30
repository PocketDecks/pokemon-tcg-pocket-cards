"""Doc size claims must match the files that actually ship.

Every payload size stated in the prose docs is a claim about a file on
disk. Hand-maintained figures drifted three times in three files, so this
parses each claim and compares it with the real minified payload. A claim
either names the payload file it describes (``[the core payload](.../cards.core.min.json)``
followed by a figure) or sits in the payloads.md size table, whose rows
name the payload by label.
"""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
V5 = ROOT / "data" / "v5"

DOCS = [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md"))]

# Label as used in docs/payloads.md's table -> file it measures.
TABLE_LABELS = {
    "core": "cards.core.min.json",
    "core no-image": "cards.core.no-image.min.json",
    "gameplay": "cards.gameplay.min.json",
    "gameplay no-image": "cards.gameplay.no-image.min.json",
    "collection": "cards.collection.min.json",
    "collection no-image": "cards.collection.no-image.min.json",
    "full no-image": "cards.no-image.min.json",
    "full": "cards.min.json",
}

# Payload file named in a markdown link -> how the prose refers to it.
LINKED_PAYLOAD = re.compile(
    r"\[[^\]]*\]\([^)]*?cards(?:\.core|\.gameplay|\.collection)?(?:\.no-image)?\.min\.json\)(.*)$",
    re.MULTILINE)
MB = re.compile(r"([0-9]+\.[0-9]+)\s*MB")
# Rows of the payloads.md decision table: | ... | **core no-image** | `import` | ~1.14 MB |
TABLE_ROW = re.compile(
    r"^\|\s*[^|]*\|\s*\*\*([a-z][a-z -]*)\*\*\s*\|[^|]*\|\s*~?([0-9]+\.[0-9]+)\s*MB", re.MULTILINE)


def real_size(name):
    """Measured size in MB, to the precision the docs round to."""
    return round((V5 / name).stat().st_size / 1_000_000, 2)


def size_for_link(target):
    """Map a markdown link target to the payload file it names."""
    name = target.rsplit("/", 1)[-1]
    return name if (V5 / name).is_file() else None


def linked_claims(text):
    """Yield (label, claimed_mb) for each size stated after a payload link."""
    for match in LINKED_PAYLOAD.finditer(text):
        tail = match.group(1)
        claimed = MB.search(tail)
        if not claimed:
            continue
        target = re.search(r"\]\(([^)]+)\)", match.group(0)).group(1)
        name = size_for_link(target)
        if name:
            yield name, float(claimed.group(1))


def table_claims(text):
    """Yield (payload file, claimed MB) for each row of the decision table."""
    for line in text.splitlines():
        if not line.startswith("|") or "MB" not in line:
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        label = None
        value = None
        for cell in cells:
            bold = re.fullmatch(r"\*\*(.+?)\*\*", cell)
            if bold:
                label = bold.group(1).strip()
            size = re.fullmatch(r"~?([0-9]+\.[0-9]+)\s*MB", cell)
            if size:
                value = float(size.group(1))
        if label in TABLE_LABELS and value is not None:
            yield TABLE_LABELS[label], value


def test_every_doc_is_scanned():
    assert len(DOCS) >= 5


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_documented_payload_sizes_match_the_files(doc):
    text = doc.read_text(encoding="utf-8")
    claims = list(table_claims(text))
    if doc.name == "payloads.md":
        assert claims, "the decision table's sizes must be machine-checkable"
    for name, claimed in claims:
        assert claimed == pytest.approx(real_size(name), abs=0.005), (
            f"{doc.name} states {claimed} MB for {name}, "
            f"but the file is {real_size(name)} MB")


def test_no_doc_states_a_size_for_an_unresolvable_payload():
    """A size claim must point at a file we can measure."""
    bad = []
    for doc in DOCS:
        text = doc.read_text(encoding="utf-8")
        for match in LINKED_PAYLOAD.finditer(text):
            if not MB.search(match.group(1)):
                continue
            target = re.search(r"\]\(([^)]+)\)", match.group(0)).group(1)
            if size_for_link(target) is None:
                bad.append(f"{doc.name}: {target}")
    assert not bad, f"size claim without a measurable target: {bad}"


def test_collection_no_image_is_documented():
    """The table must cover every shipped v5 minified payload."""
    text = (ROOT / "docs" / "payloads.md").read_text(encoding="utf-8")
    documented = {name for name, _ in table_claims(text)}
    shipped = {name for name in TABLE_LABELS.values()}
    assert documented == shipped, f"undocumented payloads: {sorted(shipped - documented)}"
