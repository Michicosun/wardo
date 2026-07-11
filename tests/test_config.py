from wardo import config

YAML = """
github:
  token: gh-token
telegram:
  token: tg-token
watcher:
  poll_interval: 30
  repositories:
    - repo: x/y
      paths:
        - src/
        - docs/
console:
  allowed_user_id: 42
"""


def test_load(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(YAML)
    cfg = config.load(str(path))
    assert cfg.github.token == "gh-token"
    assert cfg.telegram.token == "tg-token"
    assert cfg.watcher.poll_interval == 30
    assert cfg.watcher.repositories == [config.Repository(repo="x/y", paths=["src/", "docs/"])]
    assert cfg.console.allowed_user_id == 42


def test_load_default_poll_interval(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(YAML.replace("  poll_interval: 30\n", ""))
    assert config.load(str(path)).watcher.poll_interval == 60
