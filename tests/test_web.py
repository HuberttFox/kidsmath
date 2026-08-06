from html import unescape
import re

from fastapi.testclient import TestClient

from mathgen.web import app

client = TestClient(app)

def test_index_page():
    r = client.get("/")
    assert r.status_code == 200
    assert "年级" in r.text


def test_generate_preview():
    r = client.post("/generate", data={"grade": "2", "count": "5", "topic": "arithmetic"})
    assert r.status_code == 200
    assert "1." in r.text
    assert "下载" in r.text


def test_download_pdf():
    r = client.post("/generate", data={"grade": "1", "count": "3", "topic": "arithmetic", "seed": "42"})
    assert r.status_code == 200
    link = client.get("/download.pdf", params={"grade": "1", "count": "3", "topic": "arithmetic", "seed": "42"})
    assert link.status_code == 200
    assert link.headers["content-type"] == "application/pdf"
    assert link.content[:4] == b"%PDF"


def test_download_without_seed_400():
    r = client.get("/download.pdf", params={"grade": "1"})
    assert r.status_code == 400


def test_invalid_params_show_error():
    r = client.post("/generate", data={"grade": "9"})
    assert r.status_code == 200
    assert "年级" in r.text


def test_generate_without_optional_fields_link_has_no_none():
    r = client.post("/generate", data={"grade": "2"})
    assert r.status_code == 200
    m = re.search(r'href="(/download\.pdf\?[^"]+)"', r.text)
    assert m, "no download link in page"
    href = unescape(m.group(1))
    assert "None" not in href
    link = client.get(href)
    assert link.status_code == 200
    assert link.headers["content-type"] == "application/pdf"
    assert link.content[:4] == b"%PDF"


def test_generate_malformed_range_shows_error():
    r = client.post("/generate", data={"grade": "1", "ranges": "abc"})
    assert r.status_code == 200
    assert "参数格式不正确" in r.text


def test_download_malformed_range_400():
    r = client.get("/download.pdf", params={"grade": "1", "ranges": "abc", "seed": "1"})
    assert r.status_code == 400
    assert "参数格式不正确" in r.text


def test_download_generation_conflict_400_chinese():
    r = client.get("/download.pdf", params={
        "grade": "1", "operators": "-", "ranges": "0-9,0-9",
        "result_range": "100-200", "seed": "1"})
    assert r.status_code == 400
    assert "结果范围" in r.text
    assert "Traceback" not in r.text


def test_download_zip_generation_conflict_400_chinese():
    r = client.get("/download.zip", params={
        "grade": "1", "operators": "-", "ranges": "0-9,0-9",
        "result_range": "100-200", "seed": "1"})
    assert r.status_code == 400
    assert "结果范围" in r.text
