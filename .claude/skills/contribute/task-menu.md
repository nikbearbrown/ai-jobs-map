# Task menu, by what each task reveals

Every task from `paper/CONTRIBUTING-paper.md` section 3, grouped by what doing it would show. Offer only the groups `status` allows. **Component** tasks count toward authorship (Yale criterion 1); **Writing** tasks count toward criterion 2; rating alone earns **acknowledgment**.

## Reveals nothing: open to everyone, including raters whose ratings aren't complete

| Task | CRediT role | Counts as | Notes for the skill |
|---|---|---|---|
| Own a decision point: research and proposals | Methodology, Formal analysis | Component | The default for a first-time author. Research and proposals are open to everyone; running a branch and interpreting it need a cleared roster entry |
| Codebook drafting | Methodology | Component | Before the pilot only. After the pilot, a change goes through the classification system's versioning (hard rule 7) |
| Domain seed vocabularies | Methodology | Component | The contributor drafts the terms; you ask questions |
| Related work | Writing - original draft | Writing | Point to sources; they read and write |
| Evidence-packet quality checks | Data curation, Validation | Component | Packets hold ad text, never model outputs. They don't exist yet |
| Entity-resolution review | Data curation | Component | Needs a review file from the lead author holding only the name matches. Don't open AI jobs map outputs for someone who isn't cleared |
| Lifecycle fact checks | Data curation, Validation | Component | Public sources (incorporation dates, Form D, public status) for a sample of firms the lead author gives them. Recorded in the contribution log |
| Preregistration draft | Methodology, Writing - original draft | Component and writing | Before results are seen. Never shows the test set |
| Methods page | Writing - original draft | Writing | Methods only, no results |

## Needs a cleared roster entry (`status` says "may see results")

| Task | CRediT role | Counts as | Notes for the skill |
|---|---|---|---|
| Own a decision point: run branches and interpret them | Methodology, Formal analysis | Component | `branch`, `new-interpretation` (`new-branch` itself shows nothing) |
| Sector taxonomy review | Methodology | Component | Shows the rule-based sector buckets for named firms |
| Coverage analysis | Formal analysis | Component | Compares the collection with BLS metro data |
| Filing propensity | Formal analysis | Component | Visa-filing shares by size, age and sector |
| Reproducibility run | Validation | Component | The AI jobs map and the multiverse only. Recorded with `log-verification` |
| Number audit | Validation | Component | Job map and multiverse numbers only; the classifier evaluation's numbers are checked through its own process. One `log-verification` entry per item |
| Paper figures | Visualization | Component | Job map and multiverse figures only. Confusion matrices, agreement and calibration plots come from the classifier evaluation |
| Map and firm-page views | Visualization | Component | Shows classifications |
| Section drafts with results | Writing - original draft | Writing | Critique by questions only |
| Substantive revision | Writing - review & editing | Writing | Critique by questions only |

## The classification system's own process: explain and point to the lead author, never run or show

Prompt development (development set only), baseline implementation, agreement analysis, model evaluation, calibration analysis, the error audit, and the figures and numbers that come from them. Also pilot disagreement review and adjudication: both turn on how particular firms should be rated, which this skill never discusses (hard rule 3). These touch the confirmatory study's machinery, so this skill doesn't run them or show their outputs (hard rule 1).

## Refused: no help of any kind

| Request | Why, in one line |
|---|---|
| Pilot or main-round rating, or classifying any firm | Ratings must be the rater's own judgment, made without AI: the study compares models with human judgment |
| Discussing how a particular firm should be rated | Same reason; it would shape the rating |
| Labeling the AI jobs map's 50-role review sample, or showing its scores | The sample checks the pipeline's labels against a person's reading; AI help would check the pipeline against AI |
| Writing, outlining or rewording a rationale, prediction, interpretation, task description or section | The contributor does the thinking: it's their learning, and their authorship has to be real |
| Accepting, rejecting or adopting a proposal, or suggesting the decision | The group decides, with the lead author deciding |
| Running or showing anything on a locked point, the test set or the preregistered evaluation | The confirmatory study is off-limits |
| Editing the roster, or the codebook after the pilot | Only the lead author edits the roster; the codebook changes through versioning |
| Showing results to someone the roster doesn't clear | Their ratings would no longer be blind |
