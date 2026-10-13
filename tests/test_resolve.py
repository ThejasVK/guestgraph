from guestgraph.resolve import resolve

MEMBERS = [
    {"member_id": "M1", "email": "Asha@Gmail.com", "phone": "(551) 235-3720"},
    {"member_id": "M2", "email": "ben@yahoo.com", "phone": None},
]


def tx(i, card=None, member=None, email=None):
    return {"txn_id": f"T{i}", "card_token": card, "member_id": member, "receipt_email": email}


def test_anonymous_card_visit_links_to_member():
    txns = [tx(1, card="c1", member="M1"), tx(2, card="c1")]
    r = resolve(MEMBERS, txns)
    assert r.txn_to_guest["T1"] == r.txn_to_guest["T2"]


def test_receipt_email_links_card_to_member_profile():
    txns = [tx(1, card="c9", email="a.sha@gmail.com")]  # same gmail inbox as M1
    r = resolve(MEMBERS, txns)
    assert r.node_to_guest["card:c9"] == r.node_to_guest["member:M1"]


def test_different_people_stay_apart():
    txns = [tx(1, card="c1", member="M1"), tx(2, card="c2", member="M2")]
    r = resolve(MEMBERS, txns)
    assert r.txn_to_guest["T1"] != r.txn_to_guest["T2"]


def test_shared_card_is_blocked_from_merging_strangers():
    members = [{"member_id": f"M{i}", "email": f"p{i}@x.com", "phone": None} for i in range(1, 5)]
    txns = [tx(i, card="corp", member=f"M{i}") for i in range(1, 5)]
    r = resolve(members, txns, max_members_per_card=2)
    assert "corp" in r.blocked_cards
    assert len({r.txn_to_guest[f"T{i}"] for i in range(1, 5)}) == 4


def test_cash_without_ids_is_unresolved():
    r = resolve(MEMBERS, [tx(1)])
    assert r.txn_to_guest["T1"] is None
