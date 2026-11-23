"""The Phase 2 parameters: each default behaves exactly as the hard-coded rule did, and the implemented variants
do what the registry says."""
import json
import os
import unittest

from pipeline.ai_job_map import build, core, soc

CONFIG = os.path.join(os.path.dirname(__file__), "..", "config", "config.json")
REGISTRY = os.path.join(os.path.dirname(__file__), "..", "..", "..", "paper", "multiverse", "decision_points.yaml")


def load_registry(test):
    try:
        import yaml
    except ImportError:
        test.skipTest("PyYAML not installed (only the multiverse tools need it)")
    if not os.path.exists(REGISTRY):
        test.skipTest("no decision-point registry in this checkout")
    return yaml.safe_load(open(REGISTRY))


class TestDefaultsMatchTheOldConstants(unittest.TestCase):
    def setUp(self):
        self.cfg = json.load(open(CONFIG))

    def test_config_values_equal_the_code_defaults(self):
        c = self.cfg
        self.assertEqual(c["dedup"]["trailing_employment_suffix"], core.TRAILING_EMPLOYMENT_SUFFIX)
        self.assertEqual(c["dedup"]["keep_chars"], core.TITLE_KEEP_CHARS)
        self.assertEqual(c["dedup"]["remote_pattern"], core.REMOTE_PATTERN)
        self.assertEqual(tuple(c["dedup"]["role_key_fields"]), core.ROLE_KEY_FIELDS)
        self.assertEqual(set(c["skills"]["stoplist"]), core.STOP)
        self.assertEqual(c["skills"]["token_pattern"], core.TOKEN.pattern)
        self.assertEqual(c["skills"]["segment_pattern"], core.SEGMENT.pattern)
        self.assertEqual(set(c["soc"]["level_edge_words"]), soc.LEVEL_EDGE)
        self.assertEqual(tuple(c["soc"]["mode_words"]), soc.MODE_WORDS)
        self.assertEqual(c["soc"]["cut_pattern"], soc.CUT_PATTERN)
        self.assertEqual(tuple(c["soc"]["accepted_statuses"]), soc.ACCEPTED_STATUSES)
        self.assertEqual(c["soc"]["min_tail_words"], soc.MIN_TAIL_WORDS)
        self.assertEqual(tuple(c["dynamics"]["relist_match_fields"]), core.RELIST_FIELDS)

    def test_the_mode_regex_is_the_old_one(self):
        self.assertEqual(soc.MODE.pattern, r"\b(remote|hybrid|onsite|on-site|in-office|full[- ]time|part[- ]time|per diem|prn|contract|temporary|temp)\b")

    def test_title_normaliser_built_from_config_matches_the_default(self):
        c = self.cfg["soc"]
        built = soc.make_norm_title(c["level_edge_words"], c["mode_words"], c["cut_pattern"])
        for t in ("Senior Software Engineer II - Remote", "Data Scientist, Payments", "Staff ML Engineer @ Acme", "Nurse (PRN)", "Full-time Analyst"):
            self.assertEqual(built(t), soc.norm_title(t))

    def test_the_current_config_is_implemented(self):
        build.check_implemented(self.cfg)


class TestVariants(unittest.TestCase):
    def test_unimplemented_variants_stop_the_build(self):
        cfg = json.load(open(CONFIG))
        cfg["ai_relatedness"]["omega_aggregate"] = "median"
        with self.assertRaises(ValueError):
            build.check_implemented(cfg)

    def test_seed_masking_off_lets_fragments_through(self):
        on = core.ngrams_of_text("large language models in production", 3, {}, {}, ["large language models"])
        off = core.ngrams_of_text("large language models in production", 3, {}, {}, ["large language models"], mask_seeds=False)
        self.assertIn("large language models", on)
        self.assertNotIn("large language", on)
        self.assertIn("large language", off)
        self.assertIn("large language models", off)

    def test_role_key_fields(self):
        a = core.role_key("f", "Data Scientist", ["Boston, MA"])
        b = core.role_key("f", "Data Scientist", ["Cambridge, MA"])
        self.assertNotEqual(a, b)
        self.assertEqual(core.role_key("f", "Data Scientist", ["Boston, MA"], fields=("firm", "title")),
                         core.role_key("f", "Data Scientist", ["Cambridge, MA"], fields=("firm", "title")))
        with self.assertRaises(ValueError):
            core.role_key("f", "x", [], fields=("title",))

    def test_remote_pattern_default_is_the_old_substring_rule(self):
        self.assertEqual(core.norm_location_set(["Remote - US", "remote (Canada)"]), ("remote:canada", "remote:us"))
        self.assertEqual(core.norm_location_set(["Anywhere"], remote_pattern="anywhere"), ("remote:any",))

    def test_relisting_gap(self):
        ps = [{"firm": "f", "title": "t", "locs": (), "hash": "h", "source_id": "1", "first_seen": "2026-10-25", "last_seen": "2026-10-30"},
              {"firm": "f", "title": "t", "locs": (), "hash": "h", "source_id": "2", "first_seen": "2026-11-03", "last_seen": "2026-11-10"}]
        self.assertEqual(core.relisted_roles(ps), 1)
        self.assertEqual(core.relisted_roles(ps, min_gap_days=4), 1)
        self.assertEqual(core.relisted_roles(ps, min_gap_days=5), 0)
        same_day = [dict(ps[0]), dict(ps[1], first_seen="2026-10-30")]
        self.assertEqual(core.relisted_roles(same_day), 0)
        self.assertEqual(core.relisted_roles(same_day, min_gap_days=0), 1)

    def test_tail_words(self):
        tm = soc.TitleMap.__new__(soc.TitleMap)
        tm.map, tm.extra, tm.norm, tm.min_tail_words = {"engineer": "17-2199.00", "software engineer": "15-1252.00"}, {}, soc.norm_title, 2
        self.assertEqual(tm.assign("payments software engineer"), "15-1252.00")
        self.assertIsNone(tm.assign("payments platform engineer"))   # a one-word tail is not enough by default
        tm.min_tail_words = 1
        self.assertEqual(tm.assign("payments platform engineer"), "17-2199.00")


class TestRegistryAgreesWithTheBuild(unittest.TestCase):
    def test_switch_variants_match_what_the_build_implements(self):
        reg = load_registry(self)
        switches = {prm["key"]: prm["variants"] for p in reg for prm in p["parameters"] if prm["form"] == "switch" and not p["locked"]}
        self.assertEqual(switches, build.IMPLEMENTED)

    def test_every_new_or_wired_key_is_read_by_the_build(self):
        reg = load_registry(self)
        src = open(build.__file__).read()
        for p in reg:
            for prm in p["parameters"]:
                if prm["origin"] != "existing":
                    leaf = prm["key"].split(".")[-1]
                    read = f'"{leaf}"' in src or f"'{leaf}'" in src or f'"{prm["key"]}"' in src   # IMPLEMENTED checks switches by full key
                    self.assertTrue(read, f"{p['id']} {prm['key']} is in the config but build.py never reads it")

    def test_the_build_hash_is_the_multiverse_canonical_hash(self):
        try:
            from pipeline.multiverse.common import canonical_sha256
        except ImportError:
            self.skipTest("PyYAML not installed")
        cfg = json.load(open(CONFIG))
        self.assertEqual(build.config_sha256(cfg), canonical_sha256(cfg))
