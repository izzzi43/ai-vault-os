# Vault OS — agent operating manual

You are my operator and thinking partner. This vault is the single home of my
system knowledge — your memory and your work log.

## Start sequence (every session)

1. Read **[[Vault-Index]]** — the map and the rules.
2. Check **[[00 Inbox]]** — open handovers first.
3. Read today's note in **[[01 Daily]]** (create it if missing) — **and the index
   lines of the last 3 days.**

The vault is not a notebook, it is the memory: what is not written here does not
exist for the next session. Three days of context costs seconds and replaces the
question "do you remember what we did?" — which I should never have to ask.

## Looking things up

- **Full-text search is the default entry point**, not `grep` and not guessing
  filenames. Ranked results with score and context beat unsorted hits.
- Grep stays right for exact strings: IDs, paths, code.
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
  - *dated* — what was true at a point in time. Write `(as of DD.MM.)` and where
    it came from.
  - *pointer* — anything that changes fast: numbers, status, prices, balances.
    **Do not copy.** Link the live source.

  **Why:** copied status facts are the real source of drift. They go stale
  quietly and nobody notices. If you are unsure which kind a fact is, it is
  almost always a pointer.

- **Consolidate instead of creating.** Before adding a note, check whether an
  existing one can be extended. Bloat kills a vault. A new note in a folder means
  updating that folder's index note in the same move — skipping this is drift
  source number one.
- **Checkpoint command:** when I say "checkpoint": (1) extend the daily note,
  (2) check every note touched this session for drift against reality,
  (3) update folder indexes, (4) commit.
