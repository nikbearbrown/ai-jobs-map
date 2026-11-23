"""Entry point that works under `python3 -I` (isolated mode adds no path): puts the repo root on sys.path explicitly.

    python3 -I pipeline/run.py lca      # extract matching LCA rows (slow, ~1 GB of xlsx)
    python3 -I pipeline/run.py build    # derive everything into data/ai-jobs-map/v1
    python3 -I pipeline/run.py test     # unit tests (add --full on this Mac to also rebuild and check BR-0000 = main)
    python3 -I pipeline/run.py check-registry               # the decision-point registry agrees with the config
    python3 -I pipeline/run.py branch BR-0001 [--as NAME]   # run one multiverse branch (paper/multiverse/)
    python3 -I pipeline/run.py log-event --proposal P-0001 ...   # append a decision event (proposed, accepted, ...)
    python3 -I pipeline/run.py status --as NAME             # what the /contribute skill calls: see pipeline/multiverse/contribute.py
    python3 -I pipeline/run.py label    # local labeling page for the review sample (127.0.0.1:8794)
"""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
if cmd == "lca":
    from pipeline.ai_jobs_map import lca
    sys.exit(lca.main())
elif cmd == "build":
    from pipeline.ai_jobs_map import build
    sys.exit(build.main())
elif cmd == "label":
    from pipeline.ai_jobs_map import label
    sys.exit(label.main(sys.argv[2:]))
elif cmd == "test":
    import unittest
    if "--full" in sys.argv[2:]:
        os.environ["AI_JOBS_MAP_FULL_TESTS"] = "1"
    suite = unittest.TestSuite(unittest.defaultTestLoader.discover(os.path.join(ROOT, "pipeline", d, "tests"), top_level_dir=ROOT)
                               for d in ("ai_jobs_map", "multiverse"))
    sys.exit(0 if unittest.TextTestRunner(verbosity=1).run(suite).wasSuccessful() else 1)
elif cmd in ("check-registry", "branch", "log-event", "status", "points", "key-results", "own", "new-proposal", "propose", "new-branch",
             "new-interpretation", "log-contribution", "log-verification"):
    from pipeline.multiverse import cli
    sys.exit(cli.main(cmd, sys.argv[2:]))
else:
    sys.exit(f"unknown command {cmd}")
