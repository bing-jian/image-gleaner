"""
Image Gleaner — download images via Bing Image Search by keyword.

Usage:
    python gleaner.py "search term" [--count N] [--out DIR] [--no-headless]
"""

import argparse
import asyncio
import hashlib
import html
import json
import mimetypes
import re
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright


def safe_dirname(keyword: str) -> str:
    return re.sub(r"[^\w\-]+", "_", keyword).strip("_")


def parse_m_attrs(page_html: str) -> list[dict]:
    """Extract image metadata from Bing's JSON blobs embedded in 'm' attributes."""
    records = []
    for raw in re.findall(r' m="(\{[^"]+\})"', page_html):
        try:
            data = json.loads(html.unescape(raw))
            murl = data.get("murl", "")
            turl = data.get("turl", "")
            if murl or turl:
                records.append({"murl": murl, "turl": turl})
        except Exception:
            pass
    return records


async def collect_images(page, target: int) -> list[dict]:
    """Scroll Bing Images and collect image metadata until we have enough."""
    seen_murls: set[str] = set()
    records: list[dict] = []
    stall = 0
    prev = -1

    while len(records) < target:
        html_content = await page.content()
        for rec in parse_m_attrs(html_content):
            key = rec["murl"] or rec["turl"]
            if key and key not in seen_murls:
                seen_murls.add(key)
                records.append(rec)

        if len(records) == prev:
            stall += 1
            if stall >= 6:
                break
        else:
            stall = 0
        prev = len(records)

        # Scroll down to trigger lazy loading
        await page.evaluate("window.scrollBy(0, 4000)")
        await page.wait_for_timeout(1200)

        # Click "See more images" button if it appears and is visible
        more = await page.query_selector("a.btn_seemore, button.btn_seemore")
        if more and await more.is_visible():
            await more.click()
            await page.wait_for_timeout(1000)

    return records[:target]


def download_image(url: str, dest_dir: Path, index: int, label: str = "") -> Path | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read()
            ct = resp.headers.get_content_type() or ""
            ext = mimetypes.guess_extension(ct) or ".jpg"
            ext = ext.replace(".jpe", ".jpg").replace(".jpeg", ".jpg")
            fname = dest_dir / f"{index:04d}_{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"
            fname.write_bytes(data)
            return fname
    except Exception as e:
        return None


async def run(keyword: str, count: int, out_dir: Path, headless: bool):
    dest = out_dir / safe_dirname(keyword)
    dest.mkdir(parents=True, exist_ok=True)

    q = urlencode({"q": keyword})
    url = f"https://www.bing.com/images/search?{q}"

    print(f"Searching: {keyword!r}")
    print(f"Target:    {count} images → {dest}/")

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        )
        page = await ctx.new_page()
        await page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

        print("Collecting image URLs…")
        records = await collect_images(page, count)
        await browser.close()

    print(f"Found {len(records)} candidates. Downloading…")
    saved = 0
    for i, rec in enumerate(records, 1):
        if saved >= count:
            break
        path = None
        # Try original URL first, fall back to Bing thumbnail
        for url_try in [rec["murl"], rec["turl"]]:
            if url_try:
                path = download_image(url_try, dest, saved + 1)
                if path:
                    break
        if path:
            saved += 1
            print(f"  [{saved}/{count}] {path.name}")
        else:
            print(f"  [skip] #{i} — download failed")

    print(f"\nDone. {saved} images saved to {dest}/")


def main():
    parser = argparse.ArgumentParser(description="Glean images from Bing Image Search.")
    parser.add_argument("keyword", help="Search keyword(s)")
    parser.add_argument("--count", "-n", type=int, default=20,
                        help="Number of images to download (default: 20)")
    parser.add_argument("--out", "-o", type=Path, default=Path("downloads"),
                        help="Output base directory (default: downloads/)")
    parser.add_argument("--no-headless", dest="headless", action="store_false",
                        help="Show browser window while running")
    parser.set_defaults(headless=True)
    args = parser.parse_args()

    asyncio.run(run(args.keyword, args.count, args.out, args.headless))


if __name__ == "__main__":
    main()
