import datetime
import re


def _is_pr_watched(pr, watched):
    for changed_file in pr.files:
        for watched_path in watched:
            if re.search(watched_path, changed_file):
                return True

    return False


def _is_title_filtered(pr, filters):
    for title_filter in filters:
        if re.search(title_filter, pr.title):
            return True

    return False


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def is_pr_matched(pr, repo):
    return _is_pr_watched(pr, repo.paths) and not _is_title_filtered(pr, repo.title_filters)
