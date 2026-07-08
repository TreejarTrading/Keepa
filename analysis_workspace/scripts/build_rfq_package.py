#!/usr/bin/env python3
"""RFQ-пакет: 9 писем фабрикам (EN) — .txt для Alibaba-чата + сводный DOCX."""
import os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.enum.text import WD_BREAK

OUT_DIR = "/home/user/Keepa/deliverables/RFQ"
os.makedirs(OUT_DIR, exist_ok=True)

COMMON_TERMS = """COMMERCIAL TERMS & QUOTE FORMAT
- Incoterms: FOB (state your port). Also quote DDP to Hamburg, Germany if available.
- Payment: Alibaba Trade Assurance, T/T 30% deposit / 70% before shipment.
- Please quote unit price (USD) at THREE volumes: trial qty / 2x / 4x (see quantities above).
- Include: production lead time (days), sample cost + express courier cost to Europe (DHL/FedEx),
  carton dimensions & gross weight per export carton, units per carton, HS code you export under.
- Quality: we will order pre-shipment inspection (SGS/QIMA). Defect allowance in PO: max 2%.
- Packaging: neutral or our-brand retail box (artwork supplied after sample approval).
  FBA-ready: FNSKU barcode label per unit (we supply files), export carton <= 23 kg,
  no third-party brand names/logos anywhere on product or packaging.
- Please reply within 7 days with the quote table filled.

ABOUT US
Treejar Trading — private-label seller on Amazon Europe (Germany, FBA). We launch trial orders
first and scale to repeat orders of 2-4x within 3-6 months for SKUs that perform.

Contact: David (Procurement) — reply via Alibaba TradeManager / e-mail in signature."""

RFQS = [
 dict(file="RFQ_01_Jura_compatible_water_filter",
      subject="RFQ: Jura-compatible coffee machine water filter with RFID chip, 6-pack (trial 500 packs)",
      body=f"""Dear Supplier,

We are sourcing a JURA-COMPATIBLE WATER FILTER CARTRIDGE for automatic coffee machines
(compatible with Jura Claris Smart: E8, E6, E60, E80, Z8, Z6, S8, S80, J6, D6, ENA8).

PRODUCT SPECIFICATION
- Replacement/compatible cartridge with RFID CHIP: machine must auto-detect the filter
  (intelligent recognition + auto reset, same behavior as original Claris Smart).
- Filtration: activated carbon (coconut shell, food grade) + ion-exchange resin; reduces
  chlorine, scale and heavy metals; BPA-free materials, food-contact safe.
- Capacity: ~65 L / 2 months per cartridge.
- Retail unit: 6-pack color box (our brand, artwork after samples).
- MUST provide: LFGB (or EU 10/2011) food-contact test report for drinking water contact;
  confirmation of NO patent/trademark conflicts for EU sales (compatible product, no Jura logo).

QUANTITIES
- Trial order: 500 x 6-packs (3,000 cartridges). Repeat tiers: 1,000 / 2,000 x 6-packs.
- Target FOB: <= 9.30 USD per 6-pack at trial volume. Please quote your best price.

SAMPLES
- 2-3 samples of the 6-pack needed first. Please quote sample cost + DHL to Europe and
  provide a VIDEO of the RFID auto-detection working on a Jura E8/E6 machine.

{COMMON_TERMS}"""),
 dict(file="RFQ_02_DeLonghi_DLSC002_compatible_filter",
      subject="RFQ: DeLonghi DLSC002-compatible water filter, 6-pack (trial 500 packs)",
      body=f"""Dear Supplier,

We are sourcing a DELONGHI DLSC002-COMPATIBLE WATER FILTER for coffee machines
(compatible with ECAM, ESAM, ETAM, BCO, EC680/EC800 series; also fits SER3017 / 5513292811).

PRODUCT SPECIFICATION
- Activated carbon softener cartridge, coconut-shell carbon, food-grade, BPA-free.
- Reduces chlorine, scale, copper, lead; preserves minerals; improved anti-particle mesh
  (no black carbon particles leaking).
- Retail unit: 6-pack color box (our brand). Optional: 6+2 promo pack — quote both.
- MUST provide: LFGB or EU 10/2011 food-contact test report.
- "Compatible with" wording only — no DeLonghi logo anywhere.

QUANTITIES
- Trial order: 500 x 6-packs (3,000 cartridges). Repeat tiers: 1,000 / 2,500 x 6-packs.
- Target FOB: <= 4.00 USD per 6-pack at trial volume (i.e. ~0.55-0.65 USD/cartridge).

SAMPLES
- 2-3 samples of the 6-pack + fit test video on a DeLonghi ECAM machine.

{COMMON_TERMS}"""),
 dict(file="RFQ_03_Cooler_bag_40L_collapsible",
      subject="RFQ: Collapsible insulated cooler bag 40L, leakproof (trial 500 pcs)",
      body=f"""Dear Supplier,

We are sourcing a LARGE COLLAPSIBLE COOLER BAG, 40 liters, for the German market.

PRODUCT SPECIFICATION
- Capacity 40 L (also quote 20 L and 33 L versions separately if available).
- Outer: 600D Oxford polyester; Inner liner: PEVA/food-grade, fully LEAKPROOF (welded seams).
- Insulation: high-density EPE foam >= 8 mm; cooling retention >= 12 hours (state your test).
- Heavy-duty SBS zippers (double), reinforced carry handles + detachable shoulder strap,
  side pockets, front pocket; collapsible/foldable flat for storage.
- Weight ~0.8-0.95 kg. Color: black + 1-2 fashion colors. Custom logo (embroidery or print).
- OEKO-TEX for fabric is a plus. Packaging: foldable in polybag + our-brand sleeve.

QUANTITIES
- Trial order: 500 pcs. Repeat tiers: 1,000 / 2,000 pcs.
- Target FOB: <= 4.10 USD/pc at trial volume for the 40 L size.

SAMPLES
- 2 samples (black) with your standard logo process; please state cooling-hours test method.

{COMMON_TERMS}"""),
 dict(file="RFQ_04_Linen_beeswax_bread_bags",
      subject="RFQ: Linen bread bags with beeswax lining, 2-pack XL (trial 500 packs)",
      body=f"""Dear Supplier,

We are sourcing REUSABLE LINEN BREAD BAGS WITH BEESWAX LINING for the German market.

PRODUCT SPECIFICATION
- Set of 2 XL bags, approx. 43 x 33 cm each, natural linen (or linen-cotton) outer,
  FOOD-GRADE BEESWAX lining inside (breathable, keeps bread fresh 5-7 days).
- Drawstring closure; natural/undyed look; washable in cold water.
- Optional add-on to quote: same set with 1 extra small bag (baguette size).
- Food-grade wax certificate; LFGB test report preferred (we can order it on the batch).
- Retail: kraft paper belly band or box, our brand.

QUANTITIES
- Trial order: 500 x 2-packs. Repeat tiers: 1,000 / 2,000 packs.
- Target FOB: <= 1.80 USD per 2-pack at trial volume.

SAMPLES
- 2-3 sample sets; please state wax weight (gsm) and origin.

{COMMON_TERMS}"""),
 dict(file="RFQ_05_TV_stand_mobile_cart",
      subject="RFQ: Mobile TV cart / floor stand 43-75 inch, height adjustable (trial 200 pcs) — price improvement",
      body=f"""Dear Supplier,

We are sourcing a MOBILE TV CART (rolling floor stand) for 43-75 inch TVs for Amazon Germany.
We already hold a quotation at 29.70 USD EXW for this class — we invite you to beat it.

PRODUCT SPECIFICATION
- Fits 43-75" flat/curved TVs, load capacity >= 60 kg (state honest tested load).
- VESA up to 600x400; height adjustable (min. 5 levels or gas-assist); cable management.
- Heavy-gauge steel columns + base, black powder coating; lockable casters (2+ with brakes);
  optional middle AV shelf + top camera shelf (quote with and without).
- Certifications: EN/GS-type stability test report or willingness to pass one; tip-over warning
  label; knock-down packing with corner protectors, double-wall carton (drop-test safe).
- FBA-ready packaging <= 23 kg per carton if possible (or state actual).

QUANTITIES
- Trial order: 200 pcs. Repeat tiers: 400 / 800 pcs.
- Target: <= 28.30 USD FOB at 200 pcs (we hold 29.70 EXW). Also quote your 50-90"/100 kg model.

SAMPLES
- 1 sample + load test video; state carton dims/weight for freight calc.

{COMMON_TERMS}"""),
 dict(file="RFQ_06_Filing_cabinet_ZY3_4drawer",
      subject="RFQ: 4-drawer vertical steel filing cabinet A4 (trial 40 pcs) — price improvement vs PI",
      body=f"""Dear Supplier,

We are sourcing a 4-DRAWER VERTICAL STEEL FILING CABINET (A4 hanging files) for Amazon Germany.
We hold a PI at 45.00 USD EXW (1330x620x460 mm, steel 0.6/0.7 mm) — we invite you to beat it.

PRODUCT SPECIFICATION
- Approx. 1330 x 460 x 620 mm (H x W x D), 4 drawers for A4 hanging files.
- Steel body >= 0.6 mm, drawer fronts >= 0.7 mm; full-extension ball-bearing slides;
  central lock (2 keys); ANTI-TILT mechanism (only one drawer opens at a time) — mandatory.
- Color RAL 7035 light grey (+ black option). Knock-down or welded — quote both if available.
- Packaging: corner protectors + foam on all faces, double-wall carton (this is the #1
  complaint driver in this niche — packaging quality is a hard requirement).
- EN 14073 stability compliance or test willingness; tip-over warning label.

QUANTITIES
- Trial order: 40 pcs. Repeat tiers: 80 / 160 pcs.
- Target: 38-40 USD FOB at 40 pcs (we hold PI 45.00 EXW at 20 pcs).

SAMPLES
- 1 sample (or factory video + detailed QC photos of welds, slides, lock, packaging).

{COMMON_TERMS}"""),
 dict(file="RFQ_07_Cherry_pitter_table_top",
      subject="RFQ: Table-top cherry pitter with splash guard (trial 500 pcs)",
      body=f"""Dear Supplier,

We are sourcing a HOUSEHOLD CHERRY PITTER (table-top) for the German market (peak season Jun-Aug).

PRODUCT SPECIFICATION
- Table-top press-type pitter; hopper/chute feed preferred (continuous pitting, ~10-15 kg/h)
  OR 6-cherry multi-hole press — quote what you produce.
- Food-contact parts: stainless steel 304 / food-grade ABS; coated aluminum plunger OK.
- SPLASH GUARD (juice protection) + non-slip suction feet — both mandatory.
- Works with fresh, frozen and preserved cherries; spare wear-part (plunger tip) included.
- Bundle option to quote: + pit-collection container.
- LFGB test report for food contact (or we order on batch).
- Retail color box, our brand; German-language insert (artwork supplied).

QUANTITIES
- Trial order: 500 pcs. Repeat tiers: 1,000 / 2,000 pcs.
- Target FOB: <= 5.00 USD/pc for table-top type at trial volume.

SAMPLES
- 2 samples + pitting demo video (fresh + frozen cherries).

{COMMON_TERMS}"""),
 dict(file="RFQ_08_Magnetic_fly_screen_4pack",
      subject="RFQ: DIY magnetic window fly screen 150x130 cm, cuttable, 4-pack (trial 500 packs)",
      body=f"""Dear Supplier,

We are sourcing a DIY MAGNETIC WINDOW INSECT SCREEN KIT for the German market (season Apr-Sep).

PRODUCT SPECIFICATION
- Kit for windows up to 150 x 130 cm, mesh CUTTABLE to size; tool-free magnet mounting.
- >= 16 magnet sets per window (stronger hold than the 12-magnet market standard) +
  self-adhesive fixing plates with 3M (or equal) adhesive — residue-free removal.
- Fiberglass mesh, UV-resistant, anthracite/black; clear view + airflow optimized.
- Suitable for plastic, aluminum and wood frames.
- Retail unit: 4-PACK color box (4 complete window kits), our brand; German instruction
  leaflet (artwork supplied).

QUANTITIES
- Trial order: 500 x 4-packs (2,000 kits). Repeat tiers: 1,000 / 2,000 packs.
- Target FOB: <= 6.40 USD per 4-pack at trial volume.

SAMPLES
- 2 sample kits; please state magnet strength (N) and adhesive brand.

{COMMON_TERMS}"""),
 dict(file="RFQ_09_Cooling_blanket_arc_chill",
      subject="RFQ: Cooling blanket Q-max >= 0.4 (Arc-Chill type), 150x200 cm (trial 300 pcs)",
      body=f"""Dear Supplier,

We are sourcing a COOLING BLANKET (summer, cool-touch) for the German market (season May-Aug).

PRODUCT SPECIFICATION
- Size 150 x 200 cm (also quote 130x170 and 220x200 for line extension).
- Cool side: cool-touch nylon (mica nylon / "Arc-Chill" class fiber), Q-MAX >= 0.4 —
  test report required; reverse side: breathable cotton or bamboo viscose.
- Double-side design (cool summer side / soft side), weight ~0.9-1.1 kg.
- Machine washable 30C without losing cooling effect; yarn-dyed (no fading/shrinking).
- OEKO-TEX Standard 100 certificate — mandatory for Germany.
- Colors: grey + blue. Retail: zippered PVC/PEVA carry bag + our-brand insert card.
- Premium option to quote separately: PCM gel-infused version.

QUANTITIES
- Trial order: 300 pcs (150x200). Repeat tiers: 600 / 1,200 pcs.
- Target FOB: <= 8.00 USD/pc at trial volume.

SAMPLES
- 2 samples (grey) + Q-max test report + OEKO-TEX certificate copy.

{COMMON_TERMS}"""),
]

# .txt файлы
for r in RFQS:
    with open(f"{OUT_DIR}/{r['file']}.txt", "w", encoding="utf-8") as f:
        f.write("SUBJECT: " + r["subject"] + "\n\n" + r["body"] + "\n")

# Сводный DOCX
doc = Document()
st = doc.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(10)
for sec in doc.sections:
    sec.left_margin = Cm(2.0); sec.right_margin = Cm(2.0)

MUTED = RGBColor(0x5C, 0x64, 0x70); ACCENT = RGBColor(0x8A, 0x5A, 0x0E)
p = doc.add_paragraph(); r = p.add_run("RFQ PACKAGE — Amazon EU (DE) Portfolio · 9 SKU · July 2026")
r.font.size = Pt(18); r.bold = True
p = doc.add_paragraph()
r = p.add_run("Готово к отправке через Alibaba TradeManager / e-mail. Правила: 3–5 фабрик на SKU · Verified Supplier + "
              "Trade Assurance · стаж ≥3 года · сравнить с 1688 через агента · образцы до заказа · QC-инспекция до отгрузки. "
              "Отдельные .txt-файлы каждого письма — в этой же папке deliverables/RFQ/.")
r.font.size = Pt(9.5); r.font.color.rgb = MUTED

for i, rfq in enumerate(RFQS):
    if i: doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
    p = doc.add_paragraph(); r = p.add_run(f"RFQ {i+1:02d} · {rfq['file'].replace('_',' ').replace('RFQ ','')}")
    r.font.size = Pt(14); r.bold = True; r.font.color.rgb = ACCENT
    p = doc.add_paragraph(); r = p.add_run("SUBJECT: " + rfq["subject"]); r.bold = True; r.font.size = Pt(10.5)
    for line in rfq["body"].split("\n"):
        p = doc.add_paragraph(); p.paragraph_format.space_after = Pt(1)
        r = p.add_run(line); r.font.size = Pt(9.5)
        if line.strip() and line == line.upper() and len(line.strip()) > 8:
            r.bold = True

doc.save(f"{OUT_DIR}/RFQ_Package_2026-07.docx")
print("OK:", OUT_DIR, "->", len(RFQS), "писем + RFQ_Package_2026-07.docx")
