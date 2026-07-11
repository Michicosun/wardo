import dataclasses
import datetime
import logging

import requests

from . import config

log = logging.getLogger("wardo.github")

PRS_QUERY = """
query($owner: String!, $name: String!, $states: [PullRequestState!]!, $order: IssueOrderField!, $pageSize: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: $states, orderBy: {field: $order, direction: DESC}, first: $pageSize, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url createdAt updatedAt mergedAt
        author { login }
        files(first: 100) { nodes { path } }
      }
    }
  }
}
"""

SEARCH_PRS_QUERY = """
query($q: String!, $pageSize: Int!, $cursor: String) {
  search(query: $q, type: ISSUE, first: $pageSize, after: $cursor) {
    pageInfo { hasNextPage endCursor }
    nodes {
      ... on PullRequest {
        number title url createdAt updatedAt mergedAt
        author { login }
        files(first: 100) { nodes { path } }
      }
    }
  }
}
"""

@dataclasses.dataclass
class PRInfo:
    number: int
    title: str
    url: str
    author: str
    created_at: datetime.datetime
    updated_at: datetime.datetime
    merged_at: datetime.datetime | None
    files: list[str]


def _parse_ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _parse_pr(node):
    return PRInfo(
        number=node["number"],
        title=node["title"],
        url=node["url"],
        author=(node.get("author") or {}).get("login", "ghost"),
        created_at=_parse_ts(node["createdAt"]),
        updated_at=_parse_ts(node["updatedAt"]),
        merged_at=_parse_ts(node["mergedAt"]) if node["mergedAt"] else None,
        files=[f["path"] for f in node["files"]["nodes"]],
    )


class GitHub:
    def __init__(self, cfg: config.GithubConfig) -> None:
        self.api = "https://api.github.com/graphql"
        self.headers = {"Authorization": f"Bearer {cfg.token}"}

    def _graphql(self, query, variables):
        r = requests.post(self.api, json={"query": query, "variables": variables}, headers=self.headers, timeout=60)
        r.raise_for_status()

        data = r.json()

        if data.get("errors"):
            raise RuntimeError(str(data["errors"]))

        return data["data"]

    def _pull_requests(self, repo, states, order, page_size=100):
        owner, name = repo.split("/")
        cursor = None
        while True:
            data = self._graphql(PRS_QUERY, {"owner": owner, "name": name, "states": states, "order": order, "pageSize": page_size, "cursor": cursor})
            prs = data["repository"]["pullRequests"]

            for node in prs["nodes"]:
                yield _parse_pr(node)

            if not prs["pageInfo"]["hasNextPage"]:
                return

            cursor = prs["pageInfo"]["endCursor"]

    def _search_prs(self, q, page_size=100):
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

    def new_prs(self, repo, since):
        result = []
        for pr in self._pull_requests(repo, ["OPEN"], "CREATED_AT"):
            if pr.created_at <= since:
                break

            result.append(pr)

        return result

    def open_prs(self, repo, cutoff):
        q = f"repo:{repo} is:pr is:open created:>={cutoff.strftime('%Y-%m-%dT%H:%M:%S+00:00')} sort:created-desc"
        for pr in self._search_prs(q):
            if pr.created_at >= cutoff:
                yield pr

    def closed_prs(self, repo, cutoff):
        q = f"repo:{repo} is:pr is:merged merged:>={cutoff.strftime('%Y-%m-%dT%H:%M:%S+00:00')} sort:updated-desc"
        for pr in self._search_prs(q):
            if pr.merged_at and pr.merged_at >= cutoff:
                yield pr
