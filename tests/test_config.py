from wardo.config import config

YAML = """
github:
  token: gh-token
telegram:
  token: tg-token
wardo:
  poll_interval: 30
  ping_schedule: "0 9 * * *"
  allowed_user_id: 42
  repositories:
    - repo: x/y
      paths:
        - src/
        - docs/
"""


def test_load(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(YAML)
    cfg = config.load(str(path))
    assert cfg.github.token == "gh-token"
    assert cfg.telegram.token == "tg-token"
    assert cfg.wardo.poll_interval == 30
    assert cfg.wardo.allowed_user_id == 42
    assert cfg.wardo.repositories == [config.Repository(repo="x/y", paths=["src/", "docs/"], title_filters=[], label_filters=[])]
    assert cfg.wardo.repositories[0].title_filters == []
    assert cfg.wardo.ping_schedule == "0 9 * * *"


def test_load_title_filters(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(YAML + '      title_filters:\n        - "^Backport"\n')
    assert config.load(str(path)).wardo.repositories[0].title_filters == ["^Backport"]


def test_load_label_filters(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(YAML + '      label_filters:\n        - "pr-backport"\n')
    assert config.load(str(path)).wardo.repositories[0].label_filters == ["pr-backport"]


def test_load_default_poll_interval(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(YAML.replace("  poll_interval: 30\n", ""))
    assert config.load(str(path)).wardo.poll_interval == 60
