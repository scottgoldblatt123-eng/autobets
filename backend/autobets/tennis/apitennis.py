"""api-tennis.com client (read-only). The key comes from API_TENNIS_KEY. Fixture and live items already carry scores,
match statistics and point-by-point inline, so one stored row per match holds everything the API knows."""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

log = logging.getLogger("autobets.tennis")
BASE = "https://api.api-tennis.com/tennis/"


class ApiTennisError(RuntimeError):
    pass


def wanted(event_type: str) -> bool:
    """Tour-level singles only: ATP, WTA and Challenger, never ITF and never doubles."""
    t = (event_type or "").lower()
    return ("atp" in t or "wta" in t or "challenger" in t) and "itf" not in t and "doubles" not in t


class ApiTennis:
    def __init__(self, key: str | None = None, fetch: Callable[[dict], dict] | None = None):
        self.key = key if key is not None else os.environ.get("API_TENNIS_KEY", "")
        self._fetch = fetch or self._http
        self._last = 0.0

    def _http(self, params: dict) -> dict:
        gap = 0.5 - (time.monotonic() - self._last)      # be gentle: at most 2 requests a second
        if gap > 0:
            time.sleep(gap)
        self._last = time.monotonic()
        url = BASE + "?" + urllib.parse.urlencode({**params, "APIkey": self.key})
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise ApiTennisError(f"HTTP {e.code} from api-tennis") from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise ApiTennisError(f"Cannot read api-tennis: {e}") from None

    def get(self, method: str, **params: Any) -> list | dict:
        if not self.key:
            raise ApiTennisError("API_TENNIS_KEY is not set")
        out = self._fetch({"method": method, **params})
        if str(out.get("success")) not in ("1", "True", "true"):
            raise ApiTennisError(str(out.get("error") or out.get("message") or out)[:200])
        return out.get("result") or []

    def fixtures(self, start: str, stop: str) -> list:
        return [m for m in self.get("get_fixtures", date_start=start, date_stop=stop, timezone="UTC") if wanted(m.get("event_type_type"))]

    def livescore(self) -> list:
        return [m for m in self.get("get_livescore", timezone="UTC") if wanted(m.get("event_type_type"))]


if __name__ == "__main__":       # python -m autobets.tennis.apitennis : check the key and show what the API calls the match types
    api = ApiTennis()
    try:
        types = api.get("get_events")
        print("Event types:", [t.get("event_type_type") for t in types][:30])
        today = time.strftime("%Y-%m-%d", time.gmtime())
        raw = api.get("get_fixtures", date_start=today, date_stop=today)
        kinds: dict[str, int] = {}
        for m in raw:
            kinds[m.get("event_type_type", "?")] = kinds.get(m.get("event_type_type", "?"), 0) + 1
        print("Today's matches by type:", kinds)
        print("Kept (tour singles):", sum(1 for m in raw if wanted(m.get("event_type_type"))))
        if raw:
            print("Example fields:", sorted(raw[0].keys()))
    except ApiTennisError as e:
        print("FAILED:", e)
