#!/usr/bin/env python3
"""Vault search: ranked full-text search over a folder of notes, without an index or a database.

Standard library only. Reads, never writes.

    python3 tools/vault_search.py "words to find" [vault-root] [--max 8] [--json]

Where a word is found decides the rank, in this order:
  1. the `description:` line in a note's frontmatter, the title and the file name
  2. the head (between <!-- HEAD --> and <!-- /HEAD -->)
  3. the index lines at the top of a daily note
  4. anywhere else in the text
Per word only its best place counts, so a long note cannot win by length. A note that contains all words beats
a note that contains some. Filler words (the, what, der, wie ...) are ignored, the manual (CLAUDE.md, README.md)
is not searched. Output: file, line, the matching line.

Known limits: it matches words and their beginnings, not meaning ("refund" does not find "money back"). A note
without a description and without a head competes on its text alone. Checked on one real vault of 537 notes:
searching for the words of a note's file name put that note first for all 78 notes in areas and memory. That is
an easy test; questions in free wording were not measured.
"""
import argparse
import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {".git", ".obsidian", "node_modules", ".claude", "eval", "tools", "hooks", ".trash"}
WEIGHT = {"description": 8, "head": 5, "daily-index": 4, "text": 1}


def zones(path, text):
    """Yield (zone, line number, line) for every line of a note."""
    lines = text.splitlines()
    in_fm = bool(lines) and lines[0].strip() == "---"
    in_head = False
    daily_index = bool(re.match(r"\d{4}-\d{2}-\d{2}", path.stem))
    yield "description", 0, path.stem.replace("-", " ").replace("_", " ")
    for n, line in enumerate(lines, 1):
        if in_fm:
            if n > 1 and line.strip() == "---":
                in_fm = False
            elif line.startswith(("description:", "name:")):
                yield "description", n, line
            continue
        if re.search(r"<!--\s*(HEAD|KOPF)\s*-->", line):
            in_head = True
            continue
        if re.search(r"<!--\s*/(HEAD|KOPF)\s*-->", line):
            in_head = False
            continue
        if line.startswith("# "):
            yield "description", n, line
        elif in_head:
            yield "head", n, line
        elif daily_index and n <= 12 and not line.startswith("## "):
            yield "daily-index", n, line
        else:
            if line.startswith("## "):
                daily_index = False
            yield "text", n, line


STOP = set("""a an and are as at be but by do does for from has have how i if in is it me my of on or our so than that the
their them then there these this to us was we what when where which who why will with you your
aber als am an auch auf aus bei bin das dass dem den der des die dir du ein eine einem einen einer er es für hat habe
ich ihr im in ist ja kann man mein meine mit nach nicht noch nur oder sich sie sind so über um und uns unser von vor
war was wenn wer wie wir wird wo zu zum zur""".split())
SKIP_FILES = {"claude.md", "readme.md", "license.md"}        # the manual is not knowledge, it would win every query


def search(root, query, limit):
    words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 1 and w.lower() not in STOP]
    if not words:
        return []
    patterns = {w: re.compile(r"\b" + re.escape(w), re.I) for w in words}     # whole word or its beginning: parcel, parcels
    results = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if set(rel.parts[:-1]) & SKIP_DIRS or p.name.startswith("_") or (len(rel.parts) == 1 and p.name.lower() in SKIP_FILES):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        best, hits = {}, []                      # per word only its best zone counts, so a long note cannot win by length
        for zone, n, line in zones(p, text):
            in_line = [w for w in words if patterns[w].search(line)]
            if not in_line:
                continue
            for w in in_line:
                best[w] = max(best.get(w, 0), WEIGHT[zone])
            hits.append((WEIGHT[zone] * len(in_line), n, zone, line.strip()))
        if not best:
            continue
        score = sum(best.values()) * (len(best) / len(words)) ** 2          # all words beat some words
        score += min(len(hits), 5) * 0.05                                   # tie-break only
        hits.sort(key=lambda h: (-h[0], h[1]))
        results.append({"file": str(rel), "score": round(score, 2), "words": f"{len(best)}/{len(words)}",
                        "hits": [{"line": n, "zone": z, "text": t[:200]} for _, n, z, t in hits[:3]]})
    results.sort(key=lambda r: (-r["score"], r["file"]))
    return results[:limit]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("query")
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--max", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).resolve()
    if not root.is_dir():
        print(f"not a folder: {root}", file=sys.stderr)
        return 2
    res = search(root, a.query, a.max)
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    elif not res:
        print("no note contains these words")
    else:
        for r in res:
            print(f"{r['file']}  (score {r['score']}, words {r['words']})")
            for h in r["hits"]:
                print(f"   {h['line']:>4} [{h['zone']}] {h['text']}")
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
