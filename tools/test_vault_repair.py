#!/usr/bin/env python3
"""Tests for tools/vault_repair.py and the matching lint checks, on made-up notes in a temp folder. No network.

    python3 tools/test_vault_repair.py
"""
import json
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
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8") for p in sorted(root.rglob("*")) if p.is_file()}


class VaultLayout(unittest.TestCase):
    """The vault layout: 90-memory/ with MEMORY.md, 02-areas/, links between them."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        v = self.v = Path(self.tmp.name) / "vault"
        mem = v / "90-memory"
        note(mem / "MEMORY.md", "# Memory index\n\n- [Old rule](old-rule.md) — before\n- [New rule](new-rule.md) — after\n"
             "- [Trial](trial-offer.md) — until the trial ends\n- [Ship fast](ship-fast.md) — listed one\n"
             "- [Keep](keep.md) — stays\n")
        note(mem / "old-rule.md", "---\nname: old-rule\ndescription: before\n---\nReply within two days.\n")
        note(mem / "new-rule.md", "---\nname: new-rule\ndescription: after\nsupersedes: old-rule\n---\n"
             "Reply within one day. Replaces [[old-rule]].\n")
        note(mem / "trial-offer.md", "---\nname: trial-offer\nvalid_until: 2026-03-31\n---\nThe trial box costs half.\n")
        note(mem / "ship-fast.md", "---\nname: ship-fast\ndescription: listed one\n---\nShip the smallest version first, then measure.\n")
        note(mem / "ship-fast-copy.md", "---\nname: ship-fast-copy\nsource: a retro note\n---\n"
             "ship the SMALLEST version first -- then measure\n")
        note(mem / "keep.md", "---\nname: keep\nvalid_until: 2027-01-01\n---\nA rule that still holds.\n")
        note(v / "02-areas" / "support.md", "# Support\n\nSee [[old-rule]] and [copy](../90-memory/ship-fast-copy.md) "
             "and [[trial-offer]].\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_dry_run_changes_nothing(self):
        before = snapshot(self.v)
        rc, out = run("tools/vault_repair.py", self.v, "--today", "2026-06-01", "--json")
        data = json.loads(out)
        self.assertEqual(rc, 1)
        got = {(x["action"], x["note"]) for x in data["actions"]}
        self.assertEqual(got, {("superseded", "90-memory/old-rule.md"), ("expired", "90-memory/trial-offer.md"),
                               ("duplicate", "90-memory/ship-fast-copy.md")})
        self.assertEqual(snapshot(self.v), before)

    def test_today_decides_expiry(self):
        rc, out = run("tools/vault_repair.py", self.v, "--today", "2026-03-31", "--json")
        self.assertNotIn("trial-offer", out, "valid through its last day")

    def test_apply_archives_and_never_deletes(self):
        files_before = len([p for p in self.v.rglob("*.md")])
        rc, out = run("tools/vault_repair.py", self.v, "--today", "2026-06-01", "--apply")
        self.assertEqual(rc, 0, out)
        mem = self.v / "90-memory"
        arch = mem / "_archive"
        for n in ("old-rule.md", "trial-offer.md", "ship-fast-copy.md"):
            self.assertFalse((mem / n).exists(), n)
            self.assertTrue((arch / n).exists(), n)
        self.assertEqual(len([p for p in self.v.rglob("*.md")]), files_before + 1, "every file kept, plus ARCHIVE.md")
        index = (mem / "MEMORY.md").read_text(encoding="utf-8")
        self.assertNotIn("old-rule.md", index)
        self.assertNotIn("trial-offer.md", index)
        self.assertIn("ship-fast.md", index)
        log = (arch / "ARCHIVE.md").read_text(encoding="utf-8")
        self.assertIn("superseded | 90-memory/new-rule.md | - [Old rule](old-rule.md)", log)
        self.assertIn("expired (valid_until 2026-03-31)", log)
        support = (self.v / "02-areas" / "support.md").read_text(encoding="utf-8")
        self.assertIn("[[new-rule]]", support, "link to the superseded note now points at its replacement")
        self.assertIn("(../90-memory/ship-fast.md)", support, "link to the duplicate points at the stronger note")
        self.assertIn("[[trial-offer]]", support, "a link to an expired note is left for a person")
        kept = (mem / "ship-fast.md").read_text(encoding="utf-8")
        self.assertIn("source: a retro note", kept)
        self.assertIn("merged_from: ship-fast-copy", kept)
        self.assertIn("Replaces [[old-rule]]", (mem / "new-rule.md").read_text(encoding="utf-8"))
        rc, out = run("tools/vault_repair.py", self.v, "--today", "2026-06-01")
        self.assertEqual(rc, 0, "a second run finds nothing: " + out)

    def test_lint_reports_expired_and_superseded_and_skips_the_archive(self):
        rc, out = run("tools/vault_lint.py", self.v, "--json")
        by = json.loads(out)["stats"]["by_check"]
        self.assertGreaterEqual(by.get("expired", 0), 1)
        self.assertEqual(by.get("superseded", 0), 1)
        run("tools/vault_repair.py", self.v, "--today", "2099-01-01", "--apply")
        rc, out = run("tools/vault_lint.py", self.v, "--json")
        found = json.loads(out)["findings"]
        self.assertFalse([f for f in found if "_archive" in f["file"]], "archived notes are not linted")
        self.assertFalse([f for f in found if f["check"] in ("expired", "superseded")])

    def test_start_block_names_expired_notes(self):
        rc, out = run("hooks/session_start.py", self.v)
        self.assertIn("trial-offer.md", out.split("## Expired")[1] if "## Expired" in out else "")


class MemoryFolderLayout(unittest.TestCase):
    """The flat layout: MEMORY.md next to the memory files, as in the Claude Code auto-memory."""

    def test_flat_folder(self):
        with tempfile.TemporaryDirectory() as t:
            m = Path(t) / "memory"
            note(m / "MEMORY.md", "- [A](a.md) — one\n- [B](b.md) — two\n- [C](c.md) — three\n")
            note(m / "a.md", "---\nname: a\nvalid_until: 2020-01-01\n---\nAn old fact about a deadline.\n")
            note(m / "b.md", "# Same\nTwo notes, one rule: measure before you scale.\n")
            note(m / "c.md", "# same\ntwo notes one rule measure before you scale\n")
            outside = Path(t) / "outside.md"
            note(outside, "---\nvalid_until: 2020-01-01\n---\nOutside the root, never touched.\n")
            (m / "linked.md").symlink_to(outside)
            rc, out = run("tools/vault_repair.py", m, "--json")
            acts = {(x["action"], x["note"]) for x in json.loads(out)["actions"]}
            self.assertEqual(acts, {("expired", "a.md"), ("duplicate", "c.md")})
            rc, out = run("tools/vault_repair.py", m, "--apply")
            self.assertEqual(rc, 0, out)
            self.assertTrue((m / "_archive" / "a.md").exists() and (m / "_archive" / "c.md").exists())
            self.assertEqual((m / "MEMORY.md").read_text(encoding="utf-8"), "- [B](b.md) — two\n")
            self.assertTrue(outside.exists() and (m / "linked.md").is_symlink(), "symlink and its target untouched")

    def test_bad_input(self):
        self.assertEqual(run("tools/vault_repair.py", "/nonexistent-folder")[0], 2)
        with tempfile.TemporaryDirectory() as t:
            self.assertEqual(run("tools/vault_repair.py", t)[0], 2, "neither layout")
            note(Path(t) / "MEMORY.md", "")
            self.assertEqual(run("tools/vault_repair.py", t, "--today", "soon")[0], 2)


if __name__ == "__main__":
    unittest.main(verbosity=1)
