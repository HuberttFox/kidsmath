"""FastAPI 网页入口：表单 → 预览 → PDF/zip 下载；中英双语 + 明暗主题。"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
import hashlib
import io
import json
import sys
import zipfile
from urllib.parse import quote, urlencode

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

import mathgen.auth as auth
from mathgen import db as db_mod
from pathlib import Path

from mathgen import __version__
from mathgen.config import Config, ConfigError, PRESETS, resolve
from mathgen.core.engine import GenerationError, generate
from mathgen.i18n import UI, LANGS, error_text, t
from mathgen.output.pdf import render_pdf
from mathgen.output.text import arrange, render_text

BASE = Path(__file__).resolve().parent
class UserAndCSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request.state.user = None
        token = request.cookies.get(auth.COOKIE_NAME)
        if token:
            try:
                request.state.user = db_mod.get_user_by_token_hash(
                    hashlib.sha256(token.encode()).hexdigest())
            except Exception:
                request.state.user = None
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            if origin:
                from urllib.parse import urlparse
                if urlparse(origin).hostname != request.url.hostname:
                    from fastapi.responses import PlainTextResponse
                    return PlainTextResponse("请求来源不合法", status_code=403)
        return await call_next(request)


app = FastAPI(title="mathgen")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
app.add_middleware(UserAndCSRFMiddleware)


def current_user(request: Request) -> dict | None:
    token = request.cookies.get(auth.COOKIE_NAME)
    if not token:
        return None
    try:
        return db_mod.get_user_by_token_hash(hashlib.sha256(token.encode()).hexdigest())
    except Exception:
        return None
templates = Jinja2Templates(directory=BASE / "templates")
templates.env.globals["t"] = t

TOPIC_OPTIONS = [
    ("arithmetic", "topic.arithmetic"),
    ("vertical", "topic.vertical"),
    ("word_problem", "topic.word_problem"),
]

_TOPIC_ICONS = {"arithmetic": "🧮", "vertical": "✍️", "word_problem": "📖"}
_TOPIC_KEYS = dict(TOPIC_OPTIONS)
_TOPIC_LABELS = dict(TOPIC_OPTIONS)
_UI_JSON = json.dumps(UI, ensure_ascii=False)
_OP_CHARS = {"加": "+", "减": "-", "乘": "×", "除": "÷"}


def _lang(request: Request) -> str:
    cookie = request.cookies.get("mathgen_lang")
    if cookie in LANGS:
        return cookie
    accept = request.headers.get("accept-language", "")
    if accept.lower().startswith("en"):
        return "en"
    return "zh"


def _grade_options(lang: str) -> list[tuple[str, str]]:
    return ([("", t("grade.custom", lang))]
            + [(str(g), t("grade.x", lang, g=g)) for g in range(1, 7)])


def _topic_options(lang: str) -> list[tuple[str, str]]:
    return [(v, t(key, lang)) for v, key in TOPIC_OPTIONS]


def _preset_summary(d: dict, lang: str) -> str:
    parts = [f"{t('f.operators', lang)} {d['operators']}"]
    if d.get("operand_ranges"):
        label = "Range" if lang == "en" else "范围"
        parts.append(f"{label} " + "、".join(f"{lo}-{hi}" for lo, hi in d["operand_ranges"]))
    for key, zh, en in (("carry", "进位", "Carry"), ("borrow", "借位", "Borrow")):
        if d.get(key) is not None:
            label = en if lang == "en" else zh
            state = ("On" if d[key] else "Off") if lang == "en" else ("开" if d[key] else "关")
            parts.append(f"{label} {state}")
    if d.get("parentheses"):
        parts.append("()" if lang == "en" else "带括号")
    if d.get("answer_lines"):
        label = "lines" if lang == "en" else "答题线"
        parts.append(f"{label} {d['answer_lines']}")
    return "；".join(parts) if lang == "zh" else "; ".join(parts)


def _preset_fields(d: dict) -> dict:
    def r(v):
        return [list(x) for x in v] if v else None

    def p(v):
        return list(v) if v else None

    return {
        "ops": d["operators"],
        "n": d.get("operand_count", 2),
        "ranges": r(d.get("operand_ranges")),
        "rr": p(d.get("result_range")),
        "carry": d.get("carry"),
        "borrow": d.get("borrow"),
        "dr": p(d.get("divisor_range")),
        "table": p(d.get("multiplication_table")),
        "gap": d.get("gap"),
        "lines": d.get("answer_lines", 0),
        "parens": bool(d.get("parentheses")),
    }


_PRESETS_JSON = json.dumps({
    "grades": {
        str(g): {"summary": _preset_summary(d, "zh"),
                 "summary_en": _preset_summary(d, "en"),
                 "fields": _preset_fields(d)}
        for g, d in PRESETS.items()},
}, ensure_ascii=False)

PLACEHOLDER_PAGES = {
    "/user": ("user.title", [
        ("🧑", "user.history", "user.history_desc", "/user/history"),
        ("⭐", "user.saved", "user.saved_desc", "/user/saved"),
    ]),
    "/user/history": ("user.history", [("📜", "user.history", "coming_soon", None)]),
    "/user/saved": ("user.saved", [("⭐", "user.saved", "coming_soon", None)]),
    "/member": ("member.title", [
        ("🤖", "member.ai", "member.ai_desc", None),
        ("⏱️", "member.timer", "member.timer_desc", "/member/timer"),
        ("🍅", "member.pomodoro", "member.pomodoro_desc", "/member/pomodoro"),
        ("❌", "member.errors", "member.errors_desc", "/member/errors"),
        ("🔁", "member.review", "member.review_desc", "/member/review"),
    ]),
    "/member/timer": ("member.timer", [("⏱️", "member.timer", "member.timer_desc", None)]),
    "/member/pomodoro": ("member.pomodoro", [("🍅", "member.pomodoro", "member.pomodoro_desc", None)]),
    "/member/errors": ("member.errors", [("❌", "member.errors", "member.errors_desc", None)]),
    "/member/review": ("member.review", [
        ("🔁", "member.review", "member.review_desc", None),
        ("📝", "member.review_gen", "coming_soon", None),
    ]),
}


def _placeholder_context(lang: str, title_key: str, cards) -> dict:
    cards_i18n = [(icon, t(t_key, lang), t(d_key, lang), link)
                  for icon, t_key, d_key, link in cards]
    return {
        "lang": lang, "ui_json": _UI_JSON, "title": t(title_key, lang),
        "title_key": title_key, "cards": cards_i18n}


@app.get("/user/history", response_class=HTMLResponse)
async def user_history(request: Request):
    lang = _lang(request)
    user = request.state.user
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    rows = db_mod.list_history(user["id"])
    items = []
    for row in rows:
        try:
            cfg = json.loads(row["config_json"])
        except Exception:
            cfg = {}
        items.append({
            "id": row["id"],
            "time": row["created_at"][:16].replace("T", " "),
            "summary": ", ".join(f"{k}={v}" for k, v in list(cfg.items())[:6]),
        })
    return templates.TemplateResponse(request, "user_history.html", {
        "lang": lang, "ui_json": _UI_JSON, "items": items,
        "app_mode": _app_mode(request)})


@app.post("/api/history/{hid}/regenerate")
async def history_regenerate(request: Request, hid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    row = db_mod.get_history(user["id"], hid)
    if not row:
        return RedirectResponse("/user/history", status_code=302)
    return _redirect_to_config(json.loads(row["config_json"]))


@app.post("/api/history/{hid}/delete")
async def history_delete(request: Request, hid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    db_mod.delete_history(user["id"], hid)
    return RedirectResponse("/user/history", status_code=302)


@app.post("/api/saved")
async def api_saved(request: Request):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    lang = _lang(request)
    form = await request.form()
    data = {k: v for k, v in form.items() if k != "name"}
    name = (form.get("name") or "").strip() or "未命名"
    try:
        cfg = _config_from_form(data)
        resolve(cfg)
    except ConfigError as e:
        return templates.TemplateResponse(request, "index.html",
            _index_context(dict(form), error_text(e.code, e.params, lang), lang, _app_mode(request)))
    db_mod.add_saved(user["id"], name, _snapshot_json(cfg))
    return RedirectResponse("/user/saved", status_code=302)


@app.post("/api/saved/{sid}/apply")
async def saved_apply(request: Request, sid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    row = db_mod.get_saved(user["id"], sid)
    if not row:
        return RedirectResponse("/user/saved", status_code=302)
    return _redirect_to_config(json.loads(row["config_json"]))


@app.post("/api/saved/{sid}/rename")
async def saved_rename(request: Request, sid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    db_mod.rename_saved(user["id"], sid, (form.get("name") or "").strip() or "未命名")
    return RedirectResponse("/user/saved", status_code=302)


@app.post("/api/saved/{sid}/delete")
async def saved_delete(request: Request, sid: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=302)
    db_mod.delete_saved(user["id"], sid)
    return RedirectResponse("/user/saved", status_code=302)


@app.post("/api/config/export")
async def config_export(request: Request):
    form = dict(await request.form())
    cfg = _config_from_form(form)
    payload = {"version": 1, "config": json.loads(_snapshot_json(cfg))}
    return Response(json.dumps(payload, ensure_ascii=False), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="kidsmath-config.json"'})


@app.post("/api/config/import", response_class=HTMLResponse)
async def config_import(request: Request):
    lang = _lang(request)
    form = await request.form()
    file = form.get("file")
    if file is None or not file.filename:
        return templates.TemplateResponse(request, "index.html",
            _index_context({}, t("config.import_format", lang), lang, _app_mode(request)))
    raw = await file.read()
    try:
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("version") != 1 or not isinstance(payload.get("config"), dict):
            raise ValueError("bad payload")
        cfg = _config_from_form(payload["config"])
        resolve(cfg)
    except (ValueError, ConfigError, UnicodeDecodeError) as e:
        msg = str(e)
        return templates.TemplateResponse(request, "index.html",
            _index_context({}, t("config.import_error", lang, err=msg), lang, _app_mode(request)))
    return _redirect_to_config({k: v for k, v in _as_query(cfg).items() if k != "seed"})


@app.get("/user/saved", response_class=HTMLResponse)
async def user_saved(request: Request):
    lang = _lang(request)
    user = request.state.user
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    rows = db_mod.list_saved(user["id"])
    items = []
    for row in rows:
        try:
            cfg = json.loads(row["config_json"])
        except Exception:
            cfg = {}
        items.append({
            "id": row["id"], "name": row["name"],
            "time": row["created_at"][:16].replace("T", " "),
            "summary": ", ".join(f"{k}={v}" for k, v in list(cfg.items())[:6]),
        })
    return templates.TemplateResponse(request, "user_saved.html", {
        "lang": lang, "ui_json": _UI_JSON, "items": items,
        "app_mode": _app_mode(request)})


@app.get("/user")
async def user_page(request: Request):
    user = request.state.user
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    lang = _lang(request)
    return templates.TemplateResponse(request, "user.html", {
        "lang": lang, "ui_json": _UI_JSON, "username": user["username"],
        "app_mode": _app_mode(request)})


TOPIC_ALIASES = {"口算": "arithmetic", "竖式": "vertical", "应用题": "word_problem"}


def _normalize_topic(raw: str | None) -> str:
    t = (raw or "").strip()
    return TOPIC_ALIASES.get(t, t)


def _mistake_card(row: dict, lang: str) -> dict:
    due = row["due_at"][:16].replace("T", " ")
    return {
        "id": row["id"], "topic": row["topic"], "problem": row["problem"],
        "answer": row["answer"], "note": row["note"],
        "wrong_at": row["wrong_at"][:16].replace("T", " "),
        "due_at": due, "mastered": bool(row["mastered_at"]),
        "has_variant": bool(row["params"]),
    }


def _render_errors(request: Request, user: dict, f: str) -> HTMLResponse:
    lang = _lang(request)
    rows = db_mod.list_mistakes(user["id"])
    if f == "due":
        rows = [r for r in rows if not r["mastered_at"]]
    elif f == "mastered":
        rows = [r for r in rows if r["mastered_at"]]
    cards = [_mistake_card(r, lang) for r in rows]
    return templates.TemplateResponse(request, "member_errors.html", {
        "lang": lang, "ui_json": _UI_JSON, "items": cards, "filter": f,
        "app_mode": _app_mode(request)})


@app.get("/member/errors", response_class=HTMLResponse)
async def member_errors(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    return _render_errors(request, user, request.query_params.get("f", "all"))


@app.post("/api/mistakes")
async def api_mistakes(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    db_mod.add_mistake(
        user["id"], "sheet", _normalize_topic(form.get("topic")),
        form.get("problem", ""), form.get("answer", ""),
        form.get("expression") or None, form.get("question_json") or None,
        form.get("params") or None,
        int(form["q_index"]) if form.get("q_index") else None,
        form.get("note") or None)
    return RedirectResponse("/member/errors", status_code=302)


@app.post("/api/mistakes/manual")
async def api_mistakes_manual(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    db_mod.add_mistake(
        user["id"], "manual", _normalize_topic(form.get("topic")),
        form.get("problem", ""), form.get("answer", ""),
        form.get("expression") or None, None, None, None,
        form.get("note") or None)
    return RedirectResponse("/member/errors", status_code=302)


@app.get("/member/review", response_class=HTMLResponse)
async def member_review(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    lang = _lang(request)
    due = db_mod.due_mistakes(user["id"], db_mod.now_iso())
    cards = []
    now = datetime.now()
    for i, row in enumerate(due, 1):
        days = 0
        try:
            due_dt = datetime.fromisoformat(row["due_at"])
            days = (due_dt - now).days
        except ValueError:
            pass
        cards.append({
            "id": row["id"], "problem": row["problem"], "answer": row["answer"],
            "days_left": days, "n": i, "total": len(due)})
    return templates.TemplateResponse(request, "member_review.html", {
        "lang": lang, "ui_json": _UI_JSON, "cards": cards,
        "app_mode": _app_mode(request)})


@app.post("/api/mistakes/{mid}/mastered")
async def mistake_mastered(request: Request, mid: int,
                           user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    row = db_mod.get_mistake(user["id"], mid)
    if row:
        db_mod.set_mastered(user["id"], mid, None if row["mastered_at"] else db_mod.now_iso())
    return RedirectResponse("/member/errors", status_code=302)


@app.post("/api/mistakes/{mid}/delete")
async def mistake_delete(request: Request, mid: int,
                         user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    db_mod.delete_mistake(user["id"], mid)
    return RedirectResponse("/member/errors", status_code=302)


@app.post("/api/mistakes/{mid}/note")
async def mistake_note(request: Request, mid: int,
                       user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    db_mod.update_note(user["id"], mid, form.get("note") or None)
    return RedirectResponse("/member/errors", status_code=302)


@app.post("/api/mistakes/{mid}/review")
async def mistake_review(request: Request, mid: int,
                         user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    try:
        q = int(form.get("q", 0))
    except ValueError:
        q = 0
    if q not in (1, 3, 5):
        q = 1
    row = db_mod.get_mistake(user["id"], mid)
    if row:
        from mathgen.sm2 import sm2_update
        ease, interval, reps = sm2_update(q, row["ease"], row["interval"], row["reps"])
        due_at = (datetime.now() + timedelta(days=interval)).isoformat(timespec="seconds")
        db_mod.update_review(user["id"], mid, ease, interval, reps, due_at, q)
    return RedirectResponse("/member/review", status_code=302)


def _mistake_question(row: dict, mode: str) -> Question | None:
    """构造题；original=question_json 直用（manual 退化文本），variant=params 重建同序号。"""
    from mathgen.core.question import Question as Q
    try:
        if mode == "original":
            if row["question_json"]:
                data = json.loads(row["question_json"])
                return Q(**{k: data[k] for k in
                            ("topic", "statement", "answer", "expression", "layout")
                            if k in data})
            return Q(row["topic"], row["problem"], row["answer"],
                     row["expression"] or row["problem"], None)
        p = json.loads(row["params"]) if row["params"] else {}
        p.pop("seed", None)
        cfg = _config_from_form(p)
        rc = resolve(cfg)
        idx = row["q_index"] or 0
        return generate(rc)[idx]
    except (json.JSONDecodeError, ConfigError, GenerationError, IndexError, TypeError):
        return None


def _export_pdf(request: Request, user: dict, rows: list[dict],
                mode: str, title: str | None) -> Response:
    from mathgen.output.pdf import render_pdf
    questions = []
    layout_cfg = None
    for row in rows:
        if mode == "variant":
            q = _mistake_question(row, "variant")
        else:
            q = _mistake_question(row, "original")
        if q is None:
            return RedirectResponse("/member/errors", status_code=302)
        questions.append(q)
        if layout_cfg is None and row["params"]:
            try:
                layout_cfg = resolve(_config_from_form(json.loads(row["params"])))
            except (json.JSONDecodeError, ConfigError):
                pass
    if layout_cfg is None:
        layout_cfg = resolve(Config())
    cfg = dataclasses.replace(layout_cfg, count=len(questions),
                              title=title or "错题练习")
    pdf = render_pdf(questions, cfg)
    filename = "worksheet.pdf"
    disp = ('attachment; filename="{filename}"; '
            "filename*=UTF-8''" + quote("错题练习.pdf"))
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": disp})


@app.post("/api/mistakes/{mid}/export")
async def mistake_export(request: Request, mid: int,
                         user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    row = db_mod.get_mistake(user["id"], mid)
    if not row:
        return RedirectResponse("/member/errors", status_code=302)
    return _export_pdf(request, user, [row], form.get("mode") or "original",
                       form.get("title") or None)


@app.post("/api/mistakes/export-batch")
async def mistakes_export_batch(request: Request,
                                user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    ids = [x for x in (form.get("ids") or "").split(",") if x]
    if not ids or len(ids) > 100:
        return RedirectResponse("/member/errors", status_code=302)
    rows = []
    for mid in ids:
        try:
            row = db_mod.get_mistake(user["id"], int(mid))
        except ValueError:
            row = None
        if not row:
            return RedirectResponse("/member/errors", status_code=302)
        rows.append(row)
    return _export_pdf(request, user, rows, form.get("mode") or "original",
                       form.get("title") or None)


@app.get("/member/timer", response_class=HTMLResponse)
async def member_timer(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(request, "member_timer.html", {
        "lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request)})


@app.get("/member/pomodoro", response_class=HTMLResponse)
async def member_pomodoro(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(request, "member_pomodoro.html", {
        "lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request)})


@app.get("/member")
async def placeholder_page(request: Request):
    lang = _lang(request)
    title_key, cards = PLACEHOLDER_PAGES[request.url.path]
    return templates.TemplateResponse(
        request, "placeholder.html", _placeholder_context(lang, title_key, cards))


def _snapshot_json(cfg: Config) -> str:
    q = {k: v for k, v in _as_query(cfg).items() if k != "seed"}
    return json.dumps(q, ensure_ascii=False)


def _redirect_to_config(snapshot: dict) -> RedirectResponse:
    return RedirectResponse("/?" + urlencode(snapshot), status_code=302)


def _app_mode(request: Request) -> bool:
    return request.query_params.get("app") == "1"


def _index_context(form: dict | None = None, error: str | None = None,
                   lang: str = "zh", app_mode: bool = False) -> dict:
    return {
        "form": form or {},
        "error": error,
        "lang": lang,
        "presets_json": _PRESETS_JSON,
        "ui_json": _UI_JSON,
        "grades": _grade_options(lang),
        "topics": _topic_options(lang),
        "topic_icons": _TOPIC_ICONS,
        "topic_keys": _TOPIC_KEYS,
        "app_mode": app_mode,
    }


def _config_from_form(form: dict) -> Config:
    def i(v, default=None):
        if v in (None, ""):
            return default
        try:
            return int(v)
        except ValueError:
            raise ConfigError(f"参数格式不正确：{v!r} 应为整数。") from None

    def rng(v):
        if v in (None, ""):
            return None
        parts = v.split("-")
        try:
            lo, hi = int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            raise ConfigError(f"参数格式不正确：{v!r} 应为“最小值-最大值”。") from None
        return (lo, hi)

    return Config(
        grade=i(form.get("grade")),
        topic=form.get("topic") or "arithmetic",
        operators=form.get("operators") or None,
        count=i(form.get("count")),
        operand_count=i(form.get("operand_count")),
        operand_ranges=([rng(s) for s in form.get("ranges", "").split(",")]
                        if form.get("ranges") else None),
        result_range=rng(form.get("result_range")),
        carry={"yes": True, "no": False}.get(form.get("carry", "")),
        borrow={"yes": True, "no": False}.get(form.get("borrow", "")),
        divisor_range=rng(form.get("divisor_range")),
        allow_remainder=bool(form.get("remainder")),
        multiplication_table=rng(form.get("table")),
        seed=i(form.get("seed")),
        columns=i(form.get("columns")),
        gap=i(form.get("gap")),
        answer_lines=i(form.get("answer_lines")),
        answer_page=form.get("answer_page") != "off",
        title=form.get("title") or None,
        header=form.get("header") or None,
        sheets=i(form.get("sheets"), 1),
        lang=form.get("lang") or None,
        parentheses=form.get("parentheses") == "1",
        paren_weight=i(form.get("paren_weight")),
        left_factor_range=rng(form.get("left_factor_range")),
        right_factor_range=rng(form.get("right_factor_range")),
        dividend_range=rng(form.get("dividend_range")),
        op_weights=_parse_op_weights(form),
        show_numbers=form.get("show_numbers") != "0",
        number_direction=form.get("number_direction") or None,
    )


def _parse_op_weights(form: dict) -> dict[str, int] | None:
    raw = form.get("op_weights")
    if raw:
        weights: dict[str, int] = {}
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            op, _, val = part.partition("=")
            try:
                weights[op.strip()] = int(val)
            except ValueError:
                raise ConfigError("weight_format", v=part) from None
        return weights or None
    from mathgen.config import normalize_operators
    selected = normalize_operators(form.get("operators") or "")
    weights = {}
    for zh, op in _OP_CHARS.items():
        v = form.get(f"w_{zh}")
        if v in (None, ""):
            continue
        if op not in selected:
            continue  # 未勾选的运算符：忽略其权重（UI 已禁用，此处防御）
        try:
            weights[op] = int(v)
        except ValueError:
            raise ConfigError("int_format", v=v) from None
    return weights or None


def _as_query(cfg: Config) -> dict:
    q: dict = {}
    if cfg.grade is not None:
        q["grade"] = str(cfg.grade)
    if cfg.topic != "arithmetic":
        q["topic"] = cfg.topic
    if cfg.operators:
        q["operators"] = cfg.operators
    if cfg.count not in (None, 20):
        q["count"] = str(cfg.count)
    if cfg.operand_count not in (None, 2):
        q["operand_count"] = str(cfg.operand_count)
    if cfg.operand_ranges:
        q["ranges"] = ",".join(f"{lo}-{hi}" for lo, hi in cfg.operand_ranges)
    if cfg.result_range:
        q["result_range"] = f"{cfg.result_range[0]}-{cfg.result_range[1]}"
    if cfg.carry is not None:
        q["carry"] = "yes" if cfg.carry else "no"
    if cfg.borrow is not None:
        q["borrow"] = "yes" if cfg.borrow else "no"
    if cfg.divisor_range:
        q["divisor_range"] = f"{cfg.divisor_range[0]}-{cfg.divisor_range[1]}"
    if cfg.allow_remainder:
        q["remainder"] = "1"
    if cfg.multiplication_table:
        q["table"] = f"{cfg.multiplication_table[0]}-{cfg.multiplication_table[1]}"
    if cfg.seed is not None:
        q["seed"] = str(cfg.seed)
    if cfg.columns not in (None, 2):
        q["columns"] = str(cfg.columns)
    if cfg.gap is not None:
        q["gap"] = str(cfg.gap)
    if cfg.answer_lines is not None:
        q["answer_lines"] = str(cfg.answer_lines)
    if not cfg.answer_page:
        q["answer_page"] = "off"
    if cfg.parentheses is not None:
        q["parentheses"] = "1" if cfg.parentheses else "0"
    if cfg.paren_weight not in (None, 5):
        q["paren_weight"] = str(cfg.paren_weight)
    if cfg.op_weights:
        q["op_weights"] = ",".join(f"{k}={v}" for k, v in cfg.op_weights.items())
    if cfg.left_factor_range:
        q["left_factor_range"] = f"{cfg.left_factor_range[0]}-{cfg.left_factor_range[1]}"
    if cfg.right_factor_range:
        q["right_factor_range"] = f"{cfg.right_factor_range[0]}-{cfg.right_factor_range[1]}"
    if cfg.dividend_range:
        q["dividend_range"] = f"{cfg.dividend_range[0]}-{cfg.dividend_range[1]}"
    if cfg.show_numbers is False:
        q["show_numbers"] = "0"
    if cfg.number_direction == "column":
        q["number_direction"] = "column"
    if cfg.title:
        q["title"] = cfg.title
    if cfg.header:
        q["header"] = cfg.header
    if cfg.sheets not in (None, 1):
        q["sheets"] = str(cfg.sheets)
    if cfg.lang == "en":
        q["lang"] = "en"
    return q


def _expires_iso():
    return (datetime.now() + timedelta(days=auth.SESSION_DAYS)).isoformat(timespec="seconds")


def _set_session_cookie(resp: RedirectResponse, request: Request, user_id: int) -> None:
    cookie, thash = auth.new_session_token()
    db_mod.create_session(thash, user_id, _expires_iso())
    resp.set_cookie(auth.COOKIE_NAME, cookie, httponly=True, samesite="lax",
                    secure=request.url.scheme == "https", max_age=60 * 60 * 24 * 30)


SAFE_NEXT_PREFIXES = ("/", "/user", "/member")


def _safe_next(path: str | None) -> str | None:
    if path and path.startswith(SAFE_NEXT_PREFIXES) and not path.startswith("//"):
        return path
    return None


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(request, "login.html",
        {"lang": lang, "ui_json": _UI_JSON, "error": None})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(request, "register.html",
        {"lang": lang, "ui_json": _UI_JSON, "error": None})


@app.post("/api/register", response_class=HTMLResponse)
async def api_register(request: Request):
    lang = _lang(request)
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    if not (2 <= len(username) <= 32):
        return templates.TemplateResponse(request, "register.html",
            {"lang": lang, "ui_json": _UI_JSON, "error": t("auth.error_username_invalid", lang)})
    if len(password) < 6:
        return templates.TemplateResponse(request, "register.html",
            {"lang": lang, "ui_json": _UI_JSON, "error": t("auth.error_password_short", lang)})
    if db_mod.get_user_by_name(username):
        return templates.TemplateResponse(request, "register.html",
            {"lang": lang, "ui_json": _UI_JSON, "error": t("auth.error_username_taken", lang)})
    uid = db_mod.create_user(username, auth.hash_password(password))
    resp = RedirectResponse(_safe_next(request.query_params.get("next")) or "/", status_code=302)
    _set_session_cookie(resp, request, uid)
    return resp


@app.post("/api/login", response_class=HTMLResponse)
async def api_login(request: Request):
    lang = _lang(request)
    form = await request.form()
    username = (form.get("username") or "").strip()
    password = form.get("password") or ""
    user = db_mod.get_user_by_name(username) if username else None
    if not user or not auth.verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(request, "login.html",
            {"lang": lang, "ui_json": _UI_JSON, "error": t("auth.error_invalid", lang)})
    db_mod.cleanup_sessions(db_mod.now_iso())
    resp = RedirectResponse(_safe_next(request.query_params.get("next")) or "/", status_code=302)
    _set_session_cookie(resp, request, user["id"])
    return resp


@app.post("/api/logout")
async def api_logout(request: Request):
    token = request.cookies.get(auth.COOKIE_NAME)
    if token:
        db_mod.delete_session(hashlib.sha256(token.encode()).hexdigest())
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(auth.COOKIE_NAME)
    return resp


@app.get("/api/me")
async def api_me(request: Request):
    user = request.state.user
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return {"username": user["username"]}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    lang = _lang(request)
    form = {k: v for k, v in request.query_params.items()}
    return templates.TemplateResponse(
        request, "index.html",
        _index_context(form, None, lang, _app_mode(request)))


@app.get("/product", response_class=HTMLResponse)
async def product_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(
        request, "product.html",
        {"lang": lang, "ui_json": _UI_JSON, "version": __version__,
         "app_mode": _app_mode(request)})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    fd = await request.form()
    form = dict(fd)
    form["operators"] = "".join(fd.getlist("operators"))
    form.setdefault("lang", _lang(request))
    lang = form["lang"] if form["lang"] in LANGS else _lang(request)
    try:
        cfg = _config_from_form(form)
    except ConfigError as e:
        return templates.TemplateResponse(
            request, "index.html",
            _index_context(form, error_text(e.code, e.params, lang), lang, _app_mode(request)))
    try:
        resolved = resolve(cfg)
    except ConfigError as e:
        return templates.TemplateResponse(
            request, "index.html",
            _index_context(form, error_text(e.code, e.params, lang), lang, _app_mode(request)))
    if cfg.seed is None:
        cfg.seed = resolved.seed
        form["seed"] = str(resolved.seed)
    try:
        questions = generate(resolved)
    except GenerationError as e:
        return templates.TemplateResponse(
            request, "index.html",
            _index_context(form, error_text(e.code, e.params, lang), lang, _app_mode(request)))
    preview = render_text(questions, resolved)
    query = "&".join(f"{k}={v}" for k, v in _as_query(cfg).items())
    grade_label = t("grade.x", lang, g=cfg.grade) if cfg.grade else t("grade.custom", lang)
    topic_label = t(_TOPIC_LABELS.get(cfg.topic, cfg.topic), lang)
    summary = t("preview.summary", lang, grade=grade_label, topic=topic_label,
                count=len(questions))
    summary_data = json.dumps({
        "grade": cfg.grade or "", "topic": cfg.topic, "count": len(questions)},
        ensure_ascii=False)
    cfg_fields = {k: v for k, v in _as_query(cfg).items() if k != "seed"}
    numbers = {id(q): i for i, q in enumerate(questions, 1)}
    cells = []
    params_snapshot = json.dumps({k: v for k, v in _as_query(cfg).items()},
                                 ensure_ascii=False)
    snaps = {}
    for idx, q in enumerate(questions):
        snaps[id(q)] = {
            "topic": q.topic, "problem": q.statement, "answer": q.answer,
            "expression": q.expression,
            "question_json": json.dumps(dataclasses.asdict(q), ensure_ascii=False),
            "params": params_snapshot, "q_index": idx,
        }
    for row in arrange(questions, resolved.columns, resolved.number_direction):
        for q in row:
            if q is not None:
                cells.append((numbers[id(q)], q, snaps[id(q)]))
    if request.state.user:
        try:
            db_mod.add_history(request.state.user["id"], _snapshot_json(cfg))
        except Exception:
            pass
    return templates.TemplateResponse(request, "preview.html", {
        "preview": preview, "query": query, "lang": lang, "ui_json": _UI_JSON,
        "app_mode": _app_mode(request),
        "sheets": resolved.sheets, "summary": summary, "summary_data": summary_data,
        "ncols": resolved.columns, "cfg_fields": cfg_fields,
        "meta_count": len(questions), "meta_sheets": resolved.sheets,
        "version": __version__,
        "show_numbers": resolved.show_numbers,
        "number_direction": resolved.number_direction,
        "cells": cells})


def _download_params(form: dict, lang: str) -> tuple[Config | None, str | None]:
    try:
        cfg = _config_from_form(form)
    except ConfigError as e:
        return None, error_text(e.code, e.params, lang)
    try:
        resolve(cfg)
    except ConfigError as e:
        return cfg, error_text(e.code, e.params, lang)
    if cfg.seed is None:
        return cfg, error_text("seed_missing", None, lang)
    return cfg, None


@app.get("/download.pdf")
async def download_pdf(request: Request):
    cfg, err = _download_params(dict(request.query_params), _lang(request))
    if err:
        return Response(err, status_code=400, media_type="text/plain; charset=utf-8")
    lang = cfg.lang if cfg and cfg.lang in LANGS else _lang(request)
    try:
        resolved = resolve(cfg)
        questions = generate(resolved)
        data = render_pdf(questions, resolved)
    except (GenerationError, ValueError) as e:
        msg = error_text(e.code, e.params, lang) if isinstance(e, (ConfigError, GenerationError)) else str(e)
        return Response(msg, status_code=400, media_type="text/plain; charset=utf-8")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=math-sheet.pdf"})


@app.get("/download.zip")
async def download_zip(request: Request):
    cfg, err = _download_params(dict(request.query_params), _lang(request))
    if err:
        return Response(err, status_code=400, media_type="text/plain; charset=utf-8")
    lang = cfg.lang if cfg and cfg.lang in LANGS else _lang(request)
    try:
        resolved = resolve(cfg)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i in range(1, resolved.sheets + 1):
                resolved.seed = (cfg.seed or 0) + i - 1
                z.writestr(f"sheet-{i:02d}.pdf", render_pdf(generate(resolved), resolved))
        data = buf.getvalue()
    except (GenerationError, ValueError) as e:
        msg = error_text(e.code, e.params, lang) if isinstance(e, (ConfigError, GenerationError)) else str(e)
        return Response(msg, status_code=400, media_type="text/plain; charset=utf-8")
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": "attachment; filename=math-sheets.zip"})


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


def main(argv: list[str] | None = None) -> int:
    import argparse
    p = argparse.ArgumentParser(prog="mathgen-serve", description="启动 mathgen 网页界面")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8080)
    ns = p.parse_args(argv)
    print(f"mathgen 网页界面：http://{ns.host}:{ns.port}")
    serve(ns.host, ns.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
