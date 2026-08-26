#!/usr/bin/env python3
"""Build a deterministic Reddit public-JSON collection plan from TSV queries."""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
from datetime import datetime
from pathlib import Path


def slug(value: str) -> str:
    value = re.sub(r"[^\w]+", "_", value.casefold(), flags=re.UNICODE).strip("_")
    return value[:80] or "query"


def read_queries(path: Path) -> list[dict]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows or "query" not in (rows[0].keys() if rows else []):
        raise SystemExit("queries.tsv must have a header with a query column")
    cleaned = []
    for index, row in enumerate(rows, 1):
        query = (row.get("query") or "").strip()
        if not query:
            continue
        cleaned.append(
            {
                "query": query,
                "lang": (row.get("lang") or "EN").strip().upper(),
                "round": int((row.get("round") or "1").strip()),
                "sort": (row.get("sort") or "top").strip(),
                "time": (row.get("time") or "all").strip(),
                "limit": min(max(int((row.get("limit") or "100").strip()), 1), 100),
                "ordinal": index,
            }
        )
    return cleaned


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--queries", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--raw-dir", default="data/raw/source_json")
    parser.add_argument("--requested-market", default="")
    args = parser.parse_args()

    requests = []
    for row in read_queries(args.queries):
        params = {
            "q": row["query"],
            "sort": row["sort"],
            "t": row["time"],
            "limit": row["limit"],
            "raw_json": 1,
        }
        filename = (
            f"reddit_search_round{row['round']}_{slug(row['query'])}_"
            f"{row['ordinal']:03d}_page001.json"
        )
        requests.append(
            {
                **row,
                "requested_market": args.requested_market,
                "observed_market": "unknown",
                "kind": "search",
                "url": "https://www.reddit.com/search.json?" + urllib.parse.urlencode(params),
                "output": str(Path(args.raw_dir) / filename),
            }
        )

    payload = {
        "schema_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "same_origin": "https://www.reddit.com/",
        "same_origin_old": "https://old.reddit.com/",
        "requested_market": args.requested_market,
        "requests": requests,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "requests": len(requests)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
