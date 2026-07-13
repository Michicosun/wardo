import datetime
import fnmatch
import html
import re


def _matches_regex(pattern, value):
    try:
        if re.search(pattern, value):
            return True
    except:
        pass

    return False


def _matches_glob(pattern, value):
    try:
        if fnmatch.fnmatchcase(value, pattern):
            return True
    except:
        pass

    return False


def _is_pr_watched(pr, watched):
    for changed_file in pr.files:
        for watched_path in watched:
            if _matches_regex(watched_path, changed_file) or _matches_glob(watched_path, changed_file):
                return True

    return False


def _is_title_filtered(pr, filters):
    for title_filter in filters:
        if _matches_regex(title_filter, pr.title):
            return True

    return False


def _is_label_filtered(pr, filters):
    for label in pr.labels:
        for label_filter in filters:
            if _matches_regex(label_filter, label):
                return True

    return False


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def pr_link(pr):
    return f'<a href="{pr.url}">{html.escape(pr.title)}</a>'


def pr_line(pr):
    return f"{pr_link(pr)} — {pr.author}"


def is_pr_matched(pr, repo):
    return (_is_pr_watched(pr, repo.paths)
            and not _is_title_filtered(pr, repo.title_filters)
            and not _is_label_filtered(pr, repo.label_filters))
