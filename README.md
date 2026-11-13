# AI Vault OS

A memory for coding agents, made of plain Markdown files. Works with Claude Code and opens in Obsidian.

Agents forget everything between sessions. The usual fix is a bigger context
window. This is the other fix: **write things down where the agent will find
them, and make writing them down part of the work.**

I have run this daily for months across client work, ads, code and personal
planning. This repo is the empty scaffold, with the rules that make it survive
contact with reality.

**It is for you if** you work with an agent every day, on the same projects, and
you are tired of explaining the same context again each morning.

---

## The problem

Ask your agent what you worked on a week ago. If it cannot answer, you do not
have a memory system. You have a chat log.

The failure is never storage. It is that findings get *explained* in a session
and never *filed*. The next session starts from zero and you explain it all
again.

## How a session runs

```
start      The agent reads the map, the inbox, today's note, the last three days
           and the list of rules. A small script does this for it, every time.
   |
work       You work as usual. The agent looks things up in the notes before it
           answers: index first, then search.
   |
write      The moment something comes up that you will still need tomorrow, it
back       goes into today's note and into the note for that topic. In the same
           reply, not at the end.
   |
checkpoint You say "checkpoint". The agent completes today's note, checks the
           notes it touched against reality, runs the check script, commits.
```

That is the whole system. The rest of this page is detail.

## Start in five minutes

1. Copy this folder to wherever you keep notes. Open it in Obsidian if you like
   to see the notes and their links.
2. Fill in "Who I am" in `Vault-Index.md`. The agent reads it before anything
   else, so make it honest rather than impressive.
3. Open the folder in Claude Code. **Before you trust the folder, read
   [What runs on its own](#what-runs-on-its-own):** four small scripts start
   automatically.
4. Start today's note from `01-daily/_TEMPLATE.md`.
5. Work. Before you stop, say **"checkpoint"**.

You need `python3` for the scripts. Nothing else is installed.

## What is in the folder

| Path | What it holds |
|---|---|
| `CLAUDE.md` | The manual the agent loads in every session |
| `Vault-Index.md` | The map: who you are, what the folders hold, your priorities |
| `00-inbox.md` | Open handovers. Read first, cleared first, never a parking lot |
| `01-daily/` | One note per day, with a few keyword lines on top |
| `02-areas/` | The knowledge. One standing note per area you are responsible for |
| `90-memory/` | Rules about how you want to be worked with. One file per rule, plus an index |
| `hooks/` | The scripts that run on their own |
| `tools/` | The check script, the search, and their tests |
| `eval/` | A small fixed test, so a change comes with numbers |

Two of these are easy to mix up. **Areas hold knowledge about your world**
(how a system works, what was decided). **Memory holds rules about the work
itself** (how to write to a client, what never to do unasked). A fact about your
world never goes into memory, a rule about behaviour never into an area.

---

## The seven rules

Most note systems die of bloat, or of being written to once and never read. The
first six are what kept mine alive, ordered by how often I have broken them. The
seventh is newer and says so.

**1. Follow the index before you search.**
If a note on the topic exists, read it before answering. Never produce a list
from memory when the vault holds one. And "X is missing" is a claim that needs a
source: an invented gap sends you off building something you already have.

**2. Write back immediately, not at the end.**

> The moment the agent explains something you will still need tomorrow, it goes
> into the vault in the same reply.

Sessions get interrupted. A finding that lives only in the chat is a finding you
will lose, and you will not notice until you need it.

**3. Consolidate instead of creating.**
Before adding a note, check whether an existing one can take it. A new note in a
folder means updating that folder's index in the same move. Skipping that is the
most common way a vault drifts.

**4. Every fact is timeless, dated, or a pointer.**

| Kind | Example | How to write it |
|---|---|---|
| **Timeless** | How a system works, a decision, who owns what | Write it, keep it |
| **Dated** | What was true at a point in time | Add `(as of YYYY-MM-DD)` and the source |
| **Pointer** | Numbers, status, prices, balances | **Do not copy.** Link the live source |

Copied status facts are the real source of drift. They go stale quietly and
nobody notices. When in doubt which kind a fact is, it is almost always a
pointer. When a dated fact or a decision changes, the old line is not deleted:
it moves to a section "Earlier" with the date it held until and the reason.

**5. Search before you build, but only for infrastructure.**
Someone has already built the scheduler, the scraper, the dashboard. Take theirs.
But whatever produces your own judgment, the loop where you learn from your own
results, is the one thing worth building yourself and the one thing you must
never outsource.

**6. The second time something goes wrong, write the rule.**
Not the third, not the tenth. The second time is the signal that it is a pattern
and not bad luck. One line in the memory folder, with the reason, costs a minute
and saves the next hour.

**7. Give reading a budget.**
A vault that works grows, and then the agent reads all of it before every task.
More context is not more knowledge: past a point the rules that matter drown in
the ones that do not. So every long note gets a **head**, a short block at the
top with what applies to almost every task. The agent's must-read list is a few
heads, not a few files. Everything else stays in the note and is read **on
condition**: "read the pricing section only when the task is about pricing."
Nothing is deleted. It moves below the head and gets a trigger.

*Status: newer than the other six. In my own setup this cut the must-read text
per task by roughly 80 percent. In a small fixed test set (10 tasks, before and
after) the checked answers held, and the amount actually read became far more
even across tasks. Total reading dropped by about a quarter, which is within
twice the run-to-run noise, so treat that part as a hint, not a result.*

**Behind all seven: one truth per fact.** Two places holding the same fact means
one gets maintained and the other goes stale in silence. Link the source, never
copy it. That applies to indexes too: an index points, it does not store.

---

## What runs on its own

A rule in `CLAUDE.md` is a request. The agent usually follows it, but not
always. A **hook** is a script that Claude Code runs by itself at a fixed moment,
so the thing happens every time. This repo ships four, registered in
`.claude/settings.json`. They start once you trust the folder.

All four only read your notes and print text. None writes a note, none runs
anything that stands in a note, none uses the network.

| When | Script | What it does |
|---|---|---|
| A session starts, or a long chat was just compressed | `hooks/session_start.py` | Puts the start sequence in front of the agent: who you are, priorities, inbox, today's note, the keyword lines of the last three days, the list of rules. Stays under 10,000 characters and says where it cut. |
| The agent edited a note | `hooks/after_edit.py` | Checks that one note and shows at most six problems. Silent otherwise. |
| The agent is about to stop | `hooks/stop_check.py` | Reminds it once per session if it changed notes but not today's note. Looks only at what this session wrote. |
| A long chat is about to be compressed | `hooks/pre_compact.py` | Asks that findings which are not filed yet survive the summary. |

To switch them off, delete `.claude/settings.json` or set
`"disableAllHooks": true` in it. On Windows, change `python3` to `python` in
that file.

### Three things that fail without telling you

Found while cutting the start context of a working setup (November 2026, Claude
Code 2.1). Each one looked fine and was not.

1. **A rule file with `paths:` only loads when the session started in the folder
   that holds `.claude/rules/`, or in a folder above it.** Then it loads as soon
   as a matching file is read, also through `sed` in the shell. A session that
   started somewhere else and opens the same file by its full path loads
   nothing. If your agents start in another folder, name the rule file in the
   agent's own instructions. Test it: start a short session, read one matching
   file, and look for a `nested_memory` entry in the transcript.
2. **A hook that answers "ask" is no guard when the session runs with all
   permissions granted.** The question is approved without anyone seeing it. A
   guard that must hold has to block (exit code 2). Test every guard once with
   a real, harmless call in a new session, not only with made-up input.
3. **Two config folders mean two memories.** If you run Claude Code with two
   profiles (`CLAUDE_CONFIG_DIR`), each keeps its own auto-memory for the same
   project. Rules learned in one are missing in the other. Point both at one
   folder with a symlink.

## The tools

```
python3 tools/vault_lint.py            checks the vault against the rules
python3 tools/vault_search.py "words"  finds the note you mean
python3 tools/test_tools.py            tests for both, and for the hooks
```

**The check** (a "lint") turns the rules into numbers. It reports broken links,
notes that nothing links to, rules missing from the index, long notes without a
head, dates without a year, notes past their review date, old inbox items, more
than five priorities, and an inbox or rule list too long for the start block.
It is step 4 of the checkpoint. On a real vault of 537 notes it takes about a
quarter of a second.

**The search** needs no index and no database. It ranks by where a word is
found: the one-line description and the title first, then the head, then the
keyword lines of daily notes, then the rest. Per word only its best place
counts, so a long note cannot win by length.

**Consolidate.** Say "consolidate" once a week. The agent reads the last seven
days, finds what repeated, and proposes at most five changes, each with the
notes it comes from. It writes nothing before you agree.

**Audit.** Say "audit" once a quarter. The check script finds broken links, it
cannot tell whether a rule is still true. The agent reads every rule and every
head and holds it against the thing it talks about: does the script still live
there, is the routine still paused, do two rules disagree. It corrects only what
it can prove and brings you the rest as a short list of decisions. On my own
memory of 95 rules the first run found about two thirds true, a handful with
moved paths, and fourteen that needed me. None of those looked broken.

## What is measured, and what is not

`eval/` holds ten fixed questions against a small sample vault. The first run
compared the hooks and tools against the plain manual, three times each. Details
are in `eval/results.md`.

- The agent needed far fewer steps: about 25 tool calls per ten questions
  instead of about 66.
- Every answer was correct, with and without.
- The total text in front of the agent was **not** lower. The start block and
  the longer manual cost about what the saved reading gained.

So the honest claim is "fewer steps to the same answer", not "less context".
Everything that has to do with writing (the check after edits, the reminder
before stopping, review dates, consolidate) is **not measured yet**: the test
only reads. Each script lists its known limits at the top.

To measure a change of your own, see `eval/README.md`.

## What this is not

It is not a plugin, a framework or a service, and it has no database. It is a
folder with a convention, a page of rules, and a handful of small scripts you
can read in an afternoon and delete without breaking the rest. If it does not
fit how you work, change it. That is the point of shipping it empty.

## License

MIT
