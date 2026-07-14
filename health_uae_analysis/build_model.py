#!/usr/bin/env python3
"""Генератор финансовой модели «Health Products: США → ОАЭ».

Создаёт XLSX с ЖИВЫМИ формулами (не предрасчитанными значениями): меняешь
жёлтые ячейки-входы — весь расчёт пересчитывается автоматически в Excel/Google
Sheets. Методология по ТЗ:
  1) берём реальные продажи товара в США (Keepa),
  2) масштабируем на ОАЭ понижающим коэффициентом (по умолчанию ÷40),
  3) считаем, сколько юнитов надо продавать, чтобы выйти на целевую прибыль,
  4) проверяем, влезаем ли мы в оценённый спрос ОАЭ.
"""
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import json, os

HERE = os.path.dirname(os.path.abspath(__file__))

# ---- стили -----------------------------------------------------------------
INPUT   = PatternFill("solid", fgColor="FFF2CC")   # жёлтый — сюда вводим данные
CALC    = PatternFill("solid", fgColor="E2EFDA")   # зелёный — считается формулой
HEAD    = PatternFill("solid", fgColor="1F4E78")
SUB     = PatternFill("solid", fgColor="D6E4F0")
OKF     = PatternFill("solid", fgColor="C6EFCE")
WARNF   = PatternFill("solid", fgColor="FFC7CE")
WHITE   = Font(color="FFFFFF", bold=True, size=12)
BOLD    = Font(bold=True)
TITLE   = Font(bold=True, size=14, color="1F4E78")
SMALL   = Font(size=9, italic=True, color="808080")
thin    = Side(style="thin", color="BFBFBF")
BORDER  = Border(left=thin, right=thin, top=thin, bottom=thin)

def style_row_head(ws, row, text, span=4):
    c = ws.cell(row=row, column=1, value=text)
    c.font = WHITE; c.fill = HEAD; c.alignment = Alignment(vertical="center")
    for col in range(2, span + 1):
        ws.cell(row=row, column=col).fill = HEAD

def inp(ws, row, label, value, note="", fmt=None):
    ws.cell(row=row, column=1, value=label).font = BOLD
    c = ws.cell(row=row, column=2, value=value); c.fill = INPUT; c.border = BORDER
    if fmt: c.number_format = fmt
    if note: ws.cell(row=row, column=3, value=note).font = SMALL
    return f"B{row}"

def calc(ws, row, label, formula, note="", fmt=None, fill=CALC):
    ws.cell(row=row, column=1, value=label).font = BOLD
    c = ws.cell(row=row, column=2, value=formula); c.fill = fill; c.border = BORDER
    if fmt: c.number_format = fmt
    if note: ws.cell(row=row, column=3, value=note).font = SMALL
    return f"B{row}"

AED = '#,##0.00" AED"'
PCT = '0.0%'
NUM = '#,##0'

wb = Workbook()

# ============================================================================
# ЛИСТ 1 — МОДЕЛЬ (калькулятор с формулами)
# ============================================================================
ws = wb.active
ws.title = "Модель"
ws.column_dimensions['A'].width = 42
ws.column_dimensions['B'].width = 16
ws.column_dimensions['C'].width = 60

ws.cell(row=1, column=1, value="ФИН-МОДЕЛЬ: Health Products — США → ОАЭ").font = TITLE
ws.cell(row=2, column=1, value="Жёлтые ячейки — вводишь свои данные. Зелёные — считаются сами.").font = SMALL

r = 4
style_row_head(ws, r, "1. КУРС И ЦЕЛЬ"); r += 1
usd = inp(ws, r, "Курс USD → AED", 3.6725, "дирхам привязан к доллару (~3.6725)", '0.0000'); r += 1
tgt_profit = inp(ws, r, "Целевая ЧИСТАЯ прибыль, AED/мес", 3500, "«на руки» — из ТЗ ≈ 3 500 AED", AED); r += 1
tgt_rev    = inp(ws, r, "Целевой ОБОРОТ, AED/мес (альтерн. цель)", 10000, "из ТЗ — 10 000 AED выручки", AED); r += 1

r += 1
style_row_head(ws, r, "2. ЮНИТ-ЭКОНОМИКА (на 1 шт, в AED)"); r += 1
price = inp(ws, r, "Цена продажи на amazon.ae / noon, AED", 150, "розничная цена за 1 шт", AED); r += 1
cogs  = inp(ws, r, "Себестоимость landed (завод+логистика в ОАЭ), AED", 40, "закупка + доставка + растаможка на 1 шт", AED); r += 1
ref_p = inp(ws, r, "Реферальная комиссия Amazon, %", 0.15, "Health/Beauty на amazon.ae ≈ 8–15%", PCT); r += 1
fba   = inp(ws, r, "Фулфилмент FBA, AED/шт", 15, "pick&pack + вес; лёгкий товар дешевле", AED); r += 1
ppc   = inp(ws, r, "Реклама PPC, AED/шт", 15, "бюджет продвижения на 1 проданную шт", AED); r += 1
ret_p = inp(ws, r, "Возвраты + прочее, % от цены", 0.03, "брак, возвраты, упаковка", PCT); r += 1
vat_p = inp(ws, r, "НДС (VAT) ОАЭ, %", 0.05, "5% — собирается сверху и перечисляется, в прибыль НЕ идёт", PCT); r += 1

# расчёт юнит-экономики
ref_fee  = calc(ws, r, "  → Реферальная комиссия, AED", f"={price}*{ref_p}", "", AED); r += 1
ret_cost = calc(ws, r, "  → Возвраты/прочее, AED", f"={price}*{ret_p}", "", AED); r += 1
gp_unit  = calc(ws, r, "  → ВАЛОВАЯ прибыль с 1 шт, AED",
                f"={price}-{cogs}-{ref_fee}-{fba}-{ppc}-{ret_cost}",
                "цена минус все переменные затраты (без НДС)", AED); r += 1
margin   = calc(ws, r, "  → Маржа, % от цены", f"={gp_unit}/{price}",
                "цель по ТЗ: ≥ 30%", PCT); r += 1
margin_flag = calc(ws, r, "  → Проверка маржи (≥30%?)",
                f'=IF({margin}>=0.3,"✅ OK (≥30%)","⚠️ ниже 30% — поднять цену / снизить COGS")', ""); r += 1

r += 1
style_row_head(ws, r, "3. СКОЛЬКО ПРОДАВАТЬ (расчёт объёма)"); r += 1
fixed = inp(ws, r, "Фикс. расходы, AED/мес", 300, "хранение, подписка seller, сервисы", AED); r += 1
units_profit = calc(ws, r, "Юнитов/мес для целевой ПРИБЫЛИ",
                f"=ROUNDUP(({tgt_profit}+{fixed})/{gp_unit},0)",
                "= (цель прибыли + фикс) / валовая прибыль с шт", NUM); r += 1
rev_at_profit = calc(ws, r, "  → Оборот при этом объёме, AED/мес",
                f"={units_profit}*{price}", "", AED); r += 1
units_rev = calc(ws, r, "Юнитов/мес для целевого ОБОРОТА",
                f"=ROUNDUP({tgt_rev}/{price},0)", "= целевой оборот / цена", NUM); r += 1
profit_at_rev = calc(ws, r, "  → Чистая прибыль при этом обороте, AED/мес",
                f"={units_rev}*{gp_unit}-{fixed}", "", AED); r += 1

r += 1
style_row_head(ws, r, "4. ПРОВЕРКА СПРОСА: США → ОАЭ (÷ коэффициент)"); r += 1
us_units = inp(ws, r, "Продажи в США, шт/мес (из Keepa)", 10000, "monthly_sold конкретного товара/ниши", NUM); r += 1
factor   = inp(ws, r, "Понижающий коэффициент США→ОАЭ", 40, "из ТЗ: 2000 в США → 50 в ОАЭ = ÷40", NUM); r += 1
uae_dem  = calc(ws, r, "  → Оценка спроса ОАЭ, шт/мес (весь рынок)",
                f"=ROUND({us_units}/{factor},0)", "весь объём ниши в ОАЭ, не наш", NUM); r += 1
share    = calc(ws, r, "  → Наша доля рынка для цели по прибыли",
                f"={units_profit}/{uae_dem}", "какую долю ниши надо взять", PCT); r += 1
feas     = calc(ws, r, "  → ВЕРДИКТ по реалистичности",
                f'=IF({units_profit}<={uae_dem}*0.3,"✅ РЕАЛЬНО (нужно ≤30% ниши)",'
                f'IF({units_profit}<={uae_dem},"⚠️ НАПРЯЖНО (нужна большая доля ниши)",'
                f'"❌ НЕ ВЛЕЗАЕМ (спрос ОАЭ меньше цели)"))', ""); r += 1

r += 1
style_row_head(ws, r, "5. ЗАКУПКА (первая партия)"); r += 1
cover = inp(ws, r, "На сколько месяцев берём запас", 2, "1-я партия обычно на 1.5–2.5 мес", NUM); r += 1
order_units = calc(ws, r, "Юнитов заказать (по цели прибыли)",
                f"=ROUNDUP({units_profit}*{cover},0)", "", NUM); r += 1
capital = calc(ws, r, "Капитал на партию, AED",
                f"={order_units}*{cogs}", "= юнитов × себестоимость", AED); r += 1
capital_usd = calc(ws, r, "  → то же в USD", f"={capital}/{usd}", "", '#,##0" $"'); r += 1
payback = calc(ws, r, "Окупаемость партии, мес",
                f"={capital}/({units_profit}*{gp_unit})", "капитал / валовая прибыль в мес", '0.0'); r += 1

# заметка-итог
r += 2
note = ws.cell(row=r, column=1,
    value="Как читать: заполни жёлтые ячейки (цена, себестоимость, продажи в США, коэффициент). "
          "Строка «Юнитов/мес для целевой ПРИБЫЛИ» и «ВЕРДИКТ по реалистичности» — главный ответ. "
          "Если вердикт ❌/⚠️ — снижай цель, поднимай цену/маржу или бери коэффициент реалистичнее.")
note.font = Font(italic=True, color="C00000"); note.alignment = Alignment(wrap_text=True, vertical="top")
ws.merge_cells(start_row=r, start_column=1, end_row=r+2, end_column=3)

# запомним адреса для листа сценариев
ADDR = dict(price=price, cogs=cogs, ref_p=ref_p, fba=fba, ppc=ppc, ret_p=ret_p,
            gp_unit=gp_unit, tgt_profit=tgt_profit, fixed=fixed, factor=factor)

# ============================================================================
# ЛИСТ 2 — СЦЕНАРИИ (чувствительность)
# ============================================================================
ws2 = wb.create_sheet("Сценарии")
ws2.column_dimensions['A'].width = 34
for col in "BCDEFG":
    ws2.column_dimensions[col].width = 14

ws2.cell(row=1, column=1, value="СЦЕНАРИИ — сколько юнитов/мес нужно для цели по прибыли").font = TITLE
ws2.cell(row=2, column=1, value="Все формулы тянут вход с листа «Модель». Меняешь там — тут пересчитывается.").font = SMALL

# A) чувствительность по цене и марже
r2 = 4
style_row_head(ws2, r2, "A. Юнитов/мес для цели по прибыли — при разной цене и марже", span=7); r2 += 1
ws2.cell(row=r2, column=1, value="Цена, AED \\ Маржа →").font = BOLD
margins = [0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
for j, mg in enumerate(margins):
    c = ws2.cell(row=r2, column=2+j, value=mg); c.number_format = PCT; c.font = BOLD; c.fill = SUB
r2 += 1
prices = [50, 70, 90, 120, 150, 200]
first_data_row = r2
for pr in prices:
    ws2.cell(row=r2, column=1, value=pr).number_format = AED
    ws2.cell(row=r2, column=1).font = BOLD
    for j, mg in enumerate(margins):
        # юнитов = (цель прибыли + фикс) / (цена * маржа)
        f = (f"=ROUNDUP((Модель!{ADDR['tgt_profit']}+Модель!{ADDR['fixed']})"
             f"/({get_column_letter(1)}{r2}*{ws2.cell(row=first_data_row-1, column=2+j).coordinate}),0)")
        c = ws2.cell(row=r2, column=2+j, value=f)
        c.number_format = NUM; c.border = BORDER
    r2 += 1

# B) чувствительность спроса ОАЭ по коэффициенту
r2 += 2
style_row_head(ws2, r2, "B. Оценка спроса ОАЭ (шт/мес) при разных продажах в США и коэффициенте", span=7); r2 += 1
ws2.cell(row=r2, column=1, value="Продажи США, шт/мес \\ ÷K →").font = BOLD
factors = [20, 30, 40, 60, 80, 100]
for j, fc in enumerate(factors):
    c = ws2.cell(row=r2, column=2+j, value=fc); c.font = BOLD; c.fill = SUB; c.number_format = '"÷"0'
r2 += 1
us_vols = [1000, 2000, 3000, 5000, 8000, 10000]
fr = r2
for uv in us_vols:
    ws2.cell(row=r2, column=1, value=uv).number_format = NUM
    ws2.cell(row=r2, column=1).font = BOLD
    for j, fc in enumerate(factors):
        f = f"=ROUND(A{r2}/{ws2.cell(row=fr-1, column=2+j).coordinate},0)"
        c = ws2.cell(row=r2, column=2+j, value=f)
        c.number_format = NUM; c.border = BORDER
    r2 += 1
ws2.cell(row=r2+1, column=1,
    value="Сравни числа из таблицы B (спрос всей ниши в ОАЭ) с «Юнитов/мес для прибыли» "
          "из таблицы A. Если нужное число юнитов больше спроса ниши — цель нереальна.").font = SMALL

# ============================================================================
# ЛИСТ 3 — КАНДИДАТЫ (реальные данные Keepa, США)
# ============================================================================
ws3 = wb.create_sheet("Кандидаты US→ОАЭ")
cols = ["Ниша", "Пример (бренд)", "ASIN", "Цена US, $", "Цена US, AED",
        "Продажи US, шт/мес", "Оценка ОАЭ ÷40, шт/мес", "Отзывы", "Офферов",
        "Проглатывается? (регистрация DM)", "Барьер входа", "Комментарий"]
widths = [22, 20, 13, 11, 12, 16, 18, 9, 8, 26, 16, 46]
for i, (cn, w) in enumerate(zip(cols, widths), start=1):
    c = ws3.cell(row=1, column=i, value=cn); c.font = WHITE; c.fill = HEAD
    c.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    ws3.column_dimensions[get_column_letter(i)].width = w
ws3.row_dimensions[1].height = 44

# curated по итогам поиска Keepa (Health & Household, cat 3760901)
CANDS = [
 # ниша, бренд, asin, price_usd, us_units, reviews, offers, ingestible, barrier, comment
 ("Магний глицинат", "dilib", "B0C2YCK25S", 18.99, 3000, 956, 1, "ДА — рег. Dubai Munic.", "Средний",
  "Тренд-добавка, мелкий бренд растёт, лёгкий вес. Нужна регистрация БАД."),
 ("Бандаж запястья/карпал", "FREETOO", "B0DNFTL63F", 19.95, 3000, 5704, 1, "нет", "Низкий",
  "★ Не проглатывается — регистрация НЕ нужна. Лёгкий, private-label легко."),
 ("Аптечка / First Aid Kit", "First Aid Only", "B08P27LHJ4", 20.95, 10000, 5658, 1, "нет", "Низкий",
  "★ Высокий спрос, не БАД. Габарит больше — считай FBA."),
 ("Отбеливание зубов (гель)", "Opalescence", "B000MMYI8G", 28.98, 10000, 3439, 1, "косметика (проще БАД)", "Средний",
  "Косметика для рта — регистрация легче, чем БАД. Высокий спрос."),
 ("Зубная паста гидроксиапатит", "Himalaya", "B0C4MMPCQH", 19.59, 1000, 3699, 1, "косметика", "Средний",
  "Fluoride-free тренд. Оральная косметика."),
 ("Поддержка печени (БАД)", "Hepagard", "B089C71Q18", 39.95, 10000, 3982, 2, "ДА — рег. + мед.claims", "Высокий",
  "Высокий чек и спрос, НО мед-заявления + регистрация БАД = риск."),
 ("Креатин моногидрат", "Jocko Fuel", "B0BT23VBLJ", 39.99, 10000, 2073, 1, "ДА — спорт-БАД", "Высокий",
  "Спортпит популярен в ОАЭ, но рынок занят брендами + регистрация."),
 ("Пробиотик / метаболизм", "O Positiv URO", "B0FT77GQCX", 28.97, 10000, 748, 1, "ДА — рег. БАД", "Высокий",
  "Мало отзывов = свежий, но женское здоровье + мед-claims."),
 ("Тест/буст тестостерона", "Nugenix", "B0D1VZXCY9", 34.99, 3000, 5095, 1, "ДА — рег. + мед.claims", "Высокий",
  "Высокий чек, но гормональные заявления — регуляторный риск в ОАЭ."),
 ("Органические прокладки", "Honey Pot", "B0DCDPBZX2", 22.99, 2000, 1366, 2, "нет (гигиена)", "Низкий",
  "★ Не БАД. Женская гигиена, органик-ниша, растёт."),
 ("Предтрен (pre-workout)", "GHOST", "B0D9NFTNQL", 44.99, 2000, 1924, 1, "ДА — спорт-БАД", "Высокий",
  "Высокий чек, но бренд-война + регистрация."),
 ("Гидратация (electrolyte mix)", "Waterboy", "B0F63MYH3Z", 24.99, 3000, 286, 1, "ДА — рег. БАД", "Средний",
  "286 отзывов = очень свежий, категория горячая (Liquid I.V./LMNT сверху)."),
]
USD_AED = 3.6725
row = 2
for (niche, brand, asin, pu, us, rev, off, ing, bar, com) in CANDS:
    ws3.cell(row=row, column=1, value=niche)
    ws3.cell(row=row, column=2, value=brand)
    ws3.cell(row=row, column=3, value=asin)
    ws3.cell(row=row, column=4, value=pu).number_format = '#,##0.00" $"'
    ws3.cell(row=row, column=5, value=f"=D{row}*3.6725").number_format = AED
    ws3.cell(row=row, column=6, value=us).number_format = NUM
    ws3.cell(row=row, column=7, value=f"=ROUND(F{row}/40,0)").number_format = NUM
    ws3.cell(row=row, column=8, value=rev).number_format = NUM
    ws3.cell(row=row, column=9, value=off)
    ws3.cell(row=row, column=10, value=ing)
    bcell = ws3.cell(row=row, column=11, value=bar)
    bcell.fill = OKF if bar == "Низкий" else (WARNF if bar == "Высокий" else PatternFill("solid", fgColor="FFEB9C"))
    ws3.cell(row=row, column=12, value=com).alignment = Alignment(wrap_text=True, vertical="top")
    for cc in range(1, 13):
        ws3.cell(row=row, column=cc).border = BORDER
    row += 1
ws3.cell(row=row+1, column=1,
    value="★ = приоритет для НОВОГО продавца: спрос есть, вход дешевле, БЕЗ регистрации БАД. "
          "«Оценка ОАЭ ÷40» — по коэффициенту из ТЗ; на листе «Сценарии» (табл. B) можно взять другой.").font = SMALL

# ============================================================================
# ЛИСТ 4 — ИНСТРУКЦИЯ / ДОПУЩЕНИЯ
# ============================================================================
ws4 = wb.create_sheet("Инструкция")
ws4.column_dimensions['A'].width = 110
lines = [
 ("ИНСТРУКЦИЯ И ДОПУЩЕНИЯ", TITLE),
 ("", None),
 ("КАК ПОЛЬЗОВАТЬСЯ", BOLD),
 ("1. Открой лист «Модель». Заполни ЖЁЛТЫЕ ячейки: цена, себестоимость landed, комиссии, реклама.", None),
 ("2. Внизу впиши «Продажи в США, шт/мес» (из Keepa по конкретному товару) и коэффициент США→ОАЭ.", None),
 ("3. Смотри ответы: «Юнитов/мес для целевой прибыли», «ВЕРДИКТ по реалистичности», «Капитал на партию».", None),
 ("4. Лист «Сценарии» — таблицы чувствительности (цена×маржа и продажи США×коэффициент).", None),
 ("5. Лист «Кандидаты US→ОАЭ» — реальные товары из Keepa с оценкой спроса ОАЭ и барьером входа.", None),
 ("", None),
 ("МЕТОДОЛОГИЯ (по ТЗ)", BOLD),
 ("• Шаг 1 — проверяем товар в США (Keepa даёт реальные monthly_sold, рейтинг, конкуренцию).", None),
 ("• Шаг 2 — ОАЭ = основной рынок, но объём меньше: масштабируем ÷K (в ТЗ пример 2000→50, т.е. ÷40).", None),
 ("• Шаг 3 — считаем юнит-экономику и сколько штук нужно продать для цели 10 000 AED / 3 500 AED прибыли.", None),
 ("• Шаг 4 — маржа от 30%: модель подсвечивает, добита ли планка 30%.", None),
 ("", None),
 ("ВАЖНО ПРО КОЭФФИЦИЕНТ ÷40", BOLD),
 ("• Совокупно amazon.com (~$847 млрд/год) больше amazon.ae (~$770 млн/год) примерно в ~1000 раз.", None),
 ("• Но по КОНКРЕТНОЙ трендовой нише разрыв меньше: ÷40 — оптимистично, реалистичный диапазон ÷40…÷100.", None),
 ("• Поэтому коэффициент — ВХОД модели: прогони пессимистичный (÷80) и оптимистичный (÷40) сценарии.", None),
 ("• В ОАЭ спрос на здоровье растёт: поиск «collagen» +5200%, «vitamin C» +4200% (данные рынка).", None),
 ("", None),
 ("РЕГУЛЯТОРНЫЙ БАРЬЕР — КЛЮЧЕВОЕ ДЛЯ ВЫБОРА ТОВАРА", BOLD),
 ("• БАД/добавки (магний, печень, тестостерон, пробиотики, спортпит) = обязательная регистрация в", None),
 ("  Dubai Municipality (Montaji): нужен трейд-лайсенс + локальное юрлицо/склад, COA, GMP, халяль,", None),
 ("  этикетки на арабском+английском. Срок 20–30 раб.дней. Штраф за незарегистрированный товар 10–50 тыс. AED.", None),
 ("• НЕ проглатываемые товары (бандажи, аптечки, гигиена, косметика для рта) — путь входа НАМНОГО легче.", None),
 ("• Вывод: новичку начинать с ★-товаров (FREETOO бандаж, First Aid, органик-гигиена), а БАД — когда", None),
 ("  готов пройти регистрацию.", None),
 ("", None),
 ("ДОПУЩЕНИЯ ПО УМОЛЧАНИЮ (меняй под себя)", BOLD),
 ("• Курс USD→AED = 3.6725 (жёсткая привязка дирхама).", None),
 ("• Реферальная комиссия Amazon.ae для Health/Beauty ≈ 8–15% (взял 15% консервативно).", None),
 ("• FBA fulfilment и фикс-расходы — ориентировочные; уточни в Seller Central ОАЭ под свой вес/габарит.", None),
 ("• НДС ОАЭ 5% — собирается сверху цены и перечисляется государству, в чистую прибыль НЕ входит.", None),
 ("• monthly_sold из Keepa округляется бакетами (500/1K/2K/…); это оценка «куплено за месяц», не точное число.", None),
 ("", None),
 ("ИСТОЧНИКИ ДАННЫХ", BOLD),
 ("• Keepa Product Finder, категория Health & Household (US, catId 3760901) — продажи/цены/конкуренция.", None),
 ("• Amazon global revenue (ecommerceDB/Statista) и amazon.ae sales — для оценки масштаба рынков.", None),
 ("• Dubai Municipality / MOHAP — требования к регистрации БАД (freyr, artixio, dm.gov.ae).", None),
]
rr = 1
for text, font in lines:
    c = ws4.cell(row=rr, column=1, value=text)
    if font: c.font = font
    rr += 1

# freeze headers
ws.freeze_panes = "A4"
ws3.freeze_panes = "A2"

out = os.path.join(HERE, "Health_UAE_FinModel.xlsx")
wb.save(out)
print("saved:", out)
