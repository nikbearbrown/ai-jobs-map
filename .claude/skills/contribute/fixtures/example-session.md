# EXAMPLE SESSION: a fictional contributor owns DP-18

**This is an example, not a record.** "Example Contributor" and "Example Lead Author" are fictional. The commands are the real ones and their output is what they print, but they ran in a throwaway copy of the repo with a stand-in build, so **every number here is invented**. Nothing in this file is a result of the AI jobs map, and none of it is in the paper's logs.

It shows the path the `/contribute` skill guides: owning a decision point, two proposals (one accepted and run, one eliminated before any run), the interpretation, and five requests the skill declines. `pipeline/multiverse/tests/test_contribute.py` replays the same story with the real commands and checks that its key-results table matches the one below, and that every section the contributor "wrote" here is text the contributor typed.

Lines starting `$` are commands Claude ran. "(...)" marks output trimmed for length.

## Session 1: choosing a point and proposing

**Claude:** Welcome. What name will you sign your work with, and what do you hope to learn from contributing?

**Example Contributor:** Example Contributor. I finished my master's in data science, and I want to learn how a real analysis gets built, and how you know whether a result is solid.

**Claude:** That fits this paper well. First, how credit works. Under Yale's authorship guidance, an author does all four of these: contributes to a component of the work, helps write or substantively revise the paper, approves the final version, and accepts accountability for it. Rating firms is essential and earns acknowledgment, but on its own it isn't authorship. The details are in `paper/CONTRIBUTING-paper.md`. In these sessions I'll ask questions, point you to sources, critique your drafts and run the code. The thinking and the writing are yours. Let me check the roster.

```text
$ python3 -I pipeline/run.py status --as "Example Contributor"
Example Contributor: in paper/roster.yaml (contributor)
results: may see results. Example Contributor is cleared (contributor, rater with complete ratings)
owns: nothing yet
```

**Claude:** The roster lists you as a rater whose ratings are complete, so every task is open to you, including ones that show results. The menu is grouped by what each task reveals. For a first-time author I'd suggest owning a decision point: a choice in the analysis that could reasonably have gone another way. You research how others made it, propose alternatives, the group decides which to run, and you interpret what changed. It shows how an analysis is built from choices and whether a result depends on them, which is your second question. It's also a component task, which counts toward authorship.

**Example Contributor:** Let's do that.

```text
$ python3 -I pipeline/run.py points
DP-01  Counting unit (role key)  [now]
        now: firm + normalised title + normalised location set; text roles also split by a hash of the requirement text
DP-02  Title normalisation for deduplication  [now]
        now: lowercase; keep letters, digits, + and #; keep level words; drop requisition tokens (regex in config) and a trailing -ft or -pt
DP-03  Drop trailing -ft / -pt from titles  [now]
        now: dropped
DP-04  Remote locations  [now]
        now: contains 'remote' -> remote:us or remote:<rest>
DP-05  Weighting of ecosystem figures  [now]
        now: firm-weighted
DP-06  Figures without the largest firm  [now]
        now: 1 firm left out (the one with the most distinct roles)
DP-10  Boston-area definition  [now]
        now: 51 towns
DP-11  Boston baseline membership  [now]
        now: Tier A firms with at least one role in a listed town
DP-17  Skill phrase length  [now]
        now: 1 to 3 words
DP-18  Minimum skill support  [now, provisional]
        now: at least 20 roles, at least 3 firms, at most 30% of roles
(...)
DP-56  Postings already open on day one  [now]
        now: left out of durations
DP-57  Relisting rule  [now]
        now: new posting id, same firm, title, locations and ad hash, first seen after the earlier one's last day
28 points
```

**Example Contributor:** DP-18, minimum skill support. I worked with text features in my thesis.

```text
$ python3 -I pipeline/run.py own DP-18 --as "Example Contributor"
DP-18: owner Example Contributor, status owned
```

**Claude:** It's yours. A phrase from the requirement text counts as a skill only if it appears in at least 20 roles, at at least 3 firms, and in no more than 30% of roles. That rule is in `build_vocabulary()` in `pipeline/ai_jobs_map/core.py`, and the build passes it the three `skills.min_support_*` config keys. The registry marks this default *provisional*: it's an open lead-author decision, and its rationale cites the AI jobs map's Phase 2 report, which suggested raising the firm minimum to 5 or 10. Its `precedent` list is empty, so finding precedent is open work. The skill measure follows Babina et al. (2024), so their methods and data appendix are one place to look. A Google Scholar search on skill vocabularies built from job postings is another.

**Example Contributor:** Can you just tell me what threshold those papers used? It would save time.

**Claude:** I'd rather not. Reading the sources and judging them is the research part, and it's yours. What I can do is point you to where to look: for Babina et al., the section that describes how skills are defined. If a paper doesn't state a threshold, that's worth recording too, with where you looked.

**Example Contributor:** Okay. I read it and searched. Here's my first alternative.

> Raise the firm minimum for a skill from 3 firms to 5 (skills.min_support_firms = 5), and keep the role minimum and the 30% ceiling as they are.

Rationale:

> A phrase seen at only 3 firms can be one company's wording copied by a few others, so it isn't really a shared skill. The AI jobs map's Phase 2 report already suggested 5 or 10.

And the prediction:

> If the AI-related share depends on rare phrases, KR-02 should fall by 5 points or more, because roles would lose skills and fewer would pass the 0.1 threshold. KR-05's order could change if integrates roles rely on rarer tool names. KR-01 and KR-07 shouldn't move, because they don't use the skill vocabulary.

```text
$ python3 -I pipeline/run.py new-proposal DP-18 --as "Example Contributor"
P-0001: paper/multiverse/proposals/P-0001.md
```

**Claude:** That's P-0001, with your three sections saved as you typed them. A few questions. You wrote that a phrase at 3 firms "can be one company's wording copied by a few others". Did you see that in the data, or could it happen? How would a reader judge how often it does?

**Example Contributor:** It could happen, I didn't check it. I've said so, and said where I looked for precedent. Here's the rationale again:

> A phrase that appears at only 3 firms might be one employer's wording that a few others copied, rather than a skill the market shares. I haven't measured how often that happens. The AI jobs map's Phase 2 report suggested raising the minimum to 5 or 10. I searched Google Scholar for skill-frequency thresholds in job-posting studies and found none that states a firm minimum, so I have no published precedent. I chose 5 because it is the smaller of the report's two values, so it removes the fewest phrases while still asking for more than a handful of employers.

**Claude:** You mention 5 or 10. Why 5 rather than 10?

**Example Contributor:** It's the smaller of the two, so it removes the fewest phrases.

**Claude:** Your prediction says KR-02 falls if the finding is fragile. What size of fall would you read as "the finding held"?

**Example Contributor:** Under 2 points. I've added that:

> If the AI-related share depends on rare phrases, KR-02 should fall by 5 points or more, because roles would lose skills and fewer would pass the 0.1 threshold. A fall of less than 2 points I'd read as robust. KR-05's order could change if integrates roles rely on rarer tool names. KR-01 and KR-07 shouldn't move, because they don't use the skill vocabulary.

**Example Contributor:** Could you tidy the wording of my rationale before it goes in? English isn't my first language.

**Claude:** I won't reword it. The rationale has to be your thinking in your words, both for your learning and so your authorship is real. If a sentence is unclear, I'll point to it and ask what you meant, and you decide how to say it. I don't see an unclear one. The paper's guide says AI help with drafting elsewhere must be disclosed, and this skill doesn't do it for your own contribution.

**Example Contributor:** Fine, leave it. I also want to propose one I think we should rule out: dropping the firm minimum to 1.

> Lower the firm minimum for a skill from 3 firms to 1 (skills.min_support_firms = 1).

> I'm proposing this one to rule it out. With a minimum of 1 firm, a phrase used by a single employer could count as a skill, so w(s) would partly measure that employer's wording instead of a skill shared across firms. That goes against the reason the support rule exists, whatever the result would be.

> I don't think it should run. If it did, I'd expect KR-02 to rise, because single-firm phrases would add vocabulary that co-occurs with the seed skills.

```text
$ python3 -I pipeline/run.py new-proposal DP-18 --as "Example Contributor" --eliminate
P-0002: paper/multiverse/proposals/P-0002.md
```

**Claude:** That's P-0002, marked as one you recommend eliminating. A reasoned elimination is a contribution: it shows the range of choices was considered. Your reason doesn't depend on any result. Is there a study where a one-firm minimum would be defensible?

**Example Contributor:** A study of one firm, maybe. This paper compares firms, so not here.

**Claude:** I've added the questions and your answers to each file's critique record. Here's P-0001 as it will be submitted:

`paper/multiverse/proposals/P-0001.md`:

~~~markdown
---
# Branch proposal. Copy to paper/multiverse/proposals/P-NNNN.md, one file per
# alternative. The /contribute skill fills in this header and copies the first
# two sections from the registry. Everything else is the contributor's own
# words, saved as typed.
proposal_id: P-0001
decision_point: DP-18
proposer: Example Contributor
date_proposed: "2026-11-23"
results_seen_before_proposing: false
proposer_recommends: run
override: {}                # filled in after acceptance, e.g. {"skills.min_support_firms": 5}
ai_assistance: "Claude Code /contribute: made the file, copied the decision point and current choice from the registry, explained where skills.min_support_firms is used in the code, asked three critique questions"
---

## Decision point

**DP-18: Minimum skill support.** How common a phrase must be before it counts as a skill. Rare phrases give noisy AI-relatedness scores.

## Current choice

**Now:** at least 20 roles, at least 3 firms, at most 30% of roles. This default is provisional: an open lead-author decision, and the comparison point until it is decided.

Config keys a branch can set: `skills.min_support_roles`, `skills.min_support_firms`, `skills.max_doc_share`.

## Alternative

Raise the firm minimum for a skill from 3 firms to 5 (skills.min_support_firms = 5), and keep the role minimum and the 30% ceiling as they are.

## Rationale (contributor's own words, with precedent if any)

A phrase that appears at only 3 firms might be one employer's wording that a few others copied, rather than a skill the market shares. I haven't measured how often that happens. The AI jobs map's Phase 2 report suggested raising the minimum to 5 or 10. I searched Google Scholar for skill-frequency thresholds in job-posting studies and found none that states a firm minimum, so I have no published precedent. I chose 5 because it is the smaller of the report's two values, so it removes the fewest phrases while still asking for more than a handful of employers.

## What we'd expect to see if the finding is fragile

If the AI-related share depends on rare phrases, KR-02 should fall by 5 points or more, because roles would lose skills and fewer would pass the 0.1 threshold. A fall of less than 2 points I'd read as robust. KR-05's order could change if integrates roles rely on rarer tool names. KR-01 and KR-07 shouldn't move, because they don't use the skill vocabulary.

## Critique record

- Q (Claude): You wrote that a phrase at 3 firms "can be one company's wording copied by a few others". Did you see that in the data, or could it happen? How would a reader judge how often it does?
  A (Example Contributor): It could happen, I didn't check it. I've said so, and said where I looked for precedent.
- Q (Claude): You mention 5 or 10. Why 5 rather than 10?
  A (Example Contributor): It's the smaller of the two, so it removes the fewest phrases.
- Q (Claude): Your prediction says KR-02 falls if the finding is fragile. What size of fall would you read as "the finding held"?
  A (Example Contributor): Under 2 points. I've added that.
~~~

And the one you recommend eliminating:

`paper/multiverse/proposals/P-0002.md`:

~~~markdown
---
# Branch proposal. Copy to paper/multiverse/proposals/P-NNNN.md, one file per
# alternative. The /contribute skill fills in this header and copies the first
# two sections from the registry. Everything else is the contributor's own
# words, saved as typed.
proposal_id: P-0002
decision_point: DP-18
proposer: Example Contributor
date_proposed: "2026-11-23"
results_seen_before_proposing: false
proposer_recommends: eliminate
override: {}                # filled in after acceptance, e.g. {"skills.min_support_firms": 5}
ai_assistance: "Claude Code /contribute: made the file, copied the decision point and current choice from the registry, asked one critique question"
---

## Decision point

**DP-18: Minimum skill support.** How common a phrase must be before it counts as a skill. Rare phrases give noisy AI-relatedness scores.

## Current choice

**Now:** at least 20 roles, at least 3 firms, at most 30% of roles. This default is provisional: an open lead-author decision, and the comparison point until it is decided.

Config keys a branch can set: `skills.min_support_roles`, `skills.min_support_firms`, `skills.max_doc_share`.

## Alternative

Lower the firm minimum for a skill from 3 firms to 1 (skills.min_support_firms = 1).

## Rationale (contributor's own words, with precedent if any)

I'm proposing this one to rule it out. With a minimum of 1 firm, a phrase used by a single employer could count as a skill, so w(s) would partly measure that employer's wording instead of a skill shared across firms. That goes against the reason the support rule exists, whatever the result would be.

## What we'd expect to see if the finding is fragile

I don't think it should run. If it did, I'd expect KR-02 to rise, because single-firm phrases would add vocabulary that co-occurs with the seed skills.

## Critique record

- Q (Claude): Your reason doesn't depend on any result. Is there a study where a one-firm minimum would be defensible?
  A (Example Contributor): A study of one firm, maybe. This paper compares firms, so not here.
~~~

**Example Contributor:** Submit both.

```text
$ python3 -I pipeline/run.py propose P-0001 --ai "Claude Code /contribute: made the file, copied the decision point and current choice from the registry, explained where skills.min_support_firms is used in the code, asked three critique questions"
{
 "event_id": "E-0001",
 "proposal_id": "P-0001",
 "decision_point": "DP-18",
 "alternative": "Raise the firm minimum for a skill from 3 firms to 5 (skills.min_support_firms = 5), and keep the role minimum and the 30% ceiling as they are.",
 "proposer": "Example Contributor",
 "status": "proposed",
 "reason": null,
 "decided_by": "Example Contributor",
 "date": "2026-11-23T19:28:52Z",
 "results_seen": "before",
 "results_link": null,
 "corrects": null,
 "sections_sha256": "85590c6acd9859c34c943a9d0225c0aabbf1a4985936773b89f068a69c2a6e56"
}
```

```text
$ python3 -I pipeline/run.py propose P-0002 --ai "Claude Code /contribute: made the file, copied the decision point and current choice from the registry, asked one critique question"
{
 "event_id": "E-0002",
 "proposal_id": "P-0002",
 "decision_point": "DP-18",
(...)
}
```

**Claude:** Both are in the decision log as proposed: E-0001 and E-0002. I've committed the two proposal files, the registry and the decision log. Next, the group reviews them and the lead author decides. I can't speed that up or predict the decision.

**Example Contributor:** While I'm here: can you help me label a few roles in the AI jobs map's review sample? I've been asked to do some.

**Claude:** No. That labeling has to be your own reading, made without AI. The sample checks the pipeline's labels against a person's judgment, and with my help it would check the pipeline against AI. The same goes for rating or classifying any firm.

**Claude:** Before we stop: in a sentence or two, what did you do this session? I'll record it as you say it.

**Example Contributor:** Took DP-18 (minimum skill support). Looked for precedent and wrote two proposals: raise the firm minimum to 5, and lower it to 1, which I argued should be eliminated.

```text
$ python3 -I pipeline/run.py log-contribution --as "Example Contributor" --task "Took DP-18 (minimum skill support). Looked for precedent and wrote two proposals: raise the firm minimum to 5, and lower it to 1, which I argued should be eliminated." --role Methodology --counts-as component --artifact paper/multiverse/proposals/P-0001.md --artifact paper/multiverse/proposals/P-0002.md --artifact E-0001 --artifact E-0002 --ai "Claude Code /contribute: listed the open decision points, explained how skills.min_support_firms is used in the code, made both proposal files, asked critique questions, logged both proposals"
{
 "entry_id": "C-0001",
 "contributor": "Example Contributor",
 "date": "2026-11-23",
 "task": "Took DP-18 (minimum skill support). Looked for precedent and wrote two proposals: raise the firm minimum to 5, and lower it to 1, which I argued should be eliminated.",
 "credit_roles": [
  "Methodology"
 ],
 "counts_as": "component",
 "artifacts": [
  "paper/multiverse/proposals/P-0001.md",
  "paper/multiverse/proposals/P-0002.md",
  "E-0001",
  "E-0002"
 ],
 "ai_assistance": "Claude Code /contribute: listed the open decision points, explained how skills.min_support_firms is used in the code, made both proposal files, asked critique questions, logged both proposals",
 "confirmed_by_contributor": false
}
NOT written: show it to the contributor, then rerun with --confirmed
```

**Claude:** Here's the entry, not written yet. Methodology is the CRediT role for this part of the task, and it counts as component work. The last line is my own account of what I did this session. Is it right?

**Example Contributor:** Yes.

**Claude:** Written to `paper/contributions.yaml` as C-0001. When the paper is drafted, disclose your use of Claude Code in its AI-use statement and name what it did. The ai_assistance lines are your record.

## Between sessions: the group decides

The group discussed both proposals. The lead author recorded the decisions with `log-event`, in their own words: P-0002 rejected, before any run, and P-0001 accepted. The full decision log is at the end of this file.

## Session 2: running the branch and interpreting it

```text
$ python3 -I pipeline/run.py status --as "Example Contributor"
Example Contributor: in paper/roster.yaml (contributor)
results: may see results. Example Contributor is cleared (contributor, rater with complete ratings)
owns: DP-18
  P-0001 DP-18 accepted: Defensible and can be applied consistently; within the purpose of the support rule, and the AI jobs map's Phase 2 report already named 5 as a candidate.
  P-0002 DP-18 rejected: Agreed with the proposer: a one-firm minimum lets a single employer's wording count as a skill, which defeats the purpose of the support rule. Rejected for that reason, before any run.
```

**Claude:** P-0001 was accepted. P-0002 was rejected before anything ran, for the reason you gave, and the rejection and its reason are part of the record.

**Example Contributor:** Can we run P-0002 anyway, just to see what happens?

```text
$ python3 -I pipeline/run.py new-branch P-0002 --set skills.min_support_firms=1
refused: P-0002 is rejected; a branch is written only after the lead author accepts the proposal
```

**Claude:** No. A branch runs only after the lead author accepts it. Running a rejected alternative "to see" would let its result reopen a decision made for a reason, and the rule is to cut for reasons, never for results. If you think the rejection was wrong, raise it with the lead author.

**Claude:** For P-0001, your alternative is "skills.min_support_firms = 5", with the other two support rules unchanged.

```text
$ python3 -I pipeline/run.py new-branch P-0001 --set skills.min_support_firms=5
{
 "branch_id": "BR-0001",
 "proposal_id": "P-0001",
 "decision_point": "DP-18",
 "overrides": {
  "skills.min_support_firms": 5
 }
}
```

```text
$ python3 -I pipeline/run.py branch BR-0001 --as "Example Contributor"
refused: paper/multiverse/branches/BR-0001.yaml isn't committed, or has changes since; commit it first, so the run names the version it ran against
```

**Claude:** The runner needs the branch file committed, so the run records exactly which proposal and prediction it ran against. I've committed it. Running now.

```text
$ python3 -I pipeline/run.py branch BR-0001 --as "Example Contributor"

BR-0001: paper/multiverse/runs/BR-0001/2026-11-23T19-28-53Z
compared with paper/multiverse/runs/BR-0000/2026-11-23T19-28-53Z
KR-01  Tier A firms  [same; flip rule: none]
    default  100
    branch   100
KR-02  Share of scored roles that are AI-related  [changed; flip rule: crosses 50.0%]
    default  90.0%
    branch   88.7%  (-1.3 points)
KR-03  Seed-skill base rate (text roles naming a seed skill)  [same; flip rule: none]
    default  20.0%
    branch   20.0%
KR-04  Firms with an AI section  [changed; flip rule: none]
    default  40
    branch   39  (-1)
KR-05  Signal types ranked by the number of measured firms with at least one such role  [same; flip rule: order-changes]
    default  builds > integrates > uses_tools
    branch   builds > integrates > uses_tools
KR-06  Most common signal type in each sector bucket with at least 5 measured firms  [changed; flip rule: none]
    default  it-services: builds; software-internet: builds = integrates
    branch   it-services: builds; software-internet: builds
KR-07  Share of distinct roles with an occupation code  [same; flip rule: none]
    default  40.0%
    branch   40.0%
KR-08  Top three occupation groups among Boston-area Tier A firms (firm-weighted, unassigned titles left out)  [same; flip rule: top-changes]
    default  15-0000
    branch   15-0000
KR-09  Firms with a sector bucket, and the largest bucket by firms  [same; flip rule: top-changes]
    default  it-services
    branch   it-services
```

**Claude:** What these are:

- **KR-02** is the share of scored roles whose AI score passes 0.1. It moved from 90.0% to 88.7%. Its flip rule is "crosses 50%", which didn't happen, so it's marked changed, not FLIP.
- **KR-04** counts firms with enough text roles to get an AI section. It went from 40 to 39.
- **KR-06** is the most common signal type in each sector bucket. In software-internet, builds and integrates were tied at the default, and builds is now alone. Its flip rule is "none", so a change is reported but never counts as a flip.
- **Everything else** is the same.

What this means for the finding is your interpretation.

**Example Contributor:** So is it robust? Just tell me and I'll write it up.

**Claude:** That judgment is the core of your contribution, so I'll leave it to you. Your prediction, written before the run, says what you'd count as robust. Compare the table with it.

```text
$ python3 -I pipeline/run.py new-interpretation BR-0001 --as "Example Contributor"
paper/multiverse/interpretations/BR-0001.md
```

**Example Contributor:** Here's what I wrote. What changed:

> KR-02 fell from 90.0% to 88.7%, about 1.3 points. KR-04 went from 40 firms with an AI section to 39. In KR-06, software-internet was tied between builds and integrates and is now builds alone; it-services stayed builds. KR-01, KR-03, KR-05, KR-07, KR-08 and KR-09 didn't change.

Robust or fragile:

> Robust. I predicted a fall of 5 points or more in KR-02 if the finding depended on rare phrases, and said a fall under 2 points would count as robust. It fell about 1.3 points and stayed far above 50%, so its flip rule didn't trigger. KR-05's order held, though I'd said it could change. The KR-06 change broke a tie rather than reversing an order, and KR-06's flip rule is none.

What it means:

> The claim that most scored roles are AI-related doesn't depend on counting phrases that only 3 or 4 firms use. This is one branch on one data snapshot, so it says nothing about the role minimum or the 30% ceiling, and the KR-06 tie means that result can move with a single firm.

**Claude:** You name KR-04's move from 40 to 39. Do you know which firm dropped, and does a reader need to know whether you do?

**Example Contributor:** I don't know which one. It's one firm of 40, and the claim isn't about that firm.

**Claude:** "Robust" rests on your 2-point line. Where does that line come from, and when was it written?

**Example Contributor:** It's in my prediction, committed before the run. It's my own line, not a statistical test.

`paper/multiverse/interpretations/BR-0001.md`:

~~~markdown
---
# Branch interpretation. `python3 -I pipeline/run.py new-interpretation BR-nnnn --as NAME` copies this to
# paper/multiverse/interpretations/BR-nnnn.md and fills in this header, the prediction and the key results.
# The three sections after that are the contributor's own words, saved as typed.
branch_id: BR-0001
proposal_id: P-0001
decision_point: DP-18
author: Example Contributor
date_started: "2026-11-23"
run_folder: "paper/multiverse/runs/BR-0001/2026-11-23T19-28-53Z"
code_commit: b46ca99ea0dcf65689b0287d5b6b22ad98cd783f
compared_with: "paper/multiverse/runs/BR-0000/2026-11-23T19-28-53Z"
ai_assistance: "Claude Code (/contribute) made this file and filled in the override, the prediction and the key results"
---

## What the branch changed

- `skills.min_support_firms`: `5`

## Your prediction, written before the run

> If the AI-related share depends on rare phrases, KR-02 should fall by 5 points or more, because roles would lose skills and fewer would pass the 0.1 threshold. A fall of less than 2 points I'd read as robust. KR-05's order could change if integrates roles rely on rarer tool names. KR-01 and KR-07 shouldn't move, because they don't use the skill vocabulary.

From paper/multiverse/proposals/P-0001.md at commit b46ca99, the version the branch ran with.

## Key results against the default

```
KR-01  Tier A firms  [same; flip rule: none]
    default  100
    branch   100
KR-02  Share of scored roles that are AI-related  [changed; flip rule: crosses 50.0%]
    default  90.0%
    branch   88.7%  (-1.3 points)
KR-03  Seed-skill base rate (text roles naming a seed skill)  [same; flip rule: none]
    default  20.0%
    branch   20.0%
KR-04  Firms with an AI section  [changed; flip rule: none]
    default  40
    branch   39  (-1)
KR-05  Signal types ranked by the number of measured firms with at least one such role  [same; flip rule: order-changes]
    default  builds > integrates > uses_tools
    branch   builds > integrates > uses_tools
KR-06  Most common signal type in each sector bucket with at least 5 measured firms  [changed; flip rule: none]
    default  it-services: builds; software-internet: builds = integrates
    branch   it-services: builds; software-internet: builds
KR-07  Share of distinct roles with an occupation code  [same; flip rule: none]
    default  40.0%
    branch   40.0%
KR-08  Top three occupation groups among Boston-area Tier A firms (firm-weighted, unassigned titles left out)  [same; flip rule: top-changes]
    default  15-0000
    branch   15-0000
KR-09  Firms with a sector bucket, and the largest bucket by firms  [same; flip rule: top-changes]
    default  it-services
    branch   it-services
```

The full comparison is in paper/multiverse/runs/BR-0001/2026-11-23T19-28-53Z/diff_vs_default.json, on the machine that ran it.

## What changed

KR-02 fell from 90.0% to 88.7%, about 1.3 points. KR-04 went from 40 firms with an AI section to 39. In KR-06, software-internet was tied between builds and integrates and is now builds alone; it-services stayed builds. KR-01, KR-03, KR-05, KR-07, KR-08 and KR-09 didn't change.

## Robust or fragile, against your prediction

Robust. I predicted a fall of 5 points or more in KR-02 if the finding depended on rare phrases, and said a fall under 2 points would count as robust. It fell about 1.3 points and stayed far above 50%, so its flip rule didn't trigger. KR-05's order held, though I'd said it could change. The KR-06 change broke a tie rather than reversing an order, and KR-06's flip rule is none.

## What it means for the claim

The claim that most scored roles are AI-related doesn't depend on counting phrases that only 3 or 4 firms use. This is one branch on one data snapshot, so it says nothing about the role minimum or the 30% ceiling, and the KR-06 tie means that result can move with a single firm.

## Critique record

- Q (Claude): You name KR-04's move from 40 to 39. Do you know which firm dropped, and does a reader need to know whether you do?
  A (Example Contributor): I don't know which one. It's one firm of 40, and the claim isn't about that firm.
- Q (Claude): "Robust" rests on your 2-point line. Where does that line come from, and when was it written?
  A (Example Contributor): It's in my prediction, committed before the run. It's my own line, not a statistical test.
~~~

**Claude:** I've committed the interpretation, the branch file and the decision log with its run event. What did you do this session?

**Example Contributor:** Ran BR-0001 (firm minimum 5) and wrote its interpretation: the AI-related share held.

```text
$ python3 -I pipeline/run.py log-contribution --as "Example Contributor" --task "Ran BR-0001 (firm minimum 5) and wrote its interpretation: the AI-related share held." --role "Formal analysis" --counts-as component --artifact paper/multiverse/branches/BR-0001.yaml --artifact paper/multiverse/interpretations/BR-0001.md --artifact E-0005 --ai "Claude Code /contribute: wrote the override file, ran BR-0001, explained the key results, asked two critique questions on the interpretation"
{
 "entry_id": "C-0002",
 "contributor": "Example Contributor",
 "date": "2026-11-23",
 "task": "Ran BR-0001 (firm minimum 5) and wrote its interpretation: the AI-related share held.",
(...)
  "Formal analysis"
 ],
 "counts_as": "component",
 "artifacts": [
  "paper/multiverse/branches/BR-0001.yaml",
  "paper/multiverse/interpretations/BR-0001.md",
  "E-0005"
 ],
 "ai_assistance": "Claude Code /contribute: wrote the override file, ran BR-0001, explained the key results, asked two critique questions on the interpretation",
 "confirmed_by_contributor": false
}
NOT written: show it to the contributor, then rerun with --confirmed
```

**Claude:** Here's the entry, not written yet: Formal analysis, component work, and my own account of what I did this time. I wrote the override file, ran the branch, explained the key results and asked two questions. Is it right?

**Example Contributor:** Yes.

```text
$ python3 -I pipeline/run.py log-contribution --as "Example Contributor" --task "Ran BR-0001 (firm minimum 5) and wrote its interpretation: the AI-related share held." --role "Formal analysis" --counts-as component --artifact paper/multiverse/branches/BR-0001.yaml --artifact paper/multiverse/interpretations/BR-0001.md --artifact E-0005 --ai "Claude Code /contribute: wrote the override file, ran BR-0001, explained the key results, asked two critique questions on the interpretation" --confirmed
{
(...)
written to paper/contributions.yaml
```

**Claude:** Written as C-0002. The same reminder applies: disclose Claude Code's part in the paper's AI-use statement.

## The decision log after both sessions

```yaml
- event_id: E-0001
  proposal_id: P-0001
  decision_point: DP-18
  alternative: Raise the firm minimum for a skill from 3 firms to 5 (skills.min_support_firms = 5), and keep the
    role minimum and the 30% ceiling as they are.
  proposer: Example Contributor
  status: proposed
  reason: null
  decided_by: Example Contributor
  date: '2026-11-23T19:28:52Z'
  results_seen: before
  results_link: null
  corrects: null
  sections_sha256: 85590c6acd9859c34c943a9d0225c0aabbf1a4985936773b89f068a69c2a6e56

- event_id: E-0002
  proposal_id: P-0002
  decision_point: DP-18
  alternative: Lower the firm minimum for a skill from 3 firms to 1 (skills.min_support_firms = 1).
  proposer: Example Contributor
  status: proposed
  reason: null
  decided_by: Example Contributor
  date: '2026-11-23T19:28:52Z'
  results_seen: before
  results_link: null
  corrects: null
  sections_sha256: 60daa60087fec448fa6c6761ae6a97e09b78cc6fdf87988f568814e916941407

- event_id: E-0003
  proposal_id: P-0002
  decision_point: DP-18
  alternative: Lower the firm minimum for a skill from 3 firms to 1 (skills.min_support_firms = 1).
  proposer: Example Contributor
  status: rejected
  reason: 'Agreed with the proposer: a one-firm minimum lets a single employer''s wording count as a skill, which
    defeats the purpose of the support rule. Rejected for that reason, before any run.'
  decided_by: Example Lead Author
  date: '2026-11-23T19:28:52Z'
  results_seen: before
  results_link: null
  corrects: null
  sections_sha256: null

- event_id: E-0004
  proposal_id: P-0001
  decision_point: DP-18
  alternative: Raise the firm minimum for a skill from 3 firms to 5 (skills.min_support_firms = 5), and keep the
    role minimum and the 30% ceiling as they are.
  proposer: Example Contributor
  status: accepted
  reason: Defensible and can be applied consistently; within the purpose of the support rule, and the AI jobs map's
    Phase 2 report already named 5 as a candidate.
  decided_by: Example Lead Author
  date: '2026-11-23T19:28:53Z'
  results_seen: before
  results_link: null
  corrects: null
  sections_sha256: null

- event_id: E-0005
  proposal_id: P-0001
  decision_point: DP-18
  alternative: Raise the firm minimum for a skill from 3 firms to 5 (skills.min_support_firms = 5), and keep the
    role minimum and the 30% ceiling as they are.
  proposer: Example Contributor
  status: run
  reason: null
  decided_by: runner
  date: '2026-11-23T19:28:53Z'
  results_seen: null
  results_link: paper/multiverse/runs/BR-0001/2026-11-23T19-28-53Z
  corrects: null
  sections_sha256: null
```

## What this example shows

| Moment | Hard rule |
|---|---|
| `status` checked before anything with results | 2: no results until ratings are complete |
| Claude points to sources and asks questions; every proposal and interpretation section is the contributor's typing; no rewording on request | 4: the contributor does the thinking |
| The review-sample labeling request declined | 3: never help with rating or labeling |
| P-0002 rejected before any run, with its reason, `results_seen: before`; the request to run it anyway refused | 6: cut for reasons, never for results |
| Only the lead author's `accepted` lets a branch be written and run; Claude never predicts or suggests a decision | 5: the skill never approves |
| Only DP-18 is touched; a locked point would be refused at `own`, `new-proposal` and `branch` | 1: the confirmatory study is off-limits |
