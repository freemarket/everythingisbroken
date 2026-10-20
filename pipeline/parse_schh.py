"""Parse a saved ProPublica-rendered Schedule H text dump and append rows to CSV."""
import re, sys, json
import add_rows as A

LINES = {
 'a':'sch_h_7a_financial_assistance_at_cost','b':'sch_h_7b_medicaid','c':'sch_h_7c_other_means_tested',
 'd':'sch_h_7d_total_fa_and_means_tested','e':'sch_h_7e_community_health_improvement','f':'sch_h_7f_health_professions_education',
 'g':'sch_h_7g_subsidized_health_services','h':'sch_h_7h_research','i':'sch_h_7i_cash_inkind_contributions',
 'j':'sch_h_7j_total_other_benefits','k':'sch_h_7k_total_community_benefits'}

def num(s):
    s=s.replace(',','').replace('%','').strip()
    try: return float(s) if '.' in s else int(s)
    except: return None

def parse(text):
    out={}
    # Part I table: find "Financial Assistance at cost" region up to "Part II"
    i=text.find('Financial Assistance at cost'); j=text.find('Part II',i)
    seg=text[i-20:j]
    # split by line letter markers "\n\na\n", etc.
    parts=re.split(r'\n\n([a-k])\n',seg)
    # parts[0] preamble, then letter, body, letter, body...
    for k in range(1,len(parts),2):
        letter=parts[k]; body=parts[k+1]
        nums=re.findall(r'(-?[\d,]+(?:\.\d+)?)\s*%?',body)
        # take trailing 4 numeric tokens: total, offset, net, pct (for d/j/k there are leading 0 0 for optional cols)
        toks=[x for x in re.findall(r'-?[\d,]*\d(?:\.\d+)?(?: %)?',body)]
        vals=[]
        for tok in re.findall(r'(-?[\d,]*\d(?:\.\d+)?)( %)?',body):
            vals.append((num(tok[0]), bool(tok[1])))
        # find pct token (last with %), then the 3 numbers before it
        # Robust: strip label text (up to first ' . .' or 'Worksheet N)' ), then read cells line by line
        body2=re.sub(r'\(from Worksheet \d+[^)]*\)','',body)
        body2=re.sub(r'Worksheet \d+','',body2)
        cells=[c.strip() for c in body2.split('\n')]
        # keep only cells that are blank, numeric, or pct
        cells=[c for c in cells if c=='' or re.fullmatch(r'-?[\d,]*\d(?:\.\d+)?( %)?',c)]
        # drop leading empties and label residue; find pct cell
        pidx=max([i for i,c in enumerate(cells) if c.endswith('%')],default=None)
        if pidx is None or pidx<3: continue
        c3=cells[pidx-3:pidx]
        total,offset,net=[num(c) if c else 0 for c in c3]
        # for total rows (d/j/k) columns (a),(b) precede: c3 is still last three before pct, correct.
        out[letter]=dict(total=total,offset=offset,net=net,pct=num(cells[pidx]))
    m=re.search(r'Section A\. Bad Debt Expense.*?\n2\n([\d,]+)',text,re.S); out['bad_debt']=num(m.group(1)) if m else None
    m=re.search(r'\n3\n([\d,]+)\n \n4\nProvide in Part VI',text); out['bad_debt_fap_eligible']=num(m.group(1)) if m else None
    m=re.search(r'\n5\n([\d,]+)\n \n6\n',text); out['medicare_revenue']=num(m.group(1)) if m else None
    m=re.search(r'\n6\n([\d,]+)\n \n7\n',text); out['medicare_cost']=num(m.group(1)) if m else None
    m=re.search(r'\n7\n(-?[\d,]+)\n \n8\n',text); out['medicare_shortfall']=num(m.group(1)) if m else None
    m=re.search(r'Part II.*?\n10\nTotal\n[\d,]*\n[\d,]*\n([\d,]+)\n',text,re.S); out['community_building_total']=num(m.group(1)) if m else None
    m=re.search(r'How many hospital facilities did the organization operate during the tax year\?(\d+)',text); out['facility_count']=int(m.group(1)) if m else None
    m=re.search(r'3a\nYes\n \n \n(.*?)\n',text); out['fpg_free_raw']=m.group(1).strip() if m else None
    m=re.search(r'3b\nYes\n \n \n(.*?)\n',text); out['fpg_discount_raw']=m.group(1).strip() if m else None
    facs=re.findall(r'\n(\d+)\n([^\n]+)\n([^\n]+)\n([^\n]+,\s*[A-Z]{2}\s*\d{5})\n',text[text.find('Section A. Hospital Facilities'):text.find('Section B. Facility Policies')] if 'Section A. Hospital Facilities' in text else '')
    out['facilities']=[f[1] for f in facs]
    return out

def write_rows(parsed, system, entity, ein, fye, source_doc, url, extra_note=''):
    base=dict(system=system,entity_name=entity,ein=ein,fiscal_year_end=fye,source_type='IRS990',source_doc=source_doc,
              source_url=url,retrieval_method='built-in browser get_page_text of ProPublica rendered Schedule H; parsed by script')
    rows=[]
    for letter,metric in LINES.items():
        if letter in parsed:
            v=parsed[letter]
            rows.append({**base,'metric':metric+'_total_expense','value':v['total'],'unit':'USD','source_location':f'Schedule H Part I line 7{letter} col (c)','notes':extra_note})
            rows.append({**base,'metric':metric+'_offsetting_revenue','value':v['offset'],'unit':'USD','source_location':f'Schedule H Part I line 7{letter} col (d)','notes':extra_note})
            rows.append({**base,'metric':metric+'_net','value':v['net'],'unit':'USD','source_location':f'Schedule H Part I line 7{letter} col (e)','notes':extra_note})
            rows.append({**base,'metric':metric+'_pct_total_expense','value':v['pct'],'unit':'pct','source_location':f'Schedule H Part I line 7{letter} col (f)','notes':extra_note})
    for key,loc,unit in [('bad_debt','Schedule H Part III line 2','USD'),('bad_debt_fap_eligible','Schedule H Part III line 3','USD'),
                         ('medicare_revenue','Schedule H Part III line 5','USD'),('medicare_cost','Schedule H Part III line 6','USD'),
                         ('medicare_shortfall','Schedule H Part III line 7','USD'),('community_building_total','Schedule H Part II line 10 col (c)','USD'),
                         ('facility_count','Schedule H Part V Section A','count'),('fpg_free_raw','Schedule H Part I line 3a','text'),('fpg_discount_raw','Schedule H Part I line 3b','text')]:
        if parsed.get(key) is not None:
            rows.append({**base,'metric':'sch_h_'+key,'value':parsed[key],'unit':unit,'source_location':loc,'notes':extra_note})
    if parsed.get('facilities'):
        rows.append({**base,'metric':'sch_h_facilities_list','value':' | '.join(parsed['facilities']),'unit':'text','source_location':'Schedule H Part V Section A','notes':extra_note})
    A.add(*rows)
    return len(rows)

if __name__=='__main__':
    p=parse(open(sys.argv[1]).read()); print(json.dumps(p,indent=1))
