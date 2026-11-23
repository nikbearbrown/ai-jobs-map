"""Stream DOL LCA disclosure .xlsx files with the standard library and keep rows whose employer (or trade name)
matches a collected firm by normalised name. Writes a gzipped JSONL cache outside the repo.

Never stores or prints EMPLOYER_FEIN values: only whether the column is filled is logged.

    python3 -I -m pipeline.ai_job_map.lca            # from the repo root
"""
import csv
import glob
import gzip
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter

from .core import norm_employer

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
KEEP = ["CASE_NUMBER", "CASE_STATUS", "RECEIVED_DATE", "DECISION_DATE", "VISA_CLASS", "JOB_TITLE", "SOC_CODE", "SOC_TITLE",
        "FULL_TIME_POSITION", "TOTAL_WORKER_POSITIONS", "EMPLOYER_NAME", "TRADE_NAME_DBA", "EMPLOYER_CITY", "EMPLOYER_STATE",
        "EMPLOYER_POSTAL_CODE", "NAICS_CODE", "WORKSITE_CITY", "WORKSITE_STATE", "WORKSITE_POSTAL_CODE", "PW_WAGE_LEVEL",
        "WAGE_RATE_OF_PAY_FROM", "WAGE_UNIT_OF_PAY", "H_1B_DEPENDENT", "H1B_DEPENDENT", "SECONDARY_ENTITY", "SECONDARY_ENTITY_BUSINESS_NAME"]


def col_index(ref):
    letters = "".join(ch for ch in ref if ch.isalpha())
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def shared_strings(z):
    out = []
    if "xl/sharedStrings.xml" not in z.namelist():
        return out
    with z.open("xl/sharedStrings.xml") as f:
        for ev, el in ET.iterparse(f, events=("end",)):
            if el.tag == NS + "si":
                out.append("".join(t.text or "" for t in el.iter(NS + "t")))
                el.clear()
    return out


def iter_rows(path):
    z = zipfile.ZipFile(path)
    ss = shared_strings(z)
    with z.open("xl/worksheets/sheet1.xml") as f:
        for ev, el in ET.iterparse(f, events=("end",)):
            if el.tag != NS + "row":
                continue
            row = {}
            for c in el.iter(NS + "c"):
                t, v = c.get("t"), c.find(NS + "v")
                if t == "s" and v is not None:
                    val = ss[int(v.text)]
                elif t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(NS + "t"))
                else:
                    val = v.text if v is not None else ""
                row[col_index(c.get("r"))] = val
            el.clear()
            if row:
                width = max(row) + 1
                yield [row.get(i, "") for i in range(width)]


def firm_keys(live_path, companies_csv):
    """Normalised firm-name keys -> company_id, from the live collection's company names and the company list."""
    keys = {}
    with open(live_path) as f:
        for line in f:
            r = json.loads(line)
            k = norm_employer(r["company"])
            if k:
                keys.setdefault(k, set()).add(r.get("company_id") or r["company"])
    ids = {cid for v in keys.values() for cid in v}
    for row in csv.DictReader(open(companies_csv)):
        if row["company_id"] in ids:
            k = norm_employer(row["name"])
            if k:
                keys.setdefault(k, set()).add(row["company_id"])
    return keys


def extract(lca_dir, keys, out_path):
    files = sorted(glob.glob(os.path.join(lca_dir, "LCA_Disclosure_Data_*.xlsx")))
    log = []
    with gzip.open(out_path + ".tmp", "wt") as out:
        for path in files:
            name = os.path.basename(path).replace(".xlsx", "")
            rows = kept = fein_filled = 0
            header = None
            for vals in iter_rows(path):
                if header is None:
                    header = [h.strip().upper() for h in vals]
                    idx = {h: i for i, h in enumerate(header)}
                    missing = [k for k in ("EMPLOYER_NAME", "SOC_CODE", "NAICS_CODE", "TOTAL_WORKER_POSITIONS", "PW_WAGE_LEVEL", "WORKSITE_CITY") if k not in idx]
                    continue
                rows += 1
                get = lambda k: (vals[idx[k]] if k in idx and idx[k] < len(vals) else "")
                if "EMPLOYER_FEIN" in idx and get("EMPLOYER_FEIN").strip():
                    fein_filled += 1
                hits = set()
                for col in ("EMPLOYER_NAME", "TRADE_NAME_DBA"):
                    k = norm_employer(get(col))
                    if k and k in keys:
                        hits.add((col, k))
                if not hits:
                    continue
                kept += 1
                rec = {k: get(k) for k in KEEP if k in idx}
                rec["_file"] = name
                rec["_match"] = sorted([c, k, sorted(keys[k])] for c, k in hits)
                out.write(json.dumps(rec) + "\n")
            entry = {"file": name, "rows": rows, "kept": kept, "missing_columns": missing,
                     "fein_column_present": "EMPLOYER_FEIN" in (header or []), "fein_rows_filled": fein_filled}
            log.append(entry)
            print(json.dumps(entry), flush=True)
    os.replace(out_path + ".tmp", out_path)
    with open(out_path.replace(".jsonl.gz", ".log.json"), "w") as f:
        json.dump(log, f, indent=1)
    return log


def main():
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cfg = json.load(open(os.path.join(os.path.dirname(__file__), "config", "config.json")))
    inp = cfg["inputs"]
    keys = firm_keys(inp["live_collection"], inp["companies_csv"])
    print(json.dumps({"firm_name_keys": len(keys)}), flush=True)
    extract(inp["lca_dir"], keys, inp["lca_matched_cache"])


if __name__ == "__main__":
    sys.exit(main())
