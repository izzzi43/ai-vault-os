#!/usr/bin/env python3
"""PreCompact hook: its stdout becomes instructions for the compaction summary.

A compaction is where unfiled findings die: they lived in the conversation, not in the vault. This asks the
summary to carry them over, and names today's note so the next step after compaction is obvious.

    python3 hooks/pre_compact.py [vault-root]
"""
import sys
from datetime import date

print(f"""Keep in the summary, word for word where it matters:
1. Every finding, decision and number from this session that is not yet written into the vault, each with its source.
2. Every open point and what it is waiting for.
3. Which vault notes were changed in this session, and which should have been but were not.
4. Corrections the user made to how you work.
After compaction, the first step is to file point 1 into 01-daily/{date.today().isoformat()}.md and the affected area notes.""")
sys.exit(0)
