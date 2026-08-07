import json
from fastapi.testclient import TestClient
from mathgen.web import app

client = TestClient(app)


def test_ai_page_public():
    r = client.get("/member/ai")
    assert r.status_code == 200
    assert "开始解析" in r.text


def test_parse_renders_summary_and_backfill():
    r = client.post("/api/ai/parse", data={"text": "12 + 34 = 46\n23 - 11 = 12"})
    assert r.status_code == 200
    assert "识别 2/2 题" in r.text
    assert "回填表单" in r.text


def test_parse_backfill_redirect():
    from mathgen.parser import parse_examples
    fields = parse_examples("12 + 34 = 46\n23 - 11 = 12")["fields"]
    r2 = client.post("/api/ai/backfill", data={
        "fields": json.dumps(fields),
        "text": "12 + 34 = 46\n23 - 11 = 12"}, follow_redirects=False)
    assert r2.status_code == 302
    loc = r2.headers["location"]
    assert "grade=2" in loc and "operators=%2B-" in loc  # + URL 编码


def test_parse_no_numbers_disables_backfill():
    r = client.post("/api/ai/parse", data={"text": "今天天气很好"})
    assert "未识别到算式" in r.text
    assert 'action="/api/ai/backfill"' not in r.text  # 按钮禁用
