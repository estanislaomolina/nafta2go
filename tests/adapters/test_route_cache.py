"""TTL, cuota y concurrencia con reloj y cargador controlados, sin red."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest

from nafta2go.adapters.route_cache import RouteCache
from nafta2go.adapters.routing import ProviderUnavailable, QuotaExceeded


def test_hit_keeps_value_until_expiry_and_cannot_poison_storage():
    now = [0]
    cache = RouteCache(ttl=5, clock=lambda: now[0])
    load = Mock(return_value={"distance": [1000]})
    first, hit = cache.get("k", "account", load)
    assert not hit
    first["distance"][0] = 0
    now[0] = 4
    assert cache.get("k", "account", load) == ({"distance": [1000]}, True)
    now[0] = 5
    assert cache.get("k", "account", load)[1] is False
    assert load.call_count == 2


def test_lru_evicts_least_recent_entry():
    cache = RouteCache(capacity=2)
    load = Mock(return_value="valid")
    for key in ("a", "b", "a", "c", "b"):
        cache.get(key, "account", load)
    assert load.call_count == 4
    assert cache.snapshot()["entries"] == 2


def test_disabled_cache_still_respects_budget():
    cache = RouteCache(ttl=0, per_minute=1)
    load = Mock(return_value="valid")
    cache.get("k", "account", load)
    with pytest.raises(QuotaExceeded):
        cache.get("k", "account", load)
    assert load.call_count == 1 and cache.snapshot()["entries"] == 0


def test_rolling_minute_and_daily_windows_and_scopes():
    now = [0]
    cache = RouteCache(per_minute=1, per_day=2, clock=lambda: now[0])
    load = Mock(return_value="valid")
    cache.get("a", "account", load)
    with pytest.raises(QuotaExceeded) as exc:
        cache.get("b", "account", load)
    assert exc.value.retry_after_seconds == 60
    assert cache.get("a", "account", load)[1]  # Un acierto no consume cupo.
    cache.get("other-credential", "other", load)
    now[0] = 60
    cache.get("b", "account", load)
    now[0] = 120
    with pytest.raises(QuotaExceeded) as exc:
        cache.get("c", "account", load)
    assert exc.value.retry_after_seconds == 86280
    now[0] = 86400
    cache.get("c", "account", load)
    assert load.call_count == 4


@pytest.mark.parametrize("error", [ProviderUnavailable("fallo"), None])
def test_errors_and_missing_values_are_never_cached(error):
    cache = RouteCache()
    load = Mock(side_effect=error) if error else Mock(return_value=None)
    for _ in range(2):
        with pytest.raises(ProviderUnavailable):
            cache.get("k", "account", load)
    assert load.call_count == 2
    assert cache.snapshot()["errors"] == 2


def test_provider_cooldown_keeps_cached_data_but_blocks_new_requests():
    now = [0]
    cache = RouteCache(clock=lambda: now[0])
    cache.get("cached", "account", lambda: "valid")
    failing = Mock(side_effect=QuotaExceeded("cuota", retry_after_seconds=120))
    with pytest.raises(QuotaExceeded):
        cache.get("new", "account", failing)
    assert cache.get("cached", "account", lambda: pytest.fail("no consultar"))[1]
    now[0] = 119
    with pytest.raises(QuotaExceeded):
        cache.get("new", "account", failing)
    assert failing.call_count == 1
    now[0] = 120
    assert cache.get("new", "account", lambda: "recovered") == ("recovered", False)


def test_concurrent_identical_calls_only_fetch_once():
    entered, release = Event(), Event()
    calls = []
    cache = RouteCache()

    def load():
        calls.append(1)
        entered.set()
        assert release.wait(1)
        return "valid"

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(cache.get, "k", "account", load)
        assert entered.wait(1)
        second = pool.submit(cache.get, "k", "account", load)
        release.set()
        assert first.result() == ("valid", False)
        assert second.result() == ("valid", True)
    assert len(calls) == 1


def test_slow_fetch_blocks_neither_cache_hits_nor_other_keys():
    entered, release = Event(), Event()
    cache = RouteCache()
    cache.get("warm", "account", lambda: "cached")

    def slow():
        entered.set()
        assert release.wait(10)
        return "loaded"

    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(cache.get, "loading", "account", slow)
        try:
            assert entered.wait(1)
            assert cache.get("warm", "account", lambda: None) == ("cached", True)
            assert cache.get("different", "account", lambda: "new") == ("new", False)
        finally:
            release.set()
        assert task.result() == ("loaded", False)
    assert cache.snapshot()["busy"] == 0
    assert cache._inflight == {}


def test_identical_call_gives_up_after_bounded_wait(monkeypatch):
    monkeypatch.setattr("nafta2go.adapters.route_cache.FETCH_WAIT_SECONDS", 0.05)
    entered, release = Event(), Event()
    cache = RouteCache()

    def slow():
        entered.set()
        assert release.wait(10)
        return "loaded"

    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(cache.get, "k", "account", slow)
        try:
            assert entered.wait(1)
            with pytest.raises(ProviderUnavailable, match="ocupado"):
                cache.get("k", "account", lambda: pytest.fail("no duplicar la llamada"))
        finally:
            release.set()
        assert task.result() == ("loaded", False)
    assert cache.snapshot()["busy"] == 1
    assert cache._inflight == {}


def test_failed_fetch_releases_its_key():
    cache = RouteCache()
    with pytest.raises(ProviderUnavailable):
        cache.get("k", "account", Mock(side_effect=ProviderUnavailable("fallo")))
    assert cache._inflight == {}
    assert cache.get("k", "account", lambda: "valid") == ("valid", False)


@pytest.mark.parametrize(
    "settings", [{"ttl": -1}, {"ttl": 3601}, {"capacity": 0}, {"per_minute": True}, {"per_day": 0}]
)
def test_invalid_settings_are_rejected(settings):
    with pytest.raises(ValueError):
        RouteCache(**settings)
