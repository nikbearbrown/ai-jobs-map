"""BR-0000, run through the branch runner's guarded path, reproduces the main build exactly (apart from the run
time). Needs the real inputs, which exist only on the Mac that holds the job snapshots, and two full builds, so it
runs only with `python3 -I pipeline/run.py test --full`."""
import os
import shutil
import tempfile
import unittest

from pipeline.multiverse import overrides, provenance
from pipeline.multiverse.common import Paths, load_json, load_yaml
from pipeline.multiverse.compare import compare_trees, summary
from pipeline.multiverse.logs import utc_now
from pipeline.multiverse.runner import execute, jobs_map_analysis

INPUT_KEYS = ("live_collection", "text_snapshot_dir", "onet_title_map", "companies_csv", "directory_json", "lca_matched_cache")


@unittest.skipUnless(os.environ.get("AI_JOBS_MAP_FULL_TESTS") == "1", "full rebuild: run `python3 -I pipeline/run.py test --full`")
class TestDefaultBranchReproducesMain(unittest.TestCase):
    def test_br_0000_outputs_equal_a_main_build_from_the_same_commit(self):
        from pipeline.ai_jobs_map import build
        paths = Paths()
        cfg = load_json(paths.config)
        missing = [k for k in INPUT_KEYS if not os.path.exists(cfg["inputs"][k])]
        if missing:
            self.skipTest(f"inputs not on this machine: {missing}")
        tmp = tempfile.mkdtemp(prefix="mv-reproduce-")
        try:
            main_out = os.path.join(tmp, "main")
            self.assertEqual(build.main(out_dir=main_out, private_outputs=False), 0)     # the main build, config file as is
            paths.runs = os.path.join(tmp, "runs")
            g = {"branch": overrides.load_branch(paths, "BR-0000"), "base_cfg": cfg, "code": provenance.code_state(paths.root),
                 "kr_spec": load_yaml(paths.key_results)}
            run_dir, prov, kr = execute(paths, g, jobs_map_analysis, "test", utc_now())
            self.assertEqual(prov["status"], "ok")
            self.assertEqual(prov["effective_config_sha256"], build.config_sha256(cfg))
            res = compare_trees(main_out, os.path.join(run_dir, "outputs"), mask=("computed_at",))
            self.assertFalse(res["different"] or res["only_in_a"] or res["only_in_b"], summary(res))
            self.assertGreater(len(res["identical"]), 700)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
