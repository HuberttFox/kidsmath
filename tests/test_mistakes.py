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


def test_capture_sheet_mistake():
    _login()
    r = client.post("/api/mistakes", data={
        "kind": "sheet", "topic": "vertical", "problem": "23 + 48 = ____",
        "answer": "71", "expression": "23 + 48",
        "question_json": '{"topic": "vertical", "statement": "23 + 48 = ____", "answer": "71", "expression": "23 + 48", "layout": {"kind": "vertical"}}',
        "params": '{"grade": "2", "seed": 1}', "q_index": "3", "note": ""},
        follow_redirects=False)
    assert r.status_code == 302 and "/member/errors" in r.headers["location"]
    page = client.get("/member/errors").text
    assert "23 + 48" in page


def test_manual_normalize_topic():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "竖式", "problem": "12*3", "answer": "36"})
    page = client.get("/member/errors").text
    assert "12*3" in page


def test_errors_filter_tabs():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic", "problem": "1+1", "answer": "2"})
    client.post("/api/mistakes", data={"kind": "sheet", "topic": "arithmetic",
                "problem": "2+2", "answer": "4", "expression": "2+2",
                "question_json": "{}", "params": "{}", "q_index": "0"})
    for f in ("all", "due", "mastered"):
        assert client.get(f"/member/errors?f={f}").status_code == 200
