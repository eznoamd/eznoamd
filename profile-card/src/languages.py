"""Language byte aggregation across a user's public repositories."""

from __future__ import annotations

from dataclasses import dataclass

from github_api import GitHubClient


@dataclass
class LanguageShare:
    name: str
    bytes: int
    percent: float


def aggregate_languages(
    client: GitHubClient,
    repos: list[dict],
    exclude_forks: bool = True,
    exclude_repos: list[str] | None = None,
) -> dict[str, int]:
    excluded = set(exclude_repos or [])
    totals: dict[str, int] = {}

    for repo in repos:
        if exclude_forks and repo.get("fork"):
            continue
        if repo.get("name") in excluded:
            continue

        for lang, count in client.get_repo_languages(client.username, repo["name"]).items():
            totals[lang] = totals.get(lang, 0) + count

    return totals


def top_languages(byte_totals: dict[str, int], max_shown: int = 5) -> list[LanguageShare]:
    total_bytes = sum(byte_totals.values())
    if total_bytes == 0:
        return []

    ordered = sorted(byte_totals.items(), key=lambda pair: pair[1], reverse=True)
    shown = ordered[:max_shown]
    rest = ordered[max_shown:]

    entries = [(name, count) for name, count in shown]
    other_bytes = sum(count for _, count in rest)
    if other_bytes > 0:
        entries.append(("Other", other_bytes))

    percentages = [round(count * 100 / total_bytes) for _, count in entries]
    # Nudge the largest bucket so rounded percentages sum to exactly 100.
    drift = 100 - sum(percentages)
    if percentages:
        percentages[0] += drift

    return [
        LanguageShare(name=name, bytes=count, percent=pct)
        for (name, count), pct in zip(entries, percentages)
    ]
