import hashlib

from guestgraph.normalize import hashed_email, normalize_email, normalize_phone


def test_email_trim_and_case():
    assert normalize_email("  Asha.Shah@Yahoo.com ") == "asha.shah@yahoo.com"


def test_gmail_dots_and_plus_tags_collapse():
    assert normalize_email("as.ha+deals@GMAIL.com") == normalize_email("asha@gmail.com") == "asha@gmail.com"
    assert normalize_email("a.b@googlemail.com") == "ab@gmail.com"


def test_bad_email_is_none():
    assert normalize_email("not-an-email") is None
    assert normalize_email("") is None


def test_phone_formats_agree():
    forms = ["(551) 235-3720", "551-235-3720", "+1 551 235 3720", "15512353720", "5512353720"]
    assert {normalize_phone(f) for f in forms} == {"15512353720"}


def test_phone_too_short_is_none():
    assert normalize_phone("12345") is None


def test_hash_matches_platform_spec():
    assert hashed_email(" Test@Example.com") == hashlib.sha256(b"test@example.com").hexdigest()
