import logging
import sys

from . import config, console, watcher

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                    stream=sys.stdout)

cfg = config.load(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
watcher.Watcher(cfg).start()
console.Console(cfg).serve()
