"""Keepa product-research MCP server.

Exposes Keepa-backed search + metrics tools and an XLSX report writer over
the Model Context Protocol so Claude (via ``/mcp``) can search Amazon
products, pull purchase-decision metrics, reason over them, and persist a
report into the Products/ folder.

Run:  keepa-mcp           (stdio transport, for Claude Code / Desktop)
"""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from . import analysis, config, keepa_client, reports

mcp = FastMCP("keepa-product-research")


def _records_for(asins: list[str], domain: str | None, stats_days: int) -> list[dict[str, Any]]:
    code = keepa_client.normalize_domain(domain)
    products = keepa_client.query_products(asins, domain=code, stats_days=stats_days)
    return [analysis.build_record(p, stats_days=stats_days, domain=code) for p in products]


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
    max_offer_count: int | None = None,
    min_monthly_sold: int | None = None,
    extra_filters: dict[str, Any] | None = None,
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
        category_id: Keepa root category id to restrict the search
            (find ids with ``find_categories``).
        brand: Restrict to a specific brand.
        min_price / max_price: Current "New" price bounds, in dollars.
        min_rating: Minimum star rating (0-5).
        max_sales_rank: Maximum current sales rank (lower rank = better seller).
        min_review_count: Minimum number of reviews.
        max_offer_count: Maximum number of New offers (competition cap).
        min_monthly_sold: Minimum Amazon "bought in past month" estimate.
        extra_filters: Raw Keepa Product Finder keys merged verbatim on top —
            use for any additional user-supplied filter not covered above.
        limit: Max products to return (also costs Keepa tokens).
        domain: Marketplace (US, UK, DE, FR, IT, ES, ...); defaults to configured.
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
        max_offer_count=max_offer_count,
        min_monthly_sold=min_monthly_sold,
        extra_filters=extra_filters,
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
def search_multi_market(
    domains: list[str] | None = None,
    title: str | None = None,
    category_id: int | None = None,
    brand: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    min_rating: float | None = None,
    max_sales_rank: int | None = None,
    min_review_count: int | None = None,
    max_offer_count: int | None = None,
    min_monthly_sold: int | None = None,
    extra_filters: dict[str, Any] | None = None,
    limit: int = 10,
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Run the same product search across several marketplaces at once.

    Defaults to the full market list in priority order: US, UK, DE, FR, IT, ES
    (US is the most mature market, then UK and DE, then the rest). Use this to
    judge whether a category/product is worth entering per country. Note:
    ``category_id`` values differ between marketplaces — prefer ``title``/
    ``brand`` filters here, or look up the id per market with ``find_categories``.

    Returns records grouped per marketplace plus any per-market errors.
    """
    markets = domains or config.MARKET_PRIORITY
    sd = stats_days or config.DEFAULT_STATS_DAYS
    results: dict[str, Any] = {}
    errors: dict[str, str] = {}
    for market in markets:
        try:
            results[market] = search_products(
                title=title,
                category_id=category_id,
                brand=brand,
                min_price=min_price,
                max_price=max_price,
                min_rating=min_rating,
                max_sales_rank=max_sales_rank,
                min_review_count=min_review_count,
                max_offer_count=max_offer_count,
                min_monthly_sold=min_monthly_sold,
                extra_filters=extra_filters,
                limit=limit,
                domain=market,
                stats_days=sd,
            )
            results[market].pop("guidance", None)
        except Exception as exc:  # noqa: BLE001 - keep other markets going
            errors[market] = f"{type(exc).__name__}: {exc}"
    return {
        "markets": markets,
        "results": results,
        "errors": errors,
        "guidance": analysis.DECISION_GUIDANCE,
    }


@mcp.tool()
def find_categories(keyword: str, domain: str | None = None) -> dict[str, Any]:
    """Find Amazon category ids by name (e.g. "kitchen", "headphones").

    Category ids are marketplace-specific. Use the returned id as
    ``category_id`` in ``search_products`` / ``category_best_sellers``
    for the same marketplace.
    """
    cats = keepa_client.search_categories(keyword, domain=domain)
    return {
        "marketplace": keepa_client.normalize_domain(domain),
        "categories": [
            {
                "id": int(cat_id),
                "name": info.get("name"),
                "context_free_name": info.get("contextFreeName"),
                "products": info.get("productCount"),
            }
            for cat_id, info in cats.items()
        ],
    }


@mcp.tool()
def category_best_sellers(
    category_id: int,
    domain: str | None = None,
    limit: int = 20,
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Fetch the current best sellers of a category with full decision metrics.

    Good entry point for "pick a category and find products in it": shows what
    is actually selling there right now.
    """
    sd = stats_days or config.DEFAULT_STATS_DAYS
    asins = keepa_client.best_sellers(category_id, domain=domain)[: max(1, limit)]
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
def discover_products(
    title: str | None = None,
    category_id: int | None = None,
    min_price: float = 20.0,
    max_price: float = 500.0,
    min_rating: float | None = 4.0,
    max_sales_rank: int | None = 80000,
    min_review_count: int | None = None,
    max_offer_count: int | None = None,
    min_monthly_sold: int | None = None,
    min_rank_drops_30: int | None = None,
    focus: str = "all",
    extra_filters: dict[str, Any] | None = None,
    limit: int = 30,
    domain: str | None = "US",
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Discover what to source in a market: bestsellers, rising movers, new arrivals.

    Built for the sourcing workflow: a broad $20–500 sweep (US is the lead
    market — products surface here first — and the same items become candidates
    to resell in DE/AE). Each returned record is tagged **Bestseller / Rising /
    New**, scored by momentum, and carries a clickable Amazon link plus a ready
    **Alibaba supplier-search link**. Results are ordered most-interesting-first.

    Args:
        title: Optional keyword(s) to scope the sweep (omit for a category-wide
            or whole-market sweep — category ids differ per market).
        category_id: Optional Keepa root category id (find via ``find_categories``).
        min_price / max_price: Sourcing band in dollars (defaults $20–500).
        min_rating: Minimum star rating (default 4.0; pass null to disable).
        max_sales_rank: Cap on current sales rank (default 80000).
        min_review_count / max_offer_count / min_monthly_sold: Optional extra cuts.
        min_rank_drops_30: Require ≥ N sales-rank drops in 30 days (momentum floor).
        focus: Filter to one bucket — "bestsellers" | "rising" | "new" | "all".
        extra_filters: Raw Keepa Product Finder keys merged on top.
        limit: Max products to pull (also costs Keepa tokens).
        domain: Marketplace (default US, the lead market).
        stats_days: Window for stats/trend; defaults to configured.
    """
    sd = stats_days or config.DEFAULT_STATS_DAYS
    selection = keepa_client.build_selection(
        title=title,
        category_id=category_id,
        min_price=min_price,
        max_price=max_price,
        min_rating=min_rating,
        max_sales_rank=max_sales_rank,
        min_review_count=min_review_count,
        max_offer_count=max_offer_count,
        min_monthly_sold=min_monthly_sold,
        min_rank_drops_30=min_rank_drops_30,
        extra_filters=extra_filters,
    )
    asins = keepa_client.product_finder(selection, domain=domain, limit=limit)
    if not asins:
        return {"asins_found": 0, "records": [], "guidance": analysis.DISCOVERY_GUIDANCE}
    records = _records_for(asins, domain, sd)

    bucket = {"bestsellers": "Bestseller", "rising": "Rising", "new": "New"}.get(
        (focus or "all").lower()
    )
    if bucket:
        records = [
            r for r in records if bucket in (r.get("discovery") or {}).get("tags", [])
        ]
    records.sort(
        key=lambda r: (r.get("discovery") or {}).get("momentum_score") or 0,
        reverse=True,
    )
    return {
        "asins_found": len(asins),
        "returned": len(records),
        "focus": focus,
        "records": records,
        "guidance": analysis.DISCOVERY_GUIDANCE,
    }


@mcp.tool()
def save_report(
    records: list[dict[str, Any]],
    report_name: str | None = None,
    query_summary: str | None = None,
) -> dict[str, Any]:
    """Write an XLSX purchase-analysis report into the Products/ folder.

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
def save_buyer_report(
    records: list[dict[str, Any]],
    report_name: str | None = None,
    query_summary: str | None = None,
    report_format: str = "both",
) -> dict[str, Any]:
    """Write the buyer/purchaser deliverable: a data XLSX and/or a visual DOCX brief.

    Same records as the other tools (ideally from ``discover_products``, each
    optionally enriched with verdict/confidence/rationale). Both formats carry,
    per product, its discovery bucket, momentum, key demand metrics, a clickable
    Amazon link and a clickable **Alibaba supplier-search link** so the buyer can
    source immediately.

    Args:
        report_format: "both" (default) | "xlsx" | "docx".
    Returns the saved file path(s).
    """
    fmt = (report_format or "both").lower()
    formats = ("xlsx", "docx") if fmt == "both" else (fmt,)
    paths = reports.generate_reports(
        records,
        report_name=report_name or "buyer_sourcing",
        query_summary=query_summary,
        formats=formats,
    )
    return {
        "saved": paths,
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
def run_auto_search(searches_file: str | None = None) -> dict[str, Any]:
    """Execute the saved auto searches (auto_searches.json) right now.

    Runs every saved search from the config file, applies rule-based
    verdicts, and writes one XLSX per search into Products/. The same job is
    what the 2-day scheduler (``keepa-auto`` via cron) runs unattended.
    """
    from . import auto_search

    return auto_search.run_all(searches_file)


@mcp.tool()
def server_info() -> dict[str, Any]:
    """Report current server configuration (marketplace, output dir, key status)."""
    return {
        "default_domain": config.DEFAULT_DOMAIN,
        "supported_markets_priority": config.MARKET_PRIORITY,
        "default_stats_days": config.DEFAULT_STATS_DAYS,
        "output_dir": str(config.OUTPUT_DIR),
        "auto_search_file": str(config.AUTO_SEARCH_FILE),
        "api_key_configured": bool(config.KEEPA_API_KEY),
    }


def main() -> None:
    """Console-script entry point: run the server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
