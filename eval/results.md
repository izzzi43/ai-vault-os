# Eval results

One block per change, newest on top. Numbers come from `eval/run.py` on the sample vault from
`eval/make_vault.py`. Read `eval/README.md` for what the numbers can and cannot say.

## 2026-11-13: hooks, tools and the longer manual against the manual on main

- **Before:** `CLAUDE.md` from main (commit db6e285), no hooks. **After:** this branch, hooks on.
- Same 15 notes in both, including heads and descriptions, so this compares "hooks plus new manual" only.
- 10 tasks, 3 repeats each, 60 fresh headless sessions, model claude-opus-5-5, read-only tools.

| | before | after |
|---|---|---|
| answers correct (word check; the two it failed were read by hand and are right) | 30 | 30 |
| tool calls per 10 tasks (3 runs) | 57, 73, 69 | 26, 27, 23 |
| characters the agent asked for (tool results) | 47,309 / 37,041 / 38,040 | 15,308 / 13,438 / 12,903 |
| characters it got without asking (manual, start block) | 26,410 | 66,330 |
| both together | 73,719 / 63,451 / 64,450 | 81,638 / 79,768 / 79,233 |

What this says:

- **Fewer steps.** Tool calls dropped by about 60 percent. The three start-block questions (inbox, last days,
  priorities) needed no file read at all with hooks, 15 to 17 calls per three runs without.
- **Not less text.** Asked-for reading fell by about two thirds, but the start block and the longer manual
  are text too. Together the after variant carried about 19 percent more characters. The before runs
  differ by 16 percent among themselves, so call it "not lower", not "higher".
- **No difference in correctness.** Without hooks the agent followed the start sequence anyway, on this
  model and this small vault. Enforcement did not change an answer here.

What it does not say: anything about a large vault (15 notes are cheap to read either way), about writing
back (the eval allows no edits, so the stop reminder and the lint after edits were not exercised), or about
other models. The word-check judge marked two correct answers wrong ("went missing" for "lost"); both were
read by hand and counted as correct, and the pattern was widened afterwards. Input tokens were not recorded
in this run; `run.py` records them from now on.
