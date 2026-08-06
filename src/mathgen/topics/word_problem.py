"""应用题题型占位：Task 8 实现。引擎按需导入，本模块仅保证可导入。"""
from __future__ import annotations

import random

from mathgen.config import ResolvedConfig
from mathgen.core.question import Question


def gen(cfg: ResolvedConfig, rng: random.Random) -> Question:
    raise NotImplementedError("应用题题型（word_problem）归 Task 8 实现。")
