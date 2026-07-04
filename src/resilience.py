import asyncio
import random
import time
from collections import defaultdict
from typing import Awaitable, Callable, Dict, TypeVar

try:
    import structlog

    _log = structlog.get_logger("lyra")

    def get_logger():
        return _log
except Exception:  # pragma: no cover - structlog optional at runtime
    import logging

    logging.basicConfig(level=logging.INFO)

    def get_logger():
        return logging.getLogger("lyra")


T = TypeVar("T")

log = get_logger()


class CircuitOpenError(Exception):
    """Raised when a provider's circuit breaker is open (fast-fail)."""


class CircuitBreaker:
    """
    Per-provider breaker: after ``fail_threshold`` consecutive failures the
    circuit opens for ``reset_after`` seconds, fast-failing calls so a hung or
    degraded provider does not stall the whole request path (L3).
    """

    def __init__(self, fail_threshold: int = 4, reset_after: float = 30.0):
        self.fail_threshold = fail_threshold
        self.reset_after = reset_after
        self._failures = 0
        self._opened_at = 0.0

    @property
    def state(self) -> str:
        if self._failures >= self.fail_threshold:
            if time.time() - self._opened_at < self.reset_after:
                return "open"
            return "half-open"
        return "closed"

    def allow(self) -> bool:
        return self.state != "open"

    def record_success(self):
        self._failures = 0
        self._opened_at = 0.0

    def record_failure(self):
        self._failures += 1
        if self._failures >= self.fail_threshold:
            self._opened_at = time.time()


class Metrics:
    """Tiny in-process metrics surface exposed via /metrics (L3)."""

    def __init__(self):
        self.calls: Dict[str, int] = defaultdict(int)
        self.failures: Dict[str, int] = defaultdict(int)
        self.latency_ms: Dict[str, list] = defaultdict(list)
        self.cache_hits: Dict[str, int] = defaultdict(int)

    def record(self, key: str, ms: float, ok: bool):
        self.calls[key] += 1
        if not ok:
            self.failures[key] += 1
        samples = self.latency_ms[key]
        samples.append(round(ms, 1))
        if len(samples) > 200:
            del samples[: len(samples) - 200]

    def hit(self, key: str):
        self.cache_hits[key] += 1

    def snapshot(self) -> dict:
        def pct(vals, p):
            if not vals:
                return 0.0
            s = sorted(vals)
            return s[min(len(s) - 1, int(len(s) * p))]

        return {
            "calls": dict(self.calls),
            "failures": dict(self.failures),
            "cache_hits": dict(self.cache_hits),
            "latency_ms": {
                k: {"p50": pct(v, 0.5), "p95": pct(v, 0.95), "n": len(v)}
                for k, v in self.latency_ms.items()
            },
            "breakers": {k: b.state for k, b in _breakers.items()},
        }


metrics = Metrics()
_breakers: Dict[str, CircuitBreaker] = defaultdict(CircuitBreaker)


async def resilient_call(
    key: str,
    factory: Callable[[], Awaitable[T]],
    *,
    timeout: float = 30.0,
    retries: int = 2,
    base_delay: float = 0.4,
    use_breaker: bool = True,
) -> T:
    """
    Execute ``factory()`` with a bounded timeout, exponential backoff + jitter,
    and a per-key circuit breaker. ``factory`` must be re-callable (it is invoked
    once per attempt).
    """
    breaker = _breakers[key]
    if use_breaker and not breaker.allow():
        metrics.record(key, 0.0, ok=False)
        raise CircuitOpenError(f"Circuit open for '{key}'")

    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        start = time.perf_counter()
        try:
            result = await asyncio.wait_for(factory(), timeout=timeout)
            metrics.record(key, (time.perf_counter() - start) * 1000, ok=True)
            if use_breaker:
                breaker.record_success()
            return result
        except Exception as e:  # noqa: BLE001 - we retry/aggregate deliberately
            last_exc = e
            metrics.record(key, (time.perf_counter() - start) * 1000, ok=False)
            if use_breaker:
                breaker.record_failure()
            log.warning("resilient_call.attempt_failed", key=key, attempt=attempt, error=str(e))
            if attempt < retries:
                delay = base_delay * (2 ** attempt) + random.uniform(0, base_delay)
                await asyncio.sleep(delay)

    assert last_exc is not None
    raise last_exc
