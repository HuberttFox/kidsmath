"""FastAPI 网页入口：表单 → 预览 → PDF/zip 下载。"""
from __future__ import annotations

import io
import json
import sys
import zipfile

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from mathgen.config import Config, ConfigError, PRESETS, TOPIC_DEFAULTS, resolve
from mathgen.core.engine import GenerationError, generate
from mathgen.output.pdf import render_pdf
from mathgen.output.text import render_text

BASE = Path(__file__).resolve().parent
app = FastAPI(title="mathgen")
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")

GRADE_OPTIONS = [("", "自定义")] + [(str(g), f"{g} 年级") for g in range(1, 7)]
TOPIC_OPTIONS = [
    ("arithmetic", "口算/四则"),
    ("vertical", "竖式"),
    ("word_problem", "应用题"),
]

TOPIC_LABELS = dict(TOPIC_OPTIONS)


def _preset_summary(d: dict) -> str:
    parts = [f"运算符 {d['operators']}"]
    if d.get("operand_ranges"):
        parts.append("范围 " + "、".join(f"{lo}-{hi}" for lo, hi in d["operand_ranges"]))
    for key, zh in (("carry", "进位"), ("borrow", "借位")):
        if d.get(key) is not None:
            parts.append(f"{zh} {'开' if d[key] else '关'}")
    if d.get("parentheses"):
        parts.append("带括号")
    if d.get("answer_lines"):
        parts.append(f"答题线 {d['answer_lines']} 行")
    return "；".join(parts)


_PRESETS_JSON = json.dumps({
    "grades": {str(g): _preset_summary(d) for g, d in PRESETS.items()},
    "topics": {
        t: f"默认题间距 {d['gap']}pt" + (f"，答题线 {d['answer_lines']} 行" if d["answer_lines"] else "")
        for t, d in TOPIC_DEFAULTS.items()},
}, ensure_ascii=False)


def _index_context(form: dict | None = None, error: str | None = None) -> dict:
    return {
        "form": form or {},
        "error": error,
        "presets_json": _PRESETS_JSON,
        "grades": GRADE_OPTIONS,
        "topics": TOPIC_OPTIONS,
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
    )


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
    if cfg.title:
        q["title"] = cfg.title
    if cfg.header:
        q["header"] = cfg.header
    if cfg.sheets not in (None, 1):
        q["sheets"] = str(cfg.sheets)
    return q


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(request, "index.html", _index_context())


@app.post("/generate", response_class=HTMLResponse)
async def generate_page(request: Request):
    fd = await request.form()
    form = dict(fd)
    form["operators"] = "".join(fd.getlist("operators"))
    try:
        cfg = _config_from_form(form)
    except ConfigError as e:
        return templates.TemplateResponse(
            request, "index.html", _index_context(form, str(e)))
    try:
        resolved = resolve(cfg)
    except ConfigError as e:
        return templates.TemplateResponse(
            request, "index.html", _index_context(form, str(e)))
    if cfg.seed is None:
        cfg.seed = resolved.seed
        form["seed"] = str(resolved.seed)
    try:
        questions = generate(resolved)
    except GenerationError as e:
        return templates.TemplateResponse(
            request, "index.html", _index_context(form, str(e)))
    preview = render_text(questions, resolved)
    query = "&".join(f"{k}={v}" for k, v in _as_query(cfg).items())
    grade_label = f"{cfg.grade} 年级" if cfg.grade else "自定义"
    topic_label = TOPIC_LABELS.get(cfg.topic, cfg.topic)
    summary = f"{grade_label} · {topic_label} · {len(questions)} 题"
    return templates.TemplateResponse(request, "preview.html", {
        "preview": preview, "query": query,
        "sheets": resolved.sheets, "summary": summary})


def _download_params(form: dict) -> tuple[Config | None, str | None]:
    try:
        cfg = _config_from_form(form)
    except ConfigError as e:
        return None, str(e)
    try:
        resolve(cfg)
    except ConfigError as e:
        return cfg, str(e)
    if cfg.seed is None:
        return cfg, "缺少 seed 参数，请先通过表单生成再下载。"
    return cfg, None


@app.get("/download.pdf")
async def download_pdf(request: Request):
    cfg, err = _download_params(dict(request.query_params))
    if err:
        return Response(err, status_code=400, media_type="text/plain; charset=utf-8")
    try:
        resolved = resolve(cfg)
        questions = generate(resolved)
        data = render_pdf(questions, resolved)
    except (GenerationError, ValueError) as e:
        return Response(str(e), status_code=400, media_type="text/plain; charset=utf-8")
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": "attachment; filename=math-sheet.pdf"})


@app.get("/download.zip")
async def download_zip(request: Request):
    cfg, err = _download_params(dict(request.query_params))
    if err:
        return Response(err, status_code=400, media_type="text/plain; charset=utf-8")
    try:
        resolved = resolve(cfg)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for i in range(1, resolved.sheets + 1):
                resolved.seed = (cfg.seed or 0) + i - 1
                z.writestr(f"sheet-{i:02d}.pdf", render_pdf(generate(resolved), resolved))
        data = buf.getvalue()
    except (GenerationError, ValueError) as e:
        return Response(str(e), status_code=400, media_type="text/plain; charset=utf-8")
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
