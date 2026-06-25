"""Тонкий клиент Keepa API с обработкой rate-limit и retry.

Использование:
    client = KeepaClient(api_key)
    products = client.product(domain=1, asins=["B07XYZ...", ...], offers=20)
    sellers  = client.seller(domain=1, seller_ids=["A1234..."])
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import time
from typing import Any

import requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

log = logging.getLogger(__name__)

BASE_URL = "https://api.keepa.com"

# domain -> human name
DOMAINS = {
    1: "US", 2: "UK", 3: "DE", 4: "FR", 5: "JP", 6: "CA",
    8: "IT", 9: "ES", 10: "IN", 11: "MX", 12: "BR",
    13: "AU", 14: "NL", 15: "SE", 16: "PL", 17: "TR", 18: "SG", 19: "BE",
}

# CSV array indices (Keepa product.csv)
CSV = {
    "AMAZON": 0,
    "NEW": 1,
    "USED": 2,
    "SALES": 3,            # BSR
    "LIST_PRICE": 4,
    "COLLECTIBLE": 5,
    "REFURBISHED": 6,
    "NEW_FBM_SHIPPING": 7,
    "LIGHTNING_DEAL": 8,
    "WAREHOUSE": 9,
    "NEW_FBA": 10,
    "COUNT_NEW": 11,
    "COUNT_USED": 12,
    "COUNT_REFURBISHED": 13,
    "COUNT_COLLECTIBLE": 14,
    "EXTRA_INFO_UPDATES": 15,
    "RATING": 16,
    "COUNT_REVIEWS": 17,
    "BUY_BOX_SHIPPING": 18,
    "USED_NEW_SHIPPING": 19,
    "USED_VERY_GOOD_SHIPPING": 20,
    "USED_GOOD_SHIPPING": 21,
    "USED_ACCEPTABLE_SHIPPING": 22,
    "COLLECTIBLE_NEW_SHIPPING": 23,
    "REFURBISHED_SHIPPING": 27,
    "EBAY_NEW_SHIPPING": 28,
    "EBAY_USED_SHIPPING": 29,
    "TRADE_IN": 30,
    "RENT": 31,
}


class KeepaError(Exception):
    pass


class KeepaRateLimitError(KeepaError):
    pass


class KeepaClient:
    """Минималистичный клиент с авто-ожиданием при нехватке токенов."""

    def __init__(self, api_key: str, sleep_between: float = 4.0):
        self.api_key = api_key
        self.sleep_between = sleep_between  # секунд между запросами (Premium ~ 20/min -> 3 сек безопасно)
        self.tokens_left: int | None = None
        self.refill_in_ms: int | None = None
        self.session = requests.Session()

    # -- low-level GET ------------------------------------------------------
    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=60),
        retry=retry_if_exception_type((requests.RequestException, KeepaRateLimitError)),
        reraise=True,
    )
    def _get(self, path: str, params: dict[str, Any]) -> dict:
        params = {"key": self.api_key, **params}
        url = f"{BASE_URL}/{path}"
        log.debug("GET %s params=%s", url, {k: v for k, v in params.items() if k != "key"})
        r = self.session.get(url, params=params, timeout=120)
        if r.status_code == 429:
            raise KeepaRateLimitError("HTTP 429")
        r.raise_for_status()
        data = r.json()

        self.tokens_left = data.get("tokensLeft")
        self.refill_in_ms = data.get("refillIn")

        # Если токенов меньше нужного — ждём пополнения и сигналим
        if self.tokens_left is not None and self.tokens_left < 0:
            wait_s = max((self.refill_in_ms or 60000) / 1000.0, 1.0) + 1
            log.warning("tokensLeft < 0, sleeping %.1fs", wait_s)
            time.sleep(wait_s)
            raise KeepaRateLimitError("tokens depleted, will retry after sleep")

        time.sleep(self.sleep_between)
        return data

    # -- public endpoints ---------------------------------------------------
    def product(
        self,
        domain: int,
        asins: list[str],
        *,
        history: int = 1,
        stats: int = 90,
        offers: int = 0,
        buybox: int = 1,
        rating: int = 1,
    ) -> list[dict]:
        """Batch до 100 ASIN. Возвращает список product-объектов."""
        results = []
        for i in range(0, len(asins), 100):
            chunk = asins[i : i + 100]
            data = self._get(
                "product",
                {
                    "domain": domain,
                    "asin": ",".join(chunk),
                    "history": history,
                    "stats": stats,
                    "offers": offers,
                    "buybox": buybox,
                    "rating": rating,
                },
            )
            results.extend(data.get("products", []))
            log.info(
                "products batch %d-%d done, tokensLeft=%s",
                i, i + len(chunk), self.tokens_left,
            )
        return results

    def product_finder(self, domain: int, selection: dict, *, page: int = 0, per_page: int = 1000) -> list[str]:
        """Возвращает список ASIN, удовлетворяющих selection-фильтру."""
        sel = {**selection, "page": page, "perPage": per_page}
        data = self._get("query", {"domain": domain, "selection": json.dumps(sel)})
        return data.get("asinList", []) or []

    def seller(self, domain: int, seller_ids: list[str]) -> dict[str, dict]:
        """Batch до 100 seller_id. Возвращает {seller_id: seller_obj}."""
        out: dict[str, dict] = {}
        for i in range(0, len(seller_ids), 100):
            chunk = seller_ids[i : i + 100]
            data = self._get("seller", {"domain": domain, "seller": ",".join(chunk)})
            out.update(data.get("sellers") or {})
            log.info("sellers batch %d-%d, tokensLeft=%s", i, i + len(chunk), self.tokens_left)
        return out

    def category_lookup(self, domain: int, parent_id: int = 0) -> list[dict]:
        """Вернёт список под-категорий для parent_id. parent_id=0 = корни."""
        data = self._get("category", {"domain": domain, "category": parent_id})
        cats = data.get("categories") or {}
        return list(cats.values())


# ===== CLI helpers ========================================================
def _cmd_categories(args):
    client = KeepaClient(os.environ["KEEPA_API_KEY"])
    cats = client.category_lookup(args.domain, args.parent)
    for c in cats:
        print(f"  {c.get('catId'):<14} {c.get('name')}  (products: {c.get('productCount')})")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    p = argparse.ArgumentParser(prog="keepa_client", description="Keepa helper CLI")
    sp = p.add_subparsers(dest="cmd", required=True)

    pc = sp.add_parser("categories", help="List sub-categories")
    pc.add_argument("--domain", type=int, default=1)
    pc.add_argument("--parent", type=int, default=0, help="0 = root")
    pc.set_defaults(func=_cmd_categories)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
