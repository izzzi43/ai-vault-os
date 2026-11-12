---
name: consolidate
description: Weekly consolidation of the vault. Reads the last seven daily notes, finds what repeated, and proposes at most five changes to area notes and memory, each with its evidence. Use when the user says "consolidate", "weekly review of the vault", or when the same correction shows up a second time.
---

# Consolidate

Daily notes grow, but nothing moves what repeats into the notes that get read. Rule 6 says to write the rule
the second time something happens. That only works if someone notices the second time. This is the pass that
notices.

Run it in a subagent if you can, so the reading does not fill the main context. Write nothing before the
user agrees.

## Steps

1. **Read the week.** The index lines and the sections "Decisions" and "Open" of the last seven notes in
   `01-daily/`. Not the full notes unless a line needs its context.
2. **Find what repeated.** Look for:
   - the same correction from the user on two different days
   - the same gotcha or the same workaround twice
   - a decision that was made, then made again differently (one of them is now outdated)
   - an open point that is carried from day to day and never moves
   - a fact that sits only in daily notes but was needed again later
3. **Check what exists.** For each candidate run `python3 tools/vault_search.py "<words>"`. If a note already
   holds it, the proposal is to extend or correct that note, not to create one.
4. **Propose at most five changes.** One block per proposal:
   - **What:** the rule or fact in one or two sentences, in the words it would be filed in
   - **Where:** the file and section, or the new memory file with its index line
   - **Kind:** timeless, dated `(as of YYYY-MM-DD)` or pointer
   - **Evidence:** the daily notes and lines it comes from, at least two
   - **Replaces:** the line that no longer holds, if any. It moves to "Earlier" with
     `(held until YYYY-MM-DD, replaced by [[...]])`, it is not deleted
5. **Ask.** Show the proposals, wait for a yes per proposal.
6. **File what was agreed**, update the folder index in the same move, run `python3 tools/vault_lint.py`,
   and add one line to today's daily note: how many proposals, how many accepted.

## Limits

- Five proposals, not fifteen. If more than five things repeated, take the five that would have saved the
  most time and name the rest in one line.
- One occurrence is not a pattern. It stays in the daily note.
- Never invent the second occurrence. If the evidence is one note, say so and drop it.
- No personal data about other people beyond what the daily notes already hold.

## How to tell whether it works

Count per run: proposals made, proposals accepted. Keep a tally in the daily note when the user has to
repeat a correction a third time. Accepted proposals should stay above half, the tally should fall.
