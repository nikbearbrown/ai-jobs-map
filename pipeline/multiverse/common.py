"""Paths, YAML loading, canonical JSON and dotted config keys for the multiverse tools.

PyYAML is used here and only here (decision 3, Phase 1): the jobs map build itself stays standard library only."""
import copy
import hashlib
import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

# Reserved for the confirmatory firm-classifier study. Branch runs may never read these; the config's
# multiverse.locked_paths can add to this list, never remove from it.
LOCKED_PATHS_FLOOR = ("data/firm-classifier/", "paper/prereg/")

# Config keys no branch may touch, whatever the registry says.
PROTECTED_PREFIXES = ("inputs", "data_version", "method_versions", "config_version", "multiverse")


class Paths:
    """Every file the multiverse tools read or write, relative to one repo root (tests use a temporary root)."""

    def __init__(self, root=ROOT, config=None):
        self.root = os.path.abspath(root)
        self.paper = os.path.join(self.root, "paper")
        self.mv = os.path.join(self.paper, "multiverse")
        self.registry = os.path.join(self.mv, "decision_points.yaml")
        self.decision_log = os.path.join(self.mv, "decision_log.yaml")
        self.key_results = os.path.join(self.mv, "key_results.yaml")
        self.branches = os.path.join(self.mv, "branches")
        self.proposals = os.path.join(self.mv, "proposals")
        self.runs = os.path.join(self.mv, "runs")
        self.roster = os.path.join(self.paper, "roster.yaml")
        self.config = config or os.path.join(self.root, "pipeline", "ai_jobs_map", "config", "config.json")

    def rel(self, path):
        return os.path.relpath(path, self.root)


def load_yaml(path):
    import yaml
    with open(path) as fh:
        return yaml.safe_load(fh)


def dump_yaml(obj):
    import yaml
    return yaml.safe_dump(obj, sort_keys=False, allow_unicode=True, default_flow_style=False, width=110)


def load_json(path):
    with open(path) as fh:
        return json.load(fh)


def canonical_json(obj):
    """Sorted keys, no spaces: the same config always gives the same bytes, however the file is laid out."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_sha256(obj):
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()


def has_dotted(cfg, key):
    node = cfg
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return False
        node = node[part]
    return True


def get_dotted(cfg, key):
    node = cfg
    for part in key.split("."):
        node = node[part]
    return node


def with_overrides(cfg, overrides):
    """A deep copy of cfg with each dotted key set. The base config is never changed."""
    out = copy.deepcopy(cfg)
    for key, value in overrides.items():
        parts = key.split(".")
        node = out
        for part in parts[:-1]:
            node = node[part]
        node[parts[-1]] = copy.deepcopy(value)
    return out


def under(path, roots):
    """True if path (after resolving symlinks) is one of roots or inside one."""
    p = os.path.realpath(path)
    for r in roots:
        r = os.path.realpath(r)
        if p == r or p.startswith(r.rstrip(os.sep) + os.sep):
            return True
    return False
