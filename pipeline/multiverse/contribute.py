"""The commands the /contribute skill calls (.claude/skills/contribute/SKILL.md). Each one checks the paper's rules
itself, so a session can't skip a rule by accident.

    status --as NAME                      the roster gate, and this person's points, proposals and branches
    points [--all]                        open, unlocked decision points
    key-results                           the key results' ids, titles and flip rules, without their values
    own DP-nn --as NAME [--release]       mark a point owned, or give it back
    new-proposal DP-nn --as NAME          a proposal file from the template: header filled, contributor sections empty
    propose P-nnnn                        check the contributor's sections are written, then log it as proposed
    new-branch P-nnnn --set KEY=VALUE     after the lead author accepts it: the override file
    new-interpretation BR-nnnn --as NAME  after a run: an interpretation file holding the prediction and key results
    log-contribution ... [--confirmed]    one contribution-log entry, written only once the contributor confirms it
    log-verification ... [--confirmed]    one verification-log entry, written only once the checker confirms it

None of these writes a contributor's words. Rationales, predictions, interpretations and task descriptions come in
as the contributor typed them, in their own files or as arguments, and are saved unchanged."""
import datetime as dt
import glob
import json
import os
import re

from . import keyresults, logs, overrides, provenance, registry
from .common import dump_yaml, load_json, load_yaml

CREDIT_ROLES = ("Conceptualization", "Data curation", "Formal analysis", "Funding acquisition", "Investigation",
                "Methodology", "Project administration", "Resources", "Software", "Supervision", "Validation",
                "Visualization", "Writing - original draft", "Writing - review & editing")
COUNTS_AS = ("component", "writing", "acknowledgment", "none")
ITEM_TYPES = ("claim", "figure", "table", "number")
OUTCOMES = ("match", "mismatch", "could-not-check")

PROPOSAL_SECTIONS = ("Alternative", "Rationale (contributor's own words, with precedent if any)",
                     "What we'd expect to see if the finding is fragile")
PREDICTION = "What we'd expect to see if the finding is fragile"
INTERPRETATION_SECTIONS = ("What changed", "Robust or fragile, against your prediction", "What it means for the claim")

FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


class ContributeError(ValueError):
    """The command refuses; the message says why and what to do instead."""


def today(now=None):
    return (now or logs.utc_now()).date().isoformat()


YAML_WORDS = {"y", "n", "yes", "no", "on", "off", "true", "false", "null", "none"}


def scalar(v):
    """A value for one YAML line: plain words stay plain (owner: Example Contributor), anything else is JSON."""
    if isinstance(v, str) and re.fullmatch(r"[A-Za-z][A-Za-z0-9 .-]*[A-Za-z0-9]", v) and v.lower() not in YAML_WORDS:
        return v
    return json.dumps(v, ensure_ascii=False)


def next_id(prefix, existing):
    nums = [int(m.group(1)) for x in existing if (m := re.match(rf"^{prefix}-(\d{{4}})$", str(x)))]
    return f"{prefix}-{(max(nums) + 1 if nums else 1):04d}"


# ---------------------------------------------------------------- markdown files with a YAML header

def front(text):
    import yaml
    m = FRONT.match(text)
    if not m:
        raise ContributeError("the file has no --- header")
    return yaml.safe_load(m.group(1)) or {}, text[m.end():]


def set_header(text, key, value):
    """Replace one `key:` line in the header. JSON is valid YAML, so values are written as JSON."""
    m = FRONT.match(text)
    head, n = re.subn(rf"^{re.escape(key)}:.*$", lambda _: f"{key}: {scalar(value)}", m.group(1),
                      count=1, flags=re.M)
    if n != 1:
        raise ContributeError(f"the header has no {key} line")
    return "---\n" + head + "\n---\n" + text[m.end():]


def sections(body):
    out, cur = {}, None
    for line in body.splitlines(keepends=True):
        h = re.match(r"^## (.+?)\s*$", line)
        if h:
            cur = h.group(1)
            out[cur] = ""
        elif cur is not None:
            out[cur] += line
    return out


def written(s):
    """A section's text with the template's guidance comments taken out."""
    return re.sub(r"<!--.*?-->", "", s or "", flags=re.S).strip()


def set_section(text, heading, content):
    lines = text.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.rstrip("\n") == f"## {heading}"), None)
    if start is None:
        raise ContributeError(f"the file has no '## {heading}' section")
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    tail = "\n" if end < len(lines) else ""
    return "".join(lines[:start + 1]) + "\n" + content.strip() + "\n" + tail + "".join(lines[end:])


def sections_sha256(text):
    """The hash of a proposal's three contributor sections, as written. `propose` records it; the runner refuses a
    branch whose proposal no longer matches, so the prediction a branch is judged against is the one proposed."""
    import hashlib
    secs = sections(front(text)[1])
    blob = json.dumps({h: written(secs.get(h)) for h in PROPOSAL_SECTIONS}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def quote(text):
    return "\n".join("> " + ln if ln.strip() else ">" for ln in text.splitlines())


# ---------------------------------------------------------------- the append-only YAML logs

def append_entry(path, entry):
    """Append one entry to a YAML list file. Earlier bytes are kept, except the `[]` of an empty log."""
    import yaml
    text = open(path).read() if os.path.exists(path) else ""
    data = yaml.safe_load(text) if text.strip() else []
    if data is None:
        data = []
    if not isinstance(data, list):
        raise ContributeError(f"{path} is not a list")
    block = dump_yaml([entry])
    if not data and re.search(r"^\[\]\s*$", text, re.M):
        text = re.sub(r"^\[\]\s*\n?", "", text, count=1, flags=re.M)
        new = text + ("" if text.endswith("\n") or not text else "\n") + block
    else:
        new = text + ("" if text.endswith("\n") or not text else "\n") + ("\n" if text else "") + block
    check = yaml.safe_load(new)
    if not isinstance(check, list) or check[-1] != entry or check[:-1] != data:
        raise ContributeError(f"appending to {path} would change earlier entries")
    with open(path, "w") as fh:
        fh.write(new)
    return entry


def log_ids(path, field):
    data = load_yaml(path) if os.path.exists(path) else []
    return [e.get(field) for e in (data or [])]


# ---------------------------------------------------------------- registry

def point(paths, dp):
    for p in registry.load(paths):
        if p.get("id") == dp:
            return p
    raise ContributeError(f"{dp} is not in the registry")


def edit_point(paths, dp, fields):
    """Change top-level fields of one registry entry in place, leaving every other byte as it was."""
    text = open(paths.registry).read()
    m = re.search(rf"^- id: {re.escape(dp)}\n", text, re.M)
    if not m:
        raise ContributeError(f"{dp} is not in the registry")
    nxt = re.search(r"^- id: ", text[m.end():], re.M)
    end = m.end() + nxt.start() if nxt else len(text)
    block = text[m.start():end]
    for k, v in fields.items():
        block, n = re.subn(rf"^  {re.escape(k)}: .*$", lambda _: f"  {k}: {scalar(v)}", block,
                           count=1, flags=re.M)
        if n != 1:
            raise ContributeError(f"{dp} has no {k} line")
    with open(paths.registry, "w") as fh:
        fh.write(text[:m.start()] + block + text[end:])
    p = point(paths, dp)
    if any(p.get(k) != v for k, v in fields.items()):
        raise ContributeError(f"editing {dp} didn't take; check {paths.rel(paths.registry)}")
    return p


def points(paths, show_all=False):
    return [p for p in registry.load(paths)
            if show_all or (p.get("branchable") == "now" and p.get("status") == "open" and not p.get("locked"))]


def own(paths, dp, name, release=False):
    p = point(paths, dp)
    if p.get("locked"):
        raise ContributeError(f"{dp} is locked ({p.get('lock_reason')}); no branch may change it, so it can't be owned")
    if p.get("status") == "closed":
        raise ContributeError(f"{dp} is closed")
    lead = logs.lead_author(logs.load_roster(paths))
    if release:
        if not p.get("owner"):
            raise ContributeError(f"{dp} isn't owned")
        if name not in (p.get("owner"), lead):
            raise ContributeError(f"only {p.get('owner')} or the lead author can give {dp} back")
        return edit_point(paths, dp, {"owner": None, "status": "open"})
    if p.get("owner") == name:
        return p
    if p.get("owner"):
        raise ContributeError(f"{dp} is owned by {p.get('owner')}; the lead author can release it")
    return edit_point(paths, dp, {"owner": name, "status": "owned"})


# ---------------------------------------------------------------- the roster gate and a person's work

def status(paths, name):
    roster = logs.load_roster(paths)
    ok, why = logs.cleared(roster, name)
    entry = next((r for r in roster if r.get("name") == name), None)
    lead = logs.lead_author(roster)
    events = logs.load_events(paths)
    eff = logs.effective(events)
    pids = {e["proposal_id"] for e in eff if e.get("proposer") == name}
    drafts = set()
    for f in sorted(glob.glob(os.path.join(paths.proposals, "P-*.md"))):
        try:
            fm, _ = front(open(f).read())
        except ContributeError:
            continue
        if fm.get("proposer") == name:
            pids.add(fm.get("proposal_id"))
            drafts.add(fm.get("proposal_id"))
    branch_of = {}
    for f in glob.glob(os.path.join(paths.branches, "BR-*.yaml")):
        b = load_yaml(f) or {}
        if b.get("proposal_id"):
            branch_of[b["proposal_id"]] = b.get("branch_id")
    props = []
    for pid in sorted(pids):
        first = logs.first_event(events, pid, "proposed")
        dec = logs.latest_decision(events, pid)
        item = {"proposal_id": pid, "decision_point": (first or {}).get("decision_point"),
                "status": dec["status"] if dec else ("draft" if pid in drafts else "unknown")}
        if pid in branch_of:
            item["branch"] = branch_of[pid]
        if ok:     # reasons and run folders can carry results
            item["reason"] = dec.get("reason") if dec else None
            item["runs"] = [e["results_link"] for e in eff if e.get("proposal_id") == pid and e.get("status") == "run"]
        props.append(item)
    return {"name": name, "in_roster": entry is not None, "role": (entry or {}).get("role"),
            "is_lead_author": lead is not None and name == lead, "cleared_for_results": ok, "why": why,
            "owns": [p["id"] for p in registry.load(paths) if p.get("owner") == name], "proposals": props}


def check_lead_identity(paths, by, git_user):
    """Lead-author decisions are recorded from the lead author's own git identity on this machine."""
    lead = logs.lead_author(logs.load_roster(paths))
    if by != lead:
        raise ContributeError(f"only the lead author ({lead}) decides; {by!r} is not the lead author")
    if git_user != lead:
        raise ContributeError(f"this checkout's git user is {git_user!r}, not {lead}: the lead author records their own "
                              "decisions, from their own git identity")


# ---------------------------------------------------------------- proposals

def new_proposal(paths, dp, name, eliminate=False, seen_results=None, now=None):
    p = point(paths, dp)
    if p.get("locked"):
        raise ContributeError(f"{dp} is locked ({p.get('lock_reason')}); proposals can't change it")
    if p.get("status") == "closed":
        raise ContributeError(f"{dp} is closed")
    events = logs.load_events(paths)
    taken = [os.path.splitext(os.path.basename(f))[0] for f in glob.glob(os.path.join(paths.proposals, "P-*.md"))]
    pid = next_id("P", taken + [e.get("proposal_id") for e in events])
    ran = [e for e in logs.effective(events) if e.get("decision_point") == dp and e.get("status") == "run"]
    if ran and seen_results is None:
        raise ContributeError(f"branches on {dp} have already run. Ask {name} whether they have seen any of those results, "
                              "and pass --seen-results yes or no")
    text = open(os.path.join(paths.templates, "proposal.md")).read()
    for k, v in (("proposal_id", pid), ("decision_point", dp), ("proposer", name), ("date_proposed", today(now)),
                 ("results_seen_before_proposing", bool(seen_results) if ran else False),
                 ("proposer_recommends", "eliminate" if eliminate else "run"),
                 ("ai_assistance", "Claude Code (/contribute) made this file from the template and copied the decision "
                                   "point and current choice from the registry")):
        text = set_header(text, k, v)
    keys = ", ".join(f"`{prm['key']}`" for prm in p.get("parameters") or [])
    code = [loc for loc in p.get("location") or [] if not str(loc).startswith("config:")]
    provisional = (" This default is provisional: an open lead-author decision, and the comparison point until it is "
                   "decided." if p.get("default_status") == "provisional" else "")
    text = set_section(text, "Decision point", f"**{p['id']}: {p['title']}.** {p['description']}")
    text = set_section(text, "Current choice", f"**Now:** {p['current_value'].rstrip('.')}.{provisional}\n\n"
                                               f"Config keys a branch can set: {keys}."
                                               + (f" Code: {'; '.join(code)}." if code else ""))
    os.makedirs(paths.proposals, exist_ok=True)
    path = os.path.join(paths.proposals, pid + ".md")
    with open(path, "x") as fh:
        fh.write(text)
    return pid, path


def propose(paths, pid, ai=None, now=None):
    if not overrides.PROPOSAL_RE.match(pid or ""):
        raise ContributeError(f"{pid!r} is not a proposal id (P-0001, ...)")
    path = os.path.join(paths.proposals, pid + ".md")
    if not os.path.exists(path):
        raise ContributeError(f"no proposal file {paths.rel(path)}")
    text = open(path).read()
    fm, body = front(text)
    if fm.get("proposal_id") != pid:
        raise ContributeError(f"{paths.rel(path)} says proposal_id {fm.get('proposal_id')!r}")
    dp, proposer = fm.get("decision_point"), (fm.get("proposer") or "").strip()
    p = point(paths, dp)
    if p.get("locked"):
        raise ContributeError(f"{dp} is locked ({p.get('lock_reason')})")
    if not proposer:
        raise ContributeError(f"{pid} has no proposer")
    secs = sections(body)
    missing = [h for h in PROPOSAL_SECTIONS if not written(secs.get(h))]
    if missing:
        raise ContributeError(f"{pid} isn't ready: the contributor hasn't written {'; '.join(missing)}")
    events = logs.load_events(paths)
    if logs.first_event(events, pid, "proposed"):
        raise ContributeError(f"{pid} is already in the decision log as proposed")
    alternative = written(secs["Alternative"]).splitlines()[0].strip()
    if ai:
        text = set_header(text, "ai_assistance", ai)
        with open(path, "w") as fh:
            fh.write(text)
    return logs.append_event(paths, {"proposal_id": pid, "decision_point": dp, "status": "proposed",
                                     "proposer": proposer, "alternative": alternative,
                                     "sections_sha256": sections_sha256(text)}, now=now)


# ---------------------------------------------------------------- branches and interpretations

def parse_set(s):
    if "=" not in s:
        raise ContributeError(f"{s!r}: use KEY=VALUE, e.g. skills.min_support_firms=5")
    k, v = s.split("=", 1)
    try:
        return k.strip(), json.loads(v)
    except ValueError:
        return k.strip(), v      # a bare word such as off is a string


def new_branch(paths, pid, sets):
    events = logs.load_events(paths)
    lead = logs.lead_author(logs.load_roster(paths))
    dec = logs.latest_decision(events, pid)
    if not dec or dec.get("status") not in ("accepted", "adopted") or dec.get("decided_by") != lead:
        raise ContributeError(f"{pid} is {dec.get('status') if dec else 'not in the decision log'}; a branch is written "
                              "only after the lead author accepts the proposal")
    path = os.path.join(paths.proposals, pid + ".md")
    if not os.path.exists(path):
        raise ContributeError(f"no proposal file {paths.rel(path)}")
    text = open(path).read()
    fm, _ = front(text)
    dp = fm.get("decision_point")
    if dec.get("decision_point") != dp:
        raise ContributeError(f"{pid} was accepted for {dec.get('decision_point')}, but its file says {dp}")
    existing = {}
    for f in glob.glob(os.path.join(paths.branches, "BR-*.yaml")):
        b = load_yaml(f) or {}
        existing[os.path.splitext(os.path.basename(f))[0]] = b.get("proposal_id")
    for bid, p in existing.items():
        if p == pid:
            raise ContributeError(f"{pid} already has {bid}")
    ov = dict(parse_set(s) for s in sets)
    if not ov:
        raise ContributeError("give the override with --set KEY=VALUE")
    bid = next_id("BR", existing)
    branch = {"branch_id": bid, "proposal_id": pid, "decision_point": dp, "overrides": ov}
    errs = overrides.validate(branch, registry.load(paths), load_json(paths.config))
    if errs:
        raise ContributeError("; ".join(errs))
    with open(os.path.join(paths.branches, bid + ".yaml"), "x") as fh:
        fh.write(f"# {pid} on {dp}, accepted by the lead author ({dec['event_id']}). Written by run.py new-branch.\n"
                 + dump_yaml(branch))
    with open(path, "w") as fh:
        fh.write(set_header(text, "override", ov))
    return branch


def override_checks(paths, branch):
    """Values in the override that don't appear in the proposal's Alternative section, for a person to check
    against what the lead author accepted. Advice, not a refusal: the wording may say "five" for 5."""
    alt = written(sections(front(open(os.path.join(paths.proposals, branch["proposal_id"] + ".md")).read())[1]).get("Alternative"))
    out = []
    for k, v in branch["overrides"].items():
        vals = v if isinstance(v, list) else [v]
        missing = [x for x in vals if not isinstance(x, (dict, list)) and str(x).lower() not in alt.lower()]
        if missing:
            out.append(f"{k}: {', '.join(map(str, missing))} isn't in {branch['proposal_id']}'s Alternative; check it matches "
                       "what the lead author accepted")
    return out


def latest_run(paths, bid):
    runs = []
    for f in glob.glob(os.path.join(paths.runs, bid, "*", "provenance.json")):
        prov = load_json(f)
        if prov.get("status") == "ok":
            runs.append((prov["finished_at"], os.path.dirname(f), prov))
    return max(runs) if runs else None


def new_interpretation(paths, bid, name, now=None):
    ok, why = logs.cleared(logs.load_roster(paths), name)
    if not ok:
        raise ContributeError(f"{why}. An interpretation shows the branch's results, so it waits until the roster clears {name}")
    if bid == overrides.DEFAULT_BRANCH:
        raise ContributeError("BR-0000 is the default; interpret a branch that changes something")
    branch = overrides.load_branch(paths, bid)
    run = latest_run(paths, bid)
    if run is None:
        raise ContributeError(f"{bid} hasn't run yet (python3 -I pipeline/run.py branch {bid})")
    out = os.path.join(paths.interpretations, bid + ".md")
    if os.path.exists(out):
        raise ContributeError(f"{paths.rel(out)} already exists")
    _, run_dir, prov = run
    pid = branch["proposal_id"]
    rel_prop = paths.rel(os.path.join(paths.proposals, pid + ".md"))
    at_run = provenance.git(paths.root, "show", f"{prov['code_commit']}:{rel_prop}")
    prediction = written(sections(front(at_run)[1]).get(PREDICTION))
    text = open(os.path.join(paths.templates, "interpretation.md")).read()
    for k, v in (("branch_id", bid), ("proposal_id", pid), ("decision_point", branch["decision_point"]), ("author", name),
                 ("date_started", today(now)), ("run_folder", paths.rel(run_dir)), ("code_commit", prov["code_commit"]),
                 ("compared_with", prov.get("compared_with") or ""),
                 ("ai_assistance", "Claude Code (/contribute) made this file and filled in the override, the prediction "
                                   "and the key results")):
        text = set_header(text, k, v)
    text = set_section(text, "What the branch changed",
                       "\n".join(f"- `{k}`: `{json.dumps(v, ensure_ascii=False)}`" for k, v in branch["overrides"].items()))
    text = set_section(text, "Your prediction, written before the run",
                       quote(prediction) + f"\n\nFrom {rel_prop} at commit {prov['code_commit'][:7]}, the version the branch ran with.")
    diff = load_json(os.path.join(run_dir, "diff_vs_default.json"))
    text = set_section(text, "Key results against the default",
                       "```\n" + keyresults.table(diff) + "\n```\n\nThe full comparison is in "
                       f"{paths.rel(run_dir)}/diff_vs_default.json, on the machine that ran it.")
    os.makedirs(paths.interpretations, exist_ok=True)
    with open(out, "x") as fh:
        fh.write(text)
    return out


# ---------------------------------------------------------------- contribution and verification entries

def credit_roles(roles):
    out = []
    for r in roles:
        r = r.replace("–", "-").replace("—", "-").strip()
        if r not in CREDIT_ROLES:
            raise ContributeError(f"{r!r} is not a CRediT role. The 14 are: {', '.join(CREDIT_ROLES)}")
        out.append(r)
    if not out:
        raise ContributeError("give at least one CRediT role")
    return out


def contribution(paths, name, task, roles, counts_as, artifacts, ai, confirmed, now=None):
    if not (task or "").strip():
        raise ContributeError("the task is the contributor's own description of what they did; it can't be empty")
    if counts_as not in COUNTS_AS:
        raise ContributeError(f"counts_as must be one of {', '.join(COUNTS_AS)}")
    entry = {"entry_id": next_id("C", log_ids(paths.contributions, "entry_id")), "contributor": name, "date": today(now),
             "task": task.strip(), "credit_roles": credit_roles(roles) if roles or counts_as != "none" else [],
             "counts_as": counts_as, "artifacts": list(artifacts), "ai_assistance": ai or "",
             "confirmed_by_contributor": bool(confirmed)}
    return append_entry(paths.contributions, entry) if confirmed else entry


def verification(paths, name, item, item_type, against, outcome, change, notes, confirmed, now=None):
    if item_type not in ITEM_TYPES:
        raise ContributeError(f"item_type must be one of {', '.join(ITEM_TYPES)}")
    if outcome not in OUTCOMES:
        raise ContributeError(f"outcome must be one of {', '.join(OUTCOMES)}")
    ok, why = logs.cleared(logs.load_roster(paths), name)
    if not ok:
        raise ContributeError(f"{why}. The verification log checks numbers, claims and figures against outputs, which "
                              "carry results; record a data check in the contribution log instead")
    if not (item or "").strip() or not (against or "").strip():
        raise ContributeError("say what was checked and what it was checked against")
    entry = {"check_id": next_id("V", log_ids(paths.verification_log, "check_id")), "checker": name, "date": today(now),
             "item": item.strip(), "item_type": item_type, "checked_against": against.strip(), "outcome": outcome,
             "change_made": change or None, "notes": notes or "", "confirmed_by_checker": bool(confirmed)}
    return append_entry(paths.verification_log, entry) if confirmed else entry
