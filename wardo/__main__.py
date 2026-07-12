import logging
import sys

from .config import config
from .services import console, pinger, watcher

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    stream=sys.stdout)

cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")

watcher_bot = watcher.Watcher(cfg)
watcher_bot.start()

pinger_bot = pinger.Pinger(cfg)
pinger_bot.start()

console_bot = console.Console(cfg, watcher_bot, pinger_bot)
console_bot.serve()
