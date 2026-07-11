# Wardo

If you maintain a large project, you may have noticed that, for some time now, many AI slop PRs have been submitted by contributors. If another maintainer without deep knowledge of a component gets assigned to such a PR and merges it, something may break. This project lets you keep an eye on the components that matter to you.

Wardo is a stateless Telegram bot that watches configured paths in GitHub repositories and notifies the owner about newly opened PRs touching them.

## Quick start

```bash
# fill in deploy/config.yaml: tokens, repos, your user id
docker compose -f deploy/docker-compose.yml up -d --build
docker logs -f wardo
```

## Configuration (`deploy/config.yaml`)

```yaml
github:
  token: ghp_xxxxxxxxxxxx                    # personal access token, public_repo scope

telegram:
  token: "123456789:AA...."                  # from @BotFather

watcher:
  poll_interval: 60                          # seconds between polls
  allowed_user_id: 123456789                 # your Telegram user id
  repositories:
    - repo: ClickHouse/ClickHouse
      paths:                                 # substring or regex
        - src/Processors/QueryPlan/
        - ^src/Storages/MergeTree/.*\.cpp$
```

## Commands (owner only)

By default, Wardo will automatically notify you about new PRs. These commands are just handy.

- `/open [days]` — PRs opened in the last `days` days (default 1) touching watched paths
- `/closed [days]` — PRs merged in the last `days` days (default 1) touching watched paths
- `/help` — command list and watched repos

## Tests

```bash
pip install pytest
python -m pytest tests/
```
