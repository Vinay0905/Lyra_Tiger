import time
import hashlib
from collections import OrderedDict
from typing import Any, Optional, Tuple


class TTLCache:
    """Tiny time-aware cache used for intent-classification results (A4)."""

    def __init__(self, ttl_seconds: int = 600, max_entries: int = 256):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()

    def get(self, key: str) -> Optional[Any]:
        item = self._store.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.time() > expires_at:
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key)
        return value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = (time.time() + self.ttl, value)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


class LRUBytesCache:
    """
    Content-addressed LRU cache for synthesized TTS audio (A4).

    Keyed by a hash of ``text + voice`` so identical phrases replay instantly
    without re-running the Kokoro ONNX model.
    """

    def __init__(self, max_entries: int = 64):
        self.max_entries = max_entries
        self._store: "OrderedDict[str, Tuple[bytes, int]]" = OrderedDict()

    @staticmethod
    def make_key(*parts: str) -> str:
        digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
        return digest

    def get(self, key: str) -> Optional[Tuple[bytes, int]]:
        item = self._store.get(key)
        if item is None:
            return None
        self._store.move_to_end(key)
        return item

    def set(self, key: str, data: bytes, sample_rate: int) -> None:
        self._store[key] = (data, sample_rate)
        self._store.move_to_end(key)
        while len(self._store) > self.max_entries:
            self._store.popitem(last=False)


# Shared singletons
from src.config import settings  # noqa: E402

classify_cache = TTLCache(ttl_seconds=settings.classify_cache_ttl)
tts_cache = LRUBytesCache(max_entries=settings.tts_cache_size)
