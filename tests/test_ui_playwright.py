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
    page.locator('button[type="submit"]').click()
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
