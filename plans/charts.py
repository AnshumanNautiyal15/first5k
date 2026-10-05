"""
Server-rendered SVG bar chart geometry (pure Python). The template draws what this computes.
Single series, so no legend: the chart title names it. Marks: <=24px bars, 4px rounded
data-end, square baseline, 2px gap, hairline grid, selective labels (latest + best).
"""

from math import ceil

WIDTH = 340
HEIGHT = 180
PAD_LEFT = 28   # room for y tick labels
PAD_RIGHT = 6
PAD_TOP = 22    # room for cap labels
PAD_BOTTOM = 22  # room for x labels
MAX_BAR = 24
GAP = 2


def _ticks(max_value: float) -> tuple[int, list[int]]:
    step = 5 if max_value <= 20 else 10
    top = max(step, ceil(max_value / step) * step)
    return top, list(range(0, top + 1, step))


def _bar_path(x: float, y: float, w: float, base: float) -> str:
    h = base - y
    r = min(4, w / 2, h)
    if h <= 0:
        return ""
    return (f"M{x:.1f},{base:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}"
            f"H{x + w - r:.1f}Q{x + w:.1f},{y:.1f} {x + w:.1f},{y + r:.1f}V{base:.1f}Z")


def bar_chart(points: list[dict]) -> dict | None:
    """
    points: [{"label": str (x axis), "value": number, "tooltip": str}, ...] in order.
    Returns geometry for the template, or None if there's nothing to draw.
    """
    if not points:
        return None
    plot_w = WIDTH - PAD_LEFT - PAD_RIGHT
    plot_h = HEIGHT - PAD_TOP - PAD_BOTTOM
    base = PAD_TOP + plot_h
    top, ticks = _ticks(max(p["value"] for p in points))

    slot = plot_w / len(points)
    bar_w = max(2.0, min(MAX_BAR, slot - GAP))
    best = max(range(len(points)), key=lambda i: (points[i]["value"], i))
    last = len(points) - 1
    label_every = max(1, ceil(len(points) / 8))  # keep x labels from colliding

    bars = []
    for i, p in enumerate(points):
        slot_x = PAD_LEFT + i * slot
        x = slot_x + (slot - bar_w) / 2
        y = base - (p["value"] / top) * plot_h
        bars.append({
            "path": _bar_path(x, y, bar_w, base),
            "cx": x + bar_w / 2,
            "cap_y": y - 6,
            "hit_x": slot_x, "hit_w": slot,
            "value": p["value"],
            "tooltip": p["tooltip"],
            "x_label": p["label"] if (i % label_every == 0 or i == last) else "",
            "show_value": i in (best, last),
            "is_latest": i == last,
        })
    grid = [{"y": base - (t / top) * plot_h, "label": t} for t in ticks]
    return {
        "width": WIDTH, "height": HEIGHT, "base": base, "plot_top": PAD_TOP, "plot_h": plot_h,
        "tick_x": PAD_LEFT - 6,
        "left": PAD_LEFT, "right": WIDTH - PAD_RIGHT, "x_label_y": base + 16,
        "bars": bars, "grid": grid,
    }
