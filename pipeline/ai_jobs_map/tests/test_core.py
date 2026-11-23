import random
import unittest

from pipeline.ai_jobs_map import core
from pipeline.ai_jobs_map.validate import validate
import os

SCHEMAS = os.path.join(os.path.dirname(__file__), "..", "schemas")


class TestW(unittest.TestCase):
    def test_w_counts_cooccurrence_with_any_seed(self):
        roles = {1: {"machine learning", "python"}, 2: {"python", "sql"}, 3: {"deep learning", "python"}, 4: {"sql"}}
        w = core.compute_w(roles, ["machine learning", "deep learning"])
        self.assertAlmostEqual(w["python"], 2 / 3)   # 3 roles need python, 2 of them also need a seed
        self.assertEqual(w["sql"], 0.0)
        self.assertEqual(w["machine learning"], 1.0)  # a seed co-occurs with itself

    def test_w_ignores_roles_without_the_skill(self):
        w = core.compute_w({1: {"a"}, 2: {"b", "seed"}}, ["seed"])
        self.assertEqual(w["a"], 0.0)
        self.assertEqual(w["b"], 1.0)


class TestOmega(unittest.TestCase):
    def test_mean_of_w(self):
        self.assertAlmostEqual(core.omega({"a", "b"}, {"a": 0.2, "b": 0.4}), 0.3)

    def test_skills_without_w_are_skipped(self):
        self.assertAlmostEqual(core.omega({"a", "zzz"}, {"a": 0.5}), 0.5)

    def test_too_few_skills_gives_none(self):
        self.assertIsNone(core.omega({"a", "b"}, {"a": 0.5, "b": 0.1}, min_skills=3))

    def test_signal_types_follow_the_rules(self):
        rx = {"builds": core.term_regex(["pytorch"]), "integrates": core.term_regex(["rag"]), "uses_tools": core.term_regex(["copilot"])}
        self.assertTrue(core.signal_types("train in pytorch", 0.3, 0.1, rx)["builds"])
        self.assertFalse(core.signal_types("train in pytorch", 0.05, 0.1, rx)["builds"])        # builds needs omega above threshold
        self.assertTrue(core.signal_types("ship rag features", 0.05, 0.1, rx)["integrates"])
        self.assertTrue(core.signal_types("use copilot daily", 0.02, 0.1, rx)["uses_tools"])
        self.assertFalse(core.signal_types("use copilot daily", 0.5, 0.1, rx)["uses_tools"])     # AI-related roles are not tool users
        self.assertFalse(core.signal_types("fragrance", 0.5, 0.1, rx)["integrates"])              # word boundary: 'rag' inside a word


class TestDedup(unittest.TestCase):
    def test_requisition_tokens_and_case_collapse(self):
        pat = r"\(?\b(?:r|req|jr|job)?[-# ]?\d{4,}\b\)?|#\d+"
        a = core.role_key("f", "Data Scientist (R12345)", ["Boston, MA"], None, pat)
        b = core.role_key("f", "data scientist", ["Boston, MA "], None, pat)
        self.assertEqual(a, b)

    def test_level_words_are_kept(self):
        self.assertNotEqual(core.role_key("f", "Senior Engineer", ["X"]), core.role_key("f", "Engineer", ["X"]))

    def test_location_order_and_remote_variants(self):
        self.assertEqual(core.norm_location_set(["B", "A"]), core.norm_location_set(["A", "B"]))
        self.assertEqual(core.norm_location_set(["Remote - US"]), core.norm_location_set(["Remote (United States)"]))

    def test_requirements_hash_separates_roles(self):
        self.assertNotEqual(core.role_key("f", "Engineer", ["X"], "h1"), core.role_key("f", "Engineer", ["X"], "h2"))

    def test_relisting_needs_a_new_id_after_the_old_one_closed(self):
        base = {"firm": "f", "title": "t", "locs": ("x",), "hash": "h"}
        ps = [dict(base, source_id="1", first_seen="2026-10-25", last_seen="2026-10-30"),
              dict(base, source_id="2", first_seen="2026-11-05", last_seen="2026-11-10")]
        self.assertEqual(core.relisted_roles(ps), 1)
        overlap = [dict(base, source_id="1", first_seen="2026-10-25", last_seen="2026-11-30"),
                   dict(base, source_id="2", first_seen="2026-11-05", last_seen="2026-11-10")]
        self.assertEqual(core.relisted_roles(overlap), 0)
        self.assertEqual(core.relisted_roles([dict(p, hash=None) for p in ps]), 0)


class TestRequirementText(unittest.TestCase):
    CFG = {"heading_max_chars": 70, "drop_heading_patterns": ["about (us|the company)", "benefits?\\b"],
           "keep_heading_patterns": ["requirement", "what you('ll| will) do"]}

    def test_keeps_only_requirement_sections(self):
        blocks = ["About us", "We are great.", "What you'll do", "Build models.", "Requirements", "Python.", "Benefits", "Free lunch."]
        kept, sectioned = core.requirement_blocks(blocks, self.CFG)
        self.assertTrue(sectioned)
        self.assertIn("Build models.", kept)
        self.assertIn("Python.", kept)
        self.assertNotIn("We are great.", kept)
        self.assertNotIn("Free lunch.", kept)

    def test_curly_apostrophes_and_about_the_role_are_kept(self):
        import json
        cfg = json.load(open(os.path.join(os.path.dirname(__file__), "..", "config", "config.json")))["requirements_text"]
        blocks = ["About Acme", "We are great.", "About the Role", "Own the roadmap.", "What You\u2019ll Do", "Ship features.",
                  "Required", "SQL.", "US Salary Range", "$100k.", "Data Privacy", "We keep your data."]
        kept, sectioned = core.requirement_blocks(blocks, cfg)
        self.assertTrue(sectioned)
        self.assertEqual([b for b in kept if b.endswith(".")], ["Own the roadmap.", "Ship features.", "SQL."])
        kept, _ = core.requirement_blocks(["About Toast", "We serve restaurants.", "A day in the life (Responsibilities)", "Open accounts.",
                                           "Do you have the right ingredients? (Requirements)", "Sales experience.", "Benefits", "Lunch."], cfg)
        self.assertEqual([b for b in kept if b.endswith(".")], ["Open accounts.", "Sales experience."])

    def test_repeated_firm_blocks_are_dropped(self):
        posts = [["Tagline we repeat.", f"Unique {i}."] for i in range(6)]
        rep = core.repeated_blocks(posts, 0.3, 5)
        kept, _ = core.requirement_blocks(posts[0], self.CFG, rep)
        self.assertEqual(kept, ["Unique 0."])

    def test_ngrams_respect_stopwords_and_aliases(self):
        g = core.ngrams_of_text("Experience with ML and LLMs, plus Python and deep learning systems.", 3, {"ml": "machine learning", "llms": "large language models"}, {},
                                ["machine learning", "large language models", "deep learning"])
        self.assertIn("deep learning", g)
        self.assertNotIn("learning systems", g)      # no fragment of a seed survives
        self.assertNotIn("large language", g)
        self.assertIn("machine learning", g)
        self.assertIn("large language models", g)
        self.assertIn("python", g)
        self.assertNotIn("experience", g)
        self.assertNotIn("with ml", g)


class TestTiers(unittest.TestCase):
    def test_similarity_bounds(self):
        self.assertAlmostEqual(core.js_similarity({"a": 1.0}, {"a": 1.0}), 1.0)
        self.assertAlmostEqual(core.js_similarity({"a": 1.0}, {"b": 1.0}), 0.0)

    def test_cutoff_and_assignment(self):
        curve = [{"roles_from": 5, "firms": 10, "median_similarity": 0.5}, {"roles_from": 20, "firms": 10, "median_similarity": 0.8},
                 {"roles_from": 50, "firms": 10, "median_similarity": 0.9}, {"roles_from": 100, "firms": 10, "median_similarity": 0.905},
                 {"roles_from": 150, "firms": 10, "median_similarity": 0.91}]
        cut, plateau, _ = core.choose_cutoff(curve, 100, 0.02, 0.01, 20)
        self.assertEqual(cut, 50)
        self.assertEqual(core.assign_tier(49, cut), "B")
        self.assertEqual(core.assign_tier(50, cut), "A")

    def test_curve_is_deterministic(self):
        firms = {f"f{i}": random.Random(i).choices("abc", k=10 + i) for i in range(30)}
        bins = [[5, 19], [20, 39], [40, 100]]
        self.assertEqual(core.stability_curve(firms, bins, 20, 7), core.stability_curve(firms, bins, 20, 7))


class TestExposureRollup(unittest.TestCase):
    def test_role_weighted_mean_and_left_out(self):
        score, used, left = core.exposure_rollup(["15-1252", "15-1252", "43-4051", None, "99-9999"], {"15-1252": 0.8, "43-4051": 0.2})
        self.assertAlmostEqual(score, (0.8 + 0.8 + 0.2) / 3)
        self.assertEqual((used, left), (3, 2))

    def test_no_data_gives_none(self):
        self.assertEqual(core.exposure_rollup([None], {}), (None, 0, 1))


class TestSectorAndNames(unittest.TestCase):
    B = {"52": ("financial-services", "Financial Services"), "524114": ("health-care-delivery", "Health"), "5415": ("it-services", "IT")}

    def test_longest_prefix_wins(self):
        self.assertEqual(core.naics_bucket("524114", self.B)[0], "health-care-delivery")
        self.assertEqual(core.naics_bucket("522320", self.B)[0], "financial-services")
        self.assertEqual(core.naics_bucket("999999", self.B)[0], None)

    def test_employer_names_normalise(self):
        self.assertEqual(core.norm_employer("Acme, Inc."), core.norm_employer("ACME INC"))
        self.assertEqual(core.norm_employer("Acme Corporation"), "acme")


class TestSchemas(unittest.TestCase):
    def test_not_measured_needs_a_reason(self):
        s = os.path.join(SCHEMAS, "common.schema.json")
        ok = {"status": "not_measured", "reason_code": "no-source", "reason": "No data."}
        from pipeline.ai_jobs_map.validate import _errs, _load
        node = _load(s)["$defs"]["not_measured"]
        self.assertEqual(_errs(ok, node, os.path.abspath(s), "$"), [])
        self.assertTrue(_errs({"status": "not_measured"}, node, os.path.abspath(s), "$"))


if __name__ == "__main__":
    unittest.main()
