import datetime
import logging

import requests

log = logging.getLogger("wardo.github")

PRS_QUERY = """
query($owner: String!, $name: String!, $states: [PullRequestState!]!, $order: IssueOrderField!, $page: Int!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    pullRequests(states: $states, orderBy: {field: $order, direction: DESC}, first: $page, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes {
        number title url createdAt updatedAt mergedAt
        author { login }
        viewerSubscription
        files(first: 100) { nodes { path } }
      }
    }
  }
}
"""


def _parse_ts(s):
    return datetime.datetime.fromisoformat(s.replace("Z", "+00:00"))


def _is_touches_files(pr, watched):
    for changed_file in pr["files"]["nodes"]:
        for watched_path in watched:
            if changed_file["path"].startswith(watched_path):
                return True

    return False


class GitHub:
    def __init__(self, token):
        self.api = "https://api.github.com/graphql"
        self.headers = {"Authorization": f"Bearer {token}"}

    def _graphql(self, variables):
        r = requests.post(self.api, json={"query": PRS_QUERY, "variables": variables}, headers=self.headers, timeout=30)
        r.raise_for_status()

        data = r.json()

        if data.get("errors"):
            raise RuntimeError(str(data["errors"]))

        return data["data"]

    def _pull_requests(self, repo, states, order, page_size=100):
        owner, name = repo.split("/")
        cursor = None
        while True:
            data = self._graphql({"owner": owner, "name": name, "states": states, "order": order, "page": page_size, "cursor": cursor})
            prs = data["repository"]["pullRequests"]

            yield from prs["nodes"]

            if not prs["pageInfo"]["hasNextPage"]:
                return

            cursor = prs["pageInfo"]["endCursor"]

    def new_prs(self, repo, paths, since):
        result = []
        for pr in self._pull_requests(repo, ["OPEN"], "CREATED_AT", page_size=30):
            if _parse_ts(pr["createdAt"]) <= since:
                break

            if _is_touches_files(pr, paths):
                result.append(pr)

        return result

    def active_prs(self, repo, paths):
        return [pr for pr in self._pull_requests(repo, ["OPEN"], "CREATED_AT") if _is_touches_files(pr, paths)]

    def closed_prs(self, repo, paths, cutoff):
        result = []
        for pr in self._pull_requests(repo, ["MERGED"], "UPDATED_AT"):
            if _parse_ts(pr["updatedAt"]) < cutoff:
                break

            if pr["mergedAt"] and _parse_ts(pr["mergedAt"]) >= cutoff and _is_touches_files(pr, paths):
                result.append(pr)

        return result
