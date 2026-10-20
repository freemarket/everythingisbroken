#!/usr/bin/env python3
"""Append-only writer for hospital_data.csv.

Rules:
- Never rewrites or deletes existing rows. Only appends.
- Every row gets a row_id, added_at timestamp, and status (active / ignore).
- To retire a value, append a new row with status=ignore and ignore_reason, or add
  a corrected row; never remove the old one.

Usage: import add_rows; add_rows.add(dict(...), dict(...))
"""
import csv, os, sys, datetime, json

CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hospital_data.csv")

FIELDS = [
    "row_id",            # sequential, never reused
    "added_at",          # UTC ISO timestamp of append
    "status",            # active | ignore
    "ignore_reason",     # why a row should be ignored (never deleted)
    "system",            # parent system name
    "entity_name",       # filing entity exactly as on filing
    "ein",               # EIN if applicable
    "fiscal_year_end",   # YYYY-MM for FY end, or range like 2020-2022avg
    "metric",            # standardized metric key
    "value",             # numeric value as reported (no commas)
    "unit",              # USD | pct | count | text
    "person",            # for compensation rows
    "person_title",      # for compensation rows
    "source_type",       # IRS990 | Audit | IL_AG | Lown | IHPA | IHA | ProPublica | Other
    "source_doc",        # document title / filing name
    "source_location",   # form/schedule/part/line or page
    "source_url",        # URL where retrieved
    "retrieval_method",  # WebFetch summary | direct read | computed
    "notes",             # caveats, definitions, context
]

_NEXT = None
def _next_id():
    global _NEXT
    if _NEXT is not None:
        return _NEXT
    if not os.path.exists(CSV_PATH):
        _NEXT = 1; return 1
    last = None
    with open(CSV_PATH, newline="") as f:
        for row in csv.DictReader(f):
            last = row
    _NEXT = (int(last["row_id"]) + 1) if last else 1
    return _NEXT

def add(*rows):
    new_file = not os.path.exists(CSV_PATH)
    rid = _next_id()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    with open(CSV_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for r in rows:
            out = {k: "" for k in FIELDS}
            out.update({k: ("" if v is None else v) for k, v in r.items() if k in FIELDS})
            unknown = set(r) - set(FIELDS)
            if unknown:
                raise ValueError(f"unknown fields: {unknown}")
            out["row_id"] = rid
            out["added_at"] = now
            out.setdefault("status", "active")
            if not out["status"]:
                out["status"] = "active"
            w.writerow(out)
            rid += 1
    global _NEXT
    _NEXT = rid
    return rid - 1

def count():
    if not os.path.exists(CSV_PATH):
        return 0
    with open(CSV_PATH, newline="") as f:
        return sum(1 for _ in csv.DictReader(f))

if __name__ == "__main__":
    print("rows:", count())
