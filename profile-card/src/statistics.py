"""Profile-level metrics: repo/follower/star/contribution counts and
featured-project selection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass
class ProfileStats:
    public_repos: int
    followers: int
    stars: int
    contributions: int | None


def compute_stats(user: dict | None, repos: list[dict], contributions: int | None) -> ProfileStats:
    public_repos = user.get("public_repos", len(repos)) if user else len(repos)
    followers = user.get("followers", 0) if user else 0
    stars = sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork"))

    return ProfileStats(
        public_repos=public_repos,
        followers=followers,
        stars=stars,
        contributions=contributions,
    )


def select_featured_repo(repos: list[dict], config: dict) -> dict | None:
    featured_cfg = config.get("featured", {}) or {}
    if not featured_cfg.get("enabled", False):
        return None

    pinned_name = (featured_cfg.get("repository") or "").strip()
    eligible = [r for r in repos if not r.get("fork") and not r.get("archived")]

    if pinned_name:
        for repo in eligible:
            if repo.get("name") == pinned_name:
                return repo
        return None

    scored = [(repo, _score_repo(repo)) for repo in eligible]
    scored = [(repo, score) for repo, score in scored if score > 0 or repo.get("description")]
    if not scored:
        return None

    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored[0][0]


def _score_repo(repo: dict) -> float:
    score = repo.get("stargazers_count", 0) * 3 + repo.get("forks_count", 0) * 2

    pushed_at = repo.get("pushed_at")
    if pushed_at:
        try:
            pushed = datetime.strptime(pushed_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - pushed <= timedelta(days=182):
                score += 5
        except ValueError:
            pass

    return score
