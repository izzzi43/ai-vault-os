#!/usr/bin/env python3
"""Builds a small sample vault for the eval, with dates relative to today, so "the day before yesterday"
means something on the day you run it. The shop in it is invented.

    python3 eval/make_vault.py <target-folder> [--manual path/to/CLAUDE.md] [--no-hooks]

Copies the manual, tools, hooks and settings from this repo, then writes the sample notes on top.
--manual swaps in another CLAUDE.md (for a before/after run: `git show main:CLAUDE.md > /tmp/before.md`).
--no-hooks leaves out .claude/settings.json, so nothing is enforced.
"""
import argparse
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def d(days_ago):
    return (date.today() - timedelta(days=days_ago)).isoformat()


def notes():
    return {
        "Vault-Index.md": f"""# Vault-Index

The map. Read this first in every session.

## Who I am

I run Lumen, a small online shop for scented candles, alone, with two freelancers. I do marketing, the shop
and customer service myself.

## The folders

| Folder | Holds |
|---|---|
| `00-inbox.md` | Open handovers. Cleared first, never a parking lot. |
| `01-daily/` | The chronicle. One note per day, index lines on top. |
| `02-areas/` | The knowledge. Standing notes per area of responsibility. |
| `90-memory/` | Distilled rules. The agent reads the index `MEMORY.md` every session. |

## Active priorities

1. Winter collection live before the first of next month
2. Cut the share of lost parcels
3. Answer wholesale requests within two days
""",
        "00-inbox.md": f"""# 00 Inbox

Open handovers. Read first in every session, cleared before new work starts.

- {d(2)}: The glass supplier sent a corrected invoice. Check the amount against the order before paying.
- {d(1)}: Mira (freelance photos) needs the list of winter scents to plan the shoot.
""",
        f"01-daily/{d(0)}.md": f"""# {d(0)}

**Index:** nothing yet today

---

## Shipped

## Decisions

## Open
""",
        f"01-daily/{d(1)}.md": f"""# {d(1)}

**Index:** winter scents shortlist · product page draft · photo shoot planning

---

## Shipped

- Shortlist of five winter scents, see [[products]]

## Decisions

- Cedar and clove are in, vanilla is out: it sold badly last winter.

## Open

- Send the scent list to Mira
""",
        f"01-daily/{d(2)}.md": f"""# {d(2)}

**Index:** corrected invoice from the glass supplier · returns label printer broken · newsletter test

---

## Shipped

- Newsletter subject line test set up, see [[marketing]]

## Decisions

- Returns labels are sent as PDF by mail until the printer is replaced.

## Open

- Corrected invoice from the glass supplier
""",
        f"01-daily/{d(3)}.md": f"""# {d(3)}

**Index:** shipping provider switch live · first parcels with Northpost

---

## Shipped

- All new orders ship with Northpost from today, see [[shipping]]

## Decisions

- Switch from ParcelOne to Northpost, because of lost parcels.

## Open
""",
        f"01-daily/{d(6)}.md": f"""# {d(6)}

**Index:** wick supplier call · delivery delay

---

## Shipped

- Call with the wick supplier.

## Decisions

## Open

- The wick supplier delivers the cotton wicks two weeks late and offered wooden wicks as a stopgap. Not decided.
""",
        "02-areas/shipping.md": f"""---
description: How parcels leave the shop, which provider, what a lost parcel costs and what to do about one.
reviewed: {d(3)}
ttl: 90
---

# Shipping

How orders get from the shelf to the customer.

<!-- HEAD -->
- Provider is Northpost (as of {d(3)}, decision in the daily note of that day).
- A parcel counts as lost after 10 working days without a scan.
- Lost parcel: reship at once, claim from the provider afterwards. Never make the customer wait for the claim.
- Current delivery times are a pointer: the provider's status page, not this note.
<!-- /HEAD -->

## How it works

Orders placed before noon leave the same day. Each parcel gets a tracking link by mail.

## Wholesale shipments

Only when the task is about wholesale: pallets go by freight, minimum order is 12 units per scent, and
the customer books the pickup.

## Earlier

- Provider was ParcelOne (held until {d(3)}, replaced by Northpost). Reason: too many lost parcels, roughly one
  in forty over the autumn, and claims took six weeks.

Related: [[returns]]
""",
        "02-areas/returns.md": f"""---
description: Return window, who pays the return, how refunds are made and what is never done automatically.
reviewed: {d(20)}
ttl: 90
---

# Returns

<!-- HEAD -->
- Return window is 30 days from delivery.
- The shop pays the return label for damaged goods, the customer pays otherwise.
- Refunds go back to the original payment method within five working days.
- Burned candles are not taken back.
<!-- /HEAD -->

## How it works

The customer writes to service, gets a label as PDF, and the refund is made when the parcel is scanned.

Related: [[shipping]]
""",
        "02-areas/products.md": f"""---
description: The candle range, what is in stock, prices and what is planned for the next collection.
reviewed: {d(1)}
ttl: 60
---

# Products

<!-- HEAD -->
- Twelve scents all year, five more for winter.
- Stock numbers are a pointer: the inventory sheet "Lumen stock", tab "live". Never copy a number from it.
- Prices are set once per quarter.
<!-- /HEAD -->

## Winter collection

Shortlist (as of {d(1)}): cedar, clove, orange peel, pine, smoked honey.

Related: [[marketing]]
""",
        "02-areas/marketing.md": f"""---
description: Newsletter, ads and what was tested, with results.
reviewed: {d(200)}
ttl: 90
---

# Marketing

<!-- HEAD -->
- The newsletter goes out on Thursdays.
- Best performing subject lines name the scent (as of {d(200)}, three tests).
<!-- /HEAD -->

## How it works

One newsletter per week, one test per newsletter.

Related: [[products]]
""",
        "90-memory/MEMORY.md": """# Memory index

One line per memory. **The index points, it does not store.**

## Guardrails — rules that must apply unasked

- [No refund without a scan](feedback_refund_scan.md) — refund only after the return parcel was scanned
- [Never promise a delivery date](feedback_delivery_date.md) — give the tracking link, not a date

## Preferences

- [Short answers](user_short_answers.md) — three sentences unless asked for more
""",
        "90-memory/feedback_refund_scan.md": """---
name: feedback-refund-scan
description: Refund only after the return parcel was scanned by the provider
metadata:
  type: feedback
---

Refunds are made only after the return parcel has its first scan.

**Why:** two refunds went out for parcels that never came back.

**How to apply:** check the tracking link before any refund, write the scan date into the reply.
""",
        "90-memory/feedback_delivery_date.md": """---
name: feedback-delivery-date
description: Never promise a delivery date to a customer, give the tracking link
metadata:
  type: feedback
---

Never promise a delivery date.

**Why:** the provider's times vary and a missed promise costs more than no promise.

**How to apply:** send the tracking link and the usual range from the provider's status page.
""",
        "90-memory/user_short_answers.md": """---
name: user-short-answers
description: Answers in three sentences unless asked for more
metadata:
  type: user
---

Answer in three sentences unless asked for more.

**Why:** I read on the phone between other things.

**How to apply:** lead with the answer, add detail only on request.
""",
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target")
    ap.add_argument("--manual")
    ap.add_argument("--no-hooks", action="store_true")
    a = ap.parse_args(argv)
    target = Path(a.target)
    if target.exists() and any(target.iterdir()):
        print(f"target is not empty: {target}", file=sys.stderr)
        return 2
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy(a.manual or REPO / "CLAUDE.md", target / "CLAUDE.md")
    for folder in ("tools", "hooks"):
        shutil.copytree(REPO / folder, target / folder, ignore=shutil.ignore_patterns("__pycache__"))
    if not a.no_hooks:
        shutil.copytree(REPO / ".claude", target / ".claude")
    for rel, text in notes().items():
        p = target / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    print(f"sample vault written to {target} ({len(notes())} notes, hooks {'off' if a.no_hooks else 'on'})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
