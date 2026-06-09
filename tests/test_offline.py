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
