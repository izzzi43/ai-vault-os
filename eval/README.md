# Measuring a change

A rule that cannot be measured is an opinion. This folder holds a small fixed test so a change to the
manual, the hooks or the tools comes with numbers.

```
python3 eval/make_vault.py /tmp/vault-after                      # this branch, hooks on
git show main:CLAUDE.md > /tmp/before.md
python3 eval/make_vault.py /tmp/vault-before --manual /tmp/before.md --no-hooks
python3 eval/run.py /tmp/vault-before --label before --repeat 3
python3 eval/run.py /tmp/vault-after  --label after  --repeat 3
```

Each task starts a fresh headless `claude -p` session, so 10 tasks times 3 repeats times 2 variants are
60 short sessions on your plan. Results land in `eval/runs/` (ignored by git: answers quote the vault).

## Reading the numbers

- **Run every variant at least three times.** The spread between runs of the same variant is the noise. A
  difference smaller than that spread is not a result.
- **`chars_read` alone flatters hooks.** It counts what the agent asked for. What a hook or a longer manual
  puts into the context is `chars_given`. Compare the sum, or `input_tokens`.
- **`correct` is a word check.** It matches patterns, it does not read. It can fail a right answer and pass
  a wrong one. Read every miss and a sample of the passes before you write a number down.
- **The sample vault is small.** Fifteen notes are cheap to read whatever the rules say. Run against a copy
  of your own vault for numbers that mean something for you, with your own tasks in `tasks.json`.
- **Only reading is measured.** Tools are read-only in the eval, so nothing here says whether writing back
  got better.

Write the outcome into `results.md`, including what did not improve.
