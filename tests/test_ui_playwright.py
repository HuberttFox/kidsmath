import json
import re

"""HTML 按钮选取交互测试（Playwright 真实浏览器）。

fixture 起本地 uvicorn 服务，用 Chromium 点击驱动验证 JS 联动：
年级预设回填、权重框禁用、切自定义、括号禁用、语言/主题切换、生成-预览-下载全链路。
"""
import threading

import pytest
import uvicorn

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

from mathgen.web import app  # noqa: E402

BASE = "http://127.0.0.1:18099"


@pytest.fixture(scope="module")
def server():
    config = uvicorn.Config(app, host="127.0.0.1", port=18099, log_level="warning")
    srv = uvicorn.Server(config)
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        import time
        time.sleep(0.05)
    yield
    srv.should_exit = True
    t.join(timeout=5)


@pytest.fixture()
def page(server):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        pg = browser.new_page()
        yield pg
        browser.close()


def test_grade_preset_backfills_fields(page):
    page.goto(BASE + "/")
    page.locator('label.grade-btn:has-text("2 年级")').click()
    checked = page.locator('input[name="operators"]:checked')
    expect(checked).to_have_count(3)  # + - ×
    expect(page.locator('#table')).to_have_value("1-9")
    expect(page.locator('#ranges')).to_have_value("1-99,1-99")
    expect(page.locator('#result_range')).to_have_value("0-100")


def test_weight_input_disabled_follows_checkbox(page):
    page.goto(BASE + "/")
    page.locator('#advanced summary').click()
    box = page.locator('.op-item:has-text("乘") .weight-input')
    expect(box).to_be_disabled()
    page.locator('.op-item:has-text("乘")').click()
    expect(box).to_be_enabled()
    page.locator('.op-item:has-text("乘")').click()
    expect(box).to_be_disabled()


def test_manual_change_switches_grade_to_custom(page):
    page.goto(BASE + "/")
    page.locator('label.grade-btn:has-text("2 年级")').click()
    page.locator('#advanced summary').click()
    page.locator('#gap').fill("30")
    page.locator('#gap').dispatch_event("change")
    expect(page.locator('input[name="grade"][value=""]')).to_be_checked()
    expect(page.locator('#preset-hint')).to_contain_text("自定义")


def test_parentheses_disabled_below_three_operands(page):
    page.goto(BASE + "/")
    page.locator('#advanced summary').click()
    paren = page.locator('#parentheses')
    expect(paren).to_be_disabled()
    page.locator('#operand_count').fill("3")
    page.locator('#operand_count').dispatch_event("change")
    expect(paren).to_be_enabled()
    page.locator('#operand_count').fill("2")
    page.locator('#operand_count').dispatch_event("change")
    expect(paren).to_be_disabled()


def test_language_switch_updates_ui_texts(page):
    page.goto(BASE + "/")
    page.locator('#langToggle').click()
    expect(page.locator('.hero-title')).to_have_text("Math Worksheets for Kids")
    expect(page.locator('label.field-label:has-text("Grade")')).to_be_visible()
    page.locator('#langToggle').click()
    expect(page.locator('.hero-title')).to_have_text("给孩子出数学题")


def test_theme_toggle_changes_data_theme(page):
    page.goto(BASE + "/")
    page.locator('#themeToggle').click()
    expect(page.locator("html")).to_have_attribute("data-theme", "light")
    page.locator('#themeToggle').click()
    expect(page.locator("html")).to_have_attribute("data-theme", "dark")
    page.locator('#themeToggle').click()
    expect(page.locator("html")).not_to_have_attribute("data-theme", "dark")


def test_generate_preview_and_download_flow(page):
    page.goto(BASE + "/")
    page.locator('label.grade-btn:has-text("2 年级")').click()
    page.locator('#count').fill("6")
    page.locator('#generateBtn').click()
    expect(page.locator('#download')).to_be_visible()
    expect(page.locator('.cell')).to_have_count(6)
    first_batch = page.locator('.cell').all_text_contents()
    page.locator('.inline-form button[type="submit"]').click()
    expect(page.locator('.cell')).to_have_count(6)
    second_batch = page.locator('.cell').all_text_contents()
    assert first_batch != second_batch, "换一批应生成不同题目"
    with page.expect_download() as dl:
        page.locator('.btn-download').click()
    path = dl.value.path()
    with open(path, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_preview_per_page_and_jump(page):
    page.goto(BASE + "/")
    page.locator('label.grade-btn:has-text("2 年级")').click()
    page.locator('#count').fill("30")
    page.locator('#generateBtn').click()
    expect(page.locator('#pager')).to_be_visible()
    visible = page.locator('.cell:visible')
    expect(visible).to_have_count(12)  # 默认 2 列 × 6 行
    page.locator('#perPage').select_option("6")
    expect(visible).to_have_count(6)
    expect(page.locator('#pageLabel')).to_contain_text("5")  # 30/6=5 页
    page.locator('#jumpInput').fill("3")
    page.locator('#jumpBtn').click()
    expect(page.locator('#pageLabel')).to_contain_text("3")
    page.locator('#jumpInput').fill("99")
    page.locator('#jumpBtn').click()
    expect(page.locator('#pageLabel')).to_contain_text("5")  # 越界钳制


def test_column_major_pagination_continues_counting(page):
    # 16 题 2 列竖向编号 + 每页 12 格（6 行）→ 第 1 页左列 1-6、第 2 页左列继续 7
    page.goto(BASE + "/")
    page.locator('#advanced summary').click()
    page.locator('#operand_count').fill("2")
    page.locator('#operand_count').dispatch_event("change")
    page.locator('#count').fill("16")
    page.locator('#number_direction').select_option("column")
    page.locator('#generateBtn').click()
    expect(page.locator('#pager')).to_be_visible()
    first = page.locator('.cell:visible').first.inner_text()
    assert first.startswith("1."), first
    page.locator('#pageNext').click()
    second_first = page.locator('.cell:visible').first.inner_text()
    assert second_first.startswith("7."), second_first  # 左列继续计数


def test_font_uniform_yozai(page):
    page.goto(BASE + "/")
    page.evaluate("document.fonts.ready.then(() => true)")
    for sel in ("body", "h1", "button", "input[type=text]", "input[type=number]",
                "select", ".grade-btn span", ".topic-label", ".pill-toggle"):
        font = page.locator(sel).first.evaluate("el => getComputedStyle(el).fontFamily")
        assert "Yozai" in font, f"{sel}: {font}"
    css = page.request.get(BASE + "/static/style.css").text()
    assert css.count('font-family: "Yozai"') == 3, "Yozai 声明应仅 @font-face×2 + body"
    assert css.count("font-family: inherit") == 2, "inherit 声明应仅 2 处（无元素级覆盖）"


def test_language_switch_all_elements(page):
    page.goto(BASE + "/")
    page.locator('#langToggle').click()  # → EN
    keys = page.evaluate("""() => Array.from(document.querySelectorAll('[data-i18n]'))
        .map(el => el.getAttribute('data-i18n'))""")
    assert keys, "无 data-i18n 元素"
    for key in keys:
        text = page.locator(f'[data-i18n="{key}"]').first.evaluate("el => el.textContent")
        assert text.strip() and text != key, f"键 {key} 未切换: {text!r}"


def test_macaron_no_pure_white_black_render(page):
    page.goto(BASE + "/")
    for theme in ("light", "dark"):
        if theme == "dark":
            page.locator('#themeToggle').click()
        for sel in ("body", "input[type=text]", "input[type=number]", "select"):
            nums = page.locator(sel).first.evaluate(
                "el => { const m = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g); return m ? m.map(Number) : []; }")
            if len(nums) == 4 and nums[3] == 0:
                continue  # 透明背景（渐变卡）
            assert not (nums[0] >= 250 and nums[1] >= 250 and nums[2] >= 250), f"{theme}/{sel}: 纯白 {nums}"
            assert not (nums[0] <= 5 and nums[1] <= 5 and nums[2] <= 5), f"{theme}/{sel}: 纯黑 {nums}"


def test_export_formaction_downloads_current_fields(page):
    page.goto(BASE + "/")
    page.locator('label.grade-btn:has-text("3 年级")').click()
    page.locator('#count').fill("8")
    with page.expect_download() as dl:
        page.locator('button[formaction="/api/config/export"]').click()
    download = dl.value
    assert download.suggested_filename == "kidsmath-config.json"
    stream = download.path()
    data = json.load(open(stream, encoding="utf-8"))
    assert data["version"] == 1
    assert data["config"]["grade"] == "3" and data["config"]["count"] == "8"


def test_register_login_flow_and_history_page(page):
    username = "试用户"
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.locator('label.grade-btn:has-text("1 年级")').click()
    page.locator('#generateBtn').click()
    expect(page.locator('#download')).to_be_visible()
    page.goto(BASE + "/user/history")
    expect(page.locator("text=重新生成")).to_be_visible()
    expect(page.locator("text=grade=1")).to_be_visible()
    page.goto(BASE + "/user/saved")
    expect(page.locator("text=还没有保存的配置")).to_be_visible()


def test_timer_start_pause_reset(page):
    page.goto(BASE + "/member/timer")
    page.locator("#timerStart").click()
    page.wait_for_timeout(1200)
    sec = int(page.locator("#timerDisplay").inner_text().split(":")[1])
    assert 0 < sec <= 59
    page.locator("#timerPause").click()
    frozen = page.locator("#timerDisplay").inner_text()
    page.wait_for_timeout(1200)
    assert page.locator("#timerDisplay").inner_text() == frozen
    page.locator("#timerReset").click()
    assert page.locator("#timerDisplay").inner_text() == "05:00"


def test_pomodoro_chime_and_title_flash(page):
    page.goto(BASE + "/member/pomodoro")
    page.evaluate("window.__chimeCalled = false; "
                  "window.playChime = function () { window.__chimeCalled = true; };")
    page.locator("#focusMin").fill("0")
    page.locator("#focusSec").fill("1")
    page.locator("#pomodoroStart").click()
    page.wait_for_timeout(2500)
    assert page.evaluate("window.__chimeCalled")
    assert "time-up" in page.locator("body").get_attribute("class")


def test_review_flip_and_complete(page):
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill("复习用户")
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.locator('label.grade-btn:has-text("1 年级")').click()
    page.locator('#generateBtn').click()
    expect(page.locator('#download')).to_be_visible()
    page.goto(BASE + "/user/history")
    page.locator('a:has-text("打开详情")').first.click()
    page.wait_for_url(BASE + "/user/history/**")
    page.locator('input[name="questions"]').first.check()
    page.locator('button[data-i18n="history.capture"]').click()
    page.wait_for_url(BASE + "/member/errors")
    page.goto(BASE + "/member/review")
    expect(page.locator("text=显示答案")).to_be_visible()
    page.locator("#showAnswer").click()
    expect(page.locator("#answerReveal")).to_be_visible()
    page.locator('button[name="q"][value="5"]').click()
    expect(page.locator("text=今日全部完成")).to_be_visible()


def test_ai_parse_backfill_form_values(page):
    page.goto(BASE + "/member/ai")
    page.locator('textarea[name="text"]').fill("12 + 34 = 46\n23 - 11 = 12")
    page.locator('button[data-i18n="ai.parse"]').click()
    expect(page.locator("text=识别 2/2 题")).to_be_visible()
    page.locator('button[data-i18n="ai.backfill"]').click()
    page.wait_for_url(BASE + "/**")
    expect(page.locator('label.grade-btn:has-text("2 年级") input')).to_be_checked()
    expect(page.locator('input[name="operators"][value="加"]')).to_be_checked()


def test_import_button_auto_submits(page):
    page.goto(BASE + "/")
    page.set_input_files('input[type="file"][name="file"]',
                         {"name": "kidsmath-config.json", "mimeType": "application/json",
                          "buffer": bytes(json.dumps({"version": 1, "config": {"grade": "1", "count": "5"}}), "utf-8")})
    page.wait_for_url(BASE + "/**")
    expect(page.locator('#count')).to_have_value("5")
