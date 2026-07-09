#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the Russian DOCX: conclusion + investment analysis for UAE launch."""
import json
from docx import Document
from docx.shared import Pt, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

BASE="/home/user/Keepa"
data=json.load(open(f"{BASE}/analysis_workspace/03_unit_economics/uae_final20.json"))
meta=json.load(open(f"{BASE}/analysis_workspace/04_alibaba/sku_meta.json"))
QTY={"B0GKMVTD6V":600,"B0GV2DHXWS":500,"B0GT8HK7LS":300,"B0GZVM23CF":300,"B0H13ZY2W4":250,
     "B0GQHGFFHC":300,"B0GJ4NHH4L":300,"B0GYF91BXB":1200,"B0GSZHLZ3B":500,"B0GZZ3VM69":400,
     "B0G5DSK3YF":400,"B0GCJQ4Z51":400,"B0GF7LLCL8":300,"B0GDTFFKYC":500,"B0FZRGB6BN":120,
     "B0GXKMXLDC":120,"B0H2B94R5F":150,"B0GN1P7DTT":80,"B0GL357H51":200,"B0G1SX2D8H":200}
USD_AED=3.6725; CIT=0.09

# aggregates
capital=sum(QTY[x["asin"]]*x["s_landed_aed"] for x in data)
mo_eb=sum(x["mo_ebitda_pot"] for x in data)
launch_items=[("Фотоконтент + A+ листинги (20 SKU)",18000),("Образцы + инспекция качества (QC)",14000),
 ("Сертификация/регистрация (ESMA/G-Mark, бренд)",22000),("Стартовая реклама PPC (буфер сверх юнит-экономики)",60000),
 ("Логистика первой партии (буфер/страховка)",15000)]
launch_base=sum(v for _,v in launch_items); launch_res=round(launch_base*0.1); launch=launch_base+launch_res
invest=capital+launch
mo_after_tax=mo_eb*(1-CIT)
payback=invest/mo_after_tax
roi12=mo_after_tax*12/invest

doc=Document()
st=doc.styles["Normal"]; st.font.name="Calibri"; st.font.size=Pt(10.5)
st.element.rPr.rFonts.set(qn('w:eastAsia'),"Calibri")

NAVY=RGBColor(0x1F,0x4E,0x78); GREEN=RGBColor(0x1F,0x6E,0x28); RED=RGBColor(0xC0,0,0)

def H(txt,lvl=1,color=NAVY):
    p=doc.add_heading(level=lvl)
    r=p.add_run(txt); r.font.color.rgb=color
    return p
def P(txt,bold=False,size=10.5,color=None,align=None,after=4):
    p=doc.add_paragraph(); r=p.add_run(txt); r.bold=bold; r.font.size=Pt(size)
    if color: r.font.color.rgb=color
    if align: p.alignment=align
    p.paragraph_format.space_after=Pt(after)
    return p
def bullet(txt,bold_prefix=None):
    p=doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        r=p.add_run(bold_prefix); r.bold=True
    p.add_run(txt); p.paragraph_format.space_after=Pt(2)
    return p

from docx.opc.constants import RELATIONSHIP_TYPE as RT
def add_hyperlink(paragraph, url, text, color="0563C1"):
    part=paragraph.part; r_id=part.relate_to(url, RT.HYPERLINK, is_external=True)
    hyperlink=OxmlElement('w:hyperlink'); hyperlink.set(qn('r:id'), r_id)
    new_run=OxmlElement('w:r'); rPr=OxmlElement('w:rPr')
    c=OxmlElement('w:color'); c.set(qn('w:val'),color); rPr.append(c)
    u=OxmlElement('w:u'); u.set(qn('w:val'),'single'); rPr.append(u)
    sz=OxmlElement('w:sz'); sz.set(qn('w:val'),'18'); rPr.append(sz)
    new_run.append(rPr); t=OxmlElement('w:t'); t.text=text; new_run.append(t)
    hyperlink.append(new_run); paragraph._p.append(hyperlink)
    return hyperlink

def shade(cell,hexc):
    tcPr=cell._tc.get_or_add_tcPr(); sh=OxmlElement('w:shd')
    sh.set(qn('w:val'),'clear'); sh.set(qn('w:fill'),hexc); tcPr.append(sh)
def setw(cell,txt,bold=False,size=8.5,color=None,align=None):
    cell.text=""; p=cell.paragraphs[0]; r=p.add_run(str(txt)); r.bold=bold; r.font.size=Pt(size)
    if color: r.font.color.rgb=color
    if align: p.alignment=align
    p.paragraph_format.space_after=Pt(0); p.paragraph_format.space_before=Pt(0)
    return p

# ---------------- TITLE ----------------
t=doc.add_paragraph(); t.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=t.add_run("Amazon ОАЭ (amazon.ae): выбор 20 товаров-новинок\nHome & Kitchen + мебель / офисные кресла")
r.bold=True; r.font.size=Pt(18); r.font.color.rgb=NAVY
sub=doc.add_paragraph(); sub.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=sub.add_run("Технико-экономическое обоснование и инвестиционный анализ")
r.italic=True; r.font.size=Pt(12.5)
d=doc.add_paragraph(); d.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=d.add_run("Источник спроса: новинки Amazon США · Целевой рынок: Amazon.ae (FBA) · Дата: 09.07.2026")
r.font.size=Pt(10); r.font.color.rgb=RGBColor(0x60,0x60,0x60)
doc.add_paragraph()

# ---------------- 1. EXEC SUMMARY ----------------
H("1. Резюме для руководства",1)
P(f"Рекомендация: запускать портфель из 20 SKU тремя волнами. Стартовые инвестиции ≈ "
  f"{invest:,.0f} AED (≈ ${invest/USD_AED:,.0f}): оборотный капитал под закупку ≈ {capital:,.0f} AED "
  f"и бюджет запуска ≈ {launch:,.0f} AED. Потенциал портфеля на полном разгоне ≈ {mo_eb:,.0f} AED "
  f"EBITDA/мес (≈ ${mo_eb/USD_AED:,.0f}), после налога ОАЭ 9% ≈ {mo_after_tax:,.0f} AED/мес. "
  f"Окупаемость стартовых инвестиций ≈ {payback:.1f} мес, ROI за 12 мес ≈ {roi12*100:.0f}%.".replace(",", " "),
  bold=False)
P("Логика: спрос берём из новинок Amazon США (объективный, глубокий сигнал по Home & Kitchen), "
  "а продаём в ОАЭ, где конкуренция ниже, а розничные цены в AED выше — это и создаёт маржу. "
  "Портфель настроен под климат и спрос ОАЭ (охлаждение, воздух, хранение) и под вашу нишу — "
  "мебель и офисные кресла (6 из 20 SKU).", after=6)

P("Принципы отбора:",bold=True,after=2)
bullet("только частные марки без доминирования Amazon и мегабрендов (мы заходим туда, где лидер — такой же PL);",bold_prefix="Без брендовых войн. ")
bullet("рейтинг лидера ≥ 4.2, но с пространством для улучшения; барьер отзывов преодолим за 3–4 мес;",bold_prefix="Живой спрос. ")
bullet("экономика с полной нагрузкой: НДС 5% + Referral 15% + FBA (ОАЭ) + пошлина 5% + фрахт + PPC + купон + маркетинг + возвраты;",bold_prefix="Честная маржа. ")
bullet("проходной порог рабочего режима: маржа ≥ 15%, ROI ≥ 40%, EBITDA/шт > 0.",bold_prefix="Пороги. ")

# portfolio at a glance
P("Портфель одним взглядом (рабочий режим):",bold=True,after=2)
cols=["#","Товар","Цена ОАЭ, AED","Маржа %","ROI %","EBITDA/шт AED","Потенц. EBITDA/мес AED"]
tb=doc.add_table(rows=1,cols=len(cols)); tb.alignment=WD_TABLE_ALIGNMENT.CENTER
tb.style="Light Grid Accent 1"
for j,c in enumerate(cols):
    setw(tb.rows[0].cells[j],c,bold=True,size=8.5,color=RGBColor(0xFF,0xFF,0xFF),align=WD_ALIGN_PARAGRAPH.CENTER); shade(tb.rows[0].cells[j],"1F4E78")
for i,x in enumerate(data,1):
    cells=tb.add_row().cells
    setw(cells[0],i,size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[1],meta[x["asin"]]["ru"],size=8)
    setw(cells[2],f"{x['s_price_aed']:,.0f}".replace(","," "),size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[3],f"{x['s_margin']:.1f}",size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[4],f"{x['s_roi']:.0f}",size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[5],f"{x['s_ebitda_unit']:,.0f}".replace(","," "),size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[6],f"{x['mo_ebitda_pot']:,.0f}".replace(","," "),size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    if x["s_furniture"]: shade(cells[1],"FCE4D6")
tot=tb.add_row().cells
setw(tot[1],"ИТОГО портфель",bold=True,size=8.5)
setw(tot[6],f"{mo_eb:,.0f}".replace(","," "),bold=True,size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
for c in tot: shade(c,"D9E1F2")
P("Оранжевым выделена ваша ниша — мебель и офисные кресла. Полные расчёты и редактируемые формулы — "
  "в приложенном файле Excel (лист «Модель_ТЭО»).",size=9,color=RGBColor(0x60,0x60,0x60),after=6)

# ---------------- 2. STRATEGY ----------------
H("2. Стратегия и почему именно ОАЭ",1)
P("Мы используем США как «радар спроса», а ОАЭ — как рынок продажи. В новинках Amazon США виден "
  "самый чистый сигнал: какие свежие товары Home & Kitchen реально набирают продажи. Эти же категории "
  "в ОАЭ менее конкурентны, а розница в дирхамах выше, поэтому маржинальность на .ae, как правило, лучше.",after=4)
P("Проверка по живым данным Amazon.ae подтверждает спрос по нашим категориям:",bold=True,after=2)
bullet("офисные/компьютерные кресла — Efomao Big&Tall продаётся по 758–969 AED, ~160 шт/мес каждая вариация (это прямой аналог нашего SKU Big&Tall);")
bullet("хранение и организация — SKY-TOUCH, Lifewit, VENO (пакеты/сумки для хранения и переезда) стабильно в топе;")
bullet("ванная/полки — STEUGO Shower Caddy (44.98 AED, 248 шт/мес) — прямой аналог нашей телескопической стойки;")
bullet("климат — из-за жары и пыли ОАЭ вентиляторы, охладители, очистители и осушители воздуха имеют структурно высокий спрос круглый год.")
P("Поэтому портфель составлен так: 14 быстрых оборотных SKU Home & Kitchen (охлаждение, воздух, уборка, "
  "хранение, кухня, декор) обеспечивают денежный поток и высокий ROI, а 6 SKU вашей ниши (мебель и офисные "
  "кресла) дают высокий чек и абсолютную прибыль на единицу и развивают бренд.",after=6)

# ---------------- 3. TEO / COST MODEL ----------------
H("3. Технико-экономическое обоснование: структура затрат ОАЭ",1)
P("Каждый SKU просчитан с полной нагрузкой затрат. Ниже — что входит в модель (все ставки редактируются "
  "в Excel-файле, лист «Параметры»):",after=3)
bullet("курс USD→AED = 3.6725 (фиксированная привязка);",bold_prefix="Валюта. ")
bullet("НДС ОАЭ 5% — включён в розничную цену, выделяется из выручки;",bold_prefix="НДС. ")
bullet("Referral (комиссия Amazon) Home & Kitchen — 15% (8% при цене ≤ 50 AED);",bold_prefix="Referral. ")
bullet("сбор по шкале Amazon.ae: стандарт 7.2–21.5 AED, крупногабарит/тяжёлые (кресла) 60–108 AED — критичен для мебели;",bold_prefix="FBA. ")
bullet("морем Китай→Джебель-Али, расчёт по объёму (≈ $165/м³) с проверкой по весу; для кресел выгоднее FCL;",bold_prefix="Фрахт. ")
bullet("FOB-цена с завода (ориентир, подтверждается RFQ у 3–5 поставщиков Alibaba);",bold_prefix="FOB / COGS. ")
bullet("таможенная пошлина ОАЭ 5% от CIF (FOB + фрахт);",bold_prefix="Пошлина. ")
bullet("по ТЗ на запуске закладываем PPC 35% и купон 10% (агрессивный разгон); в рабочем режиме PPC ≈ 12%, купон ≈ 3%;",bold_prefix="Реклама/купон. ")
bullet("внешний/бренд-маркетинг ≈ 3% и резерв на возвраты ≈ 2%.",bold_prefix="Маркетинг и возвраты. ")
P("Формула прибыли на единицу: EBITDA/шт = Чистая выручка (без НДС) − (Referral + FBA + PPC + Купон + "
  "Маркетинг + Возвраты) − Landed COGS (FOB + фрахт + пошлина + приёмка). Маржа = EBITDA/шт ÷ Чистая выручка; "
  "ROI = EBITDA/шт ÷ Landed COGS.",bold=True,after=6)

# ---------------- 4. FULL TABLE ----------------
H("4. Портфель 20 SKU: карточки и ссылки",1)
P("ASIN кликабельны (карточка на amazon.ae), в последнем столбце — ссылка на аналог/поставщика Alibaba.",
  size=9,color=RGBColor(0x60,0x60,0x60),after=3)
cols2=["#","Товар","ASIN","Категория","Цена AED","Марж%","ROI%","Alibaba"]
w2=[0.4,3.4,1.3,2.0,0.9,0.7,0.7,1.0]
tb2=doc.add_table(rows=1,cols=len(cols2)); tb2.style="Light Grid Accent 1"
for j,c in enumerate(cols2):
    setw(tb2.rows[0].cells[j],c,bold=True,size=8,color=RGBColor(0xFF,0xFF,0xFF),align=WD_ALIGN_PARAGRAPH.CENTER); shade(tb2.rows[0].cells[j],"1F4E78")
for i,x in enumerate(data,1):
    a=x["asin"]; cells=tb2.add_row().cells
    setw(cells[0],i,size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[1],meta[a]["ru"],size=7.5)
    cells[2].text=""; add_hyperlink(cells[2].paragraphs[0],f"https://www.amazon.ae/dp/{a}",a)
    setw(cells[3],meta[a]["cat_ru"],size=7.5)
    setw(cells[4],f"{x['s_price_aed']:,.0f}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[5],f"{x['s_margin']:.0f}",size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cells[6],f"{x['s_roi']:.0f}",size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    cells[7].text=""; add_hyperlink(cells[7].paragraphs[0],meta[a]["alibaba"][0],"ссылка")
    if x["s_furniture"]: shade(cells[1],"FCE4D6")

# ---------------- 5. CATEGORY COMMENTARY ----------------
H("5. Комментарий по категориям",1)
def cat_block(title, txt):
    p=doc.add_paragraph(); r=p.add_run(title); r.bold=True; r.font.color.rgb=NAVY; r.font.size=Pt(10.5)
    P(txt,after=5)
cat_block("Охлаждение и вентиляторы (флагман ОАЭ)",
  "Ручной турбо-вентилятор, носимый вентилятор на шею и портативный кондиционер — лучшая связка ROI и "
  "объёма (ROI 100–140%). Лёгкие, быстрый оборот капитала, круглогодичный спрос из-за климата. Дифференциация: "
  "тихий бесщёточный мотор, USB-C, ёмкий аккумулятор.")
cat_block("Климат и воздух",
  "Очиститель воздуха (HEPA) и осушитель — высокий чек (244–369 AED), маржа 23–25%. Пыль и влажность "
  "побережья формируют устойчивый спрос. Требуется сертификация и сменные фильтры (встроенный LTV).")
cat_block("Уборка и бытовая техника",
  "Ручной пароочиститель и отпариватель для одежды — маржа 27–28%, ROI ~90%. Универсальный спрос, "
  "хорошо продаются в связке с текстилем/мебелью.")
cat_block("Хранение и организация (проверено в ОАЭ)",
  "Ремни для переноски мебели (30 000 продаж/мес у лидера!), вакуумные пакеты, телескопическая стойка "
  "для ванной, корзина для белья. Прямые аналоги топ-продавцов .ae. Высокий ROI, лёгкий вес.")
cat_block("Кухня и декор",
  "Набор ножей (8 предметов) и искусственная зелень — недорогие оборотные позиции для добивки контейнера; "
  "для ножей обязателен LFGB-тест.")
cat_block("Мебель и офисные кресла (ваша ниша)",
  "Эргономичное кресло-сетка, кресло руководителя (эко-кожа), усиленное Big&Tall (прямой аналог хита ОАЭ "
  "Efomao), ковёр 8×10 и коврик под кресло. Это высокочековые SKU (504–1034 AED) с максимальной абсолютной "
  "прибылью на единицу (100–143 AED), но с более высоким капиталом на единицу и чувствительностью к фрахту/FBA. "
  "Рекомендация: возить креслами FCL, держать более высокую цену (спрос .ae это позволяет), рассмотреть "
  "локальную доставку/3PL для самых тяжёлых моделей.")

# ---------------- 6. SCENARIOS ----------------
H("6. Сценарии: запуск (по ТЗ) против рабочего режима",1)
P("По ТЗ отдельно просчитан агрессивный запуск: PPC 35% + купон 10%. При такой нагрузке большинство SKU "
  "в первые 2–3 месяца работают около нуля или в минусе — это нормальные инвестиции в разгон (захват "
  "позиций, скорость продаж, отзывы). После разгона реклама снижается до ~12%, купон до ~3%, и портфель "
  "выходит на целевую маржу 15–32% и ROI 40–140%.",after=3)
P("Ключевой вывод: эти товары «проходят для запуска» именно по устойчивой экономике; фаза 35% PPC — "
  "это управляемый бюджет привлечения, а не постоянное состояние. Оба сценария считаются в Excel "
  "(столбцы «…(режим)» и «…(запуск)»).",bold=True,after=6)

# ---------------- 7. INVESTMENT ----------------
H("7. Инвестиционный анализ",1)
rows=[("Оборотный капитал под закупку (первые партии)",f"{capital:,.0f} AED"),
 ("Бюджет запуска (контент, образцы/QC, сертификация, стартовый PPC, логистика, резерв)",f"{launch:,.0f} AED"),
 ("ИТОГО стартовые инвестиции",f"{invest:,.0f} AED  (≈ ${invest/USD_AED:,.0f})"),
 ("Потенциал EBITDA/мес (полный разгон)",f"{mo_eb:,.0f} AED"),
 ("Прибыль/мес после налога ОАЭ 9%",f"{mo_after_tax:,.0f} AED"),
 ("Окупаемость стартовых инвестиций",f"{payback:.1f} мес"),
 ("ROI за 12 месяцев",f"{roi12*100:.0f}%")]
ti=doc.add_table(rows=0,cols=2); ti.style="Light List Accent 1"
for k,v in rows:
    c=ti.add_row().cells
    setw(c[0],k,bold=("ИТОГО" in k or "Окупаемость" in k or "ROI" in k),size=9.5)
    setw(c[1],v.replace(",", " "),bold=True,size=9.5,align=WD_ALIGN_PARAGRAPH.RIGHT,
         color=(GREEN if ("Окупаемость" in k or "ROI" in k) else (RED if "ИТОГО" in k else None)))
P("",after=2)
P("Разбивка бюджета запуска:",bold=True,after=2)
for k,v in launch_items: bullet(f"{v:,.0f} AED — {k}".replace(","," "))
bullet(f"{launch_res:,.0f} AED — резерв 10%".replace(","," "))
P("Развёртывание тремя волнами (снижает риск и растягивает капитал):",bold=True,after=2)
bullet("Волна 1 (немедленно): охлаждение/вентиляторы + ремни для переноски + вакуумные пакеты — самый быстрый ROI и денежный поток;",bold_prefix="")
bullet("Волна 2 (через 4–6 нед.): воздух/климат, уборка, ванная, кухня, декор;",bold_prefix="")
bullet("Волна 3 (через 8–10 нед.): мебель и офисные кресла (FCL), ковёр — высокий чек, длиннее цикл.",bold_prefix="")
P("Все объёмы заказа, капитал и окупаемость по каждому SKU редактируются в Excel (лист «Инвестиции»).",
  size=9,color=RGBColor(0x60,0x60,0x60),after=6)

# ---------------- 8. RISKS ----------------
H("8. Риски и меры",1)
risks=[("Тяжёлые кресла — фрахт и FBA «съедают» маржу","возить FCL, держать премиальную цену (спрос .ae подтверждает), для самых тяжёлых — 3PL/локальная доставка вместо FBA;"),
 ("Сертификация ОАЭ (ESMA/G-Mark) для электрики","заложено в бюджет; получать до ввоза, особенно по климатической технике;"),
 ("Реклама на запуске (35% PPC)","управляемый бюджет разгона; строго снижать по мере роста органики; следить за ACOS/TACOS;"),
 ("FOB — ориентировочные","подтвердить RFQ у 3–5 поставщиков Alibaba до заказа; брать образцы + инспекция QC;"),
 ("Сезонность части SKU (охлаждение)","в ОАЭ жара круглый год, но пик — лето; балансируется всесезонными SKU (хранение, мебель, воздух);"),
 ("Контакт с пищей (ножи) / качество","LFGB-тест по ножам; по креслам — газлифт класса 4, BIFMA, усиленная база.")]
for k,v in risks: bullet(v,bold_prefix=f"{k}: ")

# ---------------- 9. CONCLUSION ----------------
H("9. Выводы",1)
P(f"Запуск целесообразен. 20 отобранных новинок Amazon США проходят по марже, чистой прибыли, ROI и EBITDA "
  f"для продажи на Amazon.ae в рабочем режиме. Портфель сбалансирован под ОАЭ: быстрые оборотные товары "
  f"(охлаждение, воздух, хранение) генерируют денежный поток и высокий ROI, а ваша профильная ниша — мебель "
  f"и офисные кресла — даёт высокий чек и абсолютную прибыль и строит бренд.",bold=True,after=4)
P(f"Экономика (рабочий режим): маржа 15–32%, ROI 40–140% по оборотным SKU; по мебели/креслам маржа 15–25% при "
  f"высоком чеке. Стартовые инвестиции ≈ {invest:,.0f} AED (≈ ${invest/USD_AED:,.0f}) окупаются за ≈ {payback:.1f} мес; "
  f"потенциал ≈ {mo_eb:,.0f} AED EBITDA/мес; ROI за 12 мес ≈ {roi12*100:.0f}%.".replace(","," "),after=4)
P("Следующие шаги: (1) RFQ по 20 позициям у 3–5 поставщиков Alibaba и подтверждение FOB; (2) образцы + QC; "
  "(3) сертификация электрики; (4) запуск Волны 1. Все цифры пересчитываются в приложенном Excel при вводе "
  "ваших фактических данных (FOB, цена ОАЭ, объёмы, ставки рекламы).",after=6)

P("Приложения: (1) Excel-модель ТЭО с живыми формулами (UAE_HomeKitchen_TEO_Model_2026-07.xlsx); "
  "(2) ссылки Alibaba по каждому SKU (в таблице и Excel).",size=9,
  color=RGBColor(0x60,0x60,0x60))
disc=doc.add_paragraph(); r=disc.add_run(
  "Дисклеймер: данные Keepa (живой запрос, США, 09.07.2026). Цены ОАЭ, FOB, фрахт и ставки FBA — "
  "ориентировочные оценки для планирования; подтверждаются RFQ и калькулятором FBA в Seller Central .ae. "
  "Ссылки Alibaba — реальные проиндексированные карточки/витрины; MOQ и цены уточняются у поставщиков.")
r.font.size=Pt(8); r.font.color.rgb=RGBColor(0x80,0x80,0x80)

out=f"{BASE}/deliverables/UAE_HomeKitchen_Report_2026-07.docx"
doc.save(out)
print("saved",out)
print(f"capital={capital:,.0f} launch={launch:,.0f} invest={invest:,.0f} moEB={mo_eb:,.0f} payback={payback:.1f} roi12={roi12*100:.0f}%")
