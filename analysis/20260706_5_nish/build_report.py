#!/usr/bin/env python3
"""Build the final XLSX report: unit economics, top-50, new products, UAE launch.

Reads Keepa JSONs from data/, applies fee models, writes
/home/user/Keepa/Products/Анализ_5_ниш_US_UK_DE_AE_<date>.xlsx
"""
import json
import math
import re
import time
import urllib.parse
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

import os
DATA = Path(os.environ.get("REPORT_DATA_DIR", Path(__file__).parent / "data"))
OUT = Path(os.environ.get("REPORT_OUT_DIR", "/home/user/Keepa/Products"))
OUT.mkdir(exist_ok=True)

# ---------------- FX / market constants (July 2026) ----------------
FX_USD = {"US": 1.0, "UK": 1.33, "DE": 1.14, "AE": 1 / 3.6725}  # local -> USD
CURR = {"US": "$", "UK": "£", "DE": "€", "AE": "AED"}
TLD = {"US": "com", "UK": "co.uk", "DE": "de", "AE": "ae"}
VAT = {"US": 0.0, "UK": 0.20, "DE": 0.19, "AE": 0.05}
# import duty on FOB (China origin), effective 2026
DUTY = {"US": 0.35, "UK": 0.04, "DE": 0.04, "AE": 0.05}
# landed freight per kg, USD (sea, incl. last-mile to FC)
FREIGHT_KG = {"US": 2.6, "UK": 2.9, "DE": 2.9, "AE": 1.9}
TARGET_MARGIN = 0.25  # target net profit as share of selling price

CAT_RU = {
    "seat_cushion": "Подушка на сиденье",
    "ice_maker": "Льдогенератор",
    "desk_pad": "Настольный коврик (desk pad)",
    "chair_mat": "Коврик под кресло",
    "shoe_rack": "Обувница / стеллаж для обуви",
}

# Alibaba typical FOB, USD per unit (research 06.07.2026)
ALIBABA_FOB = {
    "seat_cushion": (2.5, 5.5, 3.5),
    "ice_maker": (40.0, 85.0, 52.0),
    "desk_pad": (1.5, 4.0, 2.5),
    "chair_mat": (5.0, 14.0, 8.0),
    "shoe_rack": (4.0, 15.0, 7.0),
}
ALIBABA_KW = {
    "seat_cushion": "memory foam seat cushion office chair",
    "ice_maker": "countertop ice maker machine portable",
    "desk_pad": "PU leather desk pad mat large",
    "chair_mat": "office chair mat PVC floor protection",
    "shoe_rack": "shoe rack organizer storage cabinet",
}

# AE referral fee by category (sell.amazon.ae rate card 2026)
AE_REFERRAL = {
    "seat_cushion": 0.15,   # Home
    "ice_maker": 0.13,      # Small Appliances
    "desk_pad": 0.14,       # Office Products
    "chair_mat": 0.14,      # Office Products
    "shoe_rack": 0.15,      # Home / Furniture
}
# Default referral fallback for US/UK/DE when Keepa lacks the value
REFERRAL_FALLBACK = 0.15

# AE FBA fulfilment fee model, AED by unit weight kg (rate card tiers, approx.)
AE_FBA_TIERS = [
    (0.25, 7.2), (0.5, 8.0), (1.0, 9.5), (2.0, 11.0), (3.0, 12.5),
    (5.0, 14.5), (9.0, 17.0), (12.0, 19.5), (15.0, 25.0), (20.0, 31.0),
    (30.0, 41.5),
]

# US/UK/DE FBA fallback (USD/GBP/EUR) by weight when Keepa has no fbaFees
def fba_fallback(market, kg):
    if kg is None:
        kg = 1.0
    if market == "US":
        if kg <= 0.34: return 3.6
        if kg <= 0.45: return 4.0
        if kg <= 0.9: return 5.0
        if kg <= 1.3: return 5.9
        if kg <= 2.7: return 7.2
        if kg <= 9.0: return 9.5 + (kg - 2.7) * 0.4
        return 13.0 + kg * 0.35
    else:  # UK £ / DE €
        if kg <= 0.25: return 2.9
        if kg <= 0.5: return 3.2
        if kg <= 1.0: return 3.9
        if kg <= 2.0: return 5.2
        if kg <= 4.0: return 6.5
        if kg <= 9.0: return 8.5 + (kg - 4.0) * 0.5
        return 12.0 + kg * 0.3


def ae_fba_fee(kg):
    if kg is None:
        kg = 1.0
    for lim, fee in AE_FBA_TIERS:
        if kg <= lim:
            return fee
    return 41.5 + (kg - 30) * 1.5


def kg_of(rec):
    w = rec.get("packageWeight_g") or rec.get("itemWeight_g")
    return round(w / 1000.0, 2) if w else None


def est_monthly_sales(rec, market):
    """Demand estimate, units/month."""
    ms = rec.get("monthlySold")
    if ms:
        return ms
    rank = rec.get("rank_cur") or rec.get("rank_avg90")
    if not rank:
        return None
    # rough BSR->sales curve for large home/kitchen root categories
    scale = {"US": 90000.0, "UK": 35000.0, "DE": 45000.0}[market]
    est = scale / (rank ** 0.65)
    return int(round(est))


def clean_kw(title, n=6):
    words = re.sub(r"[^\w\s-]", " ", title or "").split()
    stop = {"for", "the", "and", "with", "von", "für", "mit", "und", "der", "die", "das", "of", "to", "in"}
    out = [w for w in words if w.lower() not in stop][:n]
    return " ".join(out)


def alibaba_url(rec, slug):
    kw = clean_kw(rec.get("title") or ALIBABA_KW[slug], 5)
    return "https://www.alibaba.com/trade/search?SearchText=" + urllib.parse.quote_plus(kw)


def economics(rec, market, slug, price_local=None):
    """Compute unit economics. Returns dict or None if no price."""
    price = price_local
    if price is None:
        price = rec.get("price_bb") or rec.get("price_new") or rec.get("price_amazon")
        if price:
            price = price / 100.0
    if not price:
        return None
    fx = FX_USD[market]
    price_usd = price * fx

    if market == "AE":
        ref_pct = AE_REFERRAL[slug]
        fba = ae_fba_fee(kg_of(rec))
    else:
        ref_pct = (rec.get("referralFeePercent") or REFERRAL_FALLBACK * 100) / 100.0
        fba_c = rec.get("fbaFees")
        fba = fba_c / 100.0 if fba_c else fba_fallback(market, kg_of(rec))

    referral = price * ref_pct
    storage = price * 0.03
    vat_amt = price - price / (1 + VAT[market])
    kg = kg_of(rec) or 1.0
    freight_usd = kg * FREIGHT_KG[market]
    freight = freight_usd / fx  # to local
    duty = DUTY[market]

    net_after_amz = price - referral - fba - storage - vat_amt
    target_profit = price * TARGET_MARGIN
    fob_max_local = (net_after_amz - freight - target_profit) / (1 + duty)
    fob_max_usd = max(fob_max_local * fx, 0)

    lo, hi, typ = ALIBABA_FOB[slug]
    landed_typ = (typ * (1 + duty)) / fx + freight  # local
    profit_typ = net_after_amz - freight - landed_typ * 0  # placeholder
    profit_typ = net_after_amz - (typ * (1 + duty)) / fx - freight
    margin_typ = profit_typ / price if price else None
    roi_typ = (profit_typ * fx) / (typ + kg * FREIGHT_KG[market]) if typ else None

    return {
        "price": round(price, 2),
        "price_usd": round(price_usd, 2),
        "ref_pct": round(ref_pct * 100, 1),
        "referral": round(referral, 2),
        "fba": round(fba, 2),
        "storage": round(storage, 2),
        "vat": round(vat_amt, 2),
        "all_fees": round(referral + fba + storage + vat_amt, 2),
        "net_after_amz": round(net_after_amz, 2),
        "freight": round(freight, 2),
        "fob_max_usd": round(fob_max_usd, 2),
        "fob_typ_usd": typ,
        "profit_typ": round(profit_typ, 2),
        "margin_typ_pct": round(margin_typ * 100, 1) if margin_typ is not None else None,
        "roi_typ_pct": round(roi_typ * 100, 0) if roi_typ else None,
        "kg": kg,
    }



CAT_MUST = {
    "seat_cushion": r"cushion|kissen|seat pad",
    "ice_maker": r"ice\s?maker|eisw(ü|u)rfel",
    "desk_pad": r"desk\s?(pad|mat)|schreibtischunterlage|mouse\s?pad|mausunterlage|mauspad",
    "chair_mat": r"(chair|floor|boden).{0,12}(mat|matte)|bodenschutz|floor protector",
    "shoe_rack": r"shoe|schuh",
}
CAT_BAN = {
    "seat_cushion": r"outdoor sofa set",
    "ice_maker": r"ice cream|slush|blender|filter|scoop|tray|bag|shaver|crusher accessor",
    "desk_pad": r"treadmill|walking pad|desk frame|standing desk converter",
    "chair_mat": r"yoga|exercise|treadmill",
    "shoe_rack": r"",
}

def title_ok(slug, title):
    t = (title or "").lower()
    if not re.search(CAT_MUST[slug], t):
        return False
    ban = CAT_BAN[slug]
    if ban and re.search(ban, t):
        return False
    return True

def load_all():
    rows = []
    for f in sorted(DATA.glob("*.json")):
        d = json.loads(f.read_text())
        for rec in d["records"]:
            if not rec.get("asin"):
                continue
            if not title_ok(d["category"], rec.get("title")):
                continue
            rows.append({"slug": d["category"], "market": d["market"],
                         "mode": d["mode"], **rec})
    return rows


# ---------------- XLSX ----------------
HDR_FILL = PatternFill("solid", fgColor="1F4E78")
HDR_FONT = Font(color="FFFFFF", bold=True, size=10)
LINK_FONT = Font(color="0563C1", underline="single", size=10)
THIN = Border(*[Side(style="thin", color="D9D9D9")] * 4)
GREEN = PatternFill("solid", fgColor="C6EFCE")
YELLOW = PatternFill("solid", fgColor="FFEB9C")
RED = PatternFill("solid", fgColor="FFC7CE")


def style_header(ws, ncols, row=1):
    for c in range(1, ncols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL
        cell.font = HDR_FONT
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws.freeze_panes = ws.cell(row=row + 1, column=3)


def add_row(ws, r, values, widths=None):
    for c, v in enumerate(values, 1):
        cell = ws.cell(row=r, column=c, value=v)
        cell.border = THIN
        cell.alignment = Alignment(vertical="top", wrap_text=(c == 3))
    return r + 1


COLS = [
    ("№", 4), ("Категория", 18), ("Товар", 52), ("ASIN", 13), ("Рынок", 7),
    ("Цена (лок.)", 10), ("Цена $", 9), ("Продажи/мес (оц.)", 11), ("BSR", 9),
    ("Рейтинг", 8), ("Отзывы", 9), ("Офферов", 8), ("Вес, кг", 7),
    ("Referral %", 8), ("Referral", 9), ("FBA fee", 9), ("Хранение ~3%", 9),
    ("VAT/НДС", 9), ("Все fees (лок.)", 10), ("Остаток после Amazon", 11),
    ("Фрахт/юнит", 9), ("Закупка МАКС (FOB $) ≤", 12), ("Типовая FOB $ (Alibaba)", 11),
    ("Прибыль/юнит (лок.)", 11), ("Маржа %", 9), ("ROI %", 8),
    ("Alibaba поиск", 14), ("Дата на Amazon", 12), ("Бренд", 14), ("Вердикт", 9),
]


def write_products_sheet(ws, rows_data):
    ws.append([c[0] for c in COLS])
    style_header(ws, len(COLS))
    for i, (col, w) in enumerate(COLS, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    r = 2
    for idx, x in enumerate(rows_data, 1):
        rec, eco = x["rec"], x["eco"]
        m = x["market"]
        amazon_link = f"https://www.amazon.{TLD[m]}/dp/{rec['asin']}"
        ali = alibaba_url(rec, x["slug"])
        tracking = rec.get("trackingSince")
        listed = None
        if tracking:
            listed = time.strftime("%Y-%m-%d", time.gmtime((tracking + 21564000) * 60))
        vals = [
            idx, CAT_RU[x["slug"]], (rec.get("title") or "")[:120], rec["asin"], m,
            eco["price"], eco["price_usd"], x["demand"], rec.get("rank_cur"),
            rec.get("rating"), rec.get("reviews"), rec.get("offers_new"), eco["kg"],
            eco["ref_pct"], eco["referral"], eco["fba"], eco["storage"],
            eco["vat"], eco["all_fees"], eco["net_after_amz"],
            eco["freight"], eco["fob_max_usd"], eco["fob_typ_usd"],
            eco["profit_typ"], eco["margin_typ_pct"], eco["roi_typ_pct"],
            "Alibaba", listed, rec.get("brand"), verdict_of(eco),
        ]
        r = add_row(ws, r, vals)
        acell = ws.cell(row=r - 1, column=4)
        acell.hyperlink = amazon_link
        acell.font = LINK_FONT
        lcell = ws.cell(row=r - 1, column=27)
        lcell.hyperlink = ali
        lcell.font = LINK_FONT
        mcell = ws.cell(row=r - 1, column=25)
        if eco["margin_typ_pct"] is not None:
            mcell.fill = GREEN if eco["margin_typ_pct"] >= 25 else (
                YELLOW if eco["margin_typ_pct"] >= 15 else RED)
        vcell = ws.cell(row=r - 1, column=30)
        vcell.fill = {"BUY": GREEN, "WATCH": YELLOW, "SKIP": RED}[vcell.value]
    ws.auto_filter.ref = f"A1:{get_column_letter(len(COLS))}{r - 1}"



def verdict_of(eco):
    m = eco.get("margin_typ_pct")
    fob_ok = eco["fob_max_usd"] >= eco["fob_typ_usd"]
    if m is None:
        return "WATCH"
    if m >= 25 and fob_ok:
        return "BUY"
    if m >= 12:
        return "WATCH"
    return "SKIP"


def dedupe(items):
    """Collapse listing variants: same brand + title prefix + market."""
    best = {}
    for x in items:
        rec = x["rec"]
        key = (x["market"], (rec.get("brand") or "").lower(),
               re.sub(r"\W", "", (rec.get("title") or "").lower())[:28])
        cur = best.get(key)
        if cur is None or (x["demand"] or 0) > (cur["demand"] or 0):
            best[key] = x
    return list(best.values())

def demand_key(x):
    d = x["demand"] or 0
    return d


def main():
    rows = load_all()
    print(f"loaded {len(rows)} records")
    enriched = []
    seen = set()
    for rec in rows:
        key = (rec["asin"], rec["market"], rec["mode"])
        if key in seen:
            continue
        seen.add(key)
        eco = economics(rec, rec["market"], rec["slug"])
        if not eco:
            continue
        demand = est_monthly_sales(rec, rec["market"])
        enriched.append({"rec": rec, "eco": eco, "market": rec["market"],
                         "slug": rec["slug"], "mode": rec["mode"], "demand": demand})

    top = dedupe([x for x in enriched if x["mode"] == "top"])
    new = dedupe([x for x in enriched if x["mode"] == "new"])
    # top-50: best demand per category balance (top 10 per category by demand)
    top_sorted = []
    for slug in CAT_RU:
        cat_rows = sorted([x for x in top if x["slug"] == slug],
                          key=demand_key, reverse=True)
        top_sorted.extend(cat_rows[:12])
    top50 = sorted(top_sorted, key=demand_key, reverse=True)[:50]
    new_sorted = sorted(new, key=demand_key, reverse=True)[:50]

    wb = Workbook()
    ws1 = wb.active
    ws1.title = "ТОП-50 ходовые"
    write_products_sheet(ws1, top50)
    ws2 = wb.create_sheet("Новинки с 02.2026")
    write_products_sheet(ws2, new_sorted)

    # -------- full data sheet (all markets, all records) --------
    ws_all = wb.create_sheet("Все товары (241)")
    all_sorted = sorted(enriched, key=lambda x: (x["slug"], x["mode"], -(x["demand"] or 0)))
    write_products_sheet(ws_all, all_sorted)

    # -------- UAE launch sheet: project top candidates to AE --------
    ws3 = wb.create_sheet("Запуск ОАЭ (расчёт)")
    ae_cols = [
        ("№", 4), ("Категория", 18), ("Товар (референс)", 52), ("ASIN реф.", 13),
        ("Рынок реф.", 8), ("Спрос реф., шт/мес", 11), ("Оц. цена AED", 10),
        ("Оц. цена $", 9), ("Referral % AE", 8), ("Referral AED", 9),
        ("FBA AE, AED", 9), ("VAT 5%", 8), ("Хранение", 8),
        ("Остаток после Amazon, AED", 12), ("Фрахт/юнит AED", 9),
        ("Закупка МАКС FOB $ ≤", 12), ("Типовая FOB $", 10),
        ("Прибыль/юнит AED", 10), ("Маржа %", 9), ("ROI %", 8), ("Alibaba", 12),
    ]
    ws3.append([c[0] for c in ae_cols])
    style_header(ws3, len(ae_cols))
    for i, (col, w) in enumerate(ae_cols, 1):
        ws3.column_dimensions[get_column_letter(i)].width = w
    # candidates: best of top50 from UK/DE/US, project AE price
    r = 2
    idx = 0
    for x in top50:
        idx += 1
        rec, m = x["rec"], x["market"]
        price_usd = x["eco"]["price_usd"]
        ae_price_aed = round(price_usd * 1.08 * 3.6725, 0)  # +8% import premium
        eco = economics(rec, "AE", x["slug"], price_local=ae_price_aed)
        if not eco:
            continue
        vals = [
            idx, CAT_RU[x["slug"]], (rec.get("title") or "")[:120], rec["asin"], m,
            x["demand"], ae_price_aed, round(ae_price_aed / 3.6725, 2),
            eco["ref_pct"], eco["referral"], eco["fba"], eco["vat"], eco["storage"],
            eco["net_after_amz"], eco["freight"], eco["fob_max_usd"],
            eco["fob_typ_usd"], eco["profit_typ"], eco["margin_typ_pct"],
            eco["roi_typ_pct"], "Alibaba",
        ]
        r = add_row(ws3, r, vals)
        c4 = ws3.cell(row=r - 1, column=4)
        c4.hyperlink = f"https://www.amazon.{TLD[m]}/dp/{rec['asin']}"
        c4.font = LINK_FONT
        cl = ws3.cell(row=r - 1, column=21)
        cl.hyperlink = alibaba_url(rec, x["slug"])
        cl.font = LINK_FONT
        mc = ws3.cell(row=r - 1, column=19)
        if eco["margin_typ_pct"] is not None:
            mc.fill = GREEN if eco["margin_typ_pct"] >= 25 else (
                YELLOW if eco["margin_typ_pct"] >= 15 else RED)
    ws3.auto_filter.ref = f"A1:U{r - 1}"

    # -------- fees reference sheet --------
    ws4 = wb.create_sheet("Комиссии и тарифы")
    ref_rows = [
        ["Справочник комиссий и допущений (июль 2026)"],
        [],
        ["Referral fee (комиссия Amazon)", "US", "UK", "DE", "AE (ОАЭ)"],
        ["Home & Kitchen", "15%", "15%", "15%", "15% (Home)"],
        ["Small Appliances (льдогенераторы)", "8%", "8-15%", "8-15%", "13%"],
        ["Office Products (коврики, desk pads)", "15%", "15%", "15%", "14%"],
        ["Furniture (обувницы-шкафы)", "15%", "15%", "15%", "15% ≤750 AED / 10% >750"],
        [],
        ["FBA fulfilment AE (AED, за юнит)", "≤0.25кг: 7.2", "≤1кг: ~9.5", "≤5кг: ~14.5", "≤12кг: 19.5", "до 30кг: 41.5"],
        ["FBA скидка AE", "−2 AED при цене товара <25 AED"],
        ["Хранение AE", "2 AED/куб.фут/мес"],
        [],
        ["VAT/НДС", "US: 0% (sales tax у покупателя)", "UK: 20%", "DE: 19%", "AE: 5%"],
        ["Импортная пошлина (Китай)", "US: ~35% (Sec.301+2025)", "UK: ~4%", "DE/EU: ~4%", "AE: 5%"],
        ["Фрахт (море), $/кг", "US: 2.6", "UK: 2.9", "DE: 2.9", "AE: 1.9 (Jebel Ali)"],
        ["Курсы", "EUR/USD 1.14", "GBP/USD 1.33", "USD/AED 3.6725 (фикс)"],
        [],
        ["Целевая чистая маржа", f"{int(TARGET_MARGIN*100)}% от цены — из неё выведен потолок закупки 'не более чем'"],
        ["Формула потолка закупки", "FOB_max = (Цена − Referral − FBA − Хранение − VAT − Фрахт − 0.25×Цена) / (1 + пошлина)"],
        [],
        ["Типовые FOB Alibaba, $ (мин–макс / типовая)"],
    ]
    for slug, (lo, hi, typ) in ALIBABA_FOB.items():
        ref_rows.append([CAT_RU[slug], f"{lo}–{hi}", f"типовая {typ}",
                         "https://www.alibaba.com/trade/search?SearchText=" +
                         urllib.parse.quote_plus(ALIBABA_KW[slug])])
    for row in ref_rows:
        ws4.append(row)
    ws4.column_dimensions["A"].width = 38
    for col in "BCDE":
        ws4.column_dimensions[col].width = 26
    ws4["A1"].font = Font(bold=True, size=12)

    # -------- methodology sheet --------
    ws5 = wb.create_sheet("Методика и оговорки")
    notes = [
        "МЕТОДИКА (06.07.2026)",
        "",
        "1. Данные: Keepa API (Amazon US/UK/DE), 90-дневная статистика. Продажи/мес: точные 'куплено за месяц' (US)",
        "   или оценка из BSR (UK/DE). ОАЭ: Keepa НЕ поддерживает amazon.ae — расчёт спроса и цены по паритету UK/DE",
        "   (+8% импортная премия), комиссии по официальному rate card sell.amazon.ae.",
        "2. 'Ходовые' = рейтинг ≥4.0, отзывы ≥50-100, подтверждённые продажи (monthlySold ≥200 US / BSR-топ UK-DE).",
        "3. 'Новинки' = отслеживаются Keepa с 01.02.2026 или позже, с ненулевым спросом.",
        "4. Потолок закупки ('не более чем', FOB $) — при котором чистая маржа 25% после ВСЕХ затрат:",
        "   комиссия Amazon + FBA + хранение 3% + VAT рынка + фрахт по весу + импортная пошлина.",
        "5. Маржа % и ROI % в таблицах посчитаны при ТИПОВОЙ FOB-цене Alibaba (столбец рядом).",
        "   Если 'Закупка МАКС' ниже типовой FOB — товар при целевой марже 25% не проходит: торгуйтесь или пропускайте.",
        "6. US-пошлина на товары из Китая ~35% (оценка с учётом Sec.301/2025) — сильно бьёт по марже US.",
        "   ОАЭ: пошлина 5%, VAT 5%, дешёвый фрахт — лучшая юнит-экономика; Германия — вторая.",
        "7. FBA fee US/UK/DE: точная из Keepa (fbaFees), при отсутствии — оценка по весовой сетке 2026.",
        "8. Ссылки Alibaba — поисковые (точный матч поставщика требует ручной проверки MOQ/сертификатов CE/UKCA/ESMA).",
        "9. Льдогенераторы в ОАЭ: обязательна регистрация ESMA/ECAS (электроприбор) — заложите 1-2 мес и ~$500-1500.",
        "10. Валюта строк — локальная валюта рынка (US $, UK £, DE €, AE AED), если не указано иное.",
    ]
    for n in notes:
        ws5.append([n])
    ws5.column_dimensions["A"].width = 120

    fn = OUT / f"Анализ_5_ниш_US_UK_DE_AE_{time.strftime('%Y%m%d')}.xlsx"
    wb.save(fn)
    print("saved", fn)
    print(f"top50: {len(top50)}, new: {len(new_sorted)}")


if __name__ == "__main__":
    main()
