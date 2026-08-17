#!/usr/bin/env python3
"""Merge publication-safe reviewed entries without deleting existing issue data."""

from __future__ import annotations

import argparse
import copy
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parents[1]
ISSUES = ROOT / "src" / "data" / "issues"
CATALOG = ROOT / "src" / "data" / "catalog.json"
QUALITY_VERSION = "2026-08-17.2"
ENTRY_FIELDS = ("id", "seriesId", "kind", "quality", "title", "plain", "audience", "pain", "why", "validation", "risk", "topics", "evidence")
EVIDENCE_FIELDS = ("source", "sourceType", "originalTitle", "url", "observedAt", "metrics", "strength", "boundary")


def clean(value: Any, limit: int = 10_000) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit]


def canonical_url(value: str) -> str:
    parsed = urlsplit(value)
    query = [(key, val) for key, val in parse_qsl(parsed.query) if not key.lower().startswith("utm_") and key.lower() not in {"ref", "source", "campaign"}]
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), urlencode(query), ""))


def normalize_kind(value: str) -> str:
    mapped = {"机会": "opportunity", "实战案例": "case", "opportunity": "opportunity", "case": "case"}
    if value not in mapped:
        raise ValueError(f"unsupported content type: {value}")
    return mapped[value]


def normalize_quality(value: str) -> str:
    mapped = {"封面级": "feature", "编辑精选": "editorial", "feature": "feature", "editorial": "editorial"}
    if value not in mapped:
        raise ValueError(f"unsupported quality: {value}")
    return mapped[value]


def normalize_entry(raw: dict[str, Any], target_date: str) -> dict[str, Any]:
    entry = copy.deepcopy(raw)
    entry["kind"] = normalize_kind(clean(entry.get("kind") or entry.get("contentType") or entry.get("content_type")))
    entry["quality"] = normalize_quality(clean(entry.get("quality") or entry.get("qualityLevel") or entry.get("quality_level")))
    if not entry.get("seriesId"):
        entry["seriesId"] = entry.get("series_id")
    required_text = ("id", "seriesId", "title", "plain", "audience", "pain", "why", "validation", "risk")
    for field in required_text:
        entry[field] = clean(entry.get(field))
        if len(entry[field]) < 8:
            raise ValueError(f"entry {entry.get('id')}: {field} is missing or vague")
    topics = entry.get("topics")
    if isinstance(topics, str):
        try:
            topics = json.loads(topics)
        except json.JSONDecodeError:
            topics = [part.strip() for part in re.split(r"[,，|]", topics) if part.strip()]
    if not isinstance(topics, list) or not topics:
        raise ValueError(f"entry {entry['id']}: topics are required")
    entry["topics"] = [clean(topic, 80) for topic in topics if clean(topic, 80)]
    evidence_items = entry.get("evidence")
    if not isinstance(evidence_items, list) or not evidence_items:
        raise ValueError(f"entry {entry['id']}: evidence is required")
    normalized_evidence: list[dict[str, Any]] = []
    for evidence in evidence_items:
        item = {key: copy.deepcopy(evidence.get(key)) for key in EVIDENCE_FIELDS}
        for field in ("source", "sourceType", "originalTitle", "url", "observedAt", "strength", "boundary"):
            item[field] = clean(item.get(field))
        item["url"] = canonical_url(item["url"])
        if not item["url"].startswith(("https://", "http://")):
            raise ValueError(f"entry {entry['id']}: invalid evidence URL")
        if item["observedAt"] != target_date:
            raise ValueError(f"entry {entry['id']}: evidence date does not match target date")
        if item["strength"] not in {"强", "中"}:
            raise ValueError(f"entry {entry['id']}: invalid evidence strength")
        if not isinstance(item.get("metrics"), dict):
            raise ValueError(f"entry {entry['id']}: metrics must be an object")
        normalized_evidence.append(item)
    entry["evidence"] = normalized_evidence
    return {key: entry[key] for key in ENTRY_FIELDS}


def normalize_failure(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "source": clean(raw.get("source") or raw.get("sourceName") or raw.get("source_name"), 160),
        "status": clean(raw.get("status"), 100),
        "detail": clean(raw.get("detail"), 500),
    }


def entry_source_urls(entry: dict[str, Any]) -> set[str]:
    return {canonical_url(item.get("url", "")) for item in entry.get("evidence", []) if item.get("url")}


def merge_entries(existing: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {entry["id"]: entry for entry in existing}
    url_to_id: dict[str, str] = {}
    for entry in existing:
        for url in entry_source_urls(entry):
            url_to_id[url] = entry["id"]
    for entry in incoming:
        duplicate_id = next((url_to_id[url] for url in entry_source_urls(entry) if url in url_to_id), None)
        if duplicate_id and duplicate_id != entry["id"]:
            merged[duplicate_id] = entry | {"id": duplicate_id}
        else:
            merged[entry["id"]] = entry
        for url in entry_source_urls(entry):
            url_to_id[url] = duplicate_id or entry["id"]
    return sorted(merged.values(), key=lambda item: (item["quality"] != "feature", item["title"]))


def recompute_catalog(generated_at: str) -> dict[str, Any]:
    issues = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(ISSUES.glob("*.json"))]
    issues.sort(key=lambda item: item["date"], reverse=True)
    summaries = [{
        "date": issue["date"],
        "status": issue["status"],
        "counts": issue["counts"],
        "leadTitle": issue["entries"][0]["title"] if issue["entries"] else "当天没有值得发布的内容",
        "leadKind": issue["entries"][0]["kind"] if issue["entries"] else None,
        "hasCover": bool(issue["counts"]["features"]),
    } for issue in issues]
    series: dict[str, dict[str, Any]] = {}
    for issue in issues:
        for entry in issue["entries"]:
            item = series.setdefault(entry["seriesId"], {
                "id": entry["seriesId"], "title": entry["title"], "kind": entry["kind"],
                "topics": entry["topics"], "dates": [], "entryIds": [],
            })
            item["dates"].append(issue["date"])
            item["entryIds"].append(entry["id"])
    existing_catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    historical = int(existing_catalog.get("stats", {}).get("historicalCandidates", 0))
    published = sum(len(issue["entries"]) for issue in issues)
    features = sum(sum(entry["quality"] == "feature" for entry in issue["entries"]) for issue in issues)
    return {
        "schemaVersion": 1,
        "qualityVersion": QUALITY_VERSION,
        "generatedAt": generated_at,
        "issues": summaries,
        "series": sorted(
            (item for item in series.values() if len(item["entryIds"]) >= 2),
            key=lambda item: item["dates"][0], reverse=True,
        ),
        "stats": {
            "reportDays": len(issues),
            "historicalCandidates": historical,
            "publishedEntries": published,
            "featureEntries": features,
            "editorialEntries": published - features,
            "excludedEntries": max(0, historical - published),
        },
    }


def ingest(reviewed_path: Path, dry_run: bool = False) -> dict[str, Any]:
    reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
    target_date = clean(reviewed.get("targetDate"))
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", target_date):
        raise ValueError("targetDate must be YYYY-MM-DD")
    if reviewed.get("status") not in {"ready_for_publish", "no_quality_entries"}:
        raise ValueError("reviewed status is not publishable")
    generated_at = clean(reviewed.get("generatedAt"))
    if not generated_at:
        raise ValueError("generatedAt is required")
    incoming = [normalize_entry(entry, target_date) for entry in reviewed.get("entries", [])]
    declared = int(reviewed.get("counts", {}).get("published", len(incoming)))
    if declared != len(incoming):
        raise ValueError("reviewed published count does not match entries")
    issue_path = ISSUES / f"{target_date}.json"
    existing = json.loads(issue_path.read_text(encoding="utf-8")) if issue_path.exists() else {
        "date": target_date, "counts": {"collected": 0, "oldAccepted": 0}, "failedSources": [], "entries": [],
    }
    entries = merge_entries(existing.get("entries", []), incoming)
    failure_map = {item.get("source", ""): item for item in existing.get("failedSources", [])}
    for item in reviewed.get("failedSources", []):
        normalized = normalize_failure(item)
        if normalized["source"]:
            failure_map[normalized["source"]] = normalized
    collected = max(int(existing.get("counts", {}).get("collected", 0)), int(reviewed.get("counts", {}).get("collected", 0)))
    features = sum(entry["quality"] == "feature" for entry in entries)
    editorial = len(entries) - features
    issue = {
        "schemaVersion": 1,
        "qualityVersion": QUALITY_VERSION,
        "date": target_date,
        "generatedAt": generated_at,
        "status": "published" if entries else "no精品",
        "counts": {
            "collected": collected,
            "oldAccepted": int(existing.get("counts", {}).get("oldAccepted", 0)),
            "published": len(entries),
            "features": features,
            "editorial": editorial,
            "rejected": max(0, collected - len(entries)),
        },
        "failedSources": sorted(failure_map.values(), key=lambda item: item["source"]),
        "entries": entries,
    }
    changed = issue != existing
    if not dry_run and changed:
        issue_path.write_text(json.dumps(issue, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        catalog = recompute_catalog(generated_at)
        CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result = {"targetDate": target_date, "changed": changed, "incoming": len(incoming), "publishedAfterMerge": len(entries), "features": features, "editorial": editorial}
    print(json.dumps(result, ensure_ascii=False))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    ingest(Path(args.input), dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
