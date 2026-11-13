"""Caché LRU volátil y cupo local por credencial; sin persistencia ni reintentos."""

from collections import Counter, OrderedDict, defaultdict, deque
from copy import deepcopy
from math import ceil
from threading import Lock
from time import monotonic

from nafta2go.adapters.routing import ProviderUnavailable, QuotaExceeded

# Cubre el timeout de conexión más el de lectura del cliente de OpenRouteService (5 + 15 s).
FETCH_WAIT_SECONDS = 20


class RouteCache:
    def __init__(self, ttl=300, capacity=128, per_minute=30, per_day=450, clock=monotonic):
        values = (ttl, capacity, per_minute, per_day)
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("La configuración de rutas requiere enteros")
        if not (0 <= ttl <= 3600 and 1 <= capacity <= 1024 and 1 <= per_minute <= per_day <= 10000):
            raise ValueError("Configuración de caché o cupo fuera de rango")
        self.ttl, self.capacity = ttl, capacity
        self.per_minute, self.per_day = per_minute, per_day
        self.clock = clock
        self._entries = OrderedDict()
        self._requests = defaultdict(deque)
        self._blocked = {}
        self._state = Lock()
        self._inflight = {}
        self._metrics = Counter(hits=0, misses=0, requests=0, errors=0, limited=0, busy=0)

    def snapshot(self):
        with self._state:
            return {**self._metrics, "entries": len(self._entries)}

    def _lookup(self, key):
        now = self.clock()
        for expired in [k for k, (until, _) in self._entries.items() if until <= now]:
            del self._entries[expired]
        if key in self._entries:
            self._entries.move_to_end(key)
            self._metrics["hits"] += 1
            return deepcopy(self._entries[key][1])
        return None

    def _allow(self, scope):
        now = self.clock()
        history = self._requests[scope]
        while history and history[0] <= now - 86400:
            history.popleft()
        delay = max(0, self._blocked.get(scope, 0) - now)
        if len(history) >= self.per_day:
            delay = max(delay, history[0] + 86400 - now)
        if len(history) >= self.per_minute:
            delay = max(delay, history[-self.per_minute] + 60 - now)
        if delay > 0:
            self._metrics["limited"] += 1
            raise QuotaExceeded("Cupo local de rutas agotado", retry_after_seconds=ceil(delay))
        history.append(now)
        self._metrics["requests"] += 1

    def get(self, key, scope, load):
        """Devuelve (valor, hit). El cargador debe devolver un valor validado, no None."""
        key = (scope, key)
        with self._state:
            value = self._lookup(key)
            if value is not None:
                return value, True
        # Un lock por clave evita llamadas duplicadas sin frenar faltantes de otras rutas.
        fetch = self._join_fetch(key)
        if not fetch.acquire(timeout=FETCH_WAIT_SECONDS):
            with self._state:
                self._metrics["busy"] += 1
            self._leave_fetch(key)
            raise ProviderUnavailable("Proveedor de rutas ocupado")
        try:
            with self._state:
                value = self._lookup(key)
                if value is not None:
                    return value, True
                self._metrics["misses"] += 1
                self._allow(scope)
            try:
                value = load()
                if value is None:
                    raise ProviderUnavailable("El proveedor no devolvió una matriz")
            except Exception as exc:
                with self._state:
                    self._metrics["errors"] += 1
                    if isinstance(exc, QuotaExceeded):
                        delay = 60 if exc.retry_after_seconds is None else exc.retry_after_seconds
                        self._blocked[scope] = self.clock() + delay
                raise
            with self._state:
                if self.ttl:
                    self._entries[key] = (self.clock() + self.ttl, deepcopy(value))
                    while len(self._entries) > self.capacity:
                        self._entries.popitem(last=False)
            return deepcopy(value), False
        finally:
            fetch.release()
            self._leave_fetch(key)

    def _join_fetch(self, key):
        with self._state:
            lock, waiting = self._inflight.get(key, (Lock(), 0))
            self._inflight[key] = (lock, waiting + 1)
            return lock

    def _leave_fetch(self, key):
        with self._state:
            lock, waiting = self._inflight[key]
            if waiting == 1:
                del self._inflight[key]
            else:
                self._inflight[key] = (lock, waiting - 1)
