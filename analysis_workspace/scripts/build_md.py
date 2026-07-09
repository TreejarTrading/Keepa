#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, os
BASE="/home/user/Keepa"
d=json.load(open(os.environ.get("DATA_JSON",f"{BASE}/analysis_workspace/03_unit_economics/uae_final20.json")))
meta=json.load(open(os.environ.get("META_JSON",f"{BASE}/analysis_workspace/04_alibaba/sku_meta.json")))
OUT_MD=os.environ.get("OUT_MD",f"{BASE}/FINAL_REPORT_Amazon_UAE_2026-07.md")
TITLE=os.environ.get("MD_TITLE","20 товаров-новинок из Home & Kitchen")
NICHE=os.environ.get("MD_NICHE","Home & Kitchen — мебель, офисные кресла")
XLSX_NAME=os.environ.get("XLSX_NAME","UAE_HomeKitchen_TEO_Model_2026-07.xlsx")
DOCX_NAME=os.environ.get("DOCX_NAME","UAE_HomeKitchen_Report_2026-07.docx")
QTY={"B0GKMVTD6V":600,"B0GV2DHXWS":500,"B0GT8HK7LS":300,"B0GZVM23CF":300,"B0H13ZY2W4":250,
     "B0GQHGFFHC":300,"B0GJ4NHH4L":300,"B0GYF91BXB":1200,"B0GSZHLZ3B":500,"B0GZZ3VM69":400,
     "B0G5DSK3YF":400,"B0GCJQ4Z51":400,"B0GF7LLCL8":300,"B0GDTFFKYC":500,"B0FZRGB6BN":120,
     "B0GXKMXLDC":120,"B0H2B94R5F":150,"B0GN1P7DTT":80,"B0GL357H51":200,"B0G1SX2D8H":200}
def get_qty(x):
    if os.environ.get("FALLBACK_QTY")=="1": return max(60,round(x.get("uae_sales_mo",100)*3))
    return QTY.get(x["asin"]) or max(60,round(x.get("uae_sales_mo",100)*3))
USD_AED=3.6725; CIT=0.09
capital=sum(get_qty(x)*x["s_landed_aed"] for x in d)
mo=sum(x["mo_ebitda_pot"] for x in d)
launch=round(float(os.environ.get("LAUNCH_BASE","129000"))*1.1)
invest=capital+launch; after=mo*(1-CIT); pб=invest/after; roi=after*12/invest
L=[]
L.append(f"# 🇦🇪 Amazon ОАЭ (amazon.ae): {TITLE} — финальный отчёт\n")
L.append(f"**Дата:** 09.07.2026 · **Источник спроса:** новинки Amazon США (живой Keepa) · **Рынок продажи:** Amazon.ae (FBA)  ")
L.append(f"**Ниша клиента:** {NICHE}\n")
L.append("## 1. Резюме\n")
L.append(f"**Рекомендация: запускать 20 SKU {os.environ.get('MD_WAVE_WORD','тремя волнами')}. Стартовые инвестиции ≈ {invest:,.0f} AED "
 f"(≈ ${invest/USD_AED:,.0f}): закупка ≈ {capital:,.0f} + запуск ≈ {launch:,.0f}. Потенциал ≈ {mo:,.0f} AED "
 f"EBITDA/мес; после налога 9% ≈ {after:,.0f}/мес. Окупаемость ≈ {pб:.1f} мес, ROI 12 мес ≈ {roi*100:.0f}%.**".replace(","," ")+"\n")
L.append("Спрос берём из новинок Amazon США, продаём в ОАЭ (ниже конкуренция, выше розница в AED). "
 "Экономика с полной нагрузкой: НДС 5% + Referral 15% + FBA(ОАЭ) + пошлина 5% + фрахт + PPC + купон + маркетинг + возвраты. "
 "Порог рабочего режима: маржа ≥15%, ROI ≥40%, EBITDA/шт >0. По ТЗ отдельно учтён агрессивный запуск (PPC 35%, купон 10%).\n")
L.append("## 2. Портфель 20 SKU (рабочий режим)\n")
L.append("| # | Товар | ASIN (amazon.ae) | Категория | Цена AED | Марж % | ROI % | EBITDA/шт AED | Потенц. AED/мес | Alibaba |")
L.append("|---|-------|------------------|-----------|---------:|-------:|------:|--------------:|----------------:|---------|")
for i,x in enumerate(d,1):
    a=x["asin"]; md=meta[a]
    L.append(f"| {i} | {md['ru']} | [{a}](https://www.amazon.ae/dp/{a}) | {md['cat_ru']} | "
     f"{x['s_price_aed']:,.0f} | {x['s_margin']:.1f} | {x['s_roi']:.0f} | {x['s_ebitda_unit']:,.0f} | "
     f"{x['mo_ebitda_pot']:,.0f} | [ссылка]({md['alibaba'][0]}) |".replace(","," "))
L.append(f"| | **ИТОГО** | | | | | | | **{mo:,.0f}** | |".replace(","," ")+"\n")
L.append("## 3. Технико-экономическое обоснование (структура затрат ОАЭ)\n")
for t in ["Валюта USD→AED 3.6725 (фикс.).","НДС ОАЭ 5% (в цене).","Referral Home&Kitchen/декор 15% (8% при ≤50 AED).",
 os.environ.get("MD_FBA_NOTE","FBA Amazon.ae: стандарт 7.2–21.5 AED; крупногабарит/тяжёлые (кресла) 60–108 AED."),
 os.environ.get("MD_FREIGHT_NOTE","Фрахт море Китай→Джебель-Али ≈ $165/м³ (по объёму, проверка по весу); кресла — FCL."),
 "FOB с завода — ориентир, подтверждается RFQ у 3–5 поставщиков Alibaba.","Пошлина ОАЭ 5% от CIF.",
 "PPC: запуск 35% / рабочий режим 12%. Купон: запуск 10% / рабочий 3%. Маркетинг 3%, возвраты 2%."]:
    L.append(f"- {t}")
L.append("\n**EBITDA/шт = Чист. выручка (без НДС) − (Referral + FBA + PPC + Купон + Маркетинг + Возвраты) − Landed COGS.**\n")
L.append("## 4. Инвестиционный анализ\n")
L.append("| Показатель | Значение |")
L.append("|---|---:|")
for k,v in [("Оборотный капитал (закупка)",f"{capital:,.0f} AED"),("Бюджет запуска",f"{launch:,.0f} AED"),
 ("ИТОГО стартовые инвестиции",f"{invest:,.0f} AED (≈ ${invest/USD_AED:,.0f})"),
 ("Потенциал EBITDA/мес",f"{mo:,.0f} AED"),("Прибыль/мес после налога 9%",f"{after:,.0f} AED"),
 ("Окупаемость",f"{pб:.1f} мес"),("ROI за 12 мес",f"{roi*100:.0f}%")]:
    L.append(f"| {k} | {v} |".replace(","," "))
L.append("\n**Волны:** "+os.environ.get("MD_WAVES","1) охлаждение/вентиляторы + ремни для переноски + вакуумные пакеты (быстрый ROI); "
 "2) воздух/климат, уборка, ванная, кухня, декор; 3) мебель и офисные кресла (FCL), ковёр.")+"\n")
L.append("## 5. Выводы\n")
L.append(os.environ.get("MD_CONCLUSION",
 "Запуск целесообразен: 20 новинок США проходят по марже/прибыли/ROI/EBITDA для .ae в рабочем режиме. "
 "14 быстрых оборотных SKU дают денежный поток и высокий ROI (40–140%), 6 SKU вашей ниши (мебель/офисные кресла) — "
 "высокий чек и абсолютную прибыль. Фаза PPC 35% — управляемый бюджет разгона, а не постоянное состояние. "
 "Все цифры пересчитываются в Excel-модели при вводе ваших данных.")+"\n")
L.append(f"**Приложения:** `deliverables/{XLSX_NAME}` (живые формулы), "
 f"`deliverables/{DOCX_NAME}` (вывод + инвестанализ).\n")
L.append("---\n*Данные Keepa (США, 09.07.2026). Цены ОАЭ/FOB/фрахт/FBA — ориентиры для планирования; "
 "подтверждаются RFQ и FBA-калькулятором Seller Central .ae. Ссылки Alibaba — реальные карточки/витрины.*")
open(OUT_MD,"w").write("\n".join(L))
print("saved markdown report")

# Alibaba stage file
A=["# Этап Alibaba — ссылки для закупки 20 SKU (ОАЭ), 09.07.2026\n",
 "⚠️ Alibaba блокирует автопарсинг карточек — FOB/MOQ ниже индикативные, подтверждать RFQ у 3–5 поставщиков.\n"]
for i,x in enumerate(d,1):
    a=x["asin"]; md=meta[a]
    A.append(f"### {i}. {md['ru']}  ·  [{a}](https://www.amazon.ae/dp/{a})")
    A.append(f"- {md['fob_note']}")
    for u in md["alibaba"]: A.append(f"- {u}")
    A.append("")
open(os.environ.get("OUT_ALIBABA",f"{BASE}/analysis_workspace/04_alibaba/STAGE_UAE_ALIBABA_LINKS.md"),"w").write("\n".join(A))
print("saved alibaba stage")
