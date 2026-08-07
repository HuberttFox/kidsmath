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


def _register(username="家长", password="secret123"):
    return client.post("/api/register", data={"username": username, "password": password},
                       follow_redirects=False)


def test_register_and_me():
    r = _register()
    assert r.status_code == 302
    assert client.get("/api/me").json()["username"] == "家长"


def test_register_duplicate():
    _register()
    r = _register()
    assert r.status_code == 200
    assert "用户名已存在" in r.text


def test_register_short_password():
    r = _register(password="123")
    assert "密码至少 6 位" in r.text


def test_register_blank_username():
    r = _register(username="   ")
    assert "用户名需 2-32 个字符" in r.text


def test_login_logout():
    _register()
    r = client.post("/api/login", data={"username": "家长", "password": "secret123"},
                    follow_redirects=False)
    assert r.status_code == 302 and "kidsmath_session" in r.headers.get("set-cookie", "")
    r2 = client.post("/api/login", data={"username": "家长", "password": "wrong"})
    assert "用户名或密码错误" in r2.text  # 统一文案
    client.post("/api/logout")
    assert client.get("/api/me").status_code == 401


def test_gate_user_redirects_to_login():
    r = client.get("/user/history", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["location"]


def test_member_pages_public():
    assert client.get("/member/timer").status_code == 200


def test_login_next_consumed():
    _register()
    r = client.post("/api/login?next=/user/saved",
                    data={"username": "家长", "password": "secret123"},
                    follow_redirects=False)
    assert r.headers["location"] == "/user/saved"
