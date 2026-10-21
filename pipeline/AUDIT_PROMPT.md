# Prompt for an independent check of Report No. 1

Give the model this repository (or the files named below) and the text under the line.

---

You are auditing a dataset and a published claim before it goes public. Treat everything you are given as suspect, including the stated method. Your job is to find errors, not to confirm the work.

THE CLAIM
The headline sentence in reports/hospital-ceo-pay/summary.json ("N nonprofit hospital chief executives were paid more than their hospitals gave in charity care"). The claim covers general hospital systems in the United States with total revenue over $100 million, children's hospitals and specialty hospitals excluded, using the hospitals' own IRS Form 990 filings for the latest fiscal year available in the IRS 2025 and 2026 bulk XML releases.

DEFINITIONS USED
CEO pay = Form 990 Part VII Section A, columns D + E + F (reportable compensation from the organization, from related organizations, and other compensation) for the person identified as chief executive.
Charity care = Schedule H Part I line 7a, "financial assistance at cost," column (e), net of offsetting revenue. Not bad debt (Part III), not Medicaid shortfall (line 7b).
A row = a filing, or the set of filings that report the same chief executive, combined; revenue, expenses and charity care summed; CEO counted once. Hand-maintained override files join or split filings the rule gets wrong, or exclude a filer from CEO figures with a reason.

FILES
data/hospital-ceo-pay/systems_rollup.csv        one row per system (the table the claim is computed from)
data/hospital-ceo-pay/filers_latest.csv         one row per filing entity (EIN), latest fiscal year
data/hospital-ceo-pay/hospital_data.csv.gz      the master table: one row per figure, with form/schedule/part/line and the IRS object ID of the filing
data/hospital-ceo-pay/ceo_overrides.csv         manual decisions about who the CEO is, or that no CEO figure should be used
data/hospital-ceo-pay/rollup_overrides.csv      manual decisions about which filings form one row
data/hospital-ceo-pay/headline_exclusions.csv   specialty filers left out of the headline count
data/hospital-ceo-pay/ceo_pay_exceeds_charity_care.csv   the headline list
pipeline/REPRODUCTION_MANUAL.md                 the full method, including the decision rules in section 6 and the audit record in section 7
pipeline/build_systems.py                       the code that applies the rules

WHAT TO CHECK, IN THIS ORDER
1. For each row of the headline list: open the filing on ProPublica Nonprofit Explorer (the URL is in the row) and verify, from the filing itself, (a) the person named is the chief executive of that filer for that fiscal year and not a former, retired, interim, part-year, or parent- or regional-organization executive; (b) the pay figure equals Part VII columns D+E+F for that person; (c) the charity care figure equals Schedule H Part I line 7a column (e); (d) the organization is a general acute-care hospital or system, not a specialty, rehabilitation, long-term acute care, psychiatric, cancer or hospice facility; (e) the filing covers a normal operating year, not a closure, merger or wind-down. Report every discrepancy with the filing page and line that contradicts the table.
2. For each row of the headline list: determine whether the filer is part of a larger health system whose other hospitals file separately, and whether the person named is that larger system's executive rather than this hospital's. Evidence: Schedule R, shared officers across filings, the system's own website. A system executive's pay compared with one hospital's charity care is an error. List every such case with the parent and sibling EINs.
3. Look for the opposite error: rows that were joined but should not have been (two unrelated organizations whose chief executives share a name).
4. Sample 40 rows from systems_rollup.csv that are NOT on the headline list, chosen to include the 20 largest by revenue and 20 at random, and run checks 1(a) through 1(e) on them. Errors here change the ranking and the medians even if they do not change the headline count.
5. Check the decision rules in section 6 of the manual against what you saw. Where a rule produces a wrong answer, say which rule, give the case, and propose the narrower rule that would fix it without breaking the cases that are right.
6. Check the arithmetic: recompute charity_care_pct_computed and ceo_pay_pct_of_charity_care for every row of the headline list from the underlying figures, and recompute the headline count from systems_rollup.csv applying the stated filters (total_revenue >= 100000000; childrens_hospital != yes; publishable == yes; lead_ein not in headline_exclusions.csv; ceo_pay_pct_of_charity_care > 100). Report the number you get.
7. Report anything else that looks wrong, including things the method does not account for.

OUTPUT
A table with one row per finding: EIN, organization, what the table says, what the filing says, the page or line in the filing, severity (changes the headline count / changes a figure / cosmetic), and the fix. Then a one-paragraph verdict on whether the headline claim is supportable as stated, and if not, what number you believe is supportable and why. Do not soften findings. If you could not verify something, say so rather than assuming it is correct.
