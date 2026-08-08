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




def test_review_flow_updates_due():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "3+5", "answer": "8"})
    page = client.get("/member/review").text
    assert "3+5" in page and "显示答案" in page
    r = client.post("/api/mistakes/1/review", data={"q": "5"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert "今日全部完成" in client.get("/member/review").text


def test_review_q3_slight_ease_drop():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "7*8", "answer": "56"})
    client.post("/api/mistakes/1/review", data={"q": "3"})
    assert "今日全部完成" in client.get("/member/review").text


def test_review_anonymous_redirects():
    client.get("/api/logout")
    r = client.post("/api/mistakes/1/review", data={"q": "5"}, follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]


def test_mastered_toggle_and_delete():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "6/2", "answer": "3"})
    client.post("/api/mistakes/1/mastered")
    assert "6/2" in client.get("/member/errors?f=mastered").text
    client.post("/api/mistakes/1/mastered")
    assert "6/2" not in client.get("/member/errors?f=mastered").text
    assert client.post("/api/mistakes/1/delete",
                       follow_redirects=False).status_code == 302
    assert "还没有错题" in client.get("/member/errors").text


def test_note_edit():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "8/4", "answer": "2"})
    client.post("/api/mistakes/1/note", data={"note": "进位粗心"})
    assert "进位粗心" in client.get("/member/errors").text


def test_member_home_ai_card_links_to_ai_page():
    r = client.get("/member")
    assert r.status_code == 200
    assert 'href="/member/ai"' in r.text  # AI 卡指向真实页面
    assert client.get("/member/ai").status_code == 200


def test_review_all_cards_preview():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "11-3", "answer": "8"})
    page = client.get("/member/review").text
    assert "全部卡片预览" in page
    assert "11-3" in page
    assert "待复习" in page
    # 预览不得泄露待复习卡片答案：全页唯一"答案：8"来自测验卡的隐藏显示
    assert page.count("答案：8") == 1
    assert 'data-i18n="review.status_due"' in page  # 状态徽章走 i18n 字典


def test_review_preview_hides_due_answer_but_shows_mastered():
    _login()
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "11-3", "answer": "8"})
    client.post("/api/mistakes/manual", data={"topic": "arithmetic",
                "problem": "7+6", "answer": "13"})
    client.post("/api/mistakes/1/mastered")
    page = client.get("/member/review").text
    # 已掌握卡在预览展示答案，待复习卡不展示
    assert page.count("答案：13") == 1
    assert page.count("答案：8") == 1  # 仅测验卡隐藏显示
    assert 'review-mastered' in page and '已掌握' in page
    assert 'review-due' in page and '待复习' in page
