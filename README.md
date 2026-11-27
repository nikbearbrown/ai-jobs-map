# AI Jobs Map

**The data and the paper behind the AI jobs map.**

[See the map](https://jobs.humanitarians.ai/ecosystem) · [Read the methods draft](paper/manuscript.md) · [Help with the paper](paper/CONTRIBUTING-paper.md)

**We're inviting collaborators.** Review one claim, check a source, or take on one of the tasks listed below. You don't need to review the whole paper to help. To join, follow [Getting started](paper/CONTRIBUTING-paper.md#getting-started) in the contributor guide.

The data and the paper behind the AI jobs map: which organizations hire for AI, what kind of AI work their roles involve, and what their visa filings show. The map itself is shown at [jobs.humanitarians.ai/ecosystem](https://jobs.humanitarians.ai/ecosystem). This repo builds the data behind it and holds the paper that studies it.

## Abstract

*Working abstract for the rough methods manuscript. It reports no study results.*

This paper studies how Boston-area organizations use and present AI, using the data behind the AI jobs map: job postings, H-1B wage filings and O*NET titles. Human raters classify firms from evidence packets under a written codebook. We then test how well language models and a simple co-occurrence baseline reproduce those human classifications, and we examine agreement among raters, calibration, and errors that rest on boilerplate text. Because many analytic choices could change the picture, the paper runs a multiverse analysis over 57 registered decision points. Each one is owned by a contributor who proposes alternatives and interprets what changed. The analysis plan is to be preregistered before results are seen.

## Where the draft is

Read the [rough methods manuscript](paper/manuscript.md) and [silent critique](critiq-output/ai-jobs-map-author-review.md). The [contributor guide](paper/CONTRIBUTING-paper.md) and [decision registry](paper/multiverse/decision_points.yaml) remain the study references.

## What needs to be done

- Draft the codebook and review the sector taxonomy.
- Rate the pilot set of firms, then the main round.
- Draft the preregistration before any results are seen.
- Take ownership of the 57 decision points, one contributor each.
- Build the baseline, run the model evaluation and the agreement analysis.
- Write the sections of the paper.

Every task is listed in section 3 of the contributor guide.

## How to contribute

Start with [Getting started](paper/CONTRIBUTING-paper.md#getting-started) in the [contributor guide](paper/CONTRIBUTING-paper.md): read the draft or plan, pick one thing to do, and email Nik to be added as a collaborator. The guide lists each kind of contribution with where to start and what to send, the rules for this repo, how to submit, and how credit and authorship work.

- **A quick contribution:** open an issue about one claim, source or decision. You don't need to review the whole paper.
- **To become an author:** take on a component of the work, help write the paper, approve the final version and agree to be accountable for it. The guide explains each step.

In Claude Code, typing `/contribute` in this repo walks you through the guide.

**Raters:** do not use AI tools while rating, and finish your ratings before looking at any model output or analysis.

## What is in this repo

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
