# Reproduction manual

Everything Is Broken · Report No. 1 · Dataset as of Oct 18, 2026

This document is a complete, self-contained procedure for rebuilding the nonprofit hospital charity care and executive pay dataset from public sources, with no prior knowledge of this project. Follow it in order.

## 1. Purpose and scope

The dataset answers one question for every nonprofit hospital in the United States: how much free care did it give to patients who could not pay, and how much did it pay its chief executive, as stated in its own filings. From those two figures and the hospital's size, every other figure in the report is derived.

Scope: every organization that filed an IRS Form 990 with Schedule H (the hospital schedule) in the IRS's 2025 and 2026 e-file releases. That is 2,305 distinct filers (by EIN), which after roll-up are about 1,650 health systems. Public hospitals (county, state, VA) do not file Form 990 and are not included. For-profit hospitals do not file Form 990 and are not included.

The data rule, which governs everything below: every figure in the master dataset is either copied from a filing with its exact form, schedule, part, and line recorded, or computed from such figures with the formula stated. The only estimated figures are third-party ones (Lown Institute), and they are tagged by source so they can be excluded.

A second, smaller set of Chicago-specific sources (audited financial statements, Illinois Attorney General filings, Lown) was gathered first and remains in the dataset tagged by `source_type`. The national procedure in Section 5 does not depend on it.

## 2. Definitions

Every term below names the form line it comes from and the element name in the IRS e-file XML (namespace `http://www.irs.gov/efile`, schema version 2024v5.1 for tax year 2024 filings). Dollar amounts are whole dollars. Percentages in the XML are decimals (0.00728 means 0.728 percent).

| Term | Form and line | XML element | Meaning |
| --- | --- | --- | --- |
| Charity care | Schedule H, Part I, line 7a | `IRS990ScheduleH/FinancialAssistanceAtCostTyp` | Free or discounted care given under the hospital's written financial assistance policy, valued at the hospital's cost, not list price. Columns: `TotalCommunityBenefitExpnsAmt` (gross cost), `DirectOffsettingRevenueAmt` (grants received for it), `NetCommunityBenefitExpnsAmt` (net), `TotalExpensePct` (net as share of total expenses, filed by the hospital). The report uses net and the filed percentage. |
| Medicaid shortfall | Schedule H, Part I, line 7b | `UnreimbursedMedicaidGrp` | Cost of treating Medicaid patients minus Medicaid payments. |
| Community benefit, total | Schedule H, Part I, line 7k | `TotalCommunityBenefitsGrp` | Sum of 7a through 7i: charity care, Medicaid shortfall, other means-tested programs (7c), community health improvement (7e), health professions education (7f), subsidized health services (7g), research (7h), cash and in-kind contributions (7i). |
| Community building | Schedule H, Part II, line 10 | `TotalCommuntityBuildingActyGrp` (sic, IRS spelling) | Housing, economic development, workforce, and similar. Not part of 7k. |
| Bad debt | Schedule H, Part III, line 2 | `BadDebtExpenseAmt` | Bills the hospital tried and failed to collect. Not community benefit on the IRS form; often added by hospitals in public statements. |
| Medicare shortfall | Schedule H, Part III, line 7 | `MedicareSurplusOrShortfallAmt` | Medicare revenue (`ReimbursedByMedicareAmt`) minus Medicare cost (`CostOfCareReimbursedByMedcrAmt`). Negative is a shortfall. Not community benefit on the IRS form. |
| FPG free-care threshold | Schedule H, Part I, line 3a | `Percent100Ind` / `Percent150Ind` / `Percent200Ind` (checkbox = `X`) or `FreeCareOthPercentageGrp/FreeCareOtherPct` | Family income, as a percent of the federal poverty guideline, below which care is free. |
| FPG discount threshold | Schedule H, Part I, line 3b | `Percent200DiscountedInd` ... `Percent400Ind` or `DiscountedCareOthPercentageGrp/DiscountedCareOtherPct` | Income below which care is discounted. |
| Facility count and list | Schedule H, Part V, Section A | `HospitalFacilitiesCnt`; one `HospitalFacilitiesGrp` per facility with `BusinessName`, `USAddress`, `StateLicenseNum`, and type indicators (`ChildrensHospitalInd`, `TeachingHospitalInd`, `CriticalAccessHospitalInd`, `EmergencyRoom24HrsInd`) | Which hospitals the filing covers. |
| Total revenue, expenses, net | Form 990, Part I, lines 12, 18, 19 | `IRS990/CYTotalRevenueAmt`, `CYTotalExpensesAmt`, `CYRevenuesLessExpensesAmt` | Current-year totals. |
| Net assets, total assets | Form 990, Part I, lines 22, 20 | `NetAssetsOrFundBalancesEOYAmt`, `TotalAssetsEOYAmt` | End of year. |
| Group return | Form 990, Part I, line H(a) | `GroupReturnForAffiliatesInd` | `true` means one filing covers several hospitals. Figures are then system-wide. |
| Compensation, per person | Form 990, Part VII, Section A | One `Form990PartVIISectionAGrp` per person: `PersonNm`, `TitleTxt`, `ReportableCompFromOrgAmt` (col D), `ReportableCompFromRltdOrgAmt` (col E), `OtherCompensationAmt` (col F), and indicator flags `OfficerInd`, `KeyEmployeeInd`, `HighestCompensatedEmployeeInd`, `FormerOfcrDirectorTrusteeInd` | Total compensation for the report is D + E + F. |
| Schedule O | Schedule O | `IRS990ScheduleO/SupplementalInformationDetail` with `FormAndLineReferenceDesc` and `ExplanationTxt` | Free-text supplement. Some filers put every Part VII title here. |
| Charity care as % of expenses (system) | computed | sum of member 7a net divided by sum of member Form 990 line 18 | Computed the same way for every row, single-filer or not. The filed `TotalExpensePct` is kept in `filers_latest.csv` for comparison; 24 single filers differ from the computed figure by more than half a point, mostly foundations and joint-venture partners whose expenses are not hospital operations. |
| CEO pay as % of charity care | computed | CEO total compensation divided by system charity care net, times 100 | Over 100 means one person was paid more than the system gave in charity care. |

**What "nonprofit" means here.** A 501(c)(3) organization: no shareholders, no federal income tax, and in nearly all states no property or sales tax. Surpluses stay inside and may go to buildings, investments, and salaries. The label does not imply charity.

## 3. Environment and access

- A Linux or macOS machine with Python 3.10 or later (standard library only; no packages required), `curl`, and `unzip`. The IRS zips use Deflate64 compression, which Python's `zipfile` cannot read; the system `unzip` can.
- About 10 GB of free disk during the run (each batch unpacks to about 3 GB temporarily; the kept Schedule H filings total 1.5 GB; the master CSV is 170 MB).
- Network access to `apps.irs.gov` (bulk XML and index files) and `projects.propublica.org` (API and rendered pages for cross-checks). If working inside a sandbox with a domain allowlist, both must be added. Everything else is optional.
- No credentials, API keys, or accounts. All sources are public.

Time: the full national pull, parse, and load takes under 30 minutes of machine time. The manual review steps in Section 6 took about two hours for the systems above $1B in revenue.

**Alternate route when bulk download is unavailable.** ProPublica's Nonprofit Explorer renders every Schedule H as an HTML page at `https://projects.propublica.org/nonprofits/full_text/<object_id>/IRS990ScheduleH` (it redirects to a signed S3 URL that must be opened in a real browser; automated fetchers are refused). The text of that page can be saved and parsed with `parse_schh.py`. This is how the first nine Chicago filers were done and it produces identical figures, but it is one page per filing and does not scale. ProPublica's XML download (`/nonprofits/download-xml?object_id=...`) is behind a bot check and did not work from any route tried. ProPublica's JSON API (`/nonprofits/api/v2/organizations/<EIN>.json`) works without restriction and gives summary financials for every filing year but not Schedule H.

## 4. Data model

There is one source of truth and several derived tables. Never edit a derived table by hand; change the source or the rule and rebuild.

**`hospital_data.csv`, the master.** Long format, one row per figure, 364,682 rows at this version. Columns:

| Column | Content |
| --- | --- |
| `row_id` | Sequential integer from 1, never reused. Contiguity is checked. |
| `added_at` | UTC timestamp of the append |
| `status` | `active` or `ignore` |
| `ignore_reason` | Why a row is ignored and which row supersedes it |
| `system` | Parent system name (filled for the Chicago rows; blank for bulk rows, where system membership is derived in the roll-up) |
| `entity_name` | Filing entity exactly as on the filing |
| `ein` | `NN-NNNNNNN` |
| `fiscal_year_end` | `YYYY-MM`, or a range like `2020-2022avg` |
| `metric` | Standardized key; see the metric list below |
| `value` | The figure, no thousands separators; text for text metrics |
| `unit` | `USD`, `pct`, `count`, `text` |
| `person`, `person_title` | For compensation rows |
| `source_type` | `IRS990`, `Audit`, `IL_AG`, `Lown`, `IHPA`, `IHA`, `ProPublica` |
| `source_doc` | Filing name, tax year, filing date, IRS object ID |
| `source_location` | Form, schedule, part, line, column |
| `source_url` | Where retrieved |
| `retrieval_method` | `IRS bulk XML parsed by parse_xml.py`, `built-in browser ...`, `API JSON`, `WebFetch summary`, `hand-keyed`, `computed` |
| `notes` | Caveats such as `GROUP RETURN`, officer flags on pay rows |

**The append-only rule.** Rows are never edited or deleted. A wrong value is retired by appending a row with `status = ignore` whose `ignore_reason` names the bad row, then appending the corrected row. `add_rows.py` is the only writer and can only append. Keep a dated backup copy before any bulk load.

**Metric keys written by the bulk loader,** per filing: `filer_city_state`, `group_return`, `total_revenue`, `total_expenses`, `net_income_990`, `total_assets`, `total_liabilities`, `net_assets`, `compensation_current_officers`, `other_salaries_wages`, `investment_income`, `program_service_revenue`, `contributions_and_grants`, `cash_non_interest_bearing_eoy`, `savings_temp_cash_eoy`, `investments_public_securities_eoy`, `investments_other_securities_eoy`, `employee_count`, `indiv_over_100k_cnt`; per person: `compensation_reportable` (col D), `compensation_related_org` (col E), `compensation_other` (col F); per Schedule H line 7a to 7k: `sch_h_<line>_<name>_total_expense`, `_offsetting_revenue`, `_net`, `_pct_total_expense` (the `_pct` value is stored as a percentage, i.e. the XML decimal times 100); plus `sch_h_community_building_total`, `sch_h_bad_debt`, `sch_h_bad_debt_fap_eligible`, `sch_h_medicare_revenue`, `sch_h_medicare_cost`, `sch_h_medicare_shortfall`, `sch_h_fpg_free_pct`, `sch_h_fpg_discount_pct`, `sch_h_facility_count`, `sch_h_facilities_list`.

**Derived tables** (all under `irs/`, rebuilt by `build_systems.py` from the master in seconds):

- `filers_latest.csv`: one row per EIN, latest fiscal year, with the headline fields, the identified CEO and confidence, and flags. 2,305 rows.
- `systems_rollup.csv`: one row per system after roll-up, with summed figures, the CEO counted once, the computed ratios, `childrens_hospital`, `zero_charity_care_flag`, and `publishable`. About 1,650 rows.
- `ceo_unresolved.csv`: filers where the rule found no CEO.
- `ceo_review_large.csv`: for filers above $1B that needed review, the top six Part VII entries and any Schedule O text mentioning CEO, used for the manual pass.

**Override files** (hand-maintained, read by the build): `ceo_overrides.csv` and `rollup_overrides.csv`, described in Section 6.

**Raw inputs kept on disk:** `irs/index_2025.csv`, `irs/index_2026.csv`, `irs/xml/<object_id>_public.xml` (19,245 files), and for the Chicago page route `raw_<ENTITY>_<FY>_SchH.txt`. Every figure can be re-checked against these without network access.

## 5. Procedure

Run in this order. Scripts are in the project folder (`hospital_data/` and `hospital_data/irs/`); the four that matter are quoted or described fully enough to rewrite from this section alone.

**Step 1. Get the IRS index files.** They list every e-filed return in the release with EIN, name, tax period, return type, and the object ID and batch zip that holds it.

```
mkdir -p irs && cd irs
curl -L -o index_2025.csv https://apps.irs.gov/pub/epostcard/990/xml/2025/index_2025.csv
curl -L -o index_2026.csv https://apps.irs.gov/pub/epostcard/990/xml/2026/index_2026.csv
```

Columns: `RETURN_ID, FILING_TYPE, EIN, TAX_PERIOD, SUB_DATE, TAXPAYER_NAME, RETURN_TYPE, DLN, OBJECT_ID, XML_BATCH_ID`. At this version: 748,906 rows for 2025 and 436,239 for 2026; `RETURN_TYPE` is 990, 990EZ, 990PF, or 990T. Only 990 returns carry Schedule H. Check that a few known hospital EINs appear (Northwestern 364724966, Rush 362174823) before continuing.

**Step 2. Download every batch and keep only Schedule H filings.** `fetch_all.sh`, quoted in full:

```bash
#!/bin/bash
set -u
cd irs; mkdir -p xml logs
B2025="01A 02A 03A 04A 05A 05B 06A 07A 08A 09A 10A 11A 11B 11C 11D 12A"
B2026="01A 02A 03A 04A 05A 05B 06A 07A 08A"
for y in 2025 2026; do
  if [ "$y" = 2025 ]; then L="$B2025"; else L="$B2026"; fi
  for b in $L; do
    z="${y}_TEOS_XML_${b}.zip"
    [ -f "done_${z}" ] && continue
    curl -sS -m 900 -L -o "$z" "https://apps.irs.gov/pub/epostcard/990/xml/$y/$z" || { echo "DL FAIL $z"; continue; }
    rm -rf tmp && mkdir tmp
    unzip -q "$z" -d tmp || { echo "UNZIP FAIL $z"; continue; }
    find tmp -name '*.xml' -print0 | xargs -0 grep -l -m1 "IRS990ScheduleH" > "logs/schH_${z}.txt"
    xargs -a "logs/schH_${z}.txt" -I{} mv {} xml/
    rm -rf tmp "$z"; touch "done_${z}"
  done
done
```

The batch list is read from the IRS download page (`https://www.irs.gov/charities-non-profits/form-990-series-downloads`) and will differ in later years. Each batch is 100 to 520 MB and takes 15 to 40 seconds to download and filter. Result at this version: 19,245 files in `irs/xml/`, named `<object_id>_public.xml`. The `done_` marker files make the script resumable.

**Step 3. Parse each filing.** `parse_xml.py` exposes `parse_file(path)` which returns a dict with the header fields, Form 990 summary, a `people` list from Part VII (with Schedule O titles attached where Part VII says "See Schedule O" and Schedule O uses the "Part VII, Section A, \<Name>, Additional Positions Held" format), and a `sch_h` dict with the Part I lines, Part II total, Part III lines, FPG thresholds, facility count and list. It uses only `xml.etree.ElementTree` and the element names in Section 2. Run it on one file to see the structure: `python3 parse_xml.py xml/202601349349304525_public.xml`.

**Step 4. Load into the master.** `load_all.py` walks `irs/xml/`, parses each file, writes one row per figure to `hospital_data.csv` through `add_rows.add()`, records the object ID in `loaded_object_ids.txt` so a re-run skips it, and writes `parse_errors.txt` for any file that fails. Each row's `source_doc` carries the object ID and `source_url` gives both the IRS bulk path and the ProPublica page for the same filing. Expect about 50 filings per second once `add_rows.py` caches the next row ID (the first version re-read the whole file per append and ran at 2 per second; the cached version is what is in the folder now).

**Step 5. Build the analysis tables.** `python3 build_systems.py` reads the master, keeps the latest fiscal year per EIN, applies the CEO rule, applies `ceo_overrides.csv`, rolls filers into systems, applies `rollup_overrides.csv`, computes the flags and ratios, and writes `filers_latest.csv`, `systems_rollup.csv`, and `ceo_unresolved.csv`. Seconds to run; rerun after any change to an override file.

**Step 6. Manual review** of the large filers, per Section 6. This is the only step that is not a script.

**Step 7. Validate** per Section 7.

**Optional: the page route for a single filing.** Open `https://projects.propublica.org/nonprofits/full_text/<object_id>/IRS990ScheduleH` in a browser, save the page's full text, and run `python3 save_and_parse.py <rawfile> <system> <entity> <ein> <fye> <object_id> <filed_date> <notes> <fpg_free> <fpg_discount>`. `parse_schh.py` reads the Part I table from the rendered text by finding the line letters and the trailing percentage cell on each row; blank cells are treated as zero. Used for the first nine filers and for any filing the IRS zips omit.

## 6. Decision rules

These are the judgment calls. Each is a fixed rule in `build_systems.py`, and each has a hand-maintained override file for the cases the rule gets wrong. Change the rule only if a better one is found; otherwise add an override with its reason.

**6.1 Latest filing per EIN.** The releases contain two or three fiscal years per hospital (late and amended filings). The analysis takes the row with the highest `fiscal_year_end` per EIN. Earlier years stay in the master for the trend. Where the releases hold more than one return for the same EIN and fiscal year (38 such pairs at this version, 23 of them at the latest year), only one is used: the one filed last, by the filing date in `source_doc`, then the highest object ID. Every figure for that year, financial and personal, comes from that one return. (Added Oct 22, 2026, after an outside audit found the build could mix a title from one return, pay from another and financials from a third; at Parkview Medical Center, CO, line 7k differed between versions.)

**6.2 CEO identification.** Among the people in Part VII of a filing:

1. Exclude anyone flagged former (`FormerOfcrDirectorTrusteeInd`), or whose title contains FORMER, FRMR, FMR, RETIRED or EMERIT (RETIRED and the abbreviations added Oct 21, 2026, after a retired chief executive listed as 'Senior Advisor (Retired Pres./CEO)' was taken as the CEO), or whose title contains vice president, VP, assistant, associate, regional, division, foundation, auxiliary, medical staff, coach, or "see Schedule" (when no Schedule O title was recovered), or that serves the chief executive rather than being one: advisor to, chief of staff, "to the President/CEO" (added Oct 22, 2026: Dana-Farber's 'Sr. Advisor to President & CEO' had been taken as its CEO over Benjamin Ebert). Also exclude anyone whose title carries a start date after the fiscal year end (AS OF, EFF, BEG, START followed by a month and year): that person was not yet chief executive in the filing year (added Oct 22, 2026: Weirton's 2024 return lists 'COO (CEO AS OF 1/2025)', and the year's CEO was the predecessor, John C. Frankovitch).
2. If the title contains CEO or CHIEF EXEC(UTIVE): tier 0.
3. Else if the title contains PRESIDENT: tier 1.
4. Else if the title contains ADMINISTRATOR or EXECUTIVE DIRECTOR: tier 2.
5. Take the lowest tier present. Within that tier, order is: a candidate whose title carries neither an end date nor an interim marker; then an interim or acting candidate (current at year end); then a candidate whose title carries an end date (termed, term, thru, through, until, til, end, ended, ending, resigned, departed). So a named successor, including one whose title carries a start date (eff., beg., as of, start), stands for the year; an interim stands over a departed executive; and if no current successor is listed, the departing CEO stands. (Rule widened Oct 21, 2026: the first version matched only `TERMED`, `THRU <digit>`, `THROUGH <digit>`, `UNTIL <digit>`, so titles like 'THRU JUNE 2024', '(TERM 12/24)' and 'END 04/24' were not recognized and the departing executive's final-year payout was taken over the successor; 40 rows changed.) Among what remains, the highest total pay (columns D + E + F). A person listed on more than one Part VII line (one line per role) is counted once, taking the maximum single entry per column rather than the sum, because filers repeat the same totals on each line. Confidence is recorded as `ceo_title`, `president_title`, or `administrator_title`, with `_multiple` appended when more than one person matched that tier. No match: `unresolved`.

Why this order: CEO is unambiguous. President is usually the same person at a single hospital but is the wrong person at a university or a system parent, so it is a lower tier and is reviewed. The exclusion list exists because "Regional President" and "Vice President" match PRESIDENT; "Head Coach, Football" was the top-paid person at the University of Miami; and "See Schedule O" tells you nothing.

**6.3 `ceo_overrides.csv`.** Columns: `ein, fye, ceo_name_override, reason, resolved_by, date`. A row with a name forces that person (the name must match the filing's `PersonNm` exactly, including merged title text such as `DONNA HYLAND PRESIDENTCEO`); a row with an empty name excludes the filer from any CEO-based figure (`manual_excluded`). The reason column is mandatory and should say what in the filing supports the decision. Three current overrides rest on public knowledge rather than filing text (Mass General Brigham, Houston Methodist, UHS Binghamton) and are marked as needing a citation before publication. An override with an empty name excludes the filer from every CEO-based figure; this is used when the only chief-executive titles on a filing belong to a parent or regional organization's executives (whose pay is the parent's, not the hospital's), when a successor's reported pay is for a prior role elsewhere, or when the filing covers a closure or wind-down year. Thirty-four rows at this version (Oct 21, 2026). Look up the EIN in `filers_latest.csv`; do not type it from memory (two of the first drafts had wrong EINs).

**6.4 System roll-up, and what a row is.** Filers whose identified CEO has the same normalized name are one system. The name is normalized to uppercase letters, credentials (MD, DO, PhD, RN, FACHE and similar) are dropped, and the words are sorted, so 'Reed MD Monica' and 'REED MONICA', or 'Wandersleben Jennifer' and 'JENNIFER WANDERSLEBEN', are the same key (credentials and word order added Oct 22, 2026; this joined Adventist GlenOaks, Schuyler/Cayuga and the AdventHealth Heartland filers, and one move between hospitals that it would have joined, Hunter Nostrant at MyMichigan, is split by override). A row in `systems_rollup.csv` is therefore a filing, or a set of filings, with the chief executive those filings report; it is not always the whole corporate system. Where a system's hospitals file under their own presidents, each hospital is its own row under its own president and the parent's executives are attributed to no hospital. A shared-officer test (two or more non-clinical Part VII officers in common between filers in different rows) finds 129 such clusters at this version, Providence, Piedmont, Indiana University Health, Bon Secours, Sutter, Novant and Orlando Health among them; assembling them is the main improvement planned for the next edition and must be done filer by filer with the evidence recorded, because the same test also pairs unrelated organizations through common names and joint-venture board seats. Members' revenue, expenses, net assets, employees, charity care, community benefit, bad debt, Medicare shortfall, and facility count are summed; the CEO is counted once; the lead filer is the member with the highest revenue. Known failure modes: two unrelated systems with a CEO of the same name merge (none found above $1B); a system whose subsidiaries list regional presidents does not merge with its parent (handled by exclusions in 6.3 and merges in 6.5); a person who moved between systems during the period can merge them (CHOC and Rady were first split on this reasoning, then joined on Oct 21, 2026 once the filings showed CHOC had become part of Rady Children's Health); the same person spelled differently on different filings fails to merge (nine such joins at this version: Mount Sinai alone was five rows because Brendan Carr is spelled three ways).

**6.5 `rollup_overrides.csv`.** Columns: `ein, fye, action, system_key_override, reason, date`. Actions: `split` (put this filer under the given key instead of its CEO's), `merge` and `join` (same mechanics, used when a parent or a subsidiary should join a named system), `parent` (join the named system and supply its CEO; used for a parent that files no Schedule H and was loaded for Part VII only), `drop_duplicate` (exclude the filer because another filer already contains it). The system's lead filer for naming is the highest-revenue member; the CEO comes from the parent member when one is flagged, else from the lead. Forty-eight rows at this version (Oct 21, 2026). Ten assemble Parkview Health (IN), whose parent filer alone had shown $84,340 of charity care on $1.2B of revenue; the evidence for joining its hospitals, which list local presidents rather than the system CEO in Part VII, is that every one of them lists the Parkview Health CFO in Part VII. When a system's hospitals file under local presidents, a shared officer in Part VII is the filing-based test for membership. Six assemble Advocate Health: the NC parent (EIN 88-4157429, loaded from batch 2025\_11B into `irs/xml_nonH/`) plus Advocate Health and Hospitals, North Side, Condell, Sherman, and the Aurora (WI) group return. Atrium Health is a North Carolina public authority and files no Form 990, so the system's Southeast charity care is not in the data.

**6.6 Group-return deduplication rule.** Within a system, if a filer's name with "Group Return" or "Group" removed equals another member's name, and that other member is the group return, the non-group filer is dropped as contained. This removes the double-count of Cleveland Clinic Foundation inside its group return, and the same at OhioHealth. Tanner Medical Center is not deduplicated: its parent filing and its group return list disjoint facilities (Carrollton; Higgins and Villa Rica), so both are kept and summed. Ashtabula likewise.

**6.7 Flags on every system.**

- `childrens_hospital`: `yes` if every member's name contains CHILDREN, PEDIATRIC, SHRINERS, or ST JUDE; `mixed` if some do. Children's hospitals are reported as a separate category because Medicaid and CHIP cover most low-income children, leaving little uncompensated care to classify as charity; six of the nine systems where the CEO out-earns charity care are children's hospitals, which is a feature of the category, not of those hospitals.
- `zero_charity_care_flag`: on a filer, `yes` if 7a net is zero but 7k is positive. On a system (changed Oct 22, 2026), `yes` if the system's summed 7a is zero with 7k positive, or if flagged members hold more than 10 percent of the system's revenue; the flagged members are listed in `zero_7a_members`. A small member at zero no longer bars a system with positive charity care (Navicent Health Baldwin, 5.5 percent of its system's revenue, whose line 7a cost is fully offset by revenue). Filer-level cases: These are classification cases (Grady, Bethesda, McLeod, UMC New Orleans, Adena, Mount Nittany, Variety Children's), not zero-charity hospitals, and are excluded from rankings until each filing's Part VI narrative is read to find where charity care was booked.
- `publishable`: `yes` only if the CEO confidence is `ceo_title`, `ceo_title_multiple`, or `manual_override`, charity care is positive, and members flagged zero hold no more than 10 percent of the system's revenue. Nothing with `publishable = no` goes in a ranking.

**6.8 Computed ratios.** `charity_care_pct_computed` = system charity care net divided by system total expenses, times 100. `ceo_pay_pct_of_charity_care` = CEO total compensation (D + E + F) divided by system charity care net, times 100. Both are reported alongside the inputs, never alone.

## 7. Validation

Run all of these before using any figure. Each has been run at this version with the result shown.

1. **Row integrity.** `row_id` values in the master are contiguous from 1 with no gaps. Result: 364,682 rows, contiguous. Script: load the CSV, assert `ids == range(1, n+1)`.
2. **Parser against an independent route.** For filings pulled by both the browser page route and the bulk XML route, every Schedule H figure must match to the dollar. Result: UChicago, Loyola, Holy Cross, 133 of 133 values matched. If the IRS schema changes in a later year, redo this on at least three filings before loading.
3. **Parser against the hospital's own audit.** Northwestern's audited statements report cost of charity care of $122,632 thousand for FY2025; Schedule H line 7a gross is $130,076,665 and net $114,908,722. The audit figure sits between gross and net, consistent with a different offset treatment; the Illinois AG filing's $114,908,722 equals Schedule H net exactly. Use the AG or Schedule H figure, not the audit, when comparing hospitals.
4. **Parser against the state filing.** Northwestern's FY2025 Illinois AG community benefit report matches Schedule H line by line: charity care 114,908,722; education 102,305,423; research 72,736,172; subsidized services 61,602,066; bad debt 60,235,509; community building 6,218,881. Any future parse change should preserve this.
5. **Parse errors.** `parse_errors.txt` must be empty. Result: empty.
6. **Override integrity.** Every EIN in both override files must exist in `filers_latest.csv`. Result: all present.
7. **Spot checks against ProPublica summary pages.** Total revenue, expenses, and net assets for a sample of filers agree with the ProPublica organization page for the same object ID. Done for the nine Chicago filers.
8. **Independent pay check against CEO Paycheck** (run 18 Oct; snapshot of their 200 visible rows saved as `ceopaycheck_snapshot_2026-10-18.csv`, results in `ceopaycheck_crosscheck.csv`). Of 129 EINs present in both, 121 agree on the CEO and the pay figure to the dollar. The eight differences are each explained: two where they count an officer the filing marks Former (Intermountain's Allen, Seattle Children's Sperring) and we exclude; two where they count a departing CEO with an end date in the title (Texas Children's Wallace, Centra's Carrier) and we take the named current successor; one where both choices are defensible (UChicago: they take the highest-paid officer, Mark Anderson, the medical dean; we take Thomas Jackiewicz, President of the health system); and three small systems where the parent's CEO does not appear on the hospital filing. The 71 CEO Paycheck rows absent from our table are parent EINs whose hospitals file under subsidiary EINs. The check found two real errors on our side, both fixed: a person listed twice in Part VII had their pay summed (now the maximum single entry per column is taken; this affected Mount Sinai NY and Rochester Regional), and BJC's group return resolved to a physician rather than Richard Liekweg, whose name field carried a prefix.
9. **Outside audit (Oct 21, 2026; fixes Oct 22).** An independent read-only audit reproduced the headline of 75 and found: Weirton's CEO wrong (start date after year end); Navicent excluded by one zero-7a member; Grant Memorial joined to Uniontown because Uniontown's CEO sits on Grant's board ex officio (override excludes her as Grant's CEO); three name-format splits (GlenOaks, Schuyler, AdventHealth Heartland); duplicate returns per EIN and year mixed in the build; cancer centers in the large-system median; and the word "paid" for a figure that includes deferred and other compensation. A review of the audit found one more wrong CEO (Dana-Farber). All are fixed by the rules above, one CEO override (Grant), one rollup override (Nostrant), and two headline exclusions (Memorial Sloan Kettering, Dana-Farber, also now out of the large-system medians). Headline after fixes: 77 of 672. Still open: 7 President-only rows that would exceed 100 percent if the president is the chief executive; the Mass General Brigham override needs a dated citation.
10. **Full-table audit (Oct 21, 2026).** Eight checks run across every ranked row: shared non-clinical officers across rows (129 clusters, recorded as a limitation); the same person split by spelling (nine joins); parent or regional executives on subsidiary returns (title referencing another organization, or identical pay on a larger filer with an executive title; 11 exclusions and 8 joins); end-dated and interim titles (rule widened); line 7a small next to lines 7c and 7g (64 narratives read, none reports charity care elsewhere); mixed year-ends (12 systems, documented); expenses far from revenue (two closures excluded; foundations and joint-venture partners kept out of rate-based lists); filed versus computed percentage (24 gaps, explained); and 50 filings re-parsed from XML with no mismatches.
11. **Sanity distribution.** Median charity care percent across all filers should be near 1 percent and no filer should exceed about 25 percent (Shriners, which is almost entirely charity, is the ceiling at 21 percent). A value far outside that range is a parse error, not a finding.

## 8. Known limits and gaps

- **The IRS zips and index disagree at the edges.** Some filings listed in the index are absent from the zips (Rush and Mount Sinai FY2025 among them). The page route fills these. Check any specific hospital you intend to name.
- **Group returns** report system totals. Northwestern's 1.07 percent covers nine hospitals; Northwestern Memorial Hospital alone is not separable from the IRS filing. Facility-level charity care exists in state filings (Illinois AG Form AG-CBP-1) but the posted PDFs carry those tables as images, not text, and were not captured at this version.
- **Systems split across EINs** are reassembled by the CEO-name rule and overrides. The rule was verified by hand for every multi-filer system above $1B. Below $1B it has not been reviewed.
- **198 filers have no identifiable CEO** by the rule, all below $1B in revenue. They are in the dataset with `ceo_confidence = unresolved` and excluded from any CEO-based figure.
- **Fiscal years differ** (June, August, September, December year ends). "Latest filing" spans calendar 2024 to mid-2025. Twelve multi-filer systems sum members with different year-ends (Northwell, University of Maryland, Gundersen, Aspirus among them); their figures mix two fiscal years.
- **Compensation is the Form 990 figure,** which includes deferred compensation when paid out. A departing executive's final year is often inflated (Northwestern's Harrison, $10.83M in FY2025, marked Former). The multi-year rows in the master allow a three-year average where needed.
- **Charity care at cost depends on each hospital's cost-to-charge method,** which the IRS lets them choose. The filed percentage is comparable across hospitals only to the extent their cost accounting is; this is an industry-wide limitation shared by every study using Schedule H.
- **Children's hospitals** structurally report low charity care and are reported as their own category.
- **Zero charity care on 7a** with large 7k means a classification choice, not zero charity. Ten large filers; excluded until read.
- **The Chicago-only sources** (audit, Illinois AG, Lown, IHPA, IHA) exist only for the nine original filers. IHPA is an advocacy source of unknown funding. Lown's fair-share figures are estimates and are the only estimated numbers in the dataset.
- **Public and for-profit hospitals are absent** because they do not file Form 990. Comparisons are among nonprofits only.

## 9. Results as of this version

The table below predates the Oct 22, 2026 fixes in Section 7, item 9. After them: headline 77 of 672 general hospital systems over $100 million; 1,057 ranked systems; 229 non-children's general systems over $1B with median charity care 1.23 percent and median CEO compensation 7.6 percent of charity care.

The median nonprofit hospital system spends about one percent of expenses on charity care, and that figure is flat across every size of system. All figures from the hospitals' own filings, latest fiscal year (mostly 2024 and 2025), after the roll-up and review in Section 6.

| Measure | Value |
| --- | --- |
| Distinct filers (EINs) | 2,305 |
| Systems after roll-up | 1,653 |
| Charity care as % of expenses, all systems with a figure, median | 1.03 |
| Systems with revenue of $1B or more (excluding zero-7a classification cases) | 306 |
| Of those: charity care median | 1.20 |
| Of those: under 1 percent | 41% |
| Of those: under 2 percent | 73% |
| Publishable $1B+ systems (confident CEO, positive charity care), non-children's | 224 |
| Non-children's: charity care median / CEO pay median / CEO pay as % of charity care median | 1.23% / $2.43M / 8.4% |
| Non-children's: CEO paid more than 50% of system charity care | 10 |
| Non-children's: CEO paid more than 100% | 3 (Parkview, IN; Eisenhower, CA; Northern Light, ME) |
| Publishable children's systems | 25 |
| Children's: charity care median / CEO pay median / ratio median | 0.48% / $2.71M / 27.6% |
| Children's: ratio over 100% | 6 |

**Size does not predict charity care.** Median charity care by revenue band: $10B+ 1.11%, $3B to $10B 1.13%, $1B to $3B 1.28%, $500M to $1B 1.23%, $200M to $500M 1.24%, $50M to $200M 0.63%. Dollar-weighted, the $10B+ tier is 1.23% against 1.60% for the sector. CEO pay rises steeply with size (median $11.3M at $10B+, $0.5M at $50M to $200M) while the charity rate does not, so the ratio falls with size and is a small-hospital statistic; it is used case by case, not as a sector ranking.

**Highest-paid CEOs among publishable systems:** Grossman, NYU Langone, $30.3M (charity care 1.44%, ratio 21%); Corwin, NewYork-Presbyterian, $26.3M (1.11%, 24%); Ozuah, Montefiore, $16.7M (1.05%, 27%); Balser, Vanderbilt, $16.5M (2.82%, 7%); Lassiter, Dignity/CommonSpirit, $14.2M (1.68%, 6%). Advocate Health, assembled from the NC parent and five Midwest filers: $17.8B revenue, $114.9M charity care, 0.66 percent of expenses, the lowest rate of any system above $10B. The parent lists two chief executives for 2024, Eugene Woods (CEO, $25.78M) and James Skogsbergh (Co-CEO, $30.86M, retired at year end); Woods is taken for the ratio (22.4 percent), and the report should show both, since together they were paid 49 percent of what the system's roughly 30 Midwest hospitals gave in charity care.

**Chicago in the national frame.** Northwestern's nine-hospital group: 1.07% charity care, CEO Chrisman $8.17M, ratio 7.1%, at the national median on every measure. Advocate's six Illinois hospitals: 0.58%. UChicago Medical Center: 0.73%. Endeavor: 1.11%. Rush: 1.20%. Loyola: 2.24%. The three safety-net comparison hospitals: Mount Sinai 9.81%, Holy Cross 9.51%, St. Bernard 3.96%.

**State medians** range from 0.28% (North Dakota) and 0.29% (Maine) to above 1.2% (Alabama, Arizona); Illinois is 0.94% across 99 filers.

## 10. Annual re-run

The whole point of the pipeline is that next year costs almost nothing. What changes:

1. **Batch list.** Read the new year's batch names off the IRS download page and add them to `fetch_all.sh`. Keep the prior years' `done_` markers so only new batches download.
2. **Schema.** Each tax year has a schema version (2024v5.1 at this version). Element names in Section 2 have been stable since 2020; check three filings against the ProPublica page route (Section 3) before loading, per Validation step 2.
3. **Load.** `load_all.py` skips object IDs already in `loaded_object_ids.txt`, so it appends only the new filings to the master. Back up the master first.
4. **Rebuild.** `build_systems.py` picks the new latest year per EIN automatically. Prior years remain in the master for the trend.
5. **Review.** Re-run the large-filer review (Section 6). CEO changes, mergers, and new group returns are where last year's overrides go stale; each override row carries its fiscal year, so a new year gets a fresh decision rather than inheriting one.
6. **Publish** the same table on the same date, with last year's column beside it.

What an LLM or analyst needs to have read to do this: this tab, the four scripts named in Section 5, and the two override files. Nothing else in the project is required.

## 11. The site

The site is generated from `systems_rollup.csv` by one script, `site/build_site.py`, and rebuilt in seconds whenever the table changes. There is no database, no server code, and nothing to log into.

**Inputs:** `irs/systems_rollup.csv` and `irs/filers_latest.csv`. Two constants at the top of the script: `REPORT_TITLE` (placeholder at this version: Nonprofit Hospital CEO Pay Report) and `PUBLISHER` (Everything Is Broken).

**Outputs,** in `site/out/`: `index.html` (the ranked top 100 with search, sort, and a children's hospital toggle); `all.html` (every ranked system); `system/<slug>.html`, one per system with a page for every system that has either a pay figure or a charity care figure (1,614 at this version), each showing the three numbers, the filing link, a community benefit versus charity care bar, and the member filings; `state/<XX>.html` for 53 states and territories; `states.html`; `methodology.html`; `data.html`. All pages share one stylesheet written into each file, so the site is plain HTML with no build step beyond the script.

**What goes on a system page:** CEO total compensation (Part VII D+E+F), charity care as percent of expenses (Schedule H 7a column f), and CEO pay as a percent of charity care, each labelled with its form line; the filing's revenue, expenses, net assets, employees, facility count, bad debt and Medicare shortfall; a link to the exact filing on ProPublica by EIN and object ID; the CEO identification confidence as recorded; and for multi-filer systems a table of every member filing with its own link. A callout sentence appears automatically where the ratio is 25 percent or more. Systems not in the ranking (unidentifiable CEO, or zero on line 7a) get a page that says why.

**Ranking rule:** `publishable = yes` and a pay figure, sorted by CEO pay descending. Children's hospitals are ranked but shown in grey with a toggle, for the reason in Section 6.7.

**Deploy:** copy `site/out/` to any static host (Cloudflare Pages, Netlify, GitHub Pages, or an S3 bucket) and point the domain at it. Rerun `build_site.py` after any change to the tables or the override files, and redeploy. For the annual edition, change `EDITION`, rebuild, and keep the prior year's `out/` under a dated path so old links resolve.

**Not yet built:** per-system share images for social posts; the data download links (the files exist, the hosting does not); a prior-year column on each row once a second edition exists.
