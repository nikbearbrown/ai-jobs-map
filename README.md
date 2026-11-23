# AI Jobs Map

The data and the paper behind the AI jobs map: which organizations hire for AI, what kind of AI work their roles involve, and what their visa filings show. The map itself is shown at [jobs.humanitarians.ai/ecosystem](https://jobs.humanitarians.ai/ecosystem). This repo builds the data behind it and holds the paper that studies it.

* **`pipeline/ai_jobs_map/`** builds firm records, ecosystem aggregates and the employer crosswalk from job postings, H-1B wage filings (LCA) and O*NET titles. Python standard library only. Every output is checked against the schemas in `pipeline/ai_jobs_map/schemas/`.
* **`pipeline/multiverse/`** is the paper's branch runner: each contributor-proposed alternative to an analytic choice runs as its own branch, with full provenance.
* **`paper/`** holds the contributor guide ([CONTRIBUTING-paper.md](paper/CONTRIBUTING-paper.md)), the roster, the decision-point registry and the logs.
* **`.claude/skills/contribute/`** is the `/contribute` skill. In Claude Code, a contributor types `/contribute`, or says they want to work on the paper, and it guides them through owning a decision point under the paper's rules.

## Running it

```bash
python3 -I pipeline/run.py build    # derive everything into data/ai-jobs-map/v1
python3 -I pipeline/run.py test     # unit tests (add --full for the rebuild check)
python3 -I pipeline/run.py label    # local labeling page for the review sample, http://127.0.0.1:8794
python3 -I pipeline/run.py lca      # re-extract matching LCA rows (slow)
```

## What is not in this repo

* **Inputs.** The job-posting collection, the ad-text snapshot and the DOL files live outside the repo. Their absolute paths are in `pipeline/ai_jobs_map/config/config.json`.
* **Ad text.** It is never committed. The labeling packet is written outside the repo too.
* **Generated outputs** (`data/ai-jobs-map/v1/`), **branch runs** (`paper/multiverse/runs/`) and **phase review notes** (`notes/`) are local only.

## History

The pipeline and the paper's tools started on the `feat/ai-job-map-paper` branch of the jobs.humanitarians.ai repo and moved here, with their commit history, on 2026-11-23, when the project was renamed from "AI job map" to "AI jobs map".
