"""Branch override files (paper/multiverse/branches/BR-nnnn.yaml) and the rules that refuse a bad override."""
import os
import re

from .common import PROTECTED_PREFIXES, get_dotted, has_dotted, load_yaml
from .registry import check_value, index

BRANCH_RE = re.compile(r"^BR-\d{4}$")
PROPOSAL_RE = re.compile(r"^P-\d{4}$")
DEFAULT_BRANCH = "BR-0000"


def load_branch(paths, branch_id):
    if not isinstance(branch_id, str) or not BRANCH_RE.match(branch_id):
        raise ValueError(f"{branch_id!r} is not a branch id (BR-0001, BR-0002, ...)")
    path = os.path.join(paths.branches, branch_id + ".yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no override file {paths.rel(path)}")
    b = load_yaml(path) or {}
    if b.get("branch_id") != branch_id:
        raise ValueError(f"{paths.rel(path)} says branch_id {b.get('branch_id')!r}")
    return b


def validate(branch, points, cfg):
    """Every reason to refuse this override, as readable strings. Empty list = the override may run."""
    bid = branch.get("branch_id")
    ov = branch.get("overrides")
    if not isinstance(ov, dict):
        return [f"{bid}: overrides must be a mapping of config key to value"]
    if bid == DEFAULT_BRANCH:
        if ov or branch.get("proposal_id") or branch.get("decision_point"):
            return [f"{bid} is the default: no overrides, proposal or decision point"]
        return []
    errs = []
    if not ov:
        errs.append(f"{bid}: no overrides (only {DEFAULT_BRANCH} is the default)")
    if not isinstance(branch.get("proposal_id"), str) or not PROPOSAL_RE.match(branch["proposal_id"]):
        errs.append(f"{bid}: proposal_id must look like P-0001")
    dp = branch.get("decision_point")
    idx = index(points)
    by_id = {p["id"]: p for p in points}
    if dp not in by_id:
        errs.append(f"{bid}: decision_point {dp!r} is not in the registry")
    touched = set()
    for key, value in ov.items():
        if key.split(".")[0] in PROTECTED_PREFIXES or key.endswith("output_dir"):
            errs.append(f"{key}: protected (inputs, output_dir, data_version, method_versions and multiverse can't be overridden)")
            continue
        if key not in idx:
            if has_dotted(cfg, key):
                errs.append(f"{key}: in the config but not a parameter of any decision point")
            else:
                errs.append(f"{key}: not in the base config")
            continue
        point, prm = idx[key]
        touched.add(point["id"])
        if point.get("locked"):
            errs.append(f"{key}: belongs to locked {point['id']} ({point.get('lock_reason')})")
            continue
        if point.get("branchable") != "now":
            errs.append(f"{key}: {point['id']} is {point.get('branchable')}; there is nothing to run")
            continue
        errs += check_value(prm, get_dotted(cfg, key), value)
    if len(touched) > 1:
        errs.append(f"{bid}: the overrides span {sorted(touched)}; a combination needs a proposal of its own")
    elif touched and dp in by_id and touched != {dp}:
        errs.append(f"{bid}: the overrides belong to {sorted(touched)[0]}, but the branch names {dp}")
    return errs
