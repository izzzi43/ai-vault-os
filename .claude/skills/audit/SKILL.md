---
name: audit
description: Checks every rule in the memory folder, and the head of every area note, against reality. Corrects only what can be proven, and hands the rest to the user as a short list of decisions. Use when the user says "audit", "check the memory", "are my rules still true", or once a quarter.
---

# Audit

The check script finds broken links and missing heads. It cannot tell whether a rule is still true. A rule
that names a script that moved, a weekday that changed or a tool that was switched off looks healthy and
sends the agent the wrong way. This pass reads each rule once and holds it against the thing it talks about.

Run it in a subagent if you can. It reads a lot.

## Steps

1. **Back up first.** Copy the memory folder to a dated folder outside the vault. Delete and rename nothing.
2. **Read every rule file in full**, not just its index line.
3. **Check what can be checked.** Paths and scripts (do they exist, do the named options exist), links to
   other notes, dates that have passed, states ("paused", "not built yet"), and two rules that say different
   things about the same subject. Read, do not run. Use no tool that sends or changes anything.
4. **Sort every file into one of four lists.**
   - **A, checked and true.** Only files without any finding.
   - **B, corrected.** The fix is a fact with evidence (the file is at a new path, the linked note has a
     new name). Add one line at the end of the rule: `Corrected YYYY-MM-DD: what, evidence: where.` The
     meaning of the rule does not change.
   - **C, needs a decision.** Two rules disagree, a state looks outdated, a rule collides with a newer one.
     Do not pick a winner. Write both sides, the evidence, and one proposal.
   - **D, not checkable.** Preferences, taste, anything behind a login. Say so instead of guessing.
5. **Do the same for heads.** A head is a claim about what holds today. Where the body below it disagrees
   with itself, the head names the contradiction. It does not settle it.
6. **Report.** Counts per list, the five most important points from C first, the full lists in one note in
   the vault. One line in today's daily note that links it.

## Limits

- B is for facts, never for meaning. If you are unsure whether it is B or C, it is C.
- A written head or a corrected rule is marked "not confirmed by the user yet" until they have seen it.
- Never read secrets to check a rule. If a check would need one, the rule goes to D.

## How to tell whether it works

Count per run: files in B and points in C. Both should fall from run to run. If C grows, rules are being
written faster than they are being retired, and "consolidate" is the pass that is missing.
