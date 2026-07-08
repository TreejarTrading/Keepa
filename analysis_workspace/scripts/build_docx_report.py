#!/usr/bin/env python3
"""DOCX-версия отчета для руководства (зеркало HTML-артефакта)."""
import docx
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

# Палитра (light из артефакта)
INK = RGBColor(0x20, 0x24, 0x2B)
MUTED = RGBColor(0x5C, 0x64, 0x70)
ACCENT = RGBColor(0x8A, 0x5A, 0x0E)   # amber ink
GOOD = RGBColor(0x1F, 0x7D, 0x54)
BAD = RGBColor(0xA8, 0x40, 0x2C)
FEE = RGBColor(0x2E, 0x6D, 0xA4)
THEAD_HEX = "F2EFE7"
CARD_HEX = "FAF8F2"

doc = Document()

# Базовые стили
st = doc.styles["Normal"]
st.font.name = "Calibri"; st.font.size = Pt(10.5); st.font.color.rgb = INK
st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
for sec in doc.sections:
    sec.left_margin = Cm(1.9); sec.right_margin = Cm(1.9)
    sec.top_margin = Cm(1.6); sec.bottom_margin = Cm(1.6)

def para(text="", size=10.5, bold=False, color=INK, space_after=6, style=None, align=None, italic=False):
    p = doc.add_paragraph(style=style)
    if align: p.alignment = align
    p.paragraph_format.space_after = Pt(space_after)
    if text:
        r = p.add_run(text); r.font.size = Pt(size); r.bold = bold; r.italic = italic
        r.font.color.rgb = color
    return p

def add_run(p, text, size=10.5, bold=False, color=INK, italic=False, mono=False):
    r = p.add_run(text); r.font.size = Pt(size); r.bold = bold; r.italic = italic
    r.font.color.rgb = color
    if mono: r.font.name = "Consolas"
    return r

def hyperlink(p, url, text, size=10.5, bold=False, color=ACCENT, mono=False):
    part = p.part
    r_id = part.relate_to(url, docx.opc.constants.RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), r_id)
    new_run = OxmlElement("w:r"); rPr = OxmlElement("w:rPr")
    c = OxmlElement("w:color"); c.set(qn("w:val"), "%02X%02X%02X" % (color[0], color[1], color[2])); rPr.append(c)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rPr.append(u)
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); rPr.append(sz)
    if bold: b = OxmlElement("w:b"); rPr.append(b)
    if mono:
        f = OxmlElement("w:rFonts"); f.set(qn("w:ascii"), "Consolas"); f.set(qn("w:hAnsi"), "Consolas"); rPr.append(f)
    new_run.append(rPr)
    t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve")
    new_run.append(t); h.append(new_run); p._p.append(h)
    return h

def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)

def heading(num, text):
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(16); p.paragraph_format.space_after = Pt(6)
    add_run(p, f"{num}  ", size=11, bold=True, color=MUTED, mono=True)
    add_run(p, text, size=16, bold=True, color=INK)
    # линия снизу
    pPr = p._p.get_or_add_pPr(); pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom"); bottom.set(qn("w:val"), "single"); bottom.set(qn("w:sz"), "12")
    bottom.set(qn("w:space"), "3"); bottom.set(qn("w:color"), "20242B")
    pbdr.append(bottom); pPr.append(pbdr)

def table(headers, rows, widths=None, fontsize=9, header_fill=THEAD_HEX, num_cols=None):
    t = doc.add_table(rows=1, cols=len(headers)); t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.style = "Table Grid"
    num_cols = num_cols or set()
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]; cell.text = ""
        p = cell.paragraphs[0]; add_run(p, h, size=fontsize - 0.5, bold=True, color=MUTED)
        shade(cell, header_fill)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cell = cells[i]; cell.text = ""
            p = cell.paragraphs[0]
            if i in num_cols: p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            if callable(v): v(p)
            else: add_run(p, str(v), size=fontsize)
    if widths:
        for i, w in enumerate(widths):
            for row in t.rows: row.cells[i].width = Cm(w)
    return t

# ===== ШАПКА =====
para("TREEJAR TRADING · ОТДЕЛ ЗАКУПОК · AMAZON EU", size=9, bold=True, color=MUTED, space_after=2)
p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(4)
add_run(p, "Портфель запуска на Amazon.de: 9 SKU в трех волнах", size=24, bold=True)
para("Отчет от 08.07.2026 · Рынок: Германия (FBA) · База: 49 файлов аналитики (Keepa BlackBox — 500 бестселлеров DE, "
     "Helium 10, нишевые отчеты, PI и котировки фабрик) + живая перепроверка каждого конкурента через Keepa API "
     "08.07.2026 + верифицированные карточки Alibaba.", size=9.5, color=MUTED, space_after=8)
p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(14)
add_run(p, "  РЕКОМЕНДОВАНО К ЗАКУПКЕ · бюджет ≈ €45–48 тыс. · потенциал ≈ €25 тыс./мес  ", size=11, bold=True, color=GOOD)

# ===== 01 РЕЗЮМЕ =====
heading("01", "Резюме для руководства")
para("Из всей собранной аналитики по четырем рынкам к запуску на Amazon Германия отобраны 9 товаров: "
     "4 всесезонных SKU первой волны (заказ немедленно, продажи с октября — под пик Q4), 3 сезонных SKU второй "
     "волны (заказ ноябрь–январь, продажи с марта 2027) и 2 стратегических SKU, по которым котировки фабрик уже "
     "в руках. Все маржи в отчете — чистые, после рекламы, на живых тарифах FBA конкурентов.")
table(["Показатель", "Значение", "Комментарий"], [
    ["SKU / ниши", "9 SKU · 6 ниш", "Без электроники — ноль затрат на CE/WEEE"],
    ["Бюджет запуска", "€45–48 тыс.", "Товар + фрахт + комплаенс + стартовый PPC"],
    ["Потенциал прибыли", "≈ €25.2 тыс./мес", "Чистыми после рекламы, полный разгон 6–9 мес"],
    ["Маржинальность", "19–32% · ROI 63–243%", "Окупаемость капитала 4–6 мес, 2–4 оборота/год"],
], widths=[4.2, 4.6, 8.4], fontsize=9.5)

# ===== 02 ЛОГИКА =====
heading("02", "Логика отбора: почему именно эти товары")
para("Воронка данных:", bold=True, space_after=2)
for s in ["500 бестселлеров Amazon.de (Keepa BlackBox) → скоринг → 30 товаров A-класса;",
          "наложение сорсинг-контура: реальные FOB-диапазоны Alibaba → Landed-COGS → вердикты GO/TEST/SKIP;",
          "отдельные глубокие отчеты: ТВ-стенды (котировка BKDEP), металлическая мебель (PI Demity), мини-холодильники, кронштейны;",
          "живая перепроверка 08.07.2026 каждого финалиста через Keepa API → 9 SKU."]:
    para("•  " + s, size=10, space_after=2)
para("Пять фильтров допуска:", bold=True, space_after=2)
for s in ["Цена 20–60 € (ниже 15 € комиссии съедают маржу; исключение — стратегические SKU с прибылью €36–41/шт);",
          "ниша принадлежит private label, а не Amazon 1P (36% топа!) и не мегабрендам WMF/Philips/Bosch;",
          "барьер отзывов ≤ 2 500 у лидера — догоняем за 3–4 месяца;",
          "маржа ≥ 19% после рекламы при полной модели затрат;",
          "без электроники — экономия €3–5 тыс./год и 6–8 недель сертификации."]:
    para("•  " + s, size=10, space_after=2)
para("Главный вывод анализа рынка: на Amazon.de дешевый товар структурно убыточен (при цене <10 € медианная маржа "
     "−4%), здоровая экономика начинается с 20 € (21–29%). Целимся в коридор 20–60 € плюс два высокочековых "
     "стратегических SKU.", size=10, italic=True, color=ACCENT)

# ===== 03 ПОРТФЕЛЬ =====
heading("03", "Портфель одним экраном")
PORT = [
    ["В1", "Фильтр совм. Jura (RFID), 6-pack", "42.99", "€10.06", "23.4%", "95%", "$9.30", "5 030"],
    ["В1", "Фильтр совм. DeLonghi DLSC002, 6-pack", "24.99", "€5.16", "20.7%", "109%", "$2.89", "3 098"],
    ["В1", "Kühltasche faltbar 40L", "34.99", "€8.35", "23.9%", "142%", "$4.12", "2 505"],
    ["В1", "Brotbeutel лен/воск, 2-pack", "19.99", "€4.54", "22.7%", "150%", "$1.77", "817"],
    ["СТРАТ", "TV-стенд мобильный 43–75\" (CT7501)", "149.99", "€36.19", "24.1%", "114%", "$28.32", "2 714"],
    ["СТРАТ", "Hängeregisterschrank ZY-3 (B2B)", "219.00", "€40.91", "18.7%", "63%", "$30.40", "859"],
    ["В2", "Kirschentkerner (вишнечистка)", "45.99", "€14.87", "32.3%", "243%", "$8.29", "5 948"],
    ["В2", "Fliegengitter Magnet 150×130, 4-pack", "39.99", "€7.93", "19.8%", "98%", "$4.45", "2 378"],
    ["В2", "Kühldecke Arc-Chill 150×200", "42.99", "€8.35", "19.4%", "81%", "$6.23", "1 877"],
    ["", "ИТОГО портфель (доли ниш 12–35%)", "", "", "", "", "", "≈ 25 226"],
]
table(["Волна", "Товар", "Вход €", "Прибыль/шт", "Маржа", "ROI", "Закупка ≤ (25%)", "€/мес"],
      PORT, widths=[1.5, 6.4, 1.7, 2.2, 1.6, 1.4, 2.4, 1.9], fontsize=9, num_cols={2,3,4,5,6,7})
para("«Закупка ≤» — потолок FOB $/шт для чистой маржи ≥25% после рекламы. €/мес — полный разгон 6–9 мес; "
     "первые 3 месяца реалистично 30–40% цифры.", size=8.5, color=MUTED)

# ===== 04 КАРТОЧКИ =====
heading("04", "Карточки SKU: конкуренты · экономика · Alibaba")
para("Модель на 1 шт: НДС 19% изъят из цены · Referral 15% · FBA — живой тариф конкурента (Keepa 08.07.2026) · "
     "PPC 12% (Jura 10%, B2B 5%) · возвраты 2% · Landed = FOB×0.92×(1+пошлина+3% QC) + фрахт + €0.30 преп.",
     size=9, color=MUTED)

SKUS = [
 dict(wave="Волна 1", name="Фильтр совм. Jura E8/E6 (RFID), 6-pack", price="42.99 €",
      comp=[("Лидер: GLACIER FRESH ", "B0G1438SF7", " — 39.99 € (ср. 90д 52.99), ~2 000 шт/мес, 351 отзыв, 4.8★, 1 оффер"),
            ("Соседние: Waterdrop Philips ", "B09NRJNV7M", " · Waterdrop Siemens B07M5GK693")],
      econ=("€10.06", "23.4%", "95%", "$9.30", "25.35 €"),
      split=("Amazon+реклама 52% (22.33 €)", "Закупка 25% (10.60 €)", "Прибыль 23% (10.06 €)"),
      ali=[("Прямая фабрика лидера: Ningbo Koze Purification (производитель GLACIER FRESH; kozerofilter.com)", None),
           ("Карточка Jura Claris", "https://www.alibaba.com/product-detail/For-Jura-Filter-Claris-Blue-New_1600312097630.html"),
           ("Clearyl/Capresso", "https://www.alibaba.com/product-detail/Coffee-Machine-Water-Filter-Replacement-Compatible-1601239019634.html"),
           ("Витрина Claris Smart", "https://www.alibaba.com/showroom/jura-filterpatrone-claris-smart.html")],
      risk="Расходник → повторная покупка каждые 1–2 мес (LTV). Риски: RFID-совместимость (видео-тест E8/E6/Z8) · "
           "только «kompatibel mit» · LFGB ~€1.5–2.5 тыс."),
 dict(wave="Волна 1", name="Фильтр совм. DeLonghi DLSC002, 6-pack", price="24.99 €",
      comp=[("Лидер: FILSWA ", "B0C7ZTVPPB", " — 19.94 €, ~4 000 шт/мес (+218 отзывов/мес!), 2 527 отз., 4.7★, "
             "волатильность цены 0.05. Ниша Wessper/AquaCrest 20.99–24.99 €")],
      econ=("€5.16", "20.7%", "109%", "$2.89", "15.61 €"),
      split=("Amazon+реклама 61% (15.11 €)", "Закупка 19% (4.72 €)", "Прибыль 21% (5.16 €)"),
      ali=[("Карточка DLSC002 №1", "https://www.alibaba.com/product-detail/Coffee-Machine-Filter-Fit-for-Delonghi_1601227212670.html"),
           ("№2", "https://www.alibaba.com/product-detail/Water-Filter-for-Delonghi-DLSC002-Delongie_1600383388162.html"),
           ("№3 factory price", "https://www.alibaba.com/product-detail/Wholesale-Factory-Price-Household-Use-Auto_1600305115799.html"),
           ("Витрина", "https://www.alibaba.com/showroom/dlsc002-water-filter.html")],
      risk="Рыночный FOB картриджа $0.5–0.7 → потолок $2.89/6-pack реален. Дифференциация: 6+2 пака, кокосовый "
           "уголь, вкладыш-календарь замены."),
 dict(wave="Волна 1", name="Kühltasche faltbar 40L — сумка-холодильник", price="34.99 €",
      comp=[("Лидер: HELDENWERK 40L ", "B0FL86NQVD", " — 34.99 € (линейка свежая, 199 отз.) · семья groß "
             "B0CP2GLKW7 21.24 € · 2 000/мес · 898 отз. · 4.5★ · 1 оффер")],
      econ=("€8.35", "23.9%", "142%", "$4.12", "19.82 €"),
      split=("Amazon+реклама 59% (20.78 €)", "Закупка 17% (5.87 €)", "Прибыль 24% (8.35 €)"),
      ali=[("Collapsible Large Leakproof", "https://www.alibaba.com/product-detail/Collapsible-Large-Cooler-Bag-Insulated-Leakproof_1601231338691.html"),
           ("Foldable big capacity", "https://www.alibaba.com/product-detail/Foldable-large-capacity-big-insulated-cooler_1600958125788.html"),
           ("Leakproof foldable", "https://www.alibaba.com/product-detail/Leakproof-Insulated-Cooler-Bag-Foldable-Lunch_1601125563200.html"),
           ("Custom logo 600D Oxford", "https://www.alibaba.com/product-detail/Custom-Logo-600D-Oxford-Lunch-Cooler_1600868739125.html")],
      risk="Самый низкий барьер отзывов выборки. Только 40L-формат (в 20L маржа ~10%). Проверить PEVA-вкладыш, "
           "молнии, 12ч холода. VerpackG/LUCID."),
 dict(wave="Волна 1", name="Brotbeutel лен + пчелиный воск, 2-pack", price="19.99 €",
      comp=[("Лидер: AirBanish ", "B0GHQMDL44", " — 20.99 €, ~1 000 шт/мес, всего 101 отзыв (ниша моложе года), 4.5★")],
      econ=("€4.54", "22.7%", "150%", "$1.77", "11.73 €"),
      split=("Amazon+реклама 62% (12.42 €)", "Закупка 15% (3.03 €)", "Прибыль 23% (4.54 €)"),
      ali=[("XL Sourdough Beeswax 2-Pack (точный аналог)", "https://www.alibaba.com/product-detail/2-Pack-Sourdough-Beeswax-Bread-Bags_1601515786986.html"),
           ("Фабрика Jiahao", "https://www.alibaba.com/product-detail/sourdough-bread-storage-beeswax-lining-bag_1601416846984.html"),
           ("Витрина linen bread bag", "https://www.alibaba.com/showroom/linen-bread-bag.html")],
      risk="Микро-ставка: MOQ-вход ≈ $1.1 тыс., добивает контейнер Волны 1. ЭКО-тренд. Воск food-grade, LFGB желателен."),
 dict(wave="Стратегический", name="TV-стенд мобильный 43–75\" (CT7501)", price="149.99 €",
      comp=[("ONKRON (уронил цены на 20–45% с июня): аналог ", "B0C37Q5B6J", " — 127.99 € (ср. 90д 232.57!), BSR 12 136 · "
             "50–90\" B0C59GH76B 229.99 € · 32–65\" B085QL383L 131.99 € · 50–100\" B0BSR8QBD2 279.99 €")],
      econ=("€36.19", "24.1%", "114%", "$28.32", "86.53 €"),
      split=("Amazon+реклама 55% (82.06 €)", "Закупка 21% (31.74 €)", "Прибыль 24% (36.19 €)"),
      ali=[("✅ Котировка SUZHOU BKDEP от 26-06-04 в руках (CT7501 $29.70 · CT9501 $43.60 · CT90 $52.20 · CF1001 $149)", None),
           ("Mobile TV Stand 32–75\"", "https://www.alibaba.com/product-detail/Mobile-TV-Stand-Rolling-Cart-Floor_1601426411417.html"),
           ("LUMI", "https://www.alibaba.com/product-detail/LUMI-Economical-Modern-Rolling-Height-Adjustable_62292480460.html"),
           ("Unho 65–100\"", "https://www.alibaba.com/product-detail/Unho-Large-Mobile-TV-Floor-Stand_1601418332981.html")],
      risk="Пилот 200 шт CT7501 (+60 шт CT9501 опц.). Честные нагрузки в листинге (45 кг ≠ 60 кг ONKRON!) · Amazon 1P "
           "на трети листингов ONKRON · упаковка под FBA + тест устойчивости."),
 dict(wave="Стратегический", name="Hängeregisterschrank ZY-3 — картотека A4, B2B", price="219.00 €",
      comp=[("Jan Nowak V005 — 204–290 €, 3.3–3.5★ (уязвим!) · Sightlife 130–330 €, 4.0–4.3★ · семья Jan Nowak ",
             "B01FPD5ZUQ", " 185.99–195.99 €, 817 отз., Amazon 1P на большинстве листингов")],
      econ=("€40.91", "18.7%", "63%", "$30.40", "153.05 €"),
      split=("Amazon+реклама 52% (113.15 €)", "Закупка 30% (64.94 €)", "Прибыль 19% (40.91 €)"),
      ali=[("✅ PI Luoyang ZhenYou № 20260126cathy в руках ($45 EXW, сталь 0.6/0.7 мм)", None),
           ("Fenglee 4-drawer", "https://www.alibaba.com/product-detail/Modern-4-Drawer-Vertical-Metal-Filing_526009042.html"),
           ("Витрина Luoyang", "https://www.alibaba.com/showroom/vertical-4-drawer-steel-filing-cabinets.html")],
      risk="Изменить PI: ZY-3 20→40 шт · исключить ZY-4 · локеры 130→60–80 шт · торг $45→$38–40 · Amazon Business + "
           "EN 14073 + антиопрокидывание. Пошлина 0% (HS 9403.10)."),
 dict(wave="Волна 2", name="Kirschentkerner — вишнечистка настольная (звезда портфеля)", price="45.99 €",
      comp=[("Лидер: Thiru ", "B0CSZ1KZZB", " — 49.99 € (поднял в сезон), ~2 000 шт/мес прямо сейчас (июль = пик), "
             "523 отзыва, 4.4★, 1 оффер, Made in Germany")],
      econ=("€14.87", "32.3%", "243%", "$8.29", "18.97 €"),
      split=("Amazon+реклама 54% (24.99 €)", "Закупка 13% (6.13 €)", "Прибыль 32% (14.87 €)"),
      ali=[("6-луночная со splash guard", "https://www.alibaba.com/product-detail/2024-6-Hole-Cherry-Pitter-6_1601253386227.html"),
           ("Витрина cherry pitter", "https://www.alibaba.com/showroom/cherry-pitter.html"),
           ("6-in-1 с контейнером", "https://www.alibaba.com/showroom/cherry-pitters.html")],
      risk="Сезон июнь–август → основная партия к марту 2027 (заказ XI.26–I.27); опция: авиа-мини-партия 100–150 шт "
           "на хвост сезона 2026. LFGB. Бандл: контейнер + 25 рецептов."),
 dict(wave="Волна 2", name="Fliegengitter Magnet 150×130, 4-pack", price="39.99 €",
      comp=[("Лидер: EASYmaxx ", "B0CX5K1K2D", " — 47.99 €, ~2 000/мес (пик), 713 отз., 4.1★ — уязвим, 3–4 оффера, "
             "⚠ Amazon 1P на листинге (42.00 €)")],
      econ=("€7.93", "19.8%", "98%", "$4.45", "25.58 €"),
      split=("Amazon+реклама 60% (23.96 €)", "Закупка 20% (8.10 €)", "Прибыль 20% (7.93 €)"),
      ali=[("DIY magnetic insect screen (патентованная система)", "https://www.alibaba.com/product-detail/DIY-magnetic-insect-screen-window-with_60060039167.html"),
           ("Витрина DIY magnetic", "https://www.alibaba.com/showroom/diy-magnetic-insect-screen-window.html"),
           ("Magnetic window screen", "https://www.alibaba.com/showroom/magnetic-window-screen.html")],
      risk="Вход только через качество: 16 магнитов (у EASYmaxx 12), клей 3M, UV-стойкая рамка, инструкция DE. "
           "Сезон апрель–сентябрь → заказ к февралю 2027."),
 dict(wave="Волна 2", name="Kühldecke Arc-Chill 150×200 — охлаждающее одеяло", price="42.99 €",
      comp=[("Лидер: Elegear ", "B07QJ132TD", " — 54.99 € в пике (ср. 50.34), ~800/мес, 2 959 отз., 4.3★ (есть что "
             "улучшать), 1 оффер")],
      econ=("€8.35", "19.4%", "81%", "$6.23", "27.82 €"),
      split=("Amazon+реклама 57% (24.35 €)", "Закупка 24% (10.29 €)", "Прибыль 19% (8.35 €)"),
      ali=[("Arc-chill Q-max 0.4 нейлон (прямой аналог ткани)", "https://www.alibaba.com/product-detail/Summer-Q-Max-0-4-Arc_1601140883140.html"),
           ("Q-max>0.45 washable", "https://www.alibaba.com/product-detail/Washable-Q-Max-0-45-Arc_1601027457525.html"),
           ("Japanese Q-max 0.4", "https://www.alibaba.com/product-detail/Japanese-Q-Max-0-4-Cooling_62381033464.html"),
           ("PCM-гель (премиум)", "https://www.alibaba.com/product-detail/PCM-Gel-Cooling-Tech-Fabric-Water_1601360388125.html")],
      risk="Требовать протокол Q-max и OEKO-TEX 100. Сезон май–август → заказ к февралю 2027."),
]

for s in SKUS:
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(12); p.paragraph_format.space_after = Pt(2)
    add_run(p, f"[{s['wave']}]  ", size=9, bold=True, color=ACCENT)
    add_run(p, s["name"], size=12.5, bold=True)
    add_run(p, f"   вход {s['price']}", size=11, bold=True, color=FEE)
    for c in s["comp"]:
        p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
        add_run(p, c[0], size=9.5, color=MUTED)
        if len(c) >= 2 and c[1]:
            hyperlink(p, f"https://www.amazon.de/dp/{c[1]}", c[1], size=9.5, mono=True)
        if len(c) >= 3 and c[2]:
            add_run(p, c[2], size=9.5, color=MUTED)
    # разбивка цены
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(2)
    add_run(p, "Куда уходит цена:  ", size=9, bold=True, color=MUTED)
    add_run(p, "■ " + s["split"][0], size=9, color=FEE)
    add_run(p, "   ■ " + s["split"][1], size=9, color=ACCENT)
    add_run(p, "   ■ " + s["split"][2], size=9, bold=True, color=GOOD)
    # экономика
    t = table(["Прибыль/шт", "Маржа", "ROI", "Закупка ≤ (25%)", "Безубыток"], [list(s["econ"])],
              widths=[3.2, 3.2, 3.2, 3.6, 3.2], fontsize=9.5, num_cols={0,1,2,3,4})
    for cell in t.rows[1].cells: shade(cell, CARD_HEX)
    # alibaba
    p = doc.add_paragraph(); p.paragraph_format.space_before = Pt(3); p.paragraph_format.space_after = Pt(2)
    add_run(p, "Alibaba: ", size=9.5, bold=True, color=MUTED)
    first = True
    for label, url in s["ali"]:
        if not first: add_run(p, "  ·  ", size=9.5, color=MUTED)
        first = False
        if url: hyperlink(p, url, label, size=9.5)
        else: add_run(p, label, size=9.5, bold=True)
    para("Риски/примечания: " + s["risk"], size=9, color=MUTED, space_after=4)

# ===== 05 ОТКЛОНЕНО =====
heading("05", "Что отклонено — и почему")
table(["Товар / ниша", "Вердикт", "Причина (данные)"], [
    ["Кронштейны мониторов (6 SKU DS/DH)", "НЕ ЗАКУПАТЬ", "Все 6 убыточны на .de: −1.3%…−23.6%; бренды с 2–7.7 тыс. отзывов прижали цены к 26–60 €"],
    ["Mülltrennsystem 2×15 л", "Отклонен моделью", "9.46 кг → фрахт €10.9 + FBA €7.94: маржа −1.4% даже по цене SONGMICS 57.11 €"],
    ["Садовый ящик 270 л", "SKIP", "Sperrgut: Landed = 67% цены, маржа −27%"],
    ["ТВ-настенный кронштейн", "HARD", "Барьер 25–79 тыс. отзывов (PERLESMITH)"],
    ["Вакууматор", "HARD", "COGS 42%, маржа 11%; продажи лидера −45% за 90 дней"],
    ["Rollcontainer ZY-4 (из PI)", "Исключить", "SONGMICS/VASAGLE: 1.4–2 тыс. отзывов, маржа ≈ 0…−3 €/шт"],
    ["Ширпотреб < 15 €", "Нет", "Медианная маржа −4%…+9% — комиссии съедают все"],
    ["Одеяло 4 сезона (Siebenschläfer)", "Нет", "Amazon 1P + Made in EU + ров 28.5 тыс. отзывов"],
    ["Мини-холодильник 4–6 л", "РЕЗЕРВ", "Маржа 4.1% @ 44.99 + WEEE/CE; вернуться при ставке 7% Elektro"],
    ["Швабра (JOYMOOP-стиль)", "WATCH", "Ров 53 тыс. отзывов; цена −24% за 90 дней"],
    ["Сковорода (ZWIEGER-стиль)", "WATCH", "Ценовая война: 54.99 → 37.95 за 90 дней"],
    ["Стеклянные банки 12er", "WATCH", "3.7 кг + бой + цена упала до 39.99; маржа ~16%"],
    ["Чугунный горшок (Topbooc)", "WATCH", "BSR обвал 33 → 54 206 (сток-аут), волатильность 0.81"],
    ["US-хиты без DE-листинга", "Отдельный трек", "Спрос DE не подтвержден + почти все с батареями (WEEE/BattG)"],
], widths=[5.6, 2.8, 8.8], fontsize=9)

# ===== 06 ЖИВАЯ ПРОВЕРКА =====
heading("06", "Живая проверка 08.07.2026 — что изменилось с июня")
for s in ["ONKRON уронил цены на 20–45% (аналог CT7501: 232 → 127.99 €) → вход 149.99 вместо 184.99, прибыль €36/шт вместо €64. Проект остается сильным.",
          "Amazon 1P зашел на листинги EASYmaxx (сетки), SONGMICS (мусорные системы), Jan Nowak (шкафы) — учтено в стратегиях входа.",
          "Jura-фильтр GLACIER FRESH подешевел 59.99 → 39.99, продажи ×2 — рынок расходников растет; наша модель уже на 42.99.",
          "Kirschentkerner в сезонном пике: 2 000 шт/мес, цена поднята до 49.99 — спрос подтвержден; тайминг под сезон 2027.",
          "Мусорная система и сумка 20/30L не проходят полную модель — отклонение и переход на 40L-формат соответственно.",
          "Topbooc (чугун) нестабилен (BSR 33 → 54 206) — исключен из ядра, несмотря на Score 74 в июне."]:
    para("•  " + s, size=10, space_after=3)

# ===== 07 БЮДЖЕТ =====
heading("07", "Бюджет и график запуска")
table(["SKU", "Партия", "FOB $", "Сумма $"], [
    ["Jura-фильтр 6er", "500", "10.00", "5 000"],
    ["DeLonghi-фильтр 6er", "500", "4.00", "2 000"],
    ["Kühltasche 40L", "500", "4.50", "2 250"],
    ["Brotbeutel 2er", "500", "2.20", "1 100"],
    ["TV-стенд CT7501", "200", "29.70", "5 940"],
    ["TV-стенд CT9501 (опц.)", "60", "43.60", "2 616"],
    ["ZY-3 картотека (торг)", "40", "40–45", "1 600–1 800"],
    ["Kirschentkerner (В2)", "500", "5.00", "2 500"],
    ["Fliegengitter 4er (В2)", "500", "6.50", "3 250"],
    ["Kühldecke (В2)", "300", "8.50", "2 550"],
    ["ИТОГО FOB", "", "", "≈ 29 000"],
], widths=[6.5, 2.5, 2.5, 3.5], fontsize=9.5, num_cols={1,2,3})
para("+ фрахт/пошлины/QC ≈ €7 тыс. + комплаенс ≈ €5–6 тыс. + стартовый PPC ≈ €6–8 тыс. → полный бюджет ≈ €45–48 тыс. "
     "Окупаемость капитала ≈ 4–6 мес; 2–4 оборота в год.", size=9.5, color=MUTED)
para("График:", bold=True, space_after=2)
for b, s in [("Июль 2026", "RFQ по Волне 1 (3–5 фабрик/SKU) · образцы · старт LFGB/OEKO-TEX · GPSR-представитель · LUCID · EUIPO-марка"),
             ("Август 2026", "Заказы Волны 1 после образцов · листинги DE + A+ контент · Amazon Business для ZY-3"),
             ("Октябрь 2026", "Приход Волны 1 в Гамбург → продажи стартуют в пик Q4"),
             ("Ноябрь 2026 – январь 2027", "Заказы Волны 2 (сезонные SKU) с учетом фактов Волны 1"),
             ("Март–апрель 2027", "Приход Волны 2 к старту сезона: сетки, одеяло, вишнечистка")]:
    p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(3)
    add_run(p, "— " + b + ":  ", size=10, bold=True); add_run(p, s, size=10, color=MUTED)

# ===== 08 КОМПЛАЕНС =====
heading("08", "Комплаенс (Германия)")
table(["Требование", "Что делать", "Стоимость", "Касается"], [
    ["GPSR (Reg. 2023/988)", "EU Responsible Person + адрес на упаковке", "€200–400/год", "все SKU"],
    ["VerpackG / LUCID", "Регистрация упаковки + дуальная система", "€100–300/год", "все SKU"],
    ["LFGB (контакт с пищей)", "Лабораторный тест партии", "€1.5–2.5 тыс. × SKU", "фильтры ×2, вишнечистка, Brotbeutel"],
    ["OEKO-TEX Standard 100", "Сертификат ткани", "€0.5–1 тыс.", "Kühldecke (жел. сумка)"],
    ["EN 14073 + антиопрокидывание", "Тест + предупреждающая наклейка", "≈€0.5 тыс.", "ZY-3"],
    ["EUIPO марка + Brand Registry", "Регистрация ТМ (один бренд)", "€850 разово", "все SKU"],
    ["EAN/GTIN (GS1)", "Коды", "≈€150/год", "все SKU"],
    ["WEEE / BattG / CE", "НЕ ТРЕБУЕТСЯ — нет электроники", "€0", "—"],
], widths=[4.6, 6.2, 3.2, 4.0], fontsize=9)

# ===== 09 РИСКИ =====
heading("09", "Риски и митигация")
for i, s in enumerate([
    "Ценовые войны (ZWIEGER −31%, ONKRON −45%) → безубыток каждого SKU на 35–45% ниже входной цены.",
    "Вход Amazon 1P в нишу (EASYmaxx/SONGMICS/Jan Nowak) → диверсификация: 9 SKU × 6 ниш, ни одна ниша >24% прибыли.",
    "Сезонность (4 из 9 SKU) → календарь §7; всесезонные фильтры + ТВ + ZY-3 = ~47% прибыли.",
    "Патенты/бренды (фильтры) → только «kompatibel mit», без логотипов; запрос к Ningbo Koze; юр. проверка.",
    "Качество (рейтинг <4.2 убивает конверсию при чеке >40 €) → образцы с 2–3 фабрик, QC-инспекция (€100–250), усиленная упаковка.",
    "Валюта/фрахт → USD-контракты, курс 0.92 консервативный; FCL-консолидация Волны 1 −30–50% фрахта."], 1):
    para(f"{i}.  {s}", size=10, space_after=3)

# ===== 10 РЕШЕНИЕ =====
heading("10", "Решение к утверждению")
p = doc.add_paragraph(); add_run(p, "✅ Волна 1 — заказ немедленно:", size=11.5, bold=True, color=GOOD)
for s in ["Фильтр Jura RFID 6er — 500 паков (RFQ: Ningbo Koze + 3 фабрики)", "Фильтр DeLonghi 6er — 500 паков",
          "Kühltasche 40L — 500 шт", "Brotbeutel 2er — 500 шт (микро-тест)",
          "TV-стенд CT7501 — 200 шт по котировке BKDEP (+60 шт CT9501 опц.)",
          "ZY-3 — 40 шт (изменить PI: −ZY-4, −50 локеров; торг до $40)"]:
    para("   •  " + s, size=10, space_after=2)
p = doc.add_paragraph(); add_run(p, "📅 Волна 2 — заказ XI.2026–I.2027:", size=11.5, bold=True, color=ACCENT)
for s in ["Kirschentkerner — 500 шт (звезда портфеля: 32% маржа, ROI 243%)",
          "Fliegengitter Magnet 4er — 500 шт", "Kühldecke Arc-Chill — 300 шт"]:
    para("   •  " + s, size=10, space_after=2)
para("Не закупать: кронштейны мониторов, Mülltrennsystem, садовые ящики, ТВ-кронштейны, вакууматоры, ZY-4, "
     "ширпотреб <15 €.  Резерв Q1 2027: мини-холодильники (при ставке 7%), швабра/сковорода (после войны цен), "
     "US-новинки.", size=9.5, color=MUTED)

para("", space_after=2)
para("Источники: Keepa BlackBox DE (500 бестселлеров, 24.06.2026) · Keepa API live (08.07.2026, окно 90 дней) · "
     "DE_PrivateLabel_Top10_2026 · China_Sourcing_Report · отчеты Demity / TV-стенды / мини-холодильники / кронштейны · "
     "PI Luoyang ZhenYou · котировка SUZHOU BKDEP · Helium 10 BlackBox · проиндексированные карточки Alibaba. "
     "Все суммы: EUR с НДС на стороне продажи; FOB в USD; курс 0.92. Маржи — чистые, после рекламы. "
     "FBA-тарифы — фактические сборы листингов-конкурентов. Полная версия: FINAL_REPORT_Amazon_EU_2026-07.md.",
     size=8, color=MUTED)

out = "/home/user/Keepa/deliverables/Amazon_EU_Portfolio_Report_2026-07.docx"
import os
os.makedirs(os.path.dirname(out), exist_ok=True)
doc.save(out)
print("OK:", out)
