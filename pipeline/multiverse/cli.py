"""Command line for the multiverse tools, reached through pipeline/run.py:

    python3 -I pipeline/run.py check-registry
    python3 -I pipeline/run.py branch BR-0001 [--as "Name in roster"]
    python3 -I pipeline/run.py log-event --proposal P-0001 --dp DP-18 --status accepted --by "Lead Author" --reason "..."

and the commands the /contribute skill calls (pipeline/multiverse/contribute.py):

    status, points, key-results, own, new-proposal, propose, new-branch, new-interpretation, log-contribution,
    log-verification

A branch prints only its key results and their comparison with the default. Firm-level outputs stay in the run
folder on this Mac."""
import argparse
import json
import sys

from . import contribute, keyresults, logs, provenance, registry
from .common import Paths, load_json, load_yaml
from .runner import Refused, run_branch


def _person(paths, given):
    return given or provenance.who_ran(paths.root, None)["git_user"]


def check_registry(argv):
    paths = Paths()
    points = registry.load(paths)
    errs = registry.check(points, load_json(paths.config)) + logs.check_log(logs.load_events(paths))
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
    person = _person(paths, a.person)
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
    ap.add_argument("--status", required=True, choices=list(logs.LEAD_DECIDES),
                    help="the lead author's decision; proposals are logged with `propose`, runs by the runner")
    ap.add_argument("--by", help="the lead author, for accepted, rejected and adopted")
    ap.add_argument("--proposer")
    ap.add_argument("--alternative")
    ap.add_argument("--reason")
    ap.add_argument("--corrects")
    a = ap.parse_args(argv)
    paths = Paths()
    try:
        contribute.check_lead_identity(paths, a.by, provenance.who_ran(paths.root, None)["git_user"])
        e = logs.append_event(paths, {"proposal_id": a.proposal, "decision_point": a.dp, "status": a.status,
                                      "decided_by": a.by, "proposer": a.proposer, "alternative": a.alternative,
                                      "reason": a.reason, "corrects": a.corrects})
    except (logs.LogError, contribute.ContributeError) as err:
        print(f"refused: {err}", file=sys.stderr)
        return 3
    print(json.dumps(e, indent=1))
    return 0


def status(argv):
    ap = argparse.ArgumentParser(prog="run.py status")
    ap.add_argument("--as", dest="person", required=True, help="the contributor's name, as they give it")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    s = contribute.status(Paths(), a.person)
    if a.json:
        print(json.dumps(s, indent=1))
        return 0
    print(f"{s['name']}: {'in' if s['in_roster'] else 'NOT in'} paper/roster.yaml"
          + (f" ({s['role']})" if s["role"] else "") + (", lead author" if s["is_lead_author"] else ""))
    print(f"results: {'may see results' if s['cleared_for_results'] else 'NO RESULTS'}. {s['why']}")
    print(f"owns: {', '.join(s['owns']) or 'nothing yet'}")
    for p in s["proposals"]:
        line = f"  {p['proposal_id']} {p['decision_point'] or ''} {p['status']}"
        if p.get("branch"):
            line += f", {p['branch']}"
        if s["cleared_for_results"] and p.get("reason"):
            line += f": {p['reason']}"
        print(line)
    return 0


def points(argv):
    ap = argparse.ArgumentParser(prog="run.py points")
    ap.add_argument("--all", action="store_true", help="every point, not just the open, unlocked ones")
    a = ap.parse_args(argv)
    rows = contribute.points(Paths(), a.all)
    for p in rows:
        tag = "locked" if p.get("locked") else p.get("branchable")
        who = f", owned by {p['owner']}" if p.get("owner") else ""
        prov = ", provisional" if p.get("default_status") == "provisional" else ""
        print(f"{p['id']}  {p['title']}  [{tag}{prov}{who}]\n        now: {p['current_value']}")
    print(f"{len(rows)} points")
    return 0


def key_results(argv):
    """The key results' ids, titles and flip rules, without the default values (which are results)."""
    argparse.ArgumentParser(prog="run.py key-results").parse_args(argv)
    spec = load_yaml(Paths().key_results)
    print(f"status: {spec.get('status')}" + (f", signed off by {spec['signed_off_by']} on {spec['signed_off_on']}"
                                              if spec.get("signed_off_by") else ""))
    for r in spec["results"]:
        rule = r["flip_rule"] + (f" {r['threshold']:.0%}" if r.get("threshold") is not None else "")
        print(f"{r['id']}  {r['title']}  [flip rule: {rule}]")
    return 0


def own(argv):
    ap = argparse.ArgumentParser(prog="run.py own")
    ap.add_argument("dp")
    ap.add_argument("--as", dest="person", required=True)
    ap.add_argument("--release", action="store_true")
    a = ap.parse_args(argv)
    p = contribute.own(Paths(), a.dp, a.person, a.release)
    print(f"{p['id']}: owner {p['owner']}, status {p['status']}")
    return 0


def new_proposal(argv):
    ap = argparse.ArgumentParser(prog="run.py new-proposal")
    ap.add_argument("dp")
    ap.add_argument("--as", dest="person", required=True)
    ap.add_argument("--eliminate", action="store_true", help="the proposer expects to argue this alternative out")
    ap.add_argument("--seen-results", choices=["yes", "no"])
    a = ap.parse_args(argv)
    paths = Paths()
    seen = None if a.seen_results is None else a.seen_results == "yes"
    pid, path = contribute.new_proposal(paths, a.dp, a.person, a.eliminate, seen)
    print(f"{pid}: {paths.rel(path)}")
    return 0


def propose(argv):
    ap = argparse.ArgumentParser(prog="run.py propose")
    ap.add_argument("proposal_id")
    ap.add_argument("--ai", help="what Claude Code did for this proposal, for its ai_assistance line")
    a = ap.parse_args(argv)
    e = contribute.propose(Paths(), a.proposal_id, a.ai)
    print(json.dumps(e, indent=1))
    return 0


def new_branch(argv):
    ap = argparse.ArgumentParser(prog="run.py new-branch")
    ap.add_argument("proposal_id")
    ap.add_argument("--set", dest="sets", action="append", default=[], metavar="KEY=VALUE")
    a = ap.parse_args(argv)
    paths = Paths()
    b = contribute.new_branch(paths, a.proposal_id, a.sets)
    print(json.dumps(b, indent=1))
    for w in contribute.override_checks(paths, b):
        print("check: " + w)
    return 0


def new_interpretation(argv):
    ap = argparse.ArgumentParser(prog="run.py new-interpretation")
    ap.add_argument("branch_id")
    ap.add_argument("--as", dest="person", required=True)
    a = ap.parse_args(argv)
    paths = Paths()
    print(paths.rel(contribute.new_interpretation(paths, a.branch_id, a.person)))
    return 0


def log_contribution(argv):
    ap = argparse.ArgumentParser(prog="run.py log-contribution")
    ap.add_argument("--as", dest="person", required=True)
    ap.add_argument("--task", required=True, help="the contributor's own words")
    ap.add_argument("--role", dest="roles", action="append", default=[], help="a CRediT role; repeat for more")
    ap.add_argument("--counts-as", required=True, choices=contribute.COUNTS_AS)
    ap.add_argument("--artifact", dest="artifacts", action="append", default=[])
    ap.add_argument("--ai", default="", help="what an AI tool did, if anything")
    ap.add_argument("--confirmed", action="store_true", help="the contributor has read the entry; without this, nothing is written")
    a = ap.parse_args(argv)
    paths = Paths()
    e = contribute.contribution(paths, a.person, a.task, a.roles, a.counts_as, a.artifacts, a.ai, a.confirmed)
    print(json.dumps(e, indent=1, ensure_ascii=False))
    print("written to paper/contributions.yaml" if a.confirmed else "NOT written: show it to the contributor, then rerun with --confirmed")
    return 0


def log_verification(argv):
    ap = argparse.ArgumentParser(prog="run.py log-verification")
    ap.add_argument("--as", dest="person", required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--type", dest="item_type", required=True, choices=contribute.ITEM_TYPES)
    ap.add_argument("--against", required=True)
    ap.add_argument("--outcome", required=True, choices=contribute.OUTCOMES)
    ap.add_argument("--change")
    ap.add_argument("--notes", default="")
    ap.add_argument("--confirmed", action="store_true", help="the checker has read the entry; without this, nothing is written")
    a = ap.parse_args(argv)
    e = contribute.verification(Paths(), a.person, a.item, a.item_type, a.against, a.outcome, a.change, a.notes, a.confirmed)
    print(json.dumps(e, indent=1, ensure_ascii=False))
    print("written to paper/verification_log.yaml" if a.confirmed else "NOT written: show it to the checker, then rerun with --confirmed")
    return 0


COMMANDS = {"check-registry": check_registry, "branch": branch, "log-event": log_event, "status": status,
            "points": points, "key-results": key_results, "own": own, "new-proposal": new_proposal, "propose": propose, "new-branch": new_branch,
            "new-interpretation": new_interpretation, "log-contribution": log_contribution,
            "log-verification": log_verification}


def main(cmd, argv):
    try:
        return COMMANDS[cmd](argv)
    except (contribute.ContributeError, logs.LogError, ValueError, FileNotFoundError) as e:
        print(f"refused: {e}", file=sys.stderr)
        return 3
