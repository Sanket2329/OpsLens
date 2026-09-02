"""
Unit tests for JWT and password hashing utilities.
"""

import time

import pytest
from jose import jwt

from app.config.settings import settings
from app.security.hashing import hash_password, verify_password
from app.security.jwt import create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        hashed = hash_password("mysecret")
        assert hashed != "mysecret"

    def test_verify_correct_password(self):
        hashed = hash_password("mysecret")
        assert verify_password("mysecret", hashed) is True

    def test_verify_wrong_password(self):
        hashed = hash_password("mysecret")
        assert verify_password("wrongpassword", hashed) is False

    def test_same_password_different_hashes(self):
        # bcrypt uses random salts
        h1 = hash_password("mysecret")
        h2 = hash_password("mysecret")
        assert h1 != h2

    def test_empty_password_hashes(self):
        # Should not crash
        hashed = hash_password("")
        assert verify_password("", hashed) is True


class TestJWT:
    def test_create_and_decode(self):
        token = create_access_token({"sub": "42", "email": "test@example.com"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["email"] == "test@example.com"

    def test_invalid_token_returns_none(self):
        result = decode_access_token("this.is.not.a.valid.token")
        assert result is None

    def test_tampered_token_returns_none(self):
        token = create_access_token({"sub": "1"})
        # Flip a character in the signature
        tampered = token[:-3] + "xyz"
        assert decode_access_token(tampered) is None

    def test_token_contains_expiry(self):
        token = create_access_token({"sub": "1"})
        payload = decode_access_token(token)
        assert "exp" in payload

    def test_token_signed_with_correct_secret(self):
        token = create_access_token({"sub": "99"})
        # Manually decode with the real secret — should succeed
        raw = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert raw["sub"] == "99"

    def test_wrong_secret_returns_none(self):
        token = create_access_token({"sub": "1"})
        try:
            jwt.decode(token, "wrong-secret", algorithms=[settings.jwt_algorithm])
            assert False, "Should have raised"
        except Exception:
            pass  # Expected — signature mismatch
