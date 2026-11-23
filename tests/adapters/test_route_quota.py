"""La cuota exportada usa ventanas locales y no expone credenciales."""

from nafta2go.adapters.route_cache import RouteCache


def test_quota_uses_sliding_windows_and_never_exposes_credentials():
    now = [0]
    cache = RouteCache(ttl=0, per_minute=2, per_day=3, clock=lambda: now[0])
    cache.get("route", "private-credential", lambda: 1)
    assert cache.quota_snapshot() == {"remaining_day": 2, "remaining_minute": 1}
    now[0] = 61
    assert cache.quota_snapshot() == {"remaining_day": 2, "remaining_minute": 2}
    now[0] = 86401
    assert cache.quota_snapshot() == {"remaining_day": 3, "remaining_minute": 2}
