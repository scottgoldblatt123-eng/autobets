"""Minimal Anthropic Messages API client (standard library only, like the data clients). The key comes from ANTHROPIC_API_KEY and is
never logged or included in an error message."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"


class AiError(Exception):
    pass


class Claude:
    def __init__(self, key: str | None = None, model: str | None = None, post=None) -> None:
        self.key = key if key is not None else os.environ.get("ANTHROPIC_API_KEY", "")
        self.model = model or os.environ.get("AUTOBETS_AI_MODEL", DEFAULT_MODEL)
        self._post = post or self._http

    @property
    def enabled(self) -> bool:
        return bool(self.key)

    def _http(self, body: dict) -> dict:
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), method="POST",
                                     headers={"content-type": "application/json", "x-api-key": self.key, "anthropic-version": "2023-06-01"})
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            detail = ""
            try:
                detail = (json.loads(e.read()).get("error") or {}).get("message", "")
            except Exception:
                pass
            raise AiError(f"Claude API HTTP {e.code}" + (f": {detail}" if detail and self.key not in detail else "")) from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            raise AiError(f"Cannot reach the Claude API: {type(e).__name__}") from None

    def message(self, system: str, messages: list[dict], max_tokens: int = 1200) -> dict:
        """-> {'text', 'input_tokens', 'output_tokens', 'model'}"""
        if not self.enabled:
            raise AiError("ANTHROPIC_API_KEY is not set on the server")
        res = self._post({"model": self.model, "max_tokens": max_tokens, "system": system, "messages": messages})
        text = "".join(b.get("text", "") for b in res.get("content", []) if b.get("type") == "text")
        u = res.get("usage") or {}
        return {"text": text, "input_tokens": int(u.get("input_tokens", 0)), "output_tokens": int(u.get("output_tokens", 0)), "model": res.get("model", self.model)}
