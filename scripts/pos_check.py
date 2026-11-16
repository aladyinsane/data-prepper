"""Compare the HCRIS CCN-change candidates with CMS's Provider of Services (POS) file.

Research script for chunk 002. Standard library only. Needs internet access to
data.cms.gov. It reads hospital rows through the public CMS data API, so nothing
is downloaded into the repo.

Usage:
    python scripts/pos_check.py docs/research/ccn-change-candidates.csv

The POS field CROSS_REF_PROVIDER_NUMBER on a provider's row holds a related CCN.
This script checks how often it holds the new CCN that the HCRIS method found,
and how many POS links the HCRIS method did not find.
"""
import collections
import csv
import json
import sys
import urllib.parse
import urllib.request

# "Provider of Services File - Quality Improvement and Evaluation System", Q3 2026.
# Each quarter has its own dataset id. Find the current one in https://data.cms.gov/data.json.
API = "https://data.cms.gov/data-api/v1/dataset/8ba0f9b4-9493-4aa0-9f82-44ea9468d1b5/data"
KEEP = ["PRVDR_NUM", "FAC_NAME", "CROSS_REF_PROVIDER_NUMBER", "PGM_TRMNTN_CD",
        "TRMNTN_EXPRTN_DT", "ORGNL_PRTCPTN_DT", "STATE_CD", "CITY_NAME"]
PAGE = 5000


def fetch_hospitals():
    rows, offset = [], 0
    while True:
        query = urllib.parse.urlencode({"filter[PRVDR_CTGRY_CD]": "01", "size": PAGE, "offset": offset})
        request = urllib.request.Request(API + "?" + query, headers={"User-Agent": "research-script"})
        with urllib.request.urlopen(request, timeout=120) as response:
            page = json.load(response)
        rows += [{k: (r.get(k) or "").strip() for k in KEEP} for r in page]
        if len(page) < PAGE:
            return rows
        offset += PAGE


def main():
    candidates = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
    rows = fetch_hospitals()
    pos = {r["PRVDR_NUM"]: r for r in rows}
    print(f"POS hospital rows: {len(rows)}, with a cross reference: "
          f"{sum(bool(r['CROSS_REF_PROVIDER_NUMBER']) for r in rows)}")

    print("\nHCRIS candidates checked against POS:")
    result = collections.Counter()
    for c in candidates:
        row = pos.get(c["old_ccn"])
        if row is None:
            kind = "old CCN not in POS"
        elif row["CROSS_REF_PROVIDER_NUMBER"] == c["new_ccn"]:
            kind = "POS agrees"
        elif not row["CROSS_REF_PROVIDER_NUMBER"]:
            kind = "POS blank"
        else:
            kind = "POS points elsewhere"
        result[kind] += 1
        if kind != "POS agrees":
            print(f"  {kind}: {c['old_ccn']} -> {c['new_ccn']} ({c['type_change']}), "
                  f"POS has '{row['CROSS_REF_PROVIDER_NUMBER'] if row else ''}', {c['old_name']}")
    for kind, n in result.most_common():
        print(f"{n:4d}  {kind}")

    print("\nPOS links with a termination date in 2020 to 2025, by what the HCRIS method did with them:")
    found = {(c["old_ccn"], c["new_ccn"]) for c in candidates}
    groups = collections.Counter()
    for r in rows:
        new, ended = r["CROSS_REF_PROVIDER_NUMBER"], r["TRMNTN_EXPRTN_DT"]
        if not new or not "20200101" <= ended <= "20251231":
            continue
        if (r["PRVDR_NUM"], new) in found:
            kind = "found by the HCRIS method"
        elif not new.isdigit():
            kind = "new number is not a hospital CCN (it has a letter)"
        elif new not in pos:
            kind = "new CCN is not a hospital row in POS"
        elif pos[new]["ORGNL_PRTCPTN_DT"] and pos[new]["ORGNL_PRTCPTN_DT"] < str(int(ended) - 10000):
            kind = "new CCN existed a year or more earlier (absorbed into an existing hospital)"
        elif ended >= "20250101":
            kind = "2025 change, new CCN has probably not filed a cost report yet"
        elif ended < "20210101":
            kind = "2020 change, new CCN was already in the first HCRIS file year"
        else:
            kind = "other miss, 2021 to 2024"
            print(f"  {kind}: {r['PRVDR_NUM']} -> {new}, ended {ended}, {r['FAC_NAME']}")
        groups[kind] += 1
    for kind, n in groups.most_common():
        print(f"{n:4d}  {kind}")


if __name__ == "__main__":
    main()
