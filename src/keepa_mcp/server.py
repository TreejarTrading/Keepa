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

from . import analysis, config, keepa_client, reports, sourcing

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
def china_sourcing_guide() -> dict[str, Any]:
    """Return the China-sourcing methodology: platforms, match rules, columns.

    Read this before sourcing. It tells you to search beyond Alibaba (1688,
    Made-in-China, Global Sources, DHgate), to keep ALL MOQ price tiers and use
    the tier matching the order quantity, to match the EXACT product (model
    number / photo / specs, not a look-alike), to use the Amazon ``manufacturer``
    field as a supplier search key, and what each report column means (Russian).
    Full text: SOURCING_GUIDE.md.
    """
    return {
        "guidance": sourcing.SOURCING_GUIDANCE,
        "column_docs": [{"column": h, "meaning": d} for h, d in sourcing.COLUMN_DOCS],
        "defaults": {
            "base_currency": "USD",
            "duty_pct": sourcing.DEFAULT_DUTY_PCT,
            "referral_pct_fallback": sourcing.DEFAULT_REFERRAL_PCT,
            "freight": "вес (кг) × freight_per_kg, либо явная freight_per_unit поставщика",
        },
    }


@mcp.tool()
def sourcing_inputs_from_asins(
    asins: list[str],
    domain: str | None = None,
    stats_days: int | None = None,
) -> dict[str, Any]:
    """Build the Amazon-side sourcing skeletons for the given ASINs.

    Pulls each product from Keepa and returns the fields needed to source it in
    China: title, brand, **manufacturer** (use it as an Alibaba/1688 search key),
    sell price, real Amazon fees (referral % + FBA), monthly sales and weight.
    Attach a ``suppliers`` list to each item (from your web search across
    Alibaba/1688/Made-in-China/Global Sources/DHgate), then call
    ``build_sourcing_plan``.
    """
    sd = stats_days or config.DEFAULT_STATS_DAYS
    records = _records_for(asins, domain, sd)
    items = [sourcing.amazon_item_from_record(r) for r in records]
    return {"items": items, "guidance": sourcing.SOURCING_GUIDANCE}


@mcp.tool()
def build_sourcing_plan(
    items: list[dict[str, Any]],
    base_currency: str = "USD",
    fx: dict[str, float] | None = None,
    duty_pct: float | None = None,
    freight_per_kg: float | None = None,
    default_order_quantity: int | None = None,
    report_name: str | None = None,
    query_summary: str | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Compare Amazon products with Chinese suppliers and model the unit economics.

    Each ``items`` entry combines the Amazon side (from
    ``sourcing_inputs_from_asins``) with a ``suppliers`` list you gathered via
    web search. Each supplier MUST keep the full MOQ price ladder so the correct
    tier is used::

        {"asin": "...", "title": "...", "manufacturer": "...",
         "marketplace": "DE", "amazon_sell_price": 32.0,
         "amazon_referral_pct": 0.15, "amazon_fba_fee": 4.5,
         "monthly_sold": 400, "weight_g": 2500,
         "suppliers": [{
            "platform": "Alibaba"|"1688"|"Made-in-China"|"Global Sources"|"DHgate",
            "supplier_name": "...", "is_manufacturer": true,
            "matches_amazon_manufacturer": true,
            "match_quality": "точное"|"близкое"|"аналог",
            "match_basis": "модель MS008 + фото", "model_number": "MS008",
            "currency": "EUR", "moq": 100,
            "price_tiers": [{"min_qty": 1, "max_qty": 100, "unit_price": 9.91},
                            {"min_qty": 101, "max_qty": 999, "unit_price": 9.78},
                            {"min_qty": 1000, "max_qty": null, "unit_price": 9.53}],
            "freight_per_unit": null, "url": "https://..."}]}

    Computes landed cost, Amazon fees, profit, margin %, ROI %, per-volume
    scenarios and a rule-based verdict (ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ). Writes the
    Russian XLSX (Сопоставление / Сценарии / Пояснения / Сводка) when
    ``save=True``. Returns the plan so you can refine verdicts and re-save with
    ``save_sourcing_report``.

    Args:
        base_currency: Currency for landed cost / margin (default USD).
        fx: Map of currency -> multiplier to ``base_currency`` (e.g. {"EUR":1.08,
            "CNY":0.14}). Missing rates are assumed 1.0 and flagged.
        duty_pct: Import duty as a fraction of (cost+freight); defaults to the
            UAE/GCC 5%. A real per-product rate (e.g. from the HS code) can be
            set as ``duty_pct`` on an item or supplier and overrides this.
        freight_per_kg: Freight rate per kg in ``base_currency`` (weight from
            Keepa); used when a supplier has no explicit ``freight_per_unit``.
        default_order_quantity: Order size for the economics (default = each
            supplier's MOQ).
    """
    plan = sourcing.build_plan(
        items,
        base_currency=base_currency,
        fx=fx,
        duty_pct=sourcing.DEFAULT_DUTY_PCT if duty_pct is None else duty_pct,
        default_order_quantity=default_order_quantity,
        freight_per_kg=freight_per_kg,
    )
    if save:
        path = reports.generate_sourcing_report(
            plan, report_name=report_name, query_summary=query_summary
        )
        plan["saved_to"] = str(path)
        plan["output_dir"] = str(config.OUTPUT_DIR)
    return plan


@mcp.tool()
def save_sourcing_report(
    plan: dict[str, Any],
    report_name: str | None = None,
    query_summary: str | None = None,
) -> dict[str, Any]:
    """Write the China-sourcing comparison XLSX from a (possibly edited) plan.

    Pass the plan from ``build_sourcing_plan`` after refining any ``verdict`` /
    ``confidence`` / ``rationale`` on its ``rows``. Produces the four-sheet
    Russian report (Сопоставление / Сценарии / Пояснения / Сводка).
    """
    path = reports.generate_sourcing_report(
        plan, report_name=report_name, query_summary=query_summary
    )
    return {
        "saved_to": str(path),
        "rows": len(plan.get("rows") or []),
        "output_dir": str(config.OUTPUT_DIR),
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
