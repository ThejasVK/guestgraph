"""Identity resolution: turn loyalty records, card tokens and receipt emails into guests.

Every identifier becomes a node in a graph. Two nodes get an edge when the data shows they
belong to the same person:

* a loyalty member and the email/phone on their profile
* a loyalty member and a card token used in the same transaction (the guest scanned their
  loyalty ID and paid with that card)
* a receipt email and the card token on that transaction

Connected components are guests. This is how anonymous card-only visits get attributed to
known people, which is the whole point: most restaurant revenue comes from guests who never
scan a loyalty ID.

One guard matters a lot in practice: a single card that links to many different loyalty
members (a company card, a shared family card) would merge strangers into one "guest". Card
tokens that co-occur with more than ``max_members_per_card`` members are not used as links.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass, field

from .normalize import normalize_email, normalize_phone, sha256


class UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def add(self, x: str) -> None:
        self.parent.setdefault(x, x)

    def find(self, x: str) -> str:
        self.add(x)
        root = x
        while self.parent[root] != root:
            root = self.parent[root]
        while self.parent[x] != root:  # path compression
            self.parent[x], x = root, self.parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            if ra < rb:
                self.parent[rb] = ra
            else:
                self.parent[ra] = rb


@dataclass
class Resolution:
    node_to_guest: dict[str, str]
    txn_to_guest: dict[str, str | None]
    guest_identifiers: dict[str, dict] = field(default_factory=dict)
    blocked_cards: set[str] = field(default_factory=set)

    @property
    def guest_count(self) -> int:
        return len(set(self.node_to_guest.values()))


def _guest_id(root: str) -> str:
    return "G" + hashlib.sha1(root.encode()).hexdigest()[:10]


def resolve(members: list[dict], transactions: list[dict], max_members_per_card: int = 2) -> Resolution:
    uf = UnionFind()
    ids: dict[str, dict] = defaultdict(dict)  # node -> identifiers worth keeping

    for m in members:
        mnode = f"member:{m['member_id']}"
        uf.add(mnode)
        ids[mnode]["member_id"] = m["member_id"]
        email = normalize_email(m.get("email"))
        if email:
            enode = f"email:{sha256(email)}"
            uf.union(mnode, enode)
            ids[enode]["email_sha256"] = sha256(email)
        phone = normalize_phone(m.get("phone"))
        if phone:
            pnode = f"phone:{sha256(phone)}"
            uf.union(mnode, pnode)
            ids[pnode]["phone_sha256"] = sha256(phone)
            ids[pnode]["phone_e164_sha256"] = sha256("+" + phone)

    card_members: dict[str, set[str]] = defaultdict(set)
    for t in transactions:
        if t.get("card_token") and t.get("member_id"):
            card_members[t["card_token"]].add(t["member_id"])
    blocked = {c for c, ms in card_members.items() if len(ms) > max_members_per_card}

    for t in transactions:
        card = t.get("card_token") or None
        cnode = f"card:{card}" if card and card not in blocked else None
        if cnode:
            uf.add(cnode)
        if cnode and t.get("member_id"):
            uf.union(cnode, f"member:{t['member_id']}")
        email = normalize_email(t.get("receipt_email"))
        if email:
            enode = f"email:{sha256(email)}"
            ids[enode]["email_sha256"] = sha256(email)
            uf.add(enode)
            if cnode:
                uf.union(cnode, enode)
            elif t.get("member_id"):
                uf.union(enode, f"member:{t['member_id']}")

    node_to_guest = {n: _guest_id(uf.find(n)) for n in uf.parent}

    txn_to_guest: dict[str, str | None] = {}
    for t in transactions:
        node = None
        if t.get("member_id"):
            node = f"member:{t['member_id']}"
        elif t.get("card_token") and t["card_token"] not in blocked:
            node = f"card:{t['card_token']}"
        elif normalize_email(t.get("receipt_email")):
            node = f"email:{sha256(normalize_email(t['receipt_email']))}"
        txn_to_guest[t["txn_id"]] = node_to_guest.get(node) if node else None

    guest_ids: dict[str, dict] = defaultdict(lambda: {"member_ids": set(), "email_sha256": set(),
                                                     "phone_sha256": set(), "phone_e164_sha256": set()})
    for node, gid in node_to_guest.items():
        g = guest_ids[gid]
        info = ids.get(node, {})
        if "member_id" in info:
            g["member_ids"].add(info["member_id"])
        for k in ("email_sha256", "phone_sha256", "phone_e164_sha256"):
            if k in info:
                g[k].add(info[k])

    return Resolution(node_to_guest, txn_to_guest, dict(guest_ids), blocked)
