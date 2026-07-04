import asyncio
import ipaddress
import socket
from typing import Awaitable, Callable, TypeVar
from urllib.parse import urlparse

from src.config import settings

T = TypeVar("T")


class PolicyError(Exception):
    """Raised when a navigation/action violates the browser security policy."""


def _is_internal_ip(host: str) -> bool:
    """Best-effort SSRF guard: reject loopback / private / link-local targets."""
    candidates = set()
    try:
        candidates.add(host)
        for info in socket.getaddrinfo(host, None):
            candidates.add(info[4][0])
    except (socket.gaierror, UnicodeError, OSError):
        pass

    for cand in candidates:
        try:
            ip = ipaddress.ip_address(cand)
            if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            continue
    return False


def assert_navigable(url: str) -> None:
    """
    Validate a target URL against the security policy. Raises PolicyError.

    Rules: https/http only; no file://, no internal/loopback IPs; deny-list wins;
    if an allow-list is configured, the host must match it.
    """
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise PolicyError(f"Blocked non-web scheme: '{scheme or 'none'}'")

    host = (parsed.hostname or "").lower()
    if not host:
        raise PolicyError("Blocked URL with no host.")

    deny = settings.browser_deny_hosts
    if any(host == d or host.endswith("." + d) for d in deny):
        raise PolicyError(f"Host '{host}' is on the deny list.")

    allow = settings.browser_allow_hosts
    if allow and not any(host == a or host.endswith("." + a) for a in allow):
        raise PolicyError(f"Host '{host}' is not on the allow list.")

    if _is_internal_ip(host):
        raise PolicyError(f"Blocked internal/loopback target: '{host}'")


async def guarded_execute(action: Callable[[], Awaitable[T]], *, budget_s: float = None) -> T:
    """Run a browser action under a hard time budget (defence-in-depth)."""
    timeout = budget_s if budget_s is not None else settings.browser_action_budget_s
    try:
        return await asyncio.wait_for(action(), timeout=timeout)
    except asyncio.TimeoutError as e:
        raise PolicyError(f"Browser action exceeded {timeout}s budget.") from e
