"""Parse IRS 990 e-file XML (TY2020+ schema) for hospital filings.
Extracts header, Form 990 financial summary, Part VII compensation, and Schedule H Parts I, II, III, V.
Output: list of flat dict rows suitable for hospital_data.csv (via add_rows), plus a one-row summary dict.
"""
import re, sys, json
import xml.etree.ElementTree as ET

NS = {'i': 'http://www.irs.gov/efile'}

def _t(el, path):
    if el is None: return None
    x = el.find(path, NS)
    return x.text.strip() if x is not None and x.text is not None else None

def _n(el, path):
    v = _t(el, path)
    if v is None: return None
    try:
        return int(v) if re.fullmatch(r'-?\d+', v) else float(v)
    except ValueError:
        return v

SCHH_PARTI = [
    ('7a', 'FinancialAssistanceAtCostTyp', 'sch_h_7a_financial_assistance_at_cost'),
    ('7b', 'UnreimbursedMedicaidGrp', 'sch_h_7b_medicaid'),
    ('7c', 'UnreimbursedCostsGrp', 'sch_h_7c_other_means_tested'),
    ('7d', 'TotalFinancialAssistanceTyp', 'sch_h_7d_total_fa_and_means_tested'),
    ('7e', 'CommunityHealthServicesGrp', 'sch_h_7e_community_health_improvement'),
    ('7f', 'HealthProfessionsEducationGrp', 'sch_h_7f_health_professions_education'),
    ('7g', 'SubsidizedHealthServicesGrp', 'sch_h_7g_subsidized_health_services'),
    ('7h', 'ResearchGrp', 'sch_h_7h_research'),
    ('7i', 'CashAndInKindContributionsGrp', 'sch_h_7i_cash_inkind_contributions'),
    ('7j', 'TotalOtherBenefitsGrp', 'sch_h_7j_total_other_benefits'),
    ('7k', 'TotalCommunityBenefitsGrp', 'sch_h_7k_total_community_benefits'),
]

def parse_file(path):
    tree = ET.parse(path); root = tree.getroot()
    hdr = root.find('i:ReturnHeader', NS); data = root.find('i:ReturnData', NS)
    filer = hdr.find('i:Filer', NS)
    out = {
        'object_id': path.split('/')[-1].replace('_public.xml', ''),
        'ein': _t(filer, 'i:EIN'),
        'name': _t(filer, 'i:BusinessName/i:BusinessNameLine1Txt'),
        'name2': _t(filer, 'i:BusinessName/i:BusinessNameLine2Txt'),
        'city': _t(filer, 'i:USAddress/i:CityNm'),
        'state': _t(filer, 'i:USAddress/i:StateAbbreviationCd'),
        'zip': _t(filer, 'i:USAddress/i:ZIPCd'),
        'tax_period_end': _t(hdr, 'i:TaxPeriodEndDt'),
        'tax_period_begin': _t(hdr, 'i:TaxPeriodBeginDt'),
        'return_ts': _t(hdr, 'i:ReturnTs'),
        'return_type': _t(hdr, 'i:ReturnTypeCd'),
        'tax_year': _t(hdr, 'i:TaxYr'),
    }
    f990 = data.find('i:IRS990', NS)
    if f990 is not None:
        out.update({
            'group_return': _t(f990, 'i:GroupReturnForAffiliatesInd'),
            'total_revenue': _n(f990, 'i:CYTotalRevenueAmt'),
            'total_expenses': _n(f990, 'i:CYTotalExpensesAmt'),
            'revenue_less_expenses': _n(f990, 'i:CYRevenuesLessExpensesAmt'),
            'total_assets_eoy': _n(f990, 'i:TotalAssetsEOYAmt'),
            'total_liabilities_eoy': _n(f990, 'i:TotalLiabilitiesEOYAmt'),
            'net_assets_eoy': _n(f990, 'i:NetAssetsOrFundBalancesEOYAmt'),
            'employee_count': _n(f990, 'i:TotalEmployeeCnt'),
            'officer_comp_total': _n(f990, 'i:CompCurrentOfcrDirectorsGrp/i:TotalAmt'),
            'other_salaries_total': _n(f990, 'i:OtherSalariesAndWagesGrp/i:TotalAmt'),
            'indiv_over_100k_cnt': _n(f990, 'i:IndivRcvdGreaterThan100KCnt'),
            'investment_income': _n(f990, 'i:CYInvestmentIncomeAmt'),
            'program_service_revenue': _n(f990, 'i:CYProgramServiceRevenueAmt'),
            'contributions': _n(f990, 'i:CYContributionsGrantsAmt'),
            'savings_temp_cash_eoy': _n(f990, 'i:SavingsAndTempCashInvstGrp/i:EOYAmt'),
            'cash_eoy': _n(f990, 'i:CashNonInterestBearingGrp/i:EOYAmt'),
            'investments_pub_securities_eoy': _n(f990, 'i:InvestmentsPubTradedSecGrp/i:EOYAmt'),
            'investments_other_sec_eoy': _n(f990, 'i:InvestmentsOtherSecuritiesGrp/i:EOYAmt'),
        })
        people = []
        for p in f990.findall('i:Form990PartVIISectionAGrp', NS):
            people.append({
                'person': _t(p, 'i:PersonNm') or _t(p, 'i:BusinessName/i:BusinessNameLine1Txt'),
                'title': _t(p, 'i:TitleTxt'),
                'hours': _n(p, 'i:AverageHoursPerWeekRt'),
                'officer': _t(p, 'i:OfficerInd'), 'key_employee': _t(p, 'i:KeyEmployeeInd'),
                'highest_comp': _t(p, 'i:HighestCompensatedEmployeeInd'), 'former': _t(p, 'i:FormerOfcrDirectorTrusteeInd'),
                'comp_org': _n(p, 'i:ReportableCompFromOrgAmt') or 0,
                'comp_related': _n(p, 'i:ReportableCompFromRltdOrgAmt') or 0,
                'comp_other': _n(p, 'i:OtherCompensationAmt') or 0,
            })
        # Schedule O: harvest titles for people whose Part VII title says 'See Schedule O'
        so = data.find('i:IRS990ScheduleO', NS)
        so_titles = {}
        if so is not None:
            for g in so.findall('i:SupplementalInformationDetail', NS):
                ref = _t(g, 'i:FormAndLineReferenceDesc') or ''; txt = _t(g, 'i:ExplanationTxt') or ''
                m = re.match(r'Form 990, Part VII, Section A\s+(.+?)\s+(ADDITIONAL POSITIONS HELD|TITLES?)', ref, re.I)
                if m:
                    key = re.sub(r'[^A-Z]', '', m.group(1).upper())
                    titles = re.findall(r'Title:\s*([^,;]+)', txt)
                    so_titles[key] = so_titles.get(key, []) + [t.strip() for t in titles]
        for p in people:
            if p['person'] and re.search(r'SCHEDULE O', p['title'] or '', re.I):
                # match on surname + first initial letters regardless of order
                nm = re.sub(r'[^A-Z ]', '', p['person'].upper()).split()
                for key, titles in so_titles.items():
                    if all(part in key for part in nm if len(part) > 2):
                        p['sched_o_titles'] = ' | '.join(titles); break
        out['people'] = people
    h = data.find('i:IRS990ScheduleH', NS)
    if h is not None:
        sh = {}
        for line, tag, key in SCHH_PARTI:
            g = h.find(f'i:{tag}', NS)
            if g is None: continue
            sh[key] = {
                'total': _n(g, 'i:TotalCommunityBenefitExpnsAmt'),
                'offset': _n(g, 'i:DirectOffsettingRevenueAmt'),
                'net': _n(g, 'i:NetCommunityBenefitExpnsAmt'),
                'pct': _n(g, 'i:TotalExpensePct'),
                'line': line,
            }
        cb = h.find('i:TotalCommuntityBuildingActyGrp', NS)
        sh['community_building_total'] = _n(cb, 'i:TotalCommunityBenefitExpnsAmt') if cb is not None else None
        sh['bad_debt'] = _n(h, 'i:BadDebtExpenseAmt')
        sh['bad_debt_fap_eligible'] = _n(h, 'i:BadDebtExpenseAttributableAmt')
        sh['medicare_revenue'] = _n(h, 'i:ReimbursedByMedicareAmt')
        sh['medicare_cost'] = _n(h, 'i:CostOfCareReimbursedByMedcrAmt')
        sh['medicare_shortfall'] = _n(h, 'i:MedicareSurplusOrShortfallAmt')
        # FPG thresholds
        free = None
        for tag, v in [('Percent100Ind', 100), ('Percent150Ind', 150), ('Percent200Ind', 200)]:
            if _t(h, f'i:{tag}') == 'X': free = v
        if free is None:
            free = _n(h, 'i:FreeCareOthPercentageGrp/i:FreeCareOtherPct')
        disc = None
        for tag, v in [('Percent200DiscountedInd', 200), ('Percent250Ind', 250), ('Percent300Ind', 300), ('Percent350Ind', 350), ('Percent400Ind', 400)]:
            if _t(h, f'i:{tag}') == 'X': disc = v
        if disc is None:
            disc = _n(h, 'i:DiscountedCareOthPercentageGrp/i:DiscountedCareOtherPct')
        sh['fpg_free_pct'] = free; sh['fpg_discount_pct'] = disc
        sh['facility_count'] = _n(h, 'i:HospitalFacilitiesCnt')
        facs = []
        for g in h.findall('i:HospitalFacilitiesGrp', NS):
            facs.append({'num': _n(g, 'i:FacilityNum'), 'name': _t(g, 'i:BusinessName/i:BusinessNameLine1Txt'),
                         'city': _t(g, 'i:USAddress/i:CityNm'), 'state': _t(g, 'i:USAddress/i:StateAbbreviationCd'),
                         'zip': _t(g, 'i:USAddress/i:ZIPCd'), 'license': _t(g, 'i:StateLicenseNum'),
                         'licensed_hospital': _t(g, 'i:LicensedHospitalInd'), 'er24': _t(g, 'i:EmergencyRoom24HrsInd'),
                         'teaching': _t(g, 'i:TeachingHospitalInd'), 'critical_access': _t(g, 'i:CriticalAccessHospitalInd')})
        sh['facilities'] = facs
        out['sch_h'] = sh
    return out

if __name__ == '__main__':
    print(json.dumps(parse_file(sys.argv[1]), indent=1, default=str))
