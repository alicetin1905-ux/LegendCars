"""Beleefde HTTP-client: vaste user-agent, pauze tussen requests, retries bij 429/5xx."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


class Fetcher:
    def __init__(self, delay: float = 1.0, retries: int = 3, timeout: int = 30):
        self.delay = delay
        self.retries = retries
        self.timeout = timeout
        self._last = 0.0
        self.requests = 0

    def _wait(self):
        elapsed = time.monotonic() - self._last
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last = time.monotonic()

    def get(self, url: str, accept: str = "text/html") -> str:
        last_err: Exception | None = None
        for attempt in range(self.retries + 1):
            self._wait()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": USER_AGENT,
                    "Accept": accept,
                    "Accept-Language": "nl-BE,nl;q=0.9,en;q=0.8",
                },
            )
            try:
                self.requests += 1
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    return resp.read().decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code not in (429, 500, 502, 503, 504):
                    raise
            except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
                last_err = e
            backoff = 2 ** (attempt + 1)
            log.warning("Fout bij %s (%s), opnieuw over %ss", url, last_err, backoff)
            time.sleep(backoff)
        assert last_err is not None
        raise last_err

    def get_json(self, url: str):
        return json.loads(self.get(url, accept="application/json"))
