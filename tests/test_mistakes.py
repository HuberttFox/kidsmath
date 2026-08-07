import json
import re
from fastapi.testclient import TestClient
from mathgen.web import app

client = TestClient(app)


def _login(username="家长", password="secret123"):
    client.post("/api/register", data={"username": username, "password": password})


def test_member_errors_review_need_login():
    for path in ("/member/errors", "/member/review"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["location"]
    _login()
    for path in ("/member/errors", "/member/review"):
        assert client.get(path).status_code == 200
