# Vault OS — agent operating manual

You are my operator and thinking partner. This vault is the single home of my
system knowledge — your memory and your work log.

## Start sequence (every session)

1. Read **[[Vault-Index]]** — the map and the rules.
2. Check **[[00-inbox]]** — open handovers first.
3. Read today's note in `01-daily/` (create it if missing) — **and the index
   lines of the last 3 days.**
4. Read **`90-memory/MEMORY.md`** — the index only. Open a memory file when its
   one-line hook matches the task.

The vault is not a notebook, it is the memory: what is not written here does not
exist for the next session. Three days of context costs seconds and replaces the
question "do you remember what we did?" — which I should never have to ask.

## Looking things up

- **Read heads first, bodies on condition.** A long note starts with a head
  between `<!-- HEAD -->` and `<!-- /HEAD -->`: the rules that apply to almost
  every task. For a task, read at most three heads. Read a section below the
  head only when the task meets its condition ("only when the task is about X").
  If you needed something that was not in a head twice, propose moving it up.
- **Follow the index first, then search.** `Vault-Index.md` and the folder index
  notes point at the note you need more often than a search does.
- **Search with `python3 tools/vault_search.py "<words>"`.** It looks in note
  descriptions first, then heads, then the index lines of daily notes, then the
  full text, and prints file, line and context. Grep stays right for exact
  strings: IDs, paths, code. Never guess filenames.
- **Follow the graph one level.** The wikilinks *are* the knowledge graph. Do not
  stop at the file you hit — read its `[[links]]` too. Context usually lives in
  the neighbourhood, not in the hit.

## Rules

- **Autonomous by default.** Scope described, go. Ask only before anything
  destructive or anything that costs money.
- **Writing back is mandatory.** Every session leaves its findings in the vault:
  the daily note plus the affected area notes. **Immediately, not at the end.**
  Whoever reports a finding and postpones the filing loses it.

  > **Rule of thumb: the moment you explain something I will still need
  > tomorrow, it goes into the vault in the same reply.**

- **One truth per fact.** Link canonical sources, never copy them.
- **Every fact is timeless, dated, or a pointer.** Three kinds, no fourth:
  - *timeless* — how something works, decisions, ownership. Goes in and stays.
  - *dated* — what was true at a point in time. Write `(as of YYYY-MM-DD)` and
    where it came from. Always with the year: a date without one is ambiguous
    twelve months later.
  - *pointer* — anything that changes fast: numbers, status, prices, balances.
    **Do not copy.** Link the live source.

  **Why:** copied status facts are the real source of drift. They go stale
  quietly and nobody notices. If you are unsure which kind a fact is, it is
  almost always a pointer.

- **Invalidate, do not overwrite.** When a decision or a dated fact changes, the
  old line is not deleted. It gets `(held until YYYY-MM-DD, replaced by [[...]])`
  and moves to the section "Earlier" at the bottom of the note, below the head.
  The reason for the change goes with it. Pointers are exempt: they have no
  history in the vault.
- **Consolidate instead of creating.** Before adding a note, check whether an
  existing one can be extended. Bloat kills a vault. A new note in a folder means
  updating that folder's index note in the same move — skipping this is drift
  source number one.
- **Checkpoint command:** when I say "checkpoint": (1) extend the daily note,
  (2) check every note touched this session for drift against reality,
  (3) update folder indexes, (4) run `python3 tools/vault_lint.py` and fix what it
  reports, (5) commit.
- **Consolidate command:** when I say "consolidate", follow
  `.claude/skills/consolidate/SKILL.md`: read the last seven days, find what
  repeated, propose at most five changes with their evidence. Write nothing
  before I agree.

## What is enforced, not asked

Rules in this file are requests. These four run as hooks (`.claude/settings.json`)
because they must happen:

- **Session start:** `hooks/session_start.py` prints the map, the inbox, today's
  note, the index lines of the last three days and the memory index into the
  context. A block that ends with "cut here" is incomplete: read that file. The
  rest you do not need to open again.
- **After every edit of a note:** `hooks/after_edit.py` lints that one note and
  shows its findings.
- **Before stopping:** `hooks/stop_check.py` reminds once per session if you
  changed notes but not today's daily note.
- **Before compaction:** `hooks/pre_compact.py` tells the summary to keep open
  points and findings that are not filed yet.
