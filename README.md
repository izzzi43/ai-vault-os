# AI Vault OS

A memory system for coding agents, built on plain Markdown and Obsidian.

Agents forget everything between sessions. The usual fix is a bigger context
window. This is the other fix: **write things down where the agent will find
them, and make writing them down part of the work.**

I have run this daily for months across client work, ads, code and personal
planning. This repo is the empty scaffold, with the rules that make it survive
contact with reality.

---

## The problem it solves

Ask your agent what you worked on a week ago. If it cannot answer, you do not
have a memory system — you have a chat log.

The failure is never storage. It is that findings get *explained* in a session
and never *filed*, so the next session starts from zero and you re-explain the
same context. Again.

## The three ideas

**1. The daily note is a chronicle, not an encyclopedia.**
Each day gets one file with a keyword index on top. The index is what future
sessions read first; it is a search accelerator, not a summary. Knowledge itself
lives in area notes, and the daily note points at them.

**2. Writing back is mandatory and immediate.**

> The moment the agent explains something you will still need tomorrow, it goes
> into the vault in the same reply.

Not at the end of the session. Sessions get interrupted, and a finding that only
exists in the chat is a finding you will lose.

**3. Every fact is timeless, dated, or a pointer.**

| Kind | Example | How to write it |
|---|---|---|
| **Timeless** | How a system works, a decision, ownership | Write it, keep it |
| **Dated** | What was true at a point in time | Add `(as of DD.MM.)` and the source |
| **Pointer** | Numbers, status, prices, balances | **Do not copy.** Link the live source |

Copied status facts are the real source of drift. They go stale quietly and
nobody notices. When in doubt which kind a fact is, it is almost always a
pointer.

---

## Structure

```
CLAUDE.md          the operating manual the agent loads every session
Vault-Index.md     the map: who you are, what the folders hold, active priorities
00-inbox.md        open handovers, cleared first
01-daily/          one note per day, keyword index on top
02-areas/          standing knowledge, one note per area of responsibility
90-memory/         distilled rules, one file per fact, plus an index that points
```

## Getting started

1. Copy this folder to wherever you keep notes and open it in Obsidian.
2. Fill in the "Who I am" paragraph in `Vault-Index.md`. The agent reads it
   before anything else, so make it honest rather than impressive.
3. Point your agent at `CLAUDE.md`.
4. Start today's note from `01-daily/_TEMPLATE.md`.
5. At the end of each working day: *"Write the day into the daily note and update
   what changed in the area notes."*

That last step is the whole system. Everything else is filing.

## The checkpoint command

Say **"checkpoint"** and the agent should:

1. Extend today's note with everything since the last entry
2. Check every note touched this session for drift against reality
3. Update folder index notes
4. Commit

Running this at the end of a working session is what stops the vault rotting.

---

## What makes it survive

Most note systems die of bloat. Three rules keep this one small:

- **Consolidate instead of creating.** Extend an existing note before adding one.
- **One truth per fact.** Link canonical sources, never copy them. Two places for
  one fact means one gets maintained and the other goes stale in silence.
- **A new note means updating its folder index in the same move.** Skipping this
  is drift source number one.

## What this is not

It is not a plugin, a framework, or a dependency. It is a folder with a
convention and about a page of rules. If it does not fit how you work, change
it — that is the point of shipping it empty.

## License

MIT
