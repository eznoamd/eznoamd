"""Thin client over the official GitHub REST + GraphQL APIs.

Every public method degrades gracefully on failure (returns None/[]/{})
instead of raising, so one broken endpoint only costs its own card
section rather than crashing the whole generator.
"""

from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

REST_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"

_CONTRIBUTIONS_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        totalContributions
      }
    }
  }
}
"""


class GitHubClient:
    def __init__(
        self,
        username: str,
        token: str | None = None,
        graphql_token: str | None = None,
        timeout: float = 10.0,
        max_retries: int = 3,
    ) -> None:
        self.username = username
        self._token = token
        self._graphql_token = graphql_token
        self._timeout = timeout

        self._session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
        )
        self._session.mount("https://", HTTPAdapter(max_retries=retry))

        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._session.headers.update(headers)

    def get_user(self) -> dict | None:
        resp = self._request("GET", f"{REST_BASE}/users/{self.username}")
        if resp is None:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    def list_public_repos(self) -> list[dict]:
        repos: list[dict] = []
        url = f"{REST_BASE}/users/{self.username}/repos"
        params = {"per_page": 100, "type": "owner", "sort": "pushed"}

        while url:
            resp = self._request("GET", url, params=params)
            if resp is None:
                break
            try:
                page = resp.json()
            except ValueError:
                break
            if not isinstance(page, list):
                break

            for repo in page:
                owner = (repo.get("owner") or {}).get("login", "")
                if owner.lower() == self.username.lower():
                    repos.append(repo)

            url = resp.links.get("next", {}).get("url")
            params = None  # next URL already carries query params

        return repos

    def get_repo_languages(self, owner: str, repo: str) -> dict[str, int]:
        resp = self._request("GET", f"{REST_BASE}/repos/{owner}/{repo}/languages")
        if resp is None:
            return {}
        try:
            data = resp.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def get_total_contributions(self) -> int | None:
        if not self._graphql_token:
            return None

        data = self._graphql(_CONTRIBUTIONS_QUERY, {"login": self.username})
        if not data:
            return None

        try:
            return data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["totalContributions"]
        except (KeyError, TypeError):
            return None

    def _request(self, method: str, url: str, **kwargs) -> requests.Response | None:
        try:
            resp = self._session.request(method, url, timeout=self._timeout, **kwargs)
        except requests.RequestException:
            return None

        if resp.status_code in (403, 429):
            retry_after = resp.headers.get("retry-after")
            remaining = resp.headers.get("x-ratelimit-remaining")

            if retry_after is not None:
                try:
                    wait = min(float(retry_after), 65.0)
                except ValueError:
                    wait = 0.0
                if wait > 0:
                    time.sleep(wait)
                    try:
                        resp = self._session.request(method, url, timeout=self._timeout, **kwargs)
                    except requests.RequestException:
                        return None
            elif remaining == "0":
                # Primary rate limit exhausted - not worth a (possibly hour-long) wait.
                return None

        if resp.status_code >= 400:
            return None

        return resp

    def _graphql(self, query: str, variables: dict) -> dict | None:
        headers = {"Authorization": f"Bearer {self._graphql_token}"}
        try:
            resp = self._session.post(
                GRAPHQL_URL,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=self._timeout,
            )
        except requests.RequestException:
            return None

        if resp.status_code >= 400:
            return None

        try:
            data = resp.json()
        except ValueError:
            return None

        if "errors" in data and not data.get("data"):
            return None

        return data
