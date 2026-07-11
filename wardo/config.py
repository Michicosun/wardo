import dataclasses

import yaml


@dataclasses.dataclass
class Repository:
    repo: str
    paths: list[str]


@dataclasses.dataclass
class GithubConfig:
    token: str


@dataclasses.dataclass
class TelegramConfig:
    token: str


@dataclasses.dataclass
class WatcherConfig:
    poll_interval: int
    repositories: list[Repository]


@dataclasses.dataclass
class ConsoleConfig:
    allowed_user_id: int


@dataclasses.dataclass
class Config:
    github: GithubConfig
    telegram: TelegramConfig
    watcher: WatcherConfig
    console: ConsoleConfig


def load(path = "config.yaml"):
    with open(path) as f:
        raw = yaml.safe_load(f)

    gh, tg, w, c = raw["github"], raw["telegram"], raw["watcher"], raw["console"]

    return Config(
        github=GithubConfig(
            token=gh["token"],
        ),
        telegram=TelegramConfig(
            token=tg["token"],
        ),
        watcher=WatcherConfig(
            poll_interval=int(w.get("poll_interval", 60)),
            repositories=[Repository(repo=r["repo"], paths=list(r["paths"])) for r in w["repositories"]],
        ),
        console=ConsoleConfig(
            allowed_user_id=int(c["allowed_user_id"]),
        ),
    )
