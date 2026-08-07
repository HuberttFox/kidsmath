import hashlib
import mathgen.auth as auth


def test_hash_roundtrip():
    h = auth.hash_password("secret123")
    assert h.startswith("pbkdf2_sha256$200000$")
    assert auth.verify_password("secret123", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("secret123", "garbage")


def test_hash_salted_unique():
    assert auth.hash_password("x") != auth.hash_password("x")


def test_token_pair():
    cookie, h = auth.new_session_token()
    assert len(cookie) >= 32
    assert h == hashlib.sha256(cookie.encode()).hexdigest()

from fastapi.testclient import TestClient
from mathgen.web import app

client = TestClient(app)


def test_csrf_origin_mismatch_blocked():
    r = client.post("/generate", data={"grade": "1"},
                    headers={"origin": "https://evil.example"})
    assert r.status_code == 403


def test_csrf_missing_origin_allowed():
    r = client.post("/generate", data={"grade": "1", "count": "3"})
    assert r.status_code == 200


def test_csrf_same_origin_allowed():
    r = client.post("/generate", data={"grade": "1", "count": "3"},
                    headers={"origin": "http://testserver"})
    assert r.status_code == 200
