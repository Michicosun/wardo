import dataclasses

import yaml


@dataclasses.dataclass
class Component:
    name: str
    paths: list[str]


@dataclasses.dataclass
class Repository:
    repo: str
    components: list[Component]
    title_filters: list[str]
    label_filters: list[str]


@dataclasses.dataclass
class GithubConfig:
    token: str


@dataclasses.dataclass
class TelegramConfig:
    token: str


@dataclasses.dataclass
class WardoConfig:
    poll_interval: int
    ping_schedule: str
    allowed_user_id: int
    repositories: list[Repository]


@dataclasses.dataclass
class Config:
    github: GithubConfig
    telegram: TelegramConfig
    wardo: WardoConfig


def load(path: str = "config.yaml") -> Config:
    with open(path) as f:
        raw = yaml.safe_load(f)

    gh, tg, w = raw["github"], raw["telegram"], raw["wardo"]

    return Config(
        github=GithubConfig(
            token=gh["token"],
        ),
        telegram=TelegramConfig(
            token=tg["token"],
        ),
        wardo=WardoConfig(
            poll_interval=int(w.get("poll_interval", 60)),
            ping_schedule=w["ping_schedule"],
            allowed_user_id=int(w["allowed_user_id"]),
            repositories=[Repository(repo=r["repo"],
                                     components=[Component(name=name, paths=list(paths))
                                                 for name, paths in r["components"].items()],
                                     title_filters=list(r.get("title_filters", list())),
                                     label_filters=list(r.get("label_filters", list())))
                          for r in w["repositories"]],
        ),
    )
