#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "projects" / "downloads" / "tiktok"
DEFAULT_TIKTOKDOWNLOADER_ROOT = os.environ.get("TIKTOKDOWNLOADER_ROOT", "")
MEDIA_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv", ".m4v"}


def safe_filename(value: str, fallback: str = "tiktok-video") -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\n\r\t]+', "_", value).strip(" ._")
    cleaned = re.sub(r"\s+", " ", cleaned)
    return (cleaned or fallback)[:180]


def normalize_url(value: str) -> str:
    text = value.strip()
    if text.startswith("@") and "/" not in text:
        return f"https://www.tiktok.com/{text}"
    if text.startswith("www.tiktok.com/"):
        return f"https://{text}"
    if not text.startswith(("http://", "https://")):
        raise SystemExit("请输入完整 TikTok 链接，或传入 @handle。")
    return text


def validate_tiktokdownloader_root(root: Path) -> bool:
    if not root.exists():
        return False
    if not (root / "main.py").exists() or not (root / "src").is_dir():
        return False
    return True


def load_tiktok_extractor(root: Path) -> Any | None:
    sys.path.insert(0, str(root))
    try:
        from src.link.extractor import ExtractorTikTok  # type: ignore

        return ExtractorTikTok
    except Exception:
        return None


def infer_mode(url: str, requested_mode: str, extractor: Any | None) -> str:
    if requested_mode in {"single", "author"}:
        return requested_mode
    if extractor:
        account = extractor.account_link.search(url)
        detail = extractor.detail_link.search(url)
        if account and not detail:
            return "author"
    lowered = url.lower()
    if "tiktok.com/@" in lowered and "/video/" not in lowered and "/photo/" not in lowered:
        return "author"
    return "single"


def scan_media_files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    files: list[Path] = []
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS:
            files.append(path)
    return sorted(files)


def run_command(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, text=True, capture_output=True, check=False)


def parse_printed_paths(stdout: str) -> list[Path]:
    paths = []
    for line in stdout.splitlines():
        candidate = Path(line.strip())
        if candidate.exists() and candidate.suffix.lower() in MEDIA_EXTENSIONS:
            paths.append(candidate)
    return sorted(set(paths))


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def find_info_json(media_path: Path) -> dict[str, Any]:
    direct = media_path.with_suffix(".info.json")
    if direct.exists():
        return read_json(direct)
    for candidate in media_path.parent.glob(f"{media_path.stem}*.info.json"):
        return read_json(candidate)
    return {}


def find_thumbnail(media_path: Path) -> str | None:
    for candidate in media_path.parent.glob(f"{media_path.stem}*"):
        if candidate.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            return str(candidate)
    return None


def item_from_path(media_path: Path, output_dir: Path, source_url: str) -> dict[str, Any]:
    info = find_info_json(media_path)
    parent = media_path.parent if media_path.parent != output_dir else None
    title = info.get("title") or info.get("description") or media_path.stem
    tags = info.get("tags") if isinstance(info.get("tags"), list) else []
    return {
        "id": str(info.get("id") or media_path.stem),
        "title": str(title),
        "sourceUrl": info.get("webpage_url") or source_url,
        "author": info.get("uploader_id") or info.get("uploader") or (parent.name if parent else None),
        "authorName": info.get("channel") or info.get("uploader"),
        "description": info.get("description"),
        "duration": info.get("duration"),
        "viewCount": info.get("view_count"),
        "likeCount": info.get("like_count"),
        "commentCount": info.get("comment_count"),
        "tags": tags,
        "filePath": str(media_path),
        "thumbnailPath": find_thumbnail(media_path),
        "status": "done",
    }


def write_manifest(
    output_dir: Path,
    mode: str,
    source_url: str,
    items: list[dict[str, Any]],
    backend: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    manifest_path = output_dir / "download_manifest.json"
    manifest = {
        "jobId": f"bggg-tiktok-{int(time.time() * 1000)}",
        "mode": mode,
        "backend": backend,
        "sourceUrl": source_url,
        "outputDir": str(output_dir),
        "manifestPath": str(manifest_path),
        "itemCount": len(items),
        "items": items,
        "warnings": warnings or [],
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def ytdlp_args(args: argparse.Namespace, url: str, mode: str, output_dir: Path, limit: int) -> list[str]:
    command = shutil.which("yt-dlp")
    if not command:
        raise FileNotFoundError("未找到 yt-dlp")
    archive_path = output_dir / ".bggg-tiktok-download-archive.txt"
    result = [
        command,
        "--ignore-errors",
        "--no-overwrites",
        "--download-archive",
        str(archive_path),
        "--windows-filenames",
        "--merge-output-format",
        "mp4",
        "--format",
        "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]/best[vcodec^=avc1][ext=mp4]/best[ext=mp4]/best",
        "--paths",
        str(output_dir),
        "--output",
        "%(uploader|unknown)s/%(id)s_%(title).160B.%(ext)s",
        "--print",
        "after_move:%(filepath)s",
    ]
    if mode == "single":
        result.append("--no-playlist")
    elif mode == "author" and limit > 0:
        result.extend(["--playlist-end", str(limit)])
    if not args.no_metadata:
        result.append("--write-info-json")
    if args.thumbnail:
        result.extend(["--write-thumbnail", "--convert-thumbnails", "jpg"])
    if args.cookies_file:
        result.extend(["--cookies", args.cookies_file])
    if args.cookies_browser:
        result.extend(["--cookies-from-browser", args.cookies_browser])
    result.append(url)
    return result


def run_ytdlp_download(
    args: argparse.Namespace,
    url: str,
    mode: str,
    output_dir: Path,
    limit: int,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    before = set(scan_media_files(output_dir))
    completed = run_command(ytdlp_args(args, url, mode, output_dir, limit))
    paths = parse_printed_paths(completed.stdout)
    after = scan_media_files(output_dir)
    if not paths:
        new_files = [path for path in after if path not in before]
        paths = new_files or after
    if not paths:
        message = completed.stderr.strip() or completed.stdout.strip() or "yt-dlp 未产出文件"
        raise RuntimeError(message)
    items = [item_from_path(path, output_dir, url) for path in paths]
    warnings = []
    if completed.returncode not in {0, None}:
        warnings.append((completed.stderr or completed.stdout).strip()[:2000])
    return write_manifest(output_dir, mode, url, items, "yt-dlp", warnings)


def request_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode("utf-8"))


def download_url_to_file(url: str, target: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    temp = target.with_suffix(target.suffix + ".download")
    with urllib.request.urlopen(request, timeout=300) as response:
        with temp.open("wb") as output:
            shutil.copyfileobj(response, output)
    temp.replace(target)


def run_tikwm_single_download(
    args: argparse.Namespace,
    url: str,
    output_dir: Path,
) -> dict[str, Any]:
    api_url = "https://www.tikwm.com/api/?" + urllib.parse.urlencode({"url": url, "hd": "1"})
    response = request_json(api_url)
    data = response.get("data") or {}
    video_url = data.get("hdplay") or data.get("play")
    if not video_url:
        raise RuntimeError("tikwm 未返回可下载的视频地址。")
    video_id = str(data.get("id") or "tiktok-video")
    title = str(data.get("title") or video_id)
    author_data = data.get("author") if isinstance(data.get("author"), dict) else {}
    author = str(author_data.get("unique_id") or author_data.get("nickname") or "unknown")
    author_dir = output_dir / safe_filename(author, "unknown")
    author_dir.mkdir(parents=True, exist_ok=True)
    target = author_dir / f"{safe_filename(video_id)}_{safe_filename(title)}.mp4"
    if not target.exists():
        download_url_to_file(video_url, target)
    thumbnail_path = None
    if args.thumbnail:
        cover_url = data.get("cover") or data.get("origin_cover")
        if cover_url:
            thumb = author_dir / f"{safe_filename(video_id)}_cover.jpg"
            try:
                download_url_to_file(str(cover_url), thumb)
                thumbnail_path = str(thumb)
            except Exception:
                thumbnail_path = None
    if not args.no_metadata:
        info_path = target.with_suffix(".info.json")
        info_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    item = {
        "id": video_id,
        "title": title,
        "sourceUrl": url,
        "author": author,
        "authorName": author_data.get("nickname"),
        "description": title,
        "filePath": str(target),
        "thumbnailPath": thumbnail_path,
        "status": "done",
    }
    return write_manifest(output_dir, "single", url, [item], "tikwm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download TikTok videos with yt-dlp and a tikwm fallback for single videos.")
    parser.add_argument("url", help="TikTok video URL, author URL, or @handle")
    parser.add_argument("--mode", choices=["auto", "single", "author"], default="auto")
    parser.add_argument("--limit", type=int, default=None, help="Author mode limit. 0 means all available videos.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--tiktokdownloader-root", default=DEFAULT_TIKTOKDOWNLOADER_ROOT, help="Optional local TikTokDownloader checkout used only for URL classification helpers.")
    parser.add_argument("--cookies-file", default="")
    parser.add_argument("--cookies-browser", default="")
    parser.add_argument("--thumbnail", action="store_true", help="Download and convert thumbnails when supported.")
    parser.add_argument("--no-metadata", action="store_true", help="Skip .info.json sidecar files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    url = normalize_url(args.url)
    output_dir = Path(args.output_dir).expanduser().resolve()
    extractor = None
    if args.tiktokdownloader_root:
        tiktokdownloader_root = Path(args.tiktokdownloader_root).expanduser().resolve()
        if validate_tiktokdownloader_root(tiktokdownloader_root):
            extractor = load_tiktok_extractor(tiktokdownloader_root)
    mode = infer_mode(url, args.mode, extractor)
    limit = args.limit
    if limit is None:
        limit = 1 if mode == "single" else 0
    limit = max(0, limit)

    try:
        manifest = run_ytdlp_download(args, url, mode, output_dir, limit)
    except Exception as error:
        if mode != "single":
            raise SystemExit(f"作者批量下载失败：{error}") from error
        manifest = run_tikwm_single_download(args, url, output_dir)
        manifest["warnings"].append(f"yt-dlp 不可用或失败，已使用 tikwm 单视频兜底：{error}")
        Path(manifest["manifestPath"]).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
