import json
from fastapi.testclient import TestClient
from mathgen.web import app
from mathgen.output.answer import answer_lines
from mathgen.core.question import Question

client = TestClient(app)


def _login():
    client.post("/api/register", data={"username": "家长", "password": "secret123"})


def test_answer_lines_fallback_for_no_expression():
    q = Question("arithmetic", "3+5 = ____", "8", None, None)
    assert answer_lines([q]) == ["3+5 = ____ = 8"]


def _add_sheet():
    qj = json.dumps({"topic": "arithmetic", "statement": "12 + 7 = ____",
                     "answer": "19", "expression": "12 + 7", "layout": None})
    client.post("/api/mistakes", data={"kind": "sheet", "topic": "arithmetic",
                "problem": "12 + 7 = ____", "answer": "19", "expression": "12 + 7",
                "question_json": qj, "params": '{"grade": "1", "seed": 1}', "q_index": "0"})


def test_export_original_pdf():
    _login()
    _add_sheet()
    r = client.post("/api/mistakes/1/export", data={"mode": "original"})
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment")
    assert "filename*=UTF-8''" in r.headers["content-disposition"]
    assert r.headers["content-type"].startswith("application/pdf")


def test_export_variant_strips_seed(monkeypatch):
    _login()
    _add_sheet()
    seen = {}

    def fake_generate(cfg):
        seen["seed"] = cfg.seed
        return [Question("arithmetic", "1 + 1 = ____", "2", "1 + 1", None)]
    import mathgen.web as web
    monkeypatch.setattr(web, "generate", fake_generate)
    r = client.post("/api/mistakes/1/export", data={"mode": "variant"})
    assert r.status_code == 200
    assert seen["seed"] != 42


def test_export_batch_caps_at_100():
    _login()
    for i in range(101):
        client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                    "problem": f"{i}+1", "answer": str(i + 1)})
    ids = ",".join(str(i) for i in range(1, 102))
    r = client.post("/api/mistakes/export-batch", data={"ids": ids, "mode": "original"}, follow_redirects=False)
    assert r.status_code == 302
    r = client.post("/api/mistakes/export-batch", data={"ids": "1,2", "mode": "original"})
    assert r.status_code == 200


def test_export_manual_original_falls_back():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "9-4", "answer": "5"})
    r = client.post("/api/mistakes/1/export", data={"mode": "original"})
    assert r.status_code == 200


def test_export_anonymous_redirects():
    r = client.post("/api/mistakes/1/export", data={"mode": "original"},
                    follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]
