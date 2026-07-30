"""Scrapes basketball-reference.com/players/ into players.json at the repo root."""
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

LETTERS = "abcdefghijklmnopqrstuvwxyz"
ROW_RE = re.compile(r'<a href="(/players/[a-z]/[a-zA-Z0-9]+\.html)">([^<]+)</a>')
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; randomballer-build-script/1.0)"}
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "players.json"


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    players: list[dict[str, str]] = []
    seen: set[str] = set()
    for i, letter in enumerate(LETTERS):
        url = f"https://www.basketball-reference.com/players/{letter}/"
        try:
            html = fetch(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        for href, name in ROW_RE.findall(html):
            if href not in seen:
                seen.add(href)
                players.append({"name": name, "url": href})
        print(f"{letter}: {len(seen)} total")
        if i < len(LETTERS) - 1:
            time.sleep(3)

    OUTPUT_PATH.write_text(json.dumps(players))
    print(f"wrote {len(players)} players to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
