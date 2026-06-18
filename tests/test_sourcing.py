"""Offline tests for the China-sourcing skill (no network)."""

from __future__ import annotations

import pytest
from openpyxl import load_workbook


@pytest.fixture()
def product():
    return {
        "asin": "B0FRIDGE01",
        "title": "Mini Fridge 4L portable cooler warmer",
        "brand": "GoldApple",
        "image_url": "https://img.example/fridge.jpg",
        "reference_price": 54.0,
        "currency": "USD",
        "query_zh": "迷你冰箱 4升 便携",
    }


def test_normalize_platforms():
    from keepa_mcp import china_sourcing as cs

    assert cs.normalize_platforms(["PDD", "ali", "1688", "ali"]) == ["pinduoduo", "alibaba", "1688"]
    # Unknown names are dropped; empty falls back to the default order.
    assert cs.normalize_platforms(["nonsense"]) == cs.DEFAULT_PLATFORM_ORDER
    assert cs.normalize_platforms(None) == cs.normalize_platforms()


def test_build_search_plan(product):
    from keepa_mcp import china_sourcing as cs

    plan = cs.build_search_plan(product, platforms=["1688", "alibaba", "taobao"])
    by_platform = {p["platform"]: p for p in plan["platforms"]}

    # Chinese platforms use the translated query; Alibaba uses the source query.
    assert by_platform["1688"]["query_is_chinese"] is True
    assert "s.1688.com" in by_platform["1688"]["search_url"]
    assert by_platform["alibaba"]["query_is_chinese"] is False
    assert "alibaba.com/trade/search" in by_platform["alibaba"]["search_url"]
    # Query is URL-encoded (Chinese -> %XX, spaces -> %20).
    assert "%" in by_platform["taobao"]["search_url"]
    # We supplied query_zh, so no translation is still pending.
    assert plan["needs_translation"] is False
    # Image-search hint surfaces when an image and a platform image search exist.
    assert "image" in (by_platform["1688"]["notes"] or "")


def test_build_search_plan_needs_translation():
    from keepa_mcp import china_sourcing as cs

    plan = cs.build_search_plan({"title": "garlic press"}, platforms=["1688", "alibaba"])
    assert plan["needs_translation"] is True
    note = {p["platform"]: p["notes"] for p in plan["platforms"]}["1688"]
    assert "translate" in (note or "").lower()


def test_score_match_image_confirmed(product):
    from keepa_mcp import china_sourcing as cs

    # A Chinese-only title would not text-match, but image confirmation wins.
    res = cs.score_match(product, {"title": "迷你小冰箱车载", "image_confirmed": True})
    assert res["match_type"] == "EXACT"
    assert res["image_confirmed"] is True


def test_score_match_text(product):
    from keepa_mcp import china_sourcing as cs

    exact = cs.score_match(product, {"title_en": "Mini Fridge 4L portable cooler warmer"})
    assert exact["match_type"] == "EXACT"
    assert exact["match_score"] >= 0.9

    similar = cs.score_match(product, {"title_en": "Large 30L camping cooler box"})
    assert similar["match_type"] == "SIMILAR"
    assert similar["match_score"] < 0.9


def test_to_usd():
    from keepa_mcp import china_sourcing as cs
    from keepa_mcp import config

    assert cs.to_usd(100, "USD") == 100.0
    assert cs.to_usd(100, "CNY") == round(100 * config.CHINA_USD_PER_CNY, 2)
    # Symbols and blanks: ¥ -> CNY, blank defaults to CNY.
    assert cs.to_usd(100, "¥") == cs.to_usd(100, "CNY")
    assert cs.to_usd(100, None) == cs.to_usd(100, "CNY")
    assert cs.to_usd(None, "USD") is None


def test_estimate_margin(product):
    from keepa_mcp import china_sourcing as cs

    econ = cs.estimate_margin(
        {"unit_price": 10, "currency": "USD"},
        reference_price=50,
        reference_currency="USD",
        freight_pct=0.2,
    )
    assert econ["unit_price_usd"] == 10.0
    assert econ["landed_cost_usd"] == 12.0  # 10 * 1.2
    assert econ["margin_abs_usd"] == 38.0
    assert econ["margin_pct"] == round(38 / 50, 3)


def test_rank_offers_ordering(product):
    from keepa_mcp import china_sourcing as cs

    offers = [
        {"platform": "taobao", "title_en": "6L car fridge", "unit_price": 120, "currency": "CNY"},
        {"platform": "1688", "title_en": "Mini Fridge 4L portable cooler warmer",
         "unit_price": 85, "currency": "CNY", "image_confirmed": True},
        {"platform": "alibaba", "title_en": "Mini Fridge 4L", "unit_price": 13.0, "currency": "USD"},
    ]
    ranked = cs.rank_offers(product, offers, freight_pct=0.1)
    assert ranked["offer_count"] == 3
    assert ranked["exact_count"] >= 1
    # EXACT offer ranks first.
    assert ranked["offers"][0]["match_type"] == "EXACT"
    assert ranked["best_exact"] is not None
    assert ranked["best_exact"]["landed_cost_usd"] is not None
    assert ranked["asin"] == "B0FRIDGE01"


def test_ensure_ranked_raw_and_prescored(product):
    from keepa_mcp import china_sourcing as cs

    # Raw item -> gets scored.
    raw = {"product": product, "offers": [{"title_en": "Mini Fridge 4L portable cooler warmer",
                                           "unit_price": 80, "currency": "CNY"}]}
    out = cs.ensure_ranked(raw)
    assert out["offers"][0]["match_type"] in {"EXACT", "SIMILAR"}

    # Already-ranked result -> summary preserved/recomputed.
    pre = cs.rank_offers(product, raw["offers"])
    out2 = cs.ensure_ranked(pre)
    assert out2["offer_count"] == 1
    assert out2["product"] == pre["product"]


def test_generate_sourcing_report(product, tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPA_OUTPUT_DIR", str(tmp_path))
    import importlib
    from keepa_mcp import config, reports, china_sourcing
    importlib.reload(config)
    importlib.reload(reports)

    offers = [
        {"platform": "1688", "supplier": "Shenzhen Co", "title": "4L迷你冰箱",
         "title_en": "Mini Fridge 4L portable cooler warmer", "unit_price": 85,
         "currency": "CNY", "moq": 100, "image_confirmed": True, "url": "https://1688/x"},
        {"platform": "alibaba", "supplier": "Ningbo Ltd", "title_en": "Mini cooler 6L",
         "unit_price": 18, "currency": "USD", "moq": 50, "url": "https://ali/y"},
    ]
    res = china_sourcing.rank_offers(product, offers, freight_pct=0.15)
    path = reports.generate_sourcing_report([res], report_name="test sourcing",
                                            query_summary="unit test")
    assert path.exists() and path.suffix == ".xlsx"

    wb = load_workbook(path)
    assert {"Сорсинг", "Сводка"}.issubset(set(wb.sheetnames))
    ws = wb["Сорсинг"]
    headers = [c.value for c in ws[1]]
    assert "Match" in headers and "Landed USD" in headers and "Margin %" in headers
    assert ws.max_row >= 3  # header + 2 offers


def test_generate_sourcing_report_no_offers(product, tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPA_OUTPUT_DIR", str(tmp_path))
    import importlib
    from keepa_mcp import config, reports, china_sourcing
    importlib.reload(config)
    importlib.reload(reports)

    res = china_sourcing.rank_offers(product, [])
    path = reports.generate_sourcing_report([res], report_name="empty")
    assert path.exists()


def test_fetch_page_blocked(monkeypatch):
    import httpx
    from keepa_mcp import china_sourcing as cs

    class _Resp:
        def __init__(self, status, text, url):
            self.status_code = status
            self.text = text
            self.url = url

    monkeypatch.setattr(httpx, "get", lambda *a, **k: _Resp(200, "请输入验证码 captcha", a[0]))
    out = cs.fetch_page("https://s.1688.com/x")
    assert out["blocked"] is True
    assert out["status_code"] == 200

    def _boom(*a, **k):
        raise httpx.ConnectError("blocked by network policy")

    monkeypatch.setattr(httpx, "get", _boom)
    out2 = cs.fetch_page("https://s.1688.com/y")
    assert out2["blocked"] is True
    assert out2["status_code"] is None
    assert "ConnectError" in out2["error"]
