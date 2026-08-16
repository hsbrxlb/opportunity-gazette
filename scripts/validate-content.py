#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ISSUES = ROOT / "src" / "data" / "issues"
REQUIRED_ENTRY = {
    "id", "seriesId", "kind", "quality", "title", "plain", "audience",
    "pain", "evidence", "why", "validation", "risk", "topics",
}
REQUIRED_EVIDENCE = {
    "source", "sourceType", "originalTitle", "url", "observedAt",
    "metrics", "strength", "boundary",
}


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


files = sorted(ISSUES.glob("*.json"))
if not files:
    fail("No issue JSON files found.")

seen_entries: set[str] = set()
for path in files:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("date") != path.stem:
        fail(f"{path.name}: date does not match filename")
    entries = data.get("entries")
    if not isinstance(entries, list):
        fail(f"{path.name}: entries must be a list")
    if data.get("counts", {}).get("published") != len(entries):
        fail(f"{path.name}: published count does not match entries")
    for entry in entries:
        missing = REQUIRED_ENTRY - entry.keys()
        if missing:
            fail(f"{path.name}: {entry.get('title')} missing {sorted(missing)}")
        if entry["id"] in seen_entries:
            fail(f"duplicate public entry id: {entry['id']}")
        seen_entries.add(entry["id"])
        if entry["quality"] not in {"feature", "editorial"}:
            fail(f"{path.name}: public entry has invalid quality")
        if entry["kind"] not in {"opportunity", "case"}:
            fail(f"{path.name}: public entry has invalid kind")
        if not all(isinstance(entry[field], str) and len(entry[field].strip()) >= 8 for field in (
            "title", "plain", "audience", "pain", "why", "validation", "risk"
        )):
            fail(f"{path.name}: public entry has an empty or vague field")
        if not entry["evidence"]:
            fail(f"{path.name}: public entry has no evidence")
        for evidence in entry["evidence"]:
            missing_evidence = REQUIRED_EVIDENCE - evidence.keys()
            if missing_evidence:
                fail(f"{path.name}: evidence missing {sorted(missing_evidence)}")
            if not str(evidence["url"]).startswith(("https://", "http://")):
                fail(f"{path.name}: invalid evidence URL")

catalog = json.loads((ROOT / "src" / "data" / "catalog.json").read_text(encoding="utf-8"))
if catalog.get("stats", {}).get("publishedEntries") != len(seen_entries):
    fail("catalog publishedEntries does not match issue data")

print(f"Validated {len(files)} issues and {len(seen_entries)} published entries.")
