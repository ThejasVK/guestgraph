"""Synthetic restaurant data: loyalty members, payment cards and transactions.

Real data is messy in the ways that matter for identity resolution: the same person types
their email differently in two places, phone numbers arrive in five formats, most
transactions are anonymous card swipes, and one card can show up with and without a
loyalty scan. The generator reproduces those patterns with a fixed seed.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

FIRST = ["Asha", "Ben", "Carla", "Dev", "Elena", "Femi", "Gwen", "Hiro", "Isha", "Jon",
         "Kavya", "Liam", "Mei", "Nikhil", "Omar", "Priya", "Quinn", "Rosa", "Sam", "Tara"]
LAST = ["Shah", "Lopez", "Kim", "Okafor", "Rossi", "Nguyen", "Patel", "Smith", "Ali", "Chen"]
DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "icloud.com"]
STORES = [("S01", "Jersey City"), ("S02", "Hoboken"), ("S03", "Newark"), ("S04", "Manhattan")]


@dataclass
class Person:
    pid: int
    email: str
    phone: str
    cards: list[str]
    is_member: bool
    visits_per_month: float


def _messy_email(email: str, rng: random.Random) -> str:
    local, domain = email.split("@")
    choice = rng.random()
    if choice < 0.15:
        return f"  {email.upper()} "
    if choice < 0.25 and domain == "gmail.com":
        return f"{local[:2]}.{local[2:]}@{domain}"
    if choice < 0.30 and domain == "gmail.com":
        return f"{local}+deals@{domain}"
    return email


def _messy_phone(digits10: str, rng: random.Random) -> str:
    a, b, c = digits10[:3], digits10[3:6], digits10[6:]
    return rng.choice([f"({a}) {b}-{c}", f"{a}-{b}-{c}", f"+1 {a} {b} {c}", f"1{digits10}", digits10])


def make_people(n: int, rng: random.Random) -> list[Person]:
    people = []
    for pid in range(1, n + 1):
        first, last = rng.choice(FIRST), rng.choice(LAST)
        email = f"{first.lower()}{last.lower()}{pid}@{rng.choice(DOMAINS)}"
        phone = f"{rng.choice(['201', '551', '973', '646', '917'])}{rng.randint(2000000, 9999999)}"
        cards = [f"tok_{pid:05d}_{k}" for k in range(rng.choice([1, 1, 1, 2]))]
        people.append(Person(pid, email, phone, cards, rng.random() < 0.35, rng.uniform(0.3, 6.0)))
    return people


def generate(out_dir: Path, n_people: int = 1500, days: int = 120, seed: int = 7,
             end: date = date(2026, 9, 30)) -> dict[str, Path]:
    """Write loyalty_members.csv and transactions.csv. Returns the file paths."""
    rng = random.Random(seed)
    out_dir.mkdir(parents=True, exist_ok=True)
    people = make_people(n_people, rng)
    # A few shared cards (office or family cards) used by several loyalty members.
    shared = [f"tok_shared_{k}" for k in range(4)]
    for p in people:
        if p.is_member and rng.random() < 0.03:
            p.cards.append(rng.choice(shared))
    start = end - timedelta(days=days - 1)

    members_path = out_dir / "loyalty_members.csv"
    with members_path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["member_id", "email", "phone", "joined_on", "home_store"])
        for p in people:
            if p.is_member:
                joined = start - timedelta(days=rng.randint(0, 400))
                w.writerow([f"M{p.pid:05d}", _messy_email(p.email, rng), _messy_phone(p.phone, rng),
                            joined.isoformat(), rng.choice(STORES)[0]])

    tx_path = out_dir / "transactions.csv"
    truth_path = out_dir / "_truth.csv"  # who really made each transaction (for evaluation only)
    with tx_path.open("w", newline="") as f, truth_path.open("w", newline="") as tf:
        w = csv.writer(f)
        tw = csv.writer(tf)
        tw.writerow(["txn_id", "person_id"])
        w.writerow(["txn_id", "store_id", "txn_date", "amount", "card_token", "member_id",
                    "receipt_email"])
        txn = 0
        for p in people:
            home = rng.choice(STORES)[0]
            for d in range(days):
                if rng.random() < p.visits_per_month / 30:
                    txn += 1
                    day = start + timedelta(days=d)
                    store = home if rng.random() < 0.8 else rng.choice(STORES)[0]
                    paid_cash = rng.random() < 0.08
                    card = "" if paid_cash else rng.choice(p.cards)
                    scanned = p.is_member and rng.random() < 0.55
                    receipt = _messy_email(p.email, rng) if (not scanned and rng.random() < 0.06) else ""
                    w.writerow([f"T{txn:07d}", store, day.isoformat(), f"{rng.uniform(6, 48):.2f}",
                                card, f"M{p.pid:05d}" if scanned else "", receipt])
                    tw.writerow([f"T{txn:07d}", p.pid])
    return {"members": members_path, "transactions": tx_path, "truth": truth_path}
