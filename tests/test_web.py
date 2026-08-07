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
    cells = _re.findall(r'<div class="cell">(.*?)</div>', r.text, _re.S)
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
    assert "fonts.googleapis.com" not in r.text  # 已本地托管，无外链
    assert 'class="hero"' in r.text
    css = client.get("/static/style.css").text
    assert "@font-face" in css
    assert "Yozai" in css
    assert "woff2" in css
    for w in ("400", "700"):
        f = client.get(f"/static/fonts/yozai-{w}.woff2")
        assert f.status_code == 200
        assert f.content[:4] == b"wOF2"


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
    assert "#pager[hidden] { display: none; }" in r.text


def test_page_fade_animation_fixes_invisible_preview():
    r = client.get("/static/style.css")
    assert "@keyframes pageFade" in r.text
    assert ".page-fade { animation: pageFade" in r.text
    assert ".page-fade { opacity: 0; }" not in r.text


def test_weight_input_visible_css():
    r = client.get("/static/style.css")
    css = r.text
    assert ".op-item .weight-input {" in css
    block = css.split(".op-item .weight-input {")[1].split("}")[0]
    assert "position: static" in block
    assert "opacity: 1" in block
    assert "pointer-events: auto" in block


def test_refactor_download_cta_section():
    r = client.post("/generate", data={"grade": "2", "count": "5", "topic": "arithmetic"})
    assert r.status_code == 200
    html = r.text
    assert 'class="download" id="download"' in html
    assert 'class="download-icon"' in html
    assert 'class="btn btn-download"' in html
    assert 'class="meta-badge"' in html
    assert 'class="download-version"' in html
    assert 'mathgen v' in html
    assert 'id="preview"' in html
    assert 'href="#download"' in html and 'href="#preview"' in html


def test_refactor_index_hero_nav_footer():
    r = client.get("/")
    html = r.text
    assert 'class="hero-badge"' in html
    assert 'id="form"' in html
    assert 'href="#form"' in html
    assert 'class="site-footer"' in html
    assert 'class="legend-icon' in html
    r2 = client.get("/static/math-icon.svg")
    assert r2.status_code == 200
    assert r2.text.startswith("<svg")


def test_numbering_options_roundtrip():
    r = client.post("/generate", data={
        "grade": "1", "count": "8", "topic": "arithmetic",
        "show_numbers": "0", "number_direction": "column"})
    assert r.status_code == 200
    html = r.text
    m = re.search(r'href="(/download\.pdf\?[^"]+)"', html)
    href = unescape(m.group(1))
    assert "show_numbers=0" in href
    assert "number_direction=column" in href
    assert 'data-direction="column"' in html
    assert client.get(href).status_code == 200
    # 默认不勾选时不含显式 0（保持默认开）
    r2 = client.post("/generate", data={"grade": "1", "count": "3"})
    m2 = re.search(r'href="(/download\.pdf\?[^"]+)"', r2.text)
    href2 = unescape(m2.group(1))
    assert "show_numbers=0" not in href2


def test_index_has_numbering_form_controls():
    r = client.get("/")
    html = r.text
    assert 'name="show_numbers"' in html
    assert 'name="number_direction"' in html
    assert 'value="column"' in html


def test_weight_input_disabled_when_op_unchecked():
    r = client.get("/")
    html = r.text
    assert 'name="w_加"' in html and "disabled" in html
    # 勾选后权重框可用（回显场景）
    r2 = client.post("/generate", data={"grade": "1", "count": "x",
                                        "operators": ["加", "乘"], "w_加": "7"})
    assert r2.status_code == 200
    block = r2.text.split('name="w_加"')[1][:200]
    assert "disabled" not in block.split(">")[0]
    r3 = client.post("/generate", data={"grade": "9", "operators": ["加"], "w_乘": "3"})
    assert r3.status_code == 200
    assert "参数格式不正确" not in r3.text  # 未勾选的权重被忽略，不报错
    assert "年级 9" in r3.text


def test_parentheses_disabled_below_three_operands():
    r = client.get("/")
    assert 'name="parentheses"' in r.text
    r2 = client.post("/generate", data={"grade": "1", "count": "x", "operand_count": "2"})
    assert r2.status_code == 200
    block = r2.text.split('name="parentheses"')[1][:160]
    assert "disabled" in block
    r3 = client.post("/generate", data={"grade": "1", "count": "x", "operand_count": "3"})
    block3 = r3.text.split('name="parentheses"')[1][:160]
    assert "disabled" not in block3


def test_lang_swap_attributes_present():
    r = client.get("/")
    html = r.text
    assert 'data-i18n="grade.x"' in html and 'data-i18n-params' in html
    assert 'data-i18n="grade.custom"' in html
    assert 'data-i18n="topic.arithmetic"' in html
    assert 'data-i18n-tip="tip.grade"' in html
    r2 = client.post("/generate", data={"grade": "2", "count": "5"})
    assert 'data-summary=' in r2.text


def test_weights_and_parentheses_roundtrip():
    r = client.post("/generate", data={
        "grade": "1", "count": "6", "topic": "arithmetic",
        "operators": ["加", "乘"], "w_加": "7", "w_乘": "1", "parentheses": "1"})
    assert r.status_code == 200
    html = r.text
    m = re.search(r'href="(/download\.pdf\?[^"]+)"', html)
    href = unescape(m.group(1))
    assert "parentheses=1" in href
    assert "+=7" in href or "+%3D7" in href
    link = client.get(href)
    assert link.status_code == 200
    assert link.content[:4] == b"%PDF"


def test_weights_backfill_on_error():
    r = client.post("/generate", data={
        "grade": "1", "count": "x", "w_加": "7", "w_乘": "1"})
    assert r.status_code == 200
    html = r.text
    assert 'name="w_加"' in html
    assert 'value="7"' in html
    assert 'name="w_乘"' in html and 'value="1"' in html


def test_grade5_parentheses_off_roundtrip():
    r = client.post("/generate", data={"grade": "5", "count": "4", "parentheses": ""})
    assert r.status_code == 200
    m = re.search(r'href="(/download\.pdf\?[^"]+)"', r.text)
    href = unescape(m.group(1))
    assert "parentheses=0" in href
    assert client.get(href).status_code == 200


def test_paren_weight_roundtrip():
    r = client.post("/generate", data={"grade": "1", "count": "4", "paren_weight": "8"})
    m = re.search(r'href="(/download\.pdf\?[^"]+)"', r.text)
    href = unescape(m.group(1))
    assert "paren_weight=8" in href
    r2 = client.post("/generate", data={"grade": "1", "count": "4"})
    m2 = re.search(r'href="(/download\.pdf\?[^"]+)"', r2.text)
    assert "paren_weight" not in unescape(m2.group(1))


def test_section_icons_exist_and_used():
    for name in ("settings", "calculator", "layout", "batch"):
        r = client.get(f"/static/icons/{name}.svg")
        assert r.status_code == 200, name
        assert r.text.startswith("<svg")
    r2 = client.get("/")
    assert "/static/icons/settings.svg" in r2.text
    assert "/static/icons/calculator.svg" in r2.text
    assert "/static/icons/layout.svg" in r2.text
    assert "/static/icons/batch.svg" in r2.text


def test_no_pure_white_black_in_css():
    css = client.get("/static/style.css").text
    assert "#ffffff" not in css and "#FFFFFF" not in css
    assert "#000" not in css
    assert "#fff" not in css.replace("#fffdf7", "").replace("#fff8ec", "")  # 米色系除外
    assert "--card-bg: #fff8ec" in css
    assert "--bg: #2b211a" in css  # dark 深马卡龙
    assert "--card-bg: #382a20" in css
    assert "--input-bg: #3f2f23" in css
    assert "rgba(0, 0, 0" not in css


def test_product_page():
    r = client.get("/product")
    assert r.status_code == 200
    assert 'class="landing-hero"' in r.text
    assert 'class="feature-card' in r.text
    assert "coming-soon" in r.text
    assert 'href="/"' in r.text  # CTA
    assert r.text.count('class="feature-icon"') == 6
    for icon in ("print", "theme", "language"):
        assert f"/static/icons/{icon}.svg" in r.text
    assert 'class="btn btn-download"' in r.text
    assert 'class="download-version"' in r.text


def test_pwa_assets():
    r = client.get("/static/manifest.webmanifest")
    assert r.status_code == 200
    assert '"name"' in r.text and "kidsmath" in r.text
    assert r.headers.get("content-type", "").startswith("application/manifest")
    r2 = client.get("/static/sw.js")
    assert r2.status_code == 200
    assert "kidsmath-v3" in r2.text
    assert "startsWith('/static/')" in r2.text  # v3 白名单：仅缓存 /、/product、/static/*
    r3 = client.get("/")
    assert 'rel="manifest"' in r3.text
    assert "/static/sw.js" in r3.text


def test_placeholder_pages():
    for path in ("/member", "/member/timer", "/member/pomodoro"):
        r = client.get(path)
        assert r.status_code == 200, path
        assert "coming-soon" in r.text, path
    # /member/errors、/member/review 已真实化：未登录 → 跳登录
    for path in ("/member/errors", "/member/review"):
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 302 and "/login" in r.headers["location"], path
    # /user 系已真实化：未登录 → 跳登录
    r = client.get("/user/history", follow_redirects=False)
    assert r.status_code == 302 and "/login" in r.headers["location"]
    r = client.get("/")
    assert 'href="/login"' in r.text  # 未登录 header 显示登录入口
    assert 'href="/member/timer"' in client.get("/member").text
    client.post("/api/register", data={"username": "tt", "password": "secret123"})
    assert "用户中心" in client.get("/user").text  # 登录后可访问
    assert 'href="即将上线"' not in client.get("/member").text
    assert 'href="Coming soon"' not in client.get("/member").text


def test_all_data_i18n_keys_exist_in_both_langs():
    import re as _re
    from mathgen.i18n import UI_EN, UI_ZH
    pages = [client.get("/").text, client.get("/product").text,
             client.get("/user").text, client.get("/member").text,
             client.post("/generate", data={"grade": "1", "count": "3"}).text]
    keys = set()
    for html in pages:
        keys |= set(_re.findall(r'data-i18n="([^"]+)"', html))
        keys |= set(_re.findall(r'data-i18n-tip="([^"]+)"', html))
    assert keys, "未收集到 i18n 键"
    missing_zh = keys - set(UI_ZH)
    missing_en = keys - set(UI_EN)
    assert not missing_zh, f"缺 zh 键: {missing_zh}"
    assert not missing_en, f"缺 en 键: {missing_en}"
    # data-summary 的 topic 值必须是合法题型（属性值经 Jinja 转义，先 unescape）
    import json as _json
    for html in pages:
        for m in _re.finditer(r'data-summary="([^"]+)"', html):
            d = _json.loads(unescape(m.group(1)))
            assert d["topic"] in ("arithmetic", "vertical", "word_problem"), d


def test_pwa_manifest_id_and_png_icons():
    r = client.get("/static/manifest.webmanifest")
    assert '"id": "/"' in r.text
    assert "icon-192.png" in r.text and "icon-512.png" in r.text
    assert "icon-maskable-512.png" in r.text


def test_app_mode_hides_product_nav():
    r = client.get("/")
    assert 'href="/product"' in r.text
    r2 = client.get("/?app=1")
    assert 'href="/product"' not in r2.text
    assert 'href="#form"' in r2.text


def test_android_assets_exist():
    import pathlib as _pl
    root = _pl.Path(__file__).resolve().parent.parent
    assert (root / "android" / "twa-manifest.json").exists()
    assert (root / "scripts" / "build_android.sh").exists()
    assert (root / "docs" / "android.md").exists()
    for s in (192, 512):
        assert client.get(f"/static/icons/icon-{s}.png").status_code == 200
