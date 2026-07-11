from dataclasses import dataclass

import yaml


@dataclass
class Repository:
    repo: str
    paths: list[str]


@dataclass
class GithubConfig:
    token: str
    poll_interval: int
    repositories: list[Repository]


@dataclass
class TelegramConfig:
    token: str
    allowed_user_id: int


@dataclass
class Config:
    github: GithubConfig
    telegram: TelegramConfig


def load(path = "config.yaml"):
    with open(path) as f:
        raw = yaml.safe_load(f)

    gh, tg = raw["github"], raw["telegram"]

    return Config(
        github = GithubConfig(
            token = gh["token"],
            poll_interval = int(gh.get("poll_interval", 60)),
            repositories = [Repository(repo = r["repo"], paths = list(r["paths"])) for r in gh["repositories"]],
        ),
        telegram = TelegramConfig(
            token = tg["token"],
            allowed_user_id = int(tg["allowed_user_id"]),
        ),
    )
