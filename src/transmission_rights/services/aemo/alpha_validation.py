"""Investable alpha validation toolkit — Phase 3.

Sections
--------
1. Schema / leakage audit
2. Capital-realism backtest
   - whole units, participation caps
   - capital lock-up across overlapping quarters
   - settlement timing (capital freed only at quarter settlement)
   - no double-spend check
   - fees + funding on locked notional
   - partial / failed fills
3. OOS acceptance gate  (INSUFFICIENT_OOS_EVIDENCE status if failed)
4. Walk-forward validation (rolling, never recalibrate on future)
5. Benchmark suite (buy-all, cheapest, highest-payout, heuristic, no-trade)
6. Per-auction decision record builder
7. Go/No-Go assessment

NOTE: Results from the previous Phase 2C backtest are labelled
      IN_SAMPLE_HEURISTIC — they are NOT investable evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_COLUMNS = [
    "decision_timestamp",
    "information_cutoff",
    "ruleset_id",
    "product_id",
    "auction_clearing_price",
    "fair_value_forecast",
    "final_realised_payout_per_unit",
    "forecast_error_to_realised",
    "realised_alpha",
    "source_lineage",
    "quarter",
    "interconnector_id",
    "tranche_no",
    "units_offered",
    "units_sold",
    "fill_probability",
    "expected_alpha",
    "confidence_band",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        if pd.isna(value):
            return 0.0
        return float(value)
    except Exception:
        return 0.0


def _to_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        v = value
    else:
        v = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if v.tzinfo is None:
        return v.replace(tzinfo=UTC)
    return v.astimezone(UTC)


def _quarter_settlement_date(quarter: str) -> datetime:
    """Approximate AEMO settlement date: end of quarter + 3 months."""
    try:
        year = int(quarter[1:5])
        q = int(quarter[6])
        month_end = q * 3
        settlement_month = month_end + 3
        settlement_year = year + settlement_month // 13
        settlement_month = ((settlement_month - 1) % 12) + 1
        return datetime(settlement_year, settlement_month, 1, tzinfo=UTC)
    except Exception:
        return datetime(2099, 1, 1, tzinfo=UTC)


# ---------------------------------------------------------------------------
# 1. Schema / leakage audit
# ---------------------------------------------------------------------------

def audit_required_columns(frame: pd.DataFrame) -> Dict[str, Any]:
    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]
    return {
        "status": "pass" if not missing else "fail",
        "missing_columns": missing,
        "row_count": int(len(frame)),
    }


def leakage_audit(frame: pd.DataFrame) -> Dict[str, Any]:
    failures: List[Dict[str, Any]] = []
    for _, row in frame.iterrows():
        decision_ts = _to_dt(row["decision_timestamp"])
        cutoff_ts = _to_dt(row["information_cutoff"])
        source_max = _to_dt(row["source_timestamp_max"])

        if cutoff_ts > decision_ts:
            failures.append({
                "product_id": row.get("product_id"),
                "reason": "information_cutoff_after_decision",
                "decision_timestamp": decision_ts.isoformat(),
                "information_cutoff": cutoff_ts.isoformat(),
            })
        if source_max > cutoff_ts:
            failures.append({
                "product_id": row.get("product_id"),
                "reason": "source_timestamp_after_cutoff",
                "source_timestamp_max": source_max.isoformat(),
                "information_cutoff": cutoff_ts.isoformat(),
            })
        if not row.get("ruleset_id"):
            failures.append({"product_id": row.get("product_id"), "reason": "missing_ruleset_id"})

    return {
        "status": "pass" if not failures else "fail",
        "failures": failures,
        "checked_rows": int(len(frame)),
    }


# ---------------------------------------------------------------------------
# 2. Split assignment — CLOSED quarters only
# ---------------------------------------------------------------------------

def assign_split(frame: pd.DataFrame) -> pd.DataFrame:
    """Split based on settled quarters only (payout coverage >= 50%).

    Future / forward quarters get split='future_no_data'.
    OOS = most recent 20% of closed quarters.
    """
    out = frame.copy()
    payout_coverage = (
        out.groupby("quarter")["final_realised_payout_per_unit"]
        .apply(lambda s: s.notna().mean())
        .rename("payout_coverage")
    )
    closed_quarters = sorted(payout_coverage[payout_coverage >= 0.5].index.tolist())
    open_quarters = sorted(payout_coverage[payout_coverage < 0.5].index.tolist())

    n = len(closed_quarters)
    n_oos = max(1, int(n * 0.20))
    n_val = max(1, int(n * 0.15)) if n >= 5 else 0
    n_train = n - n_oos - n_val

    split_map: Dict[str, str] = {}
    for i, q in enumerate(closed_quarters):
        if i < n_train:
            split_map[q] = "in_sample"
        elif i < n_train + n_val:
            split_map[q] = "validation"
        else:
            split_map[q] = "out_of_sample"
    for q in open_quarters:
        split_map[q] = "future_no_data"

    out["split"] = out["quarter"].map(split_map).fillna("future_no_data")
    out["quarter_is_settled"] = out["quarter"].isin(closed_quarters)
    return out


# ---------------------------------------------------------------------------
# 3. Capital-realism backtest
# ---------------------------------------------------------------------------

@dataclass
class BacktestConfig:
    start_capital: float = 50_000.0
    max_participation_by_product: float = 0.10
    max_capital_per_product: float = 0.10
    fee_rate: float = 0.001
    annual_funding_rate: float = 0.08
    min_expected_alpha: float = 0.01
    settlement_lag_quarters: int = 1


@dataclass
class _LockedPosition:
    product_id: str
    quarter: str
    decision_dt: datetime
    units: int
    acquisition_cost: float


def run_investable_backtest(
    frame: pd.DataFrame,
    config: BacktestConfig,
) -> Tuple[pd.DataFrame, pd.DataFrame, Dict[str, Any]]:
    """Capital-realism backtest.

    Constraints enforced
    ====================
    - Capital locked until quarter settlement (no double-spend).
    - Settlement frees capital; net P&L booked at settlement.
    - Overlapping quarters share one capital pool.
    - Units: whole, <= offered*participation_cap, <= floor(free_capital*cap/price).
    - Fill simulation via fill_probability.
    - Fee on notional at purchase; funding on notional for lock period.
    - Only invests in rows with settled payout data.
    """
    data = frame.copy()
    data["decision_dt"] = data["decision_timestamp"].map(_to_dt)
    data = data.sort_values(["decision_dt", "quarter", "interconnector_id", "tranche_no"]).reset_index(drop=True)

    free_capital = config.start_capital
    locked_positions: List[_LockedPosition] = []
    peak = config.start_capital
    drawdown = 0.0
    trades: List[Dict[str, Any]] = []

    for _, row in data.iterrows():
        now_dt = _to_dt(row["decision_timestamp"])
        settlement_dt = _quarter_settlement_date(str(row["quarter"]))

        # Release settled positions
        still_locked: List[_LockedPosition] = []
        for pos in locked_positions:
            pos_settle = _quarter_settlement_date(pos.quarter)
            if now_dt >= pos_settle:
                match = data[data["product_id"] == pos.product_id]
                ppu = 0.0
                if not match.empty:
                    v = match.iloc[0]["final_realised_payout_per_unit"]
                    ppu = _safe_float(v) if not pd.isna(v) else 0.0
                free_capital += pos.acquisition_cost
                free_capital += (pos.units * ppu - pos.acquisition_cost)
            else:
                still_locked.append(pos)
        locked_positions = still_locked

        price = _safe_float(row["auction_clearing_price"])
        expected_alpha = _safe_float(row["expected_alpha"])
        units_offered = max(0, int(_safe_float(row["units_offered"])))
        fill_prob = max(0.0, min(1.0, _safe_float(row["fill_probability"])))

        if price <= 0 or expected_alpha <= config.min_expected_alpha:
            continue
        if pd.isna(row["final_realised_payout_per_unit"]):
            continue  # no settlement data — never invest on unknowns

        max_units_market = int(math.floor(units_offered * config.max_participation_by_product))
        max_units_capital = int(math.floor(free_capital * config.max_capital_per_product / price)) if price > 0 else 0
        bid_units = max(0, min(max_units_market, max_units_capital))
        if bid_units <= 0:
            continue

        executed_units = max(0, int(math.floor(bid_units * fill_prob)))
        if executed_units <= 0:
            continue

        notional = executed_units * price
        fees = notional * config.fee_rate
        lock_days = max(0, (settlement_dt - now_dt).days)
        funding = notional * config.annual_funding_rate * (lock_days / 365.0)
        acquisition_cost = notional + fees + funding

        if acquisition_cost > free_capital:
            scale = free_capital / acquisition_cost
            executed_units = max(0, int(math.floor(executed_units * scale)))
            if executed_units <= 0:
                continue
            notional = executed_units * price
            fees = notional * config.fee_rate
            funding = notional * config.annual_funding_rate * (lock_days / 365.0)
            acquisition_cost = notional + fees + funding

        free_capital -= acquisition_cost
        locked_positions.append(_LockedPosition(
            product_id=str(row["product_id"]),
            quarter=str(row["quarter"]),
            decision_dt=now_dt,
            units=executed_units,
            acquisition_cost=acquisition_cost,
        ))

        payout_per_unit = _safe_float(row["final_realised_payout_per_unit"])
        realised_payout_total = executed_units * payout_per_unit
        realised_pnl = realised_payout_total - acquisition_cost

        portfolio_value = free_capital + sum(p.acquisition_cost for p in locked_positions)
        peak = max(peak, portfolio_value)
        dd = (peak - portfolio_value) / peak if peak > 0 else 0.0
        drawdown = max(drawdown, dd)

        trades.append({
            "decision_timestamp": row["decision_timestamp"],
            "quarter": row["quarter"],
            "interconnector_id": row["interconnector_id"],
            "from_region": row.get("from_region"),
            "product_id": row["product_id"],
            "tranche_no": int(_safe_float(row["tranche_no"])),
            "confidence_band": row.get("confidence_band"),
            "split": row.get("split", "unknown"),
            "max_bid": _safe_float(row["fair_value_forecast"]),
            "auction_clearing_price": price,
            "final_realised_payout_per_unit": payout_per_unit,
            "bid_units": bid_units,
            "executed_units": executed_units,
            "lock_days": lock_days,
            "acquisition_cost": acquisition_cost,
            "realised_payout": realised_payout_total,
            "realised_pnl": realised_pnl,
            "expected_alpha": expected_alpha,
            "realised_alpha": _safe_float(row.get("realised_alpha", 0)),
            "free_capital_after": free_capital,
            "portfolio_value_after": portfolio_value,
        })

    # Final settlement
    for pos in locked_positions:
        match = data[data["product_id"] == pos.product_id]
        ppu = 0.0
        if not match.empty:
            v = match.iloc[0]["final_realised_payout_per_unit"]
            ppu = _safe_float(v) if not pd.isna(v) else 0.0
        free_capital += pos.acquisition_cost
        free_capital += (pos.units * ppu - pos.acquisition_cost)

    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return trades_df, pd.DataFrame(), {
            "label": "IN_SAMPLE_HEURISTIC — not investable evidence",
            "status": "no_trades",
            "start_capital": config.start_capital,
            "end_capital": free_capital,
            "total_pnl": free_capital - config.start_capital,
            "max_drawdown": 0.0,
            "trades": 0,
            "quarters_traded": 0,
        }

    quarter_df = (
        trades_df.groupby("quarter", as_index=False)
        .agg(
            quarter_pnl=("realised_pnl", "sum"),
            quarter_cost=("acquisition_cost", "sum"),
            quarter_trades=("product_id", "count"),
        )
        .sort_values("quarter")
    )
    quarter_df["quarter_return_on_cost"] = np.where(
        quarter_df["quarter_cost"] > 0,
        quarter_df["quarter_pnl"] / quarter_df["quarter_cost"],
        0.0,
    )

    total_cost = float(trades_df["acquisition_cost"].sum())
    total_pnl = float(trades_df["realised_pnl"].sum())
    hit_rate = float((trades_df["realised_pnl"] > 0).mean())
    winning = trades_df[trades_df["realised_pnl"] > 0]["realised_pnl"].sum()
    losing = abs(trades_df[trades_df["realised_pnl"] < 0]["realised_pnl"].sum())
    profit_factor = float(winning / losing) if losing > 0 else float("inf")
    roc = total_pnl / total_cost if total_cost > 0 else 0.0
    vol = float(quarter_df["quarter_return_on_cost"].std(ddof=0)) if len(quarter_df) > 1 else 0.0
    sharpe = roc / vol if vol > 0 else 0.0

    total_pnl_abs = abs(total_pnl)
    max_trade_pct = float(trades_df["realised_pnl"].abs().max() / total_pnl_abs) if total_pnl_abs > 0 else 0.0
    corridor_pnl = trades_df.groupby("interconnector_id")["realised_pnl"].sum()
    max_corr_pct = float(corridor_pnl.abs().max() / total_pnl_abs) if total_pnl_abs > 0 else 0.0

    worst_row = quarter_df.sort_values("quarter_pnl").iloc[0]
    best_row = quarter_df.sort_values("quarter_pnl", ascending=False).iloc[0]

    return trades_df, quarter_df, {
        "label": "IN_SAMPLE_HEURISTIC — not investable evidence",
        "status": "ok",
        "start_capital": config.start_capital,
        "end_capital": float(config.start_capital + total_pnl),
        "total_pnl": total_pnl,
        "return_on_acquisition_cost": roc,
        "hit_rate": hit_rate,
        "profit_factor": profit_factor,
        "sharpe_ratio": sharpe,
        "volatility_quarterly": vol,
        "max_drawdown": drawdown,
        "trades": len(trades_df),
        "quarters_traded": int(trades_df["quarter"].nunique()),
        "max_single_trade_contribution_pct": max_trade_pct,
        "max_corridor_contribution_pct": max_corr_pct,
        "worst_quarter": {"quarter": worst_row["quarter"], "pnl": float(worst_row["quarter_pnl"])},
        "best_quarter": {"quarter": best_row["quarter"], "pnl": float(best_row["quarter_pnl"])},
    }


# ---------------------------------------------------------------------------
# 4. OOS acceptance gate
# ---------------------------------------------------------------------------

@dataclass
class OOSGateConfig:
    min_trades: int = 30
    min_quarters: int = 4
    min_hit_rate: float = 0.50
    min_mean_realised_alpha: float = 0.0
    min_profit_factor: float = 1.25
    min_sharpe: float = 1.0
    max_drawdown: float = 0.25
    max_single_trade_pnl_pct: float = 0.20
    max_corridor_pnl_pct: float = 0.40


def oos_gate(
    oos_trades_df: pd.DataFrame,
    oos_summary: Dict[str, Any],
    gate_config: OOSGateConfig = OOSGateConfig(),
) -> Dict[str, Any]:
    """Evaluate hard OOS acceptance gates.

    Returns status PASS or INSUFFICIENT_OOS_EVIDENCE.
    """
    failures: List[str] = []
    checks: Dict[str, Any] = {}

    n_trades = len(oos_trades_df)
    n_quarters = int(oos_trades_df["quarter"].nunique()) if not oos_trades_df.empty else 0

    checks["min_trades"] = {"required": gate_config.min_trades, "actual": n_trades, "pass": n_trades >= gate_config.min_trades}
    if not checks["min_trades"]["pass"]:
        failures.append(f"min_trades: {n_trades} < {gate_config.min_trades}")

    checks["min_quarters"] = {"required": gate_config.min_quarters, "actual": n_quarters, "pass": n_quarters >= gate_config.min_quarters}
    if not checks["min_quarters"]["pass"]:
        failures.append(f"min_quarters: {n_quarters} < {gate_config.min_quarters}")

    if oos_trades_df.empty:
        return {
            "status": "INSUFFICIENT_OOS_EVIDENCE",
            "reason": "Zero out-of-sample trades executed.",
            "gate_checks": checks,
            "failures": failures,
        }

    hit_rate = float((oos_trades_df["realised_pnl"] > 0).mean())
    checks["hit_rate"] = {"required": gate_config.min_hit_rate, "actual": hit_rate, "pass": hit_rate >= gate_config.min_hit_rate}
    if not checks["hit_rate"]["pass"]:
        failures.append(f"hit_rate: {hit_rate:.3f} < {gate_config.min_hit_rate}")

    mean_alpha = float(oos_trades_df["realised_alpha"].mean())
    checks["mean_realised_alpha"] = {"required": gate_config.min_mean_realised_alpha, "actual": mean_alpha, "pass": mean_alpha > gate_config.min_mean_realised_alpha}
    if not checks["mean_realised_alpha"]["pass"]:
        failures.append(f"mean_realised_alpha: {mean_alpha:.2f} <= 0")

    winning = oos_trades_df[oos_trades_df["realised_pnl"] > 0]["realised_pnl"].sum()
    losing = abs(oos_trades_df[oos_trades_df["realised_pnl"] < 0]["realised_pnl"].sum())
    pf = float(winning / losing) if losing > 0 else float("inf")
    checks["profit_factor"] = {"required": gate_config.min_profit_factor, "actual": pf, "pass": pf >= gate_config.min_profit_factor}
    if not checks["profit_factor"]["pass"]:
        failures.append(f"profit_factor: {pf:.3f} < {gate_config.min_profit_factor}")

    sharpe = oos_summary.get("sharpe_ratio", 0.0)
    checks["sharpe_ratio"] = {"required": gate_config.min_sharpe, "actual": sharpe, "pass": sharpe >= gate_config.min_sharpe}
    if not checks["sharpe_ratio"]["pass"]:
        failures.append(f"sharpe: {sharpe:.3f} < {gate_config.min_sharpe}")

    max_dd = oos_summary.get("max_drawdown", 1.0)
    checks["max_drawdown"] = {"required": gate_config.max_drawdown, "actual": max_dd, "pass": max_dd <= gate_config.max_drawdown}
    if not checks["max_drawdown"]["pass"]:
        failures.append(f"max_drawdown: {max_dd:.3f} > {gate_config.max_drawdown}")

    total_pnl_abs = abs(float(oos_trades_df["realised_pnl"].sum()))
    max_trade_pct = float(oos_trades_df["realised_pnl"].abs().max() / total_pnl_abs) if total_pnl_abs > 0 else 0.0
    checks["max_single_trade_pnl_pct"] = {"required": gate_config.max_single_trade_pnl_pct, "actual": max_trade_pct, "pass": max_trade_pct <= gate_config.max_single_trade_pnl_pct}
    if not checks["max_single_trade_pnl_pct"]["pass"]:
        failures.append(f"single_trade_concentration: {max_trade_pct:.3f} > {gate_config.max_single_trade_pnl_pct}")

    corridor_pnl = oos_trades_df.groupby("interconnector_id")["realised_pnl"].sum()
    max_corr_pct = float(corridor_pnl.abs().max() / total_pnl_abs) if total_pnl_abs > 0 else 0.0
    checks["max_corridor_pnl_pct"] = {"required": gate_config.max_corridor_pnl_pct, "actual": max_corr_pct, "pass": max_corr_pct <= gate_config.max_corridor_pnl_pct}
    if not checks["max_corridor_pnl_pct"]["pass"]:
        failures.append(f"corridor_concentration: {max_corr_pct:.3f} > {gate_config.max_corridor_pnl_pct}")

    return {
        "status": "PASS" if not failures else "INSUFFICIENT_OOS_EVIDENCE",
        "gate_checks": checks,
        "failures": failures,
        "n_oos_trades": n_trades,
        "n_oos_quarters": n_quarters,
    }


# ---------------------------------------------------------------------------
# 5. Walk-forward validation
# ---------------------------------------------------------------------------

def walk_forward_validation(
    frame: pd.DataFrame,
    config: BacktestConfig,
) -> Dict[str, Any]:
    """True rolling walk-forward. No recalibration on future data."""
    payout_coverage = (
        frame.groupby("quarter")["final_realised_payout_per_unit"]
        .apply(lambda s: s.notna().mean())
    )
    settled = sorted(payout_coverage[payout_coverage >= 0.5].index.tolist())

    if len(settled) < 5:
        return {
            "status": "insufficient_data",
            "settled_quarters": len(settled),
            "reason": "Need at least 5 settled quarters.",
        }

    results = []
    all_wf_trades: List[pd.DataFrame] = []

    for i, test_quarter in enumerate(settled):
        test_rows = frame[frame["quarter"] == test_quarter].copy()
        test_rows["split"] = "walk_forward"
        test_rows["quarter_is_settled"] = True

        trades_df, _, _ = run_investable_backtest(test_rows, config)

        q_pnl = float(trades_df["realised_pnl"].sum()) if not trades_df.empty else 0.0
        results.append({
            "test_quarter": test_quarter,
            "train_quarters_available": i,
            "products_considered": int(len(test_rows)),
            "products_with_positive_expected_alpha": int((test_rows["expected_alpha"] > 0).sum()),
            "trades_executed": int(len(trades_df)),
            "quarter_pnl": q_pnl,
            "hit_rate": float((trades_df["realised_pnl"] > 0).mean()) if not trades_df.empty else None,
            "mean_realised_alpha_per_unit": float(test_rows["realised_alpha"].dropna().mean()) if test_rows["realised_alpha"].notna().any() else None,
        })

        if not trades_df.empty:
            all_wf_trades.append(trades_df)

    wf_trades_df = pd.concat(all_wf_trades) if all_wf_trades else pd.DataFrame()
    traded_quarters = [r for r in results if r["trades_executed"] > 0]
    hit_quarters = [r for r in traded_quarters if r["quarter_pnl"] > 0]
    total_pnl = sum(r["quarter_pnl"] for r in results)

    return {
        "status": "ok",
        "settled_quarters_tested": len(settled),
        "quarters_with_trades": len(traded_quarters),
        "total_pnl": total_pnl,
        "quarter_hit_rate": float(len(hit_quarters) / len(traded_quarters)) if traded_quarters else None,
        "per_quarter": results,
        "summary": _wf_summary(wf_trades_df),
    }


def _wf_summary(trades_df: pd.DataFrame) -> Dict[str, Any]:
    if trades_df.empty:
        return {"status": "no_trades"}
    total_pnl = float(trades_df["realised_pnl"].sum())
    total_cost = float(trades_df["acquisition_cost"].sum())
    hit_rate = float((trades_df["realised_pnl"] > 0).mean())
    winning = trades_df[trades_df["realised_pnl"] > 0]["realised_pnl"].sum()
    losing = abs(trades_df[trades_df["realised_pnl"] < 0]["realised_pnl"].sum())
    pf = float(winning / losing) if losing > 0 else float("inf")
    roc = total_pnl / total_cost if total_cost > 0 else 0.0
    return {
        "total_trades": int(len(trades_df)),
        "total_pnl": total_pnl,
        "return_on_cost": roc,
        "hit_rate": hit_rate,
        "profit_factor": pf,
    }


# ---------------------------------------------------------------------------
# 6. Benchmark suite
# ---------------------------------------------------------------------------

def _benchmark_buy_all(frame: pd.DataFrame, config: BacktestConfig) -> Dict[str, Any]:
    settled = frame[frame["final_realised_payout_per_unit"].notna()].copy()
    settled = settled.copy()
    settled["expected_alpha"] = 9999.0
    settled["split"] = "benchmark"
    settled["quarter_is_settled"] = True
    _, _, summary = run_investable_backtest(settled, config)
    summary["benchmark"] = "buy_all"
    return summary


def _benchmark_cheapest(frame: pd.DataFrame, config: BacktestConfig, top_n: int = 20) -> Dict[str, Any]:
    settled = frame[frame["final_realised_payout_per_unit"].notna()].copy()
    pieces = []
    for _, sub in settled.groupby("quarter"):
        pieces.append(sub.nsmallest(top_n, "auction_clearing_price"))
    if not pieces:
        return {"benchmark": "cheapest", "status": "no_data"}
    cheap = pd.concat(pieces).copy()
    cheap["expected_alpha"] = 9999.0
    cheap["split"] = "benchmark"
    cheap["quarter_is_settled"] = True
    _, _, summary = run_investable_backtest(cheap, config)
    summary["benchmark"] = "cheapest"
    return summary


def _benchmark_highest_payout(frame: pd.DataFrame, config: BacktestConfig, top_n: int = 20) -> Dict[str, Any]:
    settled = frame[frame["final_realised_payout_per_unit"].notna()].copy()
    quarters = sorted(settled["quarter"].unique())
    selected: List[pd.DataFrame] = []
    for i, q in enumerate(quarters):
        if i == 0:
            continue
        prior = settled[settled["quarter"].isin(quarters[:i])]
        avg = (
            prior.groupby(["interconnector_id", "from_region", "tranche_no"])["final_realised_payout_per_unit"]
            .mean().reset_index().nlargest(top_n, "final_realised_payout_per_unit")
        )
        curr = settled[settled["quarter"] == q].merge(
            avg[["interconnector_id", "from_region", "tranche_no"]],
            on=["interconnector_id", "from_region", "tranche_no"],
        )
        if not curr.empty:
            selected.append(curr)
    if not selected:
        return {"benchmark": "highest_historical_payout", "status": "no_data"}
    sel = pd.concat(selected).copy()
    sel["expected_alpha"] = 9999.0
    sel["split"] = "benchmark"
    sel["quarter_is_settled"] = True
    _, _, summary = run_investable_backtest(sel, config)
    summary["benchmark"] = "highest_historical_payout"
    return summary


def _benchmark_no_trade(config: BacktestConfig) -> Dict[str, Any]:
    return {
        "benchmark": "no_trade",
        "status": "ok",
        "label": "IN_SAMPLE_HEURISTIC — not investable evidence",
        "start_capital": config.start_capital,
        "end_capital": config.start_capital,
        "total_pnl": 0.0,
        "return_on_acquisition_cost": 0.0,
        "hit_rate": None,
        "profit_factor": None,
        "sharpe_ratio": None,
        "max_drawdown": 0.0,
    }


def run_benchmarks(frame: pd.DataFrame, config: BacktestConfig) -> Dict[str, Dict[str, Any]]:
    return {
        "buy_all": _benchmark_buy_all(frame, config),
        "cheapest_products": _benchmark_cheapest(frame, config),
        "highest_historical_payout": _benchmark_highest_payout(frame, config),
        "no_trade": _benchmark_no_trade(config),
    }


# ---------------------------------------------------------------------------
# 7. Grouped performance / split helpers
# ---------------------------------------------------------------------------

def grouped_performance(trades_df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    if trades_df.empty:
        return {"by_corridor": [], "by_tranche": [], "by_confidence_band": []}

    by_corridor = (
        trades_df.groupby(["interconnector_id", "from_region"], as_index=False)
        .agg(trades=("product_id", "count"), pnl=("realised_pnl", "sum"), mean_alpha=("realised_alpha", "mean"))
        .sort_values("pnl", ascending=False).to_dict(orient="records")
    )
    by_tranche = (
        trades_df.groupby(["tranche_no"], as_index=False)
        .agg(trades=("product_id", "count"), pnl=("realised_pnl", "sum"), mean_alpha=("realised_alpha", "mean"))
        .sort_values("tranche_no").to_dict(orient="records")
    )
    by_confidence = (
        trades_df.groupby(["confidence_band"], as_index=False)
        .agg(trades=("product_id", "count"), pnl=("realised_pnl", "sum"), mean_alpha=("realised_alpha", "mean"))
        .sort_values("pnl", ascending=False).to_dict(orient="records")
    )
    return {"by_corridor": by_corridor, "by_tranche": by_tranche, "by_confidence_band": by_confidence}


def split_summary(frame: pd.DataFrame, config: BacktestConfig) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for split in ["in_sample", "validation", "out_of_sample"]:
        subset = frame[frame["split"] == split].copy()
        trades_df, quarter_df, summary = run_investable_backtest(subset, config)
        grouped = grouped_performance(trades_df)
        out[split] = {
            "summary": summary,
            "rows": int(len(subset)),
            "trades": int(len(trades_df)),
            "quarter_rows": int(len(quarter_df)),
            **grouped,
        }
    return out


def latest_decision_report(trades_df: pd.DataFrame) -> Dict[str, Any]:
    if trades_df.empty:
        return {"status": "no_trades"}
    latest_quarter = sorted(trades_df["quarter"].unique())[-1]
    latest = trades_df[trades_df["quarter"] == latest_quarter].copy()
    return {
        "status": "ok",
        "quarter": latest_quarter,
        "products": latest[[
            "product_id", "max_bid", "bid_units", "executed_units",
            "auction_clearing_price", "final_realised_payout_per_unit", "realised_pnl",
        ]].to_dict(orient="records"),
        "realised_pnl": float(latest["realised_pnl"].sum()),
        "deployable_capital_estimate": float(latest["acquisition_cost"].sum()),
    }


# ---------------------------------------------------------------------------
# 8. Per-auction decision records
# ---------------------------------------------------------------------------

def build_auction_decision_records(frame: pd.DataFrame, config: BacktestConfig) -> List[Dict[str, Any]]:
    settled = frame[frame["final_realised_payout_per_unit"].notna()].copy()
    records: List[Dict[str, Any]] = []

    for _, row in settled.iterrows():
        price = _safe_float(row["auction_clearing_price"])
        payout = _safe_float(row["final_realised_payout_per_unit"])
        fv = _safe_float(row["fair_value_forecast"])
        ea = _safe_float(row["expected_alpha"])
        ra = _safe_float(row.get("realised_alpha", 0))

        decision = "BID" if (price > 0 and ea > config.min_expected_alpha) else "PASS"
        rejection_reason = None
        if decision == "PASS":
            rejection_reason = "zero_clearing_price" if price <= 0 else f"expected_alpha={ea:.2f}_below_threshold"

        records.append({
            "decision_date": str(row["decision_timestamp"]),
            "quarter": str(row["quarter"]),
            "product_id": str(row["product_id"]),
            "interconnector_id": str(row["interconnector_id"]),
            "from_region": str(row.get("from_region", "")),
            "tranche_no": int(_safe_float(row["tranche_no"])),
            "decision": decision,
            "rejection_reason": rejection_reason,
            "fair_value_forecast": fv,
            "recommended_max_bid": fv,
            "recommended_max_units": int(math.floor(_safe_float(row["units_offered"]) * config.max_participation_by_product)),
            "expected_edge": ea,
            "confidence_band": str(row.get("confidence_band", "")),
            "auction_clearing_price": price,
            "units_offered": int(_safe_float(row["units_offered"])),
            "units_sold": int(_safe_float(row["units_sold"])),
            "final_realised_payout_per_unit": payout,
            "realised_alpha_per_unit": ra,
            "forecast_error_to_clearing": fv - price,
            "forecast_error_to_realised": _safe_float(row.get("forecast_error_to_realised", 0)),
            "ruleset_id": str(row.get("ruleset_id", "")),
            "lesson": _lesson(decision, ea, ra, fv, price, payout),
        })

    return records


def _lesson(decision: str, ea: float, ra: float, fv: float, price: float, payout: float) -> str:
    if decision == "PASS":
        return "MISSED_OPPORTUNITY: passed but realised alpha was positive" if ra > 0 else "CORRECT_PASS: passed and realised alpha was not positive"
    if ra > 0:
        return "CORRECT_BID: positive realised alpha"
    if ra < 0:
        return "INCORRECT_BID: negative realised alpha — overpaid"
    return "NEUTRAL_BID: zero realised alpha"


# ---------------------------------------------------------------------------
# 9. Go / No-Go assessment
# ---------------------------------------------------------------------------

def go_no_go_assessment(
    wf_result: Dict[str, Any],
    oos_gate_result: Dict[str, Any],
    benchmarks: Dict[str, Dict[str, Any]],
    in_sample_summary: Dict[str, Any],
) -> Dict[str, Any]:
    oos_pass = oos_gate_result.get("status") == "PASS"
    wf_ok = wf_result.get("status") == "ok"
    wf_quarters = wf_result.get("quarters_with_trades", 0)
    wf_pnl = wf_result.get("total_pnl", 0.0)

    buy_all_pnl = benchmarks.get("buy_all", {}).get("total_pnl", 0.0)
    no_trade_pnl = 0.0

    if oos_pass and wf_ok and wf_quarters >= 4 and wf_pnl > buy_all_pnl:
        classification = "GREEN"
        rationale = "OOS gates passed. Walk-forward positive with >=4 traded quarters, outperforms buy-all benchmark."
    elif wf_ok and wf_quarters >= 2 and wf_pnl > no_trade_pnl:
        classification = "AMBER"
        rationale = "Walk-forward positive vs no-trade but OOS gates not fully met. More settled quarters needed."
    else:
        classification = "RED"
        rationale = "Walk-forward has zero or insufficient traded quarters, or negative PnL. Does not support proprietary trading."

    return {
        "classification": classification,
        "rationale": rationale,
        "oos_gate_status": oos_gate_result.get("status"),
        "walk_forward_quarters_with_trades": wf_quarters,
        "walk_forward_total_pnl": wf_pnl,
        "walk_forward_quarter_hit_rate": wf_result.get("quarter_hit_rate"),
        "in_sample_label": "IN_SAMPLE_HEURISTIC — not investable evidence",
        "in_sample_note": (
            "The $50k->$15.1m in-sample result reflects a heuristic with no look-ahead "
            "bias in the data, but the strategy has not been validated on genuinely "
            "unseen quarters. It is NOT investable evidence."
        ),
        "next_steps": _next_steps(classification),
    }


def _next_steps(classification: str) -> List[str]:
    if classification == "GREEN":
        return [
            "Commission independent model validation.",
            "Size position with Kelly/volatility-scaled capital.",
            "Paper-trade next live quarter before deploying real capital.",
        ]
    if classification == "AMBER":
        return [
            "Wait for more settled quarters (target: 4+ OOS quarters with trades).",
            "Review why OOS has few/no trades — check thresholds vs settled data.",
            "Do not deploy capital until OOS gates pass.",
        ]
    return [
        "Do not deploy capital.",
        "Investigate whether the heuristic has genuine predictive power.",
        "Consider building a first-principles valuation model.",
        "Re-run validation after >= 4 more quarters of settled auction data.",
    ]
