#!/usr/bin/env python3
"""
Scan papers.bib, extract URLs, download thumbnails, and inject preview fields.
"""
import re
import sys
from pathlib import Path

import bibtexparser
import requests
from bs4 import BeautifulSoup


ASSETS_DIR = Path("assets/img/pub_preview")
BIB_PATH = Path("_bibliography/papers.bib")


def ensure_dirs():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def discover_thumbnail_url(page_url: str) -> str | None:
    """Try to extract og:image or similar from HTML."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"
        }
        r = requests.get(page_url, headers=headers, timeout=20)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        # Try various meta tags
        for prop in ["og:image", "twitter:image", "og:image:url"]:
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                return tag["content"].strip()
        # Fallback: look for meta name=
        for name in ["twitter:image", "image"]:
            tag = soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None
    except Exception as e:
        print(f"[warn] failed to fetch {page_url}: {e}")
        return None


def download_image(url: str, dest_path: Path) -> bool:
    """Download image from url to dest_path."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"
        }
        with requests.get(url, headers=headers, timeout=20, stream=True) as r:
            if r.status_code != 200:
                return False
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:
        print(f"[warn] failed to download {url}: {e}")
        return False


def main():
    ensure_dirs()

    # Read bib
    with open(BIB_PATH, "r", encoding="utf-8") as f:
        raw_text = f.read()

    # Remove front matter if present
    lines = raw_text.splitlines()
    if lines and lines[0].strip() == "---":
        # find closing ---
        end_idx = 1
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                end_idx = i
                break
        bib_text = "\n".join(lines[end_idx + 1 :])
    else:
        bib_text = raw_text

    # Parse
    bib_db = bibtexparser.loads(bib_text)
    entries = bib_db.entries

    print(f"Found {len(entries)} entries in papers.bib")

    # For each entry, check if it has url/doi, fetch thumbnail, add preview
    for entry in entries:
        key = entry.get("ID", "unknown")
        url = entry.get("url") or entry.get("doi")
        if not url:
            print(f"[skip] {key}: no url/doi")
            continue

        # If already has preview, skip
        if entry.get("preview"):
            print(f"[skip] {key}: already has preview")
            continue

        # Normalize doi to URL
        if url.startswith("10."):
            url = f"https://doi.org/{url}"

        print(f"[process] {key}: {url}")
        thumb_url = discover_thumbnail_url(url)
        if not thumb_url:
            print(f"[skip] {key}: no thumbnail found")
            continue

        # Determine extension
        ext = ".jpg"
        if ".png" in thumb_url.lower():
            ext = ".png"
        elif ".gif" in thumb_url.lower():
            ext = ".gif"

        dest = ASSETS_DIR / f"{key}{ext}"
        ok = download_image(thumb_url, dest)
        if ok:
            preview_rel = f"pub_preview/{dest.name}"
            entry["preview"] = preview_rel
            print(f"[ok] {key}: saved to {dest}, added preview={preview_rel}")
        else:
            print(f"[fail] {key}: could not download {thumb_url}")

    # Write back
    writer = bibtexparser.bwriter.BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None
    out_text = writer.write(bib_db)

    # Restore front matter if existed
    if lines and lines[0].strip() == "---":
        front = "\n".join(lines[: end_idx + 1]) + "\n\n"
        out_text = front + out_text

    with open(BIB_PATH, "w", encoding="utf-8") as f:
        f.write(out_text)

    print(f"Updated {BIB_PATH}")


if __name__ == "__main__":
    sys.exit(main())
