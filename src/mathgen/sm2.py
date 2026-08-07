"""SM-2 间隔重复算法（简化版：q∈{1,3,5} 三档）。"""
from __future__ import annotations


def sm2_update(q: int, ease: float, interval: int, reps: int) -> tuple[float, int, int]:
    if q < 3:
        return (max(1.3, ease - 0.2), 1, 0)
    reps += 1
    interval = 1 if reps == 1 else 6 if reps == 2 else round(interval * ease)
    ease += 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)
    return (ease, interval, reps)
