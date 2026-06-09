"""Keepa product-research MCP server.

Exposes Keepa-backed search + metrics tools and an XLSX report writer over
the Model Context Protocol so Claude (via ``/mcp``) can search Amazon
products, pull purchase-decision metrics, reason over them, and persist a
report into the Продукты/ folder.

Run:  keepa-mcp           (stdio transport, for Claude Code / Desktop)
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import analysis, config, keepa_client, reports

mcp = FastMCP("keepa-product-research")


def _records_for(asins: list[str], domain: str | None, stats_days: int) -> list[dict[str, Any]]:
    products = keepa_client.query_products(asins, domain=domain, stats_days=stats_days)
    return [analysis.build_record(p, stats_days=stats_days) for p in products]


@mcp.tool()
def token_status() -> dict[str, Any]:
    """Check remaining Keepa API request tokens (quota). Use before large jobs."""
    return keepa_client.tokens_left()


@mcp.tool()
def search_products(
    title: str | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    max_sales_rank: int | None = None,
    min_review_count: int | None = None,
    limit: int = 25,
    domain: str | None = None,
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Search Amazon products via the Keepa Product Finder and return decision metrics.

    Provide any combination of filters. Prices are in dollars, rating is 0-5.
    Returns one analysis record per matched ASIN (pricing history stats, sales
    velocity, competition, reviews, specs) plus decision guidance. Claude should
    reason over these records and then call ``save_report`` with verdicts.

    Args:
        title: Keyword(s) that must appear in the product title.
        category_id: Keepa root category id to restrict the search.
        brand: Restrict to a specific brand.
        min_price / max_price: Current "New" price bounds, in dollars.
        min_rating: Minimum star rating (0-5).
        max_sales_rank: Maximum current sales rank (lower rank = better seller).
        min_review_count: Minimum number of reviews.
        limit: Max products to return (also costs Keepa tokens).
        domain: Marketplace override (US, UK, DE, ...); defaults to configured.
        stats_days: Window for price/rank stats; defaults to configured.
    """
    sd = stats_days or config.DEFAULT_STATS_DAYS
    selection = keepa_client.build_selection(
        title=title,
        category_id=category_id,
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        max_sales_rank=max_sales_rank,
        min_review_count=min_review_count,
    )
    asins = keepa_client.product_finder(selection, domain=domain, limit=limit)
    if not asins:
        return {"asins_found": 0, "records": [], "guidance": analysis.DECISION_GUIDANCE}
    records = _records_for(asins, domain, sd)
    return {
        "asins_found": len(asins),
        "records": records,
        "guidance": analysis.DECISION_GUIDANCE,
    }


@mcp.tool()
def get_products(
    asins: list[str],
    domain: str | None = None,
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Fetch full decision metrics + specs for one or more known ASINs.

    Use when you already have ASINs (e.g. from a prior search or supplied by
    the user) and want their pricing history, sales velocity, competition,
    ratings and product specifications for analysis.
    """
    sd = stats_days or config.DEFAULT_STATS_DAYS
    records = _records_for(asins, domain, sd)
    return {"records": records, "guidance": analysis.DECISION_GUIDANCE}


@mcp.tool()
def save_report(
    records: list[dict[str, Any]],
    report_name: str | None = None,
    query_summary: str | None = None,
) -> dict[str, Any]:
    """Write an XLSX purchase-analysis report into the Продукты/ folder.

    Pass the analysis records (from ``search_products`` / ``get_products``),
    each optionally enriched with your decision fields:
        - verdict: "BUY" | "WATCH" | "SKIP"
        - confidence: "high" | "medium" | "low"
        - rationale: short reason citing the driving metrics
    Returns the saved file path. The report has three sheets: Анализ (decision
    table), Характеристики (specs/features), Сводка (run summary).
    """
    path = reports.generate_report(
        records, report_name=report_name, query_summary=query_summary
    )
    return {
        "saved_to": str(path),
        "products": len(records),
        "output_dir": str(config.OUTPUT_DIR),
    }


@mcp.tool()
def analyze_and_report(
    asins: list[str],
    report_name: str | None = None,
    query_summary: str | None = None,
    domain: str | None = None,
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Fetch metrics for ASINs, write a data report, and return records to analyse.

    Convenience one-shot: pulls full records for the given ASINs, immediately
    saves a data-only XLSX (verdict columns left blank) so an artifact always
    exists, and returns the records so Claude can produce verdicts and, if
    desired, call ``save_report`` again with the enriched records.
    """
    sd = stats_days or config.DEFAULT_STATS_DAYS
    records = _records_for(asins, domain, sd)
    path = reports.generate_report(
        records, report_name=report_name, query_summary=query_summary
    )
    return {
        "saved_to": str(path),
        "records": records,
        "guidance": analysis.DECISION_GUIDANCE,
    }


@mcp.tool()
def server_info() -> dict[str, Any]:
    """Report current server configuration (marketplace, output dir, key status)."""
    return {
        "default_domain": config.DEFAULT_DOMAIN,
        "default_stats_days": config.DEFAULT_STATS_DAYS,
        "output_dir": str(config.OUTPUT_DIR),
        "api_key_configured": bool(config.KEEPA_API_KEY),
    }


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
