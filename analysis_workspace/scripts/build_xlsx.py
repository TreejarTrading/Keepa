#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the editable UAE TEO / investment XLSX with LIVE formulas."""
import json
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side, NamedStyle
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import os
BASE="/home/user/Keepa"
DATA_JSON=os.environ.get("DATA_JSON",f"{BASE}/analysis_workspace/03_unit_economics/uae_final20.json")
META_JSON=os.environ.get("META_JSON",f"{BASE}/analysis_workspace/04_alibaba/sku_meta.json")
OUT_XLSX=os.environ.get("OUT_XLSX",f"{BASE}/deliverables/UAE_HomeKitchen_TEO_Model_2026-07.xlsx")
THEME_NOTE=os.environ.get("THEME_NOTE","Home & Kitchen + мебель/офисные кресла")
data=json.load(open(DATA_JSON))
meta=json.load(open(META_JSON))

# pilot order quantities (editable defaults); fallback = ~3 months of UAE sales
QTY={"B0GKMVTD6V":600,"B0GV2DHXWS":500,"B0GT8HK7LS":300,"B0GZVM23CF":300,"B0H13ZY2W4":250,
     "B0GQHGFFHC":300,"B0GJ4NHH4L":300,"B0GYF91BXB":1200,"B0GSZHLZ3B":500,"B0GZZ3VM69":400,
     "B0G5DSK3YF":400,"B0GCJQ4Z51":400,"B0GF7LLCL8":300,"B0GDTFFKYC":500,"B0FZRGB6BN":120,
     "B0GXKMXLDC":120,"B0H2B94R5F":150,"B0GN1P7DTT":80,"B0GL357H51":200,"B0G1SX2D8H":200}
def get_qty(x):
    if os.environ.get("FALLBACK_QTY")=="1": return max(60,round(x.get("uae_sales_mo",100)*3))
    return QTY.get(x["asin"]) or max(60,round(x.get("uae_sales_mo",100)*3))

wb=Workbook()
HDR=PatternFill("solid",fgColor="1F4E78"); SUB=PatternFill("solid",fgColor="2E75B6")
PARAMFILL=PatternFill("solid",fgColor="FFF2CC"); INFILL=PatternFill("solid",fgColor="E2EFDA")
TOTFILL=PatternFill("solid",fgColor="D9E1F2")
WHITE=Font(color="FFFFFF",bold=True); BOLD=Font(bold=True)
LINK=Font(color="0563C1",underline="single")
thin=Side(style="thin",color="BFBFBF"); BORD=Border(left=thin,right=thin,top=thin,bottom=thin)
CEN=Alignment(horizontal="center",vertical="center",wrap_text=True)
LEFT=Alignment(horizontal="left",vertical="center",wrap_text=True)

# ---------- Sheet 1: Параметры ----------
ws=wb.active; ws.title="Параметры"
ws.sheet_view.showGridLines=False
ws["A1"]="ПАРАМЕТРЫ МОДЕЛИ — редактируйте жёлтые ячейки, все расчёты пересчитаются автоматически"
ws["A1"].font=Font(bold=True,size=13,color="1F4E78"); ws.merge_cells("A1:D1")
params=[
 ("USD_AED","Курс USD→AED (фикс.)",3.6725,"0.0000"),
 ("VAT","НДС ОАЭ",0.05,"0.0%"),
 ("REF","Referral fee (Home&Kitchen >50 AED)",0.15,"0.0%"),
 ("DUTY","Таможенная пошлина ОАЭ (CIF)",0.05,"0.0%"),
 ("SEA","Фрахт море Китай→Джебель-Али, $/м³",165,"$#,##0"),
 ("FRTKG","Фрахт минимум, $/кг",0.45,"$#,##0.00"),
 ("INBOUND","Приёмка/prep на FBA, AED/шт",2.0,"#,##0.0"),
 ("RET","Резерв на возвраты",0.02,"0.0%"),
 ("MKT","Маркетинг (внешний/бренд)",0.03,"0.0%"),
 ("PPC_S","PPC/реклама — рабочий режим",0.12,"0.0%"),
 ("COUP_S","Купон/скидка — рабочий режим",0.03,"0.0%"),
 ("PPC_L","PPC/реклама — ЗАПУСК (ТЗ)",0.35,"0.0%"),
 ("COUP_L","Купон/скидка — ЗАПУСК (ТЗ)",0.10,"0.0%"),
 ("UAE_MKT","Рынок ОАЭ как доля от объёма US",0.05,"0.0%"),
 ("SHARE","Наш захват ниши в ОАЭ",0.30,"0.0%"),
 ("CIT","Налог на прибыль ОАЭ (>375k AED)",0.09,"0.0%"),
]
r=3
ws.cell(r-1,1,"Параметр").font=BOLD; ws.cell(r-1,2,"Значение").font=BOLD
for name,label,val,fmt in params:
    ws.cell(r,1,label).alignment=LEFT
    c=ws.cell(r,2,val); c.fill=PARAMFILL; c.number_format=fmt; c.font=BOLD; c.border=BORD
    c.alignment=CEN
    from openpyxl.workbook.defined_name import DefinedName
    wb.defined_names[name]=DefinedName(name, attr_text=f"'Параметры'!$B${r}")
    r+=1
ws.column_dimensions["A"].width=42; ws.column_dimensions["B"].width=12
note_r=r+1
notes=[
 "МЕТОДИКА:",
 f"• Источник спроса — новинки Amazon US ({THEME_NOTE}), отслеживание с 2026.",
 "• Целевой рынок — Amazon.ae (ОАЭ), модель FBA. Цена ОАЭ = цена US × курс × наценка рынка (проверено по живым данным .ae).",
 "• 'Рабочий режим' — устойчивая экономика после разгона; 'ЗАПУСК' — повышенная реклама/скидки первые 2-3 мес (по ТЗ: PPC 35%, купон 10%).",
 "• FBA-сбор берётся из справочной таблицы (лист 'Справка_FBA'), поле редактируемое.",
 "• EBITDA/шт = Чистая выручка (без НДС) − (Referral + FBA + PPC + Купон + Маркетинг + Возвраты) − Landed COGS.",
 "• ROI = EBITDA/шт ÷ Landed COGS/шт. Маржа = EBITDA/шт ÷ Чистая выручка.",
 "• FOB и объём — ориентировочные (подтвердить RFQ у 3-5 поставщиков Alibaba).",
]
for i,t in enumerate(notes):
    cc=ws.cell(note_r+i,1,t); cc.alignment=LEFT
    if t.endswith(":"): cc.font=BOLD
    ws.merge_cells(start_row=note_r+i,start_column=1,end_row=note_r+i,end_column=6)

# ---------- Sheet 2: Модель_TEO ----------
m=wb.create_sheet("Модель_ТЭО")
m.sheet_view.showGridLines=False
cols=[("№",5),("Товар",34),("ASIN (кликаб.)",13),("Категория",20),
 ("Цена US, $",9),("Цена ОАЭ, AED",11),("Вес, кг",8),("Объём, м³",9),
 ("FOB $/шт",9),("FBA AED/шт",10),("Продажи US/мес",11),
 ("Фрахт $/шт",9),("Пошлина $",9),("Landed AED/шт",11),
 ("Referral AED",10),("PPC AED",9),("Купон AED",9),("Маркетинг AED",10),("Возвраты AED",10),
 ("НДС AED",9),("Чист.выручка AED",12),
 ("EBITDA/шт (режим)",12),("Маржа % (режим)",11),("ROI % (режим)",10),
 ("EBITDA/шт (запуск)",12),("Маржа % (запуск)",11),
 ("Потенц. EBITDA/мес AED",13),("Alibaba",11),("Вердикт",10)]
m.cell(1,1,"ТЕХНИКО-ЭКОНОМИЧЕСКОЕ ОБОСНОВАНИЕ — Amazon.ae (ОАЭ), FBA. Жёлтые/зелёные ячейки — ввод; серые — формулы.").font=Font(bold=True,size=12,color="1F4E78")
m.merge_cells(start_row=1,start_column=1,end_row=1,end_column=len(cols))
hr=3
for j,(name,w) in enumerate(cols,1):
    c=m.cell(hr,j,name); c.fill=HDR; c.font=WHITE; c.alignment=CEN; c.border=BORD
    m.column_dimensions[get_column_letter(j)].width=w
m.freeze_panes="C4"
# column letters + indices
L={name:get_column_letter(j) for j,(name,_) in enumerate(cols,1)}
IDX={name:j for j,(name,_) in enumerate(cols,1)}
def CL(n): return L[n]
first=hr+1
for i,x in enumerate(data):
    r=first+i; a=x["asin"]; md=meta[a]
    F=CL
    m.cell(r,1,i+1).alignment=CEN
    m.cell(r,2,md["ru"]).alignment=LEFT
    ac=m.cell(r,3,a); ac.hyperlink=f"https://www.amazon.ae/dp/{a}"; ac.font=LINK; ac.alignment=CEN
    m.cell(r,4,md["cat_ru"]).alignment=LEFT
    # inputs
    vE=m.cell(r,5,round(float(x["s_price_aed"])/3.6725/1.0,2)); # placeholder US price recomputed below properly
    # use real US price: reverse not needed—store actual from record if present; we kept price_aed only, so approximate US:
    us_price=round(x["s_price_aed"]/(3.6725*(1.25 if x["s_furniture"] else 1.12)),2)
    m.cell(r,5,us_price).number_format="$#,##0.00"
    m.cell(r,6,x["s_price_aed"]).number_format="#,##0"
    m.cell(r,7,x["weight_kg"]).number_format="#,##0.00"
    m.cell(r,8,x["s_vol_cbm"]).number_format="0.0000"
    m.cell(r,9,x["s_fob_usd"]).number_format="$#,##0.00"
    m.cell(r,10,x["s_fba"]).number_format="#,##0.0"
    m.cell(r,11,x["monthly_sold"]).number_format="#,##0"
    for col in (5,6,7,8,9,10,11):
        m.cell(r,col).fill=INFILL; m.cell(r,col).border=BORD; m.cell(r,col).alignment=CEN
    # formulas
    e,f,g,h,ii,jj,k=F("Цена US, $"),F("Цена ОАЭ, AED"),F("Вес, кг"),F("Объём, м³"),F("FOB $/шт"),F("FBA AED/шт"),F("Продажи US/мес")
    frt=F("Фрахт $/шт"); dut=F("Пошлина $"); lnd=F("Landed AED/шт")
    ref=F("Referral AED"); ppc=F("PPC AED"); cou=F("Купон AED"); mkt=F("Маркетинг AED"); ret=F("Возвраты AED")
    vat=F("НДС AED"); nrev=F("Чист.выручка AED"); eb=F("EBITDA/шт (режим)"); mrg=F("Маржа % (режим)"); roi=F("ROI % (режим)")
    ebl=F("EBITDA/шт (запуск)"); mrgl=F("Маржа % (запуск)"); pot=F("Потенц. EBITDA/мес AED")
    def put(col,formula,fmt):
        c=m.cell(r,L[col]==None and 1 or 0)  # dummy
    # write formulas by column letter
    m[f"{frt}{r}"]=f"=MAX({h}{r}*SEA,{g}{r}*FRTKG)"; m[f"{frt}{r}"].number_format="$#,##0.00"
    m[f"{dut}{r}"]=f"=({ii}{r}+{frt}{r})*DUTY"; m[f"{dut}{r}"].number_format="$#,##0.00"
    m[f"{lnd}{r}"]=f"=({ii}{r}+{frt}{r}+{dut}{r})*USD_AED+INBOUND"; m[f"{lnd}{r}"].number_format="#,##0.0"
    m[f"{ref}{r}"]=f"={f}{r}*REF"; m[f"{ref}{r}"].number_format="#,##0.0"
    m[f"{ppc}{r}"]=f"={f}{r}*PPC_S"; m[f"{ppc}{r}"].number_format="#,##0.0"
    m[f"{cou}{r}"]=f"={f}{r}*COUP_S"; m[f"{cou}{r}"].number_format="#,##0.0"
    m[f"{mkt}{r}"]=f"={f}{r}*MKT"; m[f"{mkt}{r}"].number_format="#,##0.0"
    m[f"{ret}{r}"]=f"={f}{r}*RET"; m[f"{ret}{r}"].number_format="#,##0.0"
    m[f"{vat}{r}"]=f"={f}{r}-{f}{r}/(1+VAT)"; m[f"{vat}{r}"].number_format="#,##0.0"
    m[f"{nrev}{r}"]=f"={f}{r}/(1+VAT)"; m[f"{nrev}{r}"].number_format="#,##0.0"
    m[f"{eb}{r}"]=f"={nrev}{r}-({ref}{r}+{jj}{r}+{ppc}{r}+{cou}{r}+{mkt}{r}+{ret}{r})-{lnd}{r}"; m[f"{eb}{r}"].number_format="#,##0.0"; m[f"{eb}{r}"].font=BOLD
    m[f"{mrg}{r}"]=f"={eb}{r}/{nrev}{r}"; m[f"{mrg}{r}"].number_format="0.0%"; m[f"{mrg}{r}"].font=BOLD
    m[f"{roi}{r}"]=f"={eb}{r}/{lnd}{r}"; m[f"{roi}{r}"].number_format="0%"; m[f"{roi}{r}"].font=BOLD
    m[f"{ebl}{r}"]=f"={nrev}{r}-({ref}{r}+{jj}{r}+{f}{r}*PPC_L+{f}{r}*COUP_L+{mkt}{r}+{ret}{r})-{lnd}{r}"; m[f"{ebl}{r}"].number_format="#,##0.0"
    m[f"{mrgl}{r}"]=f"={ebl}{r}/{nrev}{r}"; m[f"{mrgl}{r}"].number_format="0.0%"
    m[f"{pot}{r}"]=f"={eb}{r}*{k}{r}*UAE_MKT*SHARE"; m[f"{pot}{r}"].number_format="#,##0"
    # alibaba link
    al=m.cell(r,IDX["Alibaba"]); al.value="ссылка"; al.hyperlink=md["alibaba"][0]; al.font=LINK; al.alignment=CEN
    vd="ЗАПУСК" if (x["s_margin"]>=15 and x["s_roi"]>=40) else "СТРАТЕГ."
    m.cell(r,IDX["Вердикт"],vd).alignment=CEN
    for j in range(1,len(cols)+1):
        m.cell(r,j).border=BORD
        if m.cell(r,j).alignment is None: m.cell(r,j).alignment=CEN
# totals
tr=first+len(data)
m.cell(tr,2,"ИТОГО портфель").font=BOLD; m.cell(tr,2).fill=TOTFILL
potc=CL("Потенц. EBITDA/мес AED")
m[f"{potc}{tr}"]=f"=SUM({potc}{first}:{potc}{tr-1})"; m[f"{potc}{tr}"].font=BOLD; m[f"{potc}{tr}"].number_format="#,##0"; m[f"{potc}{tr}"].fill=TOTFILL
for j in range(1,len(cols)+1):
    m.cell(tr,j).fill=TOTFILL; m.cell(tr,j).border=BORD

# ---------- Sheet 3: Инвестиции ----------
inv=wb.create_sheet("Инвестиции")
inv.sheet_view.showGridLines=False
inv.cell(1,1,"ИНВЕСТИЦИОННЫЙ АНАЛИЗ (рабочий режим). Ввод: 'Заказ, шт' и бюджет запуска. Остальное — формулы.").font=Font(bold=True,size=12,color="1F4E78")
inv.merge_cells("A1:H1")
icols=[("№",5),("Товар",34),("Заказ, шт",10),("Landed AED/шт",12),("Капитал закупки AED",14),
 ("EBITDA/шт AED",12),("EBITDA/мес (при захвате) AED",16),("Окупаемость партии, мес",14)]
ihr=3
for j,(n,w) in enumerate(icols,1):
    c=inv.cell(ihr,j,n); c.fill=HDR; c.font=WHITE; c.alignment=CEN; c.border=BORD
    inv.column_dimensions[get_column_letter(j)].width=w
ifirst=ihr+1
for i,x in enumerate(data):
    r=ifirst+i; a=x["asin"]
    mrow=first+i
    inv.cell(r,1,i+1).alignment=CEN
    inv.cell(r,2,meta[a]["ru"]).alignment=LEFT
    q=inv.cell(r,3,get_qty(x)); q.fill=INFILL; q.number_format="#,##0"; q.alignment=CEN; q.border=BORD
    inv.cell(r,4).value=f"=Модель_ТЭО!{CL('Landed AED/шт')}{mrow}"; inv.cell(r,4).number_format="#,##0.0"
    inv.cell(r,5).value=f"=C{r}*D{r}"; inv.cell(r,5).number_format="#,##0"
    inv.cell(r,6).value=f"=Модель_ТЭО!{CL('EBITDA/шт (режим)')}{mrow}"; inv.cell(r,6).number_format="#,##0.0"
    inv.cell(r,7).value=f"=Модель_ТЭО!{CL('Потенц. EBITDA/мес AED')}{mrow}"; inv.cell(r,7).number_format="#,##0"
    inv.cell(r,8).value=f"=IF(G{r}>0,E{r}/G{r},\"—\")"; inv.cell(r,8).number_format="0.0"
    for j in range(1,9): inv.cell(r,j).border=BORD
itr=ifirst+len(data)
inv.cell(itr,2,"ИТОГО закупка (оборотный капитал)").font=BOLD
inv.cell(itr,5).value=f"=SUM(E{ifirst}:E{itr-1})"; inv.cell(itr,5).font=BOLD; inv.cell(itr,5).number_format="#,##0"
inv.cell(itr,7).value=f"=SUM(G{ifirst}:G{itr-1})"; inv.cell(itr,7).font=BOLD; inv.cell(itr,7).number_format="#,##0"
for j in range(1,9): inv.cell(itr,j).fill=TOTFILL; inv.cell(itr,j).border=BORD
# launch budget block
b=itr+2
inv.cell(b,2,"БЮДЖЕТ ЗАПУСКА (единовременно), AED").font=BOLD; inv.cell(b,2).fill=SUB; inv.cell(b,2).font=WHITE
budget=[("Фотоконтент + A+ листинги (20 SKU)",18000),
 ("Образцы + инспекция качества (QC)",14000),
 ("Сертификация/регистрация (ESMA/G-mark, бренд)",22000),
 ("Стартовая реклама PPC (буфер сверх юнит-экономики)",60000),
 ("Логистика первой партии (буфер/страховка)",15000),
 ("Резерв 10%",0)]
br=b+1
for lbl,val in budget:
    inv.cell(br,2,lbl).alignment=LEFT
    c=inv.cell(br,5,val); c.fill=INFILL; c.number_format="#,##0"; c.border=BORD
    br+=1
inv.cell(br-1,5).value=f"=ROUND(SUM(E{b+1}:E{br-2})*0.1,0)"  # reserve 10%
inv.cell(br,2,"Итого бюджет запуска").font=BOLD
inv.cell(br,5).value=f"=SUM(E{b+1}:E{br-1})"; inv.cell(br,5).font=BOLD; inv.cell(br,5).number_format="#,##0"; inv.cell(br,5).fill=TOTFILL
# grand totals
g=br+2
inv.cell(g,2,"ИТОГО СТАРТОВЫЕ ИНВЕСТИЦИИ (закупка + запуск), AED").font=BOLD
inv.cell(g,5).value=f"=E{itr}+E{br}"; inv.cell(g,5).font=Font(bold=True,color="C00000"); inv.cell(g,5).number_format="#,##0"
inv.cell(g+1,2,"в USD").alignment=LEFT
inv.cell(g+1,5).value=f"=E{g}/USD_AED"; inv.cell(g+1,5).number_format="$#,##0"
inv.cell(g+2,2,"Потенциал EBITDA/мес (полный разгон), AED").font=BOLD
inv.cell(g+2,5).value=f"=G{itr}"; inv.cell(g+2,5).number_format="#,##0"; inv.cell(g+2,5).font=BOLD
inv.cell(g+3,2,"Прибыль после налога ОАЭ 9% (в мес), AED").alignment=LEFT
inv.cell(g+3,5).value=f"=G{itr}*(1-CIT)"; inv.cell(g+3,5).number_format="#,##0"
inv.cell(g+4,2,"Окупаемость стартовых инвестиций, мес").font=BOLD
inv.cell(g+4,5).value=f"=E{g}/(G{itr}*(1-CIT))"; inv.cell(g+4,5).number_format="0.0"; inv.cell(g+4,5).font=Font(bold=True,color="1F6E28")
inv.cell(g+5,2,"ROI за 12 мес (годовая EBITDA после налога / инвестиции)").alignment=LEFT
inv.cell(g+5,5).value=f"=G{itr}*(1-CIT)*12/E{g}"; inv.cell(g+5,5).number_format="0%"
for rr in range(g,g+6): inv.cell(rr,5).border=BORD

# ---------- Sheet 4: Справка_FBA ----------
s=wb.create_sheet("Справка_FBA")
s.sheet_view.showGridLines=False
s.cell(1,1,"СПРАВОЧНО: ориентировочная шкала FBA-сборов Amazon.ae (AED, 2026). Значения перенесите в столбец 'FBA AED/шт'.").font=Font(bold=True,color="1F4E78")
s.merge_cells("A1:D1")
tab=[("Стандарт ≤250 г",7.2),("Стандарт ≤500 г",8.5),("Стандарт ≤1 кг",11.0),("Стандарт ≤2 кг",14.5),
 ("Стандарт ≤3 кг",16.5),("Стандарт ≤5 кг",18.5),("Стандарт ≤9 кг",20.0),("Стандарт ≤12 кг",21.5),
 ("Крупногабарит ≤2 кг",25.0),("Крупногабарит ≤5 кг",32.0),("Крупногабарит ≤10 кг",41.5),
 ("Тяж./объём ≤15 кг",60.0),("Тяж./объём ≤20 кг",78.0),("Тяж./объём ≤25 кг",92.0),
 ("Тяж./объём ≤30 кг",108.0),("Тяж./объём >30 кг","108 + 3/кг сверх 30")]
s.cell(3,1,"Тариф/категория").font=BOLD; s.cell(3,2,"AED/шт").font=BOLD
s.cell(3,1).fill=SUB; s.cell(3,1).font=WHITE; s.cell(3,2).fill=SUB; s.cell(3,2).font=WHITE
for i,(lbl,val) in enumerate(tab):
    s.cell(4+i,1,lbl); c=s.cell(4+i,2,val)
    if isinstance(val,(int,float)): c.number_format="#,##0.0"
    s.cell(4+i,1).border=BORD; c.border=BORD
s.column_dimensions["A"].width=34; s.column_dimensions["B"].width=22
refnotes=["Referral (комиссия) Home & Kitchen: 8% при цене ≤50 AED, 15% при >50 AED.",
 "НДС ОАЭ 5% включён в розничную цену (выделяется в модели).",
 "Пошлина ОАЭ 5% от CIF (FOB+фрахт).",
 "Пороги стандарт/крупногабарит зависят и от габаритов (длиннейшая сторона >45 см → крупногабарит).",
 "Точные тарифы — в FBA Revenue Calculator в Seller Central .ae (после входа)."]
for i,t in enumerate(refnotes):
    s.cell(4+len(tab)+1+i,1,t).alignment=LEFT
    s.merge_cells(start_row=4+len(tab)+1+i,start_column=1,end_row=4+len(tab)+1+i,end_column=5)

# ---------- Sheet 5: Расходы_Доходы (spend vs earn) ----------
se=wb.create_sheet("Расходы_Доходы")
se.sheet_view.showGridLines=False
se.cell(1,1,"СКОЛЬКО ПОТРАТИМ И СКОЛЬКО ЗАРАБОТАЕМ. Столбец 'Заказ, шт' — ввод; остальное — формулы.").font=Font(bold=True,size=12,color="1F4E78")
se.merge_cells("A1:M1")
scols=[("№",5),("Товар",34),("Заказ, шт",9),("Landed AED/шт",11),("ЗАКУПКА AED",12),
 ("Продажи ОАЭ/мес",12),("Цена AED",9),("Выручка/мес AED",13),
 ("EBITDA/шт (режим)",12),("EBITDA/мес AED",12),("EBITDA/мес (запуск)",13),("EBITDA/год AED",13)]
shr=3
for j,(n,w) in enumerate(scols,1):
    c=se.cell(shr,j,n); c.fill=HDR; c.font=WHITE; c.alignment=CEN; c.border=BORD
    se.column_dimensions[get_column_letter(j)].width=w
sfirst=shr+1
for i,x in enumerate(data):
    r=sfirst+i; a=x["asin"]; mrow=first+i
    se.cell(r,1,i+1).alignment=CEN
    se.cell(r,2,meta[a]["ru"]).alignment=LEFT
    q=se.cell(r,3,get_qty(x)); q.fill=INFILL; q.number_format="#,##0"; q.alignment=CEN
    se.cell(r,4).value=f"=Модель_ТЭО!{CL('Landed AED/шт')}{mrow}"; se.cell(r,4).number_format="#,##0.0"
    se.cell(r,5).value=f"=C{r}*D{r}"; se.cell(r,5).number_format="#,##0"
    se.cell(r,6).value=f"=Модель_ТЭО!{CL('Продажи US/мес')}{mrow}*UAE_MKT*SHARE"; se.cell(r,6).number_format="#,##0"
    se.cell(r,7).value=f"=Модель_ТЭО!{CL('Цена ОАЭ, AED')}{mrow}"; se.cell(r,7).number_format="#,##0"
    se.cell(r,8).value=f"=F{r}*G{r}"; se.cell(r,8).number_format="#,##0"
    se.cell(r,9).value=f"=Модель_ТЭО!{CL('EBITDA/шт (режим)')}{mrow}"; se.cell(r,9).number_format="#,##0.0"
    se.cell(r,10).value=f"=F{r}*I{r}"; se.cell(r,10).number_format="#,##0"
    se.cell(r,11).value=f"=F{r}*Модель_ТЭО!{CL('EBITDA/шт (запуск)')}{mrow}"; se.cell(r,11).number_format="#,##0"
    se.cell(r,12).value=f"=J{r}*12"; se.cell(r,12).number_format="#,##0"
    for j in range(1,13): se.cell(r,j).border=BORD
str_=sfirst+len(data)
se.cell(str_,2,"ИТОГО (20 SKU)").font=BOLD
for col in (5,8,10,11,12):
    L2=get_column_letter(col); se.cell(str_,col).value=f"=SUM({L2}{sfirst}:{L2}{str_-1})"
    se.cell(str_,col).font=BOLD; se.cell(str_,col).number_format="#,##0"
for j in range(1,13): se.cell(str_,j).fill=TOTFILL; se.cell(str_,j).border=BORD
# summary + 12-month ramp
b=str_+2
def srow(r,label,formula,fmt="#,##0",bold=False,color=None):
    se.cell(r,2,label).alignment=LEFT
    if bold: se.cell(r,2).font=BOLD
    c=se.cell(r,5); c.value=formula; c.number_format=fmt; c.alignment=CEN
    if bold: c.font=BOLD
    if color: c.font=Font(bold=True,color=color)
    c.border=BORD
se.cell(b,2,"ИТОГ: РАСХОДЫ И ДОХОДЫ").font=WHITE; se.cell(b,2).fill=SUB
srow(b+1,"Закупка (оборотный капитал), AED",f"=E{str_}",bold=True)
srow(b+2,"Бюджет запуска (единоразово), AED","=(18000+14000+22000+60000+15000)*1.1")
srow(b+3,"ИТОГО потратим на старте, AED",f"=E{b+1}+E{b+2}",bold=True,color="C00000")
srow(b+4,"Выручка/мес (полный разгон), AED",f"=H{str_}")
srow(b+5,"EBITDA/мес (полный разгон), AED",f"=J{str_}",bold=True)
srow(b+6,"Прибыль/мес после налога 9%, AED",f"=J{str_}*(1-CIT)")
srow(b+7,"EBITDA/год (полный разгон), AED",f"=M{str_}",bold=True)
se.cell(b+9,2,"12-МЕСЯЧНЫЙ ПРОГНОЗ (разгон, PPC 35% в старте)").font=WHITE; se.cell(b+9,2).fill=SUB
srow(b+10,"Мес 1-3 (запуск, 40% объёма)",f"=L{str_}*0.4*3")
srow(b+11,"Мес 4-6 (70% объёма, режим)",f"=J{str_}*0.7*3")
srow(b+12,"Мес 7-12 (100% объёма, режим)",f"=J{str_}*6")
srow(b+13,"EBITDA за 1-й год (до налога), AED",f"=E{b+10}+E{b+11}+E{b+12}",bold=True)
srow(b+14,"Чистая прибыль 1-го года после 9%, AED",f"=E{b+13}*(1-CIT)",bold=True,color="1F6E28")
srow(b+15,"Денежный результат 1-го года (минус бюджет запуска), AED",f"=E{b+14}-E{b+2}",bold=True,color="1F6E28")

# force Excel/Sheets to recalculate all formulas on open (openpyxl stores no cached values)
try:
    from openpyxl.workbook.properties import CalcProperties
    wb.calculation=CalcProperties(fullCalcOnLoad=True)
except Exception as e:
    print("calc prop warn:",e)
out=OUT_XLSX
wb.save(out)
print("saved",out)
