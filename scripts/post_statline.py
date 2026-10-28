"""Posts one random statline from last night's basketball-reference box scores to a Discord webhook."""
import argparse
import html
import json
import os
import random
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from scrape_players import HEADERS, fetch

BASE_URL = "https://www.basketball-reference.com"
GAME_LINK_RE = re.compile(r"/boxscores/\d{9}[A-Z]{3}\.html")
TEAM_RE = re.compile(r'<a href="/teams/([A-Z]{3})/\d{4}\.html">([^<]+)</a>\s*</strong>')
SCORE_RE = re.compile(r'<div class="score">(\d+)</div>')
ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
CELL_RE = re.compile(r'data-stat="(\w+)"[^>]*>(.*?)</t[hd]>', re.S)
TAG_RE = re.compile(r"<[^>]+>")
REQUEST_DELAY_SECONDS = 3


@dataclass(frozen=True)
class Team:
    abbreviation: str
    name: str
    score: int


@dataclass(frozen=True)
class Statline:
    player: str
    team: Team
    opponent: Team
    is_home: bool
    game_date: date
    stats: dict[str, str]


def parse_teams(box_html: str) -> tuple[Team, Team]:
    start = box_html.find('class="scorebox"')
    end = box_html.find('class="scorebox_meta"', start)
    if start == -1 or end == -1:
        raise ValueError("scorebox not found")
    scorebox = box_html[start:end]
    names = TEAM_RE.findall(scorebox)
    scores = SCORE_RE.findall(scorebox)
    if len(names) != 2 or len(scores) != 2:
        raise ValueError(f"expected 2 teams and 2 scores, got {names} {scores}")
    away = Team(names[0][0], html.unescape(names[0][1].strip()), int(scores[0]))
    home = Team(names[1][0], html.unescape(names[1][1].strip()), int(scores[1]))
    return away, home


def parse_player_rows(box_html: str, abbreviation: str) -> list[tuple[str, dict[str, str]]]:
    start = box_html.find(f'id="box-{abbreviation}-game-basic"')
    if start == -1:
        raise ValueError(f"box score table for {abbreviation} not found")
    body_start = box_html.find("<tbody>", start)
    body_end = box_html.find("</tbody>", body_start)
    if body_start == -1 or body_end == -1:
        raise ValueError(f"box score body for {abbreviation} not found")
    players: list[tuple[str, dict[str, str]]] = []
    for row in ROW_RE.findall(box_html[body_start:body_end]):
        cells = {stat: html.unescape(TAG_RE.sub("", value)).strip() for stat, value in CELL_RE.findall(row)}
        # DNP / inactive rows carry a "reason" cell instead of stats
        if "<a " in row and "mp" in cells and "reason" not in cells:
            players.append((cells["player"], cells))
    return players


def parse_box_score(box_html: str, game_date: date) -> list[Statline]:
    away, home = parse_teams(box_html)
    statlines: list[Statline] = []
    for team, opponent, is_home in ((away, home, False), (home, away, True)):
        for player, stats in parse_player_rows(box_html, team.abbreviation):
            statlines.append(Statline(player, team, opponent, is_home, game_date, stats))
    return statlines


def format_pct(value: str) -> str:
    return value if value else "-"


def format_statline(line: Statline) -> str:
    s = line.stats
    result = "W" if line.team.score > line.opponent.score else "L"
    location = "vs." if line.is_home else "@"
    header = (
        f"{line.player} ({line.team.abbreviation}) {location} {line.opponent.name}"
        f" // {line.game_date:%d-%m-%Y} // {result} {line.team.score}-{line.opponent.score}"
    )
    body = (
        f"{s['mp']} MP / {s['pts']} PT / {s['trb']} RB / {s['ast']} AS / {s['stl']} ST / {s['blk']} BK"
        f" / {s['tov']} TO / {s['pf']} PF / {format_pct(s['fg_pct'])} FG% ({s['fg']}-{s['fga']})"
        f" / {format_pct(s['fg3_pct'])} 3P% ({s['fg3']}-{s['fg3a']})"
    )
    return f"**{header}**\n{body}"


def collect_statlines(game_date: date) -> list[Statline]:
    scores_url = f"{BASE_URL}/boxscores/?month={game_date.month}&day={game_date.day}&year={game_date.year}"
    game_links = sorted(set(GAME_LINK_RE.findall(fetch(scores_url))))
    statlines: list[Statline] = []
    for link in game_links:
        time.sleep(REQUEST_DELAY_SECONDS)
        statlines.extend(parse_box_score(fetch(BASE_URL + link), game_date))
        print(f"{link}: {len(statlines)} statlines total")
    return statlines


def post_to_discord(webhook_url: str, message: str) -> None:
    payload = json.dumps({"content": message}).encode()
    req = urllib.request.Request(
        webhook_url,
        data=payload,
        headers={**HEADERS, "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        _ = resp.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    _ = parser.add_argument("--date", type=date.fromisoformat, help="game date YYYY-MM-DD, default yesterday (ET)")
    _ = parser.add_argument("--dry-run", action="store_true", help="print instead of posting")
    args = parser.parse_args()
    game_date: date = args.date or (datetime.now(ZoneInfo("America/New_York")).date() - timedelta(days=1))
    dry_run: bool = args.dry_run

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not dry_run and not webhook_url:
        sys.exit("DISCORD_WEBHOOK_URL is not set")

    statlines = collect_statlines(game_date)
    if not statlines:
        print(f"no games on {game_date}, nothing to post")
        return

    message = format_statline(random.choice(statlines))
    print(message)
    if not dry_run:
        post_to_discord(webhook_url, message)


if __name__ == "__main__":
    main()
