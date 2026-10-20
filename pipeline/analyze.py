"""First look at the national Schedule H table. Reads hospitals_wide.csv, keeps the latest filing per EIN, prints distributions."""
import csv, statistics as st
from collections import defaultdict

rows = list(csv.DictReader(open('hospitals_wide.csv')))
def f(x):
    try: return float(x) if x not in ('', 'None', None) else None
    except: return None

# latest filing per EIN
by = {}
for r in rows:
    k = r['ein']
    if k not in by or r['fye'] > by[k]['fye']:
        by[k] = r
latest = list(by.values())
print(f'{len(rows)} filings, {len(by)} distinct EINs; fiscal years in latest set:', sorted(set(r['fye'][:4] for r in latest)))
yrs = defaultdict(int)
for r in rows: yrs[r['fye'][:4]] += 1
print('filings by FYE year:', dict(sorted(yrs.items())))

def pct(v, q):
    v = sorted(v); return v[int(q * (len(v) - 1))]

cc = [f(r['charity_care_pct']) for r in latest if f(r['charity_care_pct']) is not None]
print(f'\nCharity care % of expenses (line 7a col f), n={len(cc)}: median {st.median(cc):.2f}, p10 {pct(cc,.1):.2f}, p25 {pct(cc,.25):.2f}, p75 {pct(cc,.75):.2f}, p90 {pct(cc,.9):.2f}')
big = [r for r in latest if (f(r['total_revenue']) or 0) >= 1e9]
ccb = [f(r['charity_care_pct']) for r in big if f(r['charity_care_pct']) is not None]
print(f'Systems with revenue >= $1B: n={len(big)}; charity care % median {st.median(ccb):.2f}, p25 {pct(ccb,.25):.2f}, p75 {pct(ccb,.75):.2f}')
under1 = sum(1 for x in ccb if x < 1); under2 = sum(1 for x in ccb if x < 2)
print(f'  under 1%: {under1} ({under1/len(ccb)*100:.0f}%), under 2%: {under2} ({under2/len(ccb)*100:.0f}%)')

# top paid vs charity care, revenue >= $1B
ratio = []
for r in big:
    tp, cc_ = f(r['top_paid_total']), f(r['charity_care_net'])
    if tp and cc_ and cc_ > 0: ratio.append((tp / cc_ * 100, r))
ratio.sort(key=lambda x: -x[0])
print(f'\nTop-paid person pay as % of charity care, revenue >= $1B, n={len(ratio)}: median {st.median([x for x,_ in ratio]):.1f}%')
print('Over 100% (one person paid more than all charity care):', sum(1 for x, _ in ratio if x >= 100))
print('\nTOP 25 by that ratio:')
for x, r in ratio[:25]:
    print(f"{x:7.0f}%  {r['name'][:45]:45s} {r['state']} FYE {r['fye'][:7]}  rev ${f(r['total_revenue'])/1e9:5.2f}B  CC {f(r['charity_care_pct']):5.2f}%  ${f(r['charity_care_net'])/1e6:6.1f}M  top ${f(r['top_paid_total'])/1e6:5.2f}M {str(r['top_paid_person'])[:22]} ({str(r['top_paid_title'])[:28]})")

print('\nLOWEST charity care % among revenue >= $1B (bottom 20):')
for r in sorted(big, key=lambda r: f(r['charity_care_pct']) if f(r['charity_care_pct']) is not None else 99)[:20]:
    print(f"{f(r['charity_care_pct']):5.2f}%  {r['name'][:50]:50s} {r['state']} rev ${f(r['total_revenue'])/1e9:5.2f}B  net assets ${(f(r['net_assets']) or 0)/1e9:5.2f}B  top ${(f(r['top_paid_total']) or 0)/1e6:5.2f}M")

print('\nHIGHEST charity care % among revenue >= $1B (top 10):')
for r in sorted(big, key=lambda r: -(f(r['charity_care_pct']) or 0))[:10]:
    print(f"{f(r['charity_care_pct']):5.2f}%  {r['name'][:50]:50s} {r['state']} rev ${f(r['total_revenue'])/1e9:5.2f}B")

print('\nTOP 20 paid people across all hospital filers (latest filing per EIN):')
for r in sorted(latest, key=lambda r: -(f(r['top_paid_total']) or 0))[:20]:
    print(f"${f(r['top_paid_total'])/1e6:6.2f}M  {str(r['top_paid_person'])[:25]:25s} {str(r['top_paid_title'])[:30]:30s} {r['name'][:40]:40s} {r['state']}  CC {f(r['charity_care_pct']) if f(r['charity_care_pct']) is not None else 'na'}%")

# state table
byst = defaultdict(list)
for r in latest:
    if f(r['charity_care_pct']) is not None: byst[r['state']].append(f(r['charity_care_pct']))
print('\nMedian charity care % by state (n>=10):')
for s, v in sorted(byst.items(), key=lambda kv: st.median(kv[1])):
    if len(v) >= 10: print(f'  {s} n={len(v):3d} median {st.median(v):.2f}')
