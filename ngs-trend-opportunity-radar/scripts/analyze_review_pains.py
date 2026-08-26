#!/usr/bin/env python3
"""Code review pain themes with an explicit, auditable keyword taxonomy."""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--taxonomy", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = Path(args.input)
    rows = load_jsonl(input_path)
    taxonomy = json.loads(Path(args.taxonomy).read_text(encoding="utf-8"))
    themes = taxonomy.get("themes") or []
    asin_counts: Counter[str] = Counter()
    low_star_rows = []
    for row in rows:
        asins = (row.get("context") or {}).get("asins") or []
        for asin in asins:
            asin_counts[str(asin)] += 1
        stars = (row.get("engagement") or {}).get("stars")
        if isinstance(stars, (int, float)) and stars <= 3:
            low_star_rows.append(row)

    coded = []
    for theme in themes:
        terms = [str(term).casefold() for term in theme.get("terms") or []]
        matches = []
        for row in rows:
            normalized = html.unescape(str(row.get("text_raw") or "")).casefold()
            hit_terms = [term for term in terms if term in normalized]
            if not hit_terms:
                continue
            stars = (row.get("engagement") or {}).get("stars")
            asins = (row.get("context") or {}).get("asins") or []
            matches.append(
                {
                    "source_id": row.get("source_id"),
                    "asin": asins[0] if asins else None,
                    "stars": stars,
                    "date": row.get("date"),
                    "text_raw": html.unescape(str(row.get("text_raw") or "")),
                    "matched_terms": hit_terms,
                    "url": f"https://www.amazon.com/dp/{asins[0]}" if asins else None,
                }
            )
        low = [row for row in matches if isinstance(row.get("stars"), (int, float)) and row["stars"] <= 3]
        evidence = sorted(low, key=lambda row: (row.get("stars") or 9, str(row.get("date") or "")))[:5]
        coded.append(
            {
                "id": theme.get("id"),
                "label": theme.get("label"),
                "severity": theme.get("severity"),
                "terms": theme.get("terms") or [],
                "all_mentions": len(matches),
                "low_star_mentions": len(low),
                "low_star_share_pct": round(100 * len(low) / len(low_star_rows), 2) if low_star_rows else 0,
                "evidence": evidence,
            }
        )
    coded.sort(key=lambda row: (-int(row.get("low_star_mentions") or 0), -int(row.get("severity") or 0), str(row.get("label") or "")))
    output = {
        "_meta": {
            "input": str(input_path),
            "taxonomy": args.taxonomy,
            "total_reviews": len(rows),
            "low_star_definition": "1-3 stars",
            "low_star_reviews": len(low_star_rows),
            "sampling_note": "One core ASIN uses full star-stratified collection and breadth ASINs use basic collection. Do not infer market satisfaction rate.",
            "counting_note": "Multi-label mentions; theme counts can sum above the number of reviews.",
        },
        "reviews_by_asin": dict(sorted(asin_counts.items())),
        "themes": coded,
    }
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"reviews": len(rows), "low_star_reviews": len(low_star_rows), "themes": len(coded)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
