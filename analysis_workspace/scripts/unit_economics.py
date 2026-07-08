#!/usr/bin/env python3
"""Этап 3: Unit-экономика Amazon.de для финального портфеля.
Все сборы FBA — живые (Keepa pickAndPackFee, 08.07.2026). Цены в EUR.
Модель: НДС 19% из цены; Referral 15%; PPC 12% от цены (год запуска);
возвраты 2%; landed = FOB*FX*(1+пошлина+3% QC/брак) + фрахт + 0.30 преп.
"""
import json, csv
from pathlib import Path

FX = 0.92          # USD -> EUR
VAT = 0.19
REFERRAL = 0.15
PPC = 0.12
RETURNS = 0.02
PREP = 0.30        # приемка/маркировка за шт
TARGET_MARGIN = 0.25

# товар: (цена входа €, реф.конкурент ASIN, цена конкурента €, FBA € (live),
#         хранение+проч €, FOB $ типовой, фрахт €/шт, пошлина, спрос ниши шт/мес,
#         доля цели %, категория пошлины)
PRODUCTS = [
    # --- Волна 1 ---
    dict(key="filter_delonghi", name="Фильтр совм. DeLonghi DLSC002, 6-pack",
         price=19.99, ref_asin="B0C7ZTVPPB", ref_price=19.94, fba=3.47,
         storage=0.40, fob_usd=6.00, freight=0.50, duty=0.035,
         demand=4000, share=0.20, hs="8421.21 (фильтры воды)"),
    dict(key="filter_jura", name="Фильтр совм. Jura (RFID), 6-pack",
         price=39.99, ref_asin="B0G1438SF7", ref_price=39.99, fba=3.46,
         storage=0.40, fob_usd=10.00, freight=0.50, duty=0.035,
         demand=2000, share=0.25, hs="8421.21"),
    dict(key="cherry_pitter", name="Kirschentkerner (вишнечистка, стол)",
         price=45.99, ref_asin="B0CSZ1KZZB", ref_price=49.99, fba=3.86,
         storage=0.45, fob_usd=5.00, freight=0.70, duty=0.085,
         demand=2000, share=0.20, hs="8210.00 (мех. кухонные устройства)"),
    dict(key="cooler_bag", name="Kühltasche faltbar 30L (сумка-холодильник)",
         price=19.99, ref_asin="B0CP2GLKW7", ref_price=21.24, fba=4.35,
         storage=0.40, fob_usd=3.20, freight=0.70, duty=0.097,
         demand=2500, share=0.20, hs="4202.92 (термосумки)"),
    # --- Волна 2 ---
    dict(key="waste_system", name="Mülltrennsystem 2×15L выдвижной",
         price=49.99, ref_asin="B0DTPH75V8", ref_price=57.11, fba=7.94,
         storage=1.00, fob_usd=12.00, freight=10.90, duty=0.065,
         demand=600, share=0.25, hs="3924/7326 (пластик+металл)"),
    dict(key="cooling_blanket", name="Kühldecke 150×200 Arc-Chill",
         price=42.99, ref_asin="B07QJ132TD", ref_price=54.99, fba=4.42,
         storage=0.60, fob_usd=8.50, freight=1.00, duty=0.12,
         demand=1500, share=0.15, hs="6301.40 (одеяла синт.)"),
    dict(key="fliegengitter", name="Fliegengitter Magnet 150×130, 4-pack",
         price=39.99, ref_asin="B0CX5K1K2D", ref_price=47.99, fba=5.48,
         storage=0.50, fob_usd=6.50, freight=1.25, duty=0.065,
         demand=2500, share=0.12, hs="3926/7019 (сетка+магниты)"),
    # --- Стратегические (свои котировки) ---
    dict(key="tv_stand", name="TV-стенд мобильный 43–75\" (BKDEP CT7501)",
         price=149.99, ref_asin="B0C37Q5B6J", ref_price=127.99, fba=14.11,
         storage=3.50, fob_usd=29.70, freight=6.60, duty=0.0,
         demand=250, share=0.30, hs="9403.20 (мебель метал.) 0%"),
    dict(key="zy3_cabinet", name="Hängeregisterschrank ZY-3 (Demity, 4 ящика)",
         price=219.00, ref_asin="B01FPD5ZUQ", ref_price=195.99, fba=25.00,
         storage=5.00, fob_usd=45.00, freight=22.00, duty=0.0,
         demand=60, share=0.35, hs="9403.10 (офисн. мебель метал.) 0%"),
    # --- Резерв ---
    dict(key="bread_bags", name="Brotbeutel лен/воск 2шт (резерв)",
         price=19.99, ref_asin="B0GHQMDL44", ref_price=20.99, fba=3.08,
         storage=0.35, fob_usd=2.20, freight=0.40, duty=0.12,
         demand=1200, share=0.15, hs="6305/6302 текстиль"),
    dict(key="mini_fridge", name="Мини-холодильник 4л (резерв, WEEE)",
         price=44.99, ref_asin="B0—AstroAI/Citybee", ref_price=44.99, fba=4.60,
         storage=0.80, fob_usd=15.50, freight=2.20, duty=0.022,
         demand=900, share=0.12, hs="8418.69 (2.2%)"),
]

def econ(p):
    price = p["price"]
    net = price / (1 + VAT)
    vat = price - net
    referral = REFERRAL * price
    ppc = PPC * price
    returns = RETURNS * price
    landed = p["fob_usd"] * FX * (1 + p["duty"] + 0.03) + p["freight"] + PREP
    costs_amz = referral + p["fba"] + p["storage"]
    profit = net - costs_amz - returns - ppc - landed
    margin = profit / price
    roi = profit / landed if landed else 0
    # максимально допустимый FOB для маржи 25%
    landed_max = net - costs_amz - returns - ppc - TARGET_MARGIN * price
    fob_max = (landed_max - p["freight"] - PREP) / (FX * (1 + p["duty"] + 0.03))
    # безубыточная цена при данном FOB (решаем price: net-fees(price)-landed=0)
    # net=P/1.19; fees_var=(REF+PPC+RET)*P; статика=fba+storage+landed
    denom = 1/1.19 - (REFERRAL + PPC + RETURNS)
    breakeven = (p["fba"] + p["storage"] + landed) / denom
    units = p["demand"] * p["share"]
    return dict(
        name=p["name"], price=price, ref_asin=p["ref_asin"], ref_price=p["ref_price"],
        net=round(net,2), vat=round(vat,2), referral=round(referral,2),
        fba=p["fba"], storage=p["storage"], ppc=round(ppc,2), returns=round(returns,2),
        fob_usd=p["fob_usd"], landed=round(landed,2),
        profit=round(profit,2), margin=round(margin*100,1), roi=round(roi*100,0),
        fob_max=round(fob_max,2), breakeven=round(breakeven,2),
        units_mo=int(units), profit_mo=int(profit*units),
        duty=f"{p['duty']*100:.1f}%", hs=p["hs"], freight=p["freight"],
    )

rows = [econ(p) for p in PRODUCTS]
out = Path("/home/user/Keepa/analysis_workspace/03_unit_economics")
out.mkdir(parents=True, exist_ok=True)

with open(out / "unit_economics.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys())
    w.writeheader(); w.writerows(rows)

hdr = f"{'Товар':<44} {'Цена':>7} {'Landed':>7} {'Приб/шт':>8} {'Маржа':>6} {'ROI':>5} {'FOB max$':>9} {'Б/у цена':>8} {'Приб/мес':>9}"
print(hdr); print("-"*len(hdr))
for r in rows:
    print(f"{r['name'][:43]:<44} {r['price']:>7.2f} {r['landed']:>7.2f} {r['profit']:>8.2f} {r['margin']:>5.1f}% {r['roi']:>4.0f}% {r['fob_max']:>9.2f} {r['breakeven']:>8.2f} {r['profit_mo']:>9}"),
print()
print("Допущения: FX 0.92, НДС 19%, Referral 15%, PPC 12%, возвраты 2%, преп 0.30€,")
print("QC/брак 3%, фрахт LCL ~120€/м³. FBA — живые тарифы Keepa 08.07.2026.")
print("FOB max$ — потолок закупки за шт для чистой маржи 25% ПОСЛЕ рекламы.")
