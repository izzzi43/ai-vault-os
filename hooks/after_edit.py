#!/usr/bin/env python3
"""PostToolUse hook for Write and Edit: lints the one note that was just changed and reports only its findings.

Silent when the file is not a note in the vault or has no findings, so it costs nothing in the normal case.

    python3 hooks/after_edit.py [vault-root]      (reads the hook JSON on stdin)
"""
import json
import subprocess
import sys
from pathlib import Path


MAX_LINES = 6        # a note with many old findings must not flood the context on every edit


def main():
    data = json.load(sys.stdin)
    path = (data.get("tool_input") or {}).get("file_path") or ""
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    p = Path(path)
    if p.suffix != ".md" or root not in p.resolve().parents:
        return
    lint = Path(__file__).resolve().parent.parent / "tools" / "vault_lint.py"
    r = subprocess.run([sys.executable, str(lint), str(root), "--file", str(p)], capture_output=True, text=True, timeout=20)
    lines = r.stdout.strip().splitlines()
    if r.returncode == 1 and lines:
        more = f"\n... and {len(lines) - MAX_LINES} more: python3 tools/vault_lint.py --file <note>" if len(lines) > MAX_LINES else ""
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext":
              "Vault lint on the note you just changed:\n" + "\n".join(lines[:MAX_LINES]) + more}}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
