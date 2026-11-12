#!/usr/bin/env python3
"""Runs the eval tasks headless against a vault and counts what the agent read to answer them.

    python3 eval/run.py <vault-folder> --label after [--tasks T01,T05] [--repeat 3] [--out eval/runs]

For every task it starts a fresh `claude -p` session in the vault folder and records:
  correct       every `must` pattern matches the answer and no `must_not` pattern does (a word check, see tasks.json)
  files_read    how many tool calls the agent made (Read, Grep, Glob, Bash)
  chars_read    characters of all tool results: the reading the agent asked for
  chars_given   characters of CLAUDE.md plus the start block: the reading it got without asking
  input_tokens  input tokens of the whole session as the tool reports them, the honest total
  hook_seen     whether the start block from hooks/session_start.py reached the session
Compare chars_read + chars_given, or input_tokens. chars_read alone flatters the hooks.
Each run costs usage on your Claude plan. Ten tasks, three repeats, two variants are 60 short sessions.
Run every variant at least three times: the run-to-run difference is the noise you compare against.

Reads the vault, writes only into --out. Needs the `claude` command line tool.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MARKER = "Vault start block"
ALLOWED = "Read,Grep,Glob,Bash(python3 tools/vault_search.py:*),Bash(python3 tools/vault_lint.py:*)"


def judge(task, answer):
    """A word check, not a reader. It can pass a wrong answer that contains the words: read a sample of the passes."""
    ok = all(re.search(rx, answer, re.I | re.S) for rx in task["must"])
    return bool(ok) and not any(re.search(rx, answer, re.I | re.S) for rx in task.get("must_not", []))


def start_block_chars(vault):
    """Characters the session start hook puts into the context. They are reading too, the agent just did not ask for it."""
    r = subprocess.run([sys.executable, str(Path(vault) / "hooks" / "session_start.py"), str(vault)], capture_output=True, text=True)
    return len(r.stdout)


def run_task(vault, task, model, timeout):
    cmd = ["claude", "-p", task["question"], "--output-format", "stream-json", "--verbose", "--allowedTools", ALLOWED]
    if model:
        cmd += ["--model", model]
    try:
        r = subprocess.run(cmd, cwd=vault, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"id": task["id"], "error": "timeout"}
    answer, tools, chars, hook, model_seen, cost, tokens = "", 0, 0, False, None, None, None
    for line in r.stdout.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if MARKER in line and '"tool_result"' not in line and ev.get("type") != "assistant":
            hook = True                      # the start block as the hook delivered it, not a file the agent read
        if ev.get("type") == "system" and ev.get("subtype") == "init":
            model_seen = ev.get("model")
        msg = ev.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use":
                tools += 1
            elif block.get("type") == "tool_result":
                c = block.get("content")
                chars += len(c) if isinstance(c, str) else sum(len(x.get("text", "")) for x in c or [] if isinstance(x, dict))
        if ev.get("type") == "result":
            answer = ev.get("result") or ""
            cost = ev.get("total_cost_usd")
            u = ev.get("usage") or {}
            tokens = sum(int(u.get(k) or 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
    if not answer:
        return {"id": task["id"], "error": (r.stderr or "no answer")[-300:]}
    given = len((Path(vault) / "CLAUDE.md").read_text(encoding="utf-8")) + (start_block_chars(vault) if hook else 0)
    return {"id": task["id"], "about": task["about"], "correct": judge(task, answer), "files_read": tools,
            "chars_read": chars, "chars_given": given, "input_tokens": tokens, "hook_seen": hook, "model": model_seen, "cost_usd": cost, "answer": answer[:600]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("vault")
    ap.add_argument("--label", required=True, help="name of the variant, e.g. before, after")
    ap.add_argument("--tasks", help="comma separated ids, default all")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--model")
    ap.add_argument("--timeout", type=int, default=240)
    ap.add_argument("--out", default=str(HERE / "runs"))
    a = ap.parse_args(argv)
    vault = Path(a.vault).resolve()
    if not (vault / "Vault-Index.md").is_file():
        print(f"no vault at {vault} (Vault-Index.md missing). Build one with eval/make_vault.py.", file=sys.stderr)
        return 2
    if not shutil.which("claude"):
        print("the `claude` command line tool is not on the PATH", file=sys.stderr)
        return 2
    tasks = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    if a.tasks:
        tasks = [t for t in tasks if t["id"] in a.tasks.split(",")]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    rows = []
    for rep in range(1, a.repeat + 1):
        for t in tasks:
            try:
                row = run_task(vault, t, a.model, a.timeout)
            except Exception as e:                      # one odd event must not lose the whole run
                row = {"id": t["id"], "error": f"{type(e).__name__}: {e}"}
            row.update(label=a.label, repeat=rep)
            rows.append(row)
            print(f"{a.label} #{rep} {row['id']}: " + (row.get("error") or
                  f"{'ok ' if row['correct'] else 'MISS'} reads {row['files_read']:>2} chars {row['chars_read']:>6} hook {'yes' if row['hook_seen'] else 'no'}"),
                  flush=True)
    good = [r for r in rows if "error" not in r]
    summary = {"label": a.label, "date": stamp, "vault": str(vault), "runs": len(rows), "errors": len(rows) - len(good),
               "correct": sum(r["correct"] for r in good), "of": len(good),
               "chars_read_total": sum(r["chars_read"] for r in good), "chars_given_total": sum(r["chars_given"] for r in good),
               "input_tokens_total": sum(r["input_tokens"] or 0 for r in good), "tool_calls_total": sum(r["files_read"] for r in good),
               "hook_seen_in": sum(r["hook_seen"] for r in good), "models": sorted({r["model"] for r in good if r.get("model")})}
    path = out / f"{stamp}-{re.sub(r'[^a-z0-9-]', '-', a.label.lower())}.json"
    path.write_text(json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"written: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
