#!/usr/bin/env python3
"""Merge normalized review JSONL files while preserving candidate ownership."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_source(value: str) -> tuple[str, Path]:
    candidate_id, separator, path = value.partition("=")
    if not separator or not candidate_id.strip() or not path.strip():
        raise argparse.ArgumentTypeError("source must be CANDIDATE_ID=PATH")
    return candidate_id.strip(), Path(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", type=parse_source, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--observed-market", default="US")
    args = parser.parse_args()

    rows = []
    counts = {}
    for candidate_id, path in args.source:
        count = 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            context = dict(row.get("context") or {})
            context.update({
                "candidate_id": candidate_id,
                "observed_market": args.observed_market,
                "candidate_source_file": str(path),
            })
            rows.append({**row, "context": context})
            count += 1
        counts[candidate_id] = count

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"output": str(args.output), "rows": len(rows), "by_candidate": counts}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
