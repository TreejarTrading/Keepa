"""China-sourcing layer: match Amazon products to Chinese suppliers and model
the unit economics of importing & reselling them.

The **Amazon side** comes from Keepa (the analysis records produced by
:mod:`keepa_mcp.analysis`). The **China side** — supplier offers and their MOQ
price tiers — is gathered by Claude via web search across Alibaba, 1688,
Made-in-China, Global Sources and DHgate (see ``SOURCING_GUIDE.md``).

This module is deliberately pure and deterministic so it stays offline-testable:
it makes **no** API/network calls. Given assembled inputs it:

* picks the **correct MOQ price tier** for the intended order quantity
  (fixes "wrong MOQ price extracted");
* converts supplier/marketplace currencies to one base currency;
* computes landed unit cost, Amazon fees, profit, margin %, ROI %;
* builds **per-volume scenarios** (precise what-if hypotheses by order size);
* assigns a rule-based sourcing verdict **ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ**.

Claude reasons over the result and may override the verdicts before the XLSX
report is written.
"""

from __future__ import annotations

from typing import Any

# --- defaults & reference tables --------------------------------------------

# Amazon referral fee as a fraction of the sale price (category-dependent;
# 15% is the common default). Override per item with ``amazon_referral_pct``.
DEFAULT_REFERRAL_PCT = 0.15

# Amazon's minimum referral fee per item (commonly $0.30 in USD terms).
MIN_REFERRAL_FEE = 0.30

# Import duty as a fraction of (unit cost + freight). Default 5% — the standard
# UAE/GCC import duty (the team imports into the UAE). Override ``duty_pct`` for
# another destination.
DEFAULT_DUTY_PCT = 0.05

# Currency reported by each Amazon marketplace (Keepa domain code -> ISO 4217).
MARKET_CURRENCY = {
    "US": "USD", "GB": "GBP", "DE": "EUR", "FR": "EUR", "IT": "EUR",
    "ES": "EUR", "JP": "JPY", "CA": "CAD", "IN": "INR", "MX": "MXN", "BR": "BRL",
}

# Chinese sourcing platforms to cover — NOT only Alibaba (fixes problem #4).
# Each entry: code, human name, and what it is good for.
CHINA_PLATFORMS = [
    {
        "code": "1688",
        "name": "1688.com",
        "note": "Внутренний оптовый рынок Китая (от Alibaba). Самые низкие цены и "
        "прямой выход на фабрики, но интерфейс на китайском, оплата внутри КНР — "
        "обычно нужен агент/карго. Лучшая площадка для поиска реальной себестоимости.",
    },
    {
        "code": "Alibaba",
        "name": "Alibaba.com",
        "note": "Экспортная B2B-площадка. Цены выше 1688, но есть Trade Assurance, "
        "англоязычные менеджеры и MOQ для экспорта.",
    },
    {
        "code": "Made-in-China",
        "name": "Made-in-China.com",
        "note": "Каталог производителей, силён в промышленных и OEM-товарах; "
        "удобно искать именно фабрику-изготовителя.",
    },
    {
        "code": "Global Sources",
        "name": "GlobalSources.com",
        "note": "Проверенные экспортёры электроники и потребтоваров; данные с "
        "выставок, выше шанс выйти на оригинального производителя.",
    },
    {
        "code": "DHgate",
        "name": "DHgate.com",
        "note": "Мелкий опт / дропшиппинг, низкие MOQ. Полезен для проверки цены "
        "на малых партиях и образцах.",
    },
]

# Allowed product-match grades (problem #2), best first.
MATCH_QUALITY = ("точное", "близкое", "аналог")
_MATCH_RANK = {q: i for i, q in enumerate(MATCH_QUALITY)}

# Sourcing-verdict thresholds (on the representative/base scenario). Documented
# in SOURCING_GUIDE.md so Claude's overrides stay consistent with auto runs.
BUY_MARGIN = 0.30        # маржа к цене продажи
BUY_ROI = 0.60           # прибыль к себестоимости (наценка)
REJECT_MARGIN = 0.15
REJECT_ROI = 0.30


# --- currency ---------------------------------------------------------------

def market_currency(marketplace: str | None) -> str:
    """ISO currency for an Amazon marketplace code (defaults to USD)."""
    return MARKET_CURRENCY.get((marketplace or "US").strip().upper(), "USD")


def fx_rate(currency: str | None, base: str, fx: dict[str, float] | None) -> tuple[float, bool]:
    """Return (multiplier to ``base``, is_known). Unknown rates assume 1.0."""
    base_u = (base or "USD").upper()
    cur = (currency or base_u).upper()
    if cur == base_u:
        return 1.0, True
    table = {k.upper(): v for k, v in (fx or {}).items()}
    rate = table.get(cur)
    if rate is None:
        return 1.0, False
    try:
        return float(rate), True
    except (TypeError, ValueError):
        return 1.0, False


def to_base(
    amount: Any, currency: str | None, base: str, fx: dict[str, float] | None
) -> tuple[float | None, bool]:
    """Convert ``amount`` (in ``currency``) to ``base``. Returns (value, known)."""
    if amount is None:
        return None, True
    try:
        val = float(amount)
    except (TypeError, ValueError):
        return None, True
    rate, known = fx_rate(currency, base, fx)
    return round(val * rate, 4), known


# --- MOQ price tiers (problem #1) -------------------------------------------

def normalize_tiers(tiers: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Sort price tiers by ``min_qty`` and infer each tier's ``max_qty``.

    On Alibaba a price like ``1-100 шт → 9.91€ / 101-999 → 9.78€ / ≥1000 →
    9.53€`` is a *quantity ladder*: the unit price depends on how many you buy.
    Storing every tier (instead of grabbing one number) is what lets
    :func:`pick_tier` select the price for the *actual* order size.
    """
    cleaned: list[dict[str, Any]] = []
    for t in tiers or []:
        if not isinstance(t, dict):
            continue
        try:
            unit = float(t.get("unit_price"))
        except (TypeError, ValueError):
            continue
        try:
            lo = int(t.get("min_qty") or 1)
        except (TypeError, ValueError):
            lo = 1
        mx = t.get("max_qty")
        try:
            hi = int(mx) if mx is not None else None
        except (TypeError, ValueError):
            hi = None
        cleaned.append({"min_qty": max(1, lo), "max_qty": hi, "unit_price": unit})

    cleaned.sort(key=lambda x: x["min_qty"])
    # Infer an open max_qty from the next tier's min_qty (… - 1).
    for i, t in enumerate(cleaned):
        if t["max_qty"] is None and i + 1 < len(cleaned):
            t["max_qty"] = max(t["min_qty"], cleaned[i + 1]["min_qty"] - 1)
    return cleaned


def pick_tier(tiers: list[dict[str, Any]] | None, qty: int | None) -> dict[str, Any] | None:
    """Return the price tier that applies to an order of ``qty`` units.

    ``qty=None`` falls back to the smallest tier's ``min_qty`` (the MOQ), so the
    representative price is the one you would actually pay on a first order —
    never the cheapest high-volume tier by accident.
    """
    norm = normalize_tiers(tiers)
    if not norm:
        return None
    if qty is None:
        qty = norm[0]["min_qty"]
    for t in norm:
        hi = t["max_qty"]
        if qty >= t["min_qty"] and (hi is None or qty <= hi):
            return t
    # Below the smallest MOQ -> smallest tier; above the largest -> largest tier.
    if qty < norm[0]["min_qty"]:
        return norm[0]
    return norm[-1]


def tiers_text(tiers: list[dict[str, Any]] | None, currency: str | None) -> str:
    """Human-readable summary of every MOQ tier (for the report / audit)."""
    norm = normalize_tiers(tiers)
    cur = (currency or "").upper()
    parts = []
    for t in norm:
        hi = t["max_qty"]
        rng = f"{t['min_qty']}–{hi}" if hi is not None else f"≥{t['min_qty']}"
        parts.append(f"{rng} шт: {t['unit_price']:g} {cur}".strip())
    return " | ".join(parts)


# --- economics --------------------------------------------------------------

def _order_qty(supplier: dict[str, Any], default_qty: int | None) -> int | None:
    """Intended order quantity: explicit > supplier MOQ > smallest tier > default."""
    for key in ("order_quantity", "moq"):
        val = supplier.get(key)
        if val:
            try:
                return max(1, int(val))
            except (TypeError, ValueError):
                pass
    norm = normalize_tiers(supplier.get("price_tiers"))
    if norm:
        return norm[0]["min_qty"]
    return default_qty


def compute_economics(
    *,
    sell_base: float | None,
    referral_pct: float,
    fba_fee_base: float | None,
    unit_cost_base: float | None,
    freight_base: float | None,
    duty_pct: float,
    monthly_sold: int | None,
    qty: int | None,
) -> dict[str, Any]:
    """Unit economics for one Amazon price vs one supplier unit cost (all in base)."""
    freight = freight_base or 0.0
    duty = round((unit_cost_base + freight) * duty_pct, 4) if unit_cost_base is not None else None
    landed = (
        round(unit_cost_base + freight + (duty or 0.0), 4)
        if unit_cost_base is not None
        else None
    )

    amazon_fee = None
    net = None
    if sell_base is not None:
        referral = max(sell_base * referral_pct, MIN_REFERRAL_FEE) if referral_pct else 0.0
        amazon_fee = round(referral + (fba_fee_base or 0.0), 4)
        net = round(sell_base - amazon_fee, 4)

    profit = margin = roi = monthly_profit = order_budget = None
    if net is not None and landed is not None:
        profit = round(net - landed, 4)
        if sell_base:
            margin = round(profit / sell_base, 4)
        if landed:
            roi = round(profit / landed, 4)
        if monthly_sold:
            monthly_profit = round(profit * monthly_sold, 2)
    if landed is not None and qty:
        order_budget = round(landed * qty, 2)

    return {
        "amazon_fee": amazon_fee,
        "unit_cost": unit_cost_base,
        "freight": round(freight, 4) if freight else freight,
        "duty": duty,
        "landed_cost": landed,
        "profit_per_unit": profit,
        "margin_pct": margin,
        "roi_pct": roi,
        "monthly_profit": monthly_profit,
        "order_budget": order_budget,
    }


def sourcing_verdict(row: dict[str, Any]) -> dict[str, Any]:
    """Rule-based ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ verdict for a comparison row."""
    margin = row.get("margin_pct")
    roi = row.get("roi_pct")
    match = (row.get("match_quality") or "").strip().lower()
    pros: list[str] = []
    cons: list[str] = []

    if margin is not None:
        if margin >= BUY_MARGIN:
            pros.append(f"маржа {margin:.0%}")
        elif margin < REJECT_MARGIN:
            cons.append(f"низкая маржа {margin:.0%}")
    if roi is not None:
        if roi >= BUY_ROI:
            pros.append(f"ROI {roi:.0%}")
        elif roi < REJECT_ROI:
            cons.append(f"низкий ROI {roi:.0%}")

    if match == "аналог":
        cons.append("найден только аналог, не тот же товар")
    elif match == "точное":
        pros.append("точное совпадение товара")
    if row.get("matches_amazon_manufacturer"):
        pros.append("совпадает производитель с Amazon")
    elif row.get("is_manufacturer"):
        pros.append("прямой производитель (OEM)")

    if margin is None or roi is None or row.get("unit_cost") is None:
        verdict, confidence = "ПРОВЕРИТЬ", "low"
        rationale = "недостаточно данных по поставщику/цене"
    else:
        if (
            margin >= BUY_MARGIN
            and roi >= BUY_ROI
            and match in ("точное", "близкое")
            and not any("низк" in c for c in cons)
        ):
            verdict = "ЗАКУПАТЬ"
        elif margin < REJECT_MARGIN or roi < REJECT_ROI or match == "аналог":
            verdict = "ОТКАЗ"
        else:
            verdict = "ПРОВЕРИТЬ"
        confidence = "high" if len(pros) + len(cons) >= 3 else "medium"
        rationale = "; ".join(["+ " + p for p in pros] + ["- " + c for c in cons]) or "—"

    return {"verdict": verdict, "confidence": confidence, "rationale": rationale}


# --- row & plan assembly ----------------------------------------------------

def _item_weight_kg(item: dict[str, Any]) -> float | None:
    """Product weight in kg from ``weight_kg`` or Keepa's ``weight_g``/packageWeight."""
    for key, div in (("weight_kg", 1.0), ("weight_g", 1000.0)):
        val = item.get(key)
        if val:
            try:
                return float(val) / div
            except (TypeError, ValueError):
                pass
    return None


def _resolve_freight(
    item: dict[str, Any],
    supplier: dict[str, Any],
    base_currency: str,
    fx: dict[str, float] | None,
    freight_per_kg: float | None,
    assumptions: list[str],
) -> tuple[float | None, bool]:
    """Freight per unit, in base currency.

    Priority: explicit ``freight_per_unit`` on the supplier > weight × rate
    (``freight_per_kg`` in base currency, weight from Keepa) > 0. Records the
    method used in ``assumptions`` so the number is auditable.
    """
    sup_cur = supplier.get("currency") or base_currency
    explicit = supplier.get("freight_per_unit")
    if explicit is not None:
        val, known = to_base(explicit, sup_cur, base_currency, fx)
        if not known:
            assumptions.append(f"курс логистики {sup_cur}→{base_currency} не задан (принят 1.0)")
        return val, known

    weight_kg = _item_weight_kg(item)
    if freight_per_kg and weight_kg:
        val = round(weight_kg * float(freight_per_kg), 4)
        assumptions.append(
            f"логистика = {weight_kg:g} кг × {float(freight_per_kg):g} {base_currency}/кг"
        )
        return val, True

    assumptions.append("логистика не задана (0)")
    return 0.0, True


def build_row(
    item: dict[str, Any],
    supplier: dict[str, Any],
    *,
    base_currency: str,
    fx: dict[str, float] | None,
    duty_pct: float,
    default_qty: int | None,
    freight_per_kg: float | None = None,
) -> dict[str, Any]:
    """Combine one Amazon product with one supplier offer into a comparison row.

    Adds the chosen MOQ tier, converted economics, per-volume scenarios and a
    rule-based verdict. ``assumptions`` records anything inferred (missing FX,
    freight, FBA fee) so the numbers are auditable.
    """
    assumptions: list[str] = []
    amz_cur = item.get("currency") or market_currency(item.get("marketplace"))
    sup_cur = supplier.get("currency") or base_currency

    sell_base, sell_known = to_base(item.get("amazon_sell_price"), amz_cur, base_currency, fx)
    if not sell_known:
        assumptions.append(f"курс {amz_cur}→{base_currency} не задан (принят 1.0)")
    referral_pct = item.get("amazon_referral_pct")
    if referral_pct is None:
        referral_pct = DEFAULT_REFERRAL_PCT
        assumptions.append(f"реферальная комиссия не задана (принято {DEFAULT_REFERRAL_PCT:.0%})")
    else:
        referral_pct = float(referral_pct)
        if item.get("amazon_referral_source") == "category":
            assumptions.append(f"referral по категории Amazon (оценка {referral_pct:.0%})")
    fba_base, _ = to_base(item.get("amazon_fba_fee"), amz_cur, base_currency, fx)
    if item.get("amazon_fba_fee") is None:
        assumptions.append("комиссия FBA не из Keepa (0)")

    qty = _order_qty(supplier, default_qty)
    tier = pick_tier(supplier.get("price_tiers"), qty)
    if tier is None:
        assumptions.append("нет ценовых уровней поставщика")
    unit_base, unit_known = to_base(
        tier["unit_price"] if tier else None, sup_cur, base_currency, fx
    )
    if tier and not unit_known:
        assumptions.append(f"курс {sup_cur}→{base_currency} не задан (принят 1.0)")
    freight_base, freight_known = _resolve_freight(
        item, supplier, base_currency, fx, freight_per_kg, assumptions
    )

    econ = compute_economics(
        sell_base=sell_base,
        referral_pct=referral_pct,
        fba_fee_base=fba_base,
        unit_cost_base=unit_base,
        freight_base=freight_base,
        duty_pct=duty_pct,
        monthly_sold=item.get("monthly_sold"),
        qty=qty,
    )

    tier_range = ""
    if tier:
        hi = tier["max_qty"]
        tier_range = f"{tier['min_qty']}–{hi}" if hi is not None else f"≥{tier['min_qty']}"

    match_q = (supplier.get("match_quality") or "").strip().lower()
    if match_q and match_q not in MATCH_QUALITY:
        match_q = ""

    row: dict[str, Any] = {
        # Amazon side
        "asin": item.get("asin"),
        "title": item.get("title"),
        "brand": item.get("brand"),
        "manufacturer": item.get("manufacturer"),
        "marketplace": item.get("marketplace"),
        "amazon_sell_price": sell_base,
        "monthly_sold": item.get("monthly_sold"),
        "amazon_url": item.get("url"),
        # China side
        "platform": supplier.get("platform"),
        "supplier_name": supplier.get("supplier_name"),
        "is_manufacturer": supplier.get("is_manufacturer"),
        "matches_amazon_manufacturer": supplier.get("matches_amazon_manufacturer"),
        "match_quality": match_q or supplier.get("match_quality"),
        "match_basis": supplier.get("match_basis"),
        "model_number": supplier.get("model_number"),
        "moq": supplier.get("moq"),
        "order_qty": qty,
        "tier_range": tier_range,
        "all_tiers": tiers_text(supplier.get("price_tiers"), sup_cur),
        "supplier_currency": sup_cur,
        "supplier_url": supplier.get("url"),
        "notes": supplier.get("notes"),
        # economics (already in base currency)
        "currency": base_currency,
        **econ,
        "assumptions": "; ".join(dict.fromkeys(assumptions)) or "—",
    }

    # Per-volume scenarios across every MOQ tier (precise what-if hypotheses).
    scenarios: list[dict[str, Any]] = []
    for t in normalize_tiers(supplier.get("price_tiers")):
        s_qty = t["min_qty"]
        u_base, _ = to_base(t["unit_price"], sup_cur, base_currency, fx)
        se = compute_economics(
            sell_base=sell_base,
            referral_pct=referral_pct,
            fba_fee_base=fba_base,
            unit_cost_base=u_base,
            freight_base=freight_base,
            duty_pct=duty_pct,
            monthly_sold=item.get("monthly_sold"),
            qty=s_qty,
        )
        hi = t["max_qty"]
        scenarios.append(
            {
                "tier_range": f"{t['min_qty']}–{hi}" if hi is not None else f"≥{t['min_qty']}",
                "qty": s_qty,
                "unit_cost": se["unit_cost"],
                "landed_cost": se["landed_cost"],
                "profit_per_unit": se["profit_per_unit"],
                "margin_pct": se["margin_pct"],
                "roi_pct": se["roi_pct"],
            }
        )
    row["scenarios"] = scenarios
    row.update(sourcing_verdict(row))
    return row


def build_plan(
    items: list[dict[str, Any]],
    *,
    base_currency: str = "USD",
    fx: dict[str, float] | None = None,
    duty_pct: float = DEFAULT_DUTY_PCT,
    default_order_quantity: int | None = None,
    freight_per_kg: float | None = None,
) -> dict[str, Any]:
    """Turn Amazon items + their supplier offers into a full comparison plan.

    Each item is ``{asin, title, brand, manufacturer, marketplace,
    amazon_sell_price, monthly_sold, url, suppliers: [...]}``; each supplier is
    ``{platform, supplier_name, match_quality, model_number, price_tiers:
    [{min_qty, max_qty, unit_price}], freight_per_unit, currency, url, ...}``.

    Returns ``{rows, currency, base_currency, fx, duty_pct, guidance}`` where
    ``rows`` is one comparison row per (product × supplier) with scenarios.
    """
    base = (base_currency or "USD").upper()
    rows: list[dict[str, Any]] = []
    for item in items or []:
        suppliers = item.get("suppliers") or []
        if not suppliers:
            rows.append(_amazon_only_row(item, base))
            continue
        for supplier in suppliers:
            rows.append(
                build_row(
                    item,
                    supplier,
                    base_currency=base,
                    fx=fx,
                    duty_pct=duty_pct,
                    default_qty=default_order_quantity,
                    freight_per_kg=freight_per_kg,
                )
            )
    return {
        "rows": rows,
        "currency": base,
        "base_currency": base,
        "fx": fx or {},
        "duty_pct": duty_pct,
        "freight_per_kg": freight_per_kg,
        "guidance": SOURCING_GUIDANCE,
    }


def _amazon_only_row(item: dict[str, Any], base: str) -> dict[str, Any]:
    """A row for an Amazon product that has no supplier match yet."""
    sell_base, _ = to_base(
        item.get("amazon_sell_price"),
        item.get("currency") or market_currency(item.get("marketplace")),
        base,
        None,
    )
    return {
        "asin": item.get("asin"),
        "title": item.get("title"),
        "brand": item.get("brand"),
        "manufacturer": item.get("manufacturer"),
        "marketplace": item.get("marketplace"),
        "amazon_sell_price": sell_base,
        "monthly_sold": item.get("monthly_sold"),
        "amazon_url": item.get("url"),
        "currency": base,
        "match_quality": "не найдено",
        "verdict": "ПРОВЕРИТЬ",
        "confidence": "low",
        "rationale": "поставщик в Китае ещё не найден",
        "assumptions": "—",
        "scenarios": [],
    }


def amazon_item_from_record(record: dict[str, Any]) -> dict[str, Any]:
    """Build the Amazon-side sourcing skeleton from a Keepa analysis record.

    Pulls title, brand and especially **manufacturer** (so it can be used as an
    Alibaba search key — problem #3), the realistic sell price (Buy Box, else
    current New), monthly sales and links. Claude attaches ``suppliers`` to it.
    """
    metrics = record.get("metrics") or {}
    pricing = metrics.get("pricing") or {}
    buy_box = (pricing.get("buy_box") or {}).get("current")
    new = (pricing.get("new") or {}).get("current")
    demand = metrics.get("demand") or {}
    fees = metrics.get("amazon_fees") or {}
    sell = fees.get("sell_price_used")
    if sell is None:
        sell = buy_box if buy_box is not None else new
    return {
        "asin": record.get("asin"),
        "title": record.get("title"),
        "brand": record.get("brand"),
        "manufacturer": record.get("manufacturer"),
        "marketplace": record.get("marketplace"),
        "currency": market_currency(record.get("marketplace")),
        "amazon_sell_price": sell,
        # Real Amazon fees from Keepa (category-correct referral, not flat 15%).
        "amazon_referral_pct": fees.get("referral_pct"),
        "amazon_referral_source": fees.get("referral_pct_source"),
        "amazon_fba_fee": fees.get("fba_fee"),
        "amazon_total_fees": fees.get("total_fees"),
        "monthly_sold": demand.get("monthly_sold_estimate"),
        "weight_g": record.get("package_weight_g"),
        "url": record.get("url"),
        "suppliers": [],
    }


# --- report column spec + docs (single source of truth) ----------------------
# Each column: header (Russian), key (into a built row), kind (formatting), doc
# (Russian explanation rendered on the "Пояснения" sheet — problem #5).
REPORT_COLUMNS: list[dict[str, str]] = [
    {"header": "ASIN", "key": "asin", "kind": "text",
     "doc": "Идентификатор товара на Amazon."},
    {"header": "Товар (Amazon)", "key": "title", "kind": "text",
     "doc": "Название листинга на Amazon, по которому ведём поиск в Китае."},
    {"header": "Бренд", "key": "brand", "kind": "text",
     "doc": "Бренд из карточки Amazon."},
    {"header": "Производитель (Amazon)", "key": "manufacturer", "kind": "text",
     "doc": "Поле Manufacturer из карточки ASIN. Используется как ключ поиска "
            "поставщика/фабрики в Китае (часто даёт прямой мэтч на производителя)."},
    {"header": "Рынок", "key": "marketplace", "kind": "text",
     "doc": "Маркетплейс Amazon (US/UK/DE/…), определяет валюту цены продажи."},
    {"header": "Цена продажи (Amazon)", "key": "amazon_sell_price", "kind": "money",
     "doc": "Реальная цена продажи на Amazon (Buy Box, иначе текущая New), "
            "пересчитанная в базовую валюту отчёта."},
    {"header": "Комиссия Amazon", "key": "amazon_fee", "kind": "money",
     "doc": "Реферальная комиссия Amazon (ставка по категории из Keepa, не плоские "
            "15%) плюс сбор FBA pick&pack за единицу."},
    {"header": "Площадка (Китай)", "key": "platform", "kind": "text",
     "doc": "Где найден поставщик: 1688 / Alibaba / Made-in-China / Global Sources "
            "/ DHgate. Поиск ведём не только на Alibaba."},
    {"header": "Поставщик", "key": "supplier_name", "kind": "text",
     "doc": "Название продавца/фабрики на площадке в Китае."},
    {"header": "Фабрика (OEM)", "key": "is_manufacturer", "kind": "bool",
     "doc": "Да — это завод-изготовитель (а не торговая компания/посредник)."},
    {"header": "Мэтч с производителем Amazon", "key": "matches_amazon_manufacturer",
     "kind": "bool",
     "doc": "Да — поставщик совпадает с полем Manufacturer из Amazon (сильный сигнал, "
            "что это тот же изготовитель)."},
    {"header": "Степень совпадения", "key": "match_quality", "kind": "text",
     "doc": "Насколько найденный товар совпадает с Amazon: точное / близкое / "
            "аналог. «Аналог» = похожий, но не тот же товар."},
    {"header": "Основание совпадения", "key": "match_basis", "kind": "text",
     "doc": "На чём основан мэтч: артикул/модель, фото, характеристики, бренд, "
            "производитель."},
    {"header": "Модель/артикул", "key": "model_number", "kind": "text",
     "doc": "Номер модели поставщика (напр. MS008) — для точной идентификации товара."},
    {"header": "MOQ", "key": "moq", "kind": "int",
     "doc": "Минимальный объём заказа у поставщика."},
    {"header": "Кол-во в заказе", "key": "order_qty", "kind": "int",
     "doc": "Объём заказа, для которого посчитана экономика (по умолч. = MOQ)."},
    {"header": "Ценовой уровень (MOQ)", "key": "tier_range", "kind": "text",
     "doc": "Диапазон количества, к которому относится взятая цена за единицу "
            "(напр. 1–100 шт). Берётся уровень под фактический объём заказа."},
    {"header": "Цена за ед. (Китай)", "key": "unit_cost", "kind": "money",
     "doc": "Закупочная цена за единицу на выбранном уровне MOQ, в базовой валюте."},
    {"header": "Логистика за ед.", "key": "freight", "kind": "money",
     "doc": "Оценка стоимости доставки/фрахта в расчёте на единицу."},
    {"header": "Пошлина за ед.", "key": "duty", "kind": "money",
     "doc": "Импортная пошлина на единицу = (цена+логистика)×ставка пошлины."},
    {"header": "Себестоимость (landed)", "key": "landed_cost", "kind": "money",
     "doc": "Полная себестоимость единицы на складе: цена + логистика + пошлина."},
    {"header": "Прибыль за ед.", "key": "profit_per_unit", "kind": "money",
     "doc": "Цена продажи − комиссия Amazon − себестоимость (landed)."},
    {"header": "Маржа, %", "key": "margin_pct", "kind": "pct",
     "doc": "Прибыль за единицу к цене продажи на Amazon."},
    {"header": "ROI, %", "key": "roi_pct", "kind": "pct",
     "doc": "Прибыль за единицу к себестоимости (наценка на вложенные деньги)."},
    {"header": "Продаж/мес (оценка)", "key": "monthly_sold", "kind": "int",
     "doc": "Оценка месячных продаж товара на Amazon (из аналитики Keepa)."},
    {"header": "Прибыль/мес (оценка)", "key": "monthly_profit", "kind": "money",
     "doc": "Прибыль за единицу × оценка месячных продаж."},
    {"header": "Бюджет на заказ", "key": "order_budget", "kind": "money",
     "doc": "Себестоимость × количество в заказе — сколько денег нужно на партию."},
    {"header": "Вердикт", "key": "verdict", "kind": "text",
     "doc": "Итог: ЗАКУПАТЬ / ПРОВЕРИТЬ / ОТКАЗ (по марже, ROI и качеству мэтча)."},
    {"header": "Уверенность", "key": "confidence", "kind": "text",
     "doc": "Надёжность вывода: high / medium / low."},
    {"header": "Обоснование", "key": "rationale", "kind": "text",
     "doc": "Ключевые сигналы «за» и «против», на которых построен вердикт."},
    {"header": "Все ценовые уровни", "key": "all_tiers", "kind": "text",
     "doc": "Полная лесенка цен MOQ, как указана у поставщика (для аудита цены)."},
    {"header": "Допущения", "key": "assumptions", "kind": "text",
     "doc": "Что принято по умолчанию (курс валют, логистика, FBA), если данных не было."},
    {"header": "Ссылка (Китай)", "key": "supplier_url", "kind": "url",
     "doc": "Ссылка на карточку поставщика/товара в Китае."},
    {"header": "Ссылка (Amazon)", "key": "amazon_url", "kind": "url",
     "doc": "Ссылка на товар на Amazon."},
]

COLUMN_DOCS: list[tuple[str, str]] = [(c["header"], c["doc"]) for c in REPORT_COLUMNS]

# Concise methodology returned to Claude alongside data (full text: SOURCING_GUIDE.md).
SOURCING_GUIDANCE = {
    "platforms": CHINA_PLATFORMS,
    "match_quality": list(MATCH_QUALITY),
    "rules": [
        "Цена за единицу зависит от объёма (лесенка MOQ). Сохрани ВСЕ уровни и "
        "бери цену под фактический объём заказа, а не самый дешёвый ≥1000.",
        "Ищи именно ТОТ ЖE товар: по модели/артикулу, фото, характеристикам и "
        "бренду. Если совпадение неполное — помечай «близкое» или «аналог».",
        "Используй поле Manufacturer из Amazon как ключ поиска фабрики — возможен "
        "прямой мэтч на производителя (OEM).",
        "Ищи не только на Alibaba: 1688 (себестоимость), Made-in-China и "
        "Global Sources (фабрики/OEM), DHgate (малые партии).",
    ],
    "verdict_thresholds": {
        "ЗАКУПАТЬ": f"маржа ≥ {BUY_MARGIN:.0%} и ROI ≥ {BUY_ROI:.0%}, мэтч точное/близкое",
        "ОТКАЗ": f"маржа < {REJECT_MARGIN:.0%} или ROI < {REJECT_ROI:.0%} или только аналог",
        "ПРОВЕРИТЬ": "промежуточные случаи / недостаточно данных",
    },
    "recommended_output": "По каждой паре (товар Amazon × поставщик) дай себестоимость "
    "landed, маржу, ROI, вердикт ЗАКУПАТЬ/ПРОВЕРИТЬ/ОТКАЗ и сценарии по объёму. "
    "Сопоставь данные Amazon и Китая, укажи гипотезы и риски.",
}
