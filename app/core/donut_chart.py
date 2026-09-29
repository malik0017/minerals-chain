"""
app/core/donut_chart.py
"""

def build_donut(segments: list[tuple[str, int, str]]) -> dict:

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
