import pytest

from wardo.clients import github


@pytest.fixture
def node():
    def make(number=1, title="Fix things", created="2026-07-10T00:00:00Z", merged=None,
             closed=None, updated=None, files=("src/a.py",)):
        closed = closed or merged
        return github.PRInfo(
            number=number,
            title=title,
            url=f"https://github.com/x/y/pull/{number}",
            author="alice",
            created_at=github._parse_ts(created),
            updated_at=github._parse_ts(updated or created),
            closed_at=github._parse_ts(closed) if closed else None,
            merged_at=github._parse_ts(merged) if merged else None,
            files=list(files),
        )
    return make
