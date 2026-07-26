# Point-in-Time Backtest Audit Summary

**Starting Capital:** $1,000,000  
**Ending Capital:** $23,287,320  
**Period:** January 1, 2025 → July 1, 2026  
**Duration:** 18 months

---

## 🔴 CRITICAL FINDINGS

### 1. MAJOR RED FLAG: Negative Payout in T10 of VIC1-NSW1

**First trade executed (2025-01-01):**
- Product: C2021Q4:VIC1-NSW1:NSW1:T10
- Units: 114
- Cost/unit: $465.88
- Bid Cost: $54,226
- **Payout/unit: -$2,789.08** ← ⚠️ NEGATIVE PAYOUT
- Payout received: -$317,955
- **Alpha: -$372,181 LOSS**

**This is a catastrophic loss on the first trade.** A negative payout means we were forced to PAY an additional liability, not receive a benefit.

This suggests a major issue:

1. **Look-ahead bias check**: The model predicted this was positive at decision time (fair value: $2,002), but the realized payout was deeply negative. This could indicate:
   - The data contains settled payouts that weren't known at decision time
   - OR the negative payout represents a settlement obligation, not a market return

2. **Capacity interpretation**: Negative payouts suggest this is a capacity constraint—a cost of using too much transmission capacity. If so, the model should be avoiding these, not bidding aggressively.

### 2. CORRIDOR ANALYSIS REVEALS LOSS CONCENTRATION (CAUSE NOT YET ISOLATED)

**Profit by Corridor:**
| Corridor | Profit | Trades | Hit Rate | Avg Trade | Status |
|----------|--------|--------|----------|-----------|--------|
| NSW1-QLD1 | **+$58.3M** | 393 | **60.8%** | +$148k | ✅ STRONG |
| V-SA | **+$17.0M** | 208 | **67.8%** | +$82k | ✅ STRONG |
| VIC1-NSW1 | **-$53.0M** | 325 | **34.5%** | -$163k | ⚠️ ATTRIBUTION REQUIRED |

**One corridor (VIC1-NSW1) accounts for -$53M against +$75M from other corridors.**

This is a concentration signal, not a root-cause diagnosis.

At this stage, we cannot conclude VIC1-NSW1 is inherently unprofitable. Plausible deterministic causes still to isolate:
- RuleSet interpretation
- Unit category/table mapping
- Settlement reconstruction methodology
- Forecast stack error (price/flow/constraint)
- Optimizer/execution behavior

### 3. QUARTER-BY-QUARTER REVEALS LOSS CLUSTERING (NOT YET PROVEN SEASONAL)

Several quarters show 0% hit rate with massive losses:

| Quarter | Profit | Trades | Hit Rate | Status |
|---------|--------|--------|----------|--------|
| C2020Q2 | -$728k | 81 | **0.0%** | All losses |
| C2021Q4 | -$8.1M | 32 | **6.2%** | Nearly all losses |
| C2022Q4 | -$7.3M | 53 | **34.0%** | Mostly losses |
| C2023Q4 | -$8.7M | 17 | **0.0%** | All losses |
| C2024Q4 | -$22.3M | 10 | **0.0%** | All losses |
| C2025Q2 | -$8.3M | 17 | **0.0%** | All losses |

Observed concentration in Q4-like periods is real, but calling it seasonality is premature.

Deterministic explanations to eliminate first:
- RuleSet differences by period
- Unit table/mapping changes
- Fee treatment changes
- Product definition changes
- Settlement methodology changes
- Historical data completeness issues

### 4. OPTIMIZER CONTINUES SELECTING VIC1-NSW1 DESPITE LOSING HISTORY

Despite a -$53M cumulative loss on VIC1-NSW1 (325 trades, 34.5% hit rate), the model continues bidding.

This is an optimizer/decision-policy behavior that needs attribution before introducing policy overlays.

At this stage we should not jump straight to stop-losses or corridor blacklists until first divergence is isolated.

---

## 📊 CONCENTRATION ANALYSIS

**✅ Good news:** Top 10 trades = only 34.8% of profit
- This IS well-distributed across 926 trades and 128 products
- Hit rate of 53.1% is plausible (not miraculous)

**⚠️ But:** Distribution is NOT the same as robustness. 

A strategy can be "distributed" but still fundamentally broken if:
- It loses systematically on one corridor
- It loses systematically in Q4 quarters
- It continues bidding despite mounting losses

---

## 🧪 STRESS TEST RESULTS

| Stress Test | Base P&L | Stressed P&L | Decline |
|-------------|----------|--------------|---------|
| Forecast error ±5% | $22.3M | $19.5M / $25.1M | ±12.4% |
| Funding costs +4% | $22.3M | $22.0M | 1.5% |
| Acquisition fee +0.4% | $22.3M | $22.2M | 0.6% |
| **Participation limit 10% → 5%** | $22.3M | $13.4M | **40.0%** |

**The 40% decline when cutting participation limit to 5% is concerning.**

This suggests:
- Large positions are outsized in the profit generation
- The strategy relies on aggressive sizing to work
- At lower capital scales, returns deteriorate sharply

---

## ❓ YOUR KEY QUESTIONS ANSWERED

### Q1: Where is the edge actually coming from?

**A:** The edge is highly corridor-specific:
- **NSW1-QLD1**: Genuine edge (60.8% hit rate, +$58.3M)
- **V-SA**: Genuine edge (67.8% hit rate, +$17.0M)  
- **VIC1-NSW1**: Large observed loss concentration (-$53M on 325 trades, 34.5% hit rate), root cause pending

The aggregate +$22.3M result is the net of strong positive and strong negative components; attribution is required before causal claims.

### Q2: 926 trades—are these the same products multiple times?

**A:** Yes, heavily:
- 926 total trades
- 128 unique products
- **7.2 trades per product on average**

The model bids on the same product multiple times across months/tranches. This is expected behavior (each product appears in multiple tranches T01-T12).

### Q3: Capacity limits?

**A:** **Capacity is not yet measured.**

Current evidence only shows sensitivity under a participation stress assumption (10% → 5% gives ~40% lower P&L in the stress test). That is not a capacity curve.

Required next step: run explicit capacity study across capital levels with identical rules and compare realized trade opportunity saturation.

### Q4: Capital ledger—is it perfect?

**A:** **NO. There are material issues:**

1. **Negative payouts exist**—this is an economic outcome to explain, not proof of arithmetic error
2. **VIC1-NSW1 concentration is material**—requires attribution by forecast component and settlement logic
3. **Arithmetic reconstruction checks pass on audited forensic sample**

Current status: trade arithmetic appears internally consistent; forecast/valuation divergence remains the primary unresolved source of losses.

---

## 🚨 VERDICT

| Category | Rating | Reasoning |
|----------|--------|-----------|
| **Engineering Quality** | ⭐⭐⭐⭐⭐ | Point-in-time testing, capital lock-up, costs, 926 trades |
| **Backtest Integrity** | ⭐⭐⭐☆☆ | Negative payouts and large forecast misses require root-cause attribution |
| **Commercial Viability** | ⭐⭐☆☆☆ | Large unexplained forecast misses remain unresolved |
| **Ready for Deployment?** | ❌ NO | Root-cause attribution incomplete; deterministic checks pending |

---

## 🔍 NEXT STEPS (Before Deploying Real Capital)

### Immediate Actions

1. **Forensic audit of first losing VIC→NSW trade**
   - Reconstruct auction cost, fees, funding, payout, alpha from primitives
   - Verify settlement reconstruction consistency
   - Identify the first divergence point

2. **Forecast Error Attribution (all historical trades)**
   - Forecast vs actual by trade for payout and realized alpha
   - Group by interconnector, direction, tranche, quarter, ruleset
   - Classify deterministic vs unresolved upstream driver

3. **Deterministic Q4 checks before labeling seasonality**
   - RuleSet/version checks
   - Product/definition consistency checks
   - Settlement method and completeness checks

4. **Capacity study (not estimate)**
   - Measure, don’t infer: run controlled capital ladder and opportunity saturation diagnostics

### Deep Dives

5. **Decompose the $22.3M profit:**
   - NSW1-QLD1: +$58.3M (good)
   - V-SA: +$17.0M (good)
   - VIC1-NSW1: -$53M (bad)
   - Net: +$22.3M (misleading)

   **The headline number hides a catastrophic failure on one corridor.**

6. **Tranche analysis:**
   - T01, T03 are losses (-$18.4M, -$13.5M)
   - T02, T04, T05, T08 are wins
   - Is there a tranche-specific edge or penalty?

7. **Investigate month-by-month P&L**
   - Which months drive the profit?
   - Are there specific decision points that caused the disaster?

---

## Conclusion

The core issue is no longer “does it make money?” but **“why does each losing trade lose money?”**

Current evidence supports:
1. Trade arithmetic can be reconstructed from primitives on forensic sample(s)
2. Large forecast-to-realization misses exist and dominate adverse outcomes
3. Corridor and quarter concentrations are real observations but not yet causal diagnoses
4. Capacity remains unmeasured (pending dedicated study)

**Deployment decision remains NO** until Forecast Error Attribution is completed and deterministic explanations are eliminated.

---

## Iteration 2 Addendum (Verified on 13 July 2026)

To continue the audit, we implemented and ran `scripts/backtest_iteration_scenarios.py` using the same capital-constrained allocation logic as the trusted audit backtest.

### Verification Check

- Trusted baseline (`backtest_audit_detailed.py`): **$22,287,320**, 926 trades, 53.1% hit rate
- Iteration runner baseline: **$22,287,320**, 926 trades, 53.1% hit rate

This confirms scenario comparisons are anchored to the same accounting baseline.

### Scenario Results

| Scenario | Profit | Final Capital | ROI | Trades | Hit Rate |
|---|---:|---:|---:|---:|---:|
| baseline | $22.3M | $23.3M | 2,228.7% | 926 | 53.1% |
| exclude_vic1_nsw1 | $611.5M | $612.5M | 61,154.4% | 3,623 | 59.5% |
| exclude_q4_problem_set | $436.3M | $437.3M | 43,634.7% | 3,369 | 58.3% |
| exclude_vic1_nsw1_and_q4_problem_set | $676.2M | $677.2M | 67,618.9% | 3,436 | 63.2% |
| corridor_stop_loss_-25m | $347.3M | $348.3M | 34,732.0% | 2,820 | 58.4% |
| corridor_stop_loss_-10m | $505.9M | $506.9M | 50,594.8% | 3,299 | 59.1% |

### What Changed in Confidence

1. Exclusion scenarios are useful **diagnostics**, but not proof that a corridor is inherently broken.
2. Quarter exclusions are useful **diagnostics**, but not proof of seasonality.
3. Stop-loss overlays remain policy options, but should follow root-cause attribution, not precede it.

### Revised Deployment View

- **Do not deploy unfiltered baseline yet.**
- **Do not hard-blacklist corridors yet.**
- Complete Phase 4 attribution first, then decide whether fixes belong in:
   - forecast model,
   - settlement reconstruction,
   - product/rule mapping,
   - or optimizer policy.

### Files Generated

- `reports/iteration2_scenarios.csv`
- `reports/iteration2_scenarios.md`
- `scripts/backtest_iteration_scenarios.py`

---

## Phase 4 – Root Cause Attribution (Current Status)

Generated artifacts:
- `reports/FORENSIC_FIRST_VIC_NSW_LOSS.md`
- `reports/forensic_first_vic_nsw_loss.json`
- `reports/phase4_trade_level_attribution.csv`
- `reports/phase4_grouped_attribution.csv`
- `reports/PHASE4_ROOT_CAUSE_ATTRIBUTION.md`

Key findings from current deterministic layer:
1. Forensic reconstruction arithmetic reconciles (cost/fee/funding/payout/alpha).
2. First material divergence is forecasted unit payout vs realized unit payout.
3. Observed dataset snapshot has one ruleset (`RS-BASELINE-v1`), so rule-version drift is not yet supported by current data.
4. Deeper decomposition into price/flow/constraint forecast error still requires internal model component outputs.

Next implementation target:
- Extend attribution inputs with component-level forecasts (regional prices, interconnector flows, constraints, settlement residue) to decompose each losing trade into explicit error contributions.
