import sys, json, parse_schh as P, add_rows as A
# usage: save_and_parse.py <rawfile> <system> <entity> <ein> <fye> <objectid> <filed> <notes> <fpg_free> <fpg_disc>
raw,system,entity,ein,fye,oid,filed,notes,fpgf,fpgd=sys.argv[1:11]
t=open(raw).read(); p=P.parse(t)
p['fpg_free_raw']=fpgf; p['fpg_discount_raw']=fpgd
print({k:p[k] for k in 'adk' if k in p}, p.get('bad_debt'), p.get('medicare_shortfall'), p.get('facility_count'))
n=P.write_rows(p,system,entity,ein,fye,f'Form 990 Schedule H FYE {fye}, TY2024 form, filed {filed}, ObjectId {oid}',
  f'https://projects.propublica.org/nonprofits/full_text/{oid}/IRS990ScheduleH',notes)
print('added',n,'total',A.count())
