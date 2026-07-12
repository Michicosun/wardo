import datetime
import re


def now():
    return datetime.datetime.now(datetime.timezone.utc)


def is_pr_watched(pr, watched):
    for changed_file in pr.files:
        for watched_path in watched:
            if re.search(watched_path, changed_file):
                return True

    return False
