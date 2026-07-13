import logging
import time

import requests
import requests.adapters

log = logging.getLogger("wardo.retries")

ATTEMPTS = 3

RETRIES = requests.adapters.Retry(total=10,
                                  backoff_factor=1,
                                  status_forcelist=[429, 500, 502, 503, 504],
                                  allowed_methods=["GET", "POST"])


def _create_session():
    s = requests.Session()
    s.mount("https://", requests.adapters.HTTPAdapter(max_retries=RETRIES))
    return s


def request(send):
    for attempt in range(ATTEMPTS):
        try:
            return send(_create_session())
        except Exception:
            if attempt == ATTEMPTS - 1:
                raise

            log.warning("request failed (attempt %d/%d), retrying", attempt + 1, ATTEMPTS, exc_info=True)
            time.sleep(2 ** attempt)
