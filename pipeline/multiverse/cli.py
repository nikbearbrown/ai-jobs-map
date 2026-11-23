"""Command line for the multiverse tools, reached through pipeline/run.py:

    python3 -I pipeline/run.py check-registry
    python3 -I pipeline/run.py branch BR-0001 [--as "Name in roster"]
    python3 -I pipeline/run.py log-event --proposal P-0001 --dp DP-18 --status accepted --by "Lead Author" --reason "..."

A branch prints only its key results and their comparison with the default. Firm-level outputs stay in the run
folder on this Mac."""
import argparse
import json
import sys

from . import keyresults, logs, provenance, registry
from .common import Paths, load_json
from .runner import Refused, run_branch


def check_registry(argv):
    paths = Paths()
    points = registry.load(paths)
    errs = registry.check(points, load_json(paths.config))
    for e in errs:
        print("  " + e)
    n_params = sum(len(p.get("parameters") or []) for p in points)
    print(f"{len(points)} decision points, {n_params} parameters: {'OK' if not errs else str(len(errs)) + ' problems'}")
    return 0 if not errs else 1


def branch(argv):
    ap = argparse.ArgumentParser(prog="run.py branch")
    ap.add_argument("branch_id")
    ap.add_argument("--as", dest="person", help="your name as it appears in paper/roster.yaml (default: git user.name)")
    a = ap.parse_args(argv)
    paths = Paths()
    person = a.person or provenance.who_ran(paths.root, None)["git_user"]
    try:
        r = run_branch(a.branch_id, person, paths)
    except (Refused, ValueError, FileNotFoundError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
    print(f"\n{a.branch_id}: {paths.rel(r['run_dir'])}")
    if r["provenance"]["compared_with"]:
        print(f"compared with {r['provenance']['compared_with']}")
    print(keyresults.table(r["diff"]))
    return 0


def log_event(argv):
    ap = argparse.ArgumentParser(prog="run.py log-event")
    ap.add_argument("--proposal", required=True)
    ap.add_argument("--dp", required=True)
    ap.add_argument("--status", required=True, choices=[s for s in logs.STATUSES if s != "run"])
    ap.add_argument("--by", help="the lead author, for accepted, rejected and adopted")
    ap.add_argument("--proposer")
    ap.add_argument("--alternative")
    ap.add_argument("--reason")
    ap.add_argument("--corrects")
    a = ap.parse_args(argv)
    try:
        e = logs.append_event(Paths(), {"proposal_id": a.proposal, "decision_point": a.dp, "status": a.status,
                                        "decided_by": a.by, "proposer": a.proposer, "alternative": a.alternative,
                                        "reason": a.reason, "corrects": a.corrects})
    except logs.LogError as err:
        print(f"refused: {err}", file=sys.stderr)
        return 3
    print(json.dumps(e, indent=1))
    return 0


COMMANDS = {"check-registry": check_registry, "branch": branch, "log-event": log_event}


def main(cmd, argv):
    return COMMANDS[cmd](argv)
