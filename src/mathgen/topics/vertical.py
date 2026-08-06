"""竖式题型占位：Task 7 实现。引擎按需导入，本模块仅保证可导入。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    raise NotImplementedError("竖式题型（vertical）归 Task 7 实现。")
