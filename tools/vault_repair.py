#!/usr/bin/env python3
"""Vault repair: archives what expired, merges exact duplicates, retires what a newer note supersedes. No model.

Standard library only. A dry run by default: it prints what it would do and changes nothing.

    python3 tools/vault_repair.py [root] [--apply] [--today YYYY-MM-DD] [--json]

Two layouts, found by themselves:
  vault          root holds 90-memory/ (and 02-areas/): each folder is repaired with its own index
  memory folder  root itself holds MEMORY.md next to the memory files (the Claude Code auto-memory)

Optional frontmatter fields, top level, in any note or memory file:
  valid_until: YYYY-MM-DD    the note holds through that day and is archived after it
  supersedes: name           the named notes are archived and links to them point here. A name is looked up in
                             the note's own folder (file name without .md, or `name:`); a value with a / is a
                             path. Several names: `a, b`, `[a, b]`, or a YAML list below the key.

What it does, in this order:
  1. supersedes   archive each note another note supersedes. Not when the name matches more than one note,
                  when the replacing note is archived itself, or in a cycle: those are warnings.
  2. expired      archive each note whose valid_until has passed
  3. duplicates   notes in one folder whose text (without frontmatter) is the same after folding case, accents,
                  spaces and typographic quotes and dashes (punctuation stays): the stronger one stays (listed in
                  the index, more notes linking to it, more frontmatter, longer). It takes over the frontmatter
                  fields it lacks and records `merged_from:`. Notes that hold only headings are left alone.

Archive means: move the file into <folder>/_archive/, take its link out of the folder index (MEMORY.md, _index.md
or index.md; a line that links only to it goes, a line that links to more keeps the others), point links that
resolve to it at the replacement, and log date, file, reason, replacement and the index line in
_archive/ARCHIVE.md. To undo, move the file back and paste the index line back. Nothing is ever deleted.

Every write is planned first and checked before the first change: no file, index, archive folder or archive log
may be a symlink or lie outside root, otherwise nothing is written. Temp files are created fresh (never reused).

Exit 0 when there is nothing to do or --apply went through, 1 when a dry run found work, 2 on bad input or when
a write was refused.

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
import tempfile
import unicodedata
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vault_lint import SKIP_DIRS, frontmatter, parse_day  # noqa: E402

ARCHIVE = "_archive"
INDEX_NAMES = ("MEMORY.md", "_index.md", "index.md")
LINK = re.compile(r"\[\[([^\]|#]+)((?:#[^\]|]*)?(?:\|([^\]]*))?)\]\]")
MDLINK = re.compile(r"\[([^\]]*)\]\(([^)#\s]+\.md)((?:#[^)]*)?)\)")
TYPO = str.maketrans({"„": '"', "“": '"', "”": '"', "«": '"', "»": '"', "‚": "'", "‘": "'", "’": "'", "`": "'",
                      "´": "'", "–": "-", "—": "-", "‐": "-", "‑": "-", " ": " "})
LOG_HEAD = ("# Archive\n\nMoved here by tools/vault_repair.py. Nothing is deleted: to undo, move the file back and "
            "paste its index line back into the index.\n\n| Date | File | Reason | Replaced by | Index line |\n"
            "|---|---|---|---|---|\n")


class Refused(Exception):
    pass


def body(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end >= 0:
            return text[end + 4:]
    return text


def fold(text):
    """Case, accents, spaces, typographic quotes and dashes folded; punctuation kept."""
    t = unicodedata.normalize("NFKC", text).translate(TYPO)
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).casefold()
    return re.sub(r"\s+", " ", t).strip()


def only_headings(text):
    return not [l for l in body(text).splitlines() if l.strip() and not l.lstrip().startswith("#")]


def supersedes_of(text):
    """The names in `supersedes:`, inline, as [a, b], or as a YAML list below the key."""
    fm = frontmatter(text)
    if "supersedes" not in fm:
        return []
    v = fm["supersedes"].strip()
    if v.startswith("[") and v.endswith("]"):
        v = v[1:-1]
    if v:
        items = re.split(r"[,;]", v)
    else:
        m = re.search(r"^supersedes:[ \t]*\n((?:[ \t]+-[^\n]*\n?)+)", text[:text.find("\n---", 4) + 1], re.M)
        items = [l.strip()[1:] for l in m.group(1).splitlines()] if m else []
    return [i.strip().strip("\"'").strip("[]").strip() for i in items if i.strip()]


def inside(p, root):
    try:
        Path(os.path.realpath(p)).relative_to(root)
        return True
    except ValueError:
        return False


def has_symlink(p, top):
    """True when the path or any folder between top and it is a symlink."""
    q = Path(p)
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
    """Every note links may live in: the whole root, without archive, tool and hidden folders, no symlinks."""
    return [p for p in sorted(root.rglob("*.md"))
            if not set(p.relative_to(root).parts[:-1]) & (SKIP_DIRS | {ARCHIVE}) and not has_symlink(p, root)]


class Links:
    """One way to decide where a link points, used for counting, the index and rewriting alike."""

    def __init__(self, root):
        self.root = root
        self.by_stem = {}
        for p in all_notes(root):
            self.by_stem.setdefault(p.stem.lower(), []).append(p.resolve())

    def wiki(self, target):
        t = target.strip()
        t = t[:-3] if t.lower().endswith(".md") else t
        if "/" in t:
            p = (self.root / (t + ".md")).resolve()
            return p if p.is_file() else None
        hits = self.by_stem.get(Path(t).name.lower(), [])
        return hits[0] if len(hits) == 1 else None             # two notes with this name: not sure, do not touch

    def md(self, target, from_file):
        if "://" in target:
            return None
        return (from_file.parent / target).resolve()

    def to(self, text, from_file, p):
        """How many links in text resolve to note p."""
        p = p.resolve()
        n = sum(1 for m in LINK.finditer(text) if self.wiki(m.group(1)) == p)
        return n + sum(1 for m in MDLINK.finditer(text) if self.md(m.group(2), from_file) == p)

    def count(self, text):
        return len(LINK.findall(text)) + len([m for m in MDLINK.finditer(text) if "://" not in m.group(2)])

    def rewrite(self, text, from_file, p, into):
        p = p.resolve()
        stem = into.stem if len(self.by_stem.get(into.stem.lower(), [])) <= 1 else \
            str(into.relative_to(self.root).with_suffix("")).replace(os.sep, "/")

        def wiki(m):
            return f"[[{stem}{m.group(2)}]]" if self.wiki(m.group(1)) == p else m.group(0)

        def md(m):
            if self.md(m.group(2), from_file) == p:
                return f"[{m.group(1)}]({os.path.relpath(into, from_file.parent).replace(os.sep, '/')}{m.group(3)})"
            return m.group(0)
        return MDLINK.sub(md, LINK.sub(wiki, text))

    def unlink(self, text, from_file, p):
        """Replace links to p by their plain text."""
        p = p.resolve()
        text = LINK.sub(lambda m: (m.group(3) or m.group(1)) if self.wiki(m.group(1)) == p else m.group(0), text)
        return MDLINK.sub(lambda m: m.group(1) if self.md(m.group(2), from_file) == p else m.group(0), text)


def resolve_supersedes(name, p, folder, notes, fms, root):
    """The notes a `supersedes:` entry names: by path, else by file name or `name:` in the note's own folder."""
    n = name[:-3] if name.lower().endswith(".md") else name
    if "/" in n:
        cands = {(p.parent / (n + ".md")).resolve(), (root / (n + ".md")).resolve()}
        return [q for q in notes if q.resolve() in cands]
    key = Path(n).name.lower()
    return [q for q in notes if q != p and q.parent == folder
            and (q.stem.lower() == key or fms[q].get("name", "").strip().lower() == key)]


def plan(root, a, today):
    texts, fms, folder_of = {}, {}, {}
    for f in folders(root, a):
        for p in notes_in(f, root):
            texts[p] = p.read_text(encoding="utf-8", errors="replace")
            fms[p] = frontmatter(texts[p])
            folder_of[p] = f
    links = Links(root)
    notes = sorted(texts)
    archived = {q.stem.lower() for f in folders(root, a) if (f / ARCHIVE).is_dir() for q in (f / ARCHIVE).glob("*.md")}
    warnings = []

    expired = {}
    for p in notes:
        v = fms[p].get("valid_until")
        if v is None:
            continue
        d = parse_day(v) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v.strip()) else None
        if d is None:
            warnings.append(f"{p.relative_to(root)}: valid_until `{v}` is not a date (YYYY-MM-DD)")
        elif d < today:
            expired[p] = d

    pairs = []
    for p in notes:
        raw = fms[p].get("supersedes")
        if raw is None:
            continue
        names = supersedes_of(texts[p])
        if not names and raw.strip():
            warnings.append(f"{p.relative_to(root)}: supersedes `{raw}` could not be read")
        for n in names:
            hits = resolve_supersedes(n, p, folder_of[p], notes, fms, root)
            if len(hits) > 1:
                warnings.append(f"{p.relative_to(root)}: supersedes `{n}` matches {len(hits)} notes, archived none")
            elif not hits:
                if Path(n).name.lower().removesuffix(".md") not in archived:
                    warnings.append(f"{p.relative_to(root)}: supersedes `{n}`, but there is no such note in its folder")
            else:
                pairs.append((hits[0], p))
    targets = {q for q, _ in pairs}
    actions, gone = [], set()
    for q, p in pairs:
        if p in targets or p in expired:
            why = "is superseded itself (a chain or a cycle)" if p in targets else "has expired itself"
            warnings.append(f"{q.relative_to(root)}: not archived, its replacement {p.relative_to(root)} {why}")
            continue
        if q not in gone:
            gone.add(q)
            actions.append({"kind": "superseded", "note": q, "into": p})
    for p, d in sorted(expired.items()):
        if p not in gone:
            gone.add(p)
            actions.append({"kind": "expired", "note": p, "into": None, "since": d.isoformat()})

    def strength(p):
        idx = index_of(folder_of[p])
        listed = bool(idx) and links.to(idx.read_text(encoding="utf-8", errors="replace"), idx, p) > 0
        inbound = sum(1 for q in all_notes(root) if q not in (p, idx)
                      and links.to(texts.get(q) or q.read_text(encoding="utf-8", errors="replace"), q, p))
        return (not listed, -inbound, -len(fms[p]), -len(texts[p]), p.name)

    groups = {}
    for p in notes:
        if p in gone or only_headings(texts[p]):
            continue
        groups.setdefault((folder_of[p], fold(body(texts[p]))), []).append(p)
    for _, ps in sorted(groups.items(), key=lambda kv: str(kv[1][0])):
        if len(ps) < 2:
            continue
        keep, *rest = sorted(ps, key=strength)
        for q in rest:
            gone.add(q)
            actions.append({"kind": "duplicate", "note": q, "into": keep})
    return actions, warnings, {"texts": texts, "fms": fms, "folder_of": folder_of, "links": links}


def add_frontmatter(text, fields):
    """Add top-level fields to an existing frontmatter block; a note without one gets none."""
    if not fields or not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    return text[:end] + "".join(f"\n{k}: {v}" for k, v in fields.items()) + text[end:]


def check_writable(p, root, what):
    if has_symlink(p, root) or not inside(p, root) or (os.path.lexists(p) and not Path(p).is_file()):
        raise Refused(f"refusing to write {what} {p}: a symlink, not a plain file, or outside the root")


def write(p, text):
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=f".{p.name}.", suffix=".repair-tmp")   # new file, O_EXCL
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, p)


def apply(root, actions, state, today):
    """Plan every change in memory, check every target, then write. Raises Refused before the first write."""
    texts, fms, folder_of, links = state["texts"], state["fms"], state["folder_of"], state["links"]
    leaving = {x["note"] for x in actions}
    new = {}

    def current(q):
        if q not in new:
            new[q] = texts.get(q) or q.read_text(encoding="utf-8", errors="replace")
        return new[q]

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
        new[keep] = add_frontmatter(current(keep), fields)

    logs, moves = {}, []
    linkable = [q for q in all_notes(root) if q not in leaving]
    for act in actions:
        p, into = act["note"], act["into"]
        folder = folder_of[p]
        idx = index_of(folder)
        dropped = ""
        if idx:
            lines = current(idx).split("\n")
            out = []
            for line in lines:
                if links.to(line, idx, p):
                    dropped = (dropped + " / " if dropped else "") + line.strip()
                    if links.count(line) > links.to(line, idx, p):
                        out.append(links.unlink(line, idx, p))     # the line points at more: keep the rest
                    continue
                out.append(line)
            new[idx] = "\n".join(out)
        if into is not None:                                     # after the index, or its line would be bent too
            for q in linkable:
                if q in (into,) or q == idx:
                    continue
                t = current(q)
                if links.to(t, q, p):
                    new[q] = links.rewrite(t, q, p, into)
        arch = folder / ARCHIVE
        target, n = arch / p.name, 2
        while os.path.lexists(target) or target in {m[1] for m in moves}:
            target, n = arch / f"{p.stem}-{n}{p.suffix}", n + 1
        moves.append((p, target))
        reason = {"superseded": "superseded", "expired": f"expired (valid_until {act.get('since', '')})",
                  "duplicate": "duplicate"}[act["kind"]]
        cell = lambda s: s.replace("|", "\\|")              # noqa: E731
        logs.setdefault(arch, []).append(
            f"| {today.isoformat()} | {cell(str(target.relative_to(folder)))} | {reason} | "
            f"{cell(str(into.relative_to(root))) if into else ''} | {cell(dropped)} |\n")

    for arch in logs:                                        # every check before the first write
        if os.path.lexists(arch) and (arch.is_symlink() or not arch.is_dir()):
            raise Refused(f"refusing to archive into {arch}: not a plain folder")
        if not inside(arch.parent, root) or has_symlink(arch.parent, root):
            raise Refused(f"refusing to archive into {arch}: outside the root or behind a symlink")
        check_writable(arch / "ARCHIVE.md", root, "the archive log")
    for q, text in new.items():
        if text != (texts.get(q) if q in texts else None):
            check_writable(q, root, "note or index")
    for p, target in moves:
        check_writable(p, root, "note")

    for q, text in new.items():
        old = texts.get(q)
        if old is None:
            old = q.read_text(encoding="utf-8", errors="replace")
        if text != old:
            write(q, text)
    for arch in logs:
        arch.mkdir(exist_ok=True)
    for p, target in moves:
        if os.path.lexists(target):
            raise Refused(f"{target} appeared while repairing, stopped before moving {p}")
        os.rename(p, target)                                 # a move, never a delete
    for arch, rows in logs.items():
        log = arch / "ARCHIVE.md"
        if log.is_symlink():
            raise Refused(f"refusing to write {log}: a symlink")
        head = "" if log.exists() else LOG_HEAD
        with open(log, "a", encoding="utf-8") as f:
            f.write(head + "".join(rows))


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
    if a.apply and actions:
        try:
            apply(root, actions, state, today)
        except Refused as e:
            print(f"nothing written: {e}", file=sys.stderr)
            return 2
    rows = [{"action": x["kind"], "note": str(x["note"].relative_to(root)),
             "into": str(x["into"].relative_to(root)) if x["into"] else None} for x in actions]
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
