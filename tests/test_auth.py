"""Auth helpers: email validation and password hashing round-trip."""
from app.schemas.auth import is_valid_email
from app.security import hash_password, verify_password


def test_email_validation():
    assert is_valid_email("user@example.com")
    assert is_valid_email("a.b-c@sub.domain.co")
    assert not is_valid_email("notanemail")
    assert not is_valid_email("missing@tld")
    assert not is_valid_email("@nolocal.com")
    assert not is_valid_email("spaces in@x.com")
    assert not is_valid_email("x@x.com" + "y" * 300)  # over length cap


def test_password_hash_roundtrip():
    h = hash_password("supersecret123")
    assert h != "supersecret123"
    assert verify_password("supersecret123", h)
    assert not verify_password("wrong", h)
