"""Offline tests — exercise analysis + report generation without the Keepa API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta

import numpy as np
import pytest
from openpyxl import load_workbook


@pytest.fixture()
def fake_product():
    """A Keepa-shaped product dict with realistic time-series arrays."""
    now = np.datetime64(datetime(2026, 6, 1))
    times = np.array([now - np.timedelta64(d, "D") for d in range(120, 0, -1)])

    # Falling-then-stable New price around $30, a couple of dips.
    new = np.linspace(34.0, 29.0, len(times))
    new[10] = 24.0  # a dip
    # Improving (decreasing) sales rank with several "sale" drops.
    sales = np.linspace(50000, 15000, len(times))
    sales[::10] = sales[::10] * 0.5  # periodic drops
    offers = np.full(len(times), 8.0)
    rating = np.full(len(times), 4.4)
    reviews = np.linspace(800, 1500, len(times))

    return {
        "asin": "B0TEST1234",
        "title": "Test Wireless Earbuds Pro",
        "brand": "Acme",
        "manufacturer": "Acme Inc",
        "productGroup": "Electronics",
        "categoryTree": [{"name": "Electronics"}, {"name": "Headphones"}],
        "features": ["Bluetooth 5.3", "30h battery", "IPX5 water resistant"],
        "description": "Premium earbuds for everyday use.",
        "numberOfItems": 1,
        "packageWeight": 250,
        "packageLength": 10,
        "packageWidth": 8,
        "packageHeight": 4,
        "variations": [],
        "monthlySold": 1200,
        "buyBoxIsAmazon": False,
        "buyBoxSellerId": "A1SELLER",
        "imagesCSV": "img1.jpg,img2.jpg",
        "data": {
            "NEW": new, "NEW_time": times,
            "AMAZON": new + 1, "AMAZON_time": times,
            "BUY_BOX_SHIPPING": new + 0.5, "BUY_BOX_SHIPPING_time": times,
            "USED": new - 5, "USED_time": times,
            "NEW_FBA": new + 2, "NEW_FBA_time": times,
            "SALES": sales, "SALES_time": times,
            "COUNT_NEW": offers, "COUNT_NEW_time": times,
            "RATING": rating, "RATING_time": times,
            "COUNT_REVIEWS": reviews, "COUNT_REVIEWS_time": times,
        },
    }


def test_build_record(fake_product):
    from keepa_mcp import analysis

    rec = analysis.build_record(fake_product, stats_days=90)
    assert rec["asin"] == "B0TEST1234"
    assert rec["brand"] == "Acme"
    assert rec["category_tree"] == ["Electronics", "Headphones"]

    m = rec["metrics"]
    assert m["pricing"]["new"]["current"] is not None
    assert m["pricing"]["new"]["min"] <= m["pricing"]["new"]["max"]
    assert m["pricing"]["new"]["volatility"] is not None
    assert m["sales_rank"]["drops_90d"] >= 1
    assert m["reviews"]["rating_current"] == pytest.approx(4.4, abs=0.01)
    assert m["demand"]["monthly_sold_estimate"] == 1200


def test_clean_sentinels():
    from keepa_mcp import analysis

    assert analysis._clean(-1) is None
    assert analysis._clean(float("nan")) is None
    assert analysis._clean(None) is None
    assert analysis._clean(3.5) == 3.5


def test_generate_report(fake_product, tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPA_OUTPUT_DIR", str(tmp_path))
    # Reload config so it picks up the patched env var.
    import importlib
    from keepa_mcp import config, reports, analysis
    importlib.reload(config)
    importlib.reload(reports)

    rec = analysis.build_record(fake_product, stats_days=90)
    rec["verdict"] = "BUY"
    rec["confidence"] = "high"
    rec["rationale"] = "Stable price, strong velocity, low competition."

    path = reports.generate_report([rec], report_name="test run", query_summary="unit test")
    assert path.exists()
    assert path.suffix == ".xlsx"

    wb = load_workbook(path)
    assert {"Анализ", "Характеристики", "Сводка"}.issubset(set(wb.sheetnames))
    ws = wb["Анализ"]
    headers = [c.value for c in ws[1]]
    assert "Verdict" in headers and "ASIN" in headers
    # Data row present
    assert ws.max_row >= 2


def test_build_selection_units():
    from keepa_mcp import keepa_client

    sel = keepa_client.build_selection(
        title="earbuds", min_price=10.0, max_price=40.0, min_rating=4.3, min_review_count=500
    )
    assert sel["current_NEW_gte"] == 1000
    assert sel["current_NEW_lte"] == 4000
    assert sel["current_RATING_gte"] == 43
    assert sel["current_COUNT_REVIEWS_gte"] == 500
    assert sel["title"] == "earbuds"


def test_build_selection_extras():
    from keepa_mcp import keepa_client

    sel = keepa_client.build_selection(
        max_offer_count=15,
        min_monthly_sold=300,
        extra_filters={"avg90_SALES_lte": 40000},
    )
    assert sel["current_COUNT_NEW_lte"] == 15
    assert sel["monthlySold_gte"] == 300
    assert sel["avg90_SALES_lte"] == 40000


def test_normalize_domain():
    from keepa_mcp import keepa_client

    assert keepa_client.normalize_domain("UK") == "GB"
    assert keepa_client.normalize_domain("uk") == "GB"
    assert keepa_client.normalize_domain("US") == "US"
    for market in ("US", "UK", "DE", "FR", "IT", "ES"):
        code = keepa_client.normalize_domain(market)
        assert code in keepa_client.DOMAIN_IDS
        assert code in keepa_client.DOMAIN_TLDS
    with pytest.raises(ValueError):
        keepa_client.normalize_domain("XX")


def test_domain_aware_urls(fake_product):
    from keepa_mcp import analysis

    rec = analysis.build_record(fake_product, domain="UK")
    assert rec["marketplace"] == "GB"
    assert rec["url"] == "https://www.amazon.co.uk/dp/B0TEST1234"
    assert rec["keepa_url"] == "https://keepa.com/#!product/2-B0TEST1234"


def test_auto_verdict_buy(fake_product):
    from keepa_mcp import analysis

    rec = analysis.auto_verdict(analysis.build_record(fake_product, stats_days=90))
    assert rec["verdict"] in {"BUY", "WATCH", "SKIP"}
    # This fixture is a healthy product: steady price, sales drops, 4.4 rating.
    assert rec["verdict"] == "BUY"
    assert rec["rationale"]
    assert rec["confidence"] in {"high", "medium", "low"}


def test_auto_verdict_skip():
    from keepa_mcp import analysis

    bad = {
        "metrics": {
            "pricing": {"new": {"volatility": 0.8}},
            "sales_rank": {"drops_30d": 0},
            "competition": {"offer_count": {"current": 40}, "buy_box_is_amazon": True},
            "reviews": {"rating_current": 3.5, "review_count_current": 20},
            "demand": {"monthly_sold_estimate": 10},
        }
    }
    rec = analysis.auto_verdict(bad)
    assert rec["verdict"] == "SKIP"


def test_env_docs_loading(tmp_path, monkeypatch):
    import importlib

    monkeypatch.delenv("KEEPA_API_KEY", raising=False)
    from keepa_mcp import config

    (tmp_path / "ENV DOCS").write_text(
        "# Keepa key\nKEEPA_API_KEY=abc123testkey\n", encoding="utf-8"
    )
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    config._load_env_docs()
    assert os.environ.get("KEEPA_API_KEY") == "abc123testkey"
    monkeypatch.delenv("KEEPA_API_KEY", raising=False)

    # Bare-token format
    (tmp_path / "ENV DOCS").write_text("a" * 64 + "\n", encoding="utf-8")
    config._load_env_docs()
    assert os.environ.get("KEEPA_API_KEY") == "a" * 64
    monkeypatch.delenv("KEEPA_API_KEY", raising=False)
    importlib.reload(config)


def test_auto_search_config(tmp_path):
    import json

    from keepa_mcp import auto_search

    cfg = tmp_path / "auto_searches.json"
    cfg.write_text(
        json.dumps(
            {
                "searches": [
                    {
                        "name": "test",
                        "domain": "UK",
                        "filters": {"title": "pet", "min_price": 10},
                        "limit": 5,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    searches = auto_search.load_searches(cfg)
    assert searches[0]["name"] == "test"
    assert searches[0]["domain"] == "UK"
    assert searches[0]["limit"] == 5

    cfg.write_text(
        json.dumps({"searches": [{"name": "bad", "filters": {"bogus_key": 1}}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="bogus_key"):
        auto_search.load_searches(cfg)

    with pytest.raises(FileNotFoundError):
        auto_search.load_searches(tmp_path / "missing.json")


def test_repo_auto_searches_file_valid():
    from keepa_mcp import auto_search, config

    searches = auto_search.load_searches(config.AUTO_SEARCH_FILE)
    assert len(searches) >= 1
    for s in searches:
        from keepa_mcp import keepa_client

        keepa_client.normalize_domain(s["domain"])  # must not raise
        keepa_client.build_selection(**s["filters"], extra_filters=s["extra_filters"])


def test_sourcing_links():
    from keepa_mcp import sourcing

    kw = sourcing.keyword_phrase("Acme Stainless Steel Garlic Press 2 Pack", "Acme")
    assert "acme" not in kw.lower()  # brand dropped
    assert "stainless" in kw and "steel" in kw  # product nouns kept
    assert "2" not in kw.split()  # pure number dropped

    # The product noun is the title tail, not the brand-line front.
    oxo = sourcing.keyword_phrase("OXO Good Grips Stainless Steel Garlic Press", "OXO")
    assert oxo.endswith("garlic press")
    assert "good" not in oxo and "grips" not in oxo
    # A trailing qualifier clause is cut before keywords are taken.
    clause = sourcing.keyword_phrase("Silicone Baking Mat, Non-Stick - 2 Pack")
    assert clause.endswith("baking mat")

    url = sourcing.alibaba_search_url("garlic press")
    assert url == "https://www.alibaba.com/trade/search?SearchText=garlic+press"
    assert sourcing.alibaba_search_url("") is None

    links = sourcing.sourcing_links("Foldable Dog Ramp", "PetCo", "Pet Supplies")
    assert links["alibaba_url"].startswith("https://www.alibaba.com/trade/search?")
    assert "Pet+Supplies" in links["alibaba_category_url"]


def test_discovery_signals(fake_product):
    from keepa_mcp import analysis

    rec = analysis.build_record(fake_product, stats_days=90)
    disc = rec["discovery"]
    # Healthy fixture: monthly 1200 → Bestseller; improving rank → Rising.
    assert "Bestseller" in disc["tags"]
    assert disc["momentum_score"] > 0
    assert rec["metrics"]["sales_rank"]["trend_pct"] is not None
    # Sourcing + image links are attached to every record.
    assert rec["alibaba_url"].startswith("https://www.alibaba.com/trade/search?")
    assert rec["image"].startswith("https://m.media-amazon.com/images/I/")


def test_buyer_report_formats(fake_product, tmp_path, monkeypatch):
    monkeypatch.setenv("KEEPA_OUTPUT_DIR", str(tmp_path))
    import importlib
    from pathlib import Path

    from openpyxl import load_workbook

    from keepa_mcp import analysis, config, reports

    importlib.reload(config)
    importlib.reload(reports)

    rec = analysis.auto_verdict(analysis.build_record(fake_product, stats_days=90))
    paths = reports.generate_reports(
        [rec], report_name="buyer", query_summary="unit test",
        formats=("xlsx", "docx"), embed_images=False,
    )
    assert set(paths) == {"xlsx", "docx"}
    assert Path(paths["xlsx"]).exists() and Path(paths["docx"]).exists()

    ws = load_workbook(paths["xlsx"])["Анализ"]
    headers = [c.value for c in ws[1]]
    for col in ("ASIN", "Bucket", "Alibaba", "Image"):
        assert col in headers
    assert "Amazon URL" not in headers

    def cell(name):
        return ws.cell(row=2, column=headers.index(name) + 1)

    assert cell("ASIN").hyperlink.target.endswith("/dp/B0TEST1234")
    assert "alibaba.com" in cell("Alibaba").hyperlink.target

    # Summary sheet carries data-driven bucket + market breakdowns.
    summary_cells = {
        c.value
        for row in load_workbook(paths["xlsx"])["Сводка"].iter_rows()
        for c in row
        if c.value is not None
    }
    assert {"Bucket", "Market", "Avg momentum"} <= summary_cells
    assert "Bestseller" in summary_cells  # fake_product is a bestseller
    assert "US" in summary_cells  # market column is data-driven (marketplace)

    from docx import Document

    doc = Document(paths["docx"])
    assert len(doc.paragraphs) > 0
