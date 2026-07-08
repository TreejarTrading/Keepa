#!/usr/bin/env python3
"""Рабочая финмодель XLSX: параметры + модель SKU (формулы) + сценарии + P&L пилота + cash-flow."""
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = openpyxl.Workbook()

INK = "20242B"; MUTED = "5C6470"; ACCENT = "8A5A0E"; GOOD = "1F7D54"; BAD = "A8402C"
HDR_FILL = PatternFill("solid", fgColor="F2EFE7")
EDIT_FILL = PatternFill("solid", fgColor="FFF3D6")   # желтые = редактируемые
CALC_FILL = PatternFill("solid", fgColor="EFF5EF")   # зеленоватые = формулы
W1_FILL = PatternFill("solid", fgColor="F7EAD0"); W2_FILL = PatternFill("solid", fgColor="E2ECF5")
ST_FILL = PatternFill("solid", fgColor="EAE8E1")
thin = Side(style="thin", color="D9D5CA"); BORDER = Border(left=thin, right=thin, top=thin, bottom=thin)
BOLD = Font(bold=True, color=INK); HDR_FONT = Font(bold=True, size=9, color=MUTED)

def style_header(ws, row, cols):
    for c in range(1, cols + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = HDR_FILL; cell.font = HDR_FONT; cell.border = BORDER
        cell.alignment = Alignment(wrap_text=True, vertical="center")

# ============ Лист 1: Параметры ============
ws = wb.active; ws.title = "Параметры"
params = [
    ("Курс USD→EUR", 0.92, "консервативный"),
    ("НДС Германия", 0.19, "изъят из розничной цены"),
    ("Referral Amazon", 0.15, "категории портфеля"),
    ("PPC по умолчанию (запуск)", 0.12, "Jura 10%, B2B 5% — заданы в листе Модель"),
    ("Возвраты", 0.02, "% от цены"),
    ("Преп/маркировка €/шт", 0.30, ""),
    ("QC/брак", 0.03, "% от FOB"),
    ("Целевая маржа A", 0.25, "порог «Закупка ≤»"),
    ("Целевая маржа B (минимум)", 0.20, "порог отмены SKU: <15% на факт. landed"),
    ("Разгон: доля цели в первые 90 дней", 0.40, "для P&L пилота"),
]
ws.append(["Параметр", "Значение", "Комментарий"])
for p in params: ws.append(list(p))
style_header(ws, 1, 3)
for r in range(2, len(params) + 2):
    ws.cell(row=r, column=2).fill = EDIT_FILL
    ws.cell(row=r, column=2).number_format = "0.00"
    for c in range(1, 4): ws.cell(row=r, column=c).border = BORDER
ws.column_dimensions["A"].width = 34; ws.column_dimensions["B"].width = 11; ws.column_dimensions["C"].width = 46
ws.append([]); ws.append(["Желтые ячейки — редактируйте (параметры и котировки). Зеленоватые — формулы, пересчет автоматический."])
ws.cell(row=len(params) + 3, column=1).font = Font(italic=True, size=9, color=MUTED)

P = "Параметры"
FX, VAT, REF, PPCD, RET, PREP, QC, TA, TB, RAMP = [f"{P}!$B${i}" for i in range(2, 12)]

# ============ Лист 2: Модель SKU ============
ws = wb.create_sheet("Модель SKU")
headers = ["SKU", "Волна", "Цена €", "FBA €", "Хран. €", "PPC %", "FOB $ (котировка)", "Фрахт €/шт",
           "Пошлина %", "Нетто €", "Referral €", "PPC €", "Возвраты €", "Landed €",
           "Прибыль €/шт", "Маржа %", "ROI %", "FOB ≤ (25%)", "FOB ≤ (20%)", "Безубыток €",
           "Партия, шт", "Цель, шт/мес", "Прибыль €/мес"]
ws.append(headers); style_header(ws, 1, len(headers))

SKUS = [
    ("Фильтр Jura RFID 6er", "В1", 42.99, 3.46, 0.40, 0.10, 10.00, 0.50, 0.035, 500, 500),
    ("Фильтр DeLonghi 6er", "В1", 24.99, 3.47, 0.40, 0.12, 4.00, 0.50, 0.035, 500, 600),
    ("Kühltasche 40L", "В1", 34.99, 4.59, 0.45, 0.12, 4.50, 0.90, 0.097, 500, 300),
    ("Brotbeutel 2er", "В1", 19.99, 3.08, 0.35, 0.12, 2.20, 0.40, 0.12, 500, 180),
    ("TV-стенд CT7501", "Страт", 149.99, 14.11, 3.50, 0.10, 29.70, 3.30, 0.0, 200, 75),
    ("Картотека ZY-3", "Страт", 219.00, 25.00, 5.00, 0.05, 45.00, 22.00, 0.0, 40, 21),
    ("Kirschentkerner", "В2", 45.99, 3.86, 0.45, 0.12, 5.00, 0.70, 0.085, 500, 400),
    ("Fliegengitter 4er", "В2", 39.99, 5.48, 0.50, 0.12, 6.50, 1.25, 0.065, 500, 300),
    ("Kühldecke Arc-Chill", "В2", 42.99, 4.42, 0.60, 0.12, 8.50, 1.00, 0.12, 300, 225),
]
for i, s in enumerate(SKUS):
    r = i + 2
    ws.append([s[0], s[1], s[2], s[3], s[4], s[5], s[6], s[7], s[8],
        f"=C{r}/(1+{VAT})",                       # J нетто
        f"=C{r}*{REF}",                            # K referral
        f"=C{r}*F{r}",                             # L ppc
        f"=C{r}*{RET}",                            # M возвраты
        f"=G{r}*{FX}*(1+I{r}+{QC})+H{r}+{PREP}",   # N landed
        f"=J{r}-K{r}-D{r}-E{r}-L{r}-M{r}-N{r}",    # O прибыль
        f"=O{r}/C{r}",                             # P маржа
        f"=O{r}/N{r}",                             # Q roi
        f"=(J{r}-K{r}-D{r}-E{r}-L{r}-M{r}-{TA}*C{r}-H{r}-{PREP})/({FX}*(1+I{r}+{QC}))",  # R fob25
        f"=(J{r}-K{r}-D{r}-E{r}-L{r}-M{r}-{TB}*C{r}-H{r}-{PREP})/({FX}*(1+I{r}+{QC}))",  # S fob20
        f"=(D{r}+E{r}+N{r})/(1/(1+{VAT})-({REF}+F{r}+{RET}))",                            # T безубыток
        s[9], s[10],
        f"=O{r}*V{r}",                             # W прибыль/мес
    ])
tr = len(SKUS) + 2
ws.append(["ИТОГО портфель"] + [""] * 21 + [f"=SUM(W2:W{tr-1})"])
for c in range(1, 24): ws.cell(row=tr, column=c).font = BOLD; ws.cell(row=tr, column=c).fill = HDR_FILL

wave_fill = {"В1": W1_FILL, "В2": W2_FILL, "Страт": ST_FILL}
for r in range(2, tr):
    for c in range(1, 24):
        cell = ws.cell(row=r, column=c); cell.border = BORDER
        if c in (3, 4, 5, 6, 7, 8, 9, 21, 22): cell.fill = EDIT_FILL
        elif c >= 10: cell.fill = CALC_FILL
        if c == 2: cell.fill = wave_fill[ws.cell(row=r, column=2).value]
        if c in (3, 4, 5, 8, 10, 11, 12, 13, 14, 15, 18, 19, 20): cell.number_format = "0.00"
        if c in (6, 9, 16, 17): cell.number_format = "0.0%"
        if c == 7: cell.number_format = "0.00"
        if c == 23: cell.number_format = "# ##0"
ws.cell(row=tr, column=23).number_format = "# ##0"
widths = [22, 6, 8, 7, 7, 7, 11, 9, 9, 8, 9, 8, 9, 9, 11, 8, 8, 10, 10, 10, 9, 9, 11]
for i, w in enumerate(widths, 1): ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "C2"

M = "'Модель SKU'"

# ============ Лист 3: Сценарии ============
ws = wb.create_sheet("Сценарии")
ws.append(["SKU", "Сценарий", "Цена ×", "FOB ×", "PPC %", "Цена €", "FOB $", "Landed €",
           "Прибыль €/шт", "Маржа %", "Прибыль €/мес (цель шт)"])
style_header(ws, 1, 11)
scen = [("Пессимист: демпинг −10% цены, FOB +20%, PPC 15%", 0.90, 1.20, 0.15),
        ("База (= лист Модель)", 1.00, 1.00, None),
        ("Оптимист: цена база, FOB −10%, PPC 8%", 1.00, 0.90, 0.08)]
r_out = 2
for i in range(len(SKUS)):
    src = i + 2
    for name, pm, fm, ppc in scen:
        ppc_formula = f"={M}!F{src}" if ppc is None else ppc
        ws.append([f"={M}!A{src}", name, pm, fm, ppc_formula,
            f"={M}!C{src}*C{r_out}",
            f"={M}!G{src}*D{r_out}",
            f"=G{r_out}*{FX}*(1+{M}!I{src}+{QC})+{M}!H{src}+{PREP}",
            f"=F{r_out}/(1+{VAT})-F{r_out}*{REF}-{M}!D{src}-{M}!E{src}-F{r_out}*E{r_out}-F{r_out}*{RET}-H{r_out}",
            f"=I{r_out}/F{r_out}",
            f"=I{r_out}*{M}!V{src}"])
        r_out += 1
for r in range(2, r_out):
    for c in range(1, 12):
        cell = ws.cell(row=r, column=c); cell.border = BORDER
        if c in (3, 4, 5): cell.fill = EDIT_FILL
        elif c >= 6: cell.fill = CALC_FILL
        if c in (6, 7, 8, 9): cell.number_format = "0.00"
        if c == 10: cell.number_format = "0.0%"
        if c == 5: cell.number_format = "0.0%"
        if c == 11: cell.number_format = "# ##0"
    if (r - 2) % 3 == 0:
        ws.cell(row=r, column=2).font = Font(color=BAD, size=9)
    elif (r - 2) % 3 == 2:
        ws.cell(row=r, column=2).font = Font(color=GOOD, size=9)
for i, w in enumerate([22, 38, 7, 7, 8, 9, 9, 9, 11, 9, 13], 1):
    ws.column_dimensions[get_column_letter(i)].width = w
ws.freeze_panes = "A2"

# ============ Лист 4: P&L пилота ============
ws = wb.create_sheet("P&L пилота")
ws.append(["SKU", "Волна", "Партия, шт", "FOB $ итого", "Landed € итого (инвестиция в товар)",
           "Продано за 90 дней (разгон), шт", "Выручка 90д €", "Прибыль 90д €",
           "Возврат инвестиции за 90д, %", "Остаток стока, шт"])
style_header(ws, 1, 10)
for i in range(len(SKUS)):
    src = i + 2; r = i + 2
    ws.append([f"={M}!A{src}", f"={M}!B{src}", f"={M}!U{src}",
        f"={M}!G{src}*C{r}",
        f"={M}!N{src}*C{r}",
        f"=MIN(C{r},ROUND({M}!V{src}*3*{RAMP},0))",
        f"={M}!C{src}*F{r}",
        f"={M}!O{src}*F{r}",
        f"=H{r}/E{r}",
        f"=C{r}-F{r}"])
tr = len(SKUS) + 2
ws.append(["ИТОГО", "", f"=SUM(C2:C{tr-1})", f"=SUM(D2:D{tr-1})", f"=SUM(E2:E{tr-1})",
           f"=SUM(F2:F{tr-1})", f"=SUM(G2:G{tr-1})", f"=SUM(H2:H{tr-1})", f"=H{tr}/E{tr}", f"=SUM(J2:J{tr-1})"])
for r in range(2, tr + 1):
    for c in range(1, 11):
        cell = ws.cell(row=r, column=c); cell.border = BORDER
        if r == tr: cell.font = BOLD; cell.fill = HDR_FILL
        elif c >= 3: cell.fill = CALC_FILL
        if c in (4, 5, 7, 8): cell.number_format = "# ##0"
        if c == 9: cell.number_format = "0%"
for i, w in enumerate([22, 6, 9, 11, 15, 13, 11, 11, 12, 10], 1):
    ws.column_dimensions[get_column_letter(i)].width = w

# ============ Лист 5: Cash-flow (план) ============
ws = wb.create_sheet("Cash-flow план")
months = ["Июл 26", "Авг 26", "Сен 26", "Окт 26", "Ноя 26", "Дек 26",
          "Янв 27", "Фев 27", "Мар 27", "Апр 27", "Май 27", "Июн 27"]
ws.append(["Статья (план, €)"] + months + ["Итого"])
style_header(ws, 1, 14)

# суммы: товар W1 ≈ 18,7k$ FOB → €17.2k; W2 8.3k$ → €7.6k; фрахт/пошл 7k; комплаенс 5.5k; PPC по выручке
rows = [
    ("Образцы + экспресс (все SKU)", {0: -1200}),
    ("Депозит 30% — Волна 1 + Страт", {0: -5160}),
    ("Баланс 70% — Волна 1 + Страт", {1: -12040}),
    ("Фрахт + пошлины + QC — Волна 1", {2: -5000}),
    ("Комплаенс (GPSR/LUCID/LFGB/OEKO/EUIPO)", {0: -3000, 1: -2500}),
    ("Депозит 30% — Волна 2", {4: -2290}),
    ("Баланс 70% — Волна 2", {6: -5340}),
    ("Фрахт + пошлины + QC — Волна 2", {7: -2000}),
    ("Реинвест в сток (повторные заказы, landed)", {2: -4000, 3: -7000, 4: -10000, 5: -12000,
     6: -14000, 7: -16000, 8: -18000, 9: -20000, 10: -21000, 11: -21000}),
    ("PPC (по выручке, разгон)", {3: -2100, 4: -3500, 5: -4900, 6: -5600, 7: -6300,
     8: -8400, 9: -9900, 10: -11100, 11: -11800}),
    ("Поступления от продаж (выручка − сборы Amazon)", {3: 10900, 4: 18100, 5: 25300,
     6: 29000, 7: 32600, 8: 42900, 9: 49500, 10: 56200, 11: 58400}),
]
r0 = 2
for name, vals in rows:
    row = [name] + [vals.get(i, 0) for i in range(12)]
    row.append(f"=SUM(B{r0}:M{r0})")
    ws.append(row); r0 += 1
net_r = r0
ws.append(["Чистый поток месяца"] + [f"=SUM({get_column_letter(c)}2:{get_column_letter(c)}{net_r-1})" for c in range(2, 14)] + [f"=SUM(B{net_r}:M{net_r})"])
cum_r = net_r + 1
cums = []
for c in range(2, 14):
    L = get_column_letter(c)
    cums.append(f"={L}{net_r}" if c == 2 else f"={get_column_letter(c-1)}{cum_r}+{L}{net_r}")
ws.append(["Кумулятивный поток"] + cums + [""])
for r in range(2, cum_r + 1):
    for c in range(1, 15):
        cell = ws.cell(row=r, column=c); cell.border = BORDER
        if c > 1: cell.number_format = "# ##0"
        if r >= net_r: cell.font = BOLD; cell.fill = HDR_FILL
ws.column_dimensions["A"].width = 40
for c in range(2, 15): ws.column_dimensions[get_column_letter(c)].width = 9
ws.append([]); ws.append(["План. Поступления = выручка − сборы Amazon (НДС/referral/FBA/возвраты); PPC и повторные закупки стока — отдельными строками. "
           "Разгон W1: окт 30% → мар 100% цели; W2: мар 30% → июн 100%. Кумулятив к июню 2027 ≈ +€78 тыс. — сходится с моделью прибыли. "
           "Пересчитать фактическими котировками после RFQ."])
ws.cell(row=cum_r + 2, column=1).font = Font(italic=True, size=9, color=MUTED)

out = "/home/user/Keepa/deliverables/Amazon_EU_Financial_Model_2026-07.xlsx"
wb.save(out)
print("OK:", out)
