import datetime
import fnmatch
import html
import re

from ..clients import github
from ..config import config


def _pr_link(pr: github.PRInfo) -> str:
    return f'<a href="{pr.url}">{html.escape(pr.title)}</a>'


def _matches_regex(pattern: str, value: str) -> bool:
    try:
        if re.search(pattern, value):
            return True
    except:
        pass

    return False


def _matches_glob(pattern: str, value: str) -> bool:
    try:
        if fnmatch.fnmatchcase(value, pattern):
            return True
    except:
        pass

    return False


def now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def pr_message(pr: github.PRInfo, repo: str, components: list[str]) -> str:
    return (f"{_pr_link(pr)}\n"
            f"<b>Repository:</b> {repo}\n"
            f"<b>Author:</b> {html.escape(pr.author)}\n"
            f"<b>Components:</b> {html.escape(', '.join(components))}")


def is_pr_watched(pr: github.PRInfo, watched: list[str]) -> bool:
    for changed_file in pr.files:
        for watched_path in watched:
            if _matches_regex(watched_path, changed_file) or _matches_glob(watched_path, changed_file):
                return True

    return False


def is_title_filtered(pr: github.PRInfo, filters: list[str]) -> bool:
    for title_filter in filters:
        if _matches_regex(title_filter, pr.title):
            return True

    return False


def is_label_filtered(pr: github.PRInfo, filters: list[str]) -> bool:
    for label in pr.labels:
        for label_filter in filters:
            if _matches_regex(label_filter, label):
                return True

    return False


def is_pr_matched(pr: github.PRInfo, repo: config.Repository) -> bool:
    return (bool(matched_components(pr, repo.components))
            and not is_title_filtered(pr, repo.title_filters)
            and not is_label_filtered(pr, repo.label_filters))


def matched_components(pr: github.PRInfo, components: list[config.Component]) -> list[str]:
    return [component.name for component in components if is_pr_watched(pr, component.paths)]
