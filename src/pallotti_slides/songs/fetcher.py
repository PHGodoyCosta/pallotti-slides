"""The single HTTP page fetcher of the songs package (downloaders and repertoire).

Cifra Club blocks ``httpx`` by TLS fingerprint (403). When a response looks blocked (403/429 or an
"Access Denied" page) the request is repeated once with ``curl_cffi`` impersonating a browser.
Same 15 s timeout, no parallelism, and a short pause between requests to the same site.
"""

import threading
import time
from collections.abc import Callable
from typing import NamedTuple

import httpx
from curl_cffi import requests as curl_requests

from pallotti_slides.domain.errors import PallottiError

USER_AGENT = "PallottiSlides/0.1 (gerador de slides paroquial; +https://github.com/PHGodoyCosta)"
TIMEOUT_SECONDS = 15.0
REQUEST_PAUSE_SECONDS = 1.0
BLOCKED_STATUSES = frozenset({403, 429})


class DownloadError(PallottiError):
    """The lyrics page could not be downloaded or understood; the message is for the user."""


class HttpReply(NamedTuple):
    status: int
    text: str


Transport = Callable[[str], HttpReply]
"""Performs one GET; connection failures are raised as ``OSError`` (``ConnectionError``)."""


def httpx_transport(url: str) -> HttpReply:
    """Plain ``httpx`` GET with an identified User-Agent."""
    try:
        response = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "pt-BR,pt;q=0.9"},
            timeout=TIMEOUT_SECONDS,
            follow_redirects=True,
        )
    except httpx.HTTPError as error:
        raise ConnectionError(str(error)) from error
    return HttpReply(response.status_code, response.text)


def browser_transport(url: str) -> HttpReply:
    """``curl_cffi`` GET impersonating Chrome (same TLS fingerprint as a browser)."""
    try:
        response = curl_requests.get(
            url,
            headers={"Accept-Language": "pt-BR,pt;q=0.9"},
            timeout=TIMEOUT_SECONDS,
            allow_redirects=True,
            impersonate="chrome",
        )
    except curl_requests.exceptions.RequestException as error:
        raise ConnectionError(str(error)) from error
    return HttpReply(response.status_code, response.text)


def looks_blocked(reply: HttpReply) -> bool:
    """403/429, or a 200 "Access Denied" interstitial."""
    if reply.status in BLOCKED_STATUSES:
        return True
    return reply.status == 200 and "access denied" in reply.text[:3000].lower()


class PageFetcher:
    """GET a page as text: ``httpx`` first, browser-like ``curl_cffi`` when blocked."""

    def __init__(
        self,
        primary: Transport | None = None,
        fallback: Transport | None = None,
        *,
        pause: float = REQUEST_PAUSE_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._primary = primary or httpx_transport
        self._fallback = fallback or browser_transport
        self._pause = pause
        self._sleep = sleep
        self._clock = clock
        self._last: dict[str, float] = {}
        self._lock = threading.Lock()  # one request at a time, no parallelism

    def get(self, url: str, site: str, advice: str = "cole a letra") -> str:
        """Page text; raises ``DownloadError`` (message in Portuguese) when it cannot be had."""
        with self._lock:
            reply = self._request(self._primary, url, site, advice)
            if looks_blocked(reply):
                reply = self._request(self._fallback, url, site, advice)
        if reply.status == 404:
            raise DownloadError(f"A página não foi encontrada no {site}: {url}")
        if reply.status != 200 or looks_blocked(reply):
            raise DownloadError(
                f"O {site} bloqueou o acesso automático (erro {reply.status}). "
                f"Não consegui baixar; {advice}."
            )
        return reply.text

    def _request(self, transport: Transport, url: str, site: str, advice: str) -> HttpReply:
        self._throttle(site)
        try:
            return transport(url)
        except OSError as error:  # ConnectionError and friends
            raise DownloadError(
                f"Não foi possível acessar o {site} (sem conexão ou site fora do ar). "
                f"Verifique a internet ou {advice}."
            ) from error
        finally:
            self._last[site] = self._clock()

    def _throttle(self, site: str) -> None:
        last = self._last.get(site)
        if last is not None:
            wait = self._pause - (self._clock() - last)
            if wait > 0:
                self._sleep(wait)


_default: PageFetcher | None = None


def default_fetcher() -> PageFetcher:
    """Process-wide fetcher, so the pause between requests holds across all callers."""
    global _default
    if _default is None:
        _default = PageFetcher()
    return _default
