"""The roster (paper/roster.yaml) and the append-only decision log (paper/multiverse/decision_log.yaml)."""
import datetime as dt
import glob
import json
import os
import re

from .common import dump_yaml, load_yaml
from .registry import load as load_registry

STATUSES = ("proposed", "accepted", "rejected", "run", "adopted")
DECISIONS = ("proposed", "accepted", "rejected", "adopted")
LEAD_DECIDES = ("accepted", "rejected", "adopted")
EVENT_FIELDS = ("event_id", "proposal_id", "decision_point", "alternative", "proposer", "status", "reason",
                "decided_by", "date", "results_seen", "results_link", "corrects", "sections_sha256")


class LogError(ValueError):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


# ---------------------------------------------------------------- roster

def load_roster(paths):
    if not os.path.exists(paths.roster):
        return []
    return load_yaml(paths.roster) or []


def lead_author(roster):
    leads = [r["name"] for r in roster if r.get("role") == "lead-author"]
    return leads[0] if len(leads) == 1 else None


def cleared(roster, name):
    """(True, why) if the roster lets this person see results; else (False, why). Anyone not listed is treated as
    a rater whose ratings are incomplete."""
    for r in roster:
        if r.get("name") == name:
            if r.get("rater") is True and r.get("ratings_complete") is not True:
                return False, f"{name} is a rater whose ratings are not marked complete in paper/roster.yaml"
            if r.get("rater") not in (True, False):
                return False, f"{name}'s roster entry doesn't say whether they rate"
            return True, f"{name} is cleared ({r.get('role')}, {'rater with complete ratings' if r.get('rater') else 'not a rater'})"
    return False, f"{name!r} is not in paper/roster.yaml, so is treated as a rater whose ratings are incomplete"


# ---------------------------------------------------------------- decision log

def load_events(paths):
    if not os.path.exists(paths.decision_log):
        return []
    return load_yaml(paths.decision_log) or []


def effective(events):
    """Events still in force: an event named in a later event's `corrects` is set aside."""
    corrected = {e.get("corrects") for e in events if e.get("corrects")}
    return [e for e in events if e.get("event_id") not in corrected]


def latest_decision(events, proposal_id):
    ds = [e for e in effective(events) if e.get("proposal_id") == proposal_id and e.get("status") in DECISIONS]
    return ds[-1] if ds else None


def first_event(events, proposal_id, status):
    for e in effective(events):
        if e.get("proposal_id") == proposal_id and e.get("status") == status:
            return e
    return None


def run_finish_times(paths, events, proposal_id):
    """When each run of this proposal finished: from `run` events and from the local run records."""
    times = [parse_iso(e["date"]) for e in events if e.get("proposal_id") == proposal_id and e.get("status") == "run"]
    for prov in glob.glob(os.path.join(paths.runs, "BR-*", "*", "provenance.json")):
        try:
            with open(prov) as fh:
                p = json.load(fh)
        except (OSError, ValueError):
            continue
        if p.get("proposal_id") == proposal_id and p.get("finished_at"):
            times.append(parse_iso(p["finished_at"]))
    return times


def check_log(events):
    """Problems that make the log ambiguous, e.g. after two checkouts' logs are merged by hand. The runner refuses
    to run while there are any."""
    probs, seen, proposed = [], set(), {}
    by_id = {e.get("event_id"): e for e in events}
    for e in events:
        if e.get("event_id") in seen:
            probs.append(f"event id {e.get('event_id')} appears more than once")
        seen.add(e.get("event_id"))
        if e.get("status") == "proposed":
            proposed.setdefault(e.get("proposal_id"), []).append(e.get("event_id"))
        c = e.get("corrects")
        if c and (c not in by_id or by_id[c].get("status") == "run"):
            probs.append(f"{e.get('event_id')} corrects {c}, which is missing or is a run")
    probs += [f"{pid} was proposed more than once ({', '.join(ids)})" for pid, ids in proposed.items() if len(ids) > 1]
    return probs


def next_event_id(events):
    nums = [int(m.group(1)) for e in events if (m := re.match(r"^E-(\d{4})$", str(e.get("event_id", ""))))]
    return f"E-{(max(nums) + 1 if nums else 1):04d}"


def append_event(paths, event, now=None):
    """Check and append one event. Returns the event as written. results_seen is computed from the run records,
    whatever the caller passed: `after` if any run of this proposal finished before now."""
    now = now or utc_now()
    events = load_events(paths)
    roster = load_roster(paths)
    e = {k: event.get(k) for k in EVENT_FIELDS}
    st = e["status"]
    if st not in STATUSES:
        raise LogError(f"status must be one of {STATUSES}")
    if not re.match(r"^P-\d{4}$", str(e["proposal_id"] or "")):
        raise LogError("proposal_id must look like P-0001")
    if not re.match(r"^DP-\d{2}$", str(e["decision_point"] or "")):
        raise LogError("decision_point must look like DP-18")
    if st in LEAD_DECIDES:
        lead = lead_author(roster)
        if not lead:
            raise LogError("paper/roster.yaml must name exactly one lead author")
        if e["decided_by"] != lead:
            raise LogError(f"only the lead author ({lead}) decides {st} events")
        if not (e["reason"] or "").strip():
            raise LogError(f"a {st} event needs the lead author's reason")
    if os.path.exists(paths.registry):
        point = next((p for p in load_registry(paths) if p.get("id") == e["decision_point"]), None)
        if point is None:
            raise LogError(f"{e['decision_point']} is not in the registry")
        if point.get("locked"):
            raise LogError(f"{e['decision_point']} is locked ({point.get('lock_reason')}); nothing about it goes in this log")
    if e["corrects"]:
        corrected = next((x for x in events if x.get("event_id") == e["corrects"]), None)
        if st not in LEAD_DECIDES:
            raise LogError("only the lead author's accepted, rejected or adopted events can correct an earlier event")
        if corrected is not None and corrected.get("status") == "run":
            raise LogError(f"{e['corrects']} is a run; runs are never set aside (every run goes in the supplement)")
        if corrected is not None and corrected.get("proposal_id") != e["proposal_id"]:
            raise LogError(f"{e['corrects']} is about {corrected.get('proposal_id')}, not {e['proposal_id']}")
    if st == "proposed":
        if not (e["proposer"] or "").strip() or not (e["alternative"] or "").strip():
            raise LogError("a proposed event needs the proposer and the alternative")
        if first_event(events, e["proposal_id"], "proposed"):
            raise LogError(f"{e['proposal_id']} is already proposed; a changed proposal is a new proposal")
        e["decided_by"] = e["proposer"]
    else:
        e["sections_sha256"] = None
    if st == "run":
        e["decided_by"] = "runner"
        if not e["results_link"]:
            raise LogError("a run event needs results_link (the run folder)")
    if st in ("accepted", "rejected", "adopted", "run"):
        prior = first_event(events, e["proposal_id"], "proposed")
        if prior is None:
            raise LogError(f"{e['proposal_id']} has no proposed event")
        e["alternative"] = e["alternative"] or prior.get("alternative")
        e["proposer"] = e["proposer"] or prior.get("proposer")
        if prior.get("decision_point") != e["decision_point"]:
            raise LogError(f"{e['proposal_id']} was proposed for {prior.get('decision_point')}, not {e['decision_point']}")
    if e["corrects"] and e["corrects"] not in {x.get("event_id") for x in events}:
        raise LogError(f"corrects {e['corrects']}, which is not in the log")
    e["event_id"] = next_event_id(events)
    e["date"] = iso(now)
    if st == "run":
        e["results_seen"] = None
    else:
        e["results_seen"] = "after" if any(t <= now for t in run_finish_times(paths, events, e["proposal_id"])) else "before"
    text = dump_yaml([e])
    ends_with_newline = True
    if os.path.exists(paths.decision_log) and os.path.getsize(paths.decision_log):
        with open(paths.decision_log, "rb") as fh:
            fh.seek(-1, os.SEEK_END)
            ends_with_newline = fh.read(1) == b"\n"
    with open(paths.decision_log, "a") as fh:   # append only: earlier bytes are never rewritten
        fh.write(("" if ends_with_newline else "\n") + "\n" + text)
    return e
