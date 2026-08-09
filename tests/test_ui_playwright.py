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


def _stage(page):
    """工作台壳内 iframe 的定位器（表单在 iframe 内）。"""
    return page.frame_locator("#stage")


def _assert_no_horizontal_overflow(locator):
    assert locator.evaluate("el => el.scrollWidth <= el.clientWidth + 1")


def _stage_height(page):
    return page.locator(".workbench-stage").evaluate("el => el.getBoundingClientRect().height")


def _embedded_scroll_metrics(page):
    return page.evaluate("""() => {
        const doc = document.getElementById('stage').contentDocument;
        return {
            viewport: doc.documentElement.clientHeight,
            content: Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight),
            outerViewport: document.documentElement.clientHeight,
            outerContent: document.documentElement.scrollHeight,
        };
    }""")


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
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("2 年级")').click()
    checked = stage.locator('input[name="operators"]:checked')
    expect(checked).to_have_count(3)  # + - ×
    expect(stage.locator('#table')).to_have_value("1-9")
    expect(stage.locator('#ranges')).to_have_value("1-99,1-99")
    expect(stage.locator('#result_range')).to_have_value("0-100")


def test_weight_input_disabled_follows_checkbox(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('#advanced summary').click()
    box = stage.locator('.op-item:has-text("乘") .weight-input')
    expect(box).to_be_disabled()
    stage.locator('.op-item:has-text("乘")').click()
    expect(box).to_be_enabled()
    stage.locator('.op-item:has-text("乘")').click()
    expect(box).to_be_disabled()


def test_manual_change_switches_grade_to_custom(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("2 年级")').click()
    stage.locator('#advanced summary').click()
    stage.locator('#gap').fill("30")
    stage.locator('#gap').dispatch_event("change")
    expect(stage.locator('input[name="grade"][value=""]')).to_be_checked()
    expect(stage.locator('#preset-hint')).to_contain_text("自定义")


def test_parentheses_disabled_below_three_operands(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('#advanced summary').click()
    paren = stage.locator('#parentheses')
    expect(paren).to_be_disabled()
    stage.locator('#operand_count').fill("3")
    stage.locator('#operand_count').dispatch_event("change")
    expect(paren).to_be_enabled()
    stage.locator('#operand_count').fill("2")
    stage.locator('#operand_count').dispatch_event("change")
    expect(paren).to_be_disabled()


def test_language_switch_updates_ui_texts(page):
    page.goto(BASE + "/")
    page.wait_for_timeout(1200)
    page.locator('#langToggle').click()
    page.wait_for_timeout(1800)
    stage = _stage(page)
    expect(stage.locator('.hero-title')).to_have_text("Math Worksheets for Kids")
    page.locator('#langToggle').click()
    page.wait_for_timeout(1800)
    expect(stage.locator('.hero-title')).to_have_text("给孩子出数学题")


def test_theme_toggle_changes_data_theme(page):
    page.goto(BASE + "/")
    page.wait_for_timeout(1200)
    page.locator('#themeToggle').click()
    page.wait_for_timeout(1500)
    stage = _stage(page)
    expect(stage.locator("html")).to_have_attribute("data-theme", "light")
    page.locator('#themeToggle').click()
    page.wait_for_timeout(1500)
    expect(stage.locator("html")).to_have_attribute("data-theme", "dark")
    page.locator('#themeToggle').click()
    page.wait_for_timeout(1500)
    expect(stage.locator("html")).not_to_have_attribute("data-theme", "dark")


def test_generate_preview_and_download_flow(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("2 年级")').click()
    stage.locator('#count').fill("6")
    stage.locator('#generateBtn').click()
    expect(stage.locator('#download')).to_be_visible()
    expect(stage.locator('.cell')).to_have_count(6)
    first_batch = stage.locator('.cell').all_text_contents()
    with page.expect_event("framenavigated", predicate=lambda frame: frame.name == "stage"):
        stage.locator('.inline-form button[type="submit"]').click()
    expect(stage.locator('.cell')).to_have_count(6)
    second_batch = stage.locator('.cell').all_text_contents()
    assert first_batch != second_batch, "换一批应生成不同题目"
    with page.expect_download() as dl:
        stage.locator('.btn-download').click()
    path = dl.value.path()
    with open(path, "rb") as f:
        assert f.read(4) == b"%PDF"


def test_preview_per_page_and_jump(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("2 年级")').click()
    stage.locator('#count').fill("30")
    stage.locator('#generateBtn').click()
    expect(stage.locator('#pager')).to_be_visible()
    visible = stage.locator('.cell:visible')
    expect(visible).to_have_count(12)  # 默认 2 列 × 6 行
    stage.locator('#perPage').select_option("6")
    expect(visible).to_have_count(6)
    expect(stage.locator('#pageLabel')).to_contain_text("5")  # 30/6=5 页
    stage.locator('#jumpInput').fill("3")
    stage.locator('#jumpBtn').click()
    expect(stage.locator('#pageLabel')).to_contain_text("3")
    stage.locator('#jumpInput').fill("99")
    stage.locator('#jumpBtn').click()
    expect(stage.locator('#pageLabel')).to_contain_text("5")  # 越界钳制


def test_column_major_pagination_continues_counting(page):
    # 16 题 2 列竖向编号 + 每页 12 格（6 行）→ 第 1 页左列 1-6、第 2 页左列继续 7
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('#advanced summary').click()
    stage.locator('#operand_count').fill("2")
    stage.locator('#operand_count').dispatch_event("change")
    stage.locator('#count').fill("16")
    stage.locator('#number_direction').select_option("column")
    stage.locator('#generateBtn').click()
    expect(stage.locator('#pager')).to_be_visible()
    first = stage.locator('.cell:visible').first.inner_text()
    assert first.startswith("1."), first
    stage.locator('#pageNext').click()
    second_first = stage.locator('.cell:visible').first.inner_text()
    assert second_first.startswith("7."), second_first  # 左列继续计数


def test_font_uniform_yozai(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    page.evaluate("document.fonts.ready.then(() => true)")
    for sel in ("body", "h1", "button", "input[type=text]", "input[type=number]",
                "select", ".grade-btn span", ".topic-label", ".pill-toggle"):
        font = stage.locator(sel).first.evaluate("el => getComputedStyle(el).fontFamily")
        assert "Yozai" in font, f"{sel}: {font}"
    css = page.request.get(BASE + "/static/style.css").text()
    assert css.count('font-family: "Yozai"') == 3, "Yozai 声明应仅 @font-face×2 + body"
    assert css.count("font-family: inherit") == 2, "inherit 声明应仅 2 处（无元素级覆盖）"


def test_language_switch_all_elements(page):
    page.goto(BASE + "/")
    page.locator('#langToggle').click()  # 壳顶栏 → EN（iframe 随 langchange 重载）
    page.wait_for_timeout(1500)
    stage = _stage(page)
    keys = stage.locator("[data-i18n]").evaluate_all("""(els) => els.map(el => el.getAttribute('data-i18n'))""")
    assert keys, "无 data-i18n 元素"
    for key in keys[:40]:
        text = stage.locator(f'[data-i18n="{key}"]').first.evaluate("el => el.textContent")
        assert text.strip() and text != key, f"键 {key} 未切换: {text!r}"


def test_macaron_no_pure_white_black_render(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    for theme in ("light", "dark"):
        if theme == "dark":
            page.locator('#themeToggle').click()
            page.wait_for_timeout(1500)
        for sel in ("body", "input[type=text]", "input[type=number]", "select"):
            nums = stage.locator(sel).first.evaluate(
                "el => { const m = getComputedStyle(el).backgroundColor.match(/[\\d.]+/g); return m ? m.map(Number) : []; }")
            if len(nums) == 4 and nums[3] == 0:
                continue  # 透明背景（渐变卡）
            assert not (nums[0] >= 250 and nums[1] >= 250 and nums[2] >= 250), f"{theme}/{sel}: 纯白 {nums}"
            assert not (nums[0] <= 5 and nums[1] <= 5 and nums[2] <= 5), f"{theme}/{sel}: 纯黑 {nums}"


def test_settings_export_downloads_full_backup_zip(page):
    # 导出设置已移到用户页，导出为全量备份 zip（含 settings.json）
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill("备份用户")
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.goto(BASE + "/user")
    with page.expect_download() as dl:
        page.locator('a[href="/api/settings/export"]').click()
    download = dl.value
    assert download.suggested_filename.startswith("kidsmath-settings-")
    import zipfile
    with zipfile.ZipFile(download.path()) as z:
        data = json.loads(z.read("settings.json"))
        assert data["version"] == 2


def test_register_login_flow_and_history_page(page):
    username = "试用户"
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.wait_for_timeout(1200)
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("1 年级")').click()
    stage.locator('#generateBtn').click()
    expect(stage.locator('#download')).to_be_visible()
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
    page.locator("#focusMin").fill("0.0167")  # ≈1 秒（秒输入已移除，用分钟小数）
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
    page.wait_for_timeout(1200)
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("1 年级")').click()
    stage.locator('#generateBtn').click()
    expect(stage.locator('#download')).to_be_visible()
    page.goto(BASE + "/user/history")
    page.locator('a:has-text("打开详情")').first.click()
    page.wait_for_url(BASE + "/user/history/**")
    page.locator('input[name="questions"]').first.check()
    page.locator('button[data-i18n="history.capture"]').click()
    page.wait_for_url(BASE + "/member/errors")
    page.goto(BASE + "/member/review")
    expect(page.locator("text=显示答案")).to_be_visible()
    page.locator(".review-show").click()
    expect(page.locator(".answer-reveal")).to_be_visible()
    page.locator('.review-grade[data-q="5"]').click()
    expect(page.locator("text=今日全部完成")).to_be_visible()


def test_ai_parse_backfill_form_values(page):
    page.goto(BASE + "/member/ai")
    page.locator('textarea[name="text"]').fill("12 + 34 = 46\n23 - 11 = 12")
    page.locator('button[data-i18n="ai.parse"]').click()
    expect(page.locator("text=识别 2/2 题")).to_be_visible()
    page.locator('button[data-i18n="ai.backfill"]').click()
    page.wait_for_url(BASE + "/**")
    page.wait_for_timeout(1500)
    stage = _stage(page)
    expect(stage.locator('label.grade-btn:has-text("2 年级") input')).to_be_checked()
    expect(stage.locator('input[name="operators"][value="加"]')).to_be_checked()


def test_settings_import_restores_backup(page):
    # 导入设置移到用户页；上传合法 zip → 覆盖还原 → ?restored=1
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill("导入用户")
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.goto(BASE + "/user")
    import io
    import zipfile
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("settings.json", json.dumps({
            "version": 2, "exported_at": "2026-01-01T00:00:00", "data": {}}))
    page.locator('form[action="/api/settings/import"] input[type="file"]').set_input_files(
        {"name": "backup.zip", "mimeType": "application/zip", "buffer": buf.getvalue()})
    page.wait_for_url(BASE + "/user?restored=1")


def test_topbar_nav_and_content_pages(page):
    page.goto(BASE + "/")
    for label in ("产品介绍", "功能使用", "会员介绍", "文档说明"):
        expect(page.locator(f'header nav a:has-text("{label}")')).to_be_visible()
    expect(page.locator('header nav a:has-text("用户信息")')).to_have_count(0)  # 未登录隐藏
    for path in ("/guide", "/docs", "/member"):
        page.goto(BASE + path)
        expect(page.locator("main")).to_be_visible()
        assert "Kids Math" in page.title()


def test_change_password_then_login_with_new(page):
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill("改密用户")
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.goto(BASE + "/user")
    page.locator('#pwForm input[name="old"]').fill("secret123")
    page.locator('#pwForm input[name="new"]').fill("newpass456")
    page.locator('#pwForm input[name="confirm"]').fill("newpass456")
    page.locator('#pwForm button[type="submit"]').click()
    page.wait_for_url(BASE + "/user?pw=ok")
    # 清会话后新旧密码
    page.context.clear_cookies()
    page.goto(BASE + "/login")
    page.locator('input[name="username"]').fill("改密用户")
    page.locator('input[name="password"]').fill("secret123")  # 旧密码应失败
    page.locator('button[type="submit"]').click()
    page.wait_for_timeout(1500)
    expect(page.locator('.error')).to_contain_text("用户名或密码错误")  # 失败提示
    page.locator('input[name="username"]').fill("改密用户")  # 失败重渲染会清空表单
    page.locator('input[name="password"]').fill("newpass456")  # 新密码成功
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    expect(page.locator('.user-chip:has-text("改密用户")')).to_be_visible()


def test_sidebar_switches_stage_without_reload(page):
    page.goto(BASE + "/")
    page.wait_for_timeout(1000)
    assert page.evaluate("document.getElementById('stage').src").endswith("/?embed=1")
    page.locator('.side-item:has-text("番茄钟")').click()
    page.wait_for_timeout(2000)
    src = page.evaluate("document.getElementById('stage').src")
    assert "/member/pomodoro" in src and "embed=1" in src
    assert page.evaluate("location.hash") == "#/member/pomodoro"
    assert page.evaluate("document.querySelector('.side-active').textContent").find("番茄钟") >= 0
    page.locator('.side-item:has-text("出题")').click()
    page.wait_for_timeout(1500)
    assert "embed=1" in page.evaluate("document.getElementById('stage').src")
    expect(page.frame_locator("#stage").locator('#generateBtn')).to_be_visible()


def test_theme_lang_switch_keeps_form_config(page):
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('label.grade-btn:has-text("2 年级")').click()
    stage.locator('#count').fill("7")
    # 主题切换不得重载 iframe / 清空表单
    page.locator('#themeToggle').click()
    page.wait_for_timeout(900)
    expect(stage.locator('#count')).to_have_value("7")
    # 语言切换同样保留
    page.locator('#langToggle').click()
    page.wait_for_timeout(900)
    expect(stage.locator('#count')).to_have_value("7")
    expect(stage.locator('input[name="grade"][value="2"]')).to_be_checked()


def test_ai_wizard_guided_backfill(page):
    page.goto(BASE + "/member/ai")
    page.locator('#tab-wizard').click()
    page.locator('#wiz-step-1 button[onclick="wizNext(1)"]').click()
    page.wait_for_timeout(200)
    page.locator('#wiz-step-2 label.grade-btn:has-text("3 年级")').click()
    page.locator('#wiz-step-2 button[onclick="wizNext(2)"]').click()
    page.wait_for_timeout(200)
    page.locator('#wizOps .op-item:has-text("乘")').click()
    page.locator('#wiz-step-3 button[onclick="wizNext(3)"]').click()
    page.wait_for_timeout(200)
    page.locator('#wizCount').fill("9")
    page.locator('#wiz-step-4 button[onclick="wizNext(4)"]').click()
    page.wait_for_timeout(200)
    page.locator('#wiz-step-5 button[onclick="wizSubmit()"]').click()
    page.wait_for_url(BASE + "/**")
    page.wait_for_timeout(1500)
    stage = _stage(page)
    expect(stage.locator('label.grade-btn:has-text("3 年级") input')).to_be_checked()
    expect(stage.locator('#count')).to_have_value("9")
    expect(stage.locator('input[name="operators"][value="乘"]')).to_be_checked()



def test_preview_omits_answer_lines_and_gap(page):
    def render(styled):
        page.goto(BASE + "/?embed=1")
        page.locator('#count').fill("2")
        if styled:
            page.locator('#advanced summary').click()
            page.locator('#answer_lines').fill("2")
            page.locator('#gap').fill("28")
        page.locator('#generateBtn').click()
        return page.locator('#preview')

    for styled in (False, True):
        preview = render(styled)
        cells = preview.locator('.cell')
        expect(cells).to_have_count(2)
        # 每个单元格只含题目文本，无输入框/答题线等额外元素
        for i in range(2):
            expect(cells.nth(i).locator('*')).to_have_count(0)
        style = preview.locator('.sheet').get_attribute("style") or ""
        assert "--preview-row-gap" not in style


def test_worksheet_practice_and_mistakes(page):
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill("做题用户")
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.goto(BASE + "/member/worksheet?grade=6&topic=arithmetic&count=3&seed=1")
    expect(page.locator('#wsSheet')).to_be_visible()
    inputs = page.locator('.ws-sheet .cell input.ans')
    cells = page.locator('.ws-sheet .cell')
    expect(inputs).to_have_count(3)
    dialogs = []
    page.once("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.locator('#wsLive').click()
    expect(page.locator('#wsLive')).not_to_be_checked()
    assert dialogs and "错误" in dialogs[0]
    inputs.nth(2).fill("99999")
    expect(inputs.nth(2)).to_be_enabled()
    page.once("dialog", lambda d: d.accept())
    page.locator('#wsLive').check()
    expect(page.locator('#wsLive')).to_be_checked()
    expect(inputs.nth(2)).to_be_disabled()
    expect(cells.nth(2)).to_have_class(re.compile(r"\b(?:bad|locked)\b"))
    inputs.nth(0).fill(inputs.nth(0).get_attribute("data-answer")[:1])
    expect(cells.nth(0)).not_to_have_class(re.compile(r"\b(?:ok|bad|locked)\b"))
    inputs.nth(0).press("Tab")
    expect(inputs.nth(0)).to_be_enabled()
    inputs.nth(0).fill(inputs.nth(0).get_attribute("data-answer"))
    expect(cells.nth(0)).to_have_class(re.compile(r"\bok\b"))
    inputs.nth(1).fill("99999")
    expect(cells.nth(1)).to_have_class(re.compile(r"\b(?:bad|locked)\b"))
    expect(inputs.nth(1)).to_be_disabled()
    page.locator('#wsReset').click()
    expect(inputs.nth(1)).to_be_enabled()
    inputs.nth(0).fill(inputs.nth(0).get_attribute("data-answer"))
    inputs.nth(1).fill("99999")
    expect(inputs.nth(1)).to_be_disabled()
    cell2_problem = cells.nth(1).get_attribute("data-problem")
    posted = []
    page.on("response", lambda r: posted.append(r)
            if r.url.endswith("/api/mistakes/manual") else None)
    page.locator('#wsSubmit').click()
    expect(page.locator('#wsResult')).to_be_visible()
    expect(page.locator('#wsResultText')).to_contain_text("正确 1/3")
    import time
    deadline = time.time() + 5
    while len(posted) < 2 and time.time() < deadline:
        page.wait_for_timeout(50)  # 等 2 个错题 POST 落库后再跳转
    page.goto(BASE + "/member/errors")
    expect(page.locator("body")).to_contain_text(cell2_problem)


def test_worksheet_steps_reveal(page):
    # 在线答题卷：每题有「解题步骤」按钮可展开；交卷后错题步骤自动显示
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill("步骤用户")
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")
    page.goto(BASE + "/member/worksheet")
    page.locator('input[name="count"]').fill("3")
    page.locator('button[data-i18n="ws.generate"]').click()
    expect(page.locator('#wsSheet')).to_be_visible()
    cells = page.locator('.ws-sheet .cell')
    expect(cells).to_have_count(3)
    expect(page.locator('.ws-steps-btn')).to_have_count(3)
    # 手动展开第一题步骤
    page.locator('.ws-steps-btn').first.click()
    first_steps = page.locator('.cell').nth(0).locator('.q-steps')
    expect(first_steps).to_be_visible()
    assert first_steps.inner_text().strip(), "步骤文本不应为空"
    # 填对一题、填错一题；交卷后错题步骤自动显示且含答案文本
    inputs = page.locator('.ws-sheet .cell input.ans')
    inputs.nth(0).fill(inputs.nth(0).get_attribute("data-answer"))
    inputs.nth(1).fill("99999")
    page.locator('#wsSubmit').click()
    bad_steps = page.locator('.cell').nth(1).locator('.q-steps')
    expect(bad_steps).to_be_visible()
    expect(bad_steps).to_contain_text("结果")


def _register(page, username):
    page.goto(BASE + "/register")
    page.locator('input[name="username"]').fill(username)
    page.locator('input[name="password"]').fill("secret123")
    page.locator('button[type="submit"]').click()
    page.wait_for_url(BASE + "/")


def test_mistakes_batch_sheet(page):
    # 批量出卷：勾选 2 张卡 + 变式 → 提交 ids 多值 + mode=variant，浏览器下载 PDF
    _register(page, "批量出卷")
    for prob, ans in (("12 + 7 = ____", "19"), ("23 + 48 = ____", "71")):
        resp = page.request.post(BASE + "/api/mistakes", form={
            "kind": "sheet", "topic": "vertical", "problem": prob, "answer": ans,
            "expression": prob.split(" = ")[0],
            "question_json": json.dumps({"topic": "vertical", "statement": prob,
                                         "answer": ans,
                                         "expression": prob.split(" = ")[0],
                                         "layout": {"kind": "vertical"}}),
            "params": '{"grade": "2", "seed": 1}', "q_index": "0"})
        assert resp.ok, resp.text
    page.goto(BASE + "/member/errors")
    boxes = page.locator('input[name="ids"]')
    expect(boxes).to_have_count(2)
    boxes.nth(0).check()
    boxes.nth(1).check()
    page.locator('#batchForm select[name="mode"]').select_option("variant")
    posted = []
    page.on("request", lambda r: posted.append(r)
            if r.url.endswith("/api/mistakes/export-batch") else None)
    with page.expect_download() as dl:
        page.locator('#batchForm button[type="submit"]').click()
    download = dl.value
    with open(download.path(), "rb") as f:
        assert f.read(4) == b"%PDF", "批量导出应返回 PDF"
    import time
    deadline = time.time() + 5
    while not posted and time.time() < deadline:
        page.wait_for_timeout(50)
    assert posted, "未收到批量导出请求"
    body = posted[0].post_data or ""
    assert body.count("ids=") == 2, f"应收到 2 个 ids：{body!r}"
    assert "mode=variant" in body, f"mode 应为 variant：{body!r}"


def test_review_single_card_queue(page):
    # 单卡队列：每次只显示一张卡，自评后推进下一张，全部完成显示横幅
    _register(page, "单卡复习")
    for prob, ans in (("5+3", "8"), ("9+2", "11")):
        resp = page.request.post(BASE + "/api/mistakes/manual",
                                 form={"topic": "arithmetic",
                                       "problem": prob, "answer": ans})
        assert resp.ok, resp.text
    page.goto(BASE + "/member/review")
    expect(page.locator(".review-card")).to_have_count(2)
    expect(page.locator(".review-card:not([hidden])")).to_have_count(1)
    expect(page.locator(".review-card:not([hidden]) .hint").first).to_have_text("第 1 张 · 共 2 张")
    page.locator("#langToggle").click()
    expect(page.locator(".review-card:not([hidden]) .hint").first).to_have_text("Card 1 of 2")
    first_problem = page.locator(".review-card:not([hidden]) .review-problem").inner_text()
    page.locator('.review-card:not([hidden]) .review-grade[data-q="5"]').click()
    expect(page.locator(".review-card:not([hidden]) .review-problem")).not_to_have_text(first_problem)
    page.locator('.review-card:not([hidden]) .review-grade[data-q="5"]').click()
    expect(page.locator("#reviewDone")).to_be_visible()
    expect(page.locator("#reviewDone")).to_contain_text("All done today!")


@pytest.mark.parametrize("viewport", [
    {"width": 375, "height": 812},
    {"width": 390, "height": 844},
    {"width": 768, "height": 1024},
    {"width": 820, "height": 1180},
    {"width": 812, "height": 375},
])
def test_mobile_workbench_has_no_horizontal_overflow(page, viewport):
    page.set_viewport_size(viewport)
    page.goto(BASE + "/")
    stage = _stage(page)
    expect(stage.locator('#generateBtn')).to_be_visible()
    _assert_no_horizontal_overflow(page.locator("html"))
    _assert_no_horizontal_overflow(stage.locator("html"))
    metrics = _embedded_scroll_metrics(page)
    assert metrics["viewport"] >= metrics["content"] - 1
    assert metrics["outerContent"] >= _stage_height(page)


def test_mobile_stage_tracks_content_and_route_changes(page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE + "/")
    stage = _stage(page)
    expect(stage.locator('#advanced')).not_to_have_attribute("open")
    initial_height = _stage_height(page)
    stage.locator('#advanced summary').click()
    expect(stage.locator('#advanced')).to_have_attribute("open", "")
    page.wait_for_function("height => document.querySelector('.workbench-stage').getBoundingClientRect().height > height", arg=initial_height)
    stage.locator('#advanced summary').click()
    expect(stage.locator('#advanced')).not_to_have_attribute("open")
    page.wait_for_function("height => document.querySelector('.workbench-stage').getBoundingClientRect().height <= height + 1", arg=initial_height)
    page.locator('#sideToggle').click()
    page.locator('.side-item:has-text("番茄钟")').click()
    expect(stage.locator('#pomodoroStart')).to_be_visible()
    page.wait_for_function("""() => {
        const doc = document.getElementById('stage').contentDocument;
        return doc.documentElement.clientHeight >= Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight) - 1;
    }""")
    metrics = _embedded_scroll_metrics(page)
    assert metrics["viewport"] >= metrics["content"] - 1
    page.set_viewport_size({"width": 812, "height": 375})
    page.wait_for_function("""() => {
        const doc = document.getElementById('stage').contentDocument;
        return doc.documentElement.clientHeight >= Math.max(doc.documentElement.scrollHeight, doc.body.scrollHeight) - 1;
    }""")


def test_mobile_drawer_keyboard_backdrop_and_switch(page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE + "/")
    page.wait_for_timeout(300)
    toggle = page.locator('#sideToggle')
    toggle.focus()
    page.keyboard.press("Enter")
    expect(page.locator('#sideRail')).to_have_class(re.compile("side-open"))
    expect(page.locator('#sideRail')).not_to_have_attribute("aria-hidden", "true")
    assert page.evaluate("document.activeElement.classList.contains('side-item')")
    page.keyboard.press("Escape")
    expect(page.locator('#sideRail')).not_to_have_class(re.compile("side-open"))
    assert page.evaluate("document.activeElement.id") == "sideToggle"
    toggle.click()
    page.locator('#sideBackdrop').click(position={"x": 300, "y": 400})
    expect(page.locator('#sideRail')).not_to_have_class(re.compile("side-open"))
    assert page.evaluate("document.activeElement.id") == "sideToggle"
    toggle.click()
    page.locator('.side-item:has-text("番茄钟")').click()
    page.wait_for_timeout(300)
    src = page.evaluate("document.getElementById('stage').src")
    assert "/member/pomodoro" in src and "embed=1" in src
    assert page.evaluate("location.hash") == "#/member/pomodoro"
    expect(page.locator('#sideRail')).not_to_have_class(re.compile("side-open"))
    assert page.evaluate("document.activeElement.id") == "stage"
    expect(page.frame_locator("#stage").locator('#pomodoroStart')).to_be_visible()


def test_mobile_preview_pager_has_no_horizontal_overflow(page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE + "/")
    stage = _stage(page)
    stage.locator('#count').fill("30")
    stage.locator('#generateBtn').click()
    expect(stage.locator('#pager')).to_be_visible()
    _assert_no_horizontal_overflow(page.locator("html"))
    _assert_no_horizontal_overflow(stage.locator("html"))
    _assert_no_horizontal_overflow(stage.locator('#pager'))


def test_drawer_state_resets_above_compact_breakpoint(page):
    page.set_viewport_size({"width": 375, "height": 812})
    page.goto(BASE + "/")
    page.locator('#sideToggle').click()
    expect(page.locator('#sideRail')).to_have_class(re.compile("side-open"))
    page.set_viewport_size({"width": 821, "height": 900})
    expect(page.locator('#sideRail')).not_to_have_attribute("inert", "")
    expect(page.locator('#sideRail')).not_to_have_attribute("aria-hidden")
    expect(page.locator('#sideRail')).not_to_have_class(re.compile("side-open"))
    expect(page.locator('#sideToggle')).to_have_attribute("aria-expanded", "false")
    expect(page.locator('.workbench-stage')).not_to_have_attribute("style", re.compile("height"))
    assert abs(_stage_height(page) - (page.viewport_size["height"] - 120)) <= 1
    expect(page.locator('#sideBackdrop')).to_be_hidden()
