import json
import re
from fastapi.testclient import TestClient
from mathgen.web import app

client = TestClient(app)


def _login():
    client.post("/api/register", data={"username": "家长", "password": "secret123"})


def test_generate_records_history():
    _login()
    client.post("/generate", data={"grade": "2", "count": "3"})
    r = client.get("/user/history")
    assert r.status_code == 200
    assert "重新生成" in r.text
    assert "grade=2" in r.text  # 摘要含配置


def test_history_regenerate_redirects_without_seed():
    _login()
    client.post("/generate", data={"grade": "2", "count": "3", "seed": "7"})
    r = client.get("/user/history")
    m = re.search(r'action="/api/history/(\d+)/regenerate"', r.text)
    assert m
    r2 = client.post(f"/api/history/{m.group(1)}/regenerate", follow_redirects=False)
    assert r2.status_code == 302
    assert "seed" not in r2.headers["location"]
    assert "grade=2" in r2.headers["location"]


def test_delete_history():
    _login()
    client.post("/generate", data={"grade": "1"})
    r = client.get("/user/history")
    m = re.search(r'action="/api/history/(\d+)/delete"', r.text)
    hid = m.group(1)
    assert client.post(f"/api/history/{hid}/delete",
                       follow_redirects=False).status_code == 302
    assert "还没有生成记录" in client.get("/user/history").text


def test_anonymous_generate_no_record_and_gate():
    _login()
    client.post("/api/logout")
    client.post("/generate", data={"grade": "1", "count": "3"})
    r = client.get("/user/history", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]


def test_history_db_failure_does_not_break_generate(monkeypatch):
    _login()
    import mathgen.db as db

    def boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr(db, "add_history", boom)
    r = client.post("/generate", data={"grade": "1", "count": "3"})
    assert r.status_code == 200  # 出题主流程不受影响
