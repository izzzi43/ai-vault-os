#!/usr/bin/env python3
"""Stop hook: reminds once if this session changed notes in the vault but not today's daily note.

Rule 2 (write back immediately) is the rule that gets broken most. This makes the miss visible at the one
moment it can still be fixed. It reminds, it does not nag:
  - it looks only at what THIS session wrote (Write and Edit calls in its transcript), so a second session,
    Obsidian, a git pull or a fresh clone never trigger it
  - when Claude is already continuing because of a stop hook (`stop_hook_active`), it stays silent
  - it reminds once per session (a marker in the temp folder), not on every turn
  - a session that only answered a question owes no note

    python3 hooks/stop_check.py [vault-root]      (reads the hook JSON on stdin)

Standard library only. Never writes into the vault. On any error: silent, exit 0.
"""
import json
import sys
import tempfile
from datetime import date
from pathlib import Path

SKIP_DIRS = {".git", ".obsidian", "node_modules", ".claude", "eval", "tools", "hooks", ".trash"}


def written_by_session(transcript, root):
    """Vault notes this session wrote, in order, from the Write and Edit calls in its transcript."""
    out = []
    with open(transcript, encoding="utf-8", errors="replace") as f:
        for line in f:
            if '"tool_use"' not in line:
                continue
            try:
                content = (json.loads(line).get("message") or {}).get("content")
            except (ValueError, AttributeError):
                continue
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") in ("Write", "Edit", "MultiEdit"):
                    p = Path(str((block.get("input") or {}).get("file_path") or ""))
                    try:
                        rel = p.resolve().relative_to(root)
                    except ValueError:
                        continue
                    if p.suffix == ".md" and not (set(rel.parts[:-1]) & SKIP_DIRS) and not p.name.startswith("_"):
                        out.append(rel)
    return out


def main():
    data = json.load(sys.stdin)
    if data.get("stop_hook_active") or not data.get("transcript_path"):
        return
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    note = Path("01-daily") / f"{date.today().isoformat()}.md"
    written = written_by_session(data["transcript_path"], root)
    others = [p for p in written if p != note]
    if not others:
        return
    if note in written and written.index(note) >= 0 and max(i for i, p in enumerate(written) if p == note) >= \
            max(i for i, p in enumerate(written) if p != note) - 2:
        return                                   # the daily note was written at about the same time as the last change
    marker = Path(tempfile.gettempdir()) / f"vault-stop-{data.get('session_id', 'x')}"
    if marker.exists():
        return
    marker.write_text("reminded", encoding="utf-8")
    what = "was not updated after your last changes" if note in written else "was not touched"
    names = ", ".join(dict.fromkeys(str(p) for p in reversed(others)))[:300]
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext":
          f"Vault check: this session changed {names}, but today's daily note ({note}) {what}. "
          "Add what was shipped, decided and left open, with links to the area notes. "
          "If nothing worth keeping happened, say so in one line and stop."}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
