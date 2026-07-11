import logging
import sys

from .config import config
from .services import console, pinger, watcher

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    stream=sys.stdout)

cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
watcher.Watcher(cfg).start()
pinger.Pinger(cfg).start()
console.Console(cfg).serve()
