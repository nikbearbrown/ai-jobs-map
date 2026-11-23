"""The decision-point registry (paper/multiverse/decision_points.yaml): loading, indexing, and the checks behind
`pipeline/run.py check-registry`."""
import re

from .common import PROTECTED_PREFIXES, get_dotted, has_dotted, load_yaml

ID_RE = re.compile(r"^DP-\d{2}$")
FORMS = ("value", "list", "switch")
ENUMS = {
    "default_status": ("settled", "provisional"),
    "kind": ("config", "mixed", "hard-coded", "dead-key", "not-implemented"),
    "feeds_study": ("sampling-frame", "packet-content", "label-space", "baseline-b", "ai-share-strata", "indirect", "none"),
    "branchable": ("now", "not-built", "locked"),
    "status": ("open", "owned", "closed"),
}
STRING_FIELDS = ("id", "title", "description", "current_value", "default_status", "kind", "feeds_study", "branchable", "status")
OPTIONAL_STRING_FIELDS = ("rationale", "lock_reason", "owner")
LIST_FIELDS = ("location", "parameters", "precedent", "affects", "analyses")


def load(paths):
    return load_yaml(paths.registry) or []


def index(points):
    """{config key: (point, parameter)} for every parameter of every point."""
    out = {}
    for p in points:
        for prm in p.get("parameters") or []:
            out[prm["key"]] = (p, prm)
    return out


def same_type(base, new):
    """Same JSON type. Numbers may switch between int and float; booleans are never numbers."""
    if isinstance(base, bool) or isinstance(new, bool):
        return isinstance(base, bool) and isinstance(new, bool)
    if isinstance(base, (int, float)):
        return isinstance(new, (int, float))
    if isinstance(base, list):
        return isinstance(new, list) and (not base or all(same_type(base[0], x) for x in new))
    if isinstance(base, dict):
        if not isinstance(new, dict):
            return False
        vals = list(base.values())
        if vals and all(same_type(vals[0], v) for v in vals):        # a map such as word -> alias: any keys
            return all(same_type(vals[0], v) for v in new.values())
        return set(new) == set(base) and all(same_type(base[k], new[k]) for k in base)   # a structured setting
    if base is None:
        return new is None
    return type(base) is type(new)


def check_value(prm, base, value):
    """Errors for setting parameter prm (whose current value is base) to value. Empty list = allowed."""
    key = prm["key"]
    if not same_type(base, value):
        return [f"{key}: {value!r} changes the type (the default is {type(base).__name__})"]
    errs = []
    if prm["form"] == "switch" and value not in prm.get("variants", []):
        errs.append(f"{key}: variant {value!r} is not implemented (implemented: {prm.get('variants')}). "
                    "A new variant is a code change, reviewed with its proposal")
    if prm["form"] == "list" and not isinstance(value, list):
        errs.append(f"{key}: must be a list")
    if "allowed" in prm and isinstance(value, list):
        bad = [x for x in value if x not in prm["allowed"]]
        if bad:
            errs.append(f"{key}: {bad} not among the allowed values {prm['allowed']}")
    if "must_include" in prm and isinstance(value, list):
        miss = [x for x in prm["must_include"] if x not in value]
        if miss:
            errs.append(f"{key}: must include {miss}")
    if "minimum" in prm and isinstance(value, (int, float)) and not isinstance(value, bool) and value < prm["minimum"]:
        errs.append(f"{key}: {value} is below the minimum {prm['minimum']}")
    return errs


def check(points, cfg):
    """All registry problems, as readable strings. Empty list = the registry and config agree."""
    errs = []
    seen_ids, seen_keys = set(), {}
    for n, p in enumerate(points):
        pid = p.get("id", f"entry {n + 1}")
        if not isinstance(pid, str) or not ID_RE.match(pid):
            errs.append(f"{pid}: id must look like DP-01")
        if pid in seen_ids:
            errs.append(f"{pid}: duplicate id")
        seen_ids.add(pid)
        for f in STRING_FIELDS:
            if not isinstance(p.get(f), str):
                errs.append(f"{pid}: {f} must be a string, got {p.get(f)!r} (YAML reads yes, no, on, off as booleans: quote them)")
        for f in OPTIONAL_STRING_FIELDS:
            if p.get(f) is not None and not isinstance(p.get(f), str):
                errs.append(f"{pid}: {f} must be a string or null, got {p.get(f)!r}")
        for f in LIST_FIELDS:
            if not isinstance(p.get(f), list):
                errs.append(f"{pid}: {f} must be a list")
        for f, allowed in ENUMS.items():
            if isinstance(p.get(f), str) and p[f] not in allowed:
                errs.append(f"{pid}: {f} {p[f]!r} not in {allowed}")
        if not isinstance(p.get("locked"), bool):
            errs.append(f"{pid}: locked must be true or false")
        elif p["locked"] != (p.get("branchable") == "locked"):
            errs.append(f"{pid}: locked and branchable disagree")
        elif p["locked"] and not p.get("lock_reason"):
            errs.append(f"{pid}: a locked point needs a lock_reason")
        params = p.get("parameters") if isinstance(p.get("parameters"), list) else []
        if p.get("branchable") == "now" and not params:
            errs.append(f"{pid}: branchable now but has no parameters")
        for prm in params:
            key = prm.get("key")
            if not isinstance(key, str):
                errs.append(f"{pid}: parameter without a key")
                continue
            if key in seen_keys:
                errs.append(f"{pid}: {key} also belongs to {seen_keys[key]} (each key belongs to one point)")
            seen_keys[key] = pid
            if key.split(".")[0] in PROTECTED_PREFIXES:
                errs.append(f"{pid}: {key} is a protected key and can't be a parameter")
            if prm.get("form") not in FORMS:
                errs.append(f"{pid}: {key} form must be one of {FORMS}")
            if prm.get("origin") not in ("existing", "new-in-phase-2", "wired-in-phase-2"):
                errs.append(f"{pid}: {key} origin is missing or unknown")
            if not has_dotted(cfg, key):
                errs.append(f"{pid}: {key} is not in the config")
                continue
            base = get_dotted(cfg, key)
            if prm.get("form") == "switch":
                if not prm.get("variants"):
                    errs.append(f"{pid}: switch {key} lists no variants")
                elif base not in prm["variants"]:
                    errs.append(f"{pid}: the config value of {key} ({base!r}) is not one of its variants")
            if prm.get("form") == "list" and not isinstance(base, list):
                errs.append(f"{pid}: {key} is a list parameter but the config value isn't a list")
            errs += [f"{pid}: the default fails its own rule: {e}" for e in check_value(prm, base, base)]
    return errs
