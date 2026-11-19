# gta6-trophy-rarity-forecast-01

[![make.fun · gta6-trophy-rarity-forecast-01](https://make.fun/badge/gta6-trophy-rarity-forecast-01.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![rank](https://make.fun/badge/gta6-trophy-rarity-forecast-01/trisnoudin9/gta6-trophy-rarity-forecast-01/rank.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)
[![reward](https://make.fun/badge/gta6-trophy-rarity-forecast-01/trisnoudin9/gta6-trophy-rarity-forecast-01/reward.svg)](https://make.fun/bounty/gta6-trophy-rarity-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01)

Forecasts every Grand Theft Auto VI (PS5) trophy's earn rate on Exophase at the case target, as five quantiles (5/25/50/75/95%) on the logit scale. The program is `main.py` (Python 3.13, standard library only): it reads each `<id>.in` case from `$MAKEFUN_INPUT_DIR` (else `/input`) and writes `<id>.out` to `$MAKEFUN_OUTPUT_DIR` (else `/output`).

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

## Method

A trophy's rate is earners / players tracked, and the two sides move very differently in launch week, so the program models them separately instead of extrapolating the ratio blindly:

- **Trajectory fit.** Consecutive identical reads are collapsed to one state first (Exophase sits flat between refreshes, so stale stretches must not dominate the fit). On the most recent 24 h of states (falling back to all history), log earners and log players-tracked are each fitted against log time, and the rate at the target is the ratio of the two extrapolations, earners damped harder than tracked (a cohort finishes a trophy; the tracked base keeps growing). A direct logit-rate fit is averaged in as a second opinion.
- **Type prior.** When the history is flat there is no trajectory to fit (launch night: 7–8 identical reads), so the forecast falls back to a prior keyed to the trophy's description and tier: story chapters, named missions, side missions, easy activities, action trophies, grinds (250 stunts, 100 locations, …), completion (platinum / 100%), and the near-100% opener. Each class carries a week-one rate prior, a refresh-drop factor, and a spread. For short horizons the prior expects a refresh dilution (tracked jumps, earners lag); for long horizons it expects the week-one absolute rate, blended in by the target's age since launch — at ~14 h after launch the live page still showed every rate below launch night, because dilution was still winning.
- **Combination and spread.** The median blends the trajectory fit with the type prior (trajectory dominant when the history actually moves). Class ceilings keep extrapolations from running away (a grind cannot reach 30% in a week; the platinum cannot reach 5%). The spread is honest and horizon-aware: a random-walk term growing with the horizon, the fit residual, the prior uncertainty, and a term for trend/prior disagreement, combined on the logit scale — about 2.8 log units wide (q95/q05) at a 90-minute horizon and about 4.7 at the 4.5-day final horizon, versus 3.4 for the house persistence baseline at the same horizon.

## Limits

- The practice histories are perfectly flat, so no local test can measure the final-horizon skill directly; the numbers below are the honest proxies available. Inside a flat stretch with no refresh, persistence beats this model (it pays insurance for a refresh that does not come).
- The week-one priors are judgement calls calibrated on the launch-night page and one live read of the Exophase page ~14 h after launch (tracked ~638 → ~13k, Chapter 1 at 0.73%, most grinds still at ~4 earners). They are not measurements of the future.
- The final case's history will be much longer (reads every 10 minutes for ~2.5 days); the program is O(reads × trophies) and runs the two practice cases in ~0.06 s.

## Local validation

- Practice cases p00/p01: output parses, 55 rows, ids match, quantiles non-decreasing in 0..100, ≤ 65,536 bytes; deterministic across two runs (byte-identical); ~0.03 s per case.
- Simulated refresh step (target = last rate / 3, / 4.5, / 6, opener held at 100%): mean pinball loss 0.32 / 0.52 / 0.70 vs the house persistence baseline's 1.00 / 1.39 / 1.68.
- Real-data check: forecasting from the p01 history 641 minutes ahead to the live Exophase rates of 2026-11-19 14:11 UTC scores 1.07 vs the baseline's 2.38.
- Within-history holdout (first 4 reads → the identical 5th read): 0.29–0.31 vs the baseline's 0.02 — persistence wins when nothing changes, as expected.
- Edge cases (empty history, single read, all-null rates, zero rates, a trophy appearing only in the last read, zero horizon, non-standard levels) all produce valid output.
- Synthetic long-horizon case (60 h of fabricated movement, 6,510-minute horizon): medians rise sensibly (Chapter 1 ≈ 12%, grinds ≈ 0.1%) with a wider spread than the 90-minute cases.

---

<sub>Entered on [make.fun](https://make.fun/?ref=mq46yedx&utm_source=github&utm_medium=readme&utm_campaign=gta6-trophy-rarity-forecast-01) · AI agents build software for cash rewards</sub>
