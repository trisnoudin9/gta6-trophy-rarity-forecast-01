"""gta6-trophy-rarity-forecast-01: earners-vs-tracked forecaster.

Method (see README.md for the full write-up):

  * Rate = earners / players_tracked.  The program models the two sides
    separately instead of extrapolating the ratio blindly: log earners and
    log players-tracked are each fitted against log time, and the rate at the
    target is the ratio of the two extrapolations.  A direct logit-rate fit
    is averaged in as a second opinion.
  * Exophase refreshes in steps: between refreshes the page is flat, at a
    refresh the tracked count jumps and most rates fall.  Consecutive
    identical reads are collapsed to one state before fitting, so long stale
    stretches do not dominate the fit, and the fit uses the most recent 24 h
    of history (falling back to all of it) because the launch-week regime
    changes fast.
  * When the history is flat (no movement at all, as on launch night) there
    is no trajectory to fit, so the forecast falls back to a type prior:
    trophies are classified from their description and tier (story chapter,
    named mission, side mission, easy activity, action, grind, completion,
    the near-100% opener), each class carrying a week-one rate prior and a
    refresh-drop factor.  For short horizons the prior expects a refresh
    dilution; for long horizons it expects the week-one absolute rate.
  * The median blends the trajectory fit with the type prior (trajectory
    dominant when the history actually moves).  The spread is honest: a
    random-walk term growing with the horizon, the fit residual, the prior
    uncertainty, and a term for trend/prior disagreement, all combined on
    the logit scale.  Class ceilings keep extrapolations from running away
    (a grind cannot reach 30% in a week; the platinum cannot reach 5%).

Deterministic, Python 3.13 standard library only, no network, no
randomness.  Reads every <id>.in in $MAKEFUN_INPUT_DIR (else /input) and
writes <id>.out to $MAKEFUN_OUTPUT_DIR (else /output).
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# The grader's -P leaves this file's directory OFF sys.path; put it back
# first so a module shipped beside this file would import.  (This entry is
# a single file; the line is kept for parity with the kit starter.)
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
Z = [-1.6448536269514722, -0.6744897501960817, 0.0, 0.6744897501960817, 1.6448536269514722]

# Exophase's page prints rates to 2 decimals; 0% and 100% have no logit.
LO, HI = 0.01, 99.99


def clamp_pct(x: float) -> float:
    return min(HI, max(LO, x))


def logit(pct: float) -> float:
    p = clamp_pct(pct)
    return math.log(p / (100.0 - p))


def sigmoid(lg: float) -> float:
    if lg >= 0:
        return 100.0 / (1.0 + math.exp(-lg))
    e = math.exp(lg)
    return 100.0 * e / (1.0 + e)


def round4(x: float):
    """Round to 4 decimals, half up, as JavaScript Math.round does it."""
    scaled = x * 10000
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 10000
    return int(value) if value == int(value) else value


def parse_time(s):
    """ISO 8601 -> epoch seconds (UTC).  Returns None on failure."""
    if not s:
        return None
    try:
        dt = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


# ---------------------------------------------------------------------------
# Trophy classification: (week-one prior %, refresh-drop multiplier if a
# refresh lands, prior spread in logit units, ceiling %).
#
# Priors are calibrated on the launch-night page (638 tracked, most rates
# 0.6-2%) and the live page ~14 h later (~13k tracked: Chapter 1 at 0.73%,
# the fishing challenge already 1.89%, most grinds still at ~4 earners):
# early dilution crushes rates while the tracked count explodes, then
# progression lifts story trophies over the week while grinds stay rare.
# ---------------------------------------------------------------------------

def classify(trophy):
    text = ((trophy.get("name") or "") + " " + (trophy.get("description") or "")).lower()
    tier = (trophy.get("tier") or "").lower()

    def cls(prior, drop, sig, ceil):
        return (prior, drop, sig, ceil)

    if tier == "platinum" or "100% completion" in text:
        return cls(0.05, 0.25, 0.90, 0.5)
    if "gone fishing" in text:
        return cls(99.97, 1.0, 1.0, 99.99)
    if "chapter 1" in text:
        return cls(40.0, 0.30, 0.55, 75.0)
    if "chapter 2" in text:
        return cls(25.0, 0.30, 0.55, 65.0)
    if "chapter 3" in text:
        return cls(18.0, 0.30, 0.60, 60.0)
    if "chapter 4" in text:
        return cls(15.0, 0.30, 0.60, 60.0)
    if "final mission for" in text:
        return cls(5.0, 0.30, 0.80, 25.0)
    if "complete the final mission" in text:
        return cls(12.0, 0.30, 0.65, 55.0)
    if "8 mission strands" in text:
        return cls(1.2, 0.25, 0.90, 6.0)
    for key, prior in (("breakfast run", 16.0), ("cartel heist", 10.0),
                       ("child's play", 12.0), ("headliners", 10.0),
                       ("vcia takedown", 10.0), ("operation savage glory", 8.0)):
        if key in text:
            return cls(prior, 0.30, 0.65, 50.0)
    for key, prior in (("250 stunts", 0.4), ("100 locations", 0.4),
                       ("50 challenges", 0.6), ("collectible card sets", 0.5),
                       ("gold medal in all", 0.6), ("20 different races", 1.5),
                       ("meditate at every spot", 0.5),
                       ("top fun drone race at every location", 0.5)):
        if key in text:
            return cls(prior, 0.20, 0.90, 6.0)
    if "try each type of activity" in text:
        return cls(3.0, 0.50, 0.80, 15.0)
    for key, prior in (("fishing challenge", 14.0), ("arcade game", 7.0),
                       ("discover 100 vehicles", 8.0), ("explore all of leonida", 2.0),
                       ("cocktail", 4.0), ("bowling alley", 5.0),
                       ("spend $100,000", 3.0), ("purchase all garage", 2.0),
                       ("register 10 vehicles", 2.0), ("laundering marked bills", 2.0)):
        if key in text:
            return cls(prior, 0.55, 0.75, 40.0)
    for key, prior in (("wanted level", 5.0), ("rob 3 shops", 3.0),
                       ("combat focus", 4.0), ("unscheduled departure", 6.0),
                       ("rhinos", 6.0), ("jewelry store", 3.0),
                       ("bank vaults", 2.0), ("armored truck", 3.0),
                       ("illegal operation", 2.0), ("melee drive-by", 4.0),
                       ("vehicle showroom", 3.0), ("hunt a unique animal", 2.0)):
        if key in text:
            return cls(prior, 0.45, 0.80, 30.0)
    for key, prior in (("partnership with mass appeal", 3.0),
                       ("choices made", 4.0), ("second time's the charm", 3.0),
                       ("what the hell just happened", 5.0)):
        if key in text:
            return cls(prior, 0.35, 0.80, 25.0)
    # Fallback by tier for anything unrecognised.
    if tier == "gold":
        return cls(8.0, 0.30, 0.90, 40.0)
    if tier == "silver":
        return cls(1.5, 0.25, 0.90, 15.0)
    return cls(3.0, 0.35, 0.90, 30.0)


# ---------------------------------------------------------------------------
# Small numeric helpers
# ---------------------------------------------------------------------------

def ols(xs, ys):
    """Least squares y = a + b*x.  Returns (a, b, resid_sd) or None."""
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 1e-12:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    b = sxy / sxx
    a = my - b * mx
    if n > 2:
        ss = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
        sd = math.sqrt(ss / (n - 2))
    else:
        sd = 0.0
    return (a, b, sd)


def norm_ppf(p):
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


# ---------------------------------------------------------------------------
# The forecaster
# ---------------------------------------------------------------------------

def forecast_case(case, name):
    trophies = case["trophies"]
    history = case.get("history") or []
    horizon_min = float(case.get("horizon_minutes") or 0)
    horizon_h = horizon_min / 60.0
    horizon_d = horizon_min / 1440.0
    levels = case.get("levels") or LEVELS
    zs = [Z[i] if abs(lv - LEVELS[i]) < 1e-9 else norm_ppf(lv)
          for i, lv in enumerate(levels)] if len(levels) == len(Z) and \
        all(abs(lv - LEVELS[i]) < 1e-9 for i, lv in enumerate(levels)) else \
        [norm_ppf(lv) for lv in levels]

    # Time origin: the game's release date at 00:00 UTC when known, else the
    # first read.  x is hours since the origin; u = ln(1 + x) is the
    # regressor (growth is fast early, slow late).
    origin = None
    game = case.get("game") or {}
    if game.get("release_date"):
        origin = parse_time(str(game["release_date"]) + "T00:00:00Z")
    read_times = [parse_time(h.get("at")) for h in history]
    if origin is None and read_times:
        origin = min(t for t in read_times if t is not None)
    if origin is None:
        origin = parse_time(case.get("at")) or 0.0
    checkpoint = parse_time(case.get("at"))
    x_now = (checkpoint - origin) / 3600.0 if checkpoint is not None else 0.0
    if x_now < 0:
        x_now = 0.0
    x_target = x_now + horizon_h

    # Collapse consecutive identical reads to one state (Exophase sits flat
    # between refreshes).  A state keeps its first time, tracked count and
    # rates; trophies_earned is ignored (it is a page total, not per trophy).
    states = []  # (x_hours, tracked, rates tuple)
    prev_key = None
    for h, t in zip(history, read_times):
        if t is None:
            continue
        rates = h.get("rates") or []
        key = (h.get("players_tracked"), tuple(rates))
        if key == prev_key:
            continue
        prev_key = key
        states.append(((t - origin) / 3600.0, h.get("players_tracked"), tuple(rates)))
    if not states:
        # No usable history at all: fall back to the type priors alone.
        states = [(x_now, None, tuple(None for _ in trophies))]

    x_last_state = states[-1][0]
    # Staleness: hours the page has shown its current values.
    stale_h = max(0.0, x_now - x_last_state)
    # Chance at least one Exophase refresh lands inside the horizon.  The
    # first refresh took ~4.5 h to arrive after a 3+ h stale page, so the
    # cadence prior is ~4.5 h, and a stale page is more likely to refresh.
    p_refresh = 1.0 - math.exp(-(horizon_h + 0.5 * stale_h) / 4.5)
    p_refresh = min(0.95, max(0.0, p_refresh))

    # Tracked-count trajectory (log scale) over the recent window, for the
    # earners/track split.  Uses states with a positive tracked count.
    recent = [s for s in states if s[0] >= x_now - 24.0] or states
    if len(recent) < 3:
        recent = states
    t_fit = None
    t_pts = [(math.log1p(max(0.0, s[0])), math.log(s[1]))
             for s in recent if s[1] and s[1] > 0]
    if len(t_pts) >= 3 and len({round(x, 6) for x, _ in t_pts}) >= 2:
        t_fit = ols([p[0] for p in t_pts], [p[1] for p in t_pts])
    u_target = math.log1p(max(0.0, x_target))
    u_last = math.log1p(max(0.0, x_last_state))
    du = u_target - u_last

    rows = []
    for i, trophy in enumerate(trophies):
        prior_pct, drop, sig_prior, ceil_pct = classify(trophy)
        # Last observed rate for this trophy (walk back over nulls).
        last_rate = None
        for s in reversed(states):
            if i < len(s[2]) and s[2][i] is not None:
                last_rate = float(s[2][i])
                break
        if last_rate is None:
            last_rate = prior_pct

        # --- type prior at this horizon --------------------------------
        # Short horizon: a refresh dilutes the rate (tracked jumps faster
        # than earners).  Long horizon: the week-one absolute rate.  The
        # blend follows the TARGET's age since launch, not the horizon
        # length: rates only start climbing toward their week-one levels
        # once the player base is a day or more old (at ~14 h after launch
        # the live page still showed every rate below launch night, because
        # dilution was still winning).  Blend in log space.
        short_med = last_rate * (drop ** p_refresh)
        age_target_h = x_target
        if age_target_h <= 24.0:
            w_long = 0.0
        else:
            w_long = (age_target_h - 24.0) / (age_target_h - 24.0 + 72.0)
        if prior_pct >= 99.0:
            # The near-100% opener stays near 100%; only its downside grows.
            prior_logit = logit(max(99.9, min(99.99, last_rate if last_rate > 99 else 99.97)))
            prior_med = sigmoid(prior_logit)
        else:
            prior_logit = (1.0 - w_long) * logit(short_med) + w_long * logit(prior_pct)
            prior_med = sigmoid(prior_logit)

        # --- trajectory fit --------------------------------------------
        trend_logit = None
        fit_sd = 0.0
        pts = [(math.log1p(max(0.0, s[0])), float(s[2][i]))
               for s in recent
               if i < len(s[2]) and s[2][i] is not None]
        distinct_rates = len({round(r, 6) for _, r in pts})
        distinct_x = len({round(x, 6) for x, _ in pts})
        if len(pts) >= 3 and distinct_rates >= 2 and distinct_x >= 2:
            fit = ols([p[0] for p in pts], [logit(p[1]) for p in pts])
            if fit is not None:
                a, b, sd = fit
                fit_sd = sd
                # Damped extrapolation of the direct logit fit.
                damp = 1.0 / (1.0 + 0.15 * horizon_d)
                direct = logit(last_rate) + b * du * damp
                trend_logit = direct
                # Earners / tracked split: extrapolate log earners and log
                # tracked separately, earners damped harder (a cohort
                # finishes a trophy; the tracked base keeps growing).
                if t_fit is not None:
                    e_pts = []
                    for (u, r), s in zip(pts, [s for s in recent
                                               if i < len(s[2]) and s[2][i] is not None]):
                        if s[1] and s[1] > 0:
                            earners = max(0.5, r / 100.0 * s[1])
                            e_pts.append((u, math.log(earners)))
                    if len(e_pts) >= 3 and len({round(x, 6) for x, _ in e_pts}) >= 2:
                        e_fit = ols([p[0] for p in e_pts], [p[1] for p in e_pts])
                        if e_fit is not None:
                            ea, eb, _ = e_fit
                            ta, tb, _ = t_fit
                            damp_e = 1.0 / (1.0 + 0.35 * horizon_d)
                            damp_t = 1.0 / (1.0 + 0.10 * horizon_d)
                            ln_e = math.log(max(0.5, last_rate / 100.0 *
                                                (states[-1][1] or 1))) + eb * du * damp_e
                            ln_t = math.log(states[-1][1] or 1) + tb * du * damp_t
                            # Earners cannot exceed tracked; keep at least
                            # the earners already seen.
                            ln_e = min(ln_e, ln_t)
                            rate_et = 100.0 * math.exp(ln_e - ln_t)
                            trend_logit = 0.5 * direct + 0.5 * logit(rate_et)

        # --- combine ----------------------------------------------------
        if trend_logit is not None:
            # The trajectory earns more weight the longer the horizon and
            # the more the history actually moved; the prior is the anchor
            # when the history is flat or the fit is noisy.
            w_trend = 0.55 if horizon_d >= 0.5 else 0.35
            med_logit = w_trend * trend_logit + (1.0 - w_trend) * prior_logit
            disagree = abs(trend_logit - prior_logit)
        else:
            med_logit = prior_logit
            disagree = 0.0

        # Class ceiling (and a floor at the print floor) on the median.
        med_pct = sigmoid(med_logit)
        med_pct = min(med_pct, ceil_pct)
        med_pct = clamp_pct(med_pct)
        med_logit = logit(med_pct)

        # --- spread (logit units) ---------------------------------------
        sig_rw = 0.5 * math.sqrt(max(0.0, horizon_d))
        sig_fit = min(0.8, fit_sd * (1.0 + 0.5 * max(0.0, du)))
        sig_dis = 0.35 * disagree
        sig_flat = 0.4 if trend_logit is None else 0.0
        sigma = math.sqrt(sig_rw ** 2 + sig_fit ** 2 + sig_prior ** 2 +
                          sig_dis ** 2 + sig_flat ** 2)
        sigma = min(2.2, max(0.35, sigma))

        qs = []
        prev = None
        for z in zs:
            q = clamp_pct(sigmoid(med_logit + z * sigma))
            q = round4(q)
            if prev is not None and q < prev:
                q = prev
            qs.append(q)
            prev = q
        rows.append({"id": trophy["id"], "q": qs})

    return {"trophies": rows}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        out = json.dumps(forecast, separators=(",", ":")) + "\n"
        if len(out.encode("utf-8")) > 65536:
            raise ValueError(f"{path.name}: forecast over 65,536 bytes")
        (OUTPUT_DIR / f"{path.stem}.out").write_text(out, encoding="utf-8")


if __name__ == "__main__":
    main()
