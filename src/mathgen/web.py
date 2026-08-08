"""FastAPI 网页入口：表单 → 预览 → PDF/zip 下载；中英双语 + 明暗主题。"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta
import hashlib
import io
import json
import mimetypes
import os
import sys
import zipfile
from urllib.parse import quote, urlencode
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               RedirectResponse, Response, StreamingResponse)
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
        response = await call_next(request)
        if request.query_params.get("embed") and response.status_code == 302:
            loc = response.headers.get("location", "")
            if loc and loc.startswith("/") and "embed=1" not in loc:
                sep = "&" if "?" in loc else "?"
                response.headers["location"] = f"{loc}{sep}embed=1"
        # 登录用户缺语言/主题 cookie 时，用 DB 偏好补齐（跨设备跟随）
        user = request.state.user
        if user:
            try:
                if not request.cookies.get("mathgen_lang"):
                    v = db_mod.get_setting(user["id"], "lang")
                    if v in LANGS:
                        response.set_cookie("mathgen_lang", v, path="/",
                                            max_age=60 * 60 * 24 * 365, samesite="lax")
                if not request.cookies.get("mathgen_theme"):
                    v = db_mod.get_setting(user["id"], "theme")
                    if v in ("light", "dark"):
                        response.set_cookie("mathgen_theme", v, path="/",
                                            max_age=60 * 60 * 24 * 365, samesite="lax")
            except Exception:
                pass  # 设置查询失败不影响响应
        return response


app = FastAPI(title="Kids Math", docs_url="/api/docs")
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
    # 登录用户无有效 cookie 时回退到 DB 偏好（跨设备跟随）
    user = getattr(request.state, "user", None)
    if user:
        try:
            v = db_mod.get_setting(user["id"], "lang")
            if v in LANGS:
                return v
        except Exception:
            pass
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
    "/member/timer": ("member.timer", [("🕐", "member.timer", "member.timer_desc", None)]),
    "/member/pomodoro": ("member.pomodoro", [("🍅", "member.pomodoro", "member.pomodoro_desc", None)]),
    "/member/worksheet": ("member.worksheet", [("📄", "member.worksheet", "member.worksheet_desc", None)]),
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
        return templates.TemplateResponse(request, "form.html",
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
        return templates.TemplateResponse(request, "form.html",
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
        return templates.TemplateResponse(request, "form.html",
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


@app.get("/user/history/{hid}", response_class=HTMLResponse)
async def user_history_detail(request: Request, hid: int,
                              user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    row = db_mod.get_history(user["id"], hid)
    if not row:
        return RedirectResponse("/user/history", status_code=302)
    lang = _lang(request)
    try:
        cfg = _config_from_form(json.loads(row["config_json"]))
        resolved = resolve(cfg)
        questions = generate(resolved)
    except (ValueError, ConfigError, GenerationError):
        return RedirectResponse("/user/history", status_code=302)
    params_snapshot = json.dumps({k: v for k, v in _as_query(cfg).items()},
                                 ensure_ascii=False)
    items = []
    for idx, q in enumerate(questions):
        items.append({
            "i": idx + 1, "problem": q.statement, "answer": q.answer,
            "snapshot": json.dumps({
                "topic": q.topic, "problem": q.statement, "answer": q.answer,
                "expression": q.expression,
                "question_json": json.dumps(dataclasses.asdict(q), ensure_ascii=False),
                "params": params_snapshot, "q_index": idx}, ensure_ascii=False),
        })
    return templates.TemplateResponse(request, "history_detail.html", {
        "lang": lang, "ui_json": _UI_JSON, "hid": hid, "items": items,
        "app_mode": _app_mode(request)})


@app.post("/api/history/{hid}/mistakes")
async def history_capture(request: Request, hid: int,
                          user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    row = db_mod.get_history(user["id"], hid)
    if not row:
        return RedirectResponse("/user/history", status_code=302)
    form = await request.form()
    count = 0
    for raw in form.getlist("questions"):
        try:
            d = json.loads(raw)
            db_mod.add_mistake(
                user["id"], "sheet", d.get("topic") or "arithmetic",
                d.get("problem", ""), d.get("answer", ""),
                d.get("expression") or None, d.get("question_json"),
                d.get("params"), d.get("q_index"), None)
            count += 1
        except (ValueError, TypeError):
            continue
    if count == 0:
        return RedirectResponse(f"/user/history/{hid}", status_code=302)
    return RedirectResponse("/member/errors", status_code=302)


@app.get("/user")
async def user_page(request: Request):
    user = request.state.user
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    lang = _lang(request)
    uid = user["id"]
    ms = _mistake_stats(db_mod.list_mistakes(uid))
    focus = [r for r in db_mod.list_pomodoro_sessions(uid) if r["kind"] == "focus"]
    stats = {
        "gen": len(db_mod.list_history(uid)),
        "mistakes_total": ms["total"],
        "mistakes_due": ms["due"],
        "mistakes_mastered": ms["mastered"],
        "pomodoro": len(focus),
        "pomodoro_sec": sum(r["planned_sec"] or 0 for r in focus),
        "saved": len(db_mod.list_saved(uid)),
    }
    prefs = {
        "theme": db_mod.get_setting(uid, "theme") or "",
        "lang": db_mod.get_setting(uid, "lang") or "",
    }
    pw = request.query_params.get("pw")
    pw_msg = None
    if pw == "ok":
        pw_msg = "user.password_ok"
    elif pw in ("fail", "old"):
        pw_msg = "user.password_fail"
    return templates.TemplateResponse(request, "user.html", {
        "lang": lang, "ui_json": _UI_JSON, "username": user["username"],
        "member_badge": "user.member_status", "stats": stats, "prefs": prefs,
        "pw_msg": pw_msg, "restored": request.query_params.get("restored"),
        "app_mode": _app_mode(request)})


@app.post("/api/user/password")
async def api_user_password(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    old = form.get("old") or ""
    new = form.get("new") or ""
    if not auth.verify_password(old, user["password_hash"]) or len(new) < 6:
        return RedirectResponse("/user?pw=fail", status_code=302)
    db_mod.change_password(user["id"], auth.hash_password(new))
    return RedirectResponse("/user?pw=ok", status_code=302)


@app.post("/api/user/delete")
async def api_user_delete(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    for old in db_mod.delete_user(user["id"]):
        try:
            if os.path.exists(old):
                os.unlink(old)
        except OSError:
            pass
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(auth.COOKIE_NAME)
    resp.delete_cookie("mathgen_lang")
    resp.delete_cookie("mathgen_theme")
    return resp


@app.post("/api/user/prefs")
async def api_user_prefs(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    form = await request.form()
    theme = form.get("theme") or ""
    lang = form.get("lang") or ""
    if theme in ("", "light", "dark"):
        db_mod.set_setting(user["id"], "theme", theme)
    if lang in LANGS:
        db_mod.set_setting(user["id"], "lang", lang)
    return JSONResponse({"ok": True})


# ---- 用户音频（登录后音乐歌单走服务器存储）----
AUDIO_EXT_WHITELIST = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac", ".opus"}
AUDIO_MAX_BYTES = 20 * 1024 * 1024
SETTINGS_ZIP_MAX_BYTES = 100 * 1024 * 1024


def _audio_ext(filename: str) -> str:
    ext = Path(filename or "").suffix.lower()
    return ext if ext in AUDIO_EXT_WHITELIST else ".bin"


def _audio_media_type(path: str) -> str:
    return mimetypes.guess_type(path)[0] or "application/octet-stream"


@app.post("/api/audio/upload")
async def audio_upload(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    form = await request.form()
    file = form.get("file")
    if file is None or not getattr(file, "filename", None):
        return JSONResponse({"error": "缺少文件"}, status_code=400)
    if not (file.content_type or "").startswith("audio/"):
        return JSONResponse({"error": "仅支持音频文件"}, status_code=400)
    try:
        await file.seek(0)
        raw = await file.read()
    except Exception:
        return JSONResponse({"error": "读取文件失败"}, status_code=400)
    if len(raw) > AUDIO_MAX_BYTES:
        return JSONResponse({"error": "文件超过 20MB"}, status_code=400)
    audio_dir = db_mod.user_audio_dir(user["id"])
    audio_dir.mkdir(parents=True, exist_ok=True)
    stored = audio_dir / f"{uuid4().hex}{_audio_ext(file.filename)}"
    try:
        stored.write_bytes(raw)
    except OSError:
        return JSONResponse({"error": "写入失败"}, status_code=500)
    aid = db_mod.add_audio(user["id"], file.filename, str(stored))
    return {"id": aid, "name": file.filename}


@app.get("/api/audio/list")
async def audio_list(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return [{"id": r["id"], "name": r["name"]} for r in db_mod.list_audio(user["id"])]


@app.get("/api/audio/{aid}")
async def audio_serve(request: Request, aid: int, user: dict | None = Depends(current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    row = db_mod.get_audio(user["id"], aid)
    if not row or not os.path.exists(row["path"]):
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(row["path"], media_type=_audio_media_type(row["path"]))


@app.post("/api/audio/{aid}/delete")
async def audio_delete(request: Request, aid: int, user: dict | None = Depends(current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    path = db_mod.delete_audio(user["id"], aid)
    if path and os.path.exists(path):
        try:
            os.unlink(path)
        except OSError:
            pass
    return {"ok": True}


# ---- 设置整体备份（zip 导出/导入）----
@app.get("/api/settings/export")
async def settings_export(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    data = db_mod.export_all(user["id"])
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        payload = {"version": 2, "exported_at": db_mod.now_iso(), "data": data}
        z.writestr("settings.json", json.dumps(payload, ensure_ascii=False))
        for entry in data.get("audio", []):
            path = entry.get("path")
            if not path or not os.path.exists(path):
                continue
            try:
                z.write(path, f"audio/{entry['name']}")
            except OSError:
                continue
    fname = f"kidsmath-settings-{user['id']}-{datetime.now():%Y%m%d}.zip"
    disp = f'attachment; filename="{fname}"'
    return StreamingResponse(iter([buf.getvalue()]), media_type="application/zip",
                             headers={"Content-Disposition": disp})


_NOT_NULL_COLS = {
    "config_history": ("config_json", "created_at"),
    "saved_configs": ("name", "config_json", "created_at"),
    "mistakes": ("kind", "topic", "problem", "answer", "wrong_at",
                 "ease", "interval", "reps", "due_at"),
    "pomodoro_sessions": ("kind", "planned_sec", "completed_at"),
    "user_settings": ("key", "value"),
}


def _validate_settings_data(data: dict) -> bool:
    """结构校验 settings.json 的 data：每个表键须为列表、行须含导入白名单全字段、
    NOT NULL 列不得为 None、audio 条目须为带 name 的对象。
    校验失败返回 False（调用方不得清空用户数据）。"""
    for table, cols in db_mod._IMPORT_COLS.items():
        rows = data.get(table)
        if rows is None:
            continue
        if not isinstance(rows, list):
            return False
        required = set(cols) - {"user_id"}
        not_null = set(_NOT_NULL_COLS.get(table, ()))
        for row in rows:
            if not isinstance(row, dict):
                return False
            for c in required:
                if c not in row or (c in not_null and row[c] is None):
                    return False
    audio = data.get("audio")
    if audio is not None:
        if not isinstance(audio, list):
            return False
        for entry in audio:
            if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
                return False
    return True


@app.post("/api/settings/import")
async def settings_import(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    file = form.get("file")
    if file is None or not getattr(file, "filename", None):
        return RedirectResponse("/user?restored=0", status_code=302)
    try:
        raw = await file.read()
    except Exception:
        return RedirectResponse("/user?restored=0", status_code=302)
    if len(raw) > SETTINGS_ZIP_MAX_BYTES:
        return RedirectResponse("/user?restored=0", status_code=302)
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
        info = zf.getinfo("settings.json")
        payload = json.loads(zf.read(info).decode("utf-8"))
        if payload.get("version") != 2 or not isinstance(payload.get("data"), dict):
            return RedirectResponse("/user?restored=0", status_code=302)
        data = payload["data"]
    except (KeyError, ValueError, zipfile.BadZipFile, OSError):
        return RedirectResponse("/user?restored=0", status_code=302)
    # 先完整校验（坏行在清空前拒绝），校验通过才清空并恢复
    if not _validate_settings_data(data):
        return RedirectResponse("/user?restored=0", status_code=302)
    for old in db_mod.clear_user_data(user["id"]):
        try:
            if os.path.exists(old):
                os.unlink(old)
        except OSError:
            pass
    try:
        db_mod.import_all(user["id"], data)
    except Exception:
        return RedirectResponse("/user?restored=0", status_code=302)
    # 恢复音频文件（zip 中缺失的条目跳过，不阻塞整体导入）
    audio_dir = db_mod.user_audio_dir(user["id"])
    audio_dir.mkdir(parents=True, exist_ok=True)
    for entry in data.get("audio", []) or []:
        name = entry.get("name")
        if not name:
            continue
        try:
            info = zf.getinfo(f"audio/{name}")
        except KeyError:
            continue
        try:
            raw = zf.read(info)
        except OSError:
            continue
        if len(raw) > AUDIO_MAX_BYTES:
            continue
        stored = audio_dir / f"{uuid4().hex}{_audio_ext(name)}"
        try:
            stored.write_bytes(raw)
            db_mod.add_audio(user["id"], name, str(stored))
        except OSError:
            continue
    return RedirectResponse("/user?restored=1", status_code=302)


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


def _mistake_stats(rows: list[dict]) -> dict:
    """错题聚合：待复习/已掌握计数、题型分布、运算符分布、最大位数。"""
    import re
    stats = {"total": len(rows), "due": 0, "mastered": 0}
    topics: dict[str, int] = {}
    ops: dict[str, int] = {}
    max_digits = 0
    for r in rows:
        if r["mastered_at"]:
            stats["mastered"] += 1
        else:
            stats["due"] += 1
        topics[r["topic"]] = topics.get(r["topic"], 0) + 1
        expr = r["expression"] or r["problem"]
        for ch in "+-×÷":
            if ch in expr:
                ops[ch] = ops.get(ch, 0) + 1
        for n in re.findall(r"\d+", expr):
            max_digits = max(max_digits, len(n))
    stats["topics"] = dict(sorted(topics.items(), key=lambda kv: -kv[1]))
    stats["ops"] = dict(sorted(ops.items(), key=lambda kv: -kv[1]))
    stats["max_digits"] = max_digits
    return stats


def _render_errors(request: Request, user: dict, f: str) -> HTMLResponse:
    lang = _lang(request)
    all_rows = db_mod.list_mistakes(user["id"])
    rows = all_rows
    if f == "due":
        rows = [r for r in all_rows if not r["mastered_at"]]
    elif f == "mastered":
        rows = [r for r in all_rows if r["mastered_at"]]
    cards = [_mistake_card(r, lang) for r in rows]
    return templates.TemplateResponse(request, "member_errors.html", {
        "lang": lang, "ui_json": _UI_JSON, "items": cards, "filter": f,
        "stats": _mistake_stats(all_rows), "app_mode": _app_mode(request)})


@app.get("/member/errors", response_class=HTMLResponse)
async def member_errors(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    return _render_errors(request, user, request.query_params.get("f", "all"))


def _worksheet_cells(questions) -> list[dict]:
    """把题目转成答题格：____ 处嵌入输入框；竖式块在题面下方给输入框。"""
    import html as _html
    out = []
    for i, q in enumerate(questions, 1):
        st = _html.escape(q.statement or "")
        ans = _html.escape(q.answer or "")
        if "____" in st:
            text = st.replace("____", '<input class="ans" data-answer="%s">' % ans)
        else:
            text = ('<span class="q-text">%s</span>'
                    '<input class="ans" data-answer="%s">' % (st, ans))
        out.append({"i": i, "text": text, "problem": st, "answer": q.answer or "",
                    "topic": q.topic, "layout_kind": (q.layout or {}).get("kind", ""),
                    "steps": q.steps})
    return out


@app.get("/member/worksheet", response_class=HTMLResponse)
async def member_worksheet(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse(f"/login?next={request.url.path}", status_code=302)
    lang = _lang(request)
    qp = dict(request.query_params)
    qp.setdefault("lang", lang)  # 步骤语言跟随界面语言，缺失时按请求语言
    cells = None
    try:
        cfg = _config_from_form(qp)
        resolved = resolve(cfg)
    except Exception:
        resolved = None
    ncols = resolved.columns if resolved else 2
    if resolved is not None and (qp.get("seed") or qp.get("topic") or qp.get("count")):
        # pinned-seed URL（可分享）→ 直接渲染答题卷；无 seed 先落 pin 再跳转
        if cfg.seed is None:
            cfg.seed = resolved.seed
            url = f"/member/worksheet?{urlencode(_as_query(cfg))}"
            return RedirectResponse(url, status_code=302)
        try:
            questions = generate(resolved)
        except GenerationError:
            questions = []
        cells = _worksheet_cells(questions)
    return templates.TemplateResponse(request, "member_worksheet.html", {
        "lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request),
        "cells": cells, "resolved": resolved, "ncols": ncols,
        "topic_options": TOPIC_OPTIONS})


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
    now_iso = db_mod.now_iso()
    now = datetime.now()
    due_rows = []
    all_cards = []
    for row in db_mod.list_mistakes(user["id"]):
        due = row["due_at"]
        status = "mastered" if row["mastered_at"] else ("due" if due <= now_iso else "coming")
        if status == "due":
            due_rows.append(row)
        all_cards.append({
            "id": row["id"], "problem": row["problem"], "answer": row["answer"],
            "due": due[:16].replace("T", " "), "due_date": due[:10], "status": status})
    due_rows.sort(key=lambda r: (r["due_at"], r["id"]))
    cards = []
    for i, row in enumerate(due_rows, 1):
        days = 0
        try:
            days = (datetime.fromisoformat(row["due_at"]) - now).days
        except ValueError:
            pass
        cards.append({
            "id": row["id"], "problem": row["problem"], "answer": row["answer"],
            "days_left": days, "n": i, "total": len(due_rows)})
    return templates.TemplateResponse(request, "member_review.html", {
        "lang": lang, "ui_json": _UI_JSON, "cards": cards, "all_cards": all_cards,
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
    """自评卡：q 来自 query 或表单，SM-2 更新后返回 JSON（单卡队列 JS fetch 用）。"""
    if not user:
        return RedirectResponse("/login", status_code=302)
    q_raw = request.query_params.get("q")
    if q_raw is None:
        form = await request.form()
        q_raw = form.get("q")
    try:
        q = int(q_raw or 0)
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
    return JSONResponse({"ok": True})


@app.post("/api/mistakes/{mid}/reschedule")
async def mistake_reschedule(request: Request, mid: int,
                             user: dict | None = Depends(current_user)):
    """复习卡改期：只改 due_at（日期），不动 SM-2 状态；改期视为重新排队。"""
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    date = (form.get("due") or "").strip()
    row = db_mod.get_mistake(user["id"], mid)
    valid = False
    try:
        datetime.strptime(date, "%Y-%m-%d")
        valid = True
    except (ValueError, TypeError):
        valid = False
    if row and valid:
        # 改期当天 00:00 即到期（字符串字典序比较因当天才「到期」）
        due_at = f"{date}T00:00:00"
        db_mod.update_review(user["id"], mid, row["ease"], row["interval"],
                             row["reps"], due_at, row["last_q"])
        db_mod.set_mastered(user["id"], mid, None)
    return RedirectResponse("/member/review", status_code=302)


@app.get("/api/mistakes/{mid}/preview")
async def mistake_preview(request: Request, mid: int,
                          user: dict | None = Depends(current_user)):
    """重出/变式页内预览：按 original/variant 重新生成题目并返回 JSON。"""
    if not user:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    row = db_mod.get_mistake(user["id"], mid)
    if not row:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "not found"}, status_code=404)
    q = _mistake_question(row, request.query_params.get("mode") or "original")
    if q is None:
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "unavailable"}, status_code=422)
    return {"problem": q.statement or "", "answer": q.answer or "",
            "expression": q.expression or q.statement or ""}


def _mistake_question(row: dict, mode: str) -> Question | None:
    """构造题；original=question_json 直用（manual 退化文本），variant=params 重建同序号。"""
    from mathgen.core.question import Question as Q
    try:
        if mode == "original":
            if row["question_json"]:
                data = json.loads(row["question_json"])
                return Q(**{k: data[k] for k in
                            ("topic", "statement", "answer", "expression", "layout", "steps")
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
    # 兼容两种提交：单个 "1,2" 字符串（测试/旧契约）与多个 ids= 复选框
    ids_list = form.getlist("ids")
    ids_raw = form.get("ids") if len(ids_list) == 1 else ",".join(ids_list)
    ids = [x for x in (ids_raw or "").split(",") if x]
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
    user = request.state.user
    stats = _pomodoro_stats(user["id"]) if user else None
    cal = None
    if stats is not None:
        try:
            stats["goal"] = int(db_mod.get_setting(user["id"], "pomodoro_goal") or 0)
        except ValueError:
            stats["goal"] = 0
        cal = _pomodoro_calendar(user["id"],
                                 (request.query_params.get("month") or "").strip(),
                                 (request.query_params.get("day") or "").strip())
    return templates.TemplateResponse(request, "member_pomodoro.html", {
        "lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request),
        "stats": stats, "cal": cal, "logged_in": bool(user)})


def _pomodoro_calendar(user_id: int, month_str: str, day_str: str) -> dict:
    """月度日历 + 饼图数据 + 选定日当天记录。"""
    from datetime import datetime, timedelta
    now = datetime.now()
    y, m = now.year, now.month
    if month_str and "-" in month_str:
        try:
            y, m = (int(x) for x in month_str.split("-"))
        except ValueError:
            pass
    y = max(2000, min(2100, y))
    m = max(1, min(12, m))
    days_in_month = (datetime(y, m + 1, 1) - timedelta(days=1)).day if m < 12 else 31
    first_weekday = datetime(y, m, 1).weekday()
    rows = db_mod.list_pomodoro_sessions(user_id)
    day_map: dict[int, dict] = {}
    total_focus = total_break = total_focus_sec = 0
    for r in rows:
        try:
            dt = datetime.fromisoformat(r["completed_at"])
        except ValueError:
            continue
        if dt.year != y or dt.month != m:
            continue
        d = day_map.setdefault(dt.day, {"focus": 0, "break": 0, "sec": 0})
        if r["kind"] == "focus":
            d["focus"] += 1
            total_focus += 1
            d["sec"] += r["planned_sec"] or 0
            total_focus_sec += r["planned_sec"] or 0
        else:
            d["break"] += 1
            total_break += 1
    cells = [None] * first_weekday
    for dd in range(1, days_in_month + 1):
        info = day_map.get(dd, {"focus": 0, "break": 0, "sec": 0})
        cells.append({"day": dd, "focus": info["focus"], "break": info["break"], "sec": info["sec"]})
    while len(cells) % 7 != 0:
        cells.append(None)
    weeks = [cells[i:i + 7] for i in range(0, len(cells), 7)]
    day_sessions = []
    if day_str:
        try:
            day_dt = datetime.strptime(day_str, "%Y-%m-%d")
        except ValueError:
            day_dt = None
        if day_dt and day_dt.year == y and day_dt.month == m:
            for r in rows:
                try:
                    dt = datetime.fromisoformat(r["completed_at"])
                except ValueError:
                    continue
                if dt.strftime("%Y-%m-%d") == day_str:
                    day_sessions.append({"time": dt.strftime("%H:%M"),
                                         "kind": r["kind"], "sec": r["planned_sec"] or 0})
    prev_m = f"{y}-{m - 1:02d}" if m > 1 else f"{y - 1}-12"
    next_m = f"{y}-{m + 1:02d}" if m < 12 else f"{y + 1}-1"
    return {
        "month_label": f"{y}年{m}月", "month_en": f"{y}-{m:02d}",
        "weeks": weeks, "total_focus": total_focus, "total_break": total_break,
        "total_focus_sec": total_focus_sec, "day_sessions": day_sessions,
        "selected_day": day_str, "prev_month": prev_m, "next_month": next_m,
        "today_str": now.strftime("%Y-%m-%d"),
    }


def _pomodoro_stats(user_id: int) -> dict:
    """按日期聚合专注会话：今日/本周/本月、近 14 天、连续天数。"""
    from datetime import datetime, timedelta
    rows = db_mod.list_pomodoro_sessions(user_id)
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    week_start = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    days: dict[str, int] = {}
    today_cnt = week_cnt = month_cnt = 0
    today_sec = week_sec = month_sec = 0
    for r in rows:
        if r["kind"] != "focus":
            continue
        try:
            dt = datetime.fromisoformat(r["completed_at"])
        except ValueError:
            continue
        d = dt.strftime("%Y-%m-%d")
        days[d] = days.get(d, 0) + 1
        sec = r["planned_sec"] or 0
        if d == today:
            today_cnt += 1
            today_sec += sec
        if dt >= week_start:
            week_cnt += 1
            week_sec += sec
        if dt >= month_start:
            month_cnt += 1
            month_sec += sec
    recent = []
    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        recent.append({"date": d, "count": days.get(d, 0)})
    streak = 0
    cur = today if today in days else (now - timedelta(days=1)).strftime("%Y-%m-%d")
    while days.get(cur, 0) > 0:
        streak += 1
        cur = (datetime.strptime(cur, "%Y-%m-%d") - timedelta(days=1)).strftime("%Y-%m-%d")
    return {"today": today_cnt, "week": week_cnt, "month": month_cnt,
            "today_sec": today_sec, "week_sec": week_sec, "month_sec": month_sec,
            "recent": recent, "streak": streak}


@app.post("/api/pomodoro/log")
async def pomodoro_log(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    kind = form.get("kind") or "focus"
    if kind not in ("focus", "break"):
        kind = "focus"
    try:
        sec = int(form.get("sec") or 0)
    except ValueError:
        sec = 0
    db_mod.add_pomodoro_session(user["id"], kind, max(0, sec))
    from fastapi.responses import JSONResponse
    return JSONResponse({"ok": True})


@app.post("/api/pomodoro/goal")
async def pomodoro_goal(request: Request, user: dict | None = Depends(current_user)):
    if not user:
        return RedirectResponse("/login", status_code=302)
    form = await request.form()
    try:
        g = int(form.get("goal") or 0)
    except ValueError:
        g = 0
    db_mod.set_setting(user["id"], "pomodoro_goal", str(max(0, g)))
    return RedirectResponse("/member/pomodoro", status_code=302)


def _ai_field_labels() -> list[tuple[str, str]]:
    return [("topic", "ai.field_topic"), ("operators", "ai.field_operators"),
            ("grade", "ai.field_grade"), ("count", "ai.field_count"),
            ("ranges", "ai.field_ranges"), ("parentheses", "ai.field_parentheses")]


def _ai_context(request: Request, text: str = "", fields: dict | None = None,
                notes: list[str] | None = None, recognized: int = 0,
                total: int = 0, error: str | None = None) -> HTMLResponse:
    lang = _lang(request)
    rows = []
    if fields:
        topic = fields.get("topic")
        topic_label = t(_TOPIC_LABELS.get(topic, topic), lang) if topic else None
        ranges = fields.get("result_range")
        parens = "✓" if fields.get("parentheses") else t("ai.default", lang)
        rows = [
            ("ai.field_topic", topic_label or t("ai.default", lang)),
            ("ai.field_operators", fields.get("operators") or t("ai.default", lang)),
            ("ai.field_grade", f"{fields.get('grade') or '-'} 年级"),
            ("ai.field_count", fields.get("count") or t("ai.default", lang)),
            ("ai.field_ranges", ranges or t("ai.default", lang)),
            ("ai.field_parentheses", parens),
        ]
    return templates.TemplateResponse(request, "member_ai.html", {
        "lang": lang, "ui_json": _UI_JSON, "text": text, "rows": rows,
        "fields_json": json.dumps(fields or {}, ensure_ascii=False),
        "can_backfill": bool(fields), "recognized": recognized, "total": total,
        "notes": notes or [], "error": error, "app_mode": _app_mode(request)})


@app.get("/member/ai", response_class=HTMLResponse)
async def member_ai(request: Request):
    return _ai_context(request)


@app.post("/api/ai/parse", response_class=HTMLResponse)
async def ai_parse(request: Request):
    form = await request.form()
    text = form.get("text") or ""
    from mathgen.parser import parse_examples
    res = parse_examples(text)
    return _ai_context(request, text=text, fields=res["fields"],
                       notes=res["notes"], recognized=res["recognized"],
                       total=res["total"])


@app.post("/api/ai/backfill", response_class=HTMLResponse)
async def ai_backfill(request: Request):
    form = await request.form()
    text = form.get("text") or ""
    try:
        data = json.loads(form.get("fields") or "{}")
        cfg = _config_from_form(data)
        resolve(cfg)
    except (json.JSONDecodeError, ConfigError) as e:
        return _ai_context(request, text=text, error=str(e))
    return _redirect_to_config({k: v for k, v in _as_query(cfg).items() if k != "seed"})


def _snapshot_json(cfg: Config) -> str:
    q = {k: v for k, v in _as_query(cfg).items() if k != "seed"}
    return json.dumps(q, ensure_ascii=False)


def _redirect_to_config(snapshot: dict) -> RedirectResponse:
    return RedirectResponse("/?" + urlencode(snapshot), status_code=302)


def _app_mode(request: Request) -> bool:
    return request.query_params.get("app") == "1"


_OP_ZH = {"+": "加", "-": "减", "×": "乘", "÷": "除"}


def _operators_zh(ops: str) -> str:
    """符号串（+-×÷）→ 中文串（加减乘除），供表单 checkbox 比较。"""
    return "".join(_OP_ZH.get(c, c) for c in ops)


def _index_context(form: dict | None = None, error: str | None = None,
                   lang: str = "zh", app_mode: bool = False) -> dict:
    form = dict(form or {})
    if form.get("operators"):
        form["operators"] = _operators_zh(form["operators"])
    return {
        "form": form,
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
    if request.query_params.get("embed"):
        lang = _lang(request)
        form = {k: v for k, v in request.query_params.items() if k != "embed"}
        return templates.TemplateResponse(request, "form.html",
            _index_context(form, None, lang, _app_mode(request)))
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


@app.get("/guide", response_class=HTMLResponse)
async def guide_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(
        request, "guide.html",
        {"lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request)})


@app.get("/docs", response_class=HTMLResponse)
async def docs_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(
        request, "docs.html",
        {"lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request)})


@app.get("/member", response_class=HTMLResponse)
async def member_page(request: Request):
    lang = _lang(request)
    return templates.TemplateResponse(
        request, "member.html",
        {"lang": lang, "ui_json": _UI_JSON, "app_mode": _app_mode(request)})


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
            request, "form.html",
            _index_context(form, error_text(e.code, e.params, lang), lang, _app_mode(request)))
    try:
        resolved = resolve(cfg)
    except ConfigError as e:
        return templates.TemplateResponse(
            request, "form.html",
            _index_context(form, error_text(e.code, e.params, lang), lang, _app_mode(request)))
    if cfg.seed is None:
        cfg.seed = resolved.seed
        form["seed"] = str(resolved.seed)
    try:
        questions = generate(resolved)
    except GenerationError as e:
        return templates.TemplateResponse(
            request, "form.html",
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
    for row in arrange(questions, resolved.columns, resolved.number_direction):
        for q in row:
            if q is not None:
                cells.append((numbers[id(q)], q))
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
