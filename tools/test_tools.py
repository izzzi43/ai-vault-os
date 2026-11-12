#!/usr/bin/env python3
"""Tests for the lint, the search and the hooks, on a vault built in a temp folder. No network, no cost.

    python3 tools/test_tools.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FAILED = []


def check(ok, text):
    print(("ok   " if ok else "FAIL ") + text)
    if not ok:
        FAILED.append(text)


def run(script, *args, stdin=None):
    r = subprocess.run([sys.executable, str(REPO / script), *map(str, args)], input=stdin, capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def main():
    with tempfile.TemporaryDirectory() as tmp:
        v = Path(tmp) / "vault"
        rc, out = run("eval/make_vault.py", v)
        check(rc == 0, "sample vault builds")
        rc, out = run("tools/vault_lint.py", v, "--json")
        data = json.loads(out)
        check(rc == 1 and data["stats"]["by_check"] == {"stale": 1}, "clean sample vault: one finding, the note that is due for review")
        check(data["stats"]["core_orphans"] == 0 and data["stats"]["core_notes"] == 7, "seven core notes, none orphaned")

        (v / "02-areas" / "lonely.md").write_text("# Lonely\n\nSee [[nowhere]] and [gone](gone.md). ![[photo.png]] Price (as of 12.11.). Time (Stand 14:30). Fine (as of Oct 2026).\n" + "line\n" * 90, encoding="utf-8")
        (v / "90-memory" / "feedback_new.md").write_text("---\nname: x\n---\nA rule.\n", encoding="utf-8")
        old = (date.today() - timedelta(days=30)).isoformat()
        with (v / "00-inbox.md").open("a", encoding="utf-8") as f:
            f.write(f"- {old}: something that never happened\n")
        idx = v / "Vault-Index.md"
        idx.write_text(idx.read_text(encoding="utf-8") + "4. four\n5. five\n6. six\n", encoding="utf-8")
        rc, out = run("tools/vault_lint.py", v, "--json")
        by = json.loads(out)["stats"]["by_check"]
        for name in ("broken-link", "orphan", "not-in-index", "no-head", "no-year", "old-inbox", "priorities", "stale"):
            check(by.get(name, 0) >= 1, f"lint finds: {name}")
        rc, out = run("tools/vault_lint.py", v, "--file", v / "02-areas" / "returns.md")
        check(rc == 0 and not out.strip(), "--file on a clean note: silent, exit 0")
        rc, out = run("tools/vault_lint.py", v, "--file", v / "02-areas" / "lonely.md")
        check(out.count("broken-link") == 2 and out.count("no-year") == 1,
              "lint: wikilink and markdown link broken, attachment ignored, only the date without a year is reported")
        (v / "02-areas" / "open.md").write_text("---\nreviewed: YYYY-MM-DD\nttl: 90 days\n---\n# Open\n<!-- HEAD -->\nnever closed\n[[shipping]]\n", encoding="utf-8")
        rc, out = run("tools/vault_lint.py", v, "--file", v / "02-areas" / "open.md")
        check("never closed" in out and "not filled in" in out, "lint: unclosed head and unfilled review fields are reported")
        rc, out = run("tools/vault_lint.py", v / "nope")
        check(rc == 2, "missing folder: exit 2")

        rc, out = run("tools/vault_search.py", "return window", v, "--json")
        check(json.loads(out)[0]["file"] == "02-areas/returns.md", "search: the note whose description matches comes first")
        rc, out = run("tools/vault_search.py", "wick supplier", v, "--json")
        check("01-daily" in json.loads(out)[0]["file"], "search: a fact that lives only in a daily note is found")
        rc, out = run("tools/vault_search.py", "zzzqqq", v)
        check(rc == 1, "search without a hit: exit 1")

        rc, out = run("hooks/session_start.py", v)
        check(rc == 0 and "Vault start block" in out and "glass supplier" in out and "No refund without a scan" in out
              and len(out) < 10_000, "start block: inbox and memory index are in it, under 10,000 characters")
        (v / "00-inbox.md").write_text("# Inbox\n" + "- a long line of handover text\n" * 2000, encoding="utf-8")
        rc, out = run("hooks/session_start.py", v)
        check(len(out) < 10_000 and "cut here" in out, "start block with a huge inbox: still under the cap, says what it cut")
        rc, out = run("hooks/session_start.py", v / "nope")
        check(rc == 0, "start block on a missing vault: exit 0, never blocks a session")

        note = v / "01-daily" / f"{date.today().isoformat()}.md"

        def transcript(*paths):
            t = Path(tmp) / "t.jsonl"
            t.write_text("\n".join(json.dumps({"message": {"content": [{"type": "tool_use", "name": "Edit",
                         "input": {"file_path": str(q)}}]}}) for q in paths) + "\n", encoding="utf-8")
            return t

        def stop(t, sid, active=False):
            return run("hooks/stop_check.py", v, stdin=json.dumps({"transcript_path": str(t), "session_id": sid,
                                                                  "stop_hook_active": active}))[1]
        sid = f"test-{os.getpid()}-{time.time()}"
        out = stop(transcript(v / "02-areas" / "shipping.md"), sid)
        check("additionalContext" in out and "shipping.md" in out, "stop check: session changed a note, not the daily note: reminds")
        check(not stop(transcript(v / "02-areas" / "shipping.md"), sid).strip(), "stop check: only once per session")
        check(not stop(transcript(v / "02-areas" / "shipping.md"), sid + "b", active=True).strip(),
              "stop check: silent when already continuing because of a stop hook")
        check(not stop(transcript(v / "02-areas" / "shipping.md", note), sid + "c").strip(),
              "stop check: silent when the daily note was written too")
        check(not stop(transcript(), sid + "d").strip(), "stop check: silent when this session wrote nothing (other sessions do not count)")
        check(not stop(transcript(v / "02-areas" / "_TEMPLATE.md", "/tmp/elsewhere.md"), sid + "e").strip(),
              "stop check: templates and files outside the vault do not count")
        check(not run("hooks/stop_check.py", v, stdin="not json")[1].strip(), "stop check: broken input: silent")

        rc, out = run("hooks/after_edit.py", v, stdin=json.dumps({"tool_input": {"file_path": str(v / "02-areas" / "lonely.md")}}))
        check("broken-link" in out, "after edit: reports the findings of the changed note")
        rc, out = run("hooks/after_edit.py", v, stdin=json.dumps({"tool_input": {"file_path": "/tmp/other.py"}}))
        check(not out.strip(), "after edit: silent for files outside the vault")
        rc, out = run("hooks/pre_compact.py", v)
        check("not yet written into the vault" in out, "pre compact: prints instructions for the summary")
        json.loads((REPO / ".claude" / "settings.json").read_text(encoding="utf-8"))
        check(True, "settings.json is valid JSON")
    print("\n" + ("all green" if not FAILED else f"{len(FAILED)} failed"))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
