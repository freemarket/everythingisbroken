import add_rows as A

NM_AUDIT = "https://www.nm.org/-/media/Northwestern/Resources/about-us/northwestern-medicine-fiscal-audit.pdf"
NM_PP = "https://projects.propublica.org/nonprofits/organizations/364724966"
RUSH_PP = "https://projects.propublica.org/nonprofits/organizations/362174823"
UCMC_PP = "https://projects.propublica.org/nonprofits/organizations/363488183"
UC_PP = "https://projects.propublica.org/nonprofits/organizations/362177139"
NS_PP = "https://projects.propublica.org/nonprofits/organizations/362167060"
AHH_PP = "https://projects.propublica.org/nonprofits/organizations/362169147"
AHCN_PP = "https://projects.propublica.org/nonprofits/organizations/362167779"
LOWN_IL = "https://lownhospitalsindex.org/wp-content/uploads/2025/04/illinois-state-report-20250416.pdf"
LOWN_24 = "https://lownhospitalsindex.org/hospital-fair-share-spending-2024/"
IHPA = "https://ihpa.org/wp-content/uploads/2026/03/2026_3.2_IHPA-IL-Memo.pdf"
IHA = "https://www.team-iha.org/getmedia/cd02194e-76c2-45b9-9b09-e5f636e4afce/chicago-nonprofit-hosp-community-value.pdf"
WF = "WebFetch summary"

rows = []
def r(*bases, **kw):
    d={}
    for b in bases: d.update(b)
    if 'notes' in d and 'notes' in kw and kw['notes']:
        kw['notes']=d['notes']+' | '+kw['notes']
    d.update(kw); rows.append(d)

# ---------- Northwestern audited financials FY2025 (thousands converted to dollars) ----------
nm = dict(system="Northwestern Medicine", entity_name="Northwestern Memorial HealthCare and Subsidiaries", ein="36-4724966",
          fiscal_year_end="2025-08", source_type="Audit", source_doc="NMHC Consolidated Financial Report FY2025/2024",
          source_url=NM_AUDIT, retrieval_method=WF, unit="USD")
r(nm, metric="total_revenue", value=10639070000, source_location="Consolidated statement of operations", notes="Audit figure; differs from 990 total revenue")
r(nm, metric="patient_service_revenue", value=9802217000, source_location="Consolidated statement of operations")
r(nm, metric="operating_income", value=379536000, source_location="Consolidated statement of operations")
r(nm, metric="excess_revenue_over_expenses", value=1430703000, source_location="Consolidated statement of operations", notes="Includes nonoperating/investment gains; total incl. noncontrolling")
r(nm, metric="excess_revenue_over_expenses_attrib_nmhc", value=1429787000, source_location="Consolidated statement of operations")
r(nm, metric="net_assets_total", value=15559037000, source_location="Balance sheet")
r(nm, metric="net_assets_without_donor_restrictions", value=14705548000, source_location="Balance sheet")
r(nm, metric="net_assets_with_donor_restrictions", value=853489000, source_location="Balance sheet")
r(nm, metric="cash_and_investments_total", value=13183250000, source_location="Balance sheet", notes="Sum of cash, ST investments, current portion of investments, noncurrent investments")
r(nm, metric="cash_and_cash_equivalents", value=885327000, source_location="Balance sheet")
r(nm, metric="short_term_investments", value=376726000, source_location="Balance sheet")
r(nm, metric="investments_current_portion", value=284634000, source_location="Balance sheet")
r(nm, metric="investments_noncurrent", value=11636563000, source_location="Balance sheet")
r(nm, metric="charity_care_cost", value=122632000, source_location="Notes: charity care", notes="Cost of charity care FY2025 per audit note")
r(nm, metric="charity_care_offset_funds_received", value=385000, source_location="Notes: charity care")
nm24 = dict(nm); nm24["fiscal_year_end"] = "2024-08"
r(nm24, metric="charity_care_cost", value=89014000, source_location="Notes: charity care", notes="Comparative FY2024 figure in FY2025 audit")
r(nm24, metric="il_ag_total_community_benefit", value=1583767000, source_location="Notes: community benefit (unaudited)", notes="Reported to Illinois AG, unaudited, FY2024; FY2025 report not yet prepared at audit date")
r(nm24, metric="il_ag_unreimbursed_charity_care", value=85722000, source_location="Notes: community benefit (unaudited)", notes="Reported to Illinois AG, unaudited, FY2024")

# ---------- Northwestern 990 FY2025 via ProPublica ----------
nmp = dict(system="Northwestern Medicine", entity_name="Northwestern Memorial Healthcare", ein="36-4724966",
           fiscal_year_end="2025-08", source_type="IRS990", source_doc="Form 990 FYE Aug 2025 (filed 2026-07-13)",
           source_url=NM_PP, retrieval_method=WF, unit="USD", source_location="Part I summary")
r(nmp, metric="total_revenue", value=11241795455)
r(nmp, metric="total_expenses", value=10980441111)
r(nmp, metric="net_income_990", value=261354344, notes="Revenue minus expenses as shown by ProPublica; differs from audit excess due to investment gain treatment")
r(nmp, metric="total_assets", value=15487332380)
r(nmp, metric="net_assets", value=11524350900)
for p, t, c, o in [("Dean M Harrison","Executive Chairman (per IHPA)",10834719,3462),
                   ("Howard B Chrisman MD","CEO (per IHPA)",7491303,682758),
                   ("John A Orsini","",4157699,421011),
                   ("Patrick McCarthy MD","",2931408,71599),
                   ("Craig A Johnson","",2231402,453917)]:
    r({**nmp, "source_location":"Part VII"}, metric="compensation_reportable", value=c, person=p, person_title=t)
    r({**nmp, "source_location":"Part VII"}, metric="compensation_other", value=o, person=p, person_title=t)

# ---------- Rush ----------
ru = dict(system="Rush", entity_name="Rush University Medical Center", ein="36-2174823", fiscal_year_end="2025-06",
          source_type="IRS990", source_doc="Form 990 FYE Jun 2025 (filed 2026-05-14)", source_url=RUSH_PP, retrieval_method=WF, unit="USD", source_location="Part I summary")
r(ru, metric="total_revenue", value=2758712727)
r(ru, metric="total_expenses", value=2347044424)
r(ru, metric="net_income_990", value=411668303)
r(ru, metric="total_assets", value=5230553562)
r(ru, metric="net_assets", value=3295855783)
for p,t,c in [("Omar B Lateef DO","President & CEO",4296109),("Angelique Richard PhD RN","SVP Hospital Operations, CNO",1753857),
              ("Matt Walsh MHA","COO",1704633),("Michael Liptay MD","Chair, Cardiovascular/Thoracic Surgery",1521794),("Patricia S O'Neil","CFO",1386497)]:
    r({**ru, "source_location":"Part VII"}, metric="compensation_reportable", value=c, person=p, person_title=t, notes="'Other' column not captured yet")

# ---------- UChicago Medical Center ----------
uc = dict(system="UChicago Medicine", entity_name="University of Chicago Medical Center", ein="36-3488183", fiscal_year_end="2025-06",
          source_type="IRS990", source_doc="Form 990 FYE Jun 2025 (filed 2026-05-14)", source_url=UCMC_PP, retrieval_method=WF, unit="USD", source_location="Part I summary")
r(uc, metric="total_revenue", value=3573895376)
r(uc, metric="total_expenses", value=3399180621)
r(uc, metric="net_income_990", value=174714755)
r(uc, metric="total_assets", value=5272904338)
r(uc, metric="net_assets", value=2823810126)
for p,t,c in [("Thomas Jackiewicz","President, UCHS",2771431),("Jason Keeler","Former EVP & COO (through 2/1/24)",2474057),
              ("Ivan Samstein","EVP, CFO (through 12/31/24)",1795872),("Krista Curell","EVP, COO UChicago Medicine Health System",1694500),("Amy Ross","EVP, Chief Growth Officer",1176534)]:
    r({**uc, "source_location":"Part VII"}, metric="compensation_reportable", value=c, person=p, person_title=t)
# University parent (separate entity) for context
up = dict(system="UChicago Medicine", entity_name="University of Chicago (parent university)", ein="36-2177139", fiscal_year_end="2025-06",
          source_type="IRS990", source_doc="Form 990 FYE Jun 2025", source_url=UC_PP, retrieval_method=WF, unit="USD", source_location="Part I summary",
          notes="Parent university, not the hospital; context only")
r(up, metric="total_revenue", value=5617072703)
r(up, metric="total_expenses", value=5563252626)
r(up, metric="net_income_990", value=53820077)
r(up, metric="total_assets", value=15809478980)
r(up, metric="net_assets", value=9040649825)

# ---------- NorthShore / Endeavor ----------
ns = dict(system="Endeavor Health (NorthShore)", entity_name="NorthShore University HealthSystem", ein="36-2167060", fiscal_year_end="2024-12",
          source_type="IRS990", source_doc="Form 990 FYE Dec 2024 (filed 2025-11-17)", source_url=NS_PP, retrieval_method=WF, unit="USD", source_location="Part I summary")
r(ns, metric="total_revenue", value=2288929952)
r(ns, metric="total_expenses", value=1996084358)
r(ns, metric="net_income_990", value=292845594)
r(ns, metric="total_assets", value=6827544435)
r(ns, metric="net_assets", value=3485591879)
for p,t,c in [("Gerald P Gallagher","President and CEO",3559263),("Julian E Bailes","Clinical Chairman, Neurosurgery",2122651),
              ("Jason L Koh","Clinical Chairman, Orthopedics",1924792),("Douglas D Welday","System Treasurer and CFO",1854234),("Mark S Talamonti","Director and Clinical Chairman, Surgery",1646055)]:
    r({**ns, "source_location":"Part VII"}, metric="compensation_reportable", value=c, person=p, person_title=t)

# ---------- Advocate ----------
ah = dict(system="Advocate Health", entity_name="Advocate Health and Hospitals Corporation", ein="36-2169147", fiscal_year_end="2024-12",
          source_type="IRS990", source_doc="Form 990 FYE Dec 2024 (filed 2025-11-18)", source_url=AHH_PP, retrieval_method=WF, unit="USD", source_location="Part I summary")
r(ah, metric="total_revenue", value=7808910070)
r(ah, metric="total_expenses", value=8322030624)
r(ah, metric="net_income_990", value=-513120554, notes="Loss likely reflects post-Atrium-merger intercompany accounting; verify against audited statements before use")
r(ah, metric="total_assets", value=23838091591)
r(ah, metric="net_assets", value=5606463281)
for p,t,c in [("Michael Farrell","President, Advocate Children's Hospital",2271050),("Hamad Farhat","Neurosurgeon",2264231),
              ("Karen Lambert","",1562748),("Marcus Talerico","Neurosurgeon",1556516),("Marianna Krive","Physician",1556111)]:
    r({**ah, "source_location":"Part VII"}, metric="compensation_reportable", value=c, person=p, person_title=t, notes="Top execs paid via related orgs not in this list")
an = dict(system="Advocate Health", entity_name="Advocate Health Care Network", ein="36-2167779", fiscal_year_end="2024-12",
          source_type="IRS990", source_doc="Form 990 FYE Dec 2024 (filed 2025-11-18)", source_url=AHCN_PP, retrieval_method=WF, unit="USD", source_location="Part I summary",
          notes="Shell/parent entity; tiny operations; exec pay shown as related-org compensation")
r(an, metric="total_revenue", value=21843129)
r(an, metric="total_expenses", value=76639)
r(an, metric="total_assets", value=625764475)
r(an, metric="net_assets", value=601755869)
for p,t,c in [("James Skogsbergh","President (former Advocate Aurora co-CEO)",30862679),("William Santulli","Director",7866221),
              ("Gary Stuck","Former Officer",5031929),("Brett Denton","Secretary",4008208),("Barbara Byrne","Former Officer",3716024)]:
    r({**an, "source_location":"Part VII (Related + Other columns summed by fetch)"}, metric="compensation_related_plus_other", value=c, person=p, person_title=t,
      notes="Sum of Related and Other columns per WebFetch; Compensation column $0; verify in filing")

# ---------- Lown Institute Illinois report (2020-2022 annual averages) ----------
lw = dict(source_type="Lown", source_doc="Lown Institute Illinois State Report (Apr 2025)", source_url=LOWN_IL, retrieval_method=WF, unit="USD", fiscal_year_end="2020-2022avg",
          source_location="Top-10 deficit/surplus tables")
for sys_, ent, v, note in [
    ("Endeavor Health (NorthShore)","Evanston Hospital",-152000000,"Largest deficit in IL; includes >1 campus under same CMS ID"),
    ("Advocate Health","Advocate Christ Medical Center (Oak Lawn)",-71000000,"IRS info prorated across multiple hospitals"),
    ("Advocate Health","Advocate Lutheran General Hospital (Park Ridge)",-68000000,"prorated"),
    ("OSF","OSF Little Company of Mary Medical Center (Evergreen Park)",-62000000,"prorated"),
    ("Northwestern Medicine","Northwestern Memorial Hospital",-50000000,"prorated"),
    ("Northwestern Medicine","Northwestern Medicine Central DuPage Hospital (Winfield)",-41000000,"prorated"),
    ("Advocate Health","Advocate Illinois Masonic Medical Center",-35000000,""),
    ("Sinai Chicago","Mount Sinai Hospital",78000000,"surplus"),
    ("Franciscan","Franciscan Health Olympia Fields",16000000,"surplus; prorated"),
    ("St. Bernard","St. Bernard Hospital",12000000,"surplus"),
    ("Holy Cross","Holy Cross Hospital",11000000,"surplus"),
    ("Endeavor Health (NorthShore)","Swedish Hospital",11000000,"surplus"),
]:
    r(lw, system=sys_, entity_name=ent, metric="lown_fair_share_annual", value=v, notes=note)
r(lw, system="Rush", entity_name="Rush University Medical Center", metric="real_estate_owned", value=406000000, notes="Report notes Rush owns $406M real estate; no fair share figure given")
st = dict(lw); st["source_location"] = "Statewide totals"
for m, v in [("il_tax_benefits_total",2300000000),("il_tax_benefit_per_hospital",16500000),("il_community_investment_total",1400000000),
             ("il_community_investment_per_hospital",10300000),("il_fair_share_deficit_total",-1300000000),
             ("il_ci_financial_assistance",617000000),("il_ci_subsidized_health_services",564000000),("il_ci_community_health_improvement",124000000),
             ("il_ci_cash_inkind_contributions",94000000),("il_ci_community_building",18000000),
             ("il_tax_federal_income",819000000),("il_tax_local_property",448000000),("il_tax_sales",402000000),("il_tax_state_income",332000000),
             ("il_tax_exempt_donations",135000000),("il_tax_exempt_bonds",126000000),("il_tax_federal_unemployment",7000000)]:
    r(st, system="ILLINOIS STATEWIDE", entity_name="All IL private nonprofit hospitals (140)", metric=m, value=v)
r({**st, "unit":"pct"}, system="ILLINOIS STATEWIDE", entity_name="All IL private nonprofit hospitals (140)", metric="il_pct_hospitals_in_deficit", value=63)
r({**st, "unit":"count"}, system="ILLINOIS STATEWIDE", entity_name="All IL private nonprofit hospitals (140)", metric="il_hospital_count", value=140)
r({**st, "unit":"text"}, system="ILLINOIS STATEWIDE", entity_name="Methodology", metric="lown_methodology",
  value="7 exemption types: fed income, state income, FUTA, sales, property, tax-exempt donations, tax-exempt bonds. Net income from CMS cost reports; donations/bonds from 990; property tax from PTAX-300-H(A) where available (56 hospitals) else imputed at national median rate. Community investment = Sch H financial assistance, community health improvement, subsidized health services, contributions to community groups, community building. Excludes research, training, Medicaid shortfall. Group filers prorated by share of system charity care.")

# Lown 2024 national page (FY2021 data)
l24 = dict(source_type="Lown", source_doc="Lown Hospital Fair Share Spending 2024 (FY2021 data)", source_url=LOWN_24, retrieval_method=WF, unit="USD", fiscal_year_end="2021", source_location="Named hospitals/systems")
r(l24, system="Sinai Chicago", entity_name="Mount Sinai Hospital", metric="lown_fair_share_annual", value=67000000, notes="surplus")
r(l24, system="Sinai Chicago", entity_name="Sinai Chicago (2 hospitals)", metric="lown_fair_share_annual", value=71000000, notes="surplus")
r(l24, system="Advocate Health", entity_name="Advocate Health (23 hospitals, multi-state)", metric="lown_fair_share_annual", value=-479000000, notes="system-wide, not IL only")
r(l24, system="ILLINOIS STATEWIDE", entity_name="IL hospitals (109)", metric="il_fair_share_deficit_total", value=-1500000000)
r({**l24, "unit":"pct"}, system="ILLINOIS STATEWIDE", entity_name="IL hospitals (109)", metric="il_pct_hospitals_in_deficit", value=86)
r({**l24, "unit":"pct"}, system="NATIONAL", entity_name="Lown fair share threshold", metric="lown_fair_share_threshold_pct_expenses", value=5.9, notes="Hospitals spending >=5.9% of expenses on FA + community investment deemed fair share")
r({**l24, "unit":"pct"}, system="NATIONAL", entity_name="2,425 private nonprofit hospitals", metric="avg_community_investment_pct_budget", value=3.87)
r(l24, system="NATIONAL", entity_name="2,425 private nonprofit hospitals", metric="national_fair_share_deficit_total", value=-25700000000)

# ---------- IHPA memo (March 2026) ----------
ih = dict(source_type="IHPA", source_doc="IHPA Illinois State Non-Profit Hospital Report memo (Mar 2026)", source_url=IHPA, retrieval_method=WF, unit="USD",
          notes="IHPA identity not verified; treat as advocacy source; figures attributed to 990s/Lown")
r(ih, system="Northwestern Medicine", entity_name="Northwestern Memorial", fiscal_year_end="2024", metric="annual_revenue_per_ihpa", value=10050000000)
r(ih, system="Northwestern Medicine", entity_name="Northwestern Memorial", fiscal_year_end="2024", metric="executive_pay_total_per_ihpa", value=23000000)
r(ih, system="Northwestern Medicine", entity_name="Northwestern Memorial", fiscal_year_end="2024", metric="compensation_reportable", value=4300000, person="Howard Chrisman", person_title="CEO", notes="'over $4.3M' per IHPA, 2024")
r(ih, system="Northwestern Medicine", entity_name="Northwestern Memorial", fiscal_year_end="2024", metric="compensation_reportable", value=6000000, person="Dean Harrison", person_title="Executive Chairman", notes="'over $6M' per IHPA, 2024")
r({**ih, "unit":"count"}, system="Northwestern Medicine", entity_name="Northwestern Memorial", fiscal_year_end="2024", metric="employees_paid_7_figures", value=17, notes="17+")
r({**ih, "unit":"pct"}, system="Northwestern Medicine", entity_name="Northwestern Memorial", fiscal_year_end="2024", metric="revenue_growth_pct", value=9.91)
r(ih, system="Advocate Health", entity_name="Advocate", fiscal_year_end="2024", metric="annual_revenue_per_ihpa", value=7810000000)
r({**ih, "unit":"count"}, system="Advocate Health", entity_name="Advocate", fiscal_year_end="2024", metric="employees_paid_7_figures", value=11)
r({**ih, "unit":"pct"}, system="Advocate Health", entity_name="Advocate", fiscal_year_end="2024", metric="revenue_growth_pct", value=13.12)
r(ih, system="Rush", entity_name="Rush", fiscal_year_end="2023", metric="annual_revenue_per_ihpa", value=3000000000)
r(ih, system="Rush", entity_name="Rush", fiscal_year_end="2023", metric="executive_pay_total_per_ihpa", value=36000000, notes="'nearly $36M'")
r(ih, system="UChicago Medicine", entity_name="UChicago Medicine", fiscal_year_end="2023", metric="annual_revenue_per_ihpa", value=3210000000)
r(ih, system="UChicago Medicine", entity_name="UChicago Medicine", fiscal_year_end="2023", metric="compensation_reportable", value=3500000, person="(President)", person_title="President", notes="'nearly $3.5M'")
r(ih, system="Loyola Medicine", entity_name="Loyola", fiscal_year_end="2023", metric="annual_revenue_per_ihpa", value=1650000000)
r(ih, system="Endeavor Health (NorthShore)", entity_name="NorthShore", fiscal_year_end="2024", metric="annual_revenue_per_ihpa", value=2290000000)
r(ih, system="Endeavor Health (NorthShore)", entity_name="NorthShore", fiscal_year_end="2024", metric="executive_pay_total_per_ihpa", value=30000000, notes="'exceeded $30M'")
r({**ih, "unit":"count"}, system="Endeavor Health (NorthShore)", entity_name="NorthShore", fiscal_year_end="2024", metric="employees_paid_7_figures", value=16)
r({**ih, "unit":"pct"}, system="Endeavor Health (NorthShore)", entity_name="NorthShore", fiscal_year_end="2024", metric="revenue_growth_pct", value=5.4)
r(ih, system="OSF", entity_name="OSF HealthCare", fiscal_year_end="2023", metric="annual_revenue_per_ihpa", value=3910000000)
r(ih, system="OSF", entity_name="OSF Saint Francis", fiscal_year_end="2020-2022avg", metric="lown_fair_share_annual", value=-58000000)

# ---------- IHA Chicago community benefit summary (FY2014-2015) ----------
ia = dict(source_type="IHA", source_doc="IHA: Value of Benefits Provided by Nonprofit Hospitals in City of Chicago (filings FY ending 12/2014-9/2015)",
          source_url=IHA, retrieval_method=WF, unit="USD", fiscal_year_end="2014-2015", system="CHICAGO AGGREGATE", entity_name="31 Chicago nonprofit hospitals reporting to IL AG",
          notes="Hospital-industry source; shows structure of 'community benefit' claim. 12 Chicago hospitals exempt from reporting; system filings include 5 non-Chicago hospitals")
for m, v in [("cb_total",1818000000),("cb_government_sponsored_programs",903000000),("cb_education",221000000),("cb_bad_debt",226000000),
             ("cb_charity_care_at_cost",220000000),("cb_research",120000000),("cb_subsidized_health_services",91000000),("cb_other",16000000),
             ("cb_donations",7000000),("cb_language_assistance",10000000),("cb_volunteers",4000000)]:
    r(ia, metric=m, value=v)

last = A.add(*rows)
print("rows now:", A.count(), "last id:", last)
