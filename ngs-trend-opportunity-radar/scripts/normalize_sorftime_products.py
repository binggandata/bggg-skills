#!/usr/bin/env python3
"""Normalize Sorftime product-search responses and retain selected ASINs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_mapping(value: str) -> tuple[str, str]:
    key, separator, item = value.partition("=")
    if not separator or not key.strip() or not item.strip():
        raise argparse.ArgumentTypeError("mapping must be CANDIDATE_ID=VALUE")
    return key.strip(), item.strip()


def unwrap(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload.get("data"), list):
        return payload
    for block in payload.get("content") or []:
        if block.get("type") != "text":
            continue
        try:
            nested = json.loads(block.get("text") or "")
        except json.JSONDecodeError:
            continue
        if isinstance(nested.get("data"), list):
            return nested
    raise SystemExit(f"No Sorftime product data in {path}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", type=parse_mapping, required=True)
    parser.add_argument("--selected", action="append", type=parse_mapping, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    selected = {
        candidate_id: {asin.strip().upper() for asin in value.split(",") if asin.strip()}
        for candidate_id, value in args.selected
    }
    rows = []
    returned = {}
    for candidate_id, source in args.source:
        path = Path(source)
        payload = unwrap(path)
        returned[candidate_id] = len(payload.get("data") or [])
        for rank, row in enumerate(payload.get("data") or [], 1):
            asin = str(row.get("asin") or "").strip().upper()
            if asin not in selected.get(candidate_id, set()):
                continue
            rows.append({
                **row,
                "asin": asin,
                "candidate_id": candidate_id,
                "rank_in_response": rank,
                "semantic_relevance": "selected",
                "source_file": str(path),
            })
    missing = {
        candidate_id: sorted(asins - {row["asin"] for row in rows if row["candidate_id"] == candidate_id})
        for candidate_id, asins in selected.items()
    }
    missing = {key: value for key, value in missing.items() if value}
    if missing:
        raise SystemExit("Selected ASINs missing from responses: " + json.dumps(missing, ensure_ascii=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps({"data": rows, "summary": {"returned": returned, "selected": len(rows)}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), "selected": len(rows), "by_candidate": {key: sum(row["candidate_id"] == key for row in rows) for key in selected}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
