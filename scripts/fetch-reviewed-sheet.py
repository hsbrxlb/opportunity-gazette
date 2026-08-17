#!/usr/bin/env python3
"""Fetch one publication-safe reviewed payload from the public Sheet bridge."""

from __future__ import annotations

import argparse
import csv
import io
import json
import urllib.request
from pathlib import Path
from typing import Any


REQUIRED_COLUMNS = {
    "target_date",
    "status",
    "reviewed_json",
    "updated_at",
    "github_write_status",
    "schema_version",
}
PUBLISHABLE_STATUSES = {"ready_for_publish", "no_quality_entries"}
MAX_CSV_BYTES = 5_000_000


class NoReviewedRow(LookupError):
    """The bridge is healthy but has no row for the requested date."""


def download_csv(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "opportunity-gazette-sheet-bridge/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(MAX_CSV_BYTES + 1)
    if len(body) > MAX_CSV_BYTES:
        raise ValueError("published Sheet CSV is unexpectedly large")
    return body.decode("utf-8-sig")


def validate_reviewed(payload: dict[str, Any], target_date: str, row_status: str) -> None:
    if payload.get("schemaVersion") != 1:
        raise ValueError("reviewed schemaVersion must be 1")
    if payload.get("targetDate") != target_date:
        raise ValueError("reviewed targetDate does not match Sheet row")
    if payload.get("status") != row_status or row_status not in PUBLISHABLE_STATUSES:
        raise ValueError("reviewed status is not publishable or does not match Sheet row")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("reviewed entries must be a list")
    counts = payload.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("reviewed counts must be an object")
    published = int(counts.get("published", -1))
    features = int(counts.get("features", -1))
    editorial = int(counts.get("editorial", -1))
    if published != len(entries) or features + editorial != published:
        raise ValueError("reviewed counts do not match entries")


def extract_reviewed(csv_text: str, target_date: str) -> dict[str, Any]:
    reader = csv.DictReader(io.StringIO(csv_text))
    if reader.fieldnames is None:
        raise ValueError("published Sheet CSV has no header")
    missing = REQUIRED_COLUMNS - set(reader.fieldnames)
    if missing:
        raise ValueError(f"published Sheet CSV is missing columns: {sorted(missing)}")
    matches = [row for row in reader if (row.get("target_date") or "").strip() == target_date]
    if not matches:
        raise NoReviewedRow(target_date)
    if len(matches) != 1:
        raise ValueError(f"published Sheet CSV has duplicate rows for {target_date}")
    row = matches[0]
    if (row.get("schema_version") or "").strip() != "1":
        raise ValueError("Sheet row schema_version must be 1")
    if not (row.get("updated_at") or "").strip():
        raise ValueError("Sheet row updated_at is required")
    if not (row.get("github_write_status") or "").strip():
        raise ValueError("Sheet row github_write_status is required")
    try:
        payload = json.loads(row.get("reviewed_json") or "")
    except json.JSONDecodeError as exc:
        raise ValueError("Sheet reviewed_json is invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("Sheet reviewed_json must be an object")
    validate_reviewed(payload, target_date, (row.get("status") or "").strip())
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--url")
    source.add_argument("--input-csv", type=Path)
    parser.add_argument("--target-date", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    csv_text = download_csv(args.url) if args.url else args.input_csv.read_text(encoding="utf-8-sig")
    try:
        payload = extract_reviewed(csv_text, args.target_date)
    except NoReviewedRow:
        print(json.dumps({"found": False, "targetDate": args.target_date}))
        return 3
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"found": True, "targetDate": args.target_date, "entries": len(payload["entries"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
