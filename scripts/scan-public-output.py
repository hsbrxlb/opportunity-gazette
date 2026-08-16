#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "src", ROOT / "public", ROOT / "dist"]
PATTERNS = {
    "本机绝对路径": re.compile(r"/" + r"Users/[^/]+/"),
    "敏感字段": re.compile(r"(?i)\b(cookie|set-cookie|authorization|bearer|password|passwd|secret|session credential)\b\s*[:=]"),
    "疑似令牌": re.compile(r"\b(?:gh[opsu]_|sk-)[A-Za-z0-9_-]{16,}\b"),
}
SUFFIXES = {".html", ".js", ".mjs", ".css", ".json", ".xml", ".txt", ".md", ".svg"}


findings: list[str] = []
for target in TARGETS:
    if not target.exists():
        continue
    for path in target.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for label, pattern in PATTERNS.items():
            if pattern.search(text):
                findings.append(f"{label}: {path.relative_to(ROOT)}")

if findings:
    print("\n".join(findings), file=sys.stderr)
    raise SystemExit(1)
print("Public source and build output passed local-path and credential scans.")
