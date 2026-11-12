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
| **Dated** | What was true at a point in time | Add `(as of YYYY-MM-DD)` and the source |
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
hooks/             what is enforced: start block, lint after edits, reminder before stopping
tools/             vault_lint.py and vault_search.py, plus their tests
eval/              a small fixed test, so a change comes with numbers
.claude/           settings.json that registers the hooks, and the consolidate skill
```

## Getting started

1. Copy this folder to wherever you keep notes and open it in Obsidian.
2. Fill in the "Who I am" paragraph in `Vault-Index.md`. The agent reads it
   before anything else, so make it honest rather than impressive.
3. Point your agent at `CLAUDE.md`.
4. Start today's note from `01-daily/_TEMPLATE.md`.
5. While you work, not at the end of the day: the moment something comes up that
   you will still need tomorrow, it goes into the daily note and the affected
   area note. Before you stop, say **"checkpoint"** to catch what slipped.

That last step is the whole system. Everything else is filing.

## The checkpoint command

Say **"checkpoint"** and the agent should:

1. Extend today's note with everything since the last entry
2. Check every note touched this session for drift against reality
3. Update folder index notes
4. Commit

Running this at the end of a working session is what stops the vault rotting.

## What runs automatically

**Read this before you open the folder in Claude Code.** The repo ships hooks in
`.claude/settings.json`. Once you trust the folder, four small Python scripts run
on their own. They only read the vault and print text; none of them writes a note,
none runs anything from a note, none uses the network.

| When | Script | What it does |
|---|---|---|
| Session start, and after a compaction | `hooks/session_start.py` | Prints the start sequence into the context: who you are, priorities, inbox, today's note, the index lines of the last three days, the memory index. Stays under 10,000 characters and says where it cut. |
| After every edit of a note | `hooks/after_edit.py` | Lints that one note and shows at most six findings. Silent otherwise. |
| Before Claude stops | `hooks/stop_check.py` | Reminds once per session if the session changed notes but not today's daily note. Looks only at what this session wrote. |
| Before a compaction | `hooks/pre_compact.py` | Asks the summary to keep findings that are not filed yet. |

To switch them off, delete `.claude/settings.json` or set `"disableAllHooks": true`
in it. They need `python3` on the path (on Windows, change the command to `python`).

Why hooks at all: a rule in `CLAUDE.md` is a request. A hook is the only way to make
something happen every time.

## The tools

```
python3 tools/vault_lint.py            what the rules ask for, as numbers
python3 tools/vault_search.py "words"  ranked search without an index or a database
python3 tools/test_tools.py            tests for both and for the hooks
```

**The lint** reports broken links, notes in areas and memory that nothing links
to, memory files missing from the index, long notes without a head, dated facts
without a year, notes past their review date, old inbox items, more than five
priorities, and an inbox or memory index too long for the start block. It runs as
step 4 of the checkpoint. On a real vault of 537 notes it takes about a quarter
of a second.

**The search** ranks by where a word is found: the `description:` line and the
title first, then the head, then the index lines of daily notes, then the text.
Per word only its best place counts, so a long note cannot win by length.

Say **"consolidate"** once a week: the agent reads the last seven days, finds what
repeated and proposes at most five changes, each with its evidence. It writes
nothing before you agree.

## What is measured, and what is not

`eval/` holds ten fixed questions against a small sample vault. The first run
compared this setup against the plain manual, three times each (`eval/results.md`):

- Tool calls per ten questions fell from about 66 to about 25.
- Every answer was correct in both variants.
- The total text in the context was **not** lower: the start block and the longer
  manual cost about what the saved reading gained.

So the honest claim is "fewer steps to the same answer", not "less context". The
lint after edits, the stop reminder, the review dates and the consolidate skill
are **not measured yet**: the eval only reads. Known limits of the lint and the
search are listed at the top of each script. Treat everything in this section as
newer than the seven rules.

---

## The seven rules

Most note systems die of bloat, or of being written to once and never read. The
first six are what kept mine alive, ordered by how often I have broken them. The
seventh is newer and says so.

**1. Follow the hub before you search.**
If a note on the topic exists, read it before answering. Never produce a list from
memory when the vault holds one. And "X is missing" is a factual claim that needs a
source — an invented gap sends you off building something you already have.

**2. Write back immediately, not at the end.**
The moment you explain something that will still matter tomorrow, file it in the
same reply. Sessions get interrupted. A finding that lives only in the chat is a
finding you will lose, and you will not notice until you need it.

**3. Consolidate instead of creating.**
Before adding a note, check whether an existing one can absorb it. And a new note
in a folder means updating that folder's index in the same move — skipping that is
drift source number one.

**4. Every fact is timeless, dated, or a pointer.**
Timeless facts go in and stay. Dated facts get `(as of YYYY-MM-DD)` and a source.
Anything that changes fast — numbers, status, prices, balances — is a pointer:
link the live source, never copy the value. Copied status facts go stale quietly,
which is worse than being wrong loudly.

**5. Search before you build, but only for infrastructure.**
Someone has already built the scheduler, the scraper, the dashboard. Take theirs.
But whatever produces your own judgment — the loop where you learn from your own
results — is the one thing worth building yourself, and the one thing you must
never outsource.

**6. The second time something goes wrong, write the rule.**
Not the third, not the tenth. The second occurrence is the signal that it is a
pattern and not bad luck. One line in the memory folder, with the reasoning, costs
a minute and saves the next hour.

**7. Give reading a budget.**
A vault that works grows, and then the agent reads all of it before every task.
More context is not more knowledge: past a point the rules that matter drown in
the ones that do not. So every long note gets a **head**, a short block at the
top with the rules that apply to almost every task, and the agent's must-read
list is a few heads, not a few files. Everything else stays in the note and is
read **on condition**: "read the pricing section only when the task is about
pricing." Nothing is deleted. It moves below the head and gets a trigger.

*Status: newer than the other six. In my own setup this cut the must-read text
per task by roughly 80 percent. In a small fixed test set (10 tasks, before and
after) the checked answers held, and the amount actually read became far more
even across tasks. Total reading dropped by about a quarter, which is within
twice the run-to-run noise, so treat that part as a hint, not a result.*

## One truth per fact

Two places holding the same fact means one gets maintained and the other goes
stale in silence. Link canonical sources; never copy them. This applies to the
index too — the index points at memories, it does not contain them.

## What this is not

It is not a plugin, a framework, or a dependency. It is a folder with a
convention and about a page of rules. If it does not fit how you work, change
it — that is the point of shipping it empty.

## License

MIT
