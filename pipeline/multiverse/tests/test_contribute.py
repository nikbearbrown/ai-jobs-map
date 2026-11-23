"""Tests for the commands the /contribute skill calls (pipeline/multiverse/contribute.py), the skill's own files
(.claude/skills/contribute/), and the example session the skill ships as a fixture.

The example session is replayed here with the real registry, config, key results and templates, and a stand-in
build whose numbers are invented (example_build). Its key-results table must match the one shown in the fixture."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from pipeline.multiverse import cli, contribute, keyresults, logs
from pipeline.multiverse.common import LOCKED_PATHS_FLOOR, ROOT, Paths, dump_yaml, load_yaml
from pipeline.multiverse.contribute import ContributeError
from pipeline.multiverse.runner import run_branch
from pipeline.multiverse.tests.test_multiverse import LEAD, REAL, Repo, stand_in

SKILL_DIR = os.path.join(ROOT, ".claude", "skills", "contribute")
FIXTURE = os.path.join(SKILL_DIR, "fixtures", "example-session.md")
EXAMPLE = "Example Contributor"


def copy_paper_files(paths):
    os.makedirs(paths.templates, exist_ok=True)
    for f in ("proposal.md", "interpretation.md"):
        shutil.copy(os.path.join(REAL.templates, f), os.path.join(paths.templates, f))
    shutil.copy(REAL.contributions, paths.contributions)
    shutil.copy(REAL.verification_log, paths.verification_log)


def fill(path, sections):
    text = open(path).read()
    for h, body in sections.items():
        text = contribute.set_section(text, h, body)
    with open(path, "w") as fh:
        fh.write(text)


def example_build(cfg, out_dir):
    """A stand-in for the AI jobs map build, used only for the example session. EVERY NUMBER IT WRITES IS INVENTED. It
    reacts to skills.min_support_firms so the example has something to interpret."""
    hi = cfg["skills"]["min_support_firms"] > 3
    cols = ["it-services", "software-internet", "sector not measured"]
    firms = [{"firm_id": f"example-firm-{i}", "bucket": cols[0] if i < 21 else cols[1], "ai_share": 0.5} for i in range(40)]
    if hi:
        firms[-1]["ai_share"] = None
    cell = lambda n: {"firms": n, "roles": n, "roles_excluding_largest_firm": n}
    rows = {"builds": [12 - hi, 10, 0], "integrates": [8, 10 - hi, 0], "uses_tools": [2, 1, 0], "none": [0, 0, 0]}
    eco = {
        "computed_at": "example",
        "step_counts": [
            {"step": "live: distinct roles -> SOC by title (exact, then trailing phrase)", "in": 1000, "out": 400},
            {"step": "ai: text roles -> roles naming a seed skill (base rate)", "in": 1000, "out": 200},
            {"step": "ai: roles with omega -> AI-related (omega > 0.1)", "in": 970 if hi else 1000, "out": 860 if hi else 900},
            {"step": "tiers: firms -> Tier A (distinct roles >= 200)", "in": 700, "out": 100},
        ],
        "distributions": {"firm_ai_share": {"firms_measured": 39 if hi else 40}},
        "matrices": {"signal_type_by_bucket": {"rows": list(rows), "columns": cols,
                                               "cells": [[cell(n) for n in rows[r]] for r in rows]}},
        "firms": firms,
        "baselines": {"boston_all": {"firms": 12, "soc_major": [{"code": "15-0000", "title": "Computer and Mathematical", "share": 0.3},
                                                                {"code": "13-0000", "title": "Business and Financial Operations", "share": 0.2},
                                                                {"code": "11-0000", "title": "Management", "share": 0.1}]}},
        "filter_coverage": {"sector_bucket": {"known": 40, "total": 60}},
    }
    with open(os.path.join(out_dir, "ecosystem.json"), "w") as fh:
        json.dump(eco, fh)
    return 0


class RealRepo(Repo):
    """A temporary git repo with the real config, registry, key results and templates, for the example session."""

    def __init__(self):
        self.dir = tempfile.mkdtemp(prefix="mv-example-")
        self.paths = Paths(self.dir)
        for d in (os.path.dirname(self.paths.config), self.paths.branches, self.paths.proposals):
            os.makedirs(d)
        shutil.copy(REAL.config, self.paths.config)
        shutil.copy(REAL.registry, self.paths.registry)
        shutil.copy(REAL.key_results, self.paths.key_results)
        shutil.copy(REAL.decision_log, self.paths.decision_log)
        shutil.copy(os.path.join(REAL.branches, "BR-0000.yaml"), self.paths.branches)
        copy_paper_files(self.paths)
        with open(self.paths.roster, "w") as fh:
            fh.write(dump_yaml([{"name": LEAD, "role": "lead-author", "rater": False, "ratings_complete": None},
                                {"name": EXAMPLE, "role": "contributor", "rater": True, "ratings_complete": True}]))
        self.git("init", "-q")
        self.commit("-A")


class FixtureRepo(Repo):
    def __init__(self, **kw):
        super().__init__(**kw)
        copy_paper_files(self.paths)
        self.commit("-A")


# ---------------------------------------------------------------- the commands

class TestStatusAndPoints(unittest.TestCase):
    def setUp(self):
        self.r = FixtureRepo()

    def tearDown(self):
        self.r.cleanup()

    def test_the_gate(self):
        s = contribute.status(self.r.paths, LEAD)
        self.assertTrue(s["cleared_for_results"] and s["is_lead_author"])
        self.assertTrue(contribute.status(self.r.paths, "Done Rater")["cleared_for_results"])
        for name in ("Busy Rater", "Someone New"):
            s = contribute.status(self.r.paths, name)
            self.assertFalse(s["cleared_for_results"])
            self.assertFalse(s["is_lead_author"])

    def test_people_not_cleared_see_no_reasons_or_run_folders(self):
        self.r.propose()      # proposed by Done Rater, accepted with a reason
        logs.append_event(self.r.paths, {"proposal_id": "P-0002", "decision_point": "DP-01", "status": "proposed",
                                         "proposer": "Busy Rater", "alternative": "x"})
        logs.append_event(self.r.paths, {"proposal_id": "P-0002", "decision_point": "DP-01", "status": "rejected",
                                         "decided_by": LEAD, "reason": "the default run shows 95 firms either way"})
        busy = contribute.status(self.r.paths, "Busy Rater")["proposals"]
        self.assertEqual(busy, [{"proposal_id": "P-0002", "decision_point": "DP-01", "status": "rejected"}])
        done = contribute.status(self.r.paths, "Done Rater")["proposals"]
        self.assertEqual(done[0]["reason"], "precedent in the literature")

    def test_points_lists_only_open_unlocked_branchable_points(self):
        self.assertEqual([p["id"] for p in contribute.points(self.r.paths)], ["DP-01", "DP-02", "DP-04"])
        self.assertEqual(len(contribute.points(self.r.paths, show_all=True)), 5)


class TestOwn(unittest.TestCase):
    def setUp(self):
        self.r = FixtureRepo()

    def tearDown(self):
        self.r.cleanup()

    def test_owning_changes_two_lines_and_nothing_else(self):
        before = open(self.r.paths.registry).read().splitlines()
        contribute.own(self.r.paths, "DP-02", "Busy Rater")    # research and proposals are open to raters
        after = open(self.r.paths.registry).read().splitlines()
        changed = [(a, b) for a, b in zip(before, after) if a != b]
        self.assertEqual(len(before), len(after))
        self.assertEqual(changed, [("  owner: null", "  owner: Busy Rater"), ("  status: open", "  status: owned")])
        self.assertNotIn("DP-02", [p["id"] for p in contribute.points(self.r.paths)])

    def test_locked_owned_and_release_rules(self):
        with self.assertRaisesRegex(ContributeError, "locked"):
            contribute.own(self.r.paths, "DP-03", "Done Rater")
        contribute.own(self.r.paths, "DP-01", "Done Rater")
        with self.assertRaisesRegex(ContributeError, "owned by Done Rater"):
            contribute.own(self.r.paths, "DP-01", "Busy Rater")
        with self.assertRaisesRegex(ContributeError, "give DP-01 back"):
            contribute.own(self.r.paths, "DP-01", "Busy Rater", release=True)
        p = contribute.own(self.r.paths, "DP-01", LEAD, release=True)
        self.assertEqual((p["owner"], p["status"]), (None, "open"))


class TestProposals(unittest.TestCase):
    def setUp(self):
        self.r = FixtureRepo()

    def tearDown(self):
        self.r.cleanup()

    def draft(self, dp="DP-01", **kw):
        pid, path = contribute.new_proposal(self.r.paths, dp, "Done Rater", **kw)
        return pid, path

    def test_a_new_proposal_has_the_header_and_registry_text_but_none_of_the_contributors_sections(self):
        pid, path = self.draft(eliminate=True)
        self.assertEqual(pid, "P-0001")
        fm, body = contribute.front(open(path).read())
        self.assertEqual((fm["proposal_id"], fm["decision_point"], fm["proposer"], fm["proposer_recommends"]),
                         ("P-0001", "DP-01", "Done Rater", "eliminate"))
        self.assertIs(fm["results_seen_before_proposing"], False)
        secs = contribute.sections(body)
        self.assertIn("DP-01", secs["Decision point"])
        self.assertIn("skills.min_support_firms", secs["Current choice"])
        for h in contribute.PROPOSAL_SECTIONS:
            self.assertEqual(contribute.written(secs[h]), "", h)

    def test_propose_waits_for_the_contributors_words_then_logs_them_unchanged(self):
        pid, path = self.draft()
        with self.assertRaisesRegex(ContributeError, "hasn't written"):
            contribute.propose(self.r.paths, pid)
        fill(path, {"Alternative": "Raise the firm minimum from 3 to 5.\n\nMore detail here.",
                    "Rationale (contributor's own words, with precedent if any)": "My reasons, as I typed them."})
        with self.assertRaisesRegex(ContributeError, "What we'd expect"):
            contribute.propose(self.r.paths, pid)
        fill(path, {"What we'd expect to see if the finding is fragile": "KR-02 falls."})
        before = open(path).read()
        e = contribute.propose(self.r.paths, pid, ai="found the config key")
        self.assertEqual((e["status"], e["proposer"], e["decided_by"], e["results_seen"]), ("proposed", "Done Rater", "Done Rater", "before"))
        self.assertEqual(e["alternative"], "Raise the firm minimum from 3 to 5.")
        after = open(path).read()
        self.assertEqual(contribute.sections(contribute.front(after)[1]), contribute.sections(contribute.front(before)[1]))
        self.assertEqual(contribute.front(after)[0]["ai_assistance"], "found the config key")
        with self.assertRaisesRegex(ContributeError, "already"):
            contribute.propose(self.r.paths, pid)

    def test_locked_points_take_no_proposals(self):
        with self.assertRaisesRegex(ContributeError, "locked"):
            self.draft("DP-03")

    def test_after_a_run_the_proposer_must_say_whether_they_saw_results(self):
        self.r.propose()
        self.r.branch("BR-0001", "P-0001", "DP-01", {"skills.min_support_firms": 5})
        run_branch("BR-0001", LEAD, self.r.paths, stand_in)
        with self.assertRaisesRegex(ContributeError, "seen-results"):
            self.draft()
        pid, path = self.draft(seen_results=True)
        self.assertIs(contribute.front(open(path).read())[0]["results_seen_before_proposing"], True)


class TestBranchesAndInterpretations(unittest.TestCase):
    def setUp(self):
        self.r = FixtureRepo()
        self.pid, self.path = contribute.new_proposal(self.r.paths, "DP-01", "Done Rater")
        fill(self.path, {"Alternative": "Firm minimum 5.", "Rationale (contributor's own words, with precedent if any)": "Mine.",
                         "What we'd expect to see if the finding is fragile": "KR-02 falls by 5 points or more."})
        contribute.propose(self.r.paths, self.pid)

    def tearDown(self):
        self.r.cleanup()

    def accept(self):
        logs.append_event(self.r.paths, {"proposal_id": self.pid, "decision_point": "DP-01", "status": "accepted",
                                         "decided_by": LEAD, "reason": "defensible and consistent"})

    def test_no_branch_before_the_lead_author_accepts(self):
        with self.assertRaisesRegex(ContributeError, "proposed"):
            contribute.new_branch(self.r.paths, self.pid, ["skills.min_support_firms=5"])

    def test_the_branch_override_is_checked_and_recorded_in_the_proposal(self):
        self.accept()
        with self.assertRaisesRegex(ContributeError, "locked DP-03"):
            contribute.new_branch(self.r.paths, self.pid, ["tier.cutoff=100"])
        with self.assertRaisesRegex(ContributeError, "below"):
            contribute.new_branch(self.r.paths, self.pid, ["skills.min_support_firms=0"])
        b = contribute.new_branch(self.r.paths, self.pid, ["skills.min_support_firms=5"])
        self.assertEqual(b, {"branch_id": "BR-0001", "proposal_id": self.pid, "decision_point": "DP-01",
                             "overrides": {"skills.min_support_firms": 5}})
        self.assertEqual(contribute.front(open(self.path).read())[0]["override"], {"skills.min_support_firms": 5})
        self.assertEqual(contribute.override_checks(self.r.paths, b), [])
        b10 = dict(b, overrides={"skills.min_support_firms": 10})
        self.assertIn("10 isn't in P-0001's Alternative", contribute.override_checks(self.r.paths, b10)[0])
        with self.assertRaisesRegex(ContributeError, "already has BR-0001"):
            contribute.new_branch(self.r.paths, self.pid, ["skills.min_support_firms=6"])

    def test_interpretation_needs_clearance_and_a_run_and_quotes_the_prediction_as_it_was_run(self):
        self.accept()
        contribute.new_branch(self.r.paths, self.pid, ["skills.min_support_firms=5"])
        with self.assertRaisesRegex(ContributeError, "hasn't run"):
            contribute.new_interpretation(self.r.paths, "BR-0001", "Done Rater")
        self.r.commit(self.path, os.path.join(self.r.paths.branches, "BR-0001.yaml"))
        run_branch("BR-0001", "Done Rater", self.r.paths, stand_in)
        with open(self.path, "a") as fh:
            fh.write("A later edit that isn't what the branch ran against.\n")
        for name in ("Busy Rater", "Someone New"):
            with self.assertRaisesRegex(ContributeError, "waits until the roster clears"):
                contribute.new_interpretation(self.r.paths, "BR-0001", name)
        out = contribute.new_interpretation(self.r.paths, "BR-0001", "Done Rater")
        secs = contribute.sections(contribute.front(open(out).read())[1])
        self.assertIn("> KR-02 falls by 5 points or more.", secs["Your prediction, written before the run"])
        self.assertNotIn("later edit", secs["Your prediction, written before the run"])
        self.assertIn("KR-02", secs["Key results against the default"])
        for h in contribute.INTERPRETATION_SECTIONS:
            self.assertEqual(contribute.written(secs[h]), "", h)
        with self.assertRaisesRegex(ContributeError, "already exists"):
            contribute.new_interpretation(self.r.paths, "BR-0001", "Done Rater")


class TestLogEntries(unittest.TestCase):
    def setUp(self):
        self.r = FixtureRepo()

    def tearDown(self):
        self.r.cleanup()

    def test_nothing_is_written_until_the_contributor_confirms(self):
        before = open(self.r.paths.contributions).read()
        e = contribute.contribution(self.r.paths, "Done Rater", "Owned DP-01.", ["Methodology"], "component", [], "", False)
        self.assertFalse(e["confirmed_by_contributor"])
        self.assertEqual(open(self.r.paths.contributions).read(), before)

    def test_entries_append_and_keep_the_header(self):
        header = open(self.r.paths.contributions).read().split("\n[]")[0]
        contribute.contribution(self.r.paths, "Done Rater", "Owned DP-01.", ["Methodology", "Formal analysis"], "component",
                                ["paper/multiverse/proposals/P-0001.md"], "Claude Code ran the branch", True)
        contribute.contribution(self.r.paths, "Busy Rater", "Read the guide; chose no task yet.", [], "none", [], "", True)
        text = open(self.r.paths.contributions).read()
        self.assertTrue(text.startswith(header))
        data = load_yaml(self.r.paths.contributions)
        self.assertEqual([e["entry_id"] for e in data], ["C-0001", "C-0002"])
        self.assertEqual(data[0]["task"], "Owned DP-01.")

    def test_credit_roles_must_be_crediT_roles(self):
        with self.assertRaisesRegex(ContributeError, "not a CRediT role"):
            contribute.contribution(self.r.paths, "x", "t", ["Coding"], "component", [], "", True)
        e = contribute.contribution(self.r.paths, "x", "t", ["Writing – original draft"], "writing", [], "", True)
        self.assertEqual(e["credit_roles"], ["Writing - original draft"])

    def test_verification_entries(self):
        with self.assertRaisesRegex(ContributeError, "outcome"):
            contribute.verification(self.r.paths, "x", "a number", "number", "ecosystem.json", "fine", None, "", True)
        for name in ("Busy Rater", "Someone New"):
            with self.assertRaisesRegex(ContributeError, "contribution log instead"):
                contribute.verification(self.r.paths, name, "Results, para 2", "number", "ecosystem.json", "match", None, "", True)
        contribute.verification(self.r.paths, "Done Rater", "Results, para 2", "number", "ecosystem.json at abc1234",
                                "match", None, "", True)
        self.assertEqual(load_yaml(self.r.paths.verification_log)[0]["check_id"], "V-0001")

    def test_lead_decisions_come_from_the_lead_authors_own_git_identity(self):
        contribute.check_lead_identity(self.r.paths, LEAD, LEAD)
        with self.assertRaisesRegex(ContributeError, "not the lead author"):
            contribute.check_lead_identity(self.r.paths, "Done Rater", "Done Rater")
        with self.assertRaisesRegex(ContributeError, "git user"):
            contribute.check_lead_identity(self.r.paths, LEAD, "someone-else")


# ---------------------------------------------------------------- the example session, replayed

def example_session(r):
    """The story in fixtures/example-session.md, run with the real commands. Returns the branch run."""
    p = r.paths
    contribute.own(p, "DP-18", EXAMPLE)
    keep, keep_path = contribute.new_proposal(p, "DP-18", EXAMPLE)
    drop, drop_path = contribute.new_proposal(p, "DP-18", EXAMPLE, eliminate=True)
    fill(keep_path, {"Alternative": "Raise skills.min_support_firms from 3 to 5.",
                     "Rationale (contributor's own words, with precedent if any)": "(the contributor's words)",
                     "What we'd expect to see if the finding is fragile": "(the contributor's prediction)"})
    fill(drop_path, {"Alternative": "Lower skills.min_support_firms from 3 to 1.",
                     "Rationale (contributor's own words, with precedent if any)": "(the contributor's words)",
                     "What we'd expect to see if the finding is fragile": "(the contributor's prediction)"})
    contribute.propose(p, keep)
    contribute.propose(p, drop)
    logs.append_event(p, {"proposal_id": drop, "decision_point": "DP-18", "status": "rejected", "decided_by": LEAD,
                          "reason": "(the lead author's reason)"})
    logs.append_event(p, {"proposal_id": keep, "decision_point": "DP-18", "status": "accepted", "decided_by": LEAD,
                          "reason": "(the lead author's reason)"})
    b = contribute.new_branch(p, keep, ["skills.min_support_firms=5"])
    r.commit(keep_path, drop_path, os.path.join(p.branches, b["branch_id"] + ".yaml"))
    res = run_branch(b["branch_id"], EXAMPLE, p, example_build)
    contribute.new_interpretation(p, b["branch_id"], EXAMPLE)
    return res


class TestExampleSession(unittest.TestCase):
    def setUp(self):
        self.r = RealRepo()

    def tearDown(self):
        self.r.cleanup()

    def test_the_example_session_runs_and_logs_an_acceptance_a_run_and_an_elimination(self):
        res = example_session(self.r)
        ev = logs.load_events(self.r.paths)
        self.assertEqual([(e["proposal_id"], e["status"], e["results_seen"]) for e in ev],
                         [("P-0001", "proposed", "before"), ("P-0002", "proposed", "before"),
                          ("P-0002", "rejected", "before"), ("P-0001", "accepted", "before"), ("P-0001", "run", None)])
        self.assertEqual(contribute.point(self.r.paths, "DP-18")["owner"], EXAMPLE)
        self.assertTrue(os.path.exists(os.path.join(self.r.paths.interpretations, "BR-0001.md")))
        if os.path.exists(FIXTURE):
            self.assertIn(keyresults.table(res["diff"]), open(FIXTURE).read(),
                          "the fixture's key-results table no longer matches what the tools print")


# ---------------------------------------------------------------- the skill's files

COMMAND_RE = re.compile(r"pipeline/run\.py ([a-z][a-z-]*)")


def skill_texts():
    out = {}
    for d, _, files in os.walk(SKILL_DIR):
        for f in files:
            if f.endswith(".md") or f.endswith(".yaml"):
                path = os.path.join(d, f)
                out[os.path.relpath(path, ROOT)] = open(path).read()
    return out


@unittest.skipUnless(os.path.isdir(SKILL_DIR), "no .claude/skills/contribute in this checkout")
class TestSkillFiles(unittest.TestCase):
    def test_the_skill_loads_on_the_right_words(self):
        fm, _ = contribute.front(open(os.path.join(SKILL_DIR, "SKILL.md")).read())
        self.assertEqual(fm["name"], "contribute")
        for words in ("contribute to the", "co-author", "work on the paper"):
            self.assertIn(words, fm["description"])

    def test_every_command_the_skill_names_exists(self):
        known = set(cli.COMMANDS) | {"test", "build", "lca", "label"}
        for rel, text in skill_texts().items():
            for cmd in COMMAND_RE.findall(text):
                self.assertIn(cmd, known, f"{rel} names pipeline/run.py {cmd}, which doesn't exist")

    def test_every_repo_path_the_skill_names_exists(self):
        for rel, text in skill_texts().items():
            if rel.endswith("fixtures/example-session.md"):
                continue      # the example's files live in its throwaway repo
            for path in re.findall(r"`((?:paper|pipeline|\.claude)/[A-Za-z0-9_./-]+)`", text):
                if re.search(r"NNNN|nnnn|-nn\b|\bNN\b|<|\*", path) or path in LOCKED_PATHS_FLOOR + ("paper/multiverse/runs/",):
                    continue      # placeholders, the study's reserved paths, and the git-ignored run folders
                self.assertTrue(os.path.exists(os.path.join(ROOT, path.rstrip("/"))), f"{rel} names {path}")

    def test_the_fixture_is_labelled_and_shows_the_three_required_events(self):
        text = open(FIXTURE).read()
        self.assertIn("EXAMPLE SESSION", text.splitlines()[0])
        self.assertIn("invented", text[:2000])
        for needle in ("DP-18", "status: proposed", "status: accepted", "status: run", "status: rejected"):
            self.assertIn(needle, text)
        self.assertRegex(text, r"status: rejected[\s\S]{0,400}results_seen: before")

    def test_in_the_fixture_every_written_contribution_is_the_contributors_own_typing(self):
        text = open(FIXTURE).read()
        turns = re.findall(r"^\*\*Example Contributor:\*\*(.*?)(?=^\*\*[A-Z][^*]*:\*\*|^#|\Z)", text, re.S | re.M)
        said = " ".join(" ".join(t.split()) for t in turns).replace("> ", "")
        blocks = re.findall(r"~~~markdown\n(---\n.*?)~~~", text, re.S)
        self.assertGreaterEqual(len(blocks), 3, "the fixture should show both proposals and the interpretation")
        checked = 0
        for b in blocks:
            secs = contribute.sections(contribute.front(b)[1])
            for h in contribute.PROPOSAL_SECTIONS + contribute.INTERPRETATION_SECTIONS:
                if h in secs and contribute.written(secs[h]):
                    words = " ".join(contribute.written(secs[h]).split())
                    self.assertIn(words, said, f"'{h}' in the fixture isn't something the contributor typed")
                    checked += 1
        self.assertGreaterEqual(checked, 9)


if __name__ == "__main__":
    unittest.main()
