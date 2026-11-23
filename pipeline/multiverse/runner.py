"""The branch runner: `python3 -I pipeline/run.py branch BR-nnnn [--as NAME]`.

1. Check the code: pipeline/ must be committed and clean.
2. Check the decision: the person is cleared by the roster; the registry agrees with the config; the override
   passes every rule; for any branch but BR-0000, the key results are signed off and the proposal's latest
   decision is the lead author's `accepted` (or `adopted`).
3. Build the effective config (base + override) and hash it as canonical JSON.
4. Run the job map build under the read and write guard, into the branch's own run folder.
5. Compute the key results and compare them with BR-0000 at the same commit (run BR-0000 first if needed).
6. Write provenance, and append a `run` event to the decision log.

The job map build is the only analysis this runner can call."""
import contextlib
import hashlib
import json
import os

from . import keyresults, logs, overrides, provenance, registry
from .common import LOCKED_PATHS_FLOOR, Paths, canonical_sha256, load_json, load_yaml, under, with_overrides
from .guard import Guard

RUNNER_VERSION = "multiverse-runner-v1"
ANALYSIS = "ai-job-map (pipeline/ai_job_map/build.py)"
PROVENANCE_FIELDS = ("runner_version", "analysis", "status", "exit_code", "branch_id", "proposal_id", "decision_point",
                     "overrides", "override_file_sha256", "base_config_sha256", "effective_config_sha256", "code_commit",
                     "code_dirty", "environment", "started_at", "finished_at", "ran_by", "inputs", "locked_paths",
                     "outputs_dir", "compared_with")


class Refused(Exception):
    """The runner will not run this branch; the message says why."""


def job_map_analysis(cfg, out_dir):
    from pipeline.ai_job_map import build
    return build.main(cfg=cfg, out_dir=out_dir, private_outputs=False)


def locked_roots(paths, cfg):
    rel = list(LOCKED_PATHS_FLOOR) + [p for p in (cfg.get("multiverse") or {}).get("locked_paths", []) if p not in LOCKED_PATHS_FLOOR]
    return [os.path.join(paths.root, p) for p in rel], rel


def check_gates(paths, branch_id, person):
    """Everything that must hold before anything runs. Raises Refused with the reason."""
    code = provenance.code_state(paths.root)
    if code["dirty"]:
        raise Refused("pipeline/ has uncommitted changes; commit them first so the run can name its code: "
                      + ", ".join(code["dirty_paths"][:10]))
    roster = logs.load_roster(paths)
    ok, why = logs.cleared(roster, person)
    if not ok:
        raise Refused(why)
    branch = overrides.load_branch(paths, branch_id)
    points = registry.load(paths)
    base_cfg = load_json(paths.config)
    reg_errs = registry.check(points, base_cfg)
    if reg_errs:
        raise Refused("the registry and the config disagree (run check-registry): " + "; ".join(reg_errs[:5]))
    errs = overrides.validate(branch, points, base_cfg)
    if errs:
        raise Refused("; ".join(errs))
    kr_spec = load_yaml(paths.key_results)
    if branch_id != overrides.DEFAULT_BRANCH:
        lead = logs.lead_author(roster)
        if not lead or kr_spec.get("signed_off_by") != lead:
            raise Refused("the key results and flip rules (paper/multiverse/key_results.yaml) are not signed off by the "
                          "lead author; only BR-0000 runs until they are")
        dec = logs.latest_decision(logs.load_events(paths), branch["proposal_id"])
        if dec is None or dec.get("status") not in ("accepted", "adopted"):
            raise Refused(f"{branch['proposal_id']}'s latest decision is {dec.get('status') if dec else 'missing'}, not accepted")
        if dec.get("decided_by") != lead:
            raise Refused(f"{branch['proposal_id']} was not accepted by the lead author")
        if dec.get("decision_point") != branch["decision_point"]:
            raise Refused(f"{branch['proposal_id']} was accepted for {dec.get('decision_point')}, not {branch['decision_point']}")
        if not os.path.exists(os.path.join(paths.proposals, branch["proposal_id"] + ".md")):
            raise Refused(f"no proposal file paper/multiverse/proposals/{branch['proposal_id']}.md")
    return {"code": code, "roster": roster, "branch": branch, "base_cfg": base_cfg, "kr_spec": kr_spec}


def new_run_dir(paths, branch_id, now):
    base = os.path.join(paths.runs, branch_id, now.strftime("%Y-%m-%dT%H-%M-%SZ"))
    d, n = base, 1
    while os.path.exists(d):
        n += 1
        d = f"{base}-{n}"
    if not overrides.BRANCH_RE.match(branch_id) or not under(d, [paths.runs]):
        raise Refused(f"run folder {d} would be outside paper/multiverse/runs/")
    return d


def execute(paths, g, analysis, person, now, compared_with=None):
    """Run one branch into a new run folder. Returns (run_dir, provenance, key results)."""
    branch, base_cfg = g["branch"], g["base_cfg"]
    eff = with_overrides(base_cfg, branch["overrides"])
    run_dir = new_run_dir(paths, branch["branch_id"], now)
    out_dir = os.path.join(run_dir, "outputs")
    os.makedirs(out_dir)
    with open(os.path.join(run_dir, "effective-config.json"), "w") as fh:
        json.dump(eff, fh, indent=1, sort_keys=True)
    with open(os.path.join(paths.branches, branch["branch_id"] + ".yaml"), "rb") as fh:
        override_sha = hashlib.sha256(fh.read()).hexdigest()
    roots, rel_roots = locked_roots(paths, base_cfg)
    started = logs.utc_now()
    with open(os.path.join(run_dir, "build.log"), "w") as log, contextlib.redirect_stdout(log):
        with Guard(roots, [run_dir]) as guard:
            rc = analysis(eff, out_dir)
    finished = logs.utc_now()
    cache = provenance.HashCache(os.path.join(paths.runs, ".hash-cache.json"))
    prov = {
        "runner_version": RUNNER_VERSION, "analysis": ANALYSIS, "status": "ok" if rc == 0 else "failed", "exit_code": rc,
        "branch_id": branch["branch_id"], "proposal_id": branch.get("proposal_id"), "decision_point": branch.get("decision_point"),
        "overrides": branch["overrides"], "override_file_sha256": override_sha,
        "base_config_sha256": canonical_sha256(base_cfg), "effective_config_sha256": canonical_sha256(eff),
        "code_commit": g["code"]["commit"], "code_dirty": g["code"]["dirty"], "environment": provenance.environment(),
        "started_at": logs.iso(started), "finished_at": logs.iso(finished),
        "ran_by": provenance.who_ran(paths.root, person),
        "inputs": provenance.input_records(guard.reads, paths.root, cache),
        "locked_paths": rel_roots, "outputs_dir": paths.rel(out_dir), "compared_with": compared_with,
    }
    cache.save()
    kr = None
    if rc == 0:
        kr = keyresults.compute(load_json(os.path.join(out_dir, "ecosystem.json")), g["kr_spec"])
        with open(os.path.join(run_dir, "key_results.json"), "w") as fh:
            json.dump(kr, fh, indent=1, sort_keys=True)
    with open(os.path.join(run_dir, "provenance.json"), "w") as fh:
        json.dump(prov, fh, indent=1, sort_keys=True)
    return run_dir, prov, kr


def find_default(paths, commit, base_sha):
    """A finished BR-0000 run at this commit and config whose inputs still hash the same, or None."""
    d = os.path.join(paths.runs, overrides.DEFAULT_BRANCH)
    if not os.path.isdir(d):
        return None
    cache = provenance.HashCache(os.path.join(paths.runs, ".hash-cache.json"))
    for stamp in sorted(os.listdir(d), reverse=True):
        p = os.path.join(d, stamp, "provenance.json")
        if not os.path.exists(p):
            continue
        prov = load_json(p)
        if (prov.get("status") != "ok" or prov.get("code_commit") != commit or prov.get("base_config_sha256") != base_sha
                or prov.get("runner_version") != RUNNER_VERSION):
            continue
        if all(os.path.isfile(i["path"]) and cache.record(i["path"])["sha256"] == i["sha256"] for i in prov["inputs"]):
            cache.save()
            return os.path.join(d, stamp)
    return None


def run_branch(branch_id, person, paths=None, analysis=job_map_analysis, now=None):
    """Run one branch. Returns {"run_dir", "key_results", "diff", "provenance"}; raises Refused."""
    paths = paths or Paths()
    g = check_gates(paths, branch_id, person)
    is_default = branch_id == overrides.DEFAULT_BRANCH
    default_dir = None
    if not is_default:
        default_dir = find_default(paths, g["code"]["commit"], canonical_sha256(g["base_cfg"]))
        if default_dir is None:
            default_dir = run_branch(overrides.DEFAULT_BRANCH, person, paths, analysis, now)["run_dir"]
    run_dir, prov, kr = execute(paths, g, analysis, person, now or logs.utc_now(),
                                compared_with=paths.rel(default_dir) if default_dir else None)
    if kr is None:
        raise Refused(f"the build failed (exit code {prov['exit_code']}); see {paths.rel(run_dir)}/build.log")
    default_kr = kr if is_default else load_json(os.path.join(default_dir, "key_results.json"))
    d = keyresults.diff(default_kr, kr, g["kr_spec"])
    with open(os.path.join(run_dir, "diff_vs_default.json"), "w") as fh:
        json.dump(d, fh, indent=1, sort_keys=True)
    if not is_default:
        b = g["branch"]
        logs.append_event(paths, {"proposal_id": b["proposal_id"], "decision_point": b["decision_point"], "status": "run",
                                  "results_link": paths.rel(run_dir)}, now=logs.parse_iso(prov["finished_at"]))
    return {"run_dir": run_dir, "key_results": kr, "diff": d, "provenance": prov}
