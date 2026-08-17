import csv
import importlib.util
import io
import json
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fetch-reviewed-sheet.py"
SPEC = importlib.util.spec_from_file_location("fetch_reviewed_sheet", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(MODULE)


def reviewed(target_date="2026-08-16"):
    return {
        "schemaVersion": 1,
        "targetDate": target_date,
        "generatedAt": "2026-08-17T20:38:05+08:00",
        "status": "ready_for_publish",
        "counts": {"published": 1, "features": 1, "editorial": 0},
        "failedSources": [],
        "entries": [{"id": "entry-123"}],
    }


def make_csv(rows):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[
        "target_date", "status", "reviewed_json", "updated_at", "github_write_status", "schema_version"
    ])
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def row(target_date="2026-08-16", payload=None):
    payload = payload or reviewed(target_date)
    return {
        "target_date": target_date,
        "status": payload["status"],
        "reviewed_json": json.dumps(payload, ensure_ascii=False),
        "updated_at": "2026-08-17T20:40:00+08:00",
        "github_write_status": "blocked_403",
        "schema_version": "1",
    }


class FetchReviewedSheetTests(unittest.TestCase):
    def test_extracts_matching_row(self):
        payload = MODULE.extract_reviewed(make_csv([row()]), "2026-08-16")
        self.assertEqual(payload["targetDate"], "2026-08-16")
        self.assertEqual(len(payload["entries"]), 1)

    def test_missing_date_is_not_a_malformed_bridge(self):
        with self.assertRaises(MODULE.NoReviewedRow):
            MODULE.extract_reviewed(make_csv([row()]), "2026-08-15")

    def test_duplicate_dates_fail_closed(self):
        with self.assertRaisesRegex(ValueError, "duplicate rows"):
            MODULE.extract_reviewed(make_csv([row(), row()]), "2026-08-16")

    def test_mismatched_counts_fail_closed(self):
        payload = reviewed()
        payload["counts"]["published"] = 2
        with self.assertRaisesRegex(ValueError, "counts do not match"):
            MODULE.extract_reviewed(make_csv([row(payload=payload)]), "2026-08-16")


if __name__ == "__main__":
    unittest.main()
