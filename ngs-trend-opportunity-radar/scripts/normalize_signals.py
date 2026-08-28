#!/usr/bin/env python3
"""Normalize and aggregate auditable trend-signal JSONL rows by explicit theme."""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def expand_inputs(patterns: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for pattern in patterns:
        matches = [Path(p) for p in glob.glob(pattern)]
        if matches:
            paths.extend(matches)
        else:
            candidate = Path(pattern)
            if candidate.exists():
                paths.append(candidate)
    return sorted(dict.fromkeys(paths))


def normalize_theme(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "").strip().lower()
    return re.sub(r"\s+", " ", value)


def stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_rows(paths: Iterable[Path]) -> tuple[list[dict], list[dict]]:
    rows: list[dict] = []
    invalid: list[dict] = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    invalid.append({"file": str(path), "line": line_no, "error": str(exc)})
                    continue
                missing = [key for key in ("theme", "platform", "source_id", "url", "observed_at") if not row.get(key)]
                if missing:
                    invalid.append({"file": str(path), "line": line_no, "missing": missing})
                    continue
                row["_source_file"] = str(path)
                rows.append(row)
    return rows, invalid


def aggregate(rows: Iterable[dict]) -> list[dict]:
    groups: dict[tuple[str, str], dict] = {}
    seen_sources: set[str] = set()
    for row in rows:
        source_id = str(row["source_id"])
        if source_id in seen_sources:
            continue
        seen_sources.add(source_id)
        theme_key = normalize_theme(str(row["theme"]))
        market = str(row.get("requested_market") or "unspecified")
        key = (theme_key, market)
        if key not in groups:
            groups[key] = {
                "candidate_id": "theme-" + stable_id(theme_key, market)[:12],
                "theme": str(row["theme"]).strip(),
                "theme_key": theme_key,
                "requested_market": market,
                "platforms": set(),
                "trend_evidence": [],
            }
        groups[key]["platforms"].add(str(row["platform"]))
        groups[key]["trend_evidence"].append(row)

    result: list[dict] = []
    for group in groups.values():
        group["platforms"] = sorted(group["platforms"])
        group["trend_evidence"].sort(key=lambda r: (str(r.get("platform")), str(r.get("observed_at")), str(r.get("source_id"))))
        group["trend_platform_count"] = len(group["platforms"])
        group["trend_source_count"] = len(group["trend_evidence"])
        group["pain_evidence"] = []
        group["sorftime"] = {"status": "not_run"}
        group["hard_exclusions"] = []
        group["critical_missing"] = []
        result.append(group)
    result.sort(key=lambda g: (-g["trend_platform_count"], -g["trend_source_count"], g["theme_key"]))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", nargs="+", required=True, help="JSONL paths or glob patterns")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    paths = expand_inputs(args.inputs)
    if not paths:
        print("No input files matched.", file=sys.stderr)
        return 2
    rows, invalid = load_rows(paths)
    themes = aggregate(rows)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "themes": themes,
        "summary": {
            "input_files": len(paths),
            "valid_rows": len(rows),
            "invalid_rows": len(invalid),
            "themes": len(themes),
            "invalid_examples": invalid[:20],
        },
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], ensure_ascii=False))
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
