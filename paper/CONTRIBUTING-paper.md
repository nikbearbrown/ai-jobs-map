# Contributing to the AI Jobs Map Paper

## Executive summary

* **What this is.** The guide for anyone who wants to contribute to the AI jobs map paper: how credit works, what every author is expected to do, and every task the paper needs done.
* **Who earns authorship.** We follow Yale's four criteria (section 1). Rating firms earns acknowledgment. Authorship also needs a component task, help writing the paper, approval of the final version and accountability for it.
* **Rules that protect the study** (section 4). No AI tools while rating. Raters see no model outputs or analysis until their ratings are marked complete.
* **The most open component task** is owning a decision point in the multiverse analysis (section 6). You research one analytic choice, propose alternatives in your own words, the group decides which run, and you interpret what changed.

This paper studies how Boston organizations use and present AI, built on the AI jobs map at jobs.humanitarians.ai/ecosystem. It needs contributors, not just raters. This guide explains how credit works, what we expect from every author, and every task the paper needs done.

## Getting started

Follow these steps in order. Steps 1 to 3 get you access. Steps 4 to 9 take one contribution from start to finish.

1. **Read first.** Read the [README](../README.md), then the rest of this guide. The [rough methods manuscript](manuscript.md) reports no results. Allow about an hour. You don't need to follow every detail, but you should know what the paper claims and what it does not.
2. **Choose one thing to do.** Pick one row from the table under [3. Tasks](#3-tasks), and narrow it to one section, one source, one case or one result. If you can't decide, ask to own a decision point (section 6).
3. **Email Nik** at bear@bearbrown.co with the subject "AI Jobs Map paper: contributor". Include:
   - your name and your GitHub username;
   - the contribution you chose and what exactly you will look at;
   - whether you hope to become an author or want to help without authorship.

   Nik will add you to the repository as a collaborator. GitHub then emails you an invitation, which you must accept within seven days.
4. **Claim the work.** Check the [open issues](https://github.com/nikbearbrown/ai-jobs-map/issues) to make sure nobody is already doing it. Then [open an issue](https://github.com/nikbearbrown/ai-jobs-map/issues/new) that says what you are taking on, and assign it to yourself.
5. **Make a branch.** Clone the repository and create a branch named `your-name/short-description`, for example `priya/dp-25-ai-threshold`. Do not commit to `main`. If you don't use git, edit the file on GitHub with the pencil button and choose "Create a new branch" when you save.
6. **Do the work.** Follow what the table asks you to send for the row you chose. Keep one branch to one piece of work.
7. **Open a pull request.** Say what you changed, how you checked it, and where you used an AI tool. Write "Closes #" and your issue's number so the two are linked, and request a review from `nikbearbrown`.
8. **Respond to the review.** Nik or another author will comment. Revise on the same branch until it is agreed, and it will be merged.
9. **Present your work.** Come to Nik's Tuesday meeting or his office hours with a short, clear presentation of what you have done. Cover what you set out to do, what you did, what you found and the evidence for it, and what you will do next or need help with. Do this each time you attend, even when the work is unfinished. Nik will send the meeting details when he adds you.
10. **Keep your record.** Your issues and pull requests are the record of what you did. If you hope to be an author, keep a list of them, because the paper's contribution statement is drawn from it.
11. **Take the next step.** Pick another piece of work. If you want to be an author, tell Nik early and read [Credit and what we expect from authors](#1-how-credit-works).

You can also help without access. Anyone can open an issue on this repository without emailing first.

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
| Venue recommendation | Recommend a journal that fits the paper and that Northeastern covers in full (section 7). Every contributor does this once | Project administration | Acknowledgment alone; supports authorship when combined with a component |

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

**With Claude Code, run /contribute.** It walks you through these steps, runs the tools, and asks you questions about your drafts. It never writes your rationale or interpretation, never helps with rating, and never approves anything. Without Claude Code, the same steps use `python3 -I pipeline/run.py` commands, listed in `pipeline/multiverse/contribute.py`.

**Raters: finish your ratings first.** Branch results are results. Until the [roster](roster.yaml) marks your ratings complete, you can research decision points and write proposals, but not run branches or interpret them. Until then, also stay out of the run folders, the interpretations, other people's proposals, the decision log's reasons and the key results' notes, which hold the default values. `python3 -I pipeline/run.py key-results` lists the key results without them.

## 7. Recommend a journal Northeastern covers in full

Every contributor is asked to do this once. Northeastern's library has agreements with publishers that pay the open-access publishing fee for its authors. The library's page says the agreements are "open to all current Northeastern faculty, students and staff who are corresponding authors." Nik is the corresponding author on this paper, so they apply. Your job is to find a journal that is a good fit for this paper and whose fee is covered in full.

1. **Know the paper.** Read the abstract and the draft, or the plan if there is no draft yet. Note the field, the method, the kind of article (research, review, tool, dataset) and its likely length.
2. **Open the library's list.** Read [Open access publishing at Northeastern](https://library.northeastern.edu/resource_discovery/open-access-publishing/) and use its journal search, [SciFree for Northeastern](https://search.scifree.se/northeastern).
3. **Keep only full coverage.** Some agreements pay 100% of the fee and some only give a discount. A discount does not count. Some publishers also cap the number of articles they cover in a year, so note any cap the page states.
4. **Shortlist three journals** and check each one on the publisher's own site:
   - **Scope:** does the journal's aims and scope cover this paper's question and method?
   - **Article type:** does the journal accept this kind of article, and does the agreement cover that type?
   - **Precedent:** two or three recent papers in the journal that are close to this one, with links.
   - **Preprints and public drafts:** this paper's draft is in a public repository. Does the journal allow that, and is its review double-blind?
   - **Practical limits:** length limit, typical time to a first decision, and any data or code requirements.
5. **Recommend one journal and a runner-up.** [Open an issue](https://github.com/nikbearbrown/ai-jobs-map/issues/new) titled "Venue recommendation: " and the journal's name. Give your reasons, the links you used and the date you checked each fact.

Confirm coverage on the library's page or the publisher's page yourself. Do not rely on memory or on an AI tool's answer, because the agreements and their caps change.
