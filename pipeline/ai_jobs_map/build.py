"""Derive the AI jobs map from raw inputs into data/ai-jobs-map/v1. Deterministic (sorted inputs, fixed seeds), re-runnable,
and it logs counts at every step. No ad text or requirement text is written anywhere: outputs carry counts, skills
(short phrases), occupation codes and role titles only."""
import csv
import glob
import gzip
import hashlib
import json
import os
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import core
from .soc import TitleMap, lca_title_dictionary, major, major_title, make_norm_title, soc6
from .validate import validate

HERE = os.path.dirname(__file__)
STEPS = []

# Switch parameters (decision points whose alternatives need code): the variants this build implements. A branch
# may pick only one of these; a new variant is a code change, reviewed with its proposal. The registry
# (paper/multiverse/decision_points.yaml) lists the same variants, and a test keeps the two in step.
IMPLEMENTED = {
    "dedup.text_role_adds_text_hash": [True],
    "dedup.keep_level_words": [True],
    "dedup.collapse_remote": [True],
    "aggregation.default_weighting": ["firm"],
    "skills.mask_seed_fragments": ["on", "off"],
    "ai_relatedness.omega_aggregate": ["mean"],
    "signal_types.integrates_requires_ai_related": [False],
    "signal_types.order": ["builds>integrates>uses_tools"],
    "visa_display.count_positions_not_cases": [True, False],
    "visa_display.ai_soc_join_window": ["all"],
    "dynamics.exclude_first_day": [True],
}
SIGNAL_TYPES = ("builds", "integrates", "uses_tools")


def step(name, n_in, n_out, **excluded):
    STEPS.append({"step": name, "in": n_in, "out": n_out, **({"excluded_by_reason": excluded} if excluded else {})})
    print(f"[{name}] in={n_in} out={n_out}" + (f" excluded={excluded}" if excluded else ""), flush=True)


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(s):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s.lower())).strip("-") or "firm"


def fiscal_year(iso):
    if not iso or len(iso) < 7:
        return None
    y, m = int(iso[:4]), int(iso[5:7])
    return f"FY{y + 1 if m >= 10 else y}"


def excel_date(v):
    """DOL .xlsx dates arrive as Excel serial numbers (e.g. 45201). Returns ISO date, or the value unchanged."""
    from datetime import date, timedelta
    s = str(v or "").strip()
    if re.match(r"^\d{5}(\.\d+)?$", s):
        return (date(1899, 12, 30) + timedelta(days=int(float(s)))).isoformat()
    return s[:10]


def to_int(v, default=1):
    try:
        return max(0, int(float(v)))
    except (TypeError, ValueError):
        return default


def config_sha256(cfg):
    """SHA-256 of the config as canonical JSON (sorted keys, no spaces), so the same settings always hash the same
    however the file is laid out, and a branch with an empty override hashes the same as the main build."""
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def check_implemented(cfg):
    for key, variants in IMPLEMENTED.items():
        node = cfg
        for part in key.split("."):
            node = node[part]
        if node not in variants:
            raise ValueError(f"{key} = {node!r} is not implemented (implemented: {variants})")


def main(cfg=None, out_dir=None, private_outputs=True):
    """Build the jobs map. With no arguments: the config file, into inputs.output_dir, as always. The branch runner
    passes an effective config and its own run folder, and private_outputs=False (no labeling packet)."""
    STEPS.clear()
    if cfg is None:
        cfg = json.load(open(os.path.join(HERE, "config", "config.json")))
    check_implemented(cfg)
    cfg_sha = config_sha256(cfg)
    inp = cfg["inputs"]
    out_dir = out_dir or inp["output_dir"]
    computed_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    os.makedirs(os.path.join(out_dir, "firms"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "review"), exist_ok=True)
    dd = cfg["dedup"]
    req_pat = dd["requisition_token"]
    title_opts = {"suffix_pattern": dd["trailing_employment_suffix"], "keep_chars": dd["keep_chars"]}
    loc_opts = {"remote_pattern": dd["remote_pattern"]}
    key_opts = {"req_pattern": req_pat, "fields": tuple(dd["role_key_fields"]), "title_opts": title_opts, "loc_opts": loc_opts}
    live_from, live_to = inp["live_collection_observed"]
    snap_date = inp["text_snapshot_date"]

    SRC = {
        "live": {"id": "ai-jobs-live", "name": "ai-jobs collector, Hetzner box (current.jsonl)", "kind": "job-postings",
                 "location": inp["live_collection"], "sha256": None, "observed_from": live_from, "observed_to": live_to, "stage": None},
        "snap": {"id": f"desc-snapshot-{snap_date}", "name": "Posting text snapshot (local, never published)", "kind": "posting-text-snapshot",
                 "location": inp["text_snapshot_dir"], "sha256": None, "observed_from": snap_date, "observed_to": snap_date, "stage": None},
        "onet": {"id": "onet-31.0", "name": "O*NET 31.0 title tables via a-new-shape-for-work title map", "kind": "occupation-data",
                 "location": inp["onet_title_map"], "sha256": None, "observed_from": "2025-08-01", "observed_to": "2025-08-01", "stage": None},
    }

    def prov(sources, d_from, d_to, roles, method, units=None, notes=None):
        return {"sources": [SRC[s] for s in sources], "date_range": {"from": d_from, "to": d_to}, "distinct_roles_used": roles,
                "units_used": units, "method_version": method, "config_sha256": cfg_sha, "computed_at": computed_at,
                "methods_url": "/methodology#ai-jobs-map", "notes": notes}

    # ------------------------------------------------------------ 1. live collection -> distinct roles
    live, by_id = [], {}
    with open(inp["live_collection"]) as f:
        for line in f:
            r = json.loads(line)
            r["firm"] = r.get("company_id") or slugify(r["company"])
            live.append(r)
            by_id[r["id"]] = r
    live.sort(key=lambda r: r["id"])
    firm_names = defaultdict(Counter)
    live_by_firm = defaultdict(list)
    for r in live:
        firm_names[r["firm"]][r["company"]] += 1
        live_by_firm[r["firm"]].append(r)
    roles = {}
    for r in live:
        k = core.role_key(r["firm"], r["title"], r.get("locations"), None, **key_opts)
        e = roles.get(k)
        if e is None:
            e = roles[k] = {"firm": r["firm"], "title": r["title"], "locations": r.get("locations") or [], "first_seen": r["first_seen"],
                            "last_seen": r["last_seen"], "open": False, "postings": 0}
        e["first_seen"] = min(e["first_seen"], r["first_seen"])
        e["last_seen"] = max(e["last_seen"], r["last_seen"])
        e["open"] = e["open"] or r["status"] == "open"
        e["postings"] += 1
    step("live: postings -> distinct roles (" + " + ".join({"firm": "firm", "title": "normalised title", "locations": "location set"}[x]
                                                         for x in dd["role_key_fields"]) + ")", len(live), len(roles))
    firms = sorted(firm_names)
    firm_roles = defaultdict(list)
    for k in sorted(roles):
        firm_roles[roles[k]["firm"]].append(roles[k])

    # ------------------------------------------------------------ 2. SOC by title (O*NET title map, then LCA title dictionary)
    sc_ = cfg["soc"]
    norm_title = make_norm_title(sc_["level_edge_words"], sc_["mode_words"], sc_["cut_pattern"])
    tm = TitleMap(inp["onet_title_map"], sc_["accepted_statuses"], norm_title, sc_["min_tail_words"])
    lca_rows_all = []
    if os.path.exists(inp["lca_matched_cache"]):
        for l in gzip.open(inp["lca_matched_cache"], "rt"):
            row = json.loads(l)
            for dk in ("RECEIVED_DATE", "DECISION_DATE"):
                row[dk] = excel_date(row.get(dk))
            lca_rows_all.append(row)
        ld = sc_["lca_dictionary"]
        tm.extra = lca_title_dictionary(lca_rows_all, ld["min_filings"], ld["min_employers"], ld["min_agreement"], norm_title)
        step(f"soc: LCA filed titles -> title dictionary (>={ld['min_filings']} filings, >={ld['min_employers']} employers, "
             f">={ld['min_agreement']:.0%} agree)", len(lca_rows_all), len(tm.extra))
    onet_titles = {}
    occ_path = os.path.join(os.path.dirname(os.path.dirname(inp["onet_title_map"])), "source", "onet-31.0", "Occupation Data.txt")
    if os.path.exists(occ_path):
        for r in csv.DictReader(open(occ_path, encoding="utf-8", errors="replace"), delimiter="\t"):
            onet_titles[r["O*NET-SOC Code"]] = r["Title"]
    methods = Counter()
    for e in roles.values():
        e["onet"], m = tm.assign_with_method(e["title"])
        e["major"] = major(e["onet"])
        methods[m or "unassigned"] += 1
    step("live: distinct roles -> SOC by title (exact, then trailing phrase)", len(roles), len(roles) - methods["unassigned"],
         **{f"method_{k}": v for k, v in methods.items()})

    # ------------------------------------------------------------ 3. text snapshot -> requirement text -> text roles
    excl_prov = set(cfg["ai_relatedness"]["exclude_providers_from_corpus"])
    firm_posts = defaultdict(list)
    n_read = n_live = n_excl = n_nojoin = 0
    for path in sorted(glob.glob(os.path.join(inp["text_snapshot_dir"], "*.jsonl.gz"))):
        for line in gzip.open(path, "rt"):
            rec = json.loads(line)
            n_read += 1
            if rec.get("state") != "live" or not rec.get("blocks"):
                continue
            n_live += 1
            if rec["id"].split(":", 1)[0] in excl_prov:
                n_excl += 1
                continue
            base = by_id.get(rec["id"])
            if base is None:
                n_nojoin += 1
                continue
            firm_posts[base["firm"]].append((rec["id"], base, rec["blocks"]))
    kept_posts = sum(len(v) for v in firm_posts.values())
    step("snapshot: records -> live with text -> AI corpus", n_read, kept_posts,
         not_live_or_empty=n_read - n_live, title_selected_providers=n_excl, not_in_live_collection=n_nojoin)

    rq = cfg["requirements_text"]
    text_roles = {}
    unsectioned = empty = 0
    for firm in sorted(firm_posts):
        posts = sorted(firm_posts[firm], key=lambda x: x[0])
        rep = core.repeated_blocks([b for _, _, b in posts], rq["firm_repetition_drop"]["share_of_firm_postings"],
                                   rq["firm_repetition_drop"]["min_firm_postings"])
        for pid, base, blocks in posts:
            kept, sectioned = core.requirement_blocks(blocks, rq, rep)
            if not kept:
                empty += 1
                continue
            unsectioned += not sectioned
            text = "\n".join(kept)
            req_sha = hashlib.sha256(re.sub(r"\s+", " ", text.lower()).encode()).hexdigest()
            k = core.role_key(firm, base["title"], base.get("locations"), req_sha if dd["text_role_adds_text_hash"] else None, **key_opts)
            if k not in text_roles:
                text_roles[k] = {"firm": firm, "title": base["title"], "text": text, "posting_id": pid, "blocks": blocks}
    step("snapshot: postings -> requirement text -> distinct text roles", kept_posts, len(text_roles),
         no_requirement_text_left=empty)
    step("snapshot: text roles with no recognised requirement headings (kept, flagged)", len(text_roles), unsectioned)

    # ------------------------------------------------------------ 4. skills vocabulary, w(s), omega(j), signal types
    sk = cfg["skills"]
    rids = sorted(text_roles, key=lambda k: text_roles[k]["posting_id"])
    seeds = cfg["ai_relatedness"]["seed_skills"]
    ng_opts = {"stop": set(sk["stoplist"]), "token_re": re.compile(sk["token_pattern"]), "segment_re": re.compile(sk["segment_pattern"]),
               "mask_seeds": sk["mask_seed_fragments"] == "on"}
    role_ngrams = {i: core.ngrams_of_text(text_roles[k]["text"], sk["max_ngram"], sk["token_alias"], sk["ngram_alias"], seeds, **ng_opts)
                   for i, k in enumerate(rids)}
    role_firm = {i: text_roles[k]["firm"] for i, k in enumerate(rids)}
    vocab = core.build_vocabulary(role_ngrams, role_firm, sk["min_support_roles"], sk["min_support_firms"], sk["max_doc_share"])
    seeds = cfg["ai_relatedness"]["seed_skills"]
    allowed = set(vocab) | set(seeds)
    role_skills = {i: g & allowed for i, g in role_ngrams.items()}
    step("skills: candidate n-grams -> vocabulary (support rule)", len({g for s in role_ngrams.values() for g in s}), len(vocab))
    del role_ngrams
    w = core.compute_w(role_skills, seeds)
    thr = cfg["ai_relatedness"]["threshold"]
    rx = {t: core.term_regex(cfg["signal_types"][t]) for t in SIGNAL_TYPES}
    tag_rx = {t: core.term_regex(terms) for t, terms in cfg["application_tags"]["tags"].items()}
    ls_rx = {t: core.term_regex(terms) for t, terms in cfg["application_tags"]["life_sciences_subtags"].items()}
    no_omega = 0
    role_text = {}
    for i, k in enumerate(rids):
        tr = text_roles[k]
        tr["skills"] = role_skills[i]
        tr["omega"] = core.omega(role_skills[i], w, sk["min_skills_for_omega"])
        no_omega += tr["omega"] is None
        low = tr["text"].lower()
        tr["sig"] = core.signal_types(low, tr["omega"], thr, rx)
        tr["tags"] = sorted(t for t, r in tag_rx.items() if r and r.search(low))
        tr["ls_tags"] = sorted(t for t, r in ls_rx.items() if r and r.search(low))
        tr["onet"] = tm.assign(tr["title"])
        tr["seed_hit"] = bool(role_skills[i] & set(seeds))
        role_text[k] = (tr.pop("text"), tr.pop("blocks"))   # kept aside only for the private labeling packet
    ai_n = sum(1 for t in text_roles.values() if t["sig"]["ai_related"])
    seed_n = sum(1 for t in text_roles.values() if t["seed_hit"])
    step("ai: text roles -> roles naming a seed skill (base rate)", len(text_roles), seed_n)
    oms = sorted(t["omega"] for t in text_roles.values() if t["omega"] is not None)
    if oms:
        q = lambda p: round(oms[min(len(oms) - 1, int(p * (len(oms) - 1)))], 4)
        print(f"[ai: omega quantiles] p10={q(.1)} p25={q(.25)} p50={q(.5)} p75={q(.75)} p90={q(.9)} p99={q(.99)}", flush=True)
        STEPS.append({"step": "ai: omega quantiles (p10,p25,p50,p75,p90,p99)", "in": len(oms), "out": len(oms),
                      "excluded_by_reason": {"p10_x1e4": int(q(.1) * 1e4), "p25_x1e4": int(q(.25) * 1e4), "p50_x1e4": int(q(.5) * 1e4),
                                             "p75_x1e4": int(q(.75) * 1e4), "p90_x1e4": int(q(.9) * 1e4), "p99_x1e4": int(q(.99) * 1e4)}})
    step("ai: text roles -> roles with omega (>= min skills)", len(text_roles), len(text_roles) - no_omega, too_few_skills=no_omega)
    step(f"ai: roles with omega -> AI-related (omega > {thr})", len(text_roles) - no_omega, ai_n)

    firm_text = defaultdict(list)
    for k in rids:
        firm_text[text_roles[k]["firm"]].append(text_roles[k])
    in_scope = [f for f in firm_text if f in firms]
    step("ai: firms in scope -> firms with any text role", len(firms), len(in_scope),
         **{f"at_least_{m}_text_roles": sum(len(firm_text[f]) >= m for f in in_scope) for m in (5, 10, 20, 50)},
         text_role_firms_outside_scope=len(firm_text) - len(in_scope))

    def ai_label(t):
        s = t["sig"]
        if t["omega"] is None:
            return "no-omega"
        return "builds" if s["builds"] else "integrates" if s["integrates"] else "ai-other" if s["ai_related"] else "uses-tools" if s["uses_tools"] else "not-ai"

    # ------------------------------------------------------------ 5. tiers (split-half stability)
    tc = cfg["tier"]
    curve = core.stability_curve({f: [r["major"] for r in firm_roles[f]] for f in firms}, tc["role_count_bins"], tc["splits_per_firm"], tc["random_seed"])
    cutoff, plateau, cut_reason = core.choose_cutoff(curve, tc["plateau_min_roles"], tc["within_plateau"], tc["max_next_gain"], tc["fallback_cutoff"])
    text_curve = core.stability_curve({f: [ai_label(t) for t in firm_text[f] if t["omega"] is not None] for f in firms if firm_text[f]},
                                      tc["role_count_bins"], tc["splits_per_firm"], tc["random_seed"] + 1)
    text_cutoff, text_plateau, text_reason = core.choose_cutoff(text_curve, tc["plateau_min_roles"], tc["within_plateau"], tc["max_next_gain"], tc["fallback_cutoff"])
    tier_a = [f for f in firms if core.assign_tier(len(firm_roles[f]), cutoff) == "A"]
    step(f"tiers: firms -> Tier A (distinct roles >= {cutoff})", len(firms), len(tier_a))

    # ------------------------------------------------------------ 6. LCA (matched cache) -> crosswalk + per-firm filings
    lca_by_firm, crosswalk, lca_meta = defaultdict(list), [], {"present": False}
    lca_path = inp["lca_matched_cache"]
    if os.path.exists(lca_path):
        lca_meta = {"present": True, "log": json.load(open(lca_path.replace(".jsonl.gz", ".log.json")))}
        key_ids = defaultdict(set)
        rows = lca_rows_all
        for row in rows:
            for col, key, ids in row["_match"]:
                key_ids[key].update(ids)
        generic = {"box", "block", "arm", "target", "square", "apple", "amazon", "general", "global", "national", "united", "american", "first", "one"}
        cw_seen = {}
        for row in rows:
            for col, key, ids in row["_match"]:
                for fid in ids:
                    if fid not in firm_names:
                        continue
                    low = len(key) < 4 or key in generic or len(key_ids[key]) > 1
                    conf = "low" if low else "medium"
                    ck = (fid, key)
                    if ck not in cw_seen:
                        cw_seen[ck] = {"firm_id": fid, "source_id": "dol-lca", "source_key": key, "source_name": row.get(col, ""),
                                       "source_address": None, "match_method": "trade-name-dba" if col == "TRADE_NAME_DBA" else "normalised-name",
                                       "confidence": conf, "status": "needs-review" if conf == "low" else "auto-accepted",
                                       "relationship": "unknown", "reviewed_on": None,
                                       "note": "Several collected firms share this normalised name." if len(key_ids[key]) > 1 else None}
                    if conf != "low":
                        lca_by_firm[fid].append(row)
        crosswalk = [cw_seen[k] for k in sorted(cw_seen)]
        dates = sorted(r.get("DECISION_DATE", "")[:10] for r in rows if r.get("DECISION_DATE"))
        lca_from, lca_to = (dates[0], dates[-1]) if dates else tuple(inp["lca_observed"])
        SRC["lca"] = {"id": "dol-lca-fy2024q1-fy2026q3", "name": "DOL LCA disclosure files (9 of 11 quarters; FY2026 Q1-Q2 missing)",
                      "kind": "visa-filing", "location": inp["lca_dir"], "sha256": None, "observed_from": lca_from, "observed_to": lca_to, "stage": "lca"}
        step("lca: matched filing rows -> rows for accepted firm matches", len(rows), sum(len(v) for v in lca_by_firm.values()),
             low_confidence_needs_review=sum(1 for c in crosswalk if c["status"] == "needs-review"))
    else:
        step("lca: matched cache missing (run `pipeline/run.py lca`)", 0, 0)

    buckets = core.load_buckets(list(csv.DictReader(open(cfg["sector"]["buckets_csv"]))))
    vd = cfg["visa_display"]
    counted = set(vd["case_statuses_counted"])

    def units(r):
        """What one counted filing contributes: its positions (blank = the configured default), or 1 if counting cases."""
        if not vd["count_positions_not_cases"]:
            return 1
        return to_int(r.get("TOTAL_WORKER_POSITIONS"), vd["missing_positions_default"])

    # ------------------------------------------------------------ 7. directory companies (self-description, ids)
    directory = json.load(open(inp["directory_json"]))
    dir_comp = {core.norm_employer(r["name"]): r for r in directory["records"] + directory["hubs"] if r["kind"] == "startup"}
    anchors = directory["anchors"]
    boston = {c.lower() for c in cfg["geography"]["boston_area"]}

    # ------------------------------------------------------------ 8. firm records
    companies = {r["company_id"]: r for r in csv.DictReader(open(inp["companies_csv"]))}
    firm_records, index, boston_roles = {}, [], {}
    sector_counts = Counter()
    for f in firms:
        name = firm_names[f].most_common(1)[0][0]
        fr = firm_roles[f]
        n_roles = len(fr)
        tier = core.assign_tier(n_roles, cutoff)
        texts = firm_text.get(f, [])
        t_om = [t for t in texts if t["omega"] is not None]
        not_measured = []

        def nm(code, reason, minimum=None, observed=None, construct=None):
            if construct:
                not_measured.append({"construct": construct, "reason": reason})
            return {"status": "not_measured", "reason_code": code, "reason": reason, "minimum_required": minimum, "observed": observed}

        # geography
        cities, remote, unparsed = Counter(), 0, 0
        for r in fr:
            got = False
            for loc in r["locations"]:
                if "remote" in (loc or "").lower():
                    remote += 1; got = True; break
                cs = core.parse_city_state(loc)
                if cs:
                    cities[cs] += 1; got = True
            unparsed += not got
        in_boston = any(st == "MA" and c.lower() in boston for (c, st) in cities)
        boston_roles[f] = sum(k for (c, st), k in cities.items() if st == "MA" and c.lower() in boston)

        # AI signals
        fps = live_by_firm[f]
        if not texts:
            first_provider = fps[0]["provider"] if fps else ""
            ai = nm("text-selected-by-title" if first_provider in excl_prov else "no-text-for-firm",
                    "Text was collected only for postings chosen by title on this firm's job board." if first_provider in excl_prov
                    else "No posting text for this firm in the 2026-11-11 snapshot.", construct="AI signals")
        elif tier == "B" or len(t_om) < text_cutoff:
            ai = nm("too-few-roles", f"Only {len(t_om)} roles with requirement text; at least {text_cutoff} are needed for a reliable AI shape.",
                    text_cutoff, len(t_om), construct="AI signals")
        else:
            edges = [i / 10 for i in range(11)]
            counts = [0] * 10
            for t in t_om:
                counts[min(9, int(t["omega"] * 10))] += 1
            above = sum(1 for t in t_om if t["sig"]["ai_related"])

            def typ(key):
                rs = [t for t in t_om if t["sig"][key]]
                return {"roles": len(rs), "share": round(len(rs) / len(t_om), 4), "example_titles": sorted({t["title"] for t in rs})[:5]}
            ai = {"status": "measured", "provenance": prov(["snap", "onet"], snap_date, snap_date, len(t_om), cfg["method_versions"]["ai_relatedness"]),
                  "omega_histogram": {"bin_edges": edges, "counts": counts}, "threshold": thr,
                  "share_above_threshold": {"roles": above, "share": round(above / len(t_om), 4)},
                  "by_type": {"builds": typ("builds"), "integrates": typ("integrates"), "uses_tools": typ("uses_tools")}}

        # hiring shape
        if tier == "B":
            shape = nm("too-few-roles", f"{n_roles} distinct roles; at least {cutoff} are needed for a reliable hiring shape.", cutoff, n_roles, construct="Hiring shape")
        else:
            mc = Counter(r["major"] for r in fr)
            dc = Counter(soc6(r["onet"]) for r in fr if r["onet"])
            shape = {"status": "measured", "provenance": prov(["live", "onet"], live_from, live_to, n_roles, cfg["method_versions"]["soc"]),
                     "soc_major": [{"code": c, "title": major_title(c), "roles": k, "share": round(k / n_roles, 4)} for c, k in sorted(mc.items()) if c != "unassigned"],
                     "soc_detailed": [{"code": c, "title": onet_titles.get(c + ".00", c), "roles": k, "share": round(k / n_roles, 4)} for c, k in dc.most_common(25)],
                     "unassigned": {"roles": mc.get("unassigned", 0), "share": round(mc.get("unassigned", 0) / n_roles, 4)},
                     "baselines": {"boston_all": "baselines.boston_all", "bucket_peers": None}, "assignment_basis": "title"}

        # dynamics
        durs = [(core.days_between(x["first_seen"], x["last_seen"]), x["status"] == "gone") for x in fps if x["first_seen"] > live_from]   # dynamics.exclude_first_day
        closed = sorted(d for d, c in durs if c)
        hash_firm = any(x.get("description_sha256") for x in fps)
        rel = core.relisted_roles([{"firm": f, "title": core.norm_role_title(x["title"], req_pat, **title_opts), "locs": core.norm_location_set(x.get("locations"), **loc_opts),
                                    "hash": x.get("description_sha256"), "source_id": x["source_id"], "first_seen": x["first_seen"], "last_seen": x["last_seen"]} for x in fps],
                                  fields=tuple(cfg["dynamics"]["relist_match_fields"]), min_gap_days=cfg["dynamics"]["relist_min_gap_days"])
        dyn = {"status": "measured", "provenance": prov(["live"], live_from, live_to, n_roles, cfg["method_versions"]["dynamics"],
                                                         notes="Postings first seen on the first collection day are left out (their start date is unknown)."),
               "median_days_open_observed": closed[len(closed) // 2] if closed else None, "median_days_open_km": core.km_median(durs),
               "postings_closed": len(closed), "postings_still_open": sum(1 for d, c in durs if not c),
               "relisted_roles": rel if hash_firm else nm("no-source", "This job board does not expose an ad-text hash, so relisting cannot be detected.")}
        months = Counter(r["first_seen"][:7] for r in fr)
        over_time = {"status": "measured", "provenance": prov(["live"], live_from, live_to, n_roles, cfg["method_versions"]["dynamics"],
                                                               notes="October counts include every role already open on the first collection day (2026-10-24)."),
                     "roles_per_month": [{"month": m, "roles": k} for m, k in sorted(months.items())],
                     "ai_share_per_month": nm("no-source", "Posting text exists for one date only (2026-11-11); a monthly series needs the collector change.")}

        # LCA, sector
        lrows = lca_by_firm.get(f, [])
        lca_pos = Counter()
        if lrows:
            cnt_rows = [r for r in lrows if r.get("CASE_STATUS") in counted]
            pos = sum(units(r) for r in cnt_rows)
            by_status = Counter(r.get("CASE_STATUS") or "not stated" for r in lrows)
            wl = Counter()
            socc = Counter()
            fy = Counter()
            vc = Counter()
            sec = 0
            naics = Counter()
            dep = Counter()
            wcities = set()
            for r in cnt_rows:
                p = units(r)
                wl[r.get("PW_WAGE_LEVEL") or "not stated"] += p
                socc[(r.get("SOC_CODE") or "")[:7]] += p
                fy[fiscal_year(r.get("DECISION_DATE", ""))] += p
                vc[r.get("VISA_CLASS") or "not stated"] += p
                sec += p if (r.get("SECONDARY_ENTITY") or "").strip().lower() in ("y", "yes") else 0
                naics[re.sub(r"\D", "", r.get("NAICS_CODE") or "")] += p
                dep[(r.get("H_1B_DEPENDENT") or r.get("H1B_DEPENDENT") or "").strip().lower()[:1]] += 1
                wcities.add(((r.get("WORKSITE_CITY") or "").title(), (r.get("WORKSITE_STATE") or "").upper()))
                lca_pos[((r.get("WORKSITE_CITY") or "").title(), (r.get("WORKSITE_STATE") or "").upper())] += p
            ai_socs = {soc6(t["onet"]) for t in t_om if t["sig"]["ai_related"] and t["onet"]}
            lca = {"status": "measured", "stage": "lca", "positions": pos, "cases": len(cnt_rows), "by_case_status": dict(sorted(by_status.items())),
                   "by_visa_class": dict(sorted(vc.items())), "by_wage_level": dict(sorted(wl.items())),
                   "by_soc": [{"code": c, "title": onet_titles.get(c + ".00", c), "roles": k, "share": round(k / pos, 4) if pos else 0} for c, k in socc.most_common(15) if c],
                   "ai_soc_positions": sum(k for c, k in socc.items() if c in ai_socs) if ai_socs else None,
                   "by_fiscal_year": {k: v for k, v in sorted(fy.items()) if k}, "secondary_entity_positions": sec,
                   "provenance": prov(["lca"], SRC["lca"]["observed_from"], SRC["lca"]["observed_to"], None, cfg["method_versions"]["lca"],
                                      units={"lca_cases": len(cnt_rows), "lca_positions": pos},
                                      notes="Counts certified and certified-withdrawn filings by positions. An LCA is an attestation, not a petition or a hire.")}
            top_naics, top_pos = naics.most_common(1)[0] if naics else ("", 0)
            b_id, b_name, b_pref = core.naics_bucket(top_naics, buckets)
            reassignment = None
            sc = cfg["sector"]
            soft_share = (sum(1 for r in fr if r["onet"] and soc6(r["onet"]) in set(sc["it_services_to_software"]["software_dev_socs"])) / n_roles) if n_roles else 0
            sec_share = sec / pos if pos else 0
            dep_yes = dep.get("y", 0) > dep.get("n", 0)
            if b_id == "it-services":
                ts, keep = sc["it_services_to_software"], sc["it_services_keep"]
                if not (sec_share >= keep["min_secondary_entity_share"] or dep_yes or len(wcities) >= keep["min_worksite_cities"]) \
                        and sec_share <= ts["max_secondary_entity_share"] and len(wcities) <= ts["max_worksite_cities"] and soft_share >= ts["min_software_dev_share"]:
                    reassignment = {"from_bucket": b_id, "to_bucket": "software-internet",
                                    "reason": f"Product-company evidence: {sec_share:.0%} client-site positions, {len(wcities)} worksite cities, {soft_share:.0%} software-development roles.", "inferred": True}
            elif top_naics[:6] in sc["rnd_codes"]:
                rr = sc["rnd_route"]
                ls = sum(1 for r in fr if r["onet"] and any(r["onet"].startswith(p) for p in rr["life_sciences_socs_prefix"])) / n_roles
                semi = sum(1 for r in fr if r["onet"] and soc6(r["onet"]) in rr["semis_socs"]) / n_roles
                eng = sum(1 for r in fr if r["onet"] and any(r["onet"].startswith(p) for p in rr["engineering_socs_prefix"])) / n_roles
                to = "life-sciences" if ls >= rr["min_share"] else "semiconductors-electronics" if semi >= rr["min_share"] else "industrials" if eng >= rr["min_share"] else None
                if to:
                    reassignment = {"from_bucket": b_id, "to_bucket": to, "reason": f"R&D code routed by hiring shape: life sciences {ls:.0%}, semiconductor/electrical {semi:.0%}, engineering {eng:.0%}.", "inferred": True}
            naics_block = {"status": "measured", "code": top_naics, "title": "", "share_of_filings": round(top_pos / pos, 4) if pos else 0, "filings": len(cnt_rows),
                           "basis": "self-reported-on-visa-filings", "similarity": None, "naics_version": "as filed (2017 or 2022; concordance pending)",
                           "provenance": lca["provenance"]}
            bucket = reassignment["to_bucket"] if reassignment else b_id
            if b_id is None:
                not_measured.append({"construct": "Sector bucket", "reason": f"NAICS {top_naics} is not in the bucket roll-up."})
        else:
            lca = nm("no-match-in-source" if lca_meta["present"] else "source-not-approved",
                     "No LCA filings matched this firm's name in the files held (FY2024 Q1 to FY2026 Q3, FY2026 Q1-Q2 missing). Absence here is not evidence that the firm does not sponsor.",
                     construct="LCA filings")
            naics_block = nm("no-source", "No visa filings matched, so there is no self-reported NAICS. Inference from hiring shape waits for the BLS staffing-pattern download.", construct="Sector (NAICS)")
            bucket, reassignment = None, None
        sector_counts[bucket or "not-measured"] += 1

        # application tags (firm level)
        at = cfg["application_tags"]
        tag_counts = Counter(tag for t in texts for tag in t["tags"])
        app_tags = [{"tag": tag, "basis": "requirement-text-terms", "inferred": True, "roles": k} for tag, k in sorted(tag_counts.items())
                    if k >= at["min_roles"] and texts and k / len(texts) >= at["min_share_of_text_roles"]]
        if bucket == "life-sciences":
            ls_counts = Counter(tag for t in texts for tag in t["ls_tags"])
            app_tags += [{"tag": "life-sciences:" + tag, "basis": "requirement-text-terms", "inferred": True, "roles": k} for tag, k in sorted(ls_counts.items()) if k >= at["min_roles"]]

        d_match = dir_comp.get(core.norm_employer(name))
        selfdesc = ({"status": "measured", "provenance": prov(["live"], live_from, live_to, None, "directory-match-v1", notes="Directory summary from startup-jobs; not posting text."), "summary": d_match["summary"]}
                    if d_match and d_match.get("summary") else nm("no-source", "No website or directory description is held for this firm.", construct="Self-description"))

        rec = {
            "schema_version": "firm-v1", "data_version": cfg["data_version"], "firm_id": f, "slug": slugify(f), "name": name,
            "identity": {"ai_jobs_company_ids": [f], "boards": sorted({x["provider"] + ":" + x["board"] for x in fps}),
                         "directory_ids": [d_match["id"]] if d_match else [], "lca_employer_names": sorted({c["source_name"] for c in crosswalk if c["firm_id"] == f and c["status"] == "auto-accepted"}),
                         "crosswalk_rows": sum(1 for c in crosswalk if c["firm_id"] == f), "lowest_match_confidence": None},
            "facts": {"incorporation_year": None, "public_status": None, "private_fundraising": [], "accelerator": [], "parent_company": None, "nonprofit_status": None,
                      "size_proxies": {"distinct_roles": n_roles, "lca_positions_24m": None, "form_d_revenue_range": None}},
            "labels": {"org_label": "not-classified", "rule_version": cfg["method_versions"]["org_label"], "inputs_used": []},
            "sector": {"naics": naics_block, "bucket": bucket, "application_tags": app_tags},
            "geography": {"precision": "city", "cities": [{"city": c, "state": s, "roles": k, "lca_positions": lca_pos.get((c, s)), "source": "posting-location"} for (c, s), k in cities.most_common(40)],
                          "remote_roles": remote, "unparsed_location_roles": unparsed},
            "tier": {"tier": tier, "distinct_roles": n_roles, "text_roles": len(t_om), "cutoff": cutoff, "text_cutoff": text_cutoff, "rule_version": cfg["method_versions"]["tier"]},
            "sections": {
                "ai_signals": ai, "hiring_shape": shape,
                "lexicon": nm("no-source", "No pipeline tags postings with Irreducibly Human Work Lexicon concepts yet.", construct="Lexicon concept profile"),
                "exposure": nm("deferred-by-decision", "Exposure score deferred (decision B, 2026-11-22): no occupation-level exposure data is approved for this site.", construct="Exposure score"),
                "over_time": over_time, "posting_dynamics": dyn,
                "visa_filings": {"lca": lca,
                                 "perm": nm("source-not-approved", "PERM files approved 2026-11-22; download pending.", construct="PERM filings"),
                                 "prevailing_wage": nm("source-not-approved", "Prevailing-wage files approved 2026-11-22; download pending.", construct="Wage determinations"),
                                 "uscis": nm("source-not-approved", "USCIS hub availability to be verified before use.", construct="USCIS petition decisions"),
                                 "not_covered_note": vd["not_covered_note"], "past_not_future_note": vd["past_not_future_note"]},
                "evidence_of_building": nm("no-source", "No papers, repositories, patents or model releases are held. Never computed from postings.", construct="Evidence of building AI"),
                "self_description": selfdesc,
            },
            "not_measured": not_measured, "computed_at": computed_at,
        }
        if reassignment:
            rec["sector"]["reassignment"] = reassignment
        firm_records[f] = rec
        index.append({"firm_id": f, "slug": rec["slug"], "name": name, "tier": tier, "org_label": "not-classified", "bucket": bucket,
                      "bucket_basis": ("inferred: " + reassignment["reason"]) if reassignment else ("self-reported NAICS on LCA filings" if bucket else None),
                      "application_tags": [t["tag"] for t in app_tags], "cities": [f"{c}, {s}" for (c, s), _ in cities.most_common(10)], "in_boston_area": in_boston,
                      "distinct_roles": n_roles, "text_roles": len(t_om),
                      "ai_share": ai["share_above_threshold"]["share"] if ai["status"] == "measured" else None,
                      "signal_types": {k: (ai["by_type"][k]["roles"] if ai["status"] == "measured" else None) for k in ("builds", "integrates", "uses_tools")},
                      "visa_stages_present": ["lca"] if lrows else [], "lca_positions_24m": None, "directory_id": d_match["id"] if d_match else None,
                      "hiring_now": sum(1 for r in fr if r["open"]),
                      "company_list_sector": (companies.get(f) or {}).get("sector")})
    step("firms: records built", len(firms), len(firm_records))
    step("sector: firms with a measured bucket", len(firms), len(firms) - sector_counts["not-measured"])

    # ------------------------------------------------------------ 9. ecosystem aggregates
    rows_t = ["builds", "integrates", "uses_tools", "none"]
    cols = sorted({x["bucket"] for x in index if x["bucket"]}) + ["sector not measured"]
    measured = [x for x in index if x["ai_share"] is not None]
    ag = cfg["aggregation"]
    largest = {x["firm_id"] for x in sorted(index, key=lambda x: -x["distinct_roles"])[:ag["exclude_largest_n"]]}
    cells = []
    for rt in rows_t:
        row = []
        for c in cols:
            fs = [x for x in measured if (x["bucket"] or "sector not measured") == c and
                  ((x["signal_types"][rt] or 0) > 0 if rt != "none" else not any((x["signal_types"][k] or 0) > 0 for k in rows_t[:3]))]
            roles_n = sum((x["signal_types"][rt] or 0) if rt != "none" else x["text_roles"] for x in fs)
            roles_nl = sum((x["signal_types"][rt] or 0) if rt != "none" else x["text_roles"] for x in fs if x["firm_id"] not in largest)
            row.append({"firms": len(fs), "roles": roles_n, "roles_excluding_largest_firm": roles_nl})
        cells.append(row)
    hist = [0] * 10
    for x in measured:
        hist[min(9, int(x["ai_share"] * 10))] += 1
    omega_hist = [0] * 10
    for t in text_roles.values():
        if t["omega"] is not None:
            omega_hist[min(9, int(t["omega"] * 10))] += 1
    city_c = defaultdict(lambda: {"firms": set(), "roles": 0})
    for f in firms:
        for c in firm_records[f]["geography"]["cities"]:
            k = (c["city"], c["state"])
            city_c[k]["firms"].add(f)
            city_c[k]["roles"] += c["roles"]
    cities_out = []
    for (c, s), v in sorted(city_c.items(), key=lambda kv: -kv[1]["roles"]):
        a = anchors.get(f"{c}, {s}")
        cities_out.append({"city": c, "state": s, "latitude": a[0] if a else None, "longitude": a[1] if a else None, "precision": "city",
                           "coordinate_source": "directory.json anchors" if a else None, "firms": len(v["firms"]), "roles": v["roles"], "ai_roles": None, "lca_positions": None})
    bl = cfg["baselines"]
    tier_of = {x["firm_id"]: x["tier"] for x in index}
    bos = [f for f in firms if tier_of[f] in bl["boston_tiers"] and boston_roles[f] >= bl["boston_min_roles_in_area"]]

    def firm_weighted_shape(fs):
        acc = Counter()
        for f in fs:
            d = core.distribution(r["major"] for r in firm_roles[f])
            for k, v in d.items():
                acc[k] += v / len(fs)
        return [{"code": k, "title": major_title(k), "roles": sum(1 for f in fs for r in firm_roles[f] if r["major"] == k), "share": round(v, 4)} for k, v in sorted(acc.items())]
    eco = {
        "schema_version": "ecosystem-v1", "data_version": cfg["data_version"], "computed_at": computed_at, "config_sha256": cfg_sha,
        "inputs": [v for v in SRC.values()], "step_counts": STEPS, "firms": [{k: v for k, v in x.items() if k not in ("hiring_now", "company_list_sector")} for x in index],
        "matrices": {"signal_type_by_bucket": {"weighting": ag["default_weighting"], "rows": rows_t, "columns": cols, "cells": cells,
                                               "provenance": prov(["snap"] + (["lca"] if "lca" in SRC else []), snap_date, snap_date, sum(x["text_roles"] for x in measured), cfg["method_versions"]["signal_types"],
                                                                  notes="Cells count firms with at least one role of the type; roles are also given without the largest firm.")}},
        "distributions": {"firm_ai_share": {"histogram": {"bin_edges": [i / 10 for i in range(11)], "counts": hist}, "firms_measured": len(measured),
                                            "firms_not_measured": len(index) - len(measured),
                                            "provenance": prov(["snap"], snap_date, snap_date, sum(x["text_roles"] for x in measured), cfg["method_versions"]["ai_relatedness"])},
                          "role_omega": {"histogram": {"bin_edges": [i / 10 for i in range(11)], "counts": omega_hist},
                                         "provenance": prov(["snap"], snap_date, snap_date, len(text_roles) - no_omega, cfg["method_versions"]["ai_relatedness"])}},
        "cities": cities_out,
        "baselines": {"boston_all": {"soc_major": firm_weighted_shape(bos), "firms": len(bos), "roles": sum(len(firm_roles[f]) for f in bos), "weighting": ag["default_weighting"],
                                     "provenance": prov(["live", "onet"], live_from, live_to, sum(len(firm_roles[f]) for f in bos), cfg["method_versions"]["soc"],
                                                        notes="Tier A firms with at least one role in a Boston-area town (config list).")},
                      "by_bucket": {b: {"soc_major": firm_weighted_shape([x["firm_id"] for x in index if x["bucket"] == b and x["tier"] == "A"])} for b in cols[:-1]}},
        "tier_rule": {"cutoff": cutoff, "text_cutoff": text_cutoff,
                      "stability_curve": [{"roles": r["roles_from"], "firms": r["firms"], "median_similarity": r["median_similarity"], "p25": r["p25"], "p75": r["p75"]} for r in curve if r["firms"]],
                      "provenance": prov(["live", "onet"], live_from, live_to, len(roles), cfg["method_versions"]["tier"], notes=f"Plateau {plateau}; {cut_reason}. Text cutoff: plateau {text_plateau}; {text_reason}.")},
        "research_layer": {"source": inp["directory_json"], "records": sum(1 for r in directory["records"] + directory["hubs"] if r["kind"] == "research"),
                           "note": "Research groups stay a separate, toggleable layer and never enter firm aggregates."},
        "filter_coverage": {
            "sector_bucket": {"known": sum(1 for x in index if x["bucket"]), "total": len(index)},
            "ai_signal_type": {"known": len(measured), "total": len(index)},
            "has_filed_lca": {"known": sum(1 for x in index if x["visa_stages_present"]), "total": len(index), "note": "Known = matched in the files held; unknown is not 'no'."},
            "org_label": {"known": 0, "total": len(index), "note": "Facts sources (Form D, EDGAR, IRS) approved; downloads pending."},
            "hiring_now": {"known": len(index), "total": len(index)},
        },
    }

    # ------------------------------------------------------------ 10. validate and write
    schema_dir = os.path.join(HERE, "schemas")
    errors = []
    for f in firms:
        errors += [f"{f}: {e}" for e in validate(firm_records[f], os.path.join(schema_dir, "firm.schema.json"))]
    errors += [f"ecosystem: {e}" for e in validate(eco, os.path.join(schema_dir, "ecosystem.schema.json"))]
    for c in crosswalk:
        errors += [f"crosswalk: {e}" for e in validate(c, os.path.join(schema_dir, "crosswalk.schema.json"))]
    step("validate: records checked against schemas", len(firms) + 1 + len(crosswalk), len(firms) + 1 + len(crosswalk) - len(errors))
    for f in firms:
        json.dump(firm_records[f], open(os.path.join(out_dir, "firms", firm_records[f]["slug"] + ".json"), "w"), indent=1, sort_keys=True)
    json.dump(eco, open(os.path.join(out_dir, "ecosystem.json"), "w"), indent=1, sort_keys=True)
    with open(os.path.join(out_dir, "crosswalk.jsonl"), "w") as fh:
        for c in crosswalk:
            fh.write(json.dumps(c, sort_keys=True) + "\n")

    # ------------------------------------------------------------ 11. review files
    rv = cfg["review"]
    rd = os.path.join(out_dir, "review")
    with open(os.path.join(rd, "top-skills-by-w.tsv"), "w") as fh:
        fh.write("rank\tskill\tw\troles_with_skill\troles_with_skill_and_seed\tfirms\n")
        ranked = sorted((s for s in w if s not in seeds and s in vocab), key=lambda s: (-w[s], -vocab[s][0], s))[:rv["top_skills"]]
        for i, s in enumerate(ranked, 1):
            fh.write(f"{i}\t{s}\t{w[s]:.3f}\t{vocab[s][0]}\t{round(w[s] * vocab[s][0])}\t{vocab[s][1]}\n")
        fh.write("\n# seed skills (w = 1 by construction)\n")
        seed_df = Counter(s for t in text_roles.values() for s in t["skills"] if s in seeds)
        for s in seeds:
            fh.write(f"seed\t{s}\t1.000\t{seed_df.get(s, 0)}\t{seed_df.get(s, 0)}\t\n")
    rng = random.Random(rv["seed"])
    pool = sorted((k for k in text_roles if text_roles[k]["omega"] is not None), key=lambda k: text_roles[k]["posting_id"])
    sample = rng.sample(pool, min(rv["random_roles"], len(pool)))
    with open(os.path.join(rd, "roles-sample-50.csv"), "w", newline="") as fh:
        wr = csv.writer(fh)
        wr.writerow(["posting_id", "firm", "title", "omega", "ai_related", "builds", "integrates", "uses_tools", "seed_skill_present", "soc", "human_label"])
        for k in sample:
            t = text_roles[k]
            wr.writerow([t["posting_id"], t["firm"], t["title"], f"{t['omega']:.3f}", t["sig"]["ai_related"], t["sig"]["builds"], t["sig"]["integrates"], t["sig"]["uses_tools"], t["seed_hit"], t["onet"] or "unassigned", ""])
    # Labeling packet: titles and ad text for the sampled roles, kept OUTSIDE the repo (ad text is never committed).
    # It carries no scores, flags or firm ids, so the labeler stays blind to the measure.
    # Branch runs (private_outputs=False) never write it.
    if private_outputs:
        pdir = inp["private_review_dir"]
        os.makedirs(pdir, exist_ok=True)
        packet = {"name": "roles-sample-50", "snapshot_date": snap_date, "config_sha256": cfg_sha,
                  "roles": [{"n": i + 1, "posting_id": text_roles[k]["posting_id"], "title": text_roles[k]["title"],
                             "requirement_text": role_text[k][0], "full_ad": role_text[k][1]} for i, k in enumerate(sample)]}
        tmp = os.path.join(pdir, "roles-sample-50.packet.json.tmp")
        with open(tmp, "w") as fh:
            json.dump(packet, fh, ensure_ascii=False, indent=1)
        os.replace(tmp, os.path.join(pdir, "roles-sample-50.packet.json"))
    picks = rng.sample(sorted(tier_a), min(rv["random_tier_a_firms"], len(tier_a)))
    with open(os.path.join(rd, "tier-a-shapes-20.md"), "w") as fh:
        fh.write(f"# Hiring shapes of {len(picks)} random Tier A firms\n\nTier A = at least {cutoff} distinct roles. SOC by exact title match (O*NET 31.0). AI signals from the {snap_date} snapshot.\n\n")
        for f in sorted(picks):
            r = firm_records[f]
            hs, ai = r["sections"]["hiring_shape"], r["sections"]["ai_signals"]
            fh.write(f"## {r['name']} ({r['tier']['distinct_roles']} roles, bucket: {r['sector']['bucket'] or 'not measured'})\n\n| SOC major group | Roles | Share |\n|---|---:|---:|\n")
            for x in sorted(hs["soc_major"], key=lambda x: -x["roles"]):
                fh.write(f"| {x['title']} | {x['roles']} | {x['share']:.0%} |\n")
            fh.write(f"| Unassigned | {hs['unassigned']['roles']} | {hs['unassigned']['share']:.0%} |\n\n")
            if ai["status"] == "measured":
                b = ai["by_type"]
                fh.write(f"AI: {ai['share_above_threshold']['share']:.0%} of {r['tier']['text_roles']} text roles above omega {thr}; builds {b['builds']['roles']}, integrates {b['integrates']['roles']}, uses tools {b['uses_tools']['roles']}.\n\n")
            else:
                fh.write(f"AI: not measured. {ai['reason']}\n\n")
    def band(n):
        return "1-4" if n < 5 else "5-19" if n < 20 else "20-49" if n < 50 else "50-199" if n < 200 else "200+"
    with open(os.path.join(rd, "included-vs-excluded.md"), "w") as fh:
        fh.write(f"# Included (Tier A) vs excluded (Tier B) firms\n\nCutoff: {cutoff} distinct roles. Sector = bucket from LCA NAICS where measured; otherwise the ai-jobs company-list sector, shown in brackets (a list label, not NAICS).\n\n")
        for title, key in (("Sector", lambda x: x["bucket"] or f"[{x['company_list_sector'] or 'none'}]"),
                           ("Size proxy (distinct roles)", lambda x: band(x["distinct_roles"])),
                           ("AI signal", lambda x: "not measured" if x["ai_share"] is None else "AI share 0" if x["ai_share"] == 0 else "AI share > 0 and < 10%" if x["ai_share"] < 0.1 else "AI share 10% or more")):
            fh.write(f"## {title}\n\n| Value | Tier A firms | Tier B firms |\n|---|---:|---:|\n")
            c = Counter((key(x), x["tier"]) for x in index)
            for v in sorted({k for k, _ in c}):
                fh.write(f"| {v} | {c.get((v, 'A'), 0)} | {c.get((v, 'B'), 0)} |\n")
            fh.write("\n")
    with open(os.path.join(rd, "stability-curve.tsv"), "w") as fh:
        fh.write("shape\troles_from\troles_to\tfirms\tmedian_similarity\tp25\tp75\n")
        for name_, cv in (("soc-major", curve), ("ai-signal", text_curve)):
            for r in cv:
                fh.write(f"{name_}\t{r['roles_from']}\t{r['roles_to']}\t{r['firms']}\t{r['median_similarity']}\t{r['p25']}\t{r['p75']}\n")
        fh.write(f"\n# cutoff {cutoff} (plateau {plateau}; {cut_reason})\n# text cutoff {text_cutoff} (plateau {text_plateau}; {text_reason})\n")
    json.dump({"computed_at": computed_at, "config_sha256": cfg_sha, "steps": STEPS, "schema_errors": errors[:200], "schema_error_count": len(errors),
               "lca": lca_meta.get("log")}, open(os.path.join(rd, "run-log.json"), "w"), indent=1)
    print(f"schema errors: {len(errors)}", flush=True)
    for e in errors[:15]:
        print("  " + e, flush=True)
    return 0 if not errors else 2
