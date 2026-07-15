#!/usr/bin/env python3
"""Собирает Word-отчёт (.docx) «Health Products: США → ОАЭ».

Не парсит markdown, а строит документ программно — так контроль над стилями,
таблицами и цветами полный. Данные держим здесь же, чтобы docx и xlsx были
из одного источника правды.
"""
import os
from docx import Document
from docx.shared import Pt, RGBColor, Cm, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

HERE = os.path.dirname(os.path.abspath(__file__))
NAVY = RGBColor(0x1F, 0x4E, 0x78)
GREY = RGBColor(0x80, 0x80, 0x80)
RED  = RGBColor(0xC0, 0x00, 0x00)
GREEN_FILL = "C6EFCE"; RED_FILL = "FFC7CE"; AMBER_FILL = "FFEB9C"; HEAD_FILL = "1F4E78"; SUB_FILL = "D6E4F0"

doc = Document()

# базовый шрифт
style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)

def shade(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd"); sh.set(qn("w:val"), "clear"); sh.set(qn("w:fill"), hexcolor)
    tcPr.append(sh)

def set_cell_text(cell, text, bold=False, color=None, white=False, size=9.5, align="left"):
    cell.text = ""
    p = cell.paragraphs[0]
    p.alignment = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER,
                   "right": WD_ALIGN_PARAGRAPH.RIGHT}[align]
    run = p.add_run(str(text))
    run.bold = bold; run.font.size = Pt(size)
    if white: run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    elif color is not None: run.font.color.rgb = color

def add_hyperlink(paragraph, url, text, color="0563C1", size=9):
    part = paragraph.part
    r_id = part.relate_to(
        url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink",
        is_external=True)
    link = OxmlElement("w:hyperlink"); link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r"); rPr = OxmlElement("w:rPr")
    col = OxmlElement("w:color"); col.set(qn("w:val"), color); rPr.append(col)
    u = OxmlElement("w:u"); u.set(qn("w:val"), "single"); rPr.append(u)
    sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); rPr.append(sz)
    run.append(rPr)
    t = OxmlElement("w:t"); t.text = text; run.append(t)
    link.append(run); paragraph._p.append(link)

def set_cell_link(cell, url, text, size=9):
    cell.text = ""
    add_hyperlink(cell.paragraphs[0], url, text, size=size)

def h1(text):
    p = doc.add_paragraph(); r = p.add_run(text)
    r.bold = True; r.font.size = Pt(15); r.font.color.rgb = NAVY
    p.space_before = Pt(10)

def h2(text):
    p = doc.add_paragraph(); r = p.add_run(text)
    r.bold = True; r.font.size = Pt(12.5); r.font.color.rgb = NAVY

def para(text, italic=False, color=None, size=10.5, bold=False):
    p = doc.add_paragraph(); r = p.add_run(text)
    r.italic = italic; r.bold = bold; r.font.size = Pt(size)
    if color is not None: r.font.color.rgb = color
    return p

def bullet(text, bold_prefix=None):
    p = doc.add_paragraph(style="List Bullet")
    if bold_prefix:
        r = p.add_run(bold_prefix); r.bold = True
    p.add_run(text)

def numbered(text):
    doc.add_paragraph(text, style="List Number")

def table(headers, rows, widths=None, verdict_col=None, barrier_col=None,
          link_col=None, link_url=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"; t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, htext in enumerate(headers):
        set_cell_text(t.rows[0].cells[i], htext, bold=True, white=True, size=9, align="center")
        shade(t.rows[0].cells[i], HEAD_FILL)
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            if link_col is not None and i == link_col and link_url:
                set_cell_link(cells[i], link_url(str(val)), str(val))
                continue
            set_cell_text(cells[i], val, size=9)
            v = str(val)
            if barrier_col is not None and i == barrier_col:
                if "Низкий" in v or "🟢" in v: shade(cells[i], GREEN_FILL)
                elif "Высокий" in v or "🔴" in v or "занято" in v: shade(cells[i], RED_FILL)
                elif "Средний" in v or "🟡" in v: shade(cells[i], AMBER_FILL)
            if verdict_col is not None and i == verdict_col:
                if "✅" in v: shade(cells[i], GREEN_FILL)
                elif "❌" in v: shade(cells[i], RED_FILL)
                elif "⚠️" in v: shade(cells[i], AMBER_FILL)
    if widths:
        for i, w in enumerate(widths):
            for r in t.rows:
                r.cells[i].width = Cm(w)
    return t

# ============================ ТИТУЛ ============================
title = doc.add_paragraph(); tr = title.add_run("Health Products: аналитика США → ОАЭ + финансовая модель")
tr.bold = True; tr.font.size = Pt(20); tr.font.color.rgb = NAVY
sub = doc.add_paragraph()
sr = sub.add_run("Категория Health & Household · без БАД · методология «проверь США → масштабируй на ОАЭ → посчитай объём»")
sr.italic = True; sr.font.size = Pt(11); sr.font.color.rgb = GREY
meta = doc.add_paragraph()
mr = meta.add_run("Дата: 2026-07-14   ·   Источник: Keepa Product Finder (US, catId 3760901) + веб-исследование рынка ОАЭ/GCC   ·   Файл-калькулятор: Health_UAE_FinModel.xlsx")
mr.font.size = Pt(9); mr.font.color.rgb = GREY
doc.add_paragraph()

# ============================ 1. Методология ============================
h1("1. Методология (по ТЗ)")
numbered("Проверяем товар в США — Keepa даёт реальные продажи (monthly_sold), рейтинг, конкуренцию, историю цен.")
numbered("ОАЭ — основной рынок, но меньше по объёму. Масштабируем спрос понижающим коэффициентом ÷K (в ТЗ: 2000 шт США → 50 шт ОАЭ = ÷40).")
numbered("Считаем объём под цель: сколько штук/мес продать, чтобы получать 10 000 AED оборота / ~3 500 AED чистыми в месяц.")
numbered("Маржа от 30% — модель подсвечивает, добита ли планка.")
numbered("Фин-модель с формулами — куда подставляешь свои данные (COGS, fees) и всё пересчитывается.")

para("Файл Health_UAE_FinModel.xlsx (5 листов, живые формулы):", bold=True)
bullet("— калькулятор одного товара: цель, юнит-экономика, объём, проверка спроса, закупка.", "Модель ")
bullet("— таблица по каждому товару: подставляешь COGS, комиссию, FBA, PPC, возвраты → маржа, юнитов для цели, спрос ОАЭ, вердикт.", "Юнит-экономика ")
bullet("— чувствительность: цена × маржа и продажи US × коэффициент.", "Сценарии ")
bullet("— реальные товары из Keepa (не БАД) + смежные ниши, подтверждённые рынком.", "Кандидаты US→ОАЭ ")
bullet("— методология, уровни регистрации в ОАЭ, источники.", "Инструкция ")

# ============================ 2. Топ США ============================
h1("2. Что в ТОПе США (высокий спрос, но вход тяжёлый)")
para("Топ по продажам Health & Household — бренд-локнутые расходники. Спрос огромный (80–100k шт/мес), но зайти новичку почти нельзя. Смотрим для понимания категорий-драйверов, а заходим в под-ниши.")
table(
    ["Товар", "Бренд", "Цена US", "Продажи US/мес", "Почему тяжело"],
    [
        ["Электролиты (саше)", "Liquid I.V. / LMNT", "$23–45", "10–50k", "Культовые бренды, реклама-стена"],
        ["Батарейки AA/AAA", "Amazon Basics", "$15–30", "30–100k", "Amazon сам держит нишу"],
        ["Туалетная бумага / полотенца", "Charmin / Bounty", "$17–44", "30–100k", "Габарит + бренд-война"],
        ["Flushable wipes", "DUDE / Cottonelle", "$16–34", "6–20k", "Занято, гонка цен"],
    ],
    widths=[4.5, 3.5, 2.2, 3, 5])

# ============================ 3. Куда влезем (без БАД) ============================
h1("3. Куда ВЛЕЗЕМ — БЕЗ БАД (только не-проглатываемые товары)")
para("По условию добавки/БАД исключены. Оставил физические не-проглатываемые health-товары с подтверждённым спросом, малым числом отзывов (свежие) и низкой конкуренцией.")
h2("Проверено в Keepa (ASIN — кликабельные ссылки на Amazon):")
table(
    ["Ниша", "Пример", "ASIN", "Цена US", "Продажи US/мес", "Отзывы", "Регистрация ОАЭ", "Барьер"],
    [
        ["★ Бандаж запястья / карпал-туннель", "FREETOO", "B0DNFTL63F", "$19.95", "3 000", "5 704", "нет (обычный товар)", "🟢 низкий"],
        ["★ Аптечка First Aid Kit", "First Aid Only", "B08P27LHJ4", "$20.95", "10 000", "5 658", "нет (набор)", "🟢 низкий"],
        ["★ Органические прокладки", "This is L.", "B0DR3BYKWC", "$22.99", "5 000", "1 091", "нет (гигиена)", "🟢 низкий"],
        ["Органич. гигиена", "Honey Pot", "B0DCDPBZX2", "$22.99", "2 000", "1 366", "нет (гигиена)", "🟢 низкий"],
        ["Отбеливание зубов (гель+каппа)", "Opalescence", "B000MMYI8G", "$28.98", "10 000", "3 439", "космет. рег.", "🟡 средний"],
        ["Зубная паста (гидроксиапатит)", "Himalaya", "B0C4MMPCQH", "$19.59", "1 000", "3 699", "космет. рег.", "🟡 средний"],
        ["Раневая повязка (Xeroform)", "Dr. Med", "B0BGXMXNRD", "$25.99", "1 000", "1 292", "мед.изделие (MOHAP)", "🔴 высокий"],
        ["Флашбл-салфетки", "DUDE Wipes", "B0GFFLR222", "$16.98", "9 000", "241k", "нет (гигиена)", "🔴 занято"],
    ],
    widths=[4.4, 2.6, 2.4, 1.6, 2.2, 1.6, 3, 1.9], barrier_col=7,
    link_col=2, link_url=lambda a: f"https://www.amazon.com/dp/{a}")
para("★ = приоритет для новичка. ASIN кликабельны (Amazon). Полная таблица с ссылками Amazon + Keepa — "
     "на листе «Кандидаты US→ОАЭ» в XLSX.", italic=True, color=GREY, size=9)

h2("Смежные не-БАД ниши — подтверждены рыночными данными:")
bullet("корректор осанки, наколенник/налокотник, компрессионные носки/рукава, люмбар-пояс, ортопедические стельки, кинезио-тейп, акупрессурный коврик, органайзер для таблеток — все 🟢 обычный товар;")
bullet("массаж-пистолет/ролик, электрогрелка — 🟡 электроника (сертификация G-mark).")

# ============================ 4. Масштабирование ============================
h1("4. Масштабирование США → ОАЭ: осторожно с ÷40")
bullet("Совокупно amazon.com (~$847 млрд/год) больше amazon.ae (~$770 млн/год) примерно в ~1000 раз — ÷40 из ТЗ оптимистичен для «среднего» товара.")
bullet("По конкретной трендовой нише разрыв меньше: реалистичный диапазон ÷40 … ÷100. Спрос на wellness в ОАЭ растёт.")
bullet("Практика: коэффициент — ВХОД модели. Прогоняй два сценария: оптимистичный ÷40 и пессимистичный ÷80 (лист «Сценарии», таблица B).")

# ============================ 5. Регуляторика ============================
h1("5. «Не БАД» ≠ «без регистрации» — уровни барьера в ОАЭ")
para("БАД мы убрали, но и среди не-проглатываемых товаров барьер разный. Это решает, какой товар брать первым:")
table(
    ["Уровень", "Товары", "Что нужно"],
    [
        ["🟢 Обычный товар", "бандажи, компрессия, стельки, органайзеры, корректор осанки, гигиена, аптечка-набор", "трейд-лайсенс + маркировка (ар/англ). Легче всего — сюда заходим"],
        ["🟡 Оральная косметика", "отбеливание зубов, паста", "регистрация косметики (легче БАД, но нужна)"],
        ["🟡 Электроника", "массаж-пистолет, электрогрелка, тонометр-девайс", "сертификация / G-mark на электронику"],
        ["🔴 Мед. изделия", "раневые повязки, TENS, глюкометры, тонометры как медприбор", "регистрация MOHAP"],
    ],
    widths=[3.2, 6.5, 6], barrier_col=0)
para("Для справки: БАД (которые мы НЕ берём) требовали бы регистрации в Dubai Municipality (Montaji) — юрлицо/склад, "
     "COA, GMP, халяль, 20–30 дней, штраф 10–50k AED.", italic=True, color=GREY, size=9)
para("Вывод: стартовать с 🟢-товаров (бандаж FREETOO, компрессия, органик-гигиена, стельки, органайзер). "
     "Косметику/электронику/мед.изделия — вторым шагом.", bold=True, color=RED)

# ============================ 6. Как работает модель ============================
h1("6. Как работает фин-модель (worked example)")
para("Дефолт в файле — жизнеспособный пример: премиум не-БАД товар (напр. бандаж-набор / аптечка премиум), US-бестселлер.")
table(
    ["Вход", "Значение", "Результат (формулы)", "Значение"],
    [
        ["Цена продажи (ОАЭ)", "150 AED", "Валовая прибыль с шт", "53 AED"],
        ["Себестоимость landed", "40 AED", "Маржа", "35.3% ✅ (≥30%)"],
        ["Комиссия 15% + FBA 15 + PPC 15 + возвр. 3%", "—", "Юнитов/мес для 3 500 AED прибыли", "72 шт"],
        ["Продажи в США", "10 000 шт/мес", "Оценка спроса ОАЭ", "250 шт/мес"],
        ["Коэффициент ÷", "40", "Наша доля ниши → вердикт", "28.8% → ✅ РЕАЛЬНО"],
        ["", "", "Капитал на партию (2 мес)", "5 760 AED (~$1 570), окуп. 1.5 мес"],
    ],
    widths=[5, 3, 5, 3.5])
para("Пример из ТЗ (2000 шт в США) при тех же условиях выходит ❌ нереальным: спрос ОАЭ = 50 шт/мес, "
     "а для цели нужно 72 шт → это 144% ниши. Модель это честно показывает.", bold=True)
para("Главный вывод по экономике: при ÷40 цель «3 500 AED чистыми» достижима только если (а) товар — US-бестселлер "
     "(≥6–10k шт/мес), либо (б) премиум-цена с прибылью ≥50 AED/шт. Дешёвые товары (<100 AED) под ÷40 цель не тянут — "
     "нужен либо мягче коэффициент (÷20–30), либо стек SKU.", color=RED)

h2("Лист «Юнит-экономика» — считаем по каждому товару (COGS, fees подставляемые)")
para("Каждая строка — товар, а столбцы Цена / COGS / Комиссия % / FBA / PPC / Возвраты % — жёлтые, редактируемые. "
     "Формулы сразу дают комиссию, переменные затраты, валовую прибыль/шт, маржу, юнитов/мес под цель, спрос ОАЭ и "
     "вердикт (✅/⚠️/❌). Цель прибыли, фикс и коэффициент тянутся с листа «Модель».")
para("Пример расчёта таблицы (цена = прямой пересчёт US×3.6725, COGS≈30%, комиссия 15%, FBA/PPC 12):", bold=True, size=9.5)
table(
    ["Товар", "Цена ОАЭ", "COGS", "Валовая приб/шт", "Маржа", "Юнитов для цели", "Спрос ОАЭ", "Вердикт"],
    [
        ["Бандаж FREETOO", "73 AED", "22", "14.1", "19.2%", "270", "75", "❌ стек SKU"],
        ["Аптечка First Aid", "77 AED", "23", "16.0", "20.8%", "238", "250", "⚠️ напряжно"],
        ["Отбеливание Opalescence", "106 AED", "32", "31.3", "29.4%", "122", "250", "⚠️ напряжно"],
        ["Отбеливание (премиум ×1.8)", "192 AED", "57", "75.6", "39.5%", "51", "250", "✅ реально"],
    ],
    widths=[4.2, 2, 1.5, 2.4, 1.8, 2.6, 2, 2.4], verdict_col=7)
para("Оранжевые строки в файле — ниши, подтверждённые рынком (осанка/компрессия/люмбар), но US-объём оценочный: "
     "уточни title-поиском в Keepa.", italic=True, color=GREY, size=9)

# ============================ 6.1 Рынок ОАЭ/GCC ============================
h1("6.1 Рынок ОАЭ/GCC — что подтверждают данные (не БАД)")
bullet("Рынок $1.46 млрд (2026), CAGR 8.7%; плохая осанка — топ-жалоба (удалёнка). Продаётся на noon.ae, лидер 46k+ отзывов.", "Корректор осанки — ")
bullet("OTC-рынок MEA $119 млн (2025) → $125 млн (2026), сконцентрирован в GCC (ОАЭ, КСА).", "Ортопедические ортезы — ")
bullet("вместе 33.9% рынка поддержки осанки. Лёгкие, дешёвые в логистике, частые повторные покупки.", "Компрессия + кинезио-тейп + люмбар-пояса — ")
bullet("4.2 млн активных онлайн-покупателей, рост GMV >22% г/г.", "Рынок ОАЭ в целом — ")

# ============================ 7. Рекомендации ============================
h1("7. Рекомендации (без БАД)")
numbered("Первый товар — 🟢 «обычный товар»: бандаж запястья (FREETOO-тип), компрессионные носки/рукава, органик-гигиена или ортопедические стельки. Спрос в США подтверждён, регистрация минимальная, логистика дешёвая.")
numbered("Целься в премиум-цену (120–200 AED) — только так юнит-экономика тянет цель при ÷40.")
numbered("Массажёры/электрогрелки/тонометры дают высокий чек, но это электроника/мед.изделия → сертификация G-mark / MOHAP. Заходить вторым шагом.")
numbered("Всегда считай два коэффициента (÷40 и ÷80) — не строй план на оптимистичном.")
numbered("Стек из 3–4 SKU одной ниши (напр. бандажи на разные суставы/размеры) надёжнее одного товара для выхода на 10 000 AED.")
numbered("Догрузи данные: по смежным нишам запусти title-поиск в Keepa и впиши реальные COGS/цены поставщика (Alibaba/1688).")

# ============================ 8. Выводы ============================
h1("8. Итоговые выводы")
numbered("Категория Health & Household в США рабочая, но топ занят брендами — заходим в под-ниши.")
numbered("Без БАД остаются сильные не-проглатываемые ниши: бандажи/ортезы, компрессия, аптечки, органик-гигиена, стельки, органайзеры (спрос 1–10k шт/мес, конкуренция 1–3 оффера).")
numbered("Регуляторика решает очередность: 🟢 обычные товары → 🟡 косметика/электроника → 🔴 мед.изделия. БАД — самый тяжёлый путь (исключён).")
numbered("Экономика жёстко зависит от ÷K: при ÷40 и дешёвом товаре маржа ~20%, цель не берётся одним SKU. Решения: премиум-цена, высокий US-объём или стек SKU.")
numbered("Инструмент готов: лист «Юнит-экономика» — подставляй свои COGS/fees по каждому товару и мгновенно видишь маржу и вердикт.")
numbered("Следующий шаг: подтвердить продажи смежных ниш через Keepa и вписать реальные COGS/цены поставщика — тогда вердикты станут боевыми.")

# ============================ Источники ============================
h1("Источники")
para("• Keepa Product Finder — категория Health & Household (US, catId 3760901).", size=9)
para("• amazon.ae / global revenue: ecommerceDB, Statista/ECDB.", size=9)
para("• Регистрация в ОАЭ: Freyr, Artixio, Dubai Municipality (Technical Guidelines for Health Supplements), MOHAP.", size=9)
para("• Рынок не-БАД ниш: Coherent Market Insights (posture corrector $1.46B, CAGR 8.7%), MarketDataForecast "
     "(MEA OTC Orthopedic Braces), noon.ae, Accio (Best sellers Amazon UAE 2026).", size=9)
para("Замечание: Keepa не покрывает marketplace ОАЭ (amazon.ae) — цифры по ОАЭ получены масштабированием US-данных "
     "и веб-исследованием рынка, а не прямым измерением. Для точной валидации спроса — Bright Data / Apify по региону AE "
     "или SP-API с seller-аккаунтом ОАЭ.", italic=True, color=GREY, size=9)

out = os.path.join(HERE, "Health_UAE_Report.docx")
doc.save(out)
print("saved:", out)
