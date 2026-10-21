# Prompt for an independent check of Report No. 1

Give the model the repository and the text under the line.

---

You are checking a dataset behind a published claim for errors the author did not catch. Assume there are more. You are given the error patterns already found; your job is to find the remaining instances of those patterns and any pattern not yet on the list.

WHERE THINGS ARE
Repository: https://github.com/freemarket/everythingisbroken (clone it). Live site: https://everythingisbroken.org/reports/hospital-ceo-pay/
- data/hospital-ceo-pay/systems_rollup.csv: one row per "system" (a filing or a set of filings reporting the same chief executive). Columns that matter: system_key, lead_filer, lead_ein, state, n_filers, member_eins, member_names, total_revenue, total_expenses, charity_care_net, charity_care_pct_computed, ceo_name, ceo_title, ceo_comp_total, ceo_confidence, ceo_pay_pct_of_charity_care, childrens_hospital, zero_charity_care_flag, publishable.
- data/hospital-ceo-pay/filers_latest.csv: one row per filing entity (EIN), latest fiscal year. Columns: ein, name, fye, object_id, group_return, city_state, total_revenue, total_expenses, charity_care_net, charity_care_pct (the hospital's own filed percentage), medicaid_shortfall_net, total_cb_net, bad_debt, facilities, ceo_name, ceo_title, ceo_comp_total, ceo_confidence, top_paid_name, top_paid_title, top_paid_total.
- data/hospital-ceo-pay/hospital_data.csv.gz: the master table, one row per figure. For Part VII people: metric is compensation_reportable, compensation_related_org or compensation_other, with person and person_title. For Schedule H: metrics named sch_h_7a_… through sch_h_7k_…, sch_h_bad_debt, sch_h_facilities_list. Filter status == active and retrieval_method starting "IRS bulk". Match fiscal_year_end to the filer's fye in filers_latest.csv.
- data/hospital-ceo-pay/ceo_overrides.csv and rollup_overrides.csv: every manual decision so far, with its reason. Read them first; they show what kinds of problems exist.
- data/hospital-ceo-pay/headline_exclusions.csv: specialty filers kept out of the headline count.
- data/hospital-ceo-pay/ceo_pay_exceeds_charity_care.csv: the headline list, with a ProPublica link to each filing.
- pipeline/REPRODUCTION_MANUAL.md: the method. Section 6 has the decision rules; section 7 item 9 records the audit already done.
- pipeline/build_systems.py: the code that picks the chief executive and assembles systems.
- Every filing can be read on ProPublica Nonprofit Explorer: https://projects.propublica.org/nonprofits/organizations/<EIN without dash>/<object_id>/full. Part VII lists officers and pay; Schedule H Part I line 7a is charity care; Schedule R lists related organizations; Schedule H Part VI and Schedule O are narrative.

THE CLAIM BEING CHECKED
The headline sentence in reports/hospital-ceo-pay/summary.json: "N nonprofit hospital chief executives were paid more than their hospitals gave in charity care," among general hospital systems with revenue over $100 million. CEO pay is Form 990 Part VII columns D+E+F. Charity care is Schedule H line 7a column (e), at cost, net.

THE FIVE WAYS IT HAS BEEN WRONG SO FAR. FIND THE REST.

1. A parent or regional executive's pay sitting on a subsidiary hospital's return, compared with that one hospital's charity care.
   Examples found: Banner Health's CEO ($9.05M) on Wyoming Medical Center's return; BayCare's CEO on St Anthony's; Trinity Health's regional president on Holy Cross Fort Lauderdale; Mount Sinai's CEO on South Nassau; a management company's CEO on Baptist Hospitals of Southeast Texas.
   Where to look: in systems_rollup.csv, rows with n_filers == 1 whose ceo_title names another organization, a region, a division, a "system", "ministry market", or "ex-officio"; rows where ceo_comp_total is large relative to total_revenue (over 0.5%); and rows where the same ceo_name with the same ceo_comp_total to the dollar appears in Part VII of a different filer (join on person and the three compensation metrics in hospital_data.csv.gz). When you find one, check Schedule R of the hospital's filing: if it lists a parent, the executive is probably the parent's.

2. One person split into several rows because filings spell the name differently.
   Examples found: "BRENDAN CARR 1", "BRENDAN CARR 1 MD", "BRENDAN CARR MD", "Brendan G Carr MD 1" (five rows for Mount Sinai); "HeinrichKerry" run together; "Cheryl Nester Wolfe" with and without an initial; "Timothy" vs "Tim".
   Where to look: group systems_rollup.csv rows by surname plus first initial plus ceo_comp_total rounded to the dollar; any group with more than one row is one person. Also look for names with digits, missing spaces, or credentials glued on.

3. The wrong person picked as chief executive from Part VII.
   Examples found: a retired CEO titled "Senior Advisor (Retired Pres./CEO)"; a departing CEO's final-year payout taken over the successor because the end date was written "THRU JUNE 2024" or "(TERM 12/24)" instead of in the form the rule matched; a board member whose title says "Pres./CEO MHCC Flint" (another hospital's CEO) taken over the hospital's own "President & CEO, part year".
   Where to look: ceo_title containing any date, "thru", "through", "until", "term", "end", "interim", "acting", "former", "fmr", "frmr", "retired", "emerit", "part year", "pt yr", "eff", "beg", "as of", "start"; rows where ceo_confidence ends in _multiple (more than one CEO-titled person on the filing); rows where top_paid_name differs from ceo_name and top_paid_title contains CEO or President. For each, read Part VII on ProPublica and say who the chief executive at fiscal year end actually was and what they were paid.

4. Charity care reported on a line other than 7a, so 7a understates it.
   Nothing confirmed yet, but 64 filings with tiny 7a next to large 7c (other means-tested programs) or 7g (subsidized health services) had their Part VI narratives read. Check the ones not yet read: rows where charity_care_net is under 10% of (sch_h_7c_… + sch_h_7g_…), revenue under $100M, and rows where charity_care_pct (filed) differs from charity_care_pct_computed by more than half a point. Read Schedule H Part VI and Schedule O for sentences saying financial assistance is "included in", "reported on", or "classified as" another line or bad debt.

5. A filing that is not a normal operating year or not a general hospital.
   Examples found: HSHS Sacred Heart Eau Claire and St Joseph's Chippewa Falls (closed March 2024; expenses double revenue); rehabilitation, long-term acute care, cancer, respiratory, behavioral and hospice filers in a list meant for general hospitals; foundations and joint-venture partners whose "expenses" are not hospital operations.
   Where to look: total_expenses / total_revenue above 1.35 or below 0.65; facilities (in filers_latest.csv) naming rehabilitation, specialty, psychiatric, behavioral, children's, hospice, LTACH, surgical; lead_filer names with "Foundation", "Ministries", "Holdings"; charity_care_pct_computed above 20%. Also check for hospitals that merged or changed EIN during the year (Schedule O usually says).

KNOWN AND ACCEPTED, DO NOT REPORT AS ERRORS
- Systems whose hospitals file under their own local presidents appear as several rows, one per president, with the parent's executives attributed to no hospital. This is stated in the method. Report it only where a row's executive is not that hospital's own (pattern 1).
- Twelve multi-filer systems sum members with different fiscal year-ends. Documented.
- Children's hospitals are ranked but excluded from the headline count. Documented.

HOW TO WORK
Start with the rows of ceo_pay_exceeds_charity_care.csv and run all five patterns against each, reading the filing on ProPublica for every one. Then run patterns 1, 2, 3 and 5 as queries across all of systems_rollup.csv where publishable == yes, and read the filings for everything the queries flag. Then take the 40 largest systems by revenue and check patterns 1 through 3 by reading their filings, because errors there move the medians on the report page even if they are not on the headline list.

WHAT TO HAND BACK
A table, one row per finding: EIN; organization; pattern number (1 to 5, or "new"); what the table says (column and value); what the filing says, with the schedule, part and line; whether it changes the headline count, changes a figure, or is cosmetic; and the fix, written as a row for ceo_overrides.csv (ein, fye, ceo_name_override or blank to exclude, reason) or rollup_overrides.csv (ein, fye, action, system_key_override, reason) in the format those files use. Then: the headline count you believe is supportable and why, and any pattern you found that is not on the list above. Do not soften findings and do not assume anything is correct because the method says it is.
