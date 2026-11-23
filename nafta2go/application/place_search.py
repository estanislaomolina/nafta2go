"""Búsqueda explícita con caché efímera y cupo compartido por proceso."""

from collections import OrderedDict
from threading import Lock
from time import monotonic

from nafta2go.domain.places import PlaceBusy


class PlaceSearch:
    def __init__(self, provider, clock=monotonic):
        self.provider, self.clock = provider, clock
        self.lock, self.cache, self.next_request = Lock(), OrderedDict(), 0.0

    def search(self, text):
        text = " ".join(text.split())
        if not 3 <= len(text) <= 120 or any(ord(c) < 32 for c in text):
            raise ValueError("Búsqueda inválida")
        if not self.lock.acquire(blocking=False):
            raise PlaceBusy()
        try:
            now, key = self.clock(), text.casefold()
            cached = self.cache.get(key)
            if cached and now - cached[0] < 600:
                self.cache.move_to_end(key)
                return cached[1]
            if now < self.next_request:
                raise PlaceBusy()
            self.next_request = now + 1
            result = tuple(self.provider(text))
            self.cache[key] = (self.clock(), result)
            self.cache.move_to_end(key)
            while len(self.cache) > 64:
                self.cache.popitem(last=False)
            return result
        finally:
            self.lock.release()
