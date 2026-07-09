#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DOCX (RU): conclusion + investment analysis — artificial plants for UAE."""
import json
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.opc.constants import RELATIONSHIP_TYPE as RT

BASE="/home/user/Keepa"
data=json.load(open(f"{BASE}/analysis_workspace/03_unit_economics/uae_plants_final20.json"))
meta=json.load(open(f"{BASE}/analysis_workspace/04_alibaba/plants_meta.json"))
def get_qty(x): return max(60,round(x.get("uae_sales_mo",100)*3))
USD_AED=3.6725; CIT=0.09
capital=sum(get_qty(x)*x["s_landed_aed"] for x in data)
mo=sum(x["mo_ebitda_pot"] for x in data)
launch_items=[("Фотоконтент + A+ листинги (20 SKU)",16000),("Образцы + инспекция качества (QC)",10000),
 ("Сертификация/регистрация (огнестойкость HoReCa, бренд)",12000),("Стартовая реклама PPC (буфер)",20000),
 ("Логистика первой партии (буфер/страховка)",8000)]
launch=round(sum(v for _,v in launch_items)*1.1)
invest=capital+launch; after=mo*(1-CIT); payback=invest/after; roi12=after*12/invest

doc=Document(); st=doc.styles["Normal"]; st.font.name="Calibri"; st.font.size=Pt(10.5)
st.element.rPr.rFonts.set(qn('w:eastAsia'),"Calibri")
NAVY=RGBColor(0x1F,0x4E,0x78); GREEN=RGBColor(0x1F,0x6E,0x28); RED=RGBColor(0xC0,0,0)
def H(txt,lvl=1,color=NAVY):
    p=doc.add_heading(level=lvl); r=p.add_run(txt); r.font.color.rgb=color; return p
def P(txt,bold=False,size=10.5,color=None,after=4):
    p=doc.add_paragraph(); r=p.add_run(txt); r.bold=bold; r.font.size=Pt(size)
    if color: r.font.color.rgb=color
    p.paragraph_format.space_after=Pt(after); return p
def bullet(txt,bold_prefix=None):
    p=doc.add_paragraph(style="List Bullet")
    if bold_prefix: r=p.add_run(bold_prefix); r.bold=True
    p.add_run(txt); p.paragraph_format.space_after=Pt(2); return p
def add_hyperlink(paragraph,url,text,color="0563C1"):
    part=paragraph.part; r_id=part.relate_to(url,RT.HYPERLINK,is_external=True)
    h=OxmlElement('w:hyperlink'); h.set(qn('r:id'),r_id)
    nr=OxmlElement('w:r'); rPr=OxmlElement('w:rPr')
    c=OxmlElement('w:color'); c.set(qn('w:val'),color); rPr.append(c)
    u=OxmlElement('w:u'); u.set(qn('w:val'),'single'); rPr.append(u)
    sz=OxmlElement('w:sz'); sz.set(qn('w:val'),'18'); rPr.append(sz)
    nr.append(rPr); t=OxmlElement('w:t'); t.text=text; nr.append(t); h.append(nr)
    paragraph._p.append(h); return h
def shade(cell,hexc):
    tcPr=cell._tc.get_or_add_tcPr(); sh=OxmlElement('w:shd')
    sh.set(qn('w:val'),'clear'); sh.set(qn('w:fill'),hexc); tcPr.append(sh)
def setw(cell,txt,bold=False,size=8.5,color=None,align=None):
    cell.text=""; p=cell.paragraphs[0]; r=p.add_run(str(txt)); r.bold=bold; r.font.size=Pt(size)
    if color: r.font.color.rgb=color
    if align: p.alignment=align
    p.paragraph_format.space_after=Pt(0); p.paragraph_format.space_before=Pt(0); return p

# TITLE
t=doc.add_paragraph(); t.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=t.add_run("Amazon ОАЭ (amazon.ae): выбор 20 товаров-новинок\nИскусственные растения (Artificial Plants)")
r.bold=True; r.font.size=Pt(18); r.font.color.rgb=NAVY
s=doc.add_paragraph(); s.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=s.add_run("Технико-экономическое обоснование и инвестиционный анализ"); r.italic=True; r.font.size=Pt(12.5)
dd=doc.add_paragraph(); dd.alignment=WD_ALIGN_PARAGRAPH.CENTER
r=dd.add_run("Проверка: Amazon США (спрос) + Amazon.ae (рынок) · FBA · Дата: 09.07.2026")
r.font.size=Pt(10); r.font.color.rgb=RGBColor(0x60,0x60,0x60)
doc.add_paragraph()

# 1. SUMMARY
H("1. Резюме для руководства",1)
P(f"Рекомендация: запускать нишевый портфель из 20 SKU искусственных растений двумя волнами. "
  f"Стартовые инвестиции ≈ {invest:,.0f} AED (≈ ${invest/USD_AED:,.0f}): закупка ≈ {capital:,.0f} AED + "
  f"запуск ≈ {launch:,.0f} AED. Потенциал ≈ {mo:,.0f} AED EBITDA/мес (после налога 9% ≈ {after:,.0f}), "
  f"окупаемость ≈ {payback:.1f} мес, ROI за 12 мес ≈ {roi12*100:.0f}%.".replace(","," "))
P("Важно понимать масштаб: искусственные растения — это высокомаржинальная, но нишевая категория "
  "с меньшими объёмами, чем широкий Home & Kitchen. Наценка отличная (маржа 17–31%, ROI 48–110%), но "
  "объёмы новых листингов в США умеренные, поэтому абсолютная прибыль скромнее. Зато вход дешёвый, "
  "капитал оборачивается быстро, а масштабирование идёт через B2B — отели, рестораны, торговые центры, "
  "ландшафт, застройщиков (в ОАЭ это огромный сегмент).",after=6)
P("Принципы отбора:",bold=True,after=2)
bullet("частные марки без Amazon 1P и мегабрендов (лидеры .ae — LYERSE, FEELEAD — такие же PL);",bold_prefix="Без брендовых войн. ")
bullet("UV-стойкость обязательна для уличных позиций — климат ОАЭ (солнце) быстро обесцвечивает дешёвый пластик;",bold_prefix="Под климат ОАЭ. ")
bullet("полная нагрузка затрат: НДС 5% + Referral 15% + FBA + пошлина 5% + фрахт + PPC + купон + маркетинг + возвраты;",bold_prefix="Честная маржа. ")
bullet("порог рабочего режима: маржа ≥ 15%, ROI ≥ 40%, EBITDA/шт > 0.",bold_prefix="Пороги. ")

P("Портфель одним взглядом (рабочий режим):",bold=True,after=2)
cols=["#","Товар","Цена AED","Маржа %","ROI %","EBITDA/шт AED","EBITDA/мес AED"]
tb=doc.add_table(rows=1,cols=len(cols)); tb.alignment=WD_TABLE_ALIGNMENT.CENTER; tb.style="Light Grid Accent 1"
for j,c in enumerate(cols):
    setw(tb.rows[0].cells[j],c,bold=True,size=8.5,color=RGBColor(0xFF,0xFF,0xFF),align=WD_ALIGN_PARAGRAPH.CENTER); shade(tb.rows[0].cells[j],"1F4E78")
for i,x in enumerate(data,1):
    cc=tb.add_row().cells
    setw(cc[0],i,size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER); setw(cc[1],meta[x["asin"]]["ru"],size=8)
    setw(cc[2],f"{x['s_price_aed']:,.0f}".replace(","," "),size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[3],f"{x['s_margin']:.1f}",size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[4],f"{x['s_roi']:.0f}",size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[5],f"{x['s_ebitda_unit']:,.0f}".replace(","," "),size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[6],f"{x['mo_ebitda_pot']:,.0f}".replace(","," "),size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
    if x["s_furniture"]: shade(cc[1],"E2EFDA")  # trees highlighted
tot=tb.add_row().cells
setw(tot[1],"ИТОГО портфель",bold=True,size=8.5)
setw(tot[6],f"{mo:,.0f}".replace(","," "),bold=True,size=8.5,align=WD_ALIGN_PARAGRAPH.CENTER)
for c in tot: shade(c,"D9E1F2")
P("Зелёным выделены искусственные деревья (высокий чек, спрос HoReCa/виллы). Полные расчёты и живые "
  "формулы — в Excel-файле.",size=9,color=RGBColor(0x60,0x60,0x60),after=6)

# 2. STRATEGY
H("2. Стратегия: США как радар, ОАЭ как рынок",1)
P("Мы берём спрос из новинок Amazon США (что реально набирает продажи в подкатегории Artificial Plants "
  "& Flowers) и продаём в ОАЭ, где искусственные растения — сильная, устойчивая ниша.",after=3)
P("Проверка спроса в ОАЭ (amazon.ae):",bold=True,after=2)
bullet("на amazon.ae есть отдельные разделы «Artificial Trees» и «Artificial Olive Tree» с ценовыми полками (искусственные оливы 150–350 AED);")
bullet("активные PL-бренды-лидеры LYERSE, FEELEAD — значит ниша открыта для нового частного бренда;")
bullet("огромный B2B-спрос: виллы, отели, рестораны, торговые центры, ландшафт — деревья 3–4 м под заказ;")
bullet("климат: круглогодичное солнце → высокий спрос на UV-стойкие уличные цветы/зелень (балконы, террасы, сады).")
P("Отсюда структура портфеля: якорь по прибыли — уличные UV-цветы и наборы эвкалипта (быстрый оборот), "
  "плюс искусственные деревья (оливы/гортензии) как высокочековые SKU с выходом на B2B, плюс комнатные "
  "акценты (сансевиерия, монстера) и топиарий.",after=6)

# 3. TEO
H("3. Технико-экономическое обоснование: структура затрат ОАЭ",1)
P("Все ставки редактируются в Excel (лист «Параметры»):",after=3)
bullet("курс USD→AED = 3.6725 (фикс.); НДС ОАЭ 5% в цене;",bold_prefix="Валюта/НДС. ")
bullet("Referral (Home décor) 15%; пошлина ОАЭ 5% от CIF;",bold_prefix="Amazon/пошлина. ")
bullet("сбор Amazon.ae: лёгкие растения 7–21 AED; крупные деревья — крупногабарит 25–60 AED;",bold_prefix="FBA. ")
bullet("морем Китай→Джебель-Али ≈ $165/м³; для деревьев критичен ОБЪЁМ (разборный ствол экономит фрахт);",bold_prefix="Фрахт. ")
bullet("FOB низкий: цветы/зелень $2–8, деревья $14–32 (подтвердить RFQ);",bold_prefix="FOB/COGS. ")
bullet("по ТЗ запуск: PPC 35% + купон 10%; рабочий режим PPC ≈ 12%, купон ≈ 3%; маркетинг 3%, возвраты 2%.",bold_prefix="Реклама/купон. ")
P("EBITDA/шт = Чист. выручка (без НДС) − (Referral + FBA + PPC + Купон + Маркетинг + Возвраты) − Landed COGS. "
  "Маржа = EBITDA/шт ÷ Чист. выручка; ROI = EBITDA/шт ÷ Landed COGS.",bold=True,after=6)

# 4. TABLE
H("4. Портфель 20 SKU: карточки и ссылки",1)
P("ASIN кликабельны (карточка amazon.ae), последний столбец — аналог/поставщик Alibaba.",
  size=9,color=RGBColor(0x60,0x60,0x60),after=3)
c2=["#","Товар","ASIN","Подкатегория","Цена AED","Марж%","ROI%","Alibaba"]
t2=doc.add_table(rows=1,cols=len(c2)); t2.style="Light Grid Accent 1"
for j,c in enumerate(c2):
    setw(t2.rows[0].cells[j],c,bold=True,size=8,color=RGBColor(0xFF,0xFF,0xFF),align=WD_ALIGN_PARAGRAPH.CENTER); shade(t2.rows[0].cells[j],"1F4E78")
for i,x in enumerate(data,1):
    a=x["asin"]; cc=t2.add_row().cells
    setw(cc[0],i,size=8,align=WD_ALIGN_PARAGRAPH.CENTER); setw(cc[1],meta[a]["ru"],size=7.5)
    cc[2].text=""; add_hyperlink(cc[2].paragraphs[0],f"https://www.amazon.ae/dp/{a}",a)
    setw(cc[3],meta[a]["cat_ru"],size=7.5)
    setw(cc[4],f"{x['s_price_aed']:,.0f}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[5],f"{x['s_margin']:.0f}",size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[6],f"{x['s_roi']:.0f}",size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    cc[7].text=""; add_hyperlink(cc[7].paragraphs[0],meta[a]["alibaba"][0],"ссылка")
    if x["s_furniture"]: shade(cc[1],"E2EFDA")

# 5. SUBCATEGORY COMMENTARY
H("5. Комментарий по подкатегориям",1)
def cb(title,txt):
    p=doc.add_paragraph(); r=p.add_run(title); r.bold=True; r.font.color.rgb=NAVY; r.font.size=Pt(10.5)
    P(txt,after=5)
cb("Искусственные деревья (высокий чек, B2B-драйвер)",
  "Оливы 6FT и деревья-гортензии — самые дорогие SKU (244–344 AED) с максимальной прибылью на единицу "
  "(40–82 AED). Прямая конкуренция с LYERSE/FEELEAD (150–350 AED на .ae). Ключ к объёму — выход на HoReCa "
  "и застройщиков. Возить разборными (ствол отдельно) — иначе объёмный фрахт убивает экономику; требовать "
  "огнестойкость (для отелей/ТЦ обязательна).")
cb("Уличные UV-цветы (якорь оборота)",
  "Герань, анютины глазки, петунии, гортензии — самая ходовая группа (наборы 6–36 шт). Маржа 22–29%, "
  "ROI 65–110%. Критично: UV-стойкий краситель (3+ года) — под солнце ОАЭ. Спрос: балконы, террасы, кашпо, "
  "входные зоны вилл.")
cb("Зелень и стебли (эвкалипт, гипсофила)",
  "Наборы эвкалипта (130/260 шт) и гипсофилы — лидер по потенциалу оборота, дёшевы в закупке, лёгкие "
  "(идеальны для добивки контейнера). Спрос: декор, свадьбы, флористика, HoReCa.")
cb("Комнатные растения и топиарий",
  "Сансевиерия (snake plant), монстера, настольные растения, топиарий-шары — акцентный интерьерный декор "
  "для квартир и офисов. Маржа 16–21%, стабильный круглогодичный спрос.")

# 6. SCENARIOS
H("6. Сценарии: запуск (по ТЗ) против рабочего режима",1)
P("По ТЗ отдельно просчитан агрессивный запуск (PPC 35% + купон 10%): в первые 2–3 месяца это съедает "
  "маржу почти в ноль — нормальная инвестиция в разгон. После выхода на органику реклама падает до ~12%, "
  "купон до ~3%, и портфель выходит на целевую маржу 17–31% и ROI 48–110%. Оба сценария считаются в Excel.",after=6)

# 7. INVESTMENT
H("7. Инвестиционный анализ",1)
rows=[("Оборотный капитал (закупка первых партий)",f"{capital:,.0f} AED"),
 ("Бюджет запуска (контент, образцы/QC, огнестойкость, PPC, логистика, резерв)",f"{launch:,.0f} AED"),
 ("ИТОГО стартовые инвестиции",f"{invest:,.0f} AED  (≈ ${invest/USD_AED:,.0f})"),
 ("Потенциал EBITDA/мес (полный разгон)",f"{mo:,.0f} AED"),
 ("Прибыль/мес после налога 9%",f"{after:,.0f} AED"),
 ("Окупаемость стартовых инвестиций",f"{payback:.1f} мес"),
 ("ROI за 12 месяцев",f"{roi12*100:.0f}%")]
ti=doc.add_table(rows=0,cols=2); ti.style="Light List Accent 1"
for k,v in rows:
    cc=ti.add_row().cells
    setw(cc[0],k,bold=("ИТОГО" in k or "Окупаемость" in k or "ROI" in k),size=9.5)
    setw(cc[1],v.replace(","," "),bold=True,size=9.5,align=WD_ALIGN_PARAGRAPH.RIGHT,
         color=(GREEN if ("Окупаемость" in k or "ROI" in k) else (RED if "ИТОГО" in k else None)))
P("",after=2)
P("Разбивка бюджета запуска:",bold=True,after=2)
for k,v in launch_items: bullet(f"{v:,.0f} AED — {k}".replace(","," "))
bullet(f"{launch-round(sum(v for _,v in launch_items)):,.0f} AED — резерв 10%".replace(","," "))

# 7.1 spend vs earn
H("7.1. Сколько потратим и сколько заработаем",2)
sc=["№","Товар","Заказ, шт","Закупка AED","Выручка/мес AED","EBITDA/мес AED","EBITDA/год AED"]
ts=doc.add_table(rows=1,cols=len(sc)); ts.style="Light Grid Accent 1"
for j,c in enumerate(sc):
    setw(ts.rows[0].cells[j],c,bold=True,size=8,color=RGBColor(0xFF,0xFF,0xFF),align=WD_ALIGN_PARAGRAPH.CENTER); shade(ts.rows[0].cells[j],"1F4E78")
sp_t=rev_t=eb_t=0
for i,x in enumerate(data,1):
    q=get_qty(x); spend=q*x["s_landed_aed"]; rev=x["uae_sales_mo"]*x["s_price_aed"]; eb=x["mo_ebitda_pot"]
    sp_t+=spend; rev_t+=rev; eb_t+=eb
    cc=ts.add_row().cells
    setw(cc[0],i,size=8,align=WD_ALIGN_PARAGRAPH.CENTER); setw(cc[1],meta[x["asin"]]["ru"],size=7.5)
    setw(cc[2],f"{q:,}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[3],f"{spend:,.0f}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[4],f"{rev:,.0f}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[5],f"{eb:,.0f}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    setw(cc[6],f"{eb*12:,.0f}".replace(","," "),size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
    if x["s_furniture"]: shade(cc[1],"E2EFDA")
tr=ts.add_row().cells; setw(tr[1],"ИТОГО (20 SKU)",bold=True,size=8)
for idx,val in [(3,sp_t),(4,rev_t),(5,eb_t),(6,eb_t*12)]:
    setw(tr[idx],f"{val:,.0f}".replace(","," "),bold=True,size=8,align=WD_ALIGN_PARAGRAPH.CENTER)
for c in tr: shade(c,"D9E1F2")
P("",after=2)
def month_eb(frac,mode):
    return sum(x["uae_sales_mo"]*frac*(x["l_ebitda"] if mode=="launch" else x["s_ebitda_unit"]) for x in data)
m13=month_eb(0.4,"launch")*3; m46=month_eb(0.7,"steady")*3; m712=month_eb(1.0,"steady")*6
yr1=m13+m46+m712; yr1n=yr1*(1-CIT)
bullet(f"{sp_t:,.0f} AED закупка + {launch:,.0f} AED запуск = ИТОГО старт ≈ {sp_t+launch:,.0f} AED (${(sp_t+launch)/USD_AED:,.0f}).".replace(","," "),bold_prefix="Потратим: ")
bullet(f"выручка ≈ {rev_t:,.0f} AED/мес, EBITDA ≈ {eb_t:,.0f} AED/мес (≈ {eb_t*12:,.0f}/год), после налога ≈ {eb_t*(1-CIT):,.0f}/мес.".replace(","," "),bold_prefix="Заработаем (разгон): ")
bullet(f"мес 1-3 {m13:,.0f}; мес 4-6 +{m46:,.0f}; мес 7-12 +{m712:,.0f}; EBITDA 1-го года ≈ {yr1:,.0f} (после налога {yr1n:,.0f}); минус запуск → денежный результат ≈ {yr1n-launch:,.0f} AED (${(yr1n-launch)/USD_AED:,.0f}).".replace(","," "),bold_prefix="1-й год: ")

# 8. RISKS
H("8. Риски и меры",1)
for k,v in [("UV-выцветание уличных позиций","требовать UV-стойкий краситель (сертификат), гарантия цвета 3+ года;"),
 ("Объёмный фрахт деревьев","возить разборными (ствол/крона отдельно), считать по м³, для крупных партий FCL;"),
 ("Огнестойкость для HoReCa/ТЦ","для B2B-канала обязателен сертификат огнестойкости (заложено в бюджет);"),
 ("Хрупкость/помятость в транзите","усиленная упаковка кроны, инспекция QC, буфер брака 2%;"),
 ("Нишевый объём","масштабировать через B2B (отели, рестораны, застройщики, ландшафт) и бандлы (растение + кашпо);"),
 ("FOB ориентировочные","RFQ у 3–5 поставщиков (Guangdong/Yiwu), образцы до заказа.")]:
    bullet(v,bold_prefix=f"{k}: ")

# 9. CONCLUSION
H("9. Выводы",1)
P(f"Запуск целесообразен как отдельная высокомаржинальная ниша. 20 новинок США проходят по марже, прибыли, "
  f"ROI и EBITDA для продажи на Amazon.ae в рабочем режиме (маржа 17–31%, ROI 48–110%). Это меньший по объёму "
  f"бизнес, чем широкий Home & Kitchen (потенциал ≈ {mo:,.0f} AED EBITDA/мес против ~73 000 у портфеля H&K), "
  f"но с дешёвым входом, быстрым оборотом капитала и главным рычагом роста — B2B-каналом ОАЭ (отели, "
  f"рестораны, ТЦ, застройщики, ландшафт).".replace(","," "),bold=True,after=4)
P(f"Экономика: стартовые инвестиции ≈ {invest:,.0f} AED (≈ ${invest/USD_AED:,.0f}) окупаются за ≈ {payback:.1f} мес; "
  f"ROI за 12 мес ≈ {roi12*100:.0f}%. Ведём двумя волнами: сначала уличные UV-цветы и наборы эвкалипта "
  f"(быстрый оборот), затем деревья и комнатные растения (высокий чек + выход на B2B).".replace(","," "),after=4)
P("Следующие шаги: (1) RFQ по 20 позициям (UV-стойкость, огнестойкость для деревьев); (2) образцы + QC; "
  "(3) запуск Волны 1; (4) параллельно — прямые контакты с отелями/ландшафтными компаниями ОАЭ под деревья. "
  "Все цифры пересчитываются в Excel при вводе ваших данных.",after=6)
P("Приложения: (1) Excel-модель ТЭО с живыми формулами (UAE_ArtificialPlants_TEO_Model_2026-07.xlsx); "
  "(2) ссылки Alibaba по каждому SKU.",size=9,color=RGBColor(0x60,0x60,0x60))
disc=doc.add_paragraph(); r=disc.add_run(
  "Дисклеймер: данные Keepa (США, подкатегория Artificial Plants & Flowers, 09.07.2026); спрос ОАЭ проверен по "
  "amazon.ae. Цены ОАЭ, FOB, фрахт и FBA — ориентиры для планирования; подтверждаются RFQ и FBA-калькулятором "
  "Seller Central .ae. Ссылки Alibaba — реальные карточки/витрины; MOQ/цены уточняются у поставщиков.")
r.font.size=Pt(8); r.font.color.rgb=RGBColor(0x80,0x80,0x80)

out=f"{BASE}/deliverables/UAE_ArtificialPlants_Report_2026-07.docx"
doc.save(out)
print("saved",out)
print(f"capital={capital:,.0f} launch={launch:,.0f} invest={invest:,.0f} moEB={mo:,.0f} payback={payback:.1f} roi12={roi12*100:.0f}%")
