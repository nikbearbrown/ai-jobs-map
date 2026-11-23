# Contributing to the AI Jobs Map Paper

## Executive summary

* **What this is.** The guide for anyone who wants to contribute to the AI jobs map paper: how credit works, what every author is expected to do, and every task the paper needs done.
* **Who earns authorship.** We follow Yale's four criteria (section 1). Rating firms earns acknowledgment. Authorship also needs a component task, help writing the paper, approval of the final version and accountability for it.
* **Rules that protect the study** (section 4). No AI tools while rating. Raters see no model outputs or analysis until their ratings are marked complete.
* **The most open component task** is owning a decision point in the multiverse analysis (section 6). You research one analytic choice, propose alternatives in your own words, the group decides which run, and you interpret what changed.

This paper studies how Boston organizations use and present AI, built on the AI jobs map at jobs.humanitarians.ai/ecosystem. It needs contributors, not just raters. This guide explains how credit works, what we expect from every author, and every task the paper needs done.

## 1. How credit works

We follow Yale's authorship guidance:
https://provost.yale.edu/policies/academic-integrity/guidance-authorship-scholarly-or-scientific-publications

Under that guidance, an author has done **all four** of the following:

1. **Contributed to a component of the work.** Its conception, design, conduct, analysis, or interpretation of at least part of the results.
2. **Helped write the paper.** Drafted part of it, or revised it for intellectual content: substance, not just copyedits.
3. **Approved the final version** before submission.
4. **Agreed to be accountable** for the work, including helping resolve any questions about its accuracy or integrity.

Yale's guidance is explicit that some contributions, valuable as they are, do not by themselves make someone an author: helping collect or assemble data, or reviewing a finished manuscript to offer suggestions. People who contribute in those ways are named in the acknowledgments.

**What this means here.** Rating firms is essential, and every rater is acknowledged. To be an author, combine rating with at least one component task from section 3, plus the writing, approval and accountability steps. Most component tasks are open to anyone willing to take one on.

## 2. What we expect from every author

**Read the whole paper,** not just your section. You're putting your name on all of it.

**Think about it, then give feedback.** Look closely at the methods: does the design answer the question, and are the comparisons fair? Look at the visualizations: do they show what the text claims, and would a different figure show it better? Check that numbers in the text match the tables and figures.

**Suggest improvements when they matter.** Don't make a suggestion just to have made one. A reader who finds nothing to change and says so has done their job. A real problem, raised clearly with a proposed fix, is the most valuable thing an author can give.

**Sign off only when you can stand behind it.** Signing off means you understand the work, you agree with it, and you would answer a question about it. If something is wrong or unclear, say so before approval, not after publication.

## 3. Tasks

Each task lists its contributor role in the CRediT taxonomy, which most journals use for contribution statements. Tasks marked **Component** satisfy Yale criterion 1 when done substantively. Sign up for tasks; don't wait to be assigned.

### Study design and codebook

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Sector taxonomy review | Check the 16-bucket NAICS roll-up and application tags against real Boston firms; propose changes | Methodology | Component |
| Codebook drafting | Write definitions and edge-case rules for each bucket, tag and the insufficient-evidence label | Methodology | Component |
| Own a decision point | Research how prior work made one analytic choice, propose alternatives, run the accepted ones as branches, interpret what changed (section 6) | Methodology, Formal analysis | Component |
| Domain seed vocabularies | Draft core terms for each domain for the co-occurrence baseline | Methodology | Component |
| Pilot disagreement review | Analyze where pilot raters split and why; propose codebook revisions | Formal analysis, Methodology | Component |
| Adjudication | Resolve rater disagreements in the main round under the codebook | Validation | Component |

### Data

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Evidence packet quality checks | Spot-check packets: boilerplate removed, correct roles included, codes normalized | Data curation, Validation | Component |
| Entity resolution review | Check low-confidence name matches between visa filings and firms | Data curation | Component |
| Lifecycle fact checks | Verify incorporation dates, Form D filings and public status for a sample of firms | Data curation, Validation | Component |
| Coverage analysis | Compare our collection's occupation mix against BLS metro data; estimate what we miss | Formal analysis | Component |

### Rating

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Pilot rating | Rate the 50-firm pilot set | Investigation | Acknowledgment alone; supports authorship when combined with a component |
| Main-round rating | Rate assigned firms in the main round | Investigation | Same |

### Models and analysis

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Prompt development | Design and iterate classification prompts, on the development set only | Methodology, Software | Component |
| Baseline implementation | Build the co-occurrence domain classifier | Software | Component |
| Agreement analysis | Compute Krippendorff's alpha and the distribution of pairwise human agreement | Formal analysis | Component |
| Model evaluation | Compare models and baselines against human labels; stratify by firm size and recognizability | Formal analysis | Component |
| Calibration analysis | Reliability diagrams and recalibration on the calibration set | Formal analysis | Component |
| Error audit | Review the model's cited evidence and flag classifications built on boilerplate | Validation | Component |
| Filing propensity | Estimate the share of firms, by size, age and sector, that have filed for visas | Formal analysis | Component |

### Visualization

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Paper figures | Confusion matrices, agreement plots, calibration plots, sector treemap | Visualization | Component |
| Map and firm-page views | Propose and test how classifications and uncertainty appear on the site | Visualization | Component |

### Writing

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Related work | Summarize and position against prior firm-level AI measurement research | Writing – original draft | Writing |
| Section drafts | Draft data, methods, results, limitations or ethics sections | Writing – original draft | Writing |
| Preregistration draft | Help draft the analysis plan for OSF before results are seen | Methodology, Writing – original draft | Component and writing |
| Methods page | Write the public methods page for the site | Writing – original draft | Writing |
| Substantive revision | Revise any section for intellectual content | Writing – review & editing | Writing |

### Integrity checks

| Task | What it involves | CRediT role | Counts as |
|---|---|---|---|
| Reproducibility run | Re-run the pipeline from raw data and confirm the results reproduce | Validation | Component |
| Number audit | Check every number in the text against its table or figure, and every table against the code output | Validation | Component |

The number audit is worth doing carefully. Published papers, including well-known ones, have shipped with duplicated table panels and mislabeled figures. We'd rather catch ours ourselves.

## 4. Rules that protect the study

1. **No AI tools while rating.** Not ChatGPT, Claude, or anything else. The study measures models against human judgment, and AI-assisted ratings would quietly measure models against models. You confirm this at the start of each rating session.
2. **Disclose AI assistance everywhere else.** AI tools are fine for code and drafting outside of rating, but note where you used them. You remain accountable for everything you contribute.
3. **Category suggestions close after the pilot.** New categories are welcome during the pilot. After the main round starts, changes go into a new codebook version, and affected firms are re-rated.
4. **Finish your ratings before seeing model outputs or analysis.** Once you've seen how the model classified firms, your ratings can't be blind. The pipeline won't show you results until your ratings are marked complete.

## 5. How contributions are tracked

1. **Log your contributions** as you go, in the project's contribution log: what you did, when, and where it lives (commit, document, figure). The log becomes the paper's contribution statement.
2. **Authorship is discussed early,** as Yale recommends, and revisited as roles change. If you think your contribution merits authorship and it isn't reflected, raise it before the final draft.
3. **Final approval round.** Before submission, every author confirms in writing that they have read the full paper, agree with it, and accept accountability for it.
4. **Author order** follows contribution, with the lead author having done the central work. The contribution statement lists each author's CRediT roles.
5. **Everyone else is acknowledged by name,** including every rater, unless they ask not to be.

## 6. Decision points and the multiverse

Every analysis is built from choices: what counts as one role, how common a phrase must be to count as a skill, which towns make up the Boston area. Each choice that could reasonably have gone another way is a **decision point**. All of them are listed in the [registry](multiverse/decision_points.yaml). Owning one is the component task most open to a first-time author, because it shows how an analysis is built from choices and whether a result depends on them.

1. **Pick an open, unlocked decision point.** Locked points define the confirmatory study and can't be changed by a branch.
2. **Research how published work made the same choice.** "No precedent found" is an acceptable answer if you say where you looked.
3. **Propose alternatives in your own words,** one file per alternative, from the [proposal template](multiverse/templates/proposal.md). Write what you'd expect to see if the finding depends on this choice **before** anything runs. An alternative you expect to eliminate is welcome: say why.
4. **The group discusses, and the lead author decides.** Every decision goes in the [decision log](multiverse/decision_log.yaml), including every rejection and its reason.
5. **Accepted alternatives run as branches,** on the jobs map's descriptive outputs only, never on the study's test set or its preregistered evaluation. Each branch is compared with the default on the [key results](multiverse/key_results.yaml).
6. **You write the interpretation:** what changed, whether the finding held against what you predicted, and what it means for the claim.

**Cut for reasons, never for results.** An alternative is rejected only for a reason that doesn't depend on its result. Every branch that runs goes in the supplement, and a branch that flips a finding is reported as a flip whether or not it is adopted.

**Raters: finish your ratings first.** Branch results are results. Until the [roster](roster.yaml) marks your ratings complete, you can research decision points and write proposals, but not run branches or interpret them.
