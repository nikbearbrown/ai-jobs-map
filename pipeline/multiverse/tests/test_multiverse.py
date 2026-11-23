"""Tests for the multiverse tools: registry, overrides, guard, logs, provenance, gates and the runner.

Runner tests use a temporary git repo, a small fixture config and registry, and a stand-in build, so they run in
seconds anywhere. The real-data test that BR-0000 reproduces the main build is in test_reproduce.py."""
import ast
import copy
import gzip
import json
import os
import shutil
import subprocess
import tempfile
import unittest

from pipeline.multiverse import keyresults, logs, overrides, registry
from pipeline.multiverse.common import ROOT, Paths, canonical_sha256, dump_yaml, load_json, load_yaml, with_overrides
from pipeline.multiverse.guard import Guard, GuardViolation
from pipeline.multiverse.runner import PROVENANCE_FIELDS, Refused, run_branch

REAL = Paths()
LEAD = "Nik Bear Brown"

FIX_CFG = {
    "config_version": "t", "data_version": "t", "method_versions": {"x": "x-v1"},
    "inputs": {"input_file": None, "output_dir": "data/out"},
    "multiverse": {"locked_paths": ["secret/"]},
    "skills": {"min_support_firms": 3, "max_ngram": 3, "stoplist": ["a", "the"]},
    "tier": {"cutoff": 200},
    "agg": {"omega": "mean", "flag": True},
    "notes": {"text": "not a parameter"},
    "unbuilt": {"window": 24},
}


def point(pid, params, branchable="now", locked=False):
    return {"id": pid, "title": pid, "description": "d", "current_value": "c", "default_status": "settled", "kind": "config",
            "location": ["config"], "parameters": params, "rationale": None, "precedent": [], "affects": [], "analyses": [],
            "feeds_study": "none", "locked": locked, "lock_reason": "study" if locked else None, "branchable": branchable,
            "owner": None, "status": "open"}


FIX_POINTS = [
    point("DP-01", [{"key": "skills.min_support_firms", "form": "value", "minimum": 1, "origin": "existing"}]),
    point("DP-02", [{"key": "skills.max_ngram", "form": "value", "origin": "existing"},
                    {"key": "skills.stoplist", "form": "list", "origin": "new-in-phase-2"}]),
    point("DP-03", [{"key": "tier.cutoff", "form": "value", "origin": "existing"}], branchable="locked", locked=True),
    point("DP-04", [{"key": "agg.omega", "form": "switch", "variants": ["mean"], "origin": "new-in-phase-2"},
                    {"key": "agg.flag", "form": "switch", "variants": [True, False], "origin": "existing"}]),
    point("DP-05", [{"key": "unbuilt.window", "form": "value", "origin": "existing"}], branchable="not-built"),
]


def fake_eco(cfg):
    """A minimal ecosystem.json carrying everything the key results read; values move with the config."""
    k = cfg["skills"]["min_support_firms"]
    cols = ["it-services", "software-internet", "sector not measured"]
    firms = [{"firm_id": f"f{i}", "bucket": cols[i % 2], "ai_share": 0.5} for i in range(12)]
    cells = [[{"firms": 6 if k == 3 else 2, "roles": 1, "roles_excluding_largest_firm": 1}, {"firms": 4, "roles": 1, "roles_excluding_largest_firm": 1}, {"firms": 0, "roles": 0, "roles_excluding_largest_firm": 0}],
             [{"firms": 5, "roles": 1, "roles_excluding_largest_firm": 1}, {"firms": 5, "roles": 1, "roles_excluding_largest_firm": 1}, {"firms": 0, "roles": 0, "roles_excluding_largest_firm": 0}],
             [{"firms": 0, "roles": 0, "roles_excluding_largest_firm": 0}] * 3,
             [{"firms": 0, "roles": 0, "roles_excluding_largest_firm": 0}] * 3]
    return {
        "computed_at": "x",
        "step_counts": [
            {"step": "live: distinct roles -> SOC by title (exact, then trailing phrase)", "in": 100, "out": 36},
            {"step": "ai: text roles -> roles naming a seed skill (base rate)", "in": 100, "out": 17},
            {"step": f"ai: roles with omega -> AI-related (omega > 0.1)", "in": 100, "out": 95 if k == 3 else 40},
            {"step": f"tiers: firms -> Tier A (distinct roles >= 200)", "in": 730, "out": 95 + k},
        ],
        "distributions": {"firm_ai_share": {"firms_measured": 12}},
        "matrices": {"signal_type_by_bucket": {"rows": ["builds", "integrates", "uses_tools", "none"], "columns": cols, "cells": cells}},
        "firms": firms,
        "baselines": {"boston_all": {"firms": 3, "soc_major": [{"code": "unassigned", "title": "U", "share": 0.6},
                                                               {"code": "15-0000", "title": "C", "share": 0.2},
                                                               {"code": "13-0000", "title": "B", "share": 0.1},
                                                               {"code": "11-0000", "title": "M", "share": 0.1}]}},
        "filter_coverage": {"sector_bucket": {"known": 12, "total": 20}},
    }


def stand_in(cfg, out_dir):
    with open(cfg["inputs"]["input_file"]) as fh:
        fh.read()
    with open(os.path.join(out_dir, "ecosystem.json"), "w") as fh:
        json.dump(fake_eco(cfg), fh)
    return 0


class Repo:
    """A temporary git repo laid out like this one, with fixture config, registry and paper files."""

    def __init__(self, signed=True, roster=None):
        self.dir = tempfile.mkdtemp(prefix="mv-test-")
        self.paths = Paths(self.dir)
        os.makedirs(os.path.join(self.dir, "pipeline", "ai_job_map", "config"))
        os.makedirs(self.paths.branches)
        os.makedirs(self.paths.proposals)
        os.makedirs(os.path.join(self.dir, "secret"))
        os.makedirs(os.path.join(self.dir, "inputs"))
        self.input = os.path.join(self.dir, "inputs", "data.txt")
        with open(self.input, "w") as fh:
            fh.write("input rows\n")
        with open(os.path.join(self.dir, "secret", "test-set.csv"), "w") as fh:
            fh.write("firm,label\n")
        cfg = copy.deepcopy(FIX_CFG)
        cfg["inputs"]["input_file"] = self.input
        with open(self.paths.config, "w") as fh:
            json.dump(cfg, fh, indent=1)
        with open(os.path.join(self.dir, "pipeline", "code.py"), "w") as fh:
            fh.write("x = 1\n")
        with open(self.paths.registry, "w") as fh:
            fh.write(dump_yaml(FIX_POINTS))
        spec = load_yaml(REAL.key_results)
        if signed:
            spec["signed_off_by"], spec["signed_off_on"] = LEAD, "2026-11-23"
        with open(self.paths.key_results, "w") as fh:
            fh.write(dump_yaml(spec))
        with open(self.paths.roster, "w") as fh:
            fh.write(dump_yaml(roster if roster is not None else [
                {"name": LEAD, "role": "lead-author", "rater": False, "ratings_complete": None},
                {"name": "Done Rater", "role": "contributor", "rater": True, "ratings_complete": True},
                {"name": "Busy Rater", "role": "contributor", "rater": True, "ratings_complete": False}]))
        shutil.copy(REAL.decision_log, self.paths.decision_log)
        self.branch("BR-0000", None, None, {})
        self.git("init", "-q")
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "fixture")

    def git(self, *a):
        subprocess.run(["git", "-C", self.dir, *a], check=True, capture_output=True)

    def branch(self, bid, pid, dp, ov):
        with open(os.path.join(self.paths.branches, bid + ".yaml"), "w") as fh:
            fh.write(dump_yaml({"branch_id": bid, "proposal_id": pid, "decision_point": dp, "overrides": ov}))

    def propose(self, pid="P-0001", dp="DP-01", accept=True):
        with open(os.path.join(self.paths.proposals, pid + ".md"), "w") as fh:
            fh.write("my words\n")
        logs.append_event(self.paths, {"proposal_id": pid, "decision_point": dp, "status": "proposed",
                                       "proposer": "Done Rater", "alternative": "raise the firm minimum to 5"})
        if accept:
            logs.append_event(self.paths, {"proposal_id": pid, "decision_point": dp, "status": "accepted",
                                           "decided_by": LEAD, "reason": "precedent in the literature"})

    def cleanup(self):
        shutil.rmtree(self.dir, ignore_errors=True)


# ---------------------------------------------------------------- registry

class TestRegistry(unittest.TestCase):
    def test_real_registry_parses_with_unique_ids_and_expected_counts(self):
        pts = registry.load(REAL)
        self.assertEqual(len(pts), 57)
        self.assertEqual(len({p["id"] for p in pts}), 57)
        counts = {}
        for p in pts:
            counts[p["branchable"]] = counts.get(p["branchable"], 0) + 1
        self.assertEqual(counts, {"now": 28, "locked": 24, "not-built": 5})

    def test_real_registry_agrees_with_real_config(self):
        errs = registry.check(registry.load(REAL), load_json(REAL.config))
        self.assertEqual(errs, [], "\n".join(errs))

    def test_fixture_registry_is_clean(self):
        self.assertEqual(registry.check(FIX_POINTS, FIX_CFG), [])

    def test_yaml_booleans_are_caught(self):
        bad = copy.deepcopy(FIX_POINTS)
        bad[0]["current_value"] = True          # what `current_value: on` becomes
        errs = registry.check(bad, FIX_CFG)
        self.assertTrue(any("booleans" in e for e in errs), errs)

    def test_a_key_in_two_points_is_caught(self):
        bad = copy.deepcopy(FIX_POINTS)
        bad[1]["parameters"].append({"key": "skills.min_support_firms", "form": "value", "origin": "existing"})
        self.assertTrue(any("also belongs to" in e for e in registry.check(bad, FIX_CFG)))

    def test_a_key_missing_from_the_config_is_caught(self):
        bad = copy.deepcopy(FIX_POINTS)
        bad[0]["parameters"][0]["key"] = "skills.nope"
        self.assertTrue(any("not in the config" in e for e in registry.check(bad, FIX_CFG)))

    def test_a_protected_key_cannot_be_a_parameter(self):
        bad = copy.deepcopy(FIX_POINTS)
        bad[0]["parameters"][0]["key"] = "inputs.input_file"
        self.assertTrue(any("protected" in e for e in registry.check(bad, FIX_CFG)))


# ---------------------------------------------------------------- overrides

def br(ov, dp="DP-01"):
    return {"branch_id": "BR-0001", "proposal_id": "P-0001", "decision_point": dp, "overrides": ov}


class TestOverrides(unittest.TestCase):
    def refused(self, branch, needle):
        errs = overrides.validate(branch, FIX_POINTS, FIX_CFG)
        self.assertTrue(any(needle in e for e in errs), f"expected {needle!r} in {errs}")

    def test_a_valid_override_passes(self):
        self.assertEqual(overrides.validate(br({"skills.min_support_firms": 5}), FIX_POINTS, FIX_CFG), [])
        self.assertEqual(overrides.validate(br({"agg.flag": False}, "DP-04"), FIX_POINTS, FIX_CFG), [])

    def test_locked_key(self):
        self.refused(br({"tier.cutoff": 100}, "DP-03"), "locked DP-03")

    def test_key_not_in_base_config(self):
        self.refused(br({"skills.min_support_people": 5}), "not in the base config")

    def test_key_in_config_but_no_decision_point(self):
        self.refused(br({"notes.text": "x"}), "not a parameter of any decision point")

    def test_protected_keys(self):
        for k in ("inputs.input_file", "inputs.output_dir", "data_version", "method_versions.x", "multiverse.locked_paths"):
            self.refused(br({k: "x"}), "protected")

    def test_type_change(self):
        self.refused(br({"skills.min_support_firms": "5"}), "changes the type")
        self.refused(br({"skills.min_support_firms": True}), "changes the type")
        self.refused(br({"skills.stoplist": [1, 2]}, "DP-02"), "changes the type")

    def test_variant_not_implemented(self):
        self.refused(br({"agg.omega": "median"}, "DP-04"), "not implemented")

    def test_spans_more_than_one_point(self):
        self.refused(br({"skills.min_support_firms": 5, "skills.max_ngram": 2}), "span")

    def test_override_must_match_the_named_point(self):
        self.refused(br({"skills.max_ngram": 2}, "DP-01"), "but the branch names DP-01")

    def test_not_built_point(self):
        self.refused(br({"unbuilt.window": 12}, "DP-05"), "not-built")

    def test_below_minimum(self):
        self.refused(br({"skills.min_support_firms": 0}), "below the minimum")

    def test_default_branch_takes_no_overrides(self):
        errs = overrides.validate({"branch_id": "BR-0000", "proposal_id": None, "decision_point": None,
                                   "overrides": {"skills.max_ngram": 2}}, FIX_POINTS, FIX_CFG)
        self.assertTrue(errs)

    def test_applying_never_changes_the_base(self):
        base = copy.deepcopy(FIX_CFG)
        eff = with_overrides(base, {"skills.min_support_firms": 5})
        self.assertEqual(base, FIX_CFG)
        self.assertEqual(eff["skills"]["min_support_firms"], 5)
        self.assertEqual(canonical_sha256(with_overrides(base, {})), canonical_sha256(FIX_CFG))

    def test_branch_ids_cannot_point_outside_the_branches_folder(self):
        with self.assertRaises(ValueError):
            overrides.load_branch(REAL, "../../data/ai-job-map")


# ---------------------------------------------------------------- guard

class TestGuard(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix="mv-guard-")
        self.locked = os.path.join(self.d, "locked")
        self.run = os.path.join(self.d, "run")
        self.other = os.path.join(self.d, "other")
        for p in (self.locked, self.run, self.other):
            os.makedirs(p)
        self.secret = os.path.join(self.locked, "test-set.csv")
        with open(self.secret, "w") as fh:
            fh.write("x\n")
        with gzip.open(self.secret + ".gz", "wt") as fh:
            fh.write("x\n")
        self.ok = os.path.join(self.other, "input.txt")
        with open(self.ok, "w") as fh:
            fh.write("y\n")

    def tearDown(self):
        shutil.rmtree(self.d, ignore_errors=True)

    def test_locked_paths_cannot_be_read_or_listed(self):
        with Guard([self.locked], [self.run]):
            for fn in (lambda: open(self.secret), lambda: gzip.open(self.secret + ".gz", "rt"),
                       lambda: os.listdir(self.locked), lambda: os.scandir(self.locked),
                       lambda: os.open(self.secret, os.O_RDONLY), lambda: open(os.path.join(self.run, "..", "locked", "test-set.csv"))):
                with self.assertRaises(GuardViolation):
                    fn()

    def test_symlinks_into_locked_paths_are_refused(self):
        link = os.path.join(self.other, "sneaky.csv")
        os.symlink(self.secret, link)
        with Guard([self.locked], [self.run]):
            with self.assertRaises(GuardViolation):
                open(link)

    def test_reads_elsewhere_work_and_are_recorded(self):
        with Guard([self.locked], [self.run]) as g:
            with open(self.ok) as fh:
                self.assertEqual(fh.read(), "y\n")
        self.assertIn(os.path.realpath(self.ok), g.reads)

    def test_writes_only_inside_the_run_folder(self):
        with Guard([self.locked], [self.run]):
            with open(os.path.join(self.run, "out.json"), "w") as fh:
                fh.write("{}")
            os.makedirs(os.path.join(self.run, "firms", "a"), exist_ok=True)
            for fn in (lambda: open(os.path.join(self.other, "main-output.json"), "w"),
                       lambda: open(self.ok, "a"),
                       lambda: os.makedirs(os.path.join(self.other, "new")),
                       lambda: os.replace(os.path.join(self.run, "out.json"), os.path.join(self.other, "moved.json")),
                       lambda: os.remove(self.ok),
                       lambda: open(os.path.join(self.locked, "x"), "w")):
                with self.assertRaises(GuardViolation):
                    fn()
        self.assertTrue(os.path.exists(self.ok))

    def test_functions_are_restored_even_after_an_error(self):
        orig = (open, gzip.open, os.listdir, os.scandir, os.replace)
        with self.assertRaises(GuardViolation):
            with Guard([self.locked], [self.run]):
                open(self.secret)
        self.assertEqual((open, gzip.open, os.listdir, os.scandir, os.replace), orig)
        with open(self.secret) as fh:
            self.assertEqual(fh.read(), "x\n")


# ---------------------------------------------------------------- logs and roster

class TestLogs(unittest.TestCase):
    def setUp(self):
        self.r = Repo()

    def tearDown(self):
        self.r.cleanup()

    def test_roster_gate(self):
        roster = logs.load_roster(self.r.paths)
        self.assertTrue(logs.cleared(roster, LEAD)[0])
        self.assertTrue(logs.cleared(roster, "Done Rater")[0])
        self.assertFalse(logs.cleared(roster, "Busy Rater")[0])
        self.assertFalse(logs.cleared(roster, "Someone New")[0])   # not listed = incomplete rater

    def test_only_the_lead_author_decides_and_rejections_need_reasons(self):
        self.r.propose(accept=False)
        with self.assertRaises(logs.LogError):
            logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "accepted",
                                             "decided_by": "Done Rater", "reason": "I like it"})
        with self.assertRaises(logs.LogError):
            logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "rejected",
                                             "decided_by": LEAD, "reason": ""})

    def test_the_log_is_appended_never_rewritten(self):
        before = open(self.r.paths.decision_log, "rb").read()
        self.r.propose()
        after = open(self.r.paths.decision_log, "rb").read()
        self.assertTrue(after.startswith(before))
        evs = logs.load_events(self.r.paths)
        self.assertEqual([e["event_id"] for e in evs], ["E-0001", "E-0002"])
        self.assertEqual([e["status"] for e in evs], ["proposed", "accepted"])

    def test_results_seen_is_computed_not_typed(self):
        self.r.propose()
        logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "run",
                                         "results_link": "paper/multiverse/runs/BR-0001/x"})
        e = logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "adopted",
                                             "decided_by": LEAD, "reason": "held up", "results_seen": "before"})
        self.assertEqual(e["results_seen"], "after")
        first = logs.load_events(self.r.paths)[1]
        self.assertEqual(first["results_seen"], "before")

    def test_a_correction_sets_the_corrected_event_aside(self):
        self.r.propose(accept=False)
        logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "rejected",
                                         "decided_by": LEAD, "reason": "wrong point"})
        logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "accepted",
                                         "decided_by": LEAD, "reason": "rejected by mistake", "corrects": "E-0002"})
        self.assertEqual(logs.latest_decision(logs.load_events(self.r.paths), "P-0001")["status"], "accepted")
        with self.assertRaises(logs.LogError):
            logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "accepted",
                                             "decided_by": LEAD, "reason": "x", "corrects": "E-0099"})


# ---------------------------------------------------------------- runner

class TestRunner(unittest.TestCase):
    def setUp(self):
        self.r = Repo()

    def tearDown(self):
        self.r.cleanup()

    def run_(self, bid="BR-0000", person=LEAD, analysis=stand_in):
        return run_branch(bid, person, self.r.paths, analysis)

    def test_default_run_writes_every_file_and_full_provenance(self):
        res = self.run_()
        d = res["run_dir"]
        self.assertTrue(d.startswith(self.r.paths.runs + os.sep))
        for f in ("effective-config.json", "outputs/ecosystem.json", "key_results.json", "diff_vs_default.json", "provenance.json", "build.log"):
            self.assertTrue(os.path.exists(os.path.join(d, f)), f)
        prov = load_json(os.path.join(d, "provenance.json"))
        for f in PROVENANCE_FIELDS:
            self.assertIn(f, prov)
        for f in ("runner_version", "branch_id", "override_file_sha256", "base_config_sha256", "effective_config_sha256",
                  "code_commit", "started_at", "finished_at", "outputs_dir"):
            self.assertTrue(prov[f], f)
        self.assertIs(prov["code_dirty"], False)
        self.assertEqual(prov["status"], "ok")
        self.assertEqual(prov["base_config_sha256"], prov["effective_config_sha256"])
        self.assertEqual(prov["ran_by"]["roster_name"], LEAD)
        self.assertIn("os_user", prov["ran_by"])
        self.assertIn("python", prov["environment"])
        self.assertEqual(prov["locked_paths"], ["data/firm-classifier/", "paper/prereg/", "secret/"])
        rec = [i for i in prov["inputs"] if i["path"] == os.path.realpath(self.r.input)]
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["size"], os.path.getsize(self.r.input))
        self.assertEqual(len(rec[0]["sha256"]), 64)

    def test_dirty_pipeline_is_refused(self):
        with open(os.path.join(self.r.dir, "pipeline", "code.py"), "a") as fh:
            fh.write("y = 2\n")
        with self.assertRaisesRegex(Refused, "uncommitted"):
            self.run_()
        with open(os.path.join(self.r.dir, "pipeline", "new.py"), "w") as fh:
            fh.write("")
        with self.assertRaisesRegex(Refused, "uncommitted"):
            self.run_()

    def test_people_the_roster_does_not_clear_are_refused(self):
        for person in ("Busy Rater", "Someone New"):
            with self.assertRaises(Refused):
                self.run_(person=person)
        self.assertEqual(self.run_(person="Done Rater")["provenance"]["status"], "ok")

    def test_unsigned_key_results_allow_only_the_default(self):
        self.r.cleanup()
        self.r = Repo(signed=False)
        self.r.propose()
        self.r.branch("BR-0001", "P-0001", "DP-01", {"skills.min_support_firms": 5})
        self.assertEqual(self.run_()["provenance"]["status"], "ok")
        with self.assertRaisesRegex(Refused, "signed off"):
            self.run_("BR-0001")

    def test_a_proposal_that_is_not_accepted_is_refused(self):
        self.r.propose(accept=False)
        self.r.branch("BR-0001", "P-0001", "DP-01", {"skills.min_support_firms": 5})
        with self.assertRaisesRegex(Refused, "not accepted"):
            self.run_("BR-0001")
        logs.append_event(self.r.paths, {"proposal_id": "P-0001", "decision_point": "DP-01", "status": "rejected",
                                         "decided_by": LEAD, "reason": "no precedent and breaks the support rule"})
        with self.assertRaisesRegex(Refused, "rejected"):
            self.run_("BR-0001")

    def test_an_acceptance_typed_in_by_someone_else_is_refused(self):
        self.r.propose(accept=False)
        with open(self.r.paths.decision_log, "a") as fh:     # a hand edit that skips log-event's checks
            fh.write("\n" + dump_yaml([{"event_id": "E-0002", "proposal_id": "P-0001", "decision_point": "DP-01",
                                        "status": "accepted", "decided_by": "Done Rater", "reason": "x", "date": "2026-11-23T00:00:00Z"}]))
        self.r.branch("BR-0001", "P-0001", "DP-01", {"skills.min_support_firms": 5})
        with self.assertRaisesRegex(Refused, "not accepted by the lead author"):
            self.run_("BR-0001")

    def test_a_locked_point_is_refused_even_when_accepted(self):
        self.r.propose(dp="DP-03")
        self.r.branch("BR-0001", "P-0001", "DP-03", {"tier.cutoff": 100})
        with self.assertRaisesRegex(Refused, "locked DP-03"):
            self.run_("BR-0001")

    def test_an_accepted_branch_runs_against_a_fresh_default_and_is_logged(self):
        self.r.propose()
        self.r.branch("BR-0001", "P-0001", "DP-01", {"skills.min_support_firms": 5})
        res = self.run_("BR-0001")
        prov = res["provenance"]
        self.assertTrue(prov["compared_with"].startswith("paper/multiverse/runs/BR-0000/"))
        self.assertNotEqual(prov["effective_config_sha256"], prov["base_config_sha256"])
        self.assertEqual(load_json(os.path.join(res["run_dir"], "effective-config.json"))["skills"]["min_support_firms"], 5)
        self.assertTrue(res["diff"]["KR-01"]["changed"])
        self.assertTrue(res["diff"]["KR-02"]["flipped"])       # 95% -> 40% crosses 50%
        self.assertFalse(res["diff"]["KR-01"]["flipped"])      # flip rule none
        self.assertTrue(res["diff"]["KR-05"]["flipped"])       # builds 10 -> 6 drops below integrates 10
        ev = logs.load_events(self.r.paths)[-1]
        self.assertEqual((ev["status"], ev["decided_by"], ev["results_link"]), ("run", "runner", self.r.paths.rel(res["run_dir"])))
        self.assertEqual(ev["alternative"], "raise the firm minimum to 5")
        # a second branch reuses the default run instead of running it again
        n_default = len(os.listdir(os.path.join(self.r.paths.runs, "BR-0000")))
        self.run_("BR-0001")
        self.assertEqual(len(os.listdir(os.path.join(self.r.paths.runs, "BR-0000"))), n_default)

    def test_a_default_run_is_redone_when_an_input_changes(self):
        self.run_()
        with open(self.r.input, "a") as fh:
            fh.write("more rows\n")
        self.r.propose()
        self.r.branch("BR-0001", "P-0001", "DP-01", {"skills.min_support_firms": 5})
        self.run_("BR-0001")
        self.assertEqual(len(os.listdir(os.path.join(self.r.paths.runs, "BR-0000"))), 2)

    def test_a_build_that_reads_a_locked_path_is_stopped(self):
        def snoop(cfg, out_dir):
            open(os.path.join(self.r.dir, "secret", "test-set.csv")).read()
            return stand_in(cfg, out_dir)
        with self.assertRaises(GuardViolation):
            self.run_(analysis=snoop)

    def test_a_build_that_writes_the_main_outputs_is_stopped(self):
        def leak(cfg, out_dir):
            os.makedirs(os.path.join(self.r.dir, cfg["inputs"]["output_dir"]))
            return stand_in(cfg, out_dir)
        with self.assertRaises(GuardViolation):
            self.run_(analysis=leak)
        self.assertFalse(os.path.exists(os.path.join(self.r.dir, "data", "out")))


# ---------------------------------------------------------------- key results on the real v1 outputs

class TestKeyResults(unittest.TestCase):
    def test_every_key_result_reads_from_a_fixture_and_diffs_with_itself(self):
        spec = load_yaml(REAL.key_results)
        kr = keyresults.compute(fake_eco(FIX_CFG), spec)
        self.assertEqual(set(kr), {f"KR-0{i}" for i in range(1, 10)})
        d = keyresults.diff(kr, kr, spec)
        self.assertFalse(any(e["changed"] or e["flipped"] for e in d.values()))

    def test_ties_are_kept_together(self):
        kr = keyresults.compute(fake_eco(FIX_CFG), load_yaml(REAL.key_results))
        self.assertEqual(kr["KR-05"]["value"], [["builds", "integrates"], ["uses_tools"]])
        self.assertEqual(kr["KR-06"]["value"], {"it-services": ["builds"], "software-internet": ["integrates"]})
        self.assertEqual(kr["KR-08"]["value"], ["15-0000"])


# ---------------------------------------------------------------- what the runner can reach

class TestReach(unittest.TestCase):
    def test_no_multiverse_module_imports_classifier_code(self):
        here = os.path.join(ROOT, "pipeline", "multiverse")
        for fn in os.listdir(here):
            if not fn.endswith(".py"):
                continue
            tree = ast.parse(open(os.path.join(here, fn)).read())
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""] + [a.name for a in node.names]
                for n in names:
                    self.assertNotIn("classif", n.lower(), f"{fn} imports {n}")

    def test_the_only_analysis_is_the_job_map_build(self):
        import inspect
        from pipeline.multiverse import runner
        src = inspect.getsource(runner.job_map_analysis)
        self.assertIn("from pipeline.ai_job_map import build", src)
        self.assertEqual([n for n in dir(runner) if n.endswith("_analysis")], ["job_map_analysis"])


if __name__ == "__main__":
    unittest.main()
