import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ingest-reviewed.py"
SPEC = importlib.util.spec_from_file_location("ingest_reviewed", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def entry(entry_id: str, url: str, quality: str = "editorial"):
    return {
        "id": entry_id,
        "seriesId": "series-12345678",
        "kind": "case",
        "quality": quality,
        "title": "A concrete automation failure",
        "plain": "A concrete automation failure caused a persisted result to disappear.",
        "audience": "Developers operating scheduled automation and data pipelines.",
        "pain": "The job looks successful although its final result was never persisted.",
        "why": "The final persistence check is reusable across automated research pipelines.",
        "validation": "Run a test job and reread the target branch after the workflow completes.",
        "risk": "This is one repository incident and does not establish market-wide demand.",
        "topics": ["automation"],
        "evidence": [{
            "source": "GitHub Issue", "sourceType": "production_case", "originalTitle": "Failure report",
            "url": url, "observedAt": "2026-08-16", "metrics": {"comments": 2},
            "strength": "强", "boundary": "Supports one concrete case, not market-wide demand.",
        }],
    }


class ReviewedIngestTests(unittest.TestCase):
    def test_chinese_labels_are_normalized(self):
        raw = entry("entry-12345678", "https://example.com/a")
        raw["kind"] = "实战案例"
        raw["quality"] = "封面级"
        normalized = module.normalize_entry(raw, "2026-08-16")
        self.assertEqual(normalized["kind"], "case")
        self.assertEqual(normalized["quality"], "feature")

    def test_same_source_url_updates_instead_of_duplicating(self):
        existing = [entry("entry-existing", "https://example.com/a?utm_source=old")]
        incoming = [entry("entry-new", "https://example.com/a", quality="feature")]
        merged = module.merge_entries(existing, incoming)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["id"], "entry-existing")
        self.assertEqual(merged[0]["quality"], "feature")

    def test_distinct_sources_are_preserved(self):
        merged = module.merge_entries(
            [entry("entry-one", "https://example.com/a")],
            [entry("entry-two", "https://example.com/b")],
        )
        self.assertEqual(len(merged), 2)


if __name__ == "__main__":
    unittest.main()
