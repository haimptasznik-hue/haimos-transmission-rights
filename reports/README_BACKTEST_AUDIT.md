# Point-in-Time Backtest Audit (January 2025 - July 2026)

## 📊 Quick Summary

**Headline Result:** $1M → $23.3M (+2,230%)  
**Engineering Quality:** ⭐⭐⭐⭐⭐ (Sound)  
**Credibility:** ⭐⭐☆☆☆ (Serious red flags)  
**Deployable:** ❌ NO (Not without fixing identified issues)

---

## 🚨 Critical Finding

**The +$22.3M profit hides a fundamental problem:**

| Corridor | Profit | Hit Rate | Status |
|----------|--------|----------|--------|
| NSW1-QLD1 | +$58.3M | 60.8% | ✅ WORKS |
| V-SA | +$17.0M | 67.8% | ✅ WORKS |
| VIC1-NSW1 | -$53.0M | 34.5% | ❌ BREAKS |
| **NET** | **+$22.3M** | — | ⚠️ UNRELIABLE |

**One corridor (35% of trades) loses as much as the other two make combined.**

---

## 📁 Audit Documents

### Executive Summary
- **[AUDIT_EXECUTIVE_SUMMARY.txt](AUDIT_EXECUTIVE_SUMMARY.txt)** ← START HERE
  - One-page overview of findings, red flags, and next steps
  - What you need to know before making decisions

### Critical Findings
- **[AUDIT_SUMMARY_CRITICAL_FINDINGS.md](AUDIT_SUMMARY_CRITICAL_FINDINGS.md)**
  - Detailed breakdown of each red flag
  - Why the 22x return is not credible in current form
  - Specific problems with corridors and seasonality

### Corridor Analysis
- **[CRITICAL_VIC_NSW_CORRIDOR_ANALYSIS.md](CRITICAL_VIC_NSW_CORRIDOR_ANALYSIS.md)**
  - Deep dive on the VIC1-NSW1 disaster
  - Explains negative payouts (real market mechanic)
  - Why the model keeps bidding on losing corridor

### Technical Audit Report
- **[backtest_audit_detailed.md](backtest_audit_detailed.md)**
  - Capital ledger reconciliation
  - Profit concentration analysis (well-distributed)
  - Stress test results (±5% forecast error, +4% funding costs, etc.)

---

## 📈 Data Files

### Trade-Level Details
- **[backtest_detailed_trades.csv](backtest_detailed_trades.csv)** (222 KB)
  - 926 rows (one per trade)
  - Columns: decision_date, quarter, product_id, corridor, tranche, units, cost_per_unit, total_cost, payout_per_unit, alpha, etc.
  - Use this to audit individual trades or reanalyze

### Monthly Summary
- **[backtest_monthly_summary.csv](backtest_monthly_summary.csv)**
  - 18 rows (Jan 2025 - Jul 2026)
  - Columns: decision_date, available_capital, locked_capital, cumulative_pnl, month_pnl, trades_this_month

### Historical Decision Records
- **[historical_investment_decisions/](historical_investment_decisions/)** (1,740 JSON files)
  - One file per product per quarter
  - Contains: decision, fair_value, clearing_price, realized_payout, alpha, confidence, lessons

---

## 🔍 Key Findings by Category

### Concentration
- ✅ Top 10 trades = 34.8% of profit (well-distributed)
- ✅ 926 trades across 128 unique products (diversified)
- ✅ 53.1% hit rate (plausible for profitable strategy)
- ❌ But profit is HEAVILY dependent on 2 corridors and specific quarters

### Red Flags

1. **Corridor Disaster (VIC1-NSW1)**
   - -$53M loss on 325 trades (35% of all trading)
   - 34.5% hit rate (below breakeven)
   - Suggests model lacks edge on this corridor

2. **Negative Payouts**
   - Example: Bid $466/unit expecting +$2,002 payout → Received -$2,789 penalty
   - Reveals model can't forecast extreme congestion
   - Is this a real risk or a data issue?

3. **Q4 Seasonality**
   - 0% hit rate in C2023Q4, C2024Q4, C2025Q2
   - C2024Q4 alone accounts for -$22.3M
   - Without C2024Q4, profit would be 0
   - Q4 quarters are systematically broken

4. **Capacity Fragility**
   - At 5% position sizing: returns drop 40%
   - Realistic capacity probably $2-5M (not $10M+)
   - At true capacity, returns would be 5-8x (not 22x)

### Stress Tests
- Forecast error ±5%: ±12% return ✅ (robust)
- Funding costs +4%: -1.5% return ✅ (robust)
- Acquisition fees +0.4%: -0.6% return ✅ (robust)
- Position limit 10%→5%: -40% return ❌ (fragile)

---

## ❓ Questions This Audit Answers

**Q: Is the 22x return real?**
A: The backtest engineering is sound, but the result hides problems. It's the net of two strong edges (+$75M) and one catastrophic liability (-$53M).

**Q: Where's the edge coming from?**
A: NSW1-QLD1 and V-SA corridors have genuine 60%+ hit rates. VIC1-NSW1 has systematic losses. Strategy lacks corridor-specific risk management.

**Q: Can it scale to $5-10M?**
A: Unlikely. Stress testing shows 40% return degradation at 50% of capital. Realistic capacity ~$2-5M.

**Q: Is the capital ledger perfect?**
A: Technically correct but reveals the model trading into known losses (VIC1-NSW1 with 34.5% hit rate).

**Q: What happens if we exclude VIC1-NSW1?**
A: Profit becomes $75.3M (not $22.3M), returns 7,430% (not 2,230%), and strategy becomes much more credible.

---

## 🎯 Before Deploying Real Capital

### Immediate (Do First)
1. Run backtest excluding VIC1-NSW1 entirely
2. Run backtest excluding Q4 quarters
3. Implement stop-losses (corridor limit, hit rate threshold)
4. Test at realistic capital sizes ($500K, $1M, $2M, $5M)

### Deep Dives
5. Investigate negative payouts (when do they occur? Can we avoid them?)
6. Investigate Q4 seasonality (data quality? Market regime? Look-ahead bias?)
7. Understand VIC1-NSW1 corridor (why keep trading despite losses?)

### Validation
8. If returns still strong after excluding problem corridors → confidence ⬆️
9. If returns collapse → learned which corridors have edge and which don't (still valuable)

---

## 📋 Verdict Matrix

| Dimension | Rating | Status |
|-----------|--------|--------|
| **Engineering** | ⭐⭐⭐⭐⭐ | Backtest is technically sound |
| **Integrity** | ⭐⭐⭐☆☆ | Multiple warning signs |
| **Credibility** | ⭐⭐☆☆☆ | Result hides fundamental problems |
| **Deployable** | ❌ | NO – Not without fixing VIC1-NSW1 |

---

## 💡 Bottom Line

**Don't believe the 22x result. Don't dismiss it either.**

The engineering is solid. The data is real. But the result is the net of:
- Two strong profitable strategies (+$75M)
- One catastrophic loss (-$53M)
- A handful of extreme outlier trades

Your job is to **break the strategy**. If it still works after aggressive testing, you have something real.

If it falls apart, you've learned which corridors to trade and which to avoid—still valuable.

---

## 📞 Files to Read in Order

1. **[AUDIT_EXECUTIVE_SUMMARY.txt](AUDIT_EXECUTIVE_SUMMARY.txt)** (5 min)
2. **[AUDIT_SUMMARY_CRITICAL_FINDINGS.md](AUDIT_SUMMARY_CRITICAL_FINDINGS.md)** (10 min)
3. **[CRITICAL_VIC_NSW_CORRIDOR_ANALYSIS.md](CRITICAL_VIC_NSW_CORRIDOR_ANALYSIS.md)** (10 min)
4. **[backtest_audit_detailed.md](backtest_audit_detailed.md)** (15 min)
5. **[backtest_detailed_trades.csv](backtest_detailed_trades.csv)** (analyze yourself)

---

Generated: July 13, 2026  
Period: January 1, 2025 - July 1, 2026  
Capital: $1,000,000 → $23,287,320
