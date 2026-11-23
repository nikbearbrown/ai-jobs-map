# Defensibility checklist for a proposal

Use these to choose questions, one at a time, quoting the sentence you're asking about. They are questions for the contributor to answer in their own words, never a rubric you fill in and never a verdict. Don't ask all of them: ask the ones the draft raises.

## The brief's four questions

1. **Precedent.** Has published work made this choice? Where did they look, and what did they search for? "No precedent found" is a fair answer when it says where they looked.
2. **Question or answer.** Does the alternative change how the analysis answers the same question, or does it change the question? An alternative that changes the question (a different population, a different outcome) is a different study, not a branch.
3. **Consistency.** Could someone else apply it the same way to every firm and role, from the proposal alone? Is any word in the alternative a judgment call ("relevant", "clearly", "most")?
4. **Breakage.** Would it break the analysis? An empty vocabulary, no Tier A firms, a share with a zero denominator, a value below the registry's `minimum`, or a variant the code doesn't implement.

## Also ask

5. **Timing.** Was this written before seeing any branch result on this decision point? (`new-proposal` asks when branches on the point have already run.)
6. **Implementable.** Is it a value the config takes, or does it need a new switch variant? A new variant is a code change: does the proposal describe it precisely enough to build and review?
7. **The prediction.** Does it name key results (KR-nn), a direction, and a rough size? Does it say what size of change they'd read as "the finding held"? Was it written before anything ran?
8. **Elimination.** If they expect to eliminate it, is the reason independent of any result? Would the reason still hold if the branch, run, had shown nothing at all?

## Never

- Offer wording, a better sentence, or "something like ...".
- Say whether the group will accept it, or whether you would.
- Suggest an alternative yourself. Pointing to how prior work made the choice is fine; proposing what to try is their work.
