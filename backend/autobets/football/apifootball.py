"""API-Football (api-sports.io) client. Read-only. Every response is saved raw to disk as it arrives, so the models
can be rebuilt from our own history later; the key comes from the API_FOOTBALL_KEY environment variable."""
from __future__ import annotations

import hashlib
import logging
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("autobets.football")
HOST = "https://v3.football.api-sports.io"


def current_season(now: time.struct_time | None = None) -> int:
    """European seasons start in August: from July on, the season is named for this year, before that for last year."""
    t = now or time.gmtime()
    return t.tm_year if t.tm_mon >= 7 else t.tm_year - 1


class ApiFootballError(RuntimeError):
    pass


class ApiFootball:
    def __init__(self, key: str | None = None, store_dir: str | None = None, fetch: Callable[[str, dict], dict] | None = None):
        self.key = key if key is not None else os.environ.get("API_FOOTBALL_KEY", "")
        self.store = Path(store_dir) if store_dir else None
        self._fetch = fetch or self._http
        self.last_limits: dict[str, str] = {}      # requests left today / per minute, from the response headers

    def _pace(self) -> None:
        """Stay inside the per-minute allowance: at most about 4 requests a second, and a pause when the headers say it is nearly used up."""
        gap = 0.25 - (time.monotonic() - getattr(self, "_last", 0.0))
        if gap > 0:
            time.sleep(gap)
        try:
            if int(self.last_limits.get("x-ratelimit-remaining", "999")) < 25:
                time.sleep(15)
        except ValueError:
            pass
        self._last = time.monotonic()

    def _http(self, path: str, params: dict) -> dict:
        self._pace()
        url = f"{HOST}/{path}" + (("?" + urllib.parse.urlencode(params)) if params else "")
        req = urllib.request.Request(url, headers={"x-apisports-key": self.key, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                self.last_limits = {k: v for k, v in r.headers.items() if k.lower().startswith("x-ratelimit")}
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise ApiFootballError(f"HTTP {e.code} from API-Football") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise ApiFootballError(f"Cannot reach API-Football: {e}") from None

    def get(self, path: str, _save: bool = True, **params: Any) -> dict:
        if not self.key:
            raise ApiFootballError("API_FOOTBALL_KEY is not set")
        out = self._fetch(path, params)
        errs = out.get("errors")
        if errs:       # the API reports problems (bad key, plan limits) inside a 200 response
            raise ApiFootballError("; ".join(f"{k}: {v}" for k, v in errs.items()) if isinstance(errs, dict) else str(errs))
        if _save:
            try:
                self._save(path, params, out)
            except OSError as e:      # the raw copy is a bonus: never let a disk or permission problem stop the data flowing
                log.warning("could not save raw API-Football response: %s", e)
        return out

    def _save(self, path: str, params: dict, out: dict) -> None:
        if not self.store:
            return
        day = time.strftime("%Y-%m-%d", time.gmtime())
        d = self.store / day
        d.mkdir(parents=True, exist_ok=True)
        tag = hashlib.sha1(json.dumps(params, sort_keys=True).encode()).hexdigest()[:8]
        (d / f"{path.replace('/', '_')}_{time.strftime('%H%M%S', time.gmtime())}_{tag}.json").write_text(json.dumps({"path": path, "params": params, "response": out}))

    def status(self) -> dict:
        """Account, plan and today's request allowance (this call does not count against the daily limit)."""
        r = self.get("status", _save=False).get("response") or {}
        return {"plan": (r.get("subscription") or {}).get("plan"), "active": (r.get("subscription") or {}).get("active"),
                "ends": (r.get("subscription") or {}).get("end"), "used_today": (r.get("requests") or {}).get("current"),
                "limit_day": (r.get("requests") or {}).get("limit_day")}


if __name__ == "__main__":          # python -m autobets.football.apifootball : check the key, plan and what the leagues look like
    api = ApiFootball(store_dir=os.environ.get("AUTOBETS_DATA", "/opt/autobets/data") + "/apifootball")
    try:
        print("Account:", api.status())
        for name, lid in {"Premier League": 39, "Bundesliga": 78, "La Liga": 140, "Serie A": 135, "Ligue 1": 61, "Scottish Premiership": 179}.items():
            r = api.get("fixtures", league=lid, season=current_season(), next=1)
            print(f"{name}: ok, next fixture {(r['response'][0]['teams']['home']['name'] + ' v ' + r['response'][0]['teams']['away']['name']) if r['response'] else 'none listed'}")
        print("Rate limit headers:", api.last_limits)
    except ApiFootballError as e:
        print("FAILED:", e)
