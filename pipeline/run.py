"""Entry point that works under `python3 -I` (isolated mode adds no path): puts the repo root on sys.path explicitly.

    python3 -I pipeline/run.py lca      # extract matching LCA rows (slow, ~1 GB of xlsx)
    python3 -I pipeline/run.py build    # derive everything into data/ai-job-map/v1
    python3 -I pipeline/run.py test     # unit tests
    python3 -I pipeline/run.py label    # local labeling page for the review sample (127.0.0.1:8794)
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
if cmd == "lca":
    from pipeline.ai_job_map import lca
    sys.exit(lca.main())
elif cmd == "build":
    from pipeline.ai_job_map import build
    sys.exit(build.main())
elif cmd == "label":
    from pipeline.ai_job_map import label
    sys.exit(label.main(sys.argv[2:]))
elif cmd == "test":
    import unittest
    suite = unittest.defaultTestLoader.discover(os.path.join(ROOT, "pipeline", "ai_job_map", "tests"), top_level_dir=ROOT)
    sys.exit(0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1)
else:
    sys.exit(f"unknown command {cmd}")
