# everythingisbroken.org

Static site, served by GitHub Pages from the root of this repository on every push to `main`.

| Path | What it is |
| --- | --- |
| `index.html` | The main page: mission statement, report index, data, contact, about, standards. One file; sections are switched client-side and linkable as `/#reports`, `/#data`, and so on. |
| `reports/hospital-ceo-pay/` | Report No. 1, generated. Ranking, complete list, by state, one page per system, methodology, reproduction manual, data files. Do not edit by hand. |
| `data/hospital-ceo-pay/` | The dataset behind Report No. 1: `systems_rollup.csv`, `filers_latest.csv`, the append-only master table (`hospital_data.csv.gz`), the override files, the CEO Paycheck cross-check, and `SHA256SUMS`. |
| `pipeline/` | The scripts that build the dataset from the IRS bulk release, the site generator, `REPRODUCTION_MANUAL.md`, and `AUDIT_PROMPT.md` (a prompt for an independent check of the report). |
| `reports/hospital-ceo-pay/cards/` | Generated share images (1200 x 630): one summary card, one per system, one per state. Every page unfurls as its card when its link is posted. |
| `fonts/` | Self-hosted Libre Baskerville and Space Mono (SIL Open Font License). |
| `logo.png` | The seal. |

## Rebuilding the report pages

Any change to the tables, the override files, or the generator:

```
python3 pipeline/build_site.py
git add -A && git commit -m "Rebuild report" && git push
```

The generator reads `data/hospital-ceo-pay/`, writes `reports/hospital-ceo-pay/`, and rewrites the three blocks in `index.html` that carry figures from the dataset (between `<!-- gen:latest -->`, `<!-- gen:report1 -->` and `<!-- gen:data -->` markers), so the main page and the report can never disagree. It needs Python 3, the `markdown` package (`pip install markdown`) for the manual page, and Playwright with Chromium (`pip install playwright && playwright install chromium`) for the cards; set `EIB_SKIP_CARDS=1` to rebuild the pages without re-rendering the cards. A full build with cards takes about four minutes.

## Next year's edition

Section 10 of `pipeline/REPRODUCTION_MANUAL.md`. In short: add the new IRS batch names to `pipeline/fetch_all.sh`, run the fetch, `load_all.py`, `build_systems.py`, review the large filers, copy the rebuilt tables into `data/hospital-ceo-pay/`, change `EDITION` and `DATA_ASOF` at the top of `pipeline/build_site.py`, rebuild, push.
