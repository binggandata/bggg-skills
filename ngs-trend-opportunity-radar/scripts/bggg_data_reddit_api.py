#!/usr/bin/env python3
"""Collect Reddit search listings or comment trees through JSON APIs."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any


TRANSIENT_STATUS = {429, 500, 502, 503, 504}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def next_attempt_path(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        return path
    for attempt in range(2, 1000):
        candidate = path.with_name(f"{path.stem}_attempt{attempt:02d}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"too many attempts for {path}")


def manifest_file(path: Path, manifest: Path) -> str:
    return os.path.relpath(path.resolve(), manifest.parent.resolve())


def rewrite_host(url: str, host: str, *, oauth: bool = False) -> str:
    parsed = urllib.parse.urlsplit(url)
    path = parsed.path
    if oauth and path.endswith(".json"):
        path = path[:-5]
    return urllib.parse.urlunsplit(("https", host, path, parsed.query, ""))


def acquire_oauth_token(user_agent: str, timeout: int) -> tuple[str | None, dict[str, Any] | None]:
    direct = os.environ.get("REDDIT_ACCESS_TOKEN", "").strip()
    if direct:
        return direct, None
    client_id = os.environ.get("REDDIT_CLIENT_ID", "").strip()
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None, None
    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    request = urllib.request.Request(
        "https://www.reddit.com/api/v1/access_token",
        data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode(),
        headers={
            "Authorization": f"Basic {basic}",
            "User-Agent": user_agent,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        token = str(payload.get("access_token") or "").strip()
        if token:
            return token, None
        return None, {"source_route": "oauth_api", "reason": "token_missing", "http_status": 200}
    except urllib.error.HTTPError as exc:
        return None, {"source_route": "oauth_api", "reason": "token_http_error", "http_status": exc.code}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None, {"source_route": "oauth_api", "reason": type(exc).__name__, "http_status": None}


def route_specs(mode: str, user_agent: str, timeout: int) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    routes: list[dict[str, str]] = []
    failures: list[dict[str, Any]] = []
    if mode in {"auto", "oauth"}:
        token, token_failure = acquire_oauth_token(user_agent, timeout)
        if token:
            routes.append({"name": "oauth_api", "host": "oauth.reddit.com", "token": token})
        elif token_failure:
            failures.append(token_failure)
        elif mode == "oauth":
            failures.append({"source_route": "oauth_api", "reason": "credentials_not_configured", "http_status": None})
    if mode in {"auto", "public"}:
        routes.append({"name": "public_json_api", "host": "www.reddit.com", "token": ""})
    return routes, failures


def fetch_json(url: str, route: dict[str, str], user_agent: str, timeout: int) -> tuple[Any | None, dict[str, Any]]:
    routed_url = rewrite_host(url, route["host"], oauth=route["name"] == "oauth_api")
    headers = {"User-Agent": user_agent, "Accept": "application/json"}
    if route["token"]:
        headers["Authorization"] = f"bearer {route['token']}"
    attempt_failures: list[dict[str, Any]] = []
    for attempt in range(1, 3):
        request = urllib.request.Request(routed_url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                body = response.read()
                content_type = response.headers.get_content_type()
                status = response.status
            if content_type not in {"application/json", "text/json"}:
                return None, {
                    "source_route": route["name"], "url": routed_url, "http_status": status,
                    "reason": "non_json_response", "content_type": content_type, "attempt": attempt,
                }
            try:
                return json.loads(body.decode("utf-8")), {
                    "source_route": route["name"], "url": routed_url, "http_status": status,
                    "attempt": attempt, "_raw_body": body, "_attempt_failures": attempt_failures,
                }
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None, {
                    "source_route": route["name"], "url": routed_url, "http_status": status,
                    "reason": "invalid_json", "content_type": content_type, "attempt": attempt,
                }
        except urllib.error.HTTPError as exc:
            last_error = {
                "source_route": route["name"], "url": routed_url, "http_status": exc.code,
                "reason": "http_error", "attempt": attempt,
            }
            attempt_failures.append(last_error)
            if exc.code not in TRANSIENT_STATUS or attempt == 2:
                break
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            try:
                delay = max(float(retry_after or 1), 0)
            except ValueError:
                delay = 1
            if delay > 5:
                last_error["reason"] = "retry_after_exceeds_local_wait_cap"
                last_error["retry_after_seconds"] = delay
                break
            time.sleep(delay)
        except (OSError, TimeoutError) as exc:
            last_error = {
                "source_route": route["name"], "url": routed_url, "http_status": None,
                "reason": type(exc).__name__, "attempt": attempt,
            }
            attempt_failures.append(last_error)
            if attempt == 2:
                break
            time.sleep(1)
    return None, {**(attempt_failures[-1] if attempt_failures else {}), "_attempt_failures": attempt_failures}


def payload_error(payload: Any, expected_kind: str | None = None) -> dict[str, Any] | None:
    if isinstance(payload, dict) and ("error" in payload or ("message" in payload and "data" not in payload)):
        return {"reason": "json_error_response", "api_error": payload.get("error"), "api_message": payload.get("message")}
    if expected_kind == "search":
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, dict) or not isinstance(data.get("children"), list) or "after" not in data:
            return {"reason": "unexpected_schema", "expected_kind": "search_listing"}
    elif expected_kind == "comments":
        if not isinstance(payload, list) or len(payload) < 2:
            return {"reason": "unexpected_schema", "expected_kind": "comment_tree"}
        for listing in payload[:2]:
            data = listing.get("data") if isinstance(listing, dict) else None
            if not isinstance(data, dict) or not isinstance(data.get("children"), list):
                return {"reason": "unexpected_schema", "expected_kind": "comment_tree"}
    return None


def fetch_with_fallback(
    url: str,
    routes: list[dict[str, str]],
    user_agent: str,
    timeout: int,
    expected_kind: str | None = None,
) -> tuple[Any | None, dict[str, Any], list[dict[str, Any]]]:
    failures = []
    for route in routes:
        payload, meta = fetch_json(url, route, user_agent, timeout)
        attempt_failures = list(meta.pop("_attempt_failures", []))
        failures.extend(attempt_failures)
        if payload is not None:
            schema_error = payload_error(payload, expected_kind)
            if schema_error:
                meta.pop("_raw_body", None)
                failures.append({**meta, **schema_error})
                continue
            return payload, meta, failures
        if not attempt_failures:
            failures.append(meta)
    return None, {}, failures


def write_raw_response(path: Path, payload: Any, meta: dict[str, Any]) -> tuple[int, str]:
    body = meta.pop("_raw_body", None)
    if body is None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    path.write_bytes(body)
    return len(body), hashlib.sha256(body).hexdigest()


def post_ids(payload: Any) -> set[str]:
    if not isinstance(payload, dict):
        return set()
    children = ((payload.get("data") or {}).get("children") or [])
    return {str((item.get("data") or {}).get("name") or "") for item in children if item.get("kind") == "t3"}


def with_after(url: str, after: str | None) -> str:
    parsed = urllib.parse.urlsplit(url)
    query = dict(urllib.parse.parse_qsl(parsed.query, keep_blank_values=True))
    if after:
        query["after"] = after
    else:
        query.pop("after", None)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(query), ""))


def page_path(value: str, page: int) -> Path:
    path = Path(value)
    name = path.name
    if "_page001" in name:
        name = name.replace("_page001", f"_page{page:03d}")
    elif page > 1:
        name = f"{path.stem}_page{page:03d}{path.suffix}"
    return path.with_name(name)


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle, delimiter="\t")]


def write_summary(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def search(args: argparse.Namespace, routes: list[dict[str, str]], route_failures: list[dict[str, Any]]) -> int:
    plan = load_json(args.plan)
    manifest = args.manifest
    failures = list(route_failures)
    saved = rows_seen = empty_responses = 0
    global_seen_ids: set[str] = set()
    for item in plan.get("requests") or []:
        after = None
        seen_cursors: set[str] = set()
        seen_ids: set[str] = set()
        for page in range(1, args.max_pages + 1):
            url = with_after(str(item["url"]), after)
            payload, meta, request_failures = fetch_with_fallback(url, routes, args.user_agent, args.timeout, "search")
            failures.extend({**failure, "query": item.get("query"), "lang": item.get("lang", "EN"), "round": item.get("round", 1), "requested_market": item.get("requested_market"), "kind": "search", "page": page, "after": after, "collected_at": now_iso()} for failure in request_failures)
            if payload is None:
                break
            current_ids = post_ids(payload)
            new_ids = current_ids - seen_ids
            global_new_ids = current_ids - global_seen_ids
            rows_seen += len(global_new_ids)
            if not current_ids:
                empty_responses += 1
            output = next_attempt_path(page_path(str(item["output"]), page))
            response_bytes, response_sha256 = write_raw_response(output, payload, meta)
            collected_at = now_iso()
            append_jsonl(manifest, {
                "kind": "search", "file": manifest_file(output, manifest), "url": meta["url"],
                "query": item.get("query"), "lang": item.get("lang", "EN"), "round": item.get("round", 1),
                "requested_market": item.get("requested_market"), "observed_market": item.get("observed_market") or "unknown",
                "sort": item.get("sort"), "time": item.get("time"), "http_status": meta["http_status"],
                "source_route": meta["source_route"], "page": page, "after": after,
                "response_bytes": response_bytes, "response_sha256": response_sha256,
                "collected_at": collected_at,
            })
            saved += 1
            seen_ids.update(current_ids)
            global_seen_ids.update(current_ids)
            next_after = str(((payload.get("data") or {}).get("after") or ""))
            if not next_after or next_after in seen_cursors or (page > 1 and not new_ids):
                break
            seen_cursors.add(next_after)
            after = next_after
    for failure in failures:
        append_jsonl(args.failure_log, failure)
    status = "success" if saved and not failures else "partial" if saved else "blocked"
    if saved and rows_seen == 0 and not failures:
        status = "empty"
    summary = {
        "status": status, "mode": "search", "saved_responses": saved, "unique_posts_seen": rows_seen,
        "empty_responses": empty_responses, "failure_count": len(failures),
        "routes_attempted": [route["name"] for route in routes], "max_pages": args.max_pages,
    }
    write_summary(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if status in {"success", "empty"} else 2


def comments(args: argparse.Namespace, routes: list[dict[str, str]], route_failures: list[dict[str, Any]]) -> int:
    manifest = args.manifest
    failures = list(route_failures)
    saved = 0
    for item in read_tsv(args.targets):
        post_id = str(item.get("post_id") or "").strip().removeprefix("t3_")
        if not post_id:
            continue
        url = f"https://www.reddit.com/comments/{post_id}.json?limit=500&depth=10&sort=top&raw_json=1"
        payload, meta, request_failures = fetch_with_fallback(url, routes, args.user_agent, args.timeout, "comments")
        failures.extend({**failure, "query": item.get("query"), "lang": item.get("lang") or "EN", "round": int(item.get("round") or 1), "requested_market": item.get("requested_market") or args.requested_market, "post_id": post_id, "kind": "comments", "collected_at": now_iso()} for failure in request_failures)
        if payload is None:
            continue
        output = next_attempt_path(args.raw_dir / f"reddit_comments_{post_id}.json")
        response_bytes, response_sha256 = write_raw_response(output, payload, meta)
        append_jsonl(manifest, {
            "kind": "comments", "file": manifest_file(output, manifest), "url": meta["url"],
            "query": item.get("query"), "lang": item.get("lang") or "EN", "round": int(item.get("round") or 1),
            "requested_market": item.get("requested_market") or args.requested_market, "observed_market": item.get("observed_market") or "unknown",
            "post_id": post_id, "http_status": meta["http_status"], "source_route": meta["source_route"],
            "response_bytes": response_bytes, "response_sha256": response_sha256,
            "collected_at": now_iso(),
        })
        saved += 1
    for failure in failures:
        append_jsonl(args.failure_log, failure)
    status = "success" if saved and not failures else "partial" if saved else "blocked"
    summary = {
        "status": status, "mode": "comments", "saved_responses": saved,
        "failure_count": len(failures), "routes_attempted": [route["name"] for route in routes],
    }
    write_summary(args.summary, summary)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if status == "success" else 2


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--api-mode", choices=("auto", "oauth", "public"), default="auto")
    parser.add_argument("--user-agent", default=os.environ.get("REDDIT_USER_AGENT", "BGGGRedditResearch/1.0 (local research)"))
    parser.add_argument("--timeout", type=int, default=20)
    subparsers = parser.add_subparsers(dest="command", required=True)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--plan", type=Path, required=True)
    search_parser.add_argument("--manifest", type=Path, required=True)
    search_parser.add_argument("--failure-log", type=Path, required=True)
    search_parser.add_argument("--summary", type=Path, required=True)
    search_parser.add_argument("--max-pages", type=int, default=1)

    comments_parser = subparsers.add_parser("comments")
    comments_parser.add_argument("--targets", type=Path, required=True)
    comments_parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/source_json"))
    comments_parser.add_argument("--requested-market", default="")
    comments_parser.add_argument("--manifest", type=Path, required=True)
    comments_parser.add_argument("--failure-log", type=Path, required=True)
    comments_parser.add_argument("--summary", type=Path, required=True)

    args = parser.parse_args()
    if getattr(args, "max_pages", 1) < 1:
        raise SystemExit("--max-pages must be at least 1")
    routes, route_failures = route_specs(args.api_mode, args.user_agent, args.timeout)
    if not routes:
        summary = {"status": "blocked", "reason": "no_api_route", "failure_count": len(route_failures)}
        write_summary(args.summary, summary)
        for failure in route_failures:
            append_jsonl(args.failure_log, {**failure, "collected_at": now_iso()})
        print(json.dumps(summary, ensure_ascii=False))
        return 2
    return search(args, routes, route_failures) if args.command == "search" else comments(args, routes, route_failures)


if __name__ == "__main__":
    raise SystemExit(main())
