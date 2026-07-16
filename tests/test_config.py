from wardo.config import config

FULL_YAML = """
github:
  token: gh-token
telegram:
  token: tg-token
wardo:
  poll_interval: 30
  stall_interval: 120
  check_interval: 15
  ping_schedule: "0 9 * * *"
  allowed_user_id: 42
  repositories:
    - repo: x/y
      components:
        core:
          - src/
        docs:
          - docs/
      title_filters:
        - "^Backport"
      label_filters:
        - "pr-backport"
"""

MINIMAL_YAML = """
github:
  token: gh-token
telegram:
  token: tg-token
wardo:
  stall_interval: 600
  check_interval: 60
  ping_schedule: "0 9 * * *"
  allowed_user_id: 42
  repositories:
    - repo: x/y
      components:
        core:
          - src/
"""


def test_load(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(FULL_YAML)
    cfg = config.load(str(path))
    assert cfg.github.token == "gh-token"
    assert cfg.telegram.token == "tg-token"
    assert cfg.wardo.poll_interval == 30
    assert cfg.wardo.stall_interval == 120
    assert cfg.wardo.check_interval == 15
    assert cfg.wardo.ping_schedule == "0 9 * * *"
    assert cfg.wardo.allowed_user_id == 42
    assert cfg.wardo.repositories == [config.Repository(repo="x/y",
                                                        components=[config.Component(name="core", paths=["src/"]),
                                                                    config.Component(name="docs", paths=["docs/"])],
                                                        title_filters=["^Backport"],
                                                        label_filters=["pr-backport"])]


def test_load_defaults(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(MINIMAL_YAML)
    cfg = config.load(str(path))
    assert cfg.wardo.poll_interval == 60
    assert cfg.wardo.stall_interval == 600
    assert cfg.wardo.check_interval == 60
    assert cfg.wardo.repositories == [config.Repository(repo="x/y",
                                                        components=[config.Component(name="core", paths=["src/"])],
                                                        title_filters=[], label_filters=[])]
