"""GTA VI Twitch CCU forecaster, variant G (median-focused, narrow spread).

Reads one makefun/twitch-ccu-case/v1 case per *.in file and forecasts hours
2..24 of the release day as five log-scale quantiles anchored on the hour-1
print.

Model, in prose:
  * Anchor: the hour-1 print p1. Every forecast is p1 times a ratio.
  * Median: for each hour h, the median over the case's own comparables of
    ln(viewers_h / viewers_1) on that launch's release day. Launch-day
    Twitch curves share one shape: a small dip in the small hours, then a
    strong rise as the big regions unlock (US East/West reach midnight
    local at 05:00Z/08:00Z), peaking in the evening. The median across
    ~38 past launches is robust to the few launches whose hour 1 was
    nearly empty. The median is refit from the comparables inside the
    case file at run time, so the final case (42 comparables) uses its
    own data; a baked-in copy of the fitted ratios is kept only as a
    fallback for hours with too few usable comparables.
  * Spread (variant G): deliberately narrow and tight around the median.
    The log-spread grows only slowly with the hour, s(h) = 0.18 +
    0.008 * (h - 2), and the quantiles are median * exp(z_tau * s(h))
    with z = (-1.645, -0.674, 0, 0.674, 1.645). This is a bet that the
    median is accurate, so the outer quantiles need not be wide. The
    spread stays well inside the house baseline's widening spread.

Standard library only, no network, deterministic: comparables are
processed in file order, medians are exact, and rounding is half-up
to 2 decimals.
"""

import json
import math
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.645, -0.674, 0, 0.674, 1.645]

# Log-spread of the narrow variant-G band: s(h) = SPREAD0 + SPREAD_GROWTH * (h - 2).
SPREAD0 = 0.18
SPREAD_GROWTH = 0.008

# Fallback median log-ratios ln(viewers_h / viewers_1) for hours 2..24,
# fitted once from the 38 comparables of a practice case (median across
# launches with a complete release day). Used only when a case carries
# too few usable comparables for some hour.
FALLBACK_LOG_RATIO = [
    -0.138, -0.283, -0.310, -0.292, -0.238, -0.220, -0.107, -0.126,
    -0.092, -0.075, -0.022, 0.057, 0.166, 0.418, 0.502, 0.571,
    0.668, 0.876, 0.864, 0.846, 0.832, 0.780, 0.712,
]

# A comparable counts for an hour only with a usable release-day curve.
MIN_COMPARABLES_PER_HOUR = 5


def _parse_time(text):
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def _median(values):
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2:
        return ordered[mid]
    return 0.5 * (ordered[mid - 1] + ordered[mid])


def fit_log_ratios(case):
    """Per-hour median log-ratio to hour 1, from the case's comparables.

    A comparable contributes to hour h when its release-day hourly curve
    holds a positive viewer count for both hour 1 and hour h. Hours with
    fewer than MIN_COMPARABLES_PER_HOUR contributors fall back to the
    baked-in fitted ratio for that hour.
    """
    per_hour = [[] for _ in range(23)]  # index 0 -> hour 2
    for comp in case.get("comparables") or []:
        hourly = comp.get("hourly") or []
        if not hourly:
            continue
        try:
            day_start = _parse_time(comp["day_start"])
        except (KeyError, TypeError, ValueError):
            continue
        by_hour = {}
        for row in hourly:
            try:
                at = _parse_time(row["from"])
                viewers = row["viewers"]
            except (KeyError, TypeError, ValueError):
                continue
            if not isinstance(viewers, (int, float)) or viewers <= 0:
                continue
            delta = at - day_start
            hour = int(delta.total_seconds() // 3600) + 1
            if 1 <= hour <= 24 and hour not in by_hour:
                by_hour[hour] = float(viewers)
        if 1 not in by_hour:
            continue
        first = math.log(by_hour[1])
        for hour in range(2, 25):
            if hour in by_hour:
                per_hour[hour - 2].append(math.log(by_hour[hour]) - first)
    ratios = []
    for k, values in enumerate(per_hour):
        if len(values) >= MIN_COMPARABLES_PER_HOUR:
            ratios.append(_median(values))
        else:
            ratios.append(FALLBACK_LOG_RATIO[k])
    return ratios


def round2(x):
    """Round to 2 decimals, half up, mirroring the house baseline."""
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value == int(value) else value


def forecast_case(case, name):
    if case.get("levels") != LEVELS:
        raise ValueError(f"{name} asks for levels {case.get('levels')}, not {LEVELS}")
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1.0, float(first["viewers"]))
    log_ratios = fit_log_ratios(case)
    hours = []
    for row in case["forecast"]:
        h = int(row["hour"])
        if h < 2 or h > 24:
            continue
        spread = SPREAD0 + SPREAD_GROWTH * (h - 2)
        centre = math.log(p1) + log_ratios[h - 2]
        qs = [round2(math.exp(centre + z * spread)) for z in Z]
        # Guard the ordering against rounding ties at tiny prints.
        for i in range(1, 5):
            if qs[i] < qs[i - 1]:
                qs[i] = qs[i - 1]
        qs = [max(1, min(1e9, q)) for q in qs]
        hours.append({"hour": h, "q": qs})
    hours.sort(key=lambda r: r["hour"])
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
