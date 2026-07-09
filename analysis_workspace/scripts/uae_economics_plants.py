#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""UAE (amazon.ae) unit-economics — artificial plants sourced from US new arrivals."""
import csv, os, json

USD_AED=3.6725; VAT=0.05; REFERRAL=0.15; DUTY=0.05; UAE_CIT=0.09
PPC_LAUNCH=0.35; PPC_STEADY=0.12; COUPON_LAUNCH=0.10; COUPON_STEADY=0.03
MARKETING=0.03; RETURNS=0.02; INBOUND_AED=2.0
SEA_RATE_USD_CBM=165.0; FREIGHT_PER_KG_FLOOR=0.45
PREMIUM_TREE=1.18   # UAE faux trees priced 150-350 AED (validated on amazon.ae)
PREMIUM_DECOR=1.12

def is_tree(title,cat):
    t=(title+" "+cat).lower()
    return any(k in t for k in ("tree","6ft","5ft","4ft","3 ft","topiary"))

def fob_estimate(price_usd,weight_g,title,cat):
    t=(title+" "+cat).lower()
    ratio=0.24
    if any(k in t for k in ("tree","olive","6ft","topiary")): ratio=0.28
    base=price_usd*ratio
    floor=weight_g/1000.0*2.0   # faux foliage light; ~$2/kg material+labor
    return round(max(base,floor),2)

def fba_ae_fee(weight_g,l,w,h):
    kg=weight_g/1000.0; longest=max(l,w,h)
    if longest<=450 and kg<=12:
        for lim,fee in [(0.25,7.2),(0.5,8.5),(1,11.0),(2,14.5),(3,16.5),(5,18.5),(9,20.0),(12,21.5)]:
            if kg<=lim: return fee
        return 21.5
    for lim,fee in [(2,25.0),(5,32.0),(10,41.5),(15,60.0),(20,78.0),(25,92.0),(30,108.0)]:
        if kg<=lim: return fee
    return 108.0+(kg-30)*3.0

def compute(row,ppc,coupon):
    price_usd=float(row["price"]) or 0
    weight_g=float(row["weight_g"]) or 0
    l,w,h=float(row["len_mm"]),float(row["wid_mm"]),float(row["hei_mm"])
    title,cat=row["title"],row["cat2"]
    tree=is_tree(title,cat)
    premium=PREMIUM_TREE if tree else PREMIUM_DECOR
    P=round(price_usd*USD_AED*premium)
    if P>=100: P=round(P/5)*5-1
    fob=fob_estimate(price_usd,weight_g,title,cat)
    vol=(l*w*h)/1e9
    freight=max(vol*SEA_RATE_USD_CBM,weight_g/1000.0*FREIGHT_PER_KG_FLOOR)
    duty=DUTY*(fob+freight)
    landed_aed=(fob+freight+duty)*USD_AED+INBOUND_AED
    referral=REFERRAL*P; fba=fba_ae_fee(weight_g,l,w,h)
    ppc_c=ppc*P; coupon_c=coupon*P; mkt_c=MARKETING*P; ret_c=RETURNS*P
    net_rev=P/(1+VAT); vat_c=P-net_rev
    total=referral+fba+ppc_c+coupon_c+mkt_c+ret_c
    eb=net_rev-total-landed_aed
    margin=eb/net_rev if net_rev else 0
    roi=eb/landed_aed if landed_aed else 0
    return dict(price_aed=P,fob_usd=fob,freight_usd=round(freight,2),landed_aed=round(landed_aed,2),
        referral=round(referral,2),fba=fba,ppc=round(ppc_c,2),coupon=round(coupon_c,2),
        mkt=round(mkt_c,2),returns=round(ret_c,2),vat=round(vat_c,2),net_rev=round(net_rev,2),
        ebitda_unit=round(eb,2),margin=round(margin*100,1),roi=round(roi*100,0),
        furniture=tree,vol_cbm=round(vol,4))

rows=[]
with open("/home/user/Keepa/analysis_workspace/02_keepa_live/us_plants_candidates.csv") as f:
    for r in csv.DictReader(f): rows.append(r)
# de-dupe near-identical titles (keep highest sold)
seen={}
for r in rows:
    key=r["title"][:20].lower(); ms=float(r["monthly_sold"] or 0)
    if key not in seen or ms>float(seen[key]["monthly_sold"] or 0): seen[key]=r
rows=list(seen.values())

results=[]
for r in rows:
    st=compute(r,PPC_STEADY,COUPON_STEADY); ln=compute(r,PPC_LAUNCH,COUPON_LAUNCH)
    ms=float(r["monthly_sold"] or 0)
    results.append(dict(asin=r["asin"],brand=r["brand"],title=r["title"][:55],cat=r["cat2"],
        monthly_sold=int(ms),rating=float(r["rating"] or 0),reviews=int(float(r["reviews"] or 0)),
        offers=int(float(r["offers"] or 0)),weight_kg=round(float(r["weight_g"] or 0)/1000,2),
        **{f"s_{k}":v for k,v in st.items()},l_ebitda=ln["ebitda_unit"],l_margin=ln["margin"]))

def passes(x):
    return (x["s_margin"]>=15 and x["s_roi"]>=40 and x["s_ebitda_unit"]>0
            and x["monthly_sold"]>=300 and x["rating"]>=4.2 and x["offers"]<=4)
passed=[x for x in results if passes(x)]
UAE_MKT=0.05; SHARE=0.30
for x in passed:
    x["uae_sales_mo"]=round(x["monthly_sold"]*UAE_MKT*SHARE)
    x["mo_ebitda_pot"]=round(x["s_ebitda_unit"]*x["monthly_sold"]*UAE_MKT*SHARE)
    x["score"]=x["mo_ebitda_pot"]*0.6+x["s_roi"]*15+x["s_margin"]*40
passed.sort(key=lambda x:-x["score"])

os.makedirs("/home/user/Keepa/analysis_workspace/03_unit_economics",exist_ok=True)
json.dump(results,open("/home/user/Keepa/analysis_workspace/03_unit_economics/uae_plants_all.json","w"),ensure_ascii=False,indent=1)
print(f"candidates:{len(results)} passed:{len(passed)}")
print(f"{'ASIN':11} {'brand':11} {'AED':>4} {'sold':>5} {'mrg':>5} {'roi':>4} {'ebU':>5} {'moEB':>5} {'tree':>4} title")
for x in passed[:32]:
    print(f"{x['asin']:11} {x['brand'][:11]:11} {x['s_price_aed']:4.0f} {x['monthly_sold']:5} {x['s_margin']:5.1f} "
          f"{x['s_roi']:4.0f} {x['s_ebitda_unit']:5.0f} {x['mo_ebitda_pot']:5} {'Y' if x['s_furniture'] else '':>4} {x['title'][:38]}")
