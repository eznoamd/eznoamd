"""Entry point: config + GitHub API -> output/card.svg.

Identity fields always come from config.yml, never from the API user
object, keeping automatic (GitHub) and manual (personal) data cleanly
separated as required by the spec.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "src"))

from github_api import GitHubClient  # noqa: E402
from languages import aggregate_languages, top_languages  # noqa: E402
from statistics import compute_stats, select_featured_repo  # noqa: E402
from svg_generator import CardData, generate_svg  # noqa: E402


def load_config(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_card_data(config: dict, user: dict | None, repos: list[dict], calendar: dict | None,
                     languages: list, featured_repo: dict | None) -> CardData:
    profile = config["profile"]

    stats = compute_stats(user, repos, calendar)

    stack = {
        category: items
        for category, items in (config.get("stack") or {}).items()
        if items
    }

    featured = None
    if featured_repo:
        featured = {
            "name": featured_repo.get("name", ""),
            "description": featured_repo.get("description") or "",
            "language": featured_repo.get("language") or "",
            "stars": featured_repo.get("stargazers_count", 0),
        }

    status = {
        "status": "ONLINE",
        "user": profile["username"],
        "role": profile["title"].upper(),
        "build": datetime.now(timezone.utc).strftime("%Y.%m.%d %H:%M UTC"),
        "mode": (config.get("system") or {}).get("mode"),
    }

    return CardData(
        theme=config["theme"],
        name=profile["name"],
        username=profile["username"],
        title=profile["title"],
        description=profile.get("description", ""),
        status=status,
        current=config.get("current") or [],
        stats={
            "public_repos": stats.public_repos,
            "followers": stats.followers,
            "stars": stats.stars,
            "contributions": stats.contributions,
        },
        languages=languages,
        activity=calendar,
        stack=stack,
        featured=featured,
        journey=config.get("journey") or [],
        organizations=config.get("organizations") or [],
        generated_at=f"GENERATED {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
    )


def main() -> int:
    config = load_config(BASE_DIR / "config.yml")
    username = config["profile"]["username"]

    token = os.environ.get("CARD_TOKEN") or os.environ.get("GITHUB_TOKEN")
    graphql_token = os.environ.get("CARD_TOKEN")

    client = GitHubClient(username=username, token=token, graphql_token=graphql_token)

    user = client.get_user()
    all_repos = client.list_public_repos()
    # The GitHub profile-README repo (name == username) isn't a "project" -
    # exclude it from language/star/featured signals so the card never ends
    # up featuring itself.
    repos = [r for r in all_repos if r.get("name", "").lower() != username.lower()]

    calendar = client.get_contribution_calendar(config.get("activity", {}).get("weeks", 12))

    lang_cfg = config.get("languages", {}) or {}
    lang_bytes = aggregate_languages(
        client,
        repos,
        exclude_forks=lang_cfg.get("exclude_forks", True),
        exclude_repos=lang_cfg.get("exclude_repos", []),
    )
    languages = top_languages(lang_bytes, lang_cfg.get("max_shown", 5))

    featured_repo = select_featured_repo(repos, config)

    card = build_card_data(config, user, repos, calendar, languages, featured_repo)
    svg = generate_svg(card)

    output_dir = BASE_DIR / "output"
    output_dir.mkdir(exist_ok=True)
    (output_dir / "card.svg").write_text(svg, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
