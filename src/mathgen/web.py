"""FastAPI 网页入口：表单 → 预览 → PDF/zip 下载；中英双语 + 明暗主题。"""
from __future__ import annotations

import io
import json
import sys
import zipfile

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from mathgen import __version__
from mathgen.config import Config, ConfigError, PRESETS, resolve
from mathgen.core.engine import GenerationError, generate
from mathgen.i18n import UI, LANGS, error_text, t
from mathgen.output.pdf import render_pdf
from mathgen.output.text import arrange, render_text

BASE = Path(__file__).resolve().parent
app = FastAPI(title="mathgen")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
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


def _index_context(form: dict | None = None, error: str | None = None,
                   lang: str = "zh") -> dict:
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
    if cfg.op_weights:
        q["op_weights"] = ",".join(f"{k}={v}" for k, v in cfg.op_weights.items())
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    lang = _lang(request)
    form = {k: v for k, v in request.query_params.items()}
    return templates.TemplateResponse(
        request, "index.html", _index_context(form, None, lang))


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
            request, "index.html", _index_context(form, error_text(e.code, e.params, lang), lang))
    try:
        resolved = resolve(cfg)
    except ConfigError as e:
        return templates.TemplateResponse(
            request, "index.html", _index_context(form, error_text(e.code, e.params, lang), lang))
    if cfg.seed is None:
        cfg.seed = resolved.seed
        form["seed"] = str(resolved.seed)
    try:
        questions = generate(resolved)
    except GenerationError as e:
        return templates.TemplateResponse(
            request, "index.html", _index_context(form, error_text(e.code, e.params, lang), lang))
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
    return templates.TemplateResponse(request, "preview.html", {
        "preview": preview, "query": query, "lang": lang, "ui_json": _UI_JSON,
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
