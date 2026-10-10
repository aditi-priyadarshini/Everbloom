"""Short lived, process-local cache for public data only (never for orders/auth)."""
from copy import deepcopy
from threading import RLock
from time import monotonic
import os

_lock = RLock()
_cache = {}


def cached(key, supplier):
    try: ttl = max(0, min(120, int(os.environ.get('PUBLIC_CACHE_TTL', '30'))))
    except ValueError: ttl = 30
    # Development and tests should see changes immediately.
    if not (os.environ.get('VERCEL') or os.environ.get('APP_ENV') == 'production') or ttl == 0:
        return supplier()
    with _lock:
        entry = _cache.get(key)
        if entry and entry[0] > monotonic():
            return deepcopy(entry[1])
    value = supplier()
    with _lock:
        _cache[key] = (monotonic() + ttl, deepcopy(value))
    return value


def invalidate(*keys):
    with _lock:
        for key in keys: _cache.pop(key, None)
