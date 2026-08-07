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


def test_save_from_main_form():
    _login()
    r = client.get("/")
    assert 'formaction="/api/saved"' in r.text  # 主表单保存按钮
    r2 = client.post("/api/saved", data={"grade": "2", "count": "3", "name": "卷A"},
                     follow_redirects=False)
    assert r2.status_code == 302 and "/user/saved" in r2.headers["location"]
    assert "卷A" in client.get("/user/saved").text


def test_import_single_button_auto_submit():
    r = client.get("/")
    assert 'import-btn' in r.text
    assert 'accept="application/json,.json"' in r.text
    assert 'onchange="this.form.submit()"' in r.text
    assert 'type="file"' in r.text


def test_saved_apply_redirects():
    _login()
    client.post("/api/saved", data={"grade": "3", "count": "5", "name": "卷B"})
    page = client.get("/user/saved")
    m = re.search(r'action="/api/saved/(\d+)/apply"', page.text)
    assert m
    r = client.post(f"/api/saved/{m.group(1)}/apply", follow_redirects=False)
    assert r.status_code == 302 and "grade=3" in r.headers["location"]
    assert "seed" not in r.headers["location"]


def test_saved_anonymous_redirects_login():
    client.post("/api/logout")
    r = client.post("/api/saved", data={"grade": "1", "name": "x"},
                    follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]


def test_saved_rename_delete():
    _login()
    client.post("/api/saved", data={"grade": "1", "name": "旧名"})
    page = client.get("/user/saved")
    m = re.search(r'action="/api/saved/(\d+)/rename"', page.text)
    sid = m.group(1)
    client.post(f"/api/saved/{sid}/rename", data={"name": "新名"})
    assert "新名" in client.get("/user/saved").text
    assert client.post(f"/api/saved/{sid}/delete",
                       follow_redirects=False).status_code == 302
    assert "新名" not in client.get("/user/saved").text


def test_export_returns_json_attachment():
    r = client.post("/api/config/export", data={"grade": "2", "count": "3", "seed": "9"})
    assert r.status_code == 200
    assert 'attachment; filename="kidsmath-config.json"' in r.headers["content-disposition"]
    data = json.loads(r.text)
    assert data["version"] == 1
    assert data["config"]["grade"] == "2"
    assert "seed" not in data["config"]


def test_import_roundtrip_and_redirect():
    r = client.post("/api/config/export", data={"grade": "3", "count": "5",
                                                "left_factor_range": "10-99"})
    files = {"file": ("kidsmath-config.json", r.content, "application/json")}
    r2 = client.post("/api/config/import", files=files, follow_redirects=False)
    assert r2.status_code == 302
    assert "grade=3" in r2.headers["location"]
    assert "left_factor_range=10-99" in r2.headers["location"]


def test_import_invalid_json_errors():
    files = {"file": ("bad.json", b"not json", "application/json")}
    r = client.post("/api/config/import", files=files)
    assert r.status_code == 200
    assert "配置导入失败" in r.text


def test_import_invalid_field_errors():
    import json as _json
    files = {"file": ("bad.json", _json.dumps({"version": 1,
            "config": {"grade": "9"}}).encode(), "application/json")}
    r = client.post("/api/config/import", files=files)
    assert "年级" in r.text


def test_history_detail_gate_and_capture():
    _login()
    client.post("/generate", data={"grade": "1", "count": "4"})
    page = client.get("/user/history").text
    m = re.search(r'href="/user/history/(\d+)"', page)
    assert m, "详情入口缺失"
    hid = m.group(1)
    r = client.get(f"/user/history/{hid}", follow_redirects=False)
    assert r.status_code == 200
    assert 'name="questions"' in r.text
    assert r.text.count('name="questions"') >= 2
    client.post("/api/logout")
    r2 = client.get(f"/user/history/{hid}", follow_redirects=False)
    assert r2.status_code == 302 and "/login" in r2.headers["location"]
    _login()


def test_capture_selected_mistakes():
    _login()
    client.post("/generate", data={"grade": "1", "count": "3"})
    page = client.get("/user/history").text
    hid = re.search(r'href="/user/history/(\d+)"', page).group(1)
    detail = client.get(f"/user/history/{hid}").text
    assert 'action="/api/history/' + hid + '/mistakes"' in detail  # 批量表单
    assert detail.count('name="questions"') == 3                    # 每题一个
    snaps = [json.dumps({"topic": "arithmetic", "problem": f"3+{i}", "answer": str(3 + i),
                         "expression": f"3+{i}", "question_json": "{}",
                         "params": "{}", "q_index": str(i)})
             for i in (1, 2)]
    r = client.post(f"/api/history/{hid}/mistakes",
                    data={"questions": snaps}, follow_redirects=False)
    assert r.status_code == 302 and "/member/errors" in r.headers["location"]
    body = client.get("/member/errors").text
    assert "3+1" in body and "3+2" in body
    client.post("/api/register", data={"username": "另一用户", "password": "secret123"})
    r2 = client.post(f"/api/history/{hid}/mistakes", data={"questions": []},
                     follow_redirects=False)
    assert r2.status_code == 302  # 跨用户查无 → 回列表
