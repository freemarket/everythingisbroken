"""Parse every Schedule H XML in ./xml and append rows to ../hospital_data.csv (append-only).
Also writes hospitals_wide.csv: one row per filing with the headline fields, for analysis.
Idempotent per object_id: skips filings already loaded (tracked in loaded_object_ids.txt).
"""
import os, sys, csv, json, glob, traceback
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import add_rows as A
import parse_xml as P

HERE = os.path.dirname(os.path.abspath(__file__))
LOADED = os.path.join(HERE, 'loaded_object_ids.txt')
WIDE = os.path.join(HERE, 'hospitals_wide.csv')
ERRS = os.path.join(HERE, 'parse_errors.txt')

loaded = set(open(LOADED).read().split()) if os.path.exists(LOADED) else set()

def fmt_ein(e): return f'{e[:2]}-{e[2:]}' if e and len(e) == 9 else e

def rows_for(d):
    oid = d['object_id']; ein = fmt_ein(d['ein'])
    fye = d['tax_period_end'][:7] if d['tax_period_end'] else ''
    base = dict(system='', entity_name=d['name'] + (f" {d['name2']}" if d.get('name2') else ''), ein=ein, fiscal_year_end=fye,
                source_type='IRS990', source_doc=f"Form 990 e-file XML, TaxYr {d['tax_year']}, filed {d['return_ts'][:10] if d['return_ts'] else ''}, ObjectId {oid}",
                source_url=f'https://apps.irs.gov/pub/epostcard/990/xml/{oid[:4]}/ (bulk zip)  |  https://projects.propublica.org/nonprofits/organizations/{d["ein"]}/{oid}/full',
                retrieval_method='IRS bulk XML parsed by parse_xml.py', unit='USD',
                notes=('GROUP RETURN' if d.get('group_return') == 'true' else ''))
    R = []
    def r(metric, value, loc, unit='USD', **kw):
        if value is None: return
        row = {**base, 'metric': metric, 'value': value, 'source_location': loc, 'unit': unit}
        row.update(kw); R.append(row)
    r('filer_city_state', f"{d['city']}, {d['state']} {d['zip']}", 'ReturnHeader/Filer', 'text')
    r('group_return', d.get('group_return'), 'Form 990 Part I line H(a)', 'text')
    for k, m, loc in [('total_revenue','total_revenue','Form 990 Part I line 12'),('total_expenses','total_expenses','Form 990 Part I line 18'),
                      ('revenue_less_expenses','net_income_990','Form 990 Part I line 19'),('total_assets_eoy','total_assets','Form 990 Part I line 20'),
                      ('total_liabilities_eoy','total_liabilities','Form 990 Part I line 21'),('net_assets_eoy','net_assets','Form 990 Part I line 22'),
                      ('officer_comp_total','compensation_current_officers','Form 990 Part IX line 5'),('other_salaries_total','other_salaries_wages','Form 990 Part IX line 7'),
                      ('investment_income','investment_income','Form 990 Part I line 10'),('program_service_revenue','program_service_revenue','Form 990 Part I line 9'),
                      ('contributions','contributions_and_grants','Form 990 Part I line 8'),('cash_eoy','cash_non_interest_bearing_eoy','Form 990 Part X line 1'),
                      ('savings_temp_cash_eoy','savings_temp_cash_eoy','Form 990 Part X line 2'),('investments_pub_securities_eoy','investments_public_securities_eoy','Form 990 Part X line 11'),
                      ('investments_other_sec_eoy','investments_other_securities_eoy','Form 990 Part X line 12')]:
        r(m, d.get(k), loc)
    r('employee_count', d.get('employee_count'), 'Form 990 Part I line 5', 'count')
    r('indiv_over_100k_cnt', d.get('indiv_over_100k_cnt'), 'Form 990 Part VII line 2', 'count')
    for p in d.get('people', []):
        tot = p['comp_org'] + p['comp_related'] + p['comp_other']
        if tot == 0: continue
        flags = ','.join(f for f, v in [('officer', p['officer']), ('key', p['key_employee']), ('highest', p['highest_comp']), ('former', p['former'])] if v == 'X')
        r('compensation_reportable', p['comp_org'], 'Form 990 Part VII col (D)', person=p['person'], person_title=p['title'], notes=flags)
        if p['comp_related']: r('compensation_related_org', p['comp_related'], 'Form 990 Part VII col (E)', person=p['person'], person_title=p['title'], notes=flags)
        if p['comp_other']: r('compensation_other', p['comp_other'], 'Form 990 Part VII col (F)', person=p['person'], person_title=p['title'], notes=flags)
    s = d.get('sch_h', {})
    for key, v in s.items():
        if isinstance(v, dict):
            ln = v['line']
            r(key + '_total_expense', v['total'], f'Schedule H Part I line {ln} col (c)')
            r(key + '_offsetting_revenue', v['offset'], f'Schedule H Part I line {ln} col (d)')
            r(key + '_net', v['net'], f'Schedule H Part I line {ln} col (e)')
            if v['pct'] is not None: r(key + '_pct_total_expense', round(v['pct'] * 100, 4), f'Schedule H Part I line {ln} col (f)', 'pct')
    r('sch_h_community_building_total', s.get('community_building_total'), 'Schedule H Part II line 10 col (c)')
    r('sch_h_bad_debt', s.get('bad_debt'), 'Schedule H Part III line 2')
    r('sch_h_bad_debt_fap_eligible', s.get('bad_debt_fap_eligible'), 'Schedule H Part III line 3')
    r('sch_h_medicare_revenue', s.get('medicare_revenue'), 'Schedule H Part III line 5')
    r('sch_h_medicare_cost', s.get('medicare_cost'), 'Schedule H Part III line 6')
    r('sch_h_medicare_shortfall', s.get('medicare_shortfall'), 'Schedule H Part III line 7')
    r('sch_h_fpg_free_pct', s.get('fpg_free_pct'), 'Schedule H Part I line 3a', 'pct')
    r('sch_h_fpg_discount_pct', s.get('fpg_discount_pct'), 'Schedule H Part I line 3b', 'pct')
    r('sch_h_facility_count', s.get('facility_count'), 'Schedule H Part V Section A', 'count')
    if s.get('facilities'):
        r('sch_h_facilities_list', ' | '.join(f"{f['name']} ({f['city']}, {f['state']})" for f in s['facilities']), 'Schedule H Part V Section A', 'text')
    return R

def wide_row(d):
    s = d.get('sch_h', {}); fa = s.get('sch_h_7a_financial_assistance_at_cost', {}); tot = s.get('sch_h_7k_total_community_benefits', {})
    ppl = sorted(d.get('people', []), key=lambda p: -(p['comp_org'] + p['comp_related'] + p['comp_other']))
    top = ppl[0] if ppl else {}
    ceo = next((p for p in ppl if p['title'] and any(k in p['title'].upper() for k in ('CEO', 'CHIEF EXECUTIVE', 'PRESIDENT'))), None)
    return {
        'object_id': d['object_id'], 'ein': fmt_ein(d['ein']), 'name': d['name'], 'city': d['city'], 'state': d['state'],
        'fye': d['tax_period_end'], 'tax_year': d['tax_year'], 'group_return': d.get('group_return'),
        'total_revenue': d.get('total_revenue'), 'total_expenses': d.get('total_expenses'), 'net_income': d.get('revenue_less_expenses'),
        'net_assets': d.get('net_assets_eoy'), 'employees': d.get('employee_count'), 'over_100k': d.get('indiv_over_100k_cnt'),
        'charity_care_net': fa.get('net'), 'charity_care_pct': (fa.get('pct') or 0) * 100 if fa else None,
        'medicaid_shortfall_net': s.get('sch_h_7b_medicaid', {}).get('net'), 'total_cb_net': tot.get('net'), 'total_cb_pct': (tot.get('pct') or 0) * 100 if tot else None,
        'bad_debt': s.get('bad_debt'), 'medicare_shortfall': s.get('medicare_shortfall'),
        'fpg_free': s.get('fpg_free_pct'), 'fpg_discount': s.get('fpg_discount_pct'), 'facility_count': s.get('facility_count'),
        'top_paid_person': top.get('person'), 'top_paid_title': top.get('title'),
        'top_paid_total': (top.get('comp_org', 0) + top.get('comp_related', 0) + top.get('comp_other', 0)) if top else None,
        'ceo_person': ceo['person'] if ceo else None, 'ceo_title': ceo['title'] if ceo else None,
        'ceo_total': (ceo['comp_org'] + ceo['comp_related'] + ceo['comp_other']) if ceo else None,
    }

def main():
    files = sorted(glob.glob(os.path.join(HERE, 'xml', '*_public.xml')))
    todo = [f for f in files if os.path.basename(f).replace('_public.xml', '') not in loaded]
    print(f'{len(files)} xml files, {len(todo)} to load')
    wide_exists = os.path.exists(WIDE)
    wf = open(WIDE, 'a', newline=''); ww = None
    nrows = 0; nfil = 0
    for i, f in enumerate(todo):
        try:
            d = P.parse_file(f)
            if 'sch_h' not in d: continue
            R = rows_for(d); A.add(*R); nrows += len(R); nfil += 1
            w = wide_row(d)
            if ww is None:
                ww = csv.DictWriter(wf, fieldnames=list(w.keys()))
                if not wide_exists: ww.writeheader()
            ww.writerow(w)
            with open(LOADED, 'a') as lf: lf.write(d['object_id'] + '\n')
        except Exception as e:
            with open(ERRS, 'a') as ef: ef.write(f'{f}: {e}\n{traceback.format_exc()}\n')
        if i % 200 == 0: print(i, nfil, nrows, flush=True)
    wf.close()
    print(f'loaded {nfil} filings, {nrows} rows; csv total {A.count()}')

if __name__ == '__main__':
    main()
