#!/usr/bin/env python3
"""UAE (amazon.ae) unit-economics engine for US new-arrival sourcing.

Source of demand: Amazon US new arrivals (Home & Kitchen + Furniture/office chairs).
Target market:    Amazon.ae (UAE), FBA.
All monetary assumptions are documented and mirrored into the editable XLSX model.
"""
import csv, math, os, json

USD_AED = 3.6725              # pegged
VAT = 0.05                    # UAE VAT (price is VAT-inclusive)
REFERRAL = 0.15              # Home&Kitchen >50 AED = 15% (<=50 AED would be 8%)
DUTY = 0.05                   # UAE customs duty on CIF
UAE_CIT = 0.09               # UAE corporate income tax (>375k AED profit)

# Scenario advertising / promo loads
PPC_LAUNCH = 0.35            # ТЗ: launch ad intensity (TACOS) first 2-3 months
PPC_STEADY = 0.12            # sustainable steady-state
COUPON_LAUNCH = 0.10        # ТЗ: coupon 10% (launch)
COUPON_STEADY = 0.03
MARKETING = 0.03            # external/brand marketing
RETURNS = 0.02              # refund/return reserve
INBOUND_AED = 2.0           # prep + inbound to FBA per unit

# Freight China -> Jebel Ali (sea LCL, all-in incl. destination + clearance handling)
SEA_RATE_USD_CBM = 165.0
FREIGHT_PER_KG_FLOOR = 0.45

# UAE selling-price premium vs US price (AED). Validated vs live amazon.ae data:
# office chairs sell AED 758-969 (~+30-50% over US*FX); H&K ~+10-15%.
PREMIUM_FURNITURE = 1.25
PREMIUM_HK = 1.12

FURNITURE_CATS = ("chair", "desk", "mirror", "furniture", "stool", "shelf", "rug")

def is_furniture(title, cat):
    t = (title + " " + cat).lower()
    return any(k in t for k in FURNITURE_CATS)

def fob_estimate(price_usd, weight_g, title, cat):
    """Indicative FOB (USD). Confirm via RFQ. Rule: private-label typical cost ratio,
    floored by a material/weight minimum."""
    t = (title + " " + cat).lower()
    ratio = 0.20
    if any(k in t for k in ("chair",)): ratio = 0.32
    elif any(k in t for k in ("desk", "mirror", "rug", "mattress", "air conditioner", "purifier", "dehumidifier", "steam", "kettle")): ratio = 0.28
    elif any(k in t for k in ("fan", "knife", "steamer")): ratio = 0.22
    base = price_usd * ratio
    # weight floor: ~ $2.2/kg raw+labor minimum
    floor = weight_g/1000.0 * 2.2
    return round(max(base, floor), 2)

def fba_ae_fee(weight_g, l, w, h):
    """Amazon.ae FBA fulfilment fee (AED), 2026 indicative schedule.
    Standard <=12kg & longest<=450mm: 7.2-21.5. Oversize/heavy above."""
    kg = weight_g/1000.0
    longest = max(l, w, h)
    girth_ok = longest <= 450 and kg <= 12
    if girth_ok:
        for lim, fee in [(0.25,7.2),(0.5,8.5),(1,11.0),(2,14.5),(3,16.5),(5,18.5),(9,20.0),(12,21.5)]:
            if kg <= lim: return fee
        return 21.5
    # oversize / heavy-bulky
    for lim, fee in [(2,25.0),(5,32.0),(10,41.5),(15,60.0),(20,78.0),(25,92.0),(30,108.0)]:
        if kg <= lim: return fee
    return 108.0 + (kg-30)*3.0

def compute(row, ppc, coupon):
    price_usd = float(row["price"]) or 0
    weight_g = float(row["weight_g"]) or 0
    l,w,h = float(row["len_mm"]),float(row["wid_mm"]),float(row["hei_mm"])
    title, cat = row["title"], row["cat2"]
    furn = is_furniture(title, cat)
    premium = PREMIUM_FURNITURE if furn else PREMIUM_HK
    # UAE list price (VAT-incl), rounded to attractive .00
    P = round(price_usd * USD_AED * premium)
    P = round(P/1)*1.0
    if P >= 100: P = round(P/5)*5 - 1     # e.g. 599
    # COGS
    fob = fob_estimate(price_usd, weight_g, title, cat)
    vol_cbm = (l*w*h)/1e9
    freight = max(vol_cbm*SEA_RATE_USD_CBM, weight_g/1000.0*FREIGHT_PER_KG_FLOOR)
    duty = DUTY*(fob+freight)
    landed_usd = fob + freight + duty
    landed_aed = landed_usd*USD_AED + INBOUND_AED
    # Amazon & selling costs (on VAT-incl list price)
    referral = REFERRAL*P
    fba = fba_ae_fee(weight_g,l,w,h)
    ppc_c = ppc*P
    coupon_c = coupon*P
    mkt_c = MARKETING*P
    ret_c = RETURNS*P
    vat_c = P - P/(1+VAT)          # output VAT remitted
    net_rev = P/(1+VAT)            # ex-VAT revenue
    total_sell_cost = referral+fba+ppc_c+coupon_c+mkt_c+ret_c
    ebitda_unit = net_rev - total_sell_cost - landed_aed   # operating profit/unit
    margin = ebitda_unit/net_rev if net_rev else 0
    roi = ebitda_unit/landed_aed if landed_aed else 0
    return dict(price_aed=P, fob_usd=fob, freight_usd=round(freight,2),
                landed_aed=round(landed_aed,2), referral=round(referral,2),
                fba=fba, ppc=round(ppc_c,2), coupon=round(coupon_c,2),
                mkt=round(mkt_c,2), returns=round(ret_c,2), vat=round(vat_c,2),
                net_rev=round(net_rev,2), ebitda_unit=round(ebitda_unit,2),
                margin=round(margin*100,1), roi=round(roi*100,0),
                furniture=furn, vol_cbm=round(vol_cbm,4))

def brand_ok(b):
    """Exclude clearly non-private-label mega/established brands."""
    bad = {"levoit","cosori","dreo","hydrojug","iris usa","sihoo","comfilife",
           "geniani","nuzzle","stanley","owala","furmax","neo chair","gtplayer",
           "n-gen gaming","felixking"}
    return b.strip().lower() not in bad

rows=[]
with open("/home/user/Keepa/analysis_workspace/02_keepa_live/us_candidates_uae.csv") as f:
    for r in csv.DictReader(f):
        rows.append(r)

# de-dupe by title root (keep highest monthly_sold)
seen={}
for r in rows:
    key=r["title"][:22].lower()
    ms=float(r["monthly_sold"] or 0)
    if key not in seen or ms>float(seen[key]["monthly_sold"] or 0):
        seen[key]=r
rows=list(seen.values())

results=[]
for r in rows:
    st=compute(r, PPC_STEADY, COUPON_STEADY)
    ln=compute(r, PPC_LAUNCH, COUPON_LAUNCH)
    ms=float(r["monthly_sold"] or 0)
    rec=dict(asin=r["asin"], brand=r["brand"], title=r["title"][:55],
             cat=r["cat2"], monthly_sold=int(ms), rating=float(r["rating"] or 0),
             reviews=int(float(r["reviews"] or 0)), offers=int(float(r["offers"] or 0)),
             weight_kg=round(float(r["weight_g"] or 0)/1000,2),
             brand_ok=brand_ok(r["brand"]), **{f"s_{k}":v for k,v in st.items()},
             l_ebitda=ln["ebitda_unit"], l_margin=ln["margin"])
    results.append(rec)

# PASS filter (steady-state): margin>=15, roi>=40, ebitda>0, sales>=300, rating>=4.2, offers<=6, brand_ok
def passes(x):
    return (x["s_margin"]>=15 and x["s_roi"]>=40 and x["s_ebitda_unit"]>0
            and x["monthly_sold"]>=300 and x["rating"]>=4.2 and x["offers"]<=6
            and x["brand_ok"])

passed=[x for x in results if passes(x)]
# score: blend of monthly EBITDA potential (capture 15%) and ROI
for x in passed:
    x["mo_ebitda_pot"]=round(x["s_ebitda_unit"]*x["monthly_sold"]*0.15)
    x["score"]=x["mo_ebitda_pot"]*0.6 + x["s_roi"]*15 + x["s_margin"]*40
passed.sort(key=lambda x:-x["score"])

os.makedirs("/home/user/Keepa/analysis_workspace/03_unit_economics", exist_ok=True)
with open("/home/user/Keepa/analysis_workspace/03_unit_economics/uae_all_computed.json","w") as f:
    json.dump(results,f,ensure_ascii=False,indent=1)

print(f"total candidates: {len(results)} | passed: {len(passed)}")
print(f"{'ASIN':11} {'brand':13} {'AED':>5} {'sold':>5} {'mrg%':>5} {'roi%':>5} {'ebU':>6} {'moEB':>6} {'furn':>4}  title")
for x in passed[:30]:
    print(f"{x['asin']:11} {x['brand'][:13]:13} {x['s_price_aed']:5.0f} {x['monthly_sold']:5} "
          f"{x['s_margin']:5.1f} {x['s_roi']:5.0f} {x['s_ebitda_unit']:6.1f} {x['mo_ebitda_pot']:6} "
          f"{'Y' if x['s_furniture'] else '':>4}  {x['title'][:40]}")
