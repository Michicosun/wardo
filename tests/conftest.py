import pytest

from wardo import github


@pytest.fixture
def node():
    def make(number=1, title="Fix things", created="2026-07-10T00:00:00Z", merged=None,
             updated=None, files=("src/a.py",)):
        return github.PRInfo(
            number=number,
            title=title,
            url=f"https://github.com/x/y/pull/{number}",
            author="alice",
            created_at=github._parse_ts(created),
            updated_at=github._parse_ts(updated or created),
            merged_at=github._parse_ts(merged) if merged else None,
            files=list(files),
        )
    return make
