"""Amazon.ae (UAE) availability check for launch candidates.

The UAE is the primary launch marketplace: products with demand already
confirmed on US/UK/DE are launched on amazon.ae first. Keepa does not track
amazon.ae, so the check goes straight to the storefront:

- HTTP 404 for ``/dp/<ASIN>``  -> the ASIN is not listed in the UAE
  (``not_listed`` — the niche is free, prime launch candidate);
- HTTP 200 -> already sold there (``listed``); the current AED price is
  extracted from the page when possible;
- CAPTCHA / throttling -> ``blocked`` (retry later or verify by hand).

Amazon throttles scrapers, so requests are spaced out and the volume should
stay small: check only BUY/WATCH candidates, not whole search results.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

UAE_BASE_URL = "https://www.amazon.ae/dp/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Price extraction patterns, most reliable first.
_PRICE_PATTERNS = [
    re.compile(r'"priceAmount"\s*:\s*([0-9]+(?:\.[0-9]+)?)'),
    re.compile(r'class="a-offscreen">\s*AED\s*(?:&nbsp;|\s)*([0-9][0-9,]*(?:\.[0-9]+)?)'),
    re.compile(r'AED\s*(?:&nbsp;|\s)*([0-9][0-9,]*(?:\.[0-9]+)?)'),
]

_CAPTCHA_MARKERS = ("api-services-support@amazon.com", "Robot Check", "validateCaptcha")


def _extract_price_aed(html: str) -> float | None:
    for pattern in _PRICE_PATTERNS:
        m = pattern.search(html)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def check_asin(
    asin: str,
    *,
    client: httpx.Client | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    """Check one ASIN on amazon.ae. Returns status + price (see module doc)."""
    own_client = client is None
    cli = client or httpx.Client(follow_redirects=True, timeout=timeout)
    url = f"{UAE_BASE_URL}{asin}"
    result: dict[str, Any] = {
        "asin": asin,
        "url": url,
        "status": "error",
        "http_status": None,
        "price_aed": None,
    }
    try:
        resp = cli.get(url, headers=_HEADERS)
    except httpx.HTTPError as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result
    finally:
        if own_client:
            cli.close()

    result["http_status"] = resp.status_code
    if resp.status_code == 404:
        result["status"] = "not_listed"
    elif resp.status_code in (503, 429) or any(m in resp.text for m in _CAPTCHA_MARKERS):
        result["status"] = "blocked"
    elif resp.status_code == 200:
        result["status"] = "listed"
        result["price_aed"] = _extract_price_aed(resp.text)
    else:
        result["error"] = f"unexpected HTTP {resp.status_code}"
    return result


def check_asins(asins: list[str], *, delay_s: float = 1.5) -> dict[str, Any]:
    """Check several ASINs on amazon.ae with polite spacing between requests.

    A ``blocked`` (anti-bot) answer is retried once with a fresh connection
    after a longer pause; a block that persists means "verify manually",
    not "absent from the UAE".
    """
    checks: list[dict[str, Any]] = []
    with httpx.Client(follow_redirects=True, timeout=20.0) as client:
        for i, asin in enumerate(asins):
            if i:
                time.sleep(delay_s)
            result = check_asin(asin, client=client)
            if result["status"] == "blocked":
                time.sleep(max(delay_s * 3, 5.0))
                result = check_asin(asin)  # fresh client = fresh connection
            checks.append(result)
    summary = {"listed": 0, "not_listed": 0, "blocked": 0, "error": 0}
    for c in checks:
        summary[c["status"]] = summary.get(c["status"], 0) + 1
    return {"marketplace": "AE (amazon.ae)", "summary": summary, "checks": checks}
