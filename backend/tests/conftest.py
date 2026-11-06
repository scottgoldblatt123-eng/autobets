import time as _time
import types

import pytest

from autobets.api import demo


@pytest.fixture(autouse=True)
def steady_demo_prices(monkeypatch):
    """Demo prices re-roll every 2-3 seconds of wall-clock time, so a test that reads a price and then trades could straddle a re-roll and
    fail now and then. Freeze the demo feed's clock for the duration of each test (nothing else's clock is touched)."""
    frozen = _time.time()
    monkeypatch.setattr(demo, "time", types.SimpleNamespace(time=lambda: frozen, sleep=_time.sleep))
