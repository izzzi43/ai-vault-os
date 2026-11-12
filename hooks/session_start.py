#!/usr/bin/env python3
"""SessionStart hook: prints the start sequence into the context, so it happens instead of being asked for.

What it prints, in this order and cut to fit: who I am and the active priorities, the inbox, today's note,
the index lines of the last three days, the memory index, and up to three notes that are due for review.
Plain stdout of a SessionStart hook is added to the context. Claude Code caps it at 10,000 characters and
shows only a preview beyond that, so this script stays under BUDGET and says what it cut.

    python3 hooks/session_start.py [vault-root]

Standard library only. Reads, never writes. Never fails the session: on any error it prints one line and exits 0.
"""
import re
import sys
from datetime import date, timedelta
from pathlib import Path

BUDGET = 9000
SHARE = {"index": 1600, "inbox": 2000, "today": 1600, "days": 1000}   # characters per block; memory gets what is left
WHO = ("Who I am", "Wer ich bin")                       # section titles in Vault-Index.md, in the languages seen so far
PRIORITIES = ("Active priorities", "Aktive Prioritäten")
GUARDRAILS = ("Guardrails",)                             # the section of the memory index that is shown first


def cut(text, limit, where):
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit("\n", 1)[0] + f"\n[cut here: {len(text) - limit} more characters. Read {where} before relying on this block.]"


def section(text, titles):
    for title in titles:
        m = re.search(rf"^##\s+{re.escape(title)}\s*$(.*?)(?=^##\s|\Z)", text, re.S | re.M)
        if m:
            return m.group(1).strip()
    return ""


def index_lines(text):
    """The keyword block at the top of a daily note: everything before the first '---' or '## '."""
    out = []
    for line in text.splitlines()[1:]:
        if line.strip() == "---" or line.startswith("## "):
            break
        if line.strip():
            out.append(line.strip())
    return " ".join(out)


def read(p):
    return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""


def main():
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    today = date.today()
    out = [f"# Vault start block ({today.isoformat()}), printed by hooks/session_start.py",
           "The start sequence, already done for you. A block that ends with 'cut here' is incomplete: "
           "read that file before you rely on it. Everything else you do not need to open again."]

    idx = read(root / "Vault-Index.md")
    who, prio = section(idx, WHO), section(idx, PRIORITIES)
    if who or prio:
        out.append("## Who I am and what matters now\n" + cut((who + "\n\n" + prio).strip(), SHARE["index"], "Vault-Index.md"))

    inbox = read(root / "00-inbox.md")
    body = "\n".join(l for l in inbox.splitlines()[1:] if l.strip())
    out.append("## Inbox (open handovers, these come first)\n" + (cut(body, SHARE["inbox"], "00-inbox.md") or "empty"))

    daily = root / "01-daily"
    note = daily / f"{today.isoformat()}.md"
    if note.is_file():
        out.append(f"## Today's note ({note.name})\n" + cut(read(note), SHARE["today"], f"01-daily/{note.name}"))
    else:
        out.append(f"## Today's note\nMissing. Create 01-daily/{today.isoformat()}.md from the template before the first finding.")
    lines = []
    if daily.is_dir():
        earlier = sorted((p for p in daily.glob("20??-??-??.md") if p.stem < today.isoformat()), reverse=True)[:3]
        for p in earlier:
            lines.append(f"- {p.stem}: {index_lines(read(p)) or '(no index lines)'}")
    out.append("## The last three days (index lines)\n" + (cut("\n".join(lines), SHARE["days"], "01-daily/") or "no earlier notes"))

    mem = read(root / "90-memory" / "MEMORY.md")
    if mem:
        left = max(1200, BUDGET - 400 - sum(len(x) for x in out))
        guard = ""
        for title in GUARDRAILS:                 # the rules that must apply unasked go first, they are cut last
            m = re.search(rf"^##\s+{title}.*?$(.*?)(?=^##\s|\Z)", mem, re.S | re.M)
            if m:
                guard = m.group(0).strip()
                mem = mem.replace(m.group(0), "")
                break
        text = (guard + "\n\n" + mem.strip()).strip() if guard else mem
        out.append("## Memory index (guardrails first; open a file when its hook matches the task)\n"
                   + cut(text, left, "90-memory/MEMORY.md"))

    due = []
    areas = root / "02-areas"
    if areas.is_dir():
        for p in sorted(areas.glob("*.md")):
            text = read(p)
            r = re.search(r"^reviewed:\s*(\d{4})-(\d{2})-(\d{2})", text, re.M)
            t = re.search(r"^ttl:\s*(\d+)", text, re.M)
            if r and t:
                d = date(*map(int, r.groups())) + timedelta(days=int(t.group(1)))
                if d < today:
                    due.append((d, p.name))
    if due:
        out.append("## Due for review (check against reality when you touch them)\n"
                   + "\n".join(f"- 02-areas/{n}, due since {d.isoformat()}" for d, n in sorted(due)[:3]))

    text = "\n\n".join(out)
    if len(text) > BUDGET:
        text = text[:BUDGET].rsplit("\n", 1)[0] + "\n[cut: start block over budget]"
    print(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:                      # a broken hook must never block a session
        print(f"Vault start block failed ({type(e).__name__}: {e}). Read Vault-Index.md, the inbox and today's note by hand.")
    sys.exit(0)
