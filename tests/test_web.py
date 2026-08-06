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


def test_error_backfills_submitted_values():
    r = client.post("/generate", data={
        "grade": "2", "count": "5", "topic": "vertical", "operators": "%"})
    assert r.status_code == 200
    html = r.text
    assert "运算符" in html
    assert 'value="5"' in html
    assert 'value="2" selected' in html
    assert 'value="vertical" selected' in html


def test_operators_chinese_checkboxes():
    r = client.post("/generate", data={
        "grade": "1", "count": "10", "topic": "arithmetic",
        "operators": ["加", "减"]})
    assert r.status_code == 200
    assert "×" not in r.text and "÷" not in r.text
    assert "+" in r.text and "-" in r.text


def test_operators_checkbox_backfill_on_error():
    r = client.post("/generate", data={
        "grade": "9", "operators": ["加", "乘"]})
    assert r.status_code == 200
    html = r.text
    assert 'value="加" checked' in html
    assert 'value="乘" checked' in html
    assert 'value="减" checked' not in html


def test_preset_hints_embedded():
    r = client.get("/")
    assert r.status_code == 200
    assert 'id="preset-hints"' in r.text
    assert '"grades"' in r.text
    assert '"topics"' in r.text
    assert '"fields"' in r.text
    assert '"ops"' in r.text


def test_preview_shows_columns_grid():
    r = client.post("/generate", data={"grade": "2", "count": "5", "topic": "arithmetic"})
    assert r.status_code == 200
    html = r.text
    assert 'class="sheet' in html
    assert 'grid-template-columns: repeat(2' in html
    assert html.count('class="cell"') == 5


def test_index_has_semantic_structure():
    r = client.get("/")
    assert '<fieldset>' in r.text
    assert '<legend>' in r.text
    assert 'name="viewport"' in r.text
    assert 'for="grade"' in r.text and 'id="grade"' in r.text
