"""Key results (paper/multiverse/key_results.yaml), read from a run's ecosystem.json, and the comparison with the
default. Nothing here is added to the build: every value is read from what the build already writes."""
from collections import Counter

SIGNAL_TYPES = ("builds", "integrates", "uses_tools")


def _step(eco, prefix):
    hits = [s for s in eco["step_counts"] if s["step"].startswith(prefix)]
    if len(hits) != 1:
        raise KeyError(f"expected one step starting {prefix!r}, found {len(hits)}")
    return hits[0]


def _ties(counts):
    """Items tied at the maximum, sorted; [] when every count is 0."""
    if not counts or max(counts.values()) == 0:
        return []
    m = max(counts.values())
    return sorted(k for k, v in counts.items() if v == m)


def _ranked_groups(counts):
    """[[highest...], [next...], ...]: items grouped by count, ties together, highest first."""
    by = {}
    for k, v in counts.items():
        by.setdefault(v, []).append(k)
    return [sorted(by[v]) for v in sorted(by, reverse=True)]


def read_one(eco, r):
    rd = r["read"]
    src = rd["from"]
    if src == "step_counts":
        s = _step(eco, rd["step_prefix"])
        if rd["value"] == "out":
            return {"value": s["out"]}
        return {"numerator": s["out"], "denominator": s["in"], "value": round(s["out"] / s["in"], 4) if s["in"] else None}
    if src == "firms_measured":
        return {"value": eco["distributions"]["firm_ai_share"]["firms_measured"]}
    m = eco["matrices"]["signal_type_by_bucket"]
    if src == "signal_type_firms":
        counts = {t: sum(c["firms"] for c in m["cells"][m["rows"].index(t)]) for t in SIGNAL_TYPES}
        return {"counts": counts, "value": _ranked_groups(counts)}
    if src == "top_signal_type_by_bucket":
        measured = Counter(x["bucket"] for x in eco["firms"] if x["ai_share"] is not None and x["bucket"])
        out = {}
        for j, col in enumerate(m["columns"]):
            if col == "sector not measured" or measured.get(col, 0) < rd["min_measured_firms"]:
                continue
            counts = {t: m["cells"][m["rows"].index(t)][j]["firms"] for t in SIGNAL_TYPES}
            out[col] = {"measured_firms": measured[col], "counts": counts, "top": _ties(counts)}
        return {"by_bucket": out, "value": {b: v["top"] for b, v in out.items()}}
    if src == "boston_top_groups":
        b = eco["baselines"]["boston_all"]
        groups = sorted((g for g in b["soc_major"] if g["code"] != "unassigned"), key=lambda g: (-g["share"], g["code"]))
        shares = {g["code"]: g["share"] for g in groups}
        return {"firms": b["firms"], "top": [{"code": g["code"], "title": g["title"], "share": g["share"]} for g in groups[:rd["n"]]],
                "value": _ties(shares)}
    if src == "sector_buckets":
        counts = Counter(x["bucket"] for x in eco["firms"] if x["bucket"])
        fc = eco["filter_coverage"]["sector_bucket"]
        return {"bucketed": fc["known"], "total": fc["total"], "largest_firms": max(counts.values()) if counts else 0, "value": _ties(counts)}
    raise KeyError(f"unknown key-result source {src!r}")


def compute(eco, spec):
    return {r["id"]: {"title": r["title"], **read_one(eco, r)} for r in spec["results"]}


def _flipped(rule, d, b, r):
    if rule == "none":
        return False
    if rule == "crosses":
        t = r["threshold"]
        return (d["value"] >= t) != (b["value"] >= t)
    if rule == "order-changes":
        return d["value"] != b["value"]
    if rule == "top-changes":
        dv, bv = d["value"], b["value"]
        if isinstance(dv, dict):   # per group: compare the groups present in both
            return any(dv[k] != bv[k] for k in set(dv) & set(bv))
        return dv != bv
    raise KeyError(f"unknown flip rule {rule!r}")


def diff(default, branch, spec):
    out = {}
    for r in spec["results"]:
        d, b = default[r["id"]], branch[r["id"]]
        e = {"title": r["title"], "flip_rule": r["flip_rule"], "default": d["value"], "branch": b["value"],
             "changed": d["value"] != b["value"], "flipped": _flipped(r["flip_rule"], d, b, r)}
        if r.get("threshold") is not None:
            e["threshold"] = r["threshold"]
        if isinstance(d["value"], (int, float)) and isinstance(b["value"], (int, float)) and not isinstance(d["value"], bool):
            e["change"] = round(b["value"] - d["value"], 4)
        if isinstance(d["value"], dict):
            only_d, only_b = sorted(set(d["value"]) - set(b["value"])), sorted(set(b["value"]) - set(d["value"]))
            if only_d or only_b:
                e["not_compared"] = {"only_in_default": only_d, "only_in_branch": only_b}
        out[r["id"]] = e
    return out


def show(v):
    """A key-result value in words: 90.0%, builds > integrates = uses_tools, it-services: builds; ..."""
    if isinstance(v, bool) or v is None:
        return str(v)
    if isinstance(v, float):
        return f"{v:.1%}" if 0 <= v <= 1 else f"{v:,}"
    if isinstance(v, int):
        return f"{v:,}"
    if isinstance(v, dict):
        return "; ".join(f"{k}: {show(x)}" for k, x in v.items()) or "(none)"
    if isinstance(v, list) and v and all(isinstance(g, list) for g in v):
        return " > ".join(" = ".join(map(str, g)) for g in v)
    if isinstance(v, list):
        return " = ".join(map(str, v)) or "(none)"
    return str(v)


def table(kr_diff):
    """Plain text for the terminal and for interpretations: each key result, its default and branch values in full,
    and whether it changed or flipped. "=" joins ties; ">" separates ranks."""
    lines = []
    for k, e in kr_diff.items():
        tag = "FLIP" if e["flipped"] else ("changed" if e["changed"] else "same")
        rule = e["flip_rule"] + (f" {show(e['threshold'])}" if e.get("threshold") is not None else "")
        lines.append(f"{k}  {e['title']}  [{tag}; flip rule: {rule}]")
        change = ""
        if "change" in e and e["change"]:
            c = e["change"]
            change = (f"  ({c * 100:+.1f} points)" if isinstance(e["default"], float) and abs(e["default"]) <= 1
                      else f"  ({c:+,})")
        lines.append(f"    default  {show(e['default'])}")
        lines.append(f"    branch   {show(e['branch'])}{change}")
    return "\n".join(lines)
