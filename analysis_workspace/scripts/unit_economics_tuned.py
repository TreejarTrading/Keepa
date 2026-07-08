#!/usr/bin/env python3
"""Этап 3b: Оптимизированные точки входа — финальная экономика портфеля.
Сценарии подобраны по результатам базового прогона: где базовая цена не дает
маржу ≥18-25%, выбрана другая упаковка/размер/цена (реальная практика PL).
"""
import csv
from pathlib import Path

FX, VAT, REF, RET, PREP, QC = 0.92, 0.19, 0.15, 0.02, 0.30, 0.03

# ppc — индивидуально: расходники/B2B ниже, конкурентные ниши выше
P = [
    # Волна 1
    dict(name="Фильтр совм. DeLonghi DLSC002, 6-pack @ 24.99",
         note="против FILSWA 19.94 (6шт) — вход через качество+чистый немецкий листинг; ниша 20.99–24.99",
         price=24.99, ref="B0C7ZTVPPB", ref_p=19.94, fba=3.47, sto=0.40,
         fob=4.00, fr=0.50, duty=0.035, ppc=0.12, demand=4000, share=0.15),
    dict(name="Фильтр совм. Jura RFID, 6-pack @ 42.99",
         note="GLACIER FRESH 39.99 (снизил с 59.99); Waterdrop-ниша; расходник, LTV",
         price=42.99, ref="B0G1438SF7", ref_p=39.99, fba=3.46, sto=0.40,
         fob=10.00, fr=0.50, duty=0.035, ppc=0.10, demand=2000, share=0.25),
    dict(name="Kirschentkerner столовый @ 45.99",
         note="Thiru 49.99 сейчас (сезонный пик 2000/мес); закупка к маю 2027 или экспресс-партия",
         price=45.99, ref="B0CSZ1KZZB", ref_p=49.99, fba=3.86, sto=0.45,
         fob=5.00, fr=0.70, duty=0.085, ppc=0.12, demand=2000, share=0.20),
    dict(name="Kühltasche faltbar 40L @ 34.99",
         note="HELDENWERK 40L = 34.99 (новая линейка, 199 отз.) — заходим в крупный формат, не в 20L",
         price=34.99, ref="B0FL86NQVD", ref_p=34.99, fba=4.59, sto=0.45,
         fob=4.50, fr=0.90, duty=0.097, ppc=0.12, demand=1500, share=0.20),
    # Волна 2
    dict(name="Kühldecke 150×200 Arc-Chill @ 42.99",
         note="Elegear 54.99 в сезоне (ср.50.3) — вход -20%; сезон V–VIII; OEKO-TEX",
         price=42.99, ref="B07QJ132TD", ref_p=54.99, fba=4.42, sto=0.60,
         fob=8.50, fr=1.00, duty=0.12, ppc=0.12, demand=1500, share=0.15),
    dict(name="Fliegengitter Magnet 4er @ 39.99",
         note="EASYmaxx 47.99, но Amazon 1P на листинге (42.00) и рейтинг 4.1 — бить качеством рамки/магнитов",
         price=39.99, ref="B0CX5K1K2D", ref_p=47.99, fba=5.48, sto=0.50,
         fob=6.50, fr=1.25, duty=0.065, ppc=0.12, demand=2500, share=0.12),
    dict(name="Brotbeutel лен/пчел.воск 2шт @ 19.99",
         note="AirBanish 20.99, всего 101 отзыв, ниша свежая; микрокапитал, добивка контейнера",
         price=19.99, ref="B0GHQMDL44", ref_p=20.99, fba=3.08, sto=0.35,
         fob=2.20, fr=0.40, duty=0.12, ppc=0.12, demand=1200, share=0.15),
    # Стратегические
    dict(name="TV-стенд 43–75\" CT7501 @ 149.99 (FCL)",
         note="ONKRON-аналог B0C37Q5B6J упал до 127.99 (ср.232) — вход 149.99; фрахт FCL 60€/м³",
         price=149.99, ref="B0C37Q5B6J", ref_p=127.99, fba=14.11, sto=3.50,
         fob=29.70, fr=3.30, duty=0.0, ppc=0.10, demand=250, share=0.30),
    dict(name="Hängeregisterschrank ZY-3 @ 219 (B2B)",
         note="Jan Nowak V005 204–290 с рейтингом 3.3–3.5; Amazon Business; PPC ниже (B2B, узкая ниша)",
         price=219.00, ref="B01FPD5ZUQ", ref_p=195.99, fba=25.00, sto=5.00,
         fob=45.00, fr=22.00, duty=0.0, ppc=0.05, demand=60, share=0.35),
    # Отклоненные (для прозрачности в отчете)
    dict(name="[ОТКЛОНЕН] Mülltrennsystem 2×15L @ 57.11",
         note="9.46 кг → фрахт 10.9 + FBA 7.94 съедают все; работает только у SONGMICS с их масштабом",
         price=57.11, ref="B0DTPH75V8", ref_p=57.11, fba=7.94, sto=1.00,
         fob=12.00, fr=10.90, duty=0.065, ppc=0.12, demand=600, share=0.25),
    dict(name="[РЕЗЕРВ] Мини-холодильник 4л @ 44.99",
         note="маржа тонкая + WEEE/CE; только если комиссия 7% (Elektro-Großgeräte) подтвердится",
         price=44.99, ref="AstroAI/Citybee", ref_p=44.99, fba=4.60, sto=0.80,
         fob=15.50, fr=2.20, duty=0.022, ppc=0.12, demand=900, share=0.12),
]

def econ(p):
    price, fba, sto, ppc = p["price"], p["fba"], p["sto"], p["ppc"]
    net = price / (1 + VAT)
    referral = REF * price
    landed = p["fob"] * FX * (1 + p["duty"] + QC) + p["fr"] + PREP
    profit = net - referral - fba - sto - RET*price - ppc*price - landed
    margin = profit / price * 100
    roi = profit / landed * 100
    denom = 1/1.19 - (REF + ppc + RET)
    breakeven = (fba + sto + landed) / denom
    for tgt in (0.25, 0.20):
        lm = net - referral - fba - sto - RET*price - ppc*price - tgt*price
        p[f"fobmax{int(tgt*100)}"] = (lm - p["fr"] - PREP) / (FX*(1+p["duty"]+QC))
    units = p["demand"] * p["share"]
    return dict(name=p["name"], price=price, ref=p["ref"], ref_p=p["ref_p"],
                fob=p["fob"], landed=round(landed,2), profit=round(profit,2),
                margin=round(margin,1), roi=round(roi,0),
                fob_max25=round(p["fobmax25"],2), fob_max20=round(p["fobmax20"],2),
                breakeven=round(breakeven,2), units=int(units),
                profit_mo=int(profit*units), ppc=int(ppc*100), note=p["note"])

rows = [econ(x) for x in P]
out = Path("/home/user/Keepa/analysis_workspace/03_unit_economics")
with open(out/"unit_economics_final.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=rows[0].keys()); w.writeheader(); w.writerows(rows)

h = f"{'Товар @ цена входа':<50} {'FOB$':>6} {'Landed':>7} {'Приб':>6} {'Маржа':>6} {'ROI':>5} {'FOBmax25%':>9} {'FOBmax20%':>9} {'Б/у':>7} {'Приб/мес':>8}"
print(h); print("-"*len(h))
tot = 0
for r in rows:
    flag = "" if r["name"].startswith("[") else "✓"
    if flag: tot += r["profit_mo"]
    print(f"{r['name'][:49]:<50} {r['fob']:>6.2f} {r['landed']:>7.2f} {r['profit']:>6.2f} {r['margin']:>5.1f}% {r['roi']:>4.0f}% {r['fob_max25']:>9.2f} {r['fob_max20']:>9.2f} {r['breakeven']:>7.2f} {r['profit_mo']:>8}")
print("-"*len(h))
print(f"Портфель (9 SKU, консервативные доли ниш): ≈ {tot:,} €/мес чистыми после рекламы")
