#!/usr/bin/env python3
import argparse
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from scholarly import scholarly, ProxyGenerator


ASSETS_DIR = Path("assets/img/pub_preview")
BIB_PATH = Path("_bibliography/papers.bib")


def slugify(text: str) -> str:
    text = text.strip().lower()
    text = re.sub(r"[^a-z0-9\-\s]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text[:80]


def ensure_dirs():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    BIB_PATH.parent.mkdir(parents=True, exist_ok=True)


def backup_bib():
    if BIB_PATH.exists():
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        backup = BIB_PATH.with_suffix(f".bak.{ts}.bib")
        backup.write_text(BIB_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        return str(backup)
    return None


def fetch_author(user_id: str):
    author = scholarly.search_author_id(user_id)
    if not author:
        raise RuntimeError("Author not found for user id: " + user_id)
    author = scholarly.fill(author, sections=["publications"])
    return author


def fetch_publications(author, max_pubs: int | None = None):
    pubs = []
    for i, pub in enumerate(author.get("publications", [])):
        if max_pubs and i >= max_pubs:
            break
        try:
            pub_filled = scholarly.fill(pub)
            pubs.append(pub_filled)
            # gentle delay to be polite
            time.sleep(0.5)
        except Exception as e:
            print(f"[warn] failed to fill publication {pub.get('bib', {}).get('title')}: {e}")
    return pubs


def parse_bibtex_key(bibtex: str, fallback_title: str, fallback_year: str | None) -> str:
    m = re.search(r"@\w+\{([^,]+)", bibtex)
    if m:
        return m.group(1)
    base = slugify(fallback_title)
    if fallback_year:
        base = f"{base}-{fallback_year}"
    return base


def discover_thumbnail_url(page_url: str) -> str | None:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"}
        r = requests.get(page_url, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, "html.parser")
        for prop in ["og:image", "twitter:image", "og:image:url"]:
            tag = soup.find("meta", property=prop)
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None
    except Exception:
        return None


def download_image(url: str, dest_path: Path) -> bool:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119 Safari/537.36"}
        with requests.get(url, headers=headers, timeout=20, stream=True) as r:
            if r.status_code != 200:
                return False
            with open(dest_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser(description="Fetch Google Scholar publications and update papers.bib with optional thumbnails.")
    parser.add_argument("--user", required=True, help="Google Scholar user id, e.g. mo4TKqkAAAAJ")
    parser.add_argument("--max", type=int, default=None, help="Max publications to fetch (optional)")
    parser.add_argument("--thumbnails", action="store_true", help="Attempt to fetch preview images and save locally")
    parser.add_argument("--serpapi-key", default=os.environ.get("SERPAPI_API_KEY"), help="SerpAPI key (optional, env SERPAPI_API_KEY)")
    args = parser.parse_args()

    ensure_dirs()

    # Try to mitigate blocking
    try:
        pg = ProxyGenerator()
        if args.serpapi_key:
            if pg.SerpApi(api_key=args.serpapi_key):
                scholarly.use_proxy(pg)
                print("Using SerpAPI via scholarly.ProxyGenerator")
        else:
            if pg.FreeProxies():
                scholarly.use_proxy(pg)
                print("Using free proxies via scholarly.ProxyGenerator")
    except Exception as e:
        print(f"[warn] failed to configure proxies: {e}")
    backup = backup_bib()
    if backup:
        print(f"Backed up existing bib to: {backup}")

    print("Fetching author and publications...")
    author = fetch_author(args.user)
    pubs = fetch_publications(author, max_pubs=args.max)
    print(f"Fetched {len(pubs)} publications.")

    bib_entries = []
    preview_map = {}

    for pub in pubs:
        title = pub.get("bib", {}).get("title", "untitled")
        year = pub.get("bib", {}).get("pub_year") or pub.get("bib", {}).get("year")
        try:
            bibtex = scholarly.bibtex(pub)
        except Exception:
            # Fallback: minimal BibTeX from available fields
            authors = pub.get("bib", {}).get("author", "")
            venue = pub.get("bib", {}).get("venue", "")
            entry_type = "article"
            key = slugify(f"{title}-{year or ''}") or f"key{int(time.time())}"
            fields = []
            if authors:
                fields.append(f"  author = {{{authors}}}")
            fields.append(f"  title = {{{title}}}")
            if year:
                fields.append(f"  year = {{{year}}}")
            if venue:
                fields.append(f"  journal = {{{venue}}}")
            bibtex = f"@{entry_type}{{{key},\n" + ",\n".join(fields) + "\n}"

        key = parse_bibtex_key(bibtex, title, year)

        # Optional thumbnails
        if args.thumbnails:
            page_url = pub.get("pub_url") or pub.get("eprint_url") or pub.get("eprint") or pub.get("gscholar_souce")
            thumb_url = None
            if page_url:
                thumb_url = discover_thumbnail_url(page_url)
            if thumb_url:
                ext = os.path.splitext(thumb_url.split("?")[0])[1] or ".jpg"
                dest = ASSETS_DIR / f"{key}{ext}"
                ok = download_image(thumb_url, dest)
                if ok:
                    preview_rel = f"{ASSETS_DIR.as_posix()}/{dest.name}"
                    preview_map[key] = preview_rel

        bib_entries.append((year or "0000", bibtex, key))

    # sort by year desc (unknown last)
    def _sort_key(t):
        y = t[0]
        try:
            return -(int(y))
        except Exception:
            return 0

    bib_entries.sort(key=_sort_key)

    # inject preview field if available
    final_entries = []
    for _, bibtex, key in bib_entries:
        if key in preview_map:
            # insert preview = {...} before closing brace
            if bibtex.strip().endswith('}'):
                bibtex = bibtex.rstrip().rstrip('}')
                # ensure ends with comma
                if not bibtex.strip().endswith(','):
                    bibtex += ',\n'
                bibtex += f"  preview = {{{preview_map[key]}}}\n}}\n"
        # Ensure trailing newline between entries
        if not bibtex.endswith("\n\n"):
            bibtex = bibtex.rstrip() + "\n\n"
        final_entries.append(bibtex)

    BIB_PATH.write_text("".join(final_entries), encoding="utf-8")
    print(f"Wrote {len(final_entries)} entries to {BIB_PATH}")


if __name__ == "__main__":
    sys.exit(main())
