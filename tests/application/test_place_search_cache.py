"""Caché y admisión de búsquedas sin consultar servicios externos."""

from threading import Event, Thread
from unittest.mock import Mock

import pytest

from nafta2go.application.place_search import PlaceSearch
from nafta2go.domain.places import Place, PlaceBusy


def test_cache_is_bounded_expires_and_reuses_normalized_queries():
    clock = [0.0]
    provider = Mock(return_value=[Place("Lugar", -34.6, -58.4)])
    service = PlaceSearch(provider, lambda: clock[0])
    first = service.search("Corrientes  1234")
    assert service.search("corrientes 1234") == first
    assert provider.call_count == 1
    with pytest.raises(PlaceBusy):
        service.search("Otro lugar")
    clock[0] = 601
    service.search("Corrientes 1234")
    assert provider.call_count == 2
    for n in range(70):
        clock[0] += 2
        service.search(f"Lugar {n}")
    assert len(service.cache) == 64


def test_only_one_provider_lookup_runs_at_a_time():
    entered, release = Event(), Event()

    def provider(_text):
        entered.set()
        assert release.wait(3)
        return []

    service = PlaceSearch(provider)
    worker = Thread(target=lambda: service.search("Un lugar"))
    worker.start()
    try:
        assert entered.wait(2)
        with pytest.raises(PlaceBusy):
            service.search("Otro lugar")
    finally:
        release.set()
        worker.join(2)
    assert not worker.is_alive()


@pytest.mark.parametrize("query", ["ab", "   ", "a" * 121, "ab\x00c"])
def test_invalid_query_never_reaches_the_provider(query):
    provider = Mock()
    with pytest.raises(ValueError):
        PlaceSearch(provider).search(query)
    provider.assert_not_called()
