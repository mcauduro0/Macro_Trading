# Phase 8: Inflation & Monetary Policy Agents - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Build two fully functional analytical agents — `InflationAgent` and `MonetaryPolicyAgent` — each running real econometric models against point-in-time data and producing typed `AgentSignal` outputs. Agents plug into the existing `AgentRegistry` and `BaseAgent` framework from Phase 7. Strategy consumption and portfolio integration are downstream phases.

</domain>

<decisions>
## Implementation Decisions

### Signal thresholds & direction rules

- **INFLATION_BR_SURPRISE**: |z| > 1.0 → signal fires, |z| > 2.0 → STRONG. Upside surprise (actual > consensus) = LONG (hawkish), downside = SHORT. z-score computed against trailing 12-month rolling distribution of IPCA vs Focus median deviations.
- **INFLATION_BR_PERSISTENCE**: 0-100 composite score maps as: > 60 → LONG (sticky inflation), < 40 → SHORT (falling), 40-60 → NEUTRAL.
- **MONETARY_BR_TAYLOR gap strength bands**: Claude's discretion — calibrate based on historical BCB policy gap distribution (100bps floor specified in roadmap; strength escalation above that to be determined by researcher).
- **MONETARY_BR_SELIC_PATH direction logic**: Claude's discretion — determine signal direction convention (market-above-model vs market-below-model) based on standard rates strategy interpretation.

### Composite signal weighting

- **INFLATION_BR_COMPOSITE** weights across 4 sub-signals (Phillips Curve, BottomUp, Surprise, Persistence): Claude's discretion — pick weights that reflect model quality hierarchy (quantitative OLS models carry more weight than heuristic scores).
- **Conflict handling**: Claude's discretion — when sub-signals significantly disagree, apply a dampening mechanism to composite strength/confidence rather than letting conflicting signals fully net out.
- **MONETARY_BR_COMPOSITE** weighting across Taylor Rule gap, Selic Path deviation, Term Premium: Claude's discretion — allocate based on fundamental vs market-signal hierarchy.
- **US signals vs BR composites**: Claude's discretion — decide whether INFLATION_US_TREND and MONETARY_US_FED_STANCE remain standalone signals only or feed a spillover adjustment into BR composites.

### Model windows & estimation approach

- **Phillips Curve OLS**: 10-year rolling window (120 months). Re-fit each run using the trailing 120 months of available data.
- **Kalman Filter r\***: Full re-estimation monthly — run the complete filter on all available history each month. No separate hyperparameter vs state update cadence.
- **Insufficient data handling**: Return `NO_SIGNAL` with `confidence=0.0` and log a warning. The composite continues with remaining sub-signals and renormalizes weights accordingly. No hard failures.
- **IPCA Bottom-Up seasonal adjustment**: Claude's discretion — pick a seasonal factor approach appropriate to the 9-component IPCA breakdown (no external X-13ARIMA dependency required).

### Feature engine data series selection

- **Output gap (Phillips Curve)**: IBC-Br monthly activity index from BCB, HP-filtered to extract trend. Gap = (actual - trend) / trend.
- **Inflation expectations**: Primary model input uses 12-month-ahead IPCA Focus median. End-of-year IPCA Focus expectations added as secondary feature for cross-check signal.
- **FX passthrough**: Claude's discretion — pick the USDBRL change horizon (and transformation) that best reflects FX pass-through into Brazilian inflation based on the literature. Document the choice.
- **DI curve tenors for monetary feature engine**: 1Y, 2Y, 5Y, 10Y. These define slope (10Y–1Y), belly (2Y vs 1Y+5Y midpoint), and long-end premium features.

### Claude's Discretion

- Taylor Rule gap strength band calibration (100bps floor is locked; bands above TBD)
- MONETARY_BR_SELIC_PATH signal direction convention
- INFLATION_BR_COMPOSITE sub-signal weights
- MONETARY_BR_COMPOSITE sub-signal weights
- Conflict dampening mechanics for composites
- US-to-BR signal spillover architecture
- IPCA Bottom-Up seasonal adjustment method
- FX passthrough specification (horizon and transformation)

</decisions>

<specifics>
## Specific Ideas

- IBC-Br is the preferred output gap base — it is the most timely broad activity indicator for Brazil and is what the BCB itself monitors. HP filter is sufficient (no band-pass filter needed).
- Both 12M and end-of-year Focus expectations should be in the feature set — 12M drives the models, end-of-year is a cross-check feature that may capture market positioning differences.
- DI tenors 1Y, 2Y, 5Y, 10Y were chosen to capture front-end (policy signal), belly (risk premium), and long-end (fiscal/inflation risk premium).
- Insufficient data should gracefully return NO_SIGNAL rather than abort — the pipeline must be resilient to stale series during backtesting over historical periods.
- Phillips Curve uses 10Y rolling (not 5Y) to get stable coefficients while still capturing post-2015 Brazil macro dynamics.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 08-inflation-monetary-policy-agents*
*Context gathered: 2026-02-21*
