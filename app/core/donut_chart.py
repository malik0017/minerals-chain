"""
app/core/donut_chart.py

Batch E: dashboards need a simple status-breakdown visualization
(e.g. "3 draft, 5 verified, 1 failed"). This project has stayed
dependency-light throughout (see core/localization.py's docstring for
the same reasoning applied to translations) — Chart.js isn't bundled
in this project, and pulling it in from a CDN for what's fundamentally
a handful of colored arcs is more dependency than the need justifies.

CSS conic-gradient() (broadly supported in every modern browser) draws
the same donut with zero JavaScript and zero extra requests — this
module just computes the gradient's color-stop string and the
percentages for an accompanying legend.
"""


def build_donut(segments: list[tuple[str, int, str]]) -> dict:
    """
    segments: list of (label, count, css_color) tuples.
    Returns {"gradient": "<css conic-gradient() stops>", "legend": [...], "total": int}.
    Segments with a zero count are dropped from both the gradient and
    the legend — nothing to show for them. If everything is zero,
    gradient is a flat neutral ring instead of an empty/invalid one.
    """
    total = sum(count for _, count, _ in segments)
    legend = []
    if total == 0:
        return {"gradient": "#e9ecef 0% 100%", "legend": [], "total": 0}

    stops = []
    cursor = 0.0
    for label, count, color in segments:
        if count <= 0:
            continue
        pct = (count / total) * 100
        start = cursor
        end = cursor + pct
        stops.append(f"{color} {start:.2f}% {end:.2f}%")
        legend.append({"label": label, "count": count, "color": color, "pct": round(pct)})
        cursor = end

    return {"gradient": ", ".join(stops), "legend": legend, "total": total}
