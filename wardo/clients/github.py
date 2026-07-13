import dataclasses
import datetime
import logging
from collections.abc import Iterator
from typing import Any

from ..config import config
from . import retries

log = logging.getLogger("wardo.github")

PR_FIELDS = """
      number title url createdAt updatedAt closedAt mergedAt
      author { login }
      labels(first: 100) { nodes { name } }
      files(first: 100) { nodes { path } }
"""

SEARCH_PRS_QUERY = """
query($q: String!, $pageSize: Int!, $cursor: String) {
  search(query: $q, type: ISSUE, first: $pageSize, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {%s}
    }
  }
}
""" % PR_FIELDS

PR_QUERY = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {%s}
  }
}
""" % PR_FIELDS


@dataclasses.dataclass
class PRInfo:
    number: int
    title: str
    url: str
    author: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    closed_at: datetime.datetime | None
    merged_at: datetime.datetime | None
    files: list[str]
    labels: list[str]


def _parse_ts(s: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _fmt_search_ts(ts: datetime.datetime) -> str:
    return ts.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _parse_pr(node: dict[str, Any]) -> PRInfo:
    return PRInfo(
        number=node["number"],
        title=node["title"],
        url=node["url"],
        author=(node.get("author") or {}).get("login", "ghost"),
        created_at=_parse_ts(node["createdAt"]),
        updated_at=_parse_ts(node["updatedAt"]),
        closed_at=_parse_ts(node["closedAt"]) if node["closedAt"] else None,
        merged_at=_parse_ts(node["mergedAt"]) if node["mergedAt"] else None,
        files=[f["path"] for f in node["files"]["nodes"]],
        labels=[l["name"] for l in node["labels"]["nodes"]],
    )


class GitHub:
    def __init__(self, cfg: config.GithubConfig) -> None:
        self.api = "https://api.github.com/graphql"
        self.headers = {"Authorization": f"Bearer {cfg.token}"}

    def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        def call(s):
            r = s.post(self.api, json={"query": query, "variables": variables}, headers=self.headers, timeout=60)
            r.raise_for_status()
            return r.json()

        data = retries.request(call)

        if data.get("errors"):
            raise RuntimeError(str(data["errors"]))

        return data["data"]

    def _search_prs(self, q: str, page_size: int = 100) -> Iterator[PRInfo]:
        cursor = None
        while True:
            data = self._graphql(SEARCH_PRS_QUERY, {"q": q, "pageSize": page_size, "cursor": cursor})
            found = data["search"]

            for node in found["nodes"]:
                if node:
                    yield _parse_pr(node)

            if not found["pageInfo"]["hasNextPage"]:
                return

            cursor = found["pageInfo"]["endCursor"]

    def pr(self, repo: str, number: int) -> PRInfo | None:
        owner, name = repo.split("/")
        data = self._graphql(PR_QUERY, {"owner": owner, "name": name, "number": number})
        node = data["repository"]["pullRequest"]
        return _parse_pr(node) if node else None

    def open_prs(self, repo: str, cutoff: datetime.datetime) -> Iterator[PRInfo]:
        q = f"repo:{repo} is:pr is:open created:>={_fmt_search_ts(cutoff)} sort:created-desc"
        for pr in self._search_prs(q):
            if pr.created_at >= cutoff:
                yield pr

    def merged_prs(self, repo: str, cutoff: datetime.datetime) -> Iterator[PRInfo]:
        q = f"repo:{repo} is:pr is:merged merged:>={_fmt_search_ts(cutoff)} sort:updated-desc"
        for pr in self._search_prs(q):
            if pr.merged_at and pr.merged_at >= cutoff:
                yield pr

    def closed_prs(self, repo: str, cutoff: datetime.datetime) -> Iterator[PRInfo]:
        q = f"repo:{repo} is:pr is:closed is:unmerged closed:>={_fmt_search_ts(cutoff)} sort:updated-desc"
        for pr in self._search_prs(q):
            if pr.closed_at and not pr.merged_at and pr.closed_at >= cutoff:
                yield pr
