#!/usr/bin/env python3
"""Vault lint: counts what the rules ask for, so a broken rule shows up as a number.

Standard library only. Reads, never writes.

    python3 tools/vault_lint.py [vault-root] [--json] [--quiet] [--file changed.md]

Exit 0 when nothing is found, 1 when there are findings, 2 on bad input.
Folder names follow the template (00-inbox.md, 01-daily/, 02-areas/, 90-memory/); a vault that names
them differently passes --inbox, --daily, --areas, --memory.

Checks
  broken-link     a [[wikilink]] that points at no note
  orphan          a note in areas or memory that no other note links to
  not-in-index    a memory file that the memory index does not list
  no-head         an area note longer than --long lines without a <!-- HEAD --> block
  long-head       a head longer than --head-max lines
  no-year         "(as of 12.11.)": a dated fact without a year
  stale           a note whose `reviewed:` date plus `ttl:` days has passed
  old-inbox       an inbox line with a date older than --inbox-days
  priorities      more than five active priorities in the index
  memory-size     the memory index is close to the size where rules get dropped
  start-budget    the inbox or the memory index is longer than the start block can show

Known limits
  - Dates are found only inside brackets: "(as of 12.11.)". A bare "as of 12.11." in a sentence is not seen.
  - An inbox item counts only as a list item with a full date. Prose and dates without a year slip through.
  - "orphan" follows links only. A note that is named in plain text without a link still counts as orphaned.
  - Thresholds (80 lines, 25 head lines, 7 days) are starting values, not calibrated.
"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
MDLINK = re.compile(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)")
ASOF = re.compile(r"\(\s*(?:as of|Stand)\b:?\s*([^)]*)\)", re.I)
YEAR = re.compile(r"\b20\d\d\b")
DAY_MONTH = re.compile(r"\b\d{1,2}\.\s?\d{1,2}\.(?!\s?\d)|\b\d{1,2}/\d{1,2}\b(?!/)")     # 12.11. or 11/12, no year after it
START_SHARE = {"Vault-Index.md": 1600, "inbox": 2000, "memory": 3000}    # what hooks/session_start.py can show, in characters
ISO = re.compile(r"\b(20\d\d)-(\d\d)-(\d\d)\b")
DMY = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(20\d\d)\b")
SKIP_DIRS = {".git", ".obsidian", "node_modules", ".claude", "eval", "tools", "hooks", ".trash"}
CODE = re.compile(r"```.*?```|`[^`\n]*`", re.S)


def notes(root):
    for p in sorted(root.rglob("*.md")):
        if not (set(p.relative_to(root).parts[:-1]) & SKIP_DIRS):
            yield p


def frontmatter(text):
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    out = {}
    for line in text[4:end].splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip().strip("\"'")
    return out


def parse_day(text):
    m = ISO.search(text)
    if m:
        y, mo, d = map(int, m.groups())
    else:
        m = DMY.search(text)
        if not m:
            return None
        d, mo, y = map(int, m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def head(text):
    m = re.search(r"<!--\s*(?:HEAD|KOPF)\s*-->(.*?)<!--\s*/(?:HEAD|KOPF)\s*-->", text, re.S)
    return m.group(1).strip("\n") if m else None


def lint(root, a):
    today = date.today()
    files = list(notes(root))
    texts = {p: p.read_text(encoding="utf-8", errors="replace") for p in files}
    by_stem, by_rel = {}, {}
    for p in files:
        by_stem.setdefault(p.stem.lower(), []).append(p)
        by_rel[str(p.relative_to(root)).lower()] = p
    by_resolved = {p.resolve(): p for p in files}
    incoming = {p: set() for p in files}
    findings = []

    def add(check, p, line, msg):
        findings.append({"check": check, "file": str(p.relative_to(root)), "line": line, "message": msg})

    for p, text in texts.items():
        template = p.name.startswith("_")
        clean = CODE.sub(lambda m: " " * len(m.group(0)), text)
        for n, line in enumerate(clean.splitlines(), 1):
            for m in WIKILINK.finditer(line):
                target = m.group(1).strip()
                key = Path(target).name.lower()
                key = key[:-3] if key.endswith(".md") else key
                hit = by_stem.get(key) or ([by_rel[target.lower() + ".md"]] if target.lower() + ".md" in by_rel else [])
                if hit:
                    for h in hit:
                        if h != p:
                            incoming[h].add(p)
                elif (not template and "..." not in target and not (root / target).exists()
                      and Path(target).suffix.lower() in ("", ".md")):          # attachments ([[photo.png]]) are not notes
                    add("broken-link", p, n, f"[[{target}]] points at no note")
            for m in MDLINK.finditer(line):
                if "://" in m.group(1):
                    continue
                target_path = (p.parent / m.group(1)).resolve()
                h = by_resolved.get(target_path)
                if h is None:
                    if not template and not target_path.is_file():       # a file outside the vault that exists is fine
                        add("broken-link", p, n, f"({m.group(1)}) points at no note")
                elif h != p:
                    incoming[h].add(p)
            if not template:
                for m in ASOF.finditer(line):
                    inner = m.group(1)
                    if DAY_MONTH.search(inner) and not YEAR.search(inner):
                        add("no-year", p, n, f"dated fact without a year: {m.group(0)}")

    areas, memory = root / a.areas, root / a.memory
    index = next((memory / n for n in ("MEMORY.md", "_index.md", "index.md") if (memory / n).is_file()), None)
    index_text = texts.get(index, "") if index else ""
    for p, text in texts.items():
        rel = p.relative_to(root)
        if p.name.startswith("_") or p == index:
            continue
        in_areas, in_memory = areas in p.parents, memory in p.parents
        if (in_areas or in_memory) and not incoming[p]:
            add("orphan", p, 1, "no other note links here, so the index never leads to it")
        if in_memory and index and f"({p.name})" not in index_text and f"/{p.name})" not in index_text \
                and not re.search(r"\[\[" + re.escape(p.stem) + r"[\]|#]", index_text):
            add("not-in-index", p, 1, f"missing from {index.relative_to(root)}")
        if in_areas:
            lines = text.count("\n") + 1
            h = head(text)
            if h is None and re.search(r"<!--\s*(?:HEAD|KOPF)\s*-->", text):
                add("no-head", p, 1, "head is opened but never closed (<!-- /HEAD --> missing)")
            elif h is None and lines > a.long:
                add("no-head", p, 1, f"{lines} lines and no <!-- HEAD --> block")
            elif h is not None and h.count("\n") + 1 > a.head_max:
                add("long-head", p, 1, f"head has {h.count(chr(10)) + 1} lines, limit {a.head_max}")
            fm = frontmatter(text)
            if "reviewed" in fm or "ttl" in fm:
                d = parse_day(fm.get("reviewed", ""))
                if d is None or not fm.get("ttl", "").isdigit():
                    add("stale", p, 1, f"`reviewed: {fm.get('reviewed', '')}` / `ttl: {fm.get('ttl', '')}` is not filled in "
                        "(expected a date YYYY-MM-DD and a number of days)")
                elif d + timedelta(days=int(fm["ttl"])) < today:
                    add("stale", p, 1, f"reviewed {d.isoformat()}, ttl {fm['ttl']} days: check it against reality")

    inbox = root / a.inbox
    if inbox.is_file():
        for n, line in enumerate(texts.get(inbox, inbox.read_text(encoding="utf-8", errors="replace")).splitlines(), 1):
            d = parse_day(line)
            item = re.match(r"^\s*(?:[-*]|\d+[.)])\s+(?!\[[xX]\])", line)          # a list item that is not ticked off
            if d and item and (today - d).days > a.inbox_days:
                add("old-inbox", inbox, n, f"dated {d.isoformat()}, older than {a.inbox_days} days: do it or drop it")
    vault_index = root / "Vault-Index.md"
    if vault_index.is_file():
        m = re.search(r"^##\s+(?:Active priorities|Aktive Prioritäten)\s*$(.*?)(?=^##\s|\Z)", texts.get(vault_index, ""), re.S | re.M)
        if m:
            n = len(re.findall(r"^(?:[-*]|\d+\.)\s+\S", m.group(1), re.M))        # top-level items only
            if n > 5:
                add("priorities", vault_index, 1, f"{n} active priorities, limit 5")
    if index:
        lines, size = index_text.count("\n") + 1, len(index_text.encode("utf-8"))
        if lines > 180 or size > 22_000:
            add("memory-size", index, 1, f"{lines} lines, {size} bytes: past about 200 lines or 25 KB rules get dropped")
    for p, share in ((inbox, START_SHARE["inbox"]), (index, START_SHARE["memory"])):
        if p and p.is_file() and len(texts.get(p, "")) > share:
            add("start-budget", p, 1, f"{len(texts[p])} characters, the start block shows about {share}: "
                "the session start hook has to cut this file, so part of it is not seen unless the file is opened")

    always = [root / "CLAUDE.md", vault_index, inbox] + ([index] if index else [])
    core = [p for p in files if (areas in p.parents or memory in p.parents) and not p.name.startswith("_") and p != index]
    stats = {
        "notes": len(files),
        "core_notes": len(core),
        "core_orphans": sum(1 for f in findings if f["check"] == "orphan"),
        "always_loaded_chars": sum(len(p.read_text(encoding="utf-8", errors="replace")) for p in always if p.is_file()),
        "findings": len(findings),
        "by_check": {c: sum(1 for f in findings if f["check"] == c) for c in sorted({f["check"] for f in findings})},
    }
    return findings, stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet", action="store_true", help="numbers only")
    ap.add_argument("--file", help="only report findings in this file (for a hook after an edit)")
    ap.add_argument("--inbox", default="00-inbox.md")
    ap.add_argument("--daily", default="01-daily")
    ap.add_argument("--areas", default="02-areas")
    ap.add_argument("--memory", default="90-memory")
    ap.add_argument("--long", type=int, default=80, help="lines from which an area note needs a head")
    ap.add_argument("--head-max", type=int, default=25)
    ap.add_argument("--inbox-days", type=int, default=7)
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 2
    findings, stats = lint(root, a)
    if a.file:
        try:
            rel = str(Path(a.file).resolve().relative_to(root))
        except ValueError:
            return 0
        findings = [f for f in findings if f["file"] == rel]
    if a.json:
        print(json.dumps({"date": datetime.now().isoformat(timespec="seconds"), "stats": stats, "findings": findings},
                         ensure_ascii=False, indent=2))
    else:
        if not a.quiet:
            for f in findings:
                print(f"{f['check']:13} {f['file']}:{f['line']}  {f['message']}")
        if not a.file:
            print(f"{stats['notes']} notes, {stats['core_notes']} in areas and memory, {stats['core_orphans']} of those orphaned. "
                  f"Always loaded: {stats['always_loaded_chars']} chars. Findings: {stats['findings']} "
                  + (str(stats["by_check"]) if stats["by_check"] else ""))
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
