#!/usr/bin/env python3
"""Tests for tools/vault_repair.py and the matching lint checks, on made-up notes in a temp folder. No network.

    python3 tools/test_vault_repair.py
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def run(script, *args):
    r = subprocess.run([sys.executable, str(REPO / script), *map(str, args)], capture_output=True, text=True)
    return r.returncode, r.stdout + r.stderr


def note(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def snapshot(root):
    return {str(p.relative_to(root)): (os.readlink(p) if p.is_symlink() else p.read_bytes())
            for p in sorted(root.rglob("*")) if p.is_file() or p.is_symlink()}


def actions(root, *extra):
    rc, out = run("tools/vault_repair.py", root, "--json", *extra)
    data = json.loads(out)
    return rc, {(x["action"], x["note"]) for x in data["actions"]}, data["warnings"]


class Temp(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.t = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()


class VaultLayout(Temp):
    def setUp(self):
        super().setUp()
        v = self.v = self.t / "vault"
        mem = self.mem = v / "90-memory"
        note(mem / "MEMORY.md", "# Memory index\n\n- [Old rule](old-rule.md) — before\n- [New rule](new-rule.md) — after\n"
             "- [Trial](trial-offer.md) — until the trial ends\n- [Ship fast](ship-fast.md) — listed one\n"
             "- [Keep](keep.md) — stays, see also [Trial](trial-offer.md)\n")
        note(mem / "old-rule.md", "---\nname: old-rule\ndescription: before\n---\nReply within two days.\n")
        note(mem / "new-rule.md", "---\nname: new-rule\ndescription: after\nsupersedes: old-rule\n---\n"
             "Reply within one day. Replaces [[old-rule]].\n")
        note(mem / "trial-offer.md", "---\nname: trial-offer\nvalid_until: 2026-03-31\n---\nThe trial box costs half.\n")
        note(mem / "ship-fast.md", "---\nname: ship-fast\ndescription: listed one\n---\nShip the smallest version first – then measure.\n")
        note(mem / "ship-fast-copy.md", "---\nname: ship-fast-copy\nsource: a retro note\n---\n"
             "ship  the SMALLEST versión first - then measure.\n")
        note(mem / "ship-fast-other.md", "---\nname: ship-fast-other\n---\nShip the smallest version first, then measure.\n")
        note(mem / "heading-a.md", "# Placeholder\n\n## Later\n")
        note(mem / "heading-b.md", "# placeholder\n\n## later\n")
        note(mem / "keep.md", "---\nname: keep\nvalid_until: 2027-01-01\n---\nA rule that still holds.\n")
        note(v / "02-areas" / "support.md", "# Support\n\nSee [[old-rule]] and [copy](../90-memory/ship-fast-copy.md) "
             "and [[trial-offer]].\n")

    def test_dry_run_changes_nothing(self):
        before = snapshot(self.v)
        rc, got, _ = actions(self.v, "--today", "2026-06-01")
        self.assertEqual(rc, 1)
        self.assertEqual(got, {("superseded", "90-memory/old-rule.md"), ("expired", "90-memory/trial-offer.md"),
                               ("duplicate", "90-memory/ship-fast-copy.md")},
                         "case, accents, spaces and dashes fold; a different comma does not; headings-only notes stay")
        self.assertEqual(snapshot(self.v), before)

    def test_today_decides_expiry(self):
        _, got, _ = actions(self.v, "--today", "2026-03-31")
        self.assertNotIn(("expired", "90-memory/trial-offer.md"), got, "valid through its last day")

    def test_apply_archives_and_never_deletes(self):
        files_before = len(list(self.v.rglob("*.md")))
        rc, out = run("tools/vault_repair.py", self.v, "--today", "2026-06-01", "--apply")
        self.assertEqual(rc, 0, out)
        arch = self.mem / "_archive"
        for n in ("old-rule.md", "trial-offer.md", "ship-fast-copy.md"):
            self.assertFalse((self.mem / n).exists(), n)
            self.assertTrue((arch / n).exists(), n)
        self.assertEqual(len(list(self.v.rglob("*.md"))), files_before + 1, "every file kept, plus ARCHIVE.md")
        index = (self.mem / "MEMORY.md").read_text(encoding="utf-8")
        self.assertNotIn("old-rule.md", index)
        self.assertNotIn("- [Trial]", index)
        self.assertIn("- [Keep](keep.md) — stays, see also Trial\n", index, "a line with more links keeps the others")
        self.assertEqual(index.count("ship-fast.md"), 1, "no second index line for the survivor")
        log = (arch / "ARCHIVE.md").read_text(encoding="utf-8")
        self.assertIn("superseded | 90-memory/new-rule.md | - [Old rule](old-rule.md)", log)
        self.assertIn("expired (valid_until 2026-03-31)", log)
        support = (self.v / "02-areas" / "support.md").read_text(encoding="utf-8")
        self.assertIn("[[new-rule]]", support)
        self.assertIn("(../90-memory/ship-fast.md)", support)
        self.assertIn("[[trial-offer]]", support, "a link to an expired note is left for a person")
        kept = (self.mem / "ship-fast.md").read_text(encoding="utf-8")
        self.assertIn("source: a retro note", kept)
        self.assertIn("merged_from: ship-fast-copy", kept)
        self.assertIn("Replaces [[old-rule]]", (self.mem / "new-rule.md").read_text(encoding="utf-8"))
        self.assertEqual(run("tools/vault_repair.py", self.v, "--today", "2026-06-01")[0], 0, "a second run finds nothing")

    def test_links_rewritten_only_where_they_resolve(self):
        note(self.v / "02-areas" / "old-rule.md", "# Old rule (areas)\n\nAnother note with the same name.\n")
        note(self.v / "02-areas" / "faq.md", "# FAQ\n\n[areas one](old-rule.md) and [memory one](../90-memory/old-rule.md)\n")
        run("tools/vault_repair.py", self.v, "--today", "2026-06-01", "--apply")
        faq = (self.v / "02-areas" / "faq.md").read_text(encoding="utf-8")
        self.assertIn("[areas one](old-rule.md)", faq, "points at a different file: untouched")
        self.assertIn("[memory one](../90-memory/new-rule.md)", faq)
        self.assertIn("[[old-rule]]", (self.v / "02-areas" / "support.md").read_text(encoding="utf-8"),
                      "an ambiguous wikilink is not guessed")

    def test_lint_reports_expired_and_superseded_and_skips_the_archive(self):
        by = json.loads(run("tools/vault_lint.py", self.v, "--json")[1])["stats"]["by_check"]
        self.assertGreaterEqual(by.get("expired", 0), 1)
        self.assertEqual(by.get("superseded", 0), 1)
        run("tools/vault_repair.py", self.v, "--today", "2099-01-01", "--apply")
        found = json.loads(run("tools/vault_lint.py", self.v, "--json")[1])["findings"]
        self.assertFalse([f for f in found if "_archive" in f["file"]], "archived notes are not linted")
        self.assertFalse([f for f in found if f["check"] in ("expired", "superseded")])

    def test_start_block_names_expired_notes(self):
        out = run("hooks/session_start.py", self.v)[1]
        self.assertIn("trial-offer.md", out.split("## Expired")[1] if "## Expired" in out else "")


class IndexAndAbort(Temp):
    def test_ambiguous_index_wikilink_warns_and_stays(self):
        v = self.t / "vault"
        note(v / "90-memory" / "MEMORY.md", "- [[old-rule]] — before\n- [New](new-rule.md)\n")
        note(v / "90-memory" / "old-rule.md", "Reply within two days.\n")
        note(v / "90-memory" / "new-rule.md", "---\nsupersedes: old-rule\n---\nReply within one day.\n")
        note(v / "02-areas" / "old-rule.md", "# Same name, other folder\n\nText.\n")
        _, got, warn = actions(v)
        self.assertEqual(got, {("superseded", "90-memory/old-rule.md")})
        self.assertTrue(any("fix it by hand" in w for w in warn), warn)
        run("tools/vault_repair.py", v, "--apply")
        self.assertIn("[[old-rule]]", (v / "90-memory" / "MEMORY.md").read_text(encoding="utf-8"))

    def test_archive_log_is_written_before_the_moves(self):
        m = self.t / "memory"
        note(m / "MEMORY.md", "- [A](a.md) — one\n- [B](b.md) — two\n")
        note(m / "a.md", "---\nvalid_until: 2020-01-01\n---\nAn old fact about a deadline.\n")
        note(m / "b.md", "Something that holds.\n")
        sys.path.insert(0, str(REPO / "tools"))
        import argparse
        import vault_repair
        from datetime import date
        a = argparse.Namespace(areas="02-areas", memory="90-memory")
        acts, _, state = vault_repair.plan(m.resolve(), a, date(2026, 6, 1))
        echt = os.rename

        def kaputt(*_):
            raise OSError("disk went away")
        os.rename = kaputt
        try:
            with self.assertRaises(OSError):
                vault_repair.apply(m.resolve(), acts, state, date(2026, 6, 1))
        finally:
            os.rename = echt
        log = (m / "_archive" / "ARCHIVE.md").read_text(encoding="utf-8")
        self.assertIn("- [A](a.md) — one", log, "the dropped index line is on record although the move failed")
        self.assertTrue((m / "a.md").exists(), "nothing lost: the note is still where it was")


class Supersedes(Temp):
    def mem(self, files):
        m = self.t / "memory"
        note(m / "MEMORY.md", "".join(f"- [{n}]({n}.md)\n" for n in files))
        for n, text in files.items():
            note(m / f"{n}.md", text)
        return m

    def test_list_forms(self):
        m = self.mem({"a": "A one.\n", "b": "B one.\n", "c": "C one.\n",
                      "new": "---\nsupersedes: [a, b]\n---\nNew one.\n", "newer": "---\nsupersedes:\n  - c\n---\nNewer one.\n"})
        _, got, warn = actions(m)
        self.assertEqual(got, {("superseded", "a.md"), ("superseded", "b.md"), ("superseded", "c.md")}, warn)

    def test_ambiguous_name_warns(self):
        m = self.mem({"x": "First x.\n", "y": "---\nname: x\n---\nSecond x by name.\n", "new": "---\nsupersedes: x\n---\nNew.\n"})
        _, got, warn = actions(m)
        self.assertEqual(got, set())
        self.assertTrue(any("matches 2 notes" in w for w in warn), warn)

    def test_other_folder_only_by_path(self):
        v = self.t / "vault"
        note(v / "90-memory" / "MEMORY.md", "- [r](rule.md)\n")
        note(v / "90-memory" / "rule.md", "A rule.\n")
        note(v / "02-areas" / "a.md", "---\nsupersedes: rule\n---\nArea note.\n")
        _, got, warn = actions(v)
        self.assertEqual(got, set(), "a name is looked up in the own folder only")
        self.assertTrue(warn)
        note(v / "02-areas" / "a.md", "---\nsupersedes: 90-memory/rule\n---\nArea note.\n")
        _, got, _ = actions(v)
        self.assertEqual(got, {("superseded", "90-memory/rule.md")}, "a path works across folders")

    def test_cycle_chain_and_expired_replacement_warn(self):
        m = self.mem({"a": "---\nsupersedes: b\n---\nA.\n", "b": "---\nsupersedes: a\n---\nB.\n",
                      "c": "C.\n", "d": "---\nsupersedes: c\nvalid_until: 2020-01-01\n---\nD.\n"})
        _, got, warn = actions(m, "--today", "2026-01-01")
        self.assertEqual(got, {("expired", "d.md")}, warn)
        self.assertEqual(sum("superseded itself" in w for w in warn), 2)
        self.assertTrue(any("has expired itself" in w for w in warn))


class Symlinks(Temp):
    """Security: a symlink anywhere in the write set stops the run before the first write."""

    def flat(self):
        m = self.t / "memory"
        note(m / "MEMORY.md", "- [A](a.md) — one\n- [B](b.md) — two\n")
        note(m / "a.md", "---\nvalid_until: 2020-01-01\n---\nAn old fact about a deadline.\n")
        note(m / "b.md", "Something that holds.\n")
        self.outside = self.t / "outside"
        self.outside.mkdir()
        note(self.outside / "victim.md", "untouched\n")
        return m

    def refused(self, m):
        before, outside = snapshot(m), snapshot(self.outside)
        rc, out = run("tools/vault_repair.py", m, "--apply")
        self.assertEqual(rc, 2, out)
        self.assertIn("nothing written", out)
        self.assertEqual(snapshot(m), before)
        self.assertEqual(snapshot(self.outside), outside)

    def test_archive_folder_symlink(self):
        m = self.flat()
        (m / "_archive").symlink_to(self.outside, target_is_directory=True)
        self.refused(m)

    def test_archive_log_symlink(self):
        m = self.flat()
        (m / "_archive").mkdir()
        (m / "_archive" / "ARCHIVE.md").symlink_to(self.outside / "victim.md")
        self.refused(m)

    def test_index_symlink(self):
        m = self.flat()
        real = self.outside / "MEMORY.md"
        real.write_text((m / "MEMORY.md").read_text(encoding="utf-8"), encoding="utf-8")
        (m / "MEMORY.md").unlink()
        (m / "MEMORY.md").symlink_to(real)
        self.refused(m)

    def test_planted_temp_name_is_not_followed(self):
        m = self.flat()
        (m / ".MEMORY.md.repair-tmp").symlink_to(self.outside / "victim.md")
        rc, out = run("tools/vault_repair.py", m, "--apply")
        self.assertEqual(rc, 0, out)
        self.assertEqual((self.outside / "victim.md").read_text(encoding="utf-8"), "untouched\n")
        self.assertEqual((m / "MEMORY.md").read_text(encoding="utf-8"), "- [B](b.md) — two\n")

    def test_symlinked_note_is_not_touched(self):
        m = self.flat()
        note(self.outside / "linked.md", "---\nvalid_until: 2020-01-01\n---\nOutside the root.\n")
        (m / "linked.md").symlink_to(self.outside / "linked.md")
        _, got, _ = actions(m)
        self.assertEqual(got, {("expired", "a.md")})


class MemoryFolderLayout(Temp):
    def test_flat_folder(self):
        m = self.t / "memory"
        note(m / "MEMORY.md", "- [A](a.md) — one\n- [B](b.md) — two\n- [C](c.md) — three\n")
        note(m / "a.md", "---\nname: a\nvalid_until: 2020-01-01\n---\nAn old fact about a deadline.\n")
        note(m / "b.md", "# Same\nTwo notes, one rule: measure before you scale.\n")
        note(m / "c.md", "# same\ntwo notes, one rule: MEASURE before you scale.\n")
        _, got, _ = actions(m)
        self.assertEqual(got, {("expired", "a.md"), ("duplicate", "c.md")})
        rc, out = run("tools/vault_repair.py", m, "--apply")
        self.assertEqual(rc, 0, out)
        self.assertTrue((m / "_archive" / "a.md").exists() and (m / "_archive" / "c.md").exists())
        self.assertEqual((m / "MEMORY.md").read_text(encoding="utf-8"), "- [B](b.md) — two\n")

    def test_bad_input(self):
        self.assertEqual(run("tools/vault_repair.py", "/nonexistent-folder")[0], 2)
        self.assertEqual(run("tools/vault_repair.py", self.t)[0], 2, "neither layout")
        note(self.t / "MEMORY.md", "")
        self.assertEqual(run("tools/vault_repair.py", self.t, "--today", "soon")[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
