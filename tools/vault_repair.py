#!/usr/bin/env python3
"""Vault repair: archives what expired, merges exact duplicates, retires what a newer note supersedes. No model.

Standard library only. A dry run by default: it prints what it would do and changes nothing.

    python3 tools/vault_repair.py [root] [--apply] [--today YYYY-MM-DD] [--json]

Two layouts, found by themselves:
  vault          root holds 90-memory/ (and 02-areas/): each folder is repaired with its own index
  memory folder  root itself holds MEMORY.md next to the memory files (the Claude Code auto-memory)

Optional frontmatter fields, top level, in any note or memory file:
  valid_until: YYYY-MM-DD    the note holds through that day and is archived after it
  supersedes: name[, name]   the named notes (file name without .md, or their `name:`) are archived,
                             and links to them are pointed at this note

What it does, in this order:
  1. supersedes   archive each note another note supersedes
  2. expired      archive each note whose valid_until has passed
  3. duplicates   notes in one folder whose text (without frontmatter) is the same after folding case,
                  accents, punctuation and spaces: the stronger one stays (listed in the index, more notes
                  linking to it, more frontmatter, longer). It takes over the frontmatter fields it lacks and
                  records `merged_from:`; links to the others are pointed at it.

Archive means: move the file into <folder>/_archive/, drop its line from the folder index (MEMORY.md, _index.md
or index.md), and log date, file, reason, replacement and the dropped index line in _archive/ARCHIVE.md.
To undo, move the file back and paste the index line back. Nothing is ever deleted. Symlinks are never
followed, and nothing outside root is touched.

Exit 0 when there is nothing to do or --apply went through, 1 when a dry run found work, 2 on bad input.

Known limits
  - Duplicates must match exactly after folding. Two notes that say the same thing in other words stay;
    that needs a reader, see the consolidate skill.
  - A link inside a code block is rewritten like any other link.
  - A note archived because it expired leaves links to it broken on purpose: the lint reports them, a person
    decides what replaces them.
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_lint import SKIP_DIRS, frontmatter, parse_day  # noqa: E402

ARCHIVE = "_archive"
INDEX_NAMES = ("MEMORY.md", "_index.md", "index.md")
MIN_CHARS = 20                                              # shorter bodies are templates or stubs, not duplicates
LINK = re.compile(r"\[\[([^\]|#]+)((?:#[^\]|]*)?(?:\|[^\]]*)?)\]\]")
MDLINK = re.compile(r"(\]\()([^)#\s]+\.md)((?:#[^)]*)?\))")
LOG_HEAD = ("# Archive\n\nMoved here by tools/vault_repair.py. Nothing is deleted: to undo, move the file back and "
            "paste its index line back into the index.\n\n| Date | File | Reason | Replaced by | Index line |\n"
            "|---|---|---|---|---|\n")


def body(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            return text[end + 4:]
    return text


def fold(text):
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c)).casefold()
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", t)).strip()


def inside(p, root):
    try:
        Path(os.path.realpath(p)).relative_to(root)
        return True
    except ValueError:
        return False


def has_symlink(p, top):
    """True when the file or any folder between top and it is a symlink."""
    q = p
    while True:
        if q.is_symlink():
            return True
        if q == top or q.parent == q:
            return False
        q = q.parent


def folders(root, a):
    if (root / "MEMORY.md").is_file():
        return [root]
    return [root / f for f in (a.memory, a.areas) if (root / f).is_dir() and not (root / f).is_symlink()]


def index_of(folder):
    return next((folder / n for n in INDEX_NAMES if (folder / n).is_file()), None)


def notes_in(folder, root):
    idx = index_of(folder)
    out = []
    for p in sorted(folder.rglob("*.md")):
        rel = p.relative_to(folder).parts[:-1]
        if set(rel) & (SKIP_DIRS | {ARCHIVE}) or p.name.startswith("_") or p == idx:
            continue
        if has_symlink(p, folder) or not inside(p, root):
            continue
        out.append(p)
    return out


def all_notes(root):
    """Every note links may live in: the whole root, without archive, tool and hidden folders."""
    out = []
    for p in sorted(root.rglob("*.md")):
        if set(p.relative_to(root).parts[:-1]) & (SKIP_DIRS | {ARCHIVE}) or has_symlink(p, root):
            continue
        out.append(p)
    return out


def names(p, fm):
    out = {p.stem.lower()}
    if fm.get("name"):
        out.add(fm["name"].strip().lower())
    return out


def link_targets(text):
    found = {Path(m.group(1).strip()).name.lower().removesuffix(".md") for m in LINK.finditer(text)}
    found |= {Path(m.group(2)).stem.lower() for m in MDLINK.finditer(text) if "://" not in m.group(2)}
    return found


def plan(root, a, today):
    texts, fms, folder_of = {}, {}, {}
    for f in folders(root, a):
        for p in notes_in(f, root):
            texts[p] = p.read_text(encoding="utf-8", errors="replace")
            fms[p] = frontmatter(texts[p])
            folder_of[p] = f
    linkers = {}
    for p in all_notes(root):
        t = texts.get(p) or p.read_text(encoding="utf-8", errors="replace")
        for target in link_targets(t):
            linkers.setdefault(target, set()).add(p)
    by_name = {}
    for p, fm in fms.items():
        for n in names(p, fm):
            by_name.setdefault(n, []).append(p)
    archived_names = set()
    for f in folders(root, a):
        if (f / ARCHIVE).is_dir():
            archived_names |= {q.stem.lower() for q in (f / ARCHIVE).glob("*.md")}

    actions, warnings, gone = [], [], set()
    for p in sorted(fms):
        for raw in re.split(r"[,;]", fms[p].get("supersedes", "")):
            n = raw.strip().strip("[]").removesuffix(".md").lower()
            if not n:
                continue
            hits = [q for q in by_name.get(n, []) if q != p]
            if not hits:
                if n not in archived_names and n not in names(p, fms[p]):
                    warnings.append(f"{p.relative_to(root)}: supersedes `{n}`, but there is no such note")
                continue
            for q in hits:
                if q not in gone:
                    gone.add(q)
                    actions.append({"kind": "superseded", "note": q, "into": p})
    for p in sorted(fms):
        v = fms[p].get("valid_until")
        if v is None or p in gone:
            continue
        d = parse_day(v) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) else None
        if d is None:
            warnings.append(f"{p.relative_to(root)}: valid_until `{v}` is not a date (YYYY-MM-DD)")
        elif d < today:
            gone.add(p)
            actions.append({"kind": "expired", "note": p, "into": None, "since": d.isoformat()})

    def strength(p):
        idx = index_of(folder_of[p])
        listed = bool(idx) and p.name in idx.read_text(encoding="utf-8", errors="replace")
        inbound = len({q for n in names(p, fms[p]) for q in linkers.get(n, set())} - {p, idx})
        return (not listed, -inbound, -len(fms[p]), -len(texts[p]), p.name)

    groups = {}
    for p in fms:
        if p in gone:
            continue
        key = fold(body(texts[p]))
        if len(key) >= MIN_CHARS:
            groups.setdefault((folder_of[p], key), []).append(p)
    for (_, _), ps in sorted(groups.items(), key=lambda kv: str(kv[1][0])):
        if len(ps) < 2:
            continue
        keep, *rest = sorted(ps, key=strength)
        for q in rest:
            gone.add(q)
            actions.append({"kind": "duplicate", "note": q, "into": keep})
    return actions, warnings, {"texts": texts, "fms": fms, "folder_of": folder_of}


def write(p, text):
    tmp = p.with_name(f".{p.name}.repair-tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, p)


def add_frontmatter(text, fields):
    """Add top-level fields to an existing frontmatter block; a note without one gets none."""
    if not fields or not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    return text[:end] + "".join(f"\n{k}: {v}" for k, v in fields.items()) + text[end:]


def rewrite_links(text, old_names, new_path, from_dir):
    def wiki(m):
        target = m.group(1).strip()
        if Path(target).name.lower().removesuffix(".md") in old_names:
            return f"[[{new_path.stem}{m.group(2)}]]"
        return m.group(0)

    def md(m):
        if "://" not in m.group(2) and Path(m.group(2)).stem.lower() in old_names:
            return m.group(1) + os.path.relpath(new_path, from_dir).replace(os.sep, "/") + m.group(3)
        return m.group(0)
    return MDLINK.sub(md, LINK.sub(wiki, text))


def apply(root, actions, state, today):
    texts, fms, folder_of = state["texts"], state["fms"], state["folder_of"]
    merged = {}
    for act in actions:
        if act["kind"] == "duplicate":
            merged.setdefault(act["into"], []).append(act["note"])
    for keep, others in merged.items():                     # the stronger note takes over what it lacks
        fields = {}
        for q in others:
            for k, v in fms[q].items():
                if k not in fms[keep] and k not in ("name", "description", "valid_until", "supersedes", "merged_from") and v:
                    fields.setdefault(k, v)
        fields["merged_from"] = ", ".join(q.stem for q in others)
        new = add_frontmatter(texts[keep], fields)
        if new != texts[keep]:
            write(keep, new)
            texts[keep] = new
    linkable = all_notes(root)
    for act in actions:
        p, into = act["note"], act["into"]
        folder = folder_of[p]
        idx = index_of(folder)
        dropped = ""
        if idx:
            lines = idx.read_text(encoding="utf-8", errors="replace").split("\n")
            pat = re.compile(r"\(([^)]*/)?" + re.escape(p.name) + r"\)|\[\[" + re.escape(p.stem) + r"[\]|#]")
            keep_lines = [l for l in lines if not pat.search(l)]
            dropped = " / ".join(l.strip() for l in lines if pat.search(l))
            if len(keep_lines) != len(lines):
                write(idx, "\n".join(keep_lines))
        if into is not None:                                # after the index line is gone, or it would be bent too
            old = names(p, fms[p])
            for q in linkable:
                if q in (p, into) or not q.exists():
                    continue
                t = q.read_text(encoding="utf-8", errors="replace")
                n = rewrite_links(t, old, into, q.parent)
                if n != t:
                    write(q, n)
        arch = folder / ARCHIVE
        arch.mkdir(exist_ok=True)
        if arch.is_symlink() or not inside(arch, root):
            raise SystemExit(f"refusing to archive into {arch}: not a plain folder under root")
        target, n = arch / p.name, 2
        while target.exists():
            target, n = arch / f"{p.stem}-{n}{p.suffix}", n + 1
        os.rename(p, target)                                # a move, never a delete
        log = arch / "ARCHIVE.md"
        if not log.exists():
            log.write_text(LOG_HEAD, encoding="utf-8")
        reason = {"superseded": "superseded", "expired": f"expired (valid_until {act.get('since', '')})",
                  "duplicate": "duplicate"}[act["kind"]]
        cell = lambda s: s.replace("|", "\\|")              # noqa: E731
        with log.open("a", encoding="utf-8") as f:
            f.write(f"| {today.isoformat()} | {cell(str(target.relative_to(folder)))} | {reason} | "
                    f"{cell(str(into.relative_to(root))) if into else ''} | {cell(dropped)} |\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--apply", action="store_true", help="do it; without this flag nothing is changed")
    ap.add_argument("--today", help="YYYY-MM-DD, to test expiry")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--areas", default="02-areas")
    ap.add_argument("--memory", default="90-memory")
    a = ap.parse_args(argv)
    root = Path(a.root)
    if not root.is_dir() or root.is_symlink():
        print(f"not a plain folder: {root}", file=sys.stderr)
        return 2
    root = root.resolve()
    try:
        today = date.fromisoformat(a.today) if a.today else date.today()
    except ValueError:
        print(f"--today wants YYYY-MM-DD, got {a.today}", file=sys.stderr)
        return 2
    if not folders(root, a):
        print(f"no MEMORY.md in {root} and no {a.memory}/ or {a.areas}/ under it", file=sys.stderr)
        return 2
    actions, warnings, state = plan(root, a, today)
    rows = [{"action": x["kind"], "note": str(x["note"].relative_to(root)),
             "into": str(x["into"].relative_to(root)) if x["into"] else None} for x in actions]
    if a.apply and actions:
        apply(root, actions, state, today)
    if a.json:
        print(json.dumps({"apply": a.apply, "today": today.isoformat(), "actions": rows, "warnings": warnings},
                         ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['action']:11} {r['note']}" + (f"  -> {r['into']}" if r["into"] else ""))
        for w in warnings:
            print(f"warning     {w}")
        print(f"{len(rows)} to archive, {len(warnings)} warnings. "
              + ("Applied." if a.apply else "Dry run, nothing changed. Add --apply to do it."))
    return 1 if actions and not a.apply else 0


if __name__ == "__main__":
    sys.exit(main())
