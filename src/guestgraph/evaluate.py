"""How good is the identity resolution? Compare against ground truth.

The synthetic generator records who really made each transaction. Two numbers matter:

* purity: of the guests we built, how many contain only one real person? Low purity means
  we merged strangers, which is the worse mistake (one person's offers go to another).
* fragmentation: how many guest IDs does one real person end up split across? High
  fragmentation means we under-merged and undercount loyal guests.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


def evaluate(txn_to_guest: dict[str, str | None], truth_csv: Path) -> dict:
    with Path(truth_csv).open(newline="") as f:
        truth = {r["txn_id"]: r["person_id"] for r in csv.DictReader(f)}
    guest_people: dict[str, set] = defaultdict(set)
    person_guests: dict[str, set] = defaultdict(set)
    for txn, gid in txn_to_guest.items():
        if gid is None or txn not in truth:
            continue
        guest_people[gid].add(truth[txn])
        person_guests[truth[txn]].add(gid)
    pure = sum(1 for ps in guest_people.values() if len(ps) == 1)
    return {
        "guests": len(guest_people),
        "real_people": len(person_guests),
        "purity": round(pure / len(guest_people), 4) if guest_people else 0.0,
        "avg_guest_ids_per_person": round(sum(len(g) for g in person_guests.values()) / len(person_guests), 3)
        if person_guests else 0.0,
        "people_split_across_ids": sum(1 for g in person_guests.values() if len(g) > 1),
    }
