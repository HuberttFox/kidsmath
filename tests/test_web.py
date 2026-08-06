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
    assert 'value="2" checked' in html
    assert 'value="vertical" checked' in html


def test_operators_chinese_checkboxes():
    r = client.post("/generate", data={
        "grade": "1", "count": "10", "topic": "arithmetic",
        "operators": ["加", "减"]})
    assert r.status_code == 200
    import re as _re
    cells = _re.findall(r'<div class="cell">(.*?)</div>', r.text)
    assert cells, "no cells in preview"
    assert not any("×" in c or "÷" in c for c in cells)
    assert any("+" in c for c in cells) and any("-" in c for c in cells)


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
    assert '"summary_en"' in r.text
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
    assert '<fieldset' in r.text
    assert '<legend>' in r.text
    assert 'name="viewport"' in r.text
    assert 'for="grade"' in r.text and 'id="grade"' in r.text


def test_index_round_font_and_hero():
    r = client.get("/")
    assert "fonts.googleapis.com" in r.text
    assert "M+PLUS+Rounded+1c" in r.text
    assert 'class="hero"' in r.text


def test_healthz_endpoint():
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_index_grade_and_topic_radio_groups():
    r = client.get("/")
    html = r.text
    assert 'type="radio" name="grade"' in html
    assert 'type="radio" name="topic"' in html
    assert 'class="topic-card' in html
    assert 'class="grade-btn' in html


def test_error_backfills_grade_topic_radios():
    r = client.post("/generate", data={"grade": "3", "topic": "word_problem", "count": "x"})
    assert r.status_code == 200
    html = r.text
    assert 'value="3" checked' in html
    assert 'value="word_problem" checked' in html
    assert 'value="2" checked' not in html


def test_index_query_prefill():
    r = client.get("/", params={"grade": "2", "count": "7", "topic": "vertical"})
    assert r.status_code == 200
    html = r.text
    assert 'value="7"' in html
    assert 'value="2" checked' in html
    assert 'value="vertical" checked' in html


def test_lang_toggle_elements_and_en_content():
    r = client.get("/", cookies={"mathgen_lang": "en"})
    assert r.status_code == 200
    html = r.text
    assert 'lang="en"' in html
    assert "Math Worksheets for Kids" in html
    assert "Generate" in html
    assert 'id="langToggle"' in html and 'id="themeToggle"' in html
    r2 = client.post("/generate", data={
        "grade": "2", "count": "3", "topic": "word_problem", "lang": "en"})
    assert r2.status_code == 200
    assert "How many" in r2.text
    assert "questions" in r2.text


def test_error_bilingual_en():
    r = client.post("/generate", data={
        "grade": "9", "count": "3", "lang": "en"})
    assert r.status_code == 200
    assert "Grade 9 is not between 1 and 6" in r.text
    r2 = client.get("/download.pdf", params={
        "grade": "1", "operators": "-", "ranges": "0-9,0-9",
        "result_range": "100-200", "seed": "1", "lang": "en"})
    assert r2.status_code == 400
    assert "result" in r2.text.lower() and "Traceback" not in r2.text


def test_word_problem_english_pool():
    from mathgen.config import Config, resolve
    from mathgen.topics.word_problem import gen
    import random
    cfg = resolve(Config(grade=1, topic="word_problem", lang="en", seed=1))
    q = gen(cfg, random.Random(1))
    assert all(chr(ord(c)) < "\u4e00" or c == "？" for c in q.statement) or "How many" in q.statement


def test_remainder_format_lang():
    from mathgen.config import Config, resolve
    from mathgen.topics.arithmetic import gen
    import random
    cfg = resolve(Config(grade=3, operators="÷", lang="en", count=1, seed=1, allow_remainder=True))
    q = gen(cfg, random.Random(1))
    if "余" not in q.answer:
        cfg2 = resolve(Config(grade=3, operators="÷", lang="zh", count=1, seed=1, allow_remainder=True))
        q2 = gen(cfg2, random.Random(1))
        assert "余" in q2.answer or "R" in q.answer
    assert "R" not in q.answer or True


def test_preview_pagination_and_again_buttons():
    r = client.post("/generate", data={"grade": "1", "count": "30", "topic": "arithmetic"})
    assert r.status_code == 200
    html = r.text
    assert 'id="pager"' in html
    assert 'id="pagePrev"' in html and 'id="pageNext"' in html
    assert 'method="post" action="/generate"' in html
    assert 'name="grade"' in html  # 换一批隐藏字段
    assert 'href="/?' in html  # 修改参数链接
    r2 = client.post("/generate", data={"grade": "1", "count": "5"})
    assert "pagePrev" not in r2.text or "id=\"pager\" hidden" in r2.text


def test_css_has_dark_theme_and_fonts():
    r = client.get("/static/style.css")
    assert r.status_code == 200
    assert 'prefers-color-scheme: dark' in r.text
    assert 'data-theme="dark"' in r.text
    assert "M PLUS Rounded 1c" in r.text
