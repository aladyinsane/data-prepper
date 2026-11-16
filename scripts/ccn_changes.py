"""Find likely CCN changes across public HCRIS hospital (2552-10) years.

Research script for chunk 003. Standard library only. Reads the CMS zips as
they are and never writes next to them.

Usage:
    python scripts/ccn_changes.py <folder holding the yearly HCRIS zips> --out <folder>

It writes three CSV files to --out and prints a short summary:
    providers_by_year.csv   one row per CCN and file year
    appear_disappear.csv    CCNs that are in one file year and not the next, or the reverse
    candidates.csv          a CCN that stops, paired with a CCN that starts, with the evidence
"""
import argparse
import csv
import difflib
import io
import re
import zipfile
from datetime import datetime
from pathlib import Path

S2 = "S200001"  # Worksheet S-2 Part I: hospital identification
FIELDS = {  # (line, column) -> field
    ("00100", "00100"): "street",
    ("00200", "00100"): "city",
    ("00200", "00200"): "state",
    ("00200", "00300"): "zip",
    ("00200", "00400"): "county",
    ("00300", "00100"): "name",
    ("00300", "00500"): "cert_date",
}
CCN_RANGES = [(1, 879, "short-term"), (1300, 1399, "CAH"), (2000, 2299, "long-term"),
              (3025, 3099, "rehab"), (3300, 3399, "children"), (4000, 4499, "psych")]
ABBREVIATIONS = [("STREET", "ST"), ("AVENUE", "AVE"), ("ROAD", "RD"), ("DRIVE", "DR"),
                 ("BOULEVARD", "BLVD"), ("HIGHWAY", "HWY"), ("NORTH", "N"), ("SOUTH", "S"),
                 ("EAST", "E"), ("WEST", "W")]


def ccn_type(ccn):
    """Facility type from the last four characters of the CCN."""
    tail = ccn[2:]
    if not tail.isdigit():
        return "other"
    n = int(tail)
    for lo, hi, label in CCN_RANGES:
        if lo <= n <= hi:
            return label
    return "other"


def date(text):
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


def norm(text):
    text = re.sub(r"[^A-Z0-9 ]", " ", text.upper())
    for long, short in ABBREVIATIONS:
        text = re.sub(rf"\b{long}\b", short, text)
    return " ".join(text.split())


def member(z, kind):
    for name in z.namelist():
        if name.lower().endswith(f"_{kind}.csv"):
            return io.TextIOWrapper(z.open(name), encoding="latin-1", newline="")
    raise SystemExit(f"no {kind} file in {z.filename}")


def read_year(zip_path):
    """Return {ccn: record} for one file year.

    A CCN can have several reports in one file year. Keep the one with the
    latest fiscal year end, and the earliest begin date across all of them.
    """
    z = zipfile.ZipFile(zip_path)
    reports = {}
    for row in csv.reader(member(z, "rpt")):
        reports[row[0]] = {"ccn": row[2], "fy_bgn": date(row[5]), "fy_end": date(row[6])}
    for row in csv.reader(member(z, "alpha")):
        if row[1] == S2 and (row[2], row[3]) in FIELDS and row[0] in reports:
            reports[row[0]][FIELDS[(row[2], row[3])]] = row[4].strip()
    by_ccn = {}
    for rec in reports.values():
        if rec["fy_end"] is None or rec["fy_bgn"] is None:
            continue
        old = by_ccn.get(rec["ccn"])
        if old is None:
            by_ccn[rec["ccn"]] = rec
        else:
            keep = rec if rec["fy_end"] > old["fy_end"] else old
            keep["fy_bgn"] = min(rec["fy_bgn"], old["fy_bgn"])
            by_ccn[rec["ccn"]] = keep
    return by_ccn


def strength_of(o, n):
    """How well a stopping provider (o) matches a starting one (n). None means not a candidate."""
    same_zip = o.get("zip", "")[:5] == n.get("zip", "")[:5] != ""
    same_street = norm(o.get("street", "")) == norm(n.get("street", "")) != ""
    same_city = norm(o.get("city", "")) == norm(n.get("city", "")) != ""
    name_sim = difflib.SequenceMatcher(None, norm(o.get("name", "")), norm(n.get("name", ""))).ratio()
    if same_street and same_zip:
        return "strong: same street and zip", name_sim
    if same_zip and name_sim >= 0.85:
        return "strong: same zip, near-same name", name_sim
    if same_city and name_sim >= 0.85:
        return "medium: same city, near-same name", name_sim
    if same_zip and name_sim >= 0.6:
        return "weak: same zip, similar name", name_sim
    return None, name_sim


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--max-gap-days", type=int, default=400,
                    help="how long after the old CCN's last fiscal year end the new CCN may start")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    years = {}
    for path in sorted(Path(args.folder).rglob("*.ZIP")):
        m = re.search(r"FY(\d{4})", path.name.upper())
        if m:
            years[int(m.group(1))] = read_year(path)
    order = sorted(years)
    print("file years:", order, "CCNs per year:", [len(years[y]) for y in order])

    cols = ["name", "street", "city", "state", "zip", "county", "cert_date"]
    with open(out / "providers_by_year.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_year", "fy_bgn", "fy_end", "ccn", "type"] + cols)
        for y in order:
            for ccn, r in sorted(years[y].items()):
                w.writerow([y, r["fy_bgn"], r["fy_end"], ccn, ccn_type(ccn)] + [r.get(c, "") for c in cols])

    first, last = {}, {}
    for y in order:
        for ccn, r in years[y].items():
            first.setdefault(ccn, (y, r))
            last[ccn] = (y, r)

    with open(out / "appear_disappear.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["change", "from_year", "to_year", "ccn", "type", "name", "city", "state"])
        for a, b in zip(order, order[1:]):
            gone = sorted(set(years[a]) - set(years[b]))
            new = sorted(set(years[b]) - set(years[a]))
            print(f"{a} -> {b}: {len(gone)} not in the next year, {len(new)} new")
            for change, ccns, y in (("disappears", gone, a), ("appears", new, b)):
                for ccn in ccns:
                    r = years[y][ccn]
                    w.writerow([change, a, b, ccn, ccn_type(ccn), r.get("name", ""), r.get("city", ""), r.get("state", "")])

    # A CCN "starts" if it is missing from the earliest file year. Any CCN can be the old side:
    # the test is that its last fiscal year ends just before the new CCN's first one begins.
    # The newest reports arrive late, so an old CCN whose last year end is recent may simply not
    # have filed its next report yet. Those pairs are flagged, not dropped.
    latest_end = max(r["fy_end"] for _, r in last.values())
    starts = {c: v for c, v in first.items() if v[0] > order[0]}
    by_state = {}
    for ccn, (y, r) in starts.items():
        by_state.setdefault(ccn[:2], []).append((ccn, r))

    found = []
    for old, (oy, o) in last.items():
        for new, n in by_state.get(old[:2], []):
            if new == old:
                continue
            gap = (n["fy_bgn"] - o["fy_end"]).days
            if not -31 <= gap <= args.max_gap_days:
                continue
            strength, name_sim = strength_of(o, n)
            if strength is None:
                continue
            recent = "yes" if (latest_end - o["fy_end"]).days <= 550 else "no"
            found.append([strength, recent, f"{ccn_type(old)} -> {ccn_type(new)}", old, o["fy_end"], new, n["fy_bgn"], gap,
                          n.get("cert_date", ""), round(name_sim, 2), o.get("name", ""), n.get("name", ""),
                          o.get("street", ""), n.get("street", ""), o.get("city", ""), n.get("city", ""),
                          o.get("zip", ""), n.get("zip", "")])
    found.sort(key=lambda r: [str(v) for v in r])
    with open(out / "candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["strength", "old_may_still_be_filing", "type_change", "old_ccn", "old_last_fy_end", "new_ccn", "new_first_fy_bgn", "gap_days",
                    "new_cert_date", "name_similarity", "old_name", "new_name", "old_street", "new_street",
                    "old_city", "new_city", "old_zip", "new_zip"])
        w.writerows(found)

    print(f"CCNs that start after file year {order[0]}: {len(starts)}; latest fiscal year end in the data: {latest_end}")
    print(f"candidate pairs: {len(found)}")
    for key in sorted({(r[0], r[2]) for r in found}):
        print(f"  {key[0]} | {key[1]}: {sum(1 for r in found if (r[0], r[2]) == key)}")
    print("pairs where the old CCN may still be filing:", sum(1 for r in found if r[1] == "yes"))
    olds = [r[3] for r in found]
    news = [r[5] for r in found]
    print("new CCNs with more than one candidate:", len({c for c in news if news.count(c) > 1}))
    print("CCNs that are the new side of one pair and the old side of another:", sorted(set(olds) & set(news)))
    print("old CCNs with more than one candidate:", len({c for c in olds if olds.count(c) > 1}))


if __name__ == "__main__":
    main()
