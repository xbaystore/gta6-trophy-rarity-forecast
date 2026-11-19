#!/usr/bin/env python3
"""Forecast GTA VI trophy rarity rates.

Reads every *.in case in $MAKEFUN_INPUT_DIR and writes <id>.out files
to $MAKEFUN_OUTPUT_DIR. Offline, stdlib only, deterministic.
"""

import glob
import json
import math
import os
import sys
from datetime import datetime, timezone

RELEASE = datetime(2026, 11, 19, 0, 0, 0, tzinfo=timezone.utc)
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]
TIER_FLOOR = {
    "platinum": 0.02,
    "gold": 0.05,
    "silver": 0.10,
    "bronze": 0.15,
}


def parse_time(text):
    if text is None:
        return RELEASE
    s = str(text).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def hours_since_release(dt):
    return (dt - RELEASE).total_seconds() / 3600.0


def log_time(hours):
    """ln(1 + t) that stays defined for reads slightly before release.

    The practice history contains reads a few minutes before RELEASE,
    so t can be a small negative number. Clamping t to zero would pile
    those reads onto the release instant and distort the fit; log1p
    handles -1 < t < 0 correctly, and anything at or before -1 h is
    pinned to a very small positive argument instead of crashing.
    """
    if hours <= -1.0:
        return math.log(0.001)
    return math.log1p(hours)


def clamp_rate(r):
    if r < 0.01:
        return 0.01
    if r > 99.99:
        return 99.99
    return r


def logit_of_rate(rate):
    p = clamp_rate(rate) / 100.0
    return math.log(p / (1.0 - p))


def rate_of_logit(x):
    if x >= 0:
        p = 1.0 / (1.0 + math.exp(-x))
    else:
        ex = math.exp(x)
        p = ex / (1.0 + ex)
    return p * 100.0


def median(values):
    if not values:
        return 0.0
    s = sorted(values)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return s[mid]
    return 0.5 * (s[mid - 1] + s[mid])


def build_states(history):
    """Deduplicate consecutive identical reads into states."""
    states = []
    last_key = None
    for read in history:
        n = read.get("players_tracked")
        rates = read.get("rates")
        key = (n, tuple(rates) if isinstance(rates, list) else rates)
        if states and key == last_key:
            continue
        states.append(read)
        last_key = key
    return states


def fit_logit_line(points, checkpoint_hours):
    """points: list of (t_h, rate). Returns (slope, resid_sd).

    Weights are the time gap to the next state; the last point is
    weighted by its gap to the checkpoint (at least 0.5 h).
    """
    n = len(points)
    if n < 4:
        resid = 0.25
    else:
        resid = None
    if n < 3:
        return 0.0, 0.25
    rates = [r for (_t, r) in points]
    if all(r == rates[0] for r in rates):
        if resid is None:
            resid = 0.0
        return 0.0, resid

    xs = []
    ys = []
    ws = []
    for idx, (t_h, r) in enumerate(points):
        xs.append(log_time(t_h))
        ys.append(logit_of_rate(r))
        if idx + 1 < n:
            gap = points[idx + 1][0] - t_h
            ws.append(max(gap, 0.0))
        else:
            # Spec: the last state is weighted by its gap to the
            # checkpoint, with a floor of 0.5 hours.
            gap = checkpoint_hours - t_h
            ws.append(max(gap, 0.5))

    total_w = sum(ws)
    if total_w <= 0:
        ws = [1.0] * n
        total_w = float(n)

    xbar = sum(w * x for w, x in zip(ws, xs)) / total_w
    ybar = sum(w * y for w, y in zip(ws, ys)) / total_w
    denom = sum(w * (x - xbar) ** 2 for w, x in zip(ws, xs))
    if denom <= 0:
        slope = 0.0
    else:
        numer = sum(
            w * (x - xbar) * (y - ybar) for w, x, y in zip(ws, xs, ys)
        )
        slope = numer / denom
    intercept = ybar - slope * xbar

    if resid is None:
        var = (
            sum(w * (y - (intercept + slope * x)) ** 2 for w, x, y in zip(ws, xs, ys))
            / total_w
        )
        resid = math.sqrt(max(var, 0.0))
    return slope, resid


def forecast_case(case):
    trophies = sorted(case.get("trophies", []), key=lambda t: t.get("id", 0))
    history = case.get("history", []) or []
    checkpoint = parse_time(case.get("at"))
    checkpoint_hours = hours_since_release(checkpoint)
    target_dt = parse_time(case.get("target"))
    t_target = hours_since_release(target_dt)
    horizon_minutes = case.get("horizon_minutes") or 0
    try:
        horizon_days = float(horizon_minutes) / 1440.0
    except (TypeError, ValueError):
        horizon_days = 0.0

    states = build_states(history)

    # Last raw read (not last state) drives r_last / N_last / e_last.
    if history:
        last_read = history[-1]
        t_last = hours_since_release(parse_time(last_read.get("at")))
        n_last_all = last_read.get("players_tracked") or 0
        last_rates = last_read.get("rates") or []
    else:
        t_last = checkpoint_hours
        n_last_all = 0
        last_rates = []

    all_n_same = True
    if history:
        first_n = history[0].get("players_tracked")
        for read in history:
            if read.get("players_tracked") != first_n:
                all_n_same = False
                break

    # Trophy order in `rates` follows trophy id order as given in the
    # case file; the spec says rates are per trophy in id order. The
    # trophies array itself is already in that order in practice, but
    # rates index must follow the original array order, so keep an
    # index map from the original (unsorted) list.
    original = case.get("trophies", []) or []
    index_of = {}
    for pos, tr in enumerate(original):
        index_of[tr.get("id")] = pos

    per_trophy = []
    for tr in trophies:
        tid = tr.get("id")
        pos = index_of.get(tid, 0)

        pts = []
        for st in states:
            rates = st.get("rates") or []
            if pos >= len(rates):
                continue
            r = rates[pos]
            if r is None:
                continue
            t_h = hours_since_release(parse_time(st.get("at")))
            pts.append((t_h, float(r)))

        slope_i, resid_i = fit_logit_line(pts, checkpoint_hours)

        if pos < len(last_rates) and last_rates[pos] is not None:
            r_last = float(last_rates[pos])
        else:
            # Edge case: the final read may carry null for this trophy.
            # Fall back to the most recent non-null rate in history so
            # the median is anchored to real data instead of zero.
            r_last = 0.0
            for read in reversed(history):
                rr = read.get("rates") or []
                if pos < len(rr) and rr[pos] is not None:
                    r_last = float(rr[pos])
                    break
        n_last = float(n_last_all) if n_last_all else 0.0
        e_last = (r_last / 100.0) * n_last if n_last else 0.0

        per_trophy.append(
            {
                "id": tid,
                "tier": tr.get("tier"),
                "slope": slope_i,
                "resid": resid_i,
                "r_last": r_last,
                "n_last": n_last,
                "e_last": e_last,
            }
        )

    pooled = median(
        [p["slope"] for p in per_trophy if p["e_last"] >= 20]
    )

    dx = log_time(t_target) - log_time(t_last)

    out_rows = []
    for p in per_trophy:
        r_last = p["r_last"]
        e_last = p["e_last"]
        if r_last >= 99.99:
            out_rows.append({"id": p["id"], "q": [99.5, 99.9, 99.99, 99.99, 99.99]})
            continue

        rel = e_last / (e_last + 25.0) if e_last > 0 else 0.0
        b = rel * p["slope"] + (1.0 - rel) * pooled

        delta = 0.8 * b * dx
        if delta > 2.2:
            delta = 2.2
        elif delta < -2.2:
            delta = -2.2

        if e_last < 3:
            floor = TIER_FLOOR.get(str(p["tier"]).lower(), 0.10)
            base_rate = max(r_last, floor)
        else:
            base_rate = r_last
        m = logit_of_rate(base_rate) + delta

        sd = math.sqrt(
            (0.34 * math.sqrt(max(horizon_days, 0.0))) ** 2
            + p["resid"] ** 2
            + 1.0 / max(e_last, 1.0)
        )
        if sd < 0.42:
            sd = 0.42
        elif sd > 1.5:
            sd = 1.5
        if all_n_same:
            sd = max(sd, 0.95)

        qs = []
        running = 0.01
        for z in Z:
            val = rate_of_logit(m + z * sd)
            val = clamp_rate(val)
            val = round(val, 4)
            if val < running:
                val = running
            else:
                running = val
            qs.append(val)
        out_rows.append({"id": p["id"], "q": qs})

    out_rows.sort(key=lambda row: row["id"])
    return {"trophies": out_rows}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR", "/input")
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    paths = sorted(glob.glob(os.path.join(in_dir, "*.in")))
    for path in paths:
        with open(path, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        result = forecast_case(case)
        case_id = case.get("id")
        if case_id is None:
            case_id = os.path.splitext(os.path.basename(path))[0]
        out_path = os.path.join(out_dir, "%s.out" % case_id)
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(result))
            fh.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
