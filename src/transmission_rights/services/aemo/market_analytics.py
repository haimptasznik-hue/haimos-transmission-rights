from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from transmission_rights.adapters.aemo.historical_data_fetcher import HistoricalDataFetcher


def _safe_corr(a: pd.Series, b: pd.Series) -> float:
    if len(a) < 2 or len(b) < 2:
        return 0.0
    if float(a.std(ddof=0)) == 0.0 or float(b.std(ddof=0)) == 0.0:
        return 0.0
    value = a.corr(b)
    if pd.isna(value):
        return 0.0
    return float(value)


def load_market_frame(results_dir: Path) -> pd.DataFrame:
    if not results_dir.exists():
        return pd.DataFrame()

    fetcher = HistoricalDataFetcher()
    rows: list[dict[str, Any]] = []

    for path in sorted(results_dir.glob("*.csv")):
        try:
            snapshots = fetcher.parse_sra_results(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for snapshot in snapshots:
            units_offered = max(int(snapshot.units_offered or 0), 1)
            units_sold = int(snapshot.units_sold or 0)
            fill_rate = units_sold / units_offered
            rows.append(
                {
                    "contract_id": snapshot.contract_id,
                    "quarter": snapshot.quarter,
                    "tranche_no": int(snapshot.tranche_no or 0),
                    "interconnector": snapshot.directional_interconnector,
                    "from_region": snapshot.from_region,
                    "units_offered": units_offered,
                    "units_sold": units_sold,
                    "fill_rate": fill_rate,
                    "clearing_price": float(snapshot.clearing_price or 0.0),
                    "source_file": path.name,
                }
            )

    if not rows:
        return pd.DataFrame()

    frame = pd.DataFrame(rows)
    frame = frame[frame["clearing_price"] > 0].copy()
    frame["product_key"] = (
        frame["quarter"].astype(str)
        + ":"
        + frame["interconnector"].astype(str)
        + ":"
        + frame["from_region"].astype(str)
    )
    frame["fill_rate_pct"] = frame["fill_rate"].rank(pct=True) * 100.0
    frame["volume_pct"] = frame["units_offered"].rank(pct=True) * 100.0
    return frame


def correlation_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"status": "no_data", "message": "No SRA rows available."}

    cols = ["fill_rate", "units_sold", "units_offered", "clearing_price"]
    corr_p = frame[cols].corr(method="pearson").round(4)
    corr_s = frame[cols].corr(method="spearman").round(4)

    interconnector_stats = (
        frame.groupby("interconnector", as_index=False)
        .agg(
            rows=("clearing_price", "size"),
            mean_price=("clearing_price", "mean"),
            price_std=("clearing_price", "std"),
            mean_fill_rate=("fill_rate", "mean"),
            fill_vs_price_corr=("fill_rate", lambda s: _safe_corr(s, frame.loc[s.index, "clearing_price"])),
        )
        .fillna(0.0)
        .sort_values("rows", ascending=False)
    )

    quarterly_stats = (
        frame.groupby("quarter", as_index=False)
        .agg(
            rows=("clearing_price", "size"),
            mean_price=("clearing_price", "mean"),
            price_std=("clearing_price", "std"),
            mean_fill_rate=("fill_rate", "mean"),
        )
        .fillna(0.0)
        .sort_values("quarter")
    )

    return {
        "status": "ok",
        "rows": int(len(frame)),
        "pearson": corr_p.to_dict(),
        "spearman": corr_s.to_dict(),
        "interconnector": interconnector_stats.round(4).to_dict(orient="records"),
        "quarterly": quarterly_stats.round(4).to_dict(orient="records"),
    }


def trend_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"status": "no_data", "message": "No SRA rows available."}

    trend_rows: list[dict[str, Any]] = []

    for key, grp in frame.groupby("product_key"):
        ordered = grp.sort_values("tranche_no")
        if len(ordered) < 2:
            continue

        x = ordered["tranche_no"].to_numpy(dtype=float)
        y = ordered["clearing_price"].to_numpy(dtype=float)
        if len(np.unique(x)) < 2:
            continue

        slope = float(np.polyfit(x, y, 1)[0])
        fill_price_corr = _safe_corr(ordered["fill_rate"], ordered["clearing_price"]) if len(ordered) > 1 else 0.0
        trend_rows.append(
            {
                "product_key": key,
                "n_points": int(len(ordered)),
                "tranche_start": int(ordered["tranche_no"].min()),
                "tranche_end": int(ordered["tranche_no"].max()),
                "price_slope_per_tranche": round(slope, 4),
                "fill_price_corr": round(0.0 if np.isnan(fill_price_corr) else fill_price_corr, 4),
                "start_price": round(float(ordered["clearing_price"].iloc[0]), 2),
                "end_price": round(float(ordered["clearing_price"].iloc[-1]), 2),
            }
        )

    if not trend_rows:
        return {"status": "ok", "products_with_trend": 0, "rows": []}

    trend_df = pd.DataFrame(trend_rows)
    rising = int((trend_df["price_slope_per_tranche"] > 0).sum())
    falling = int((trend_df["price_slope_per_tranche"] < 0).sum())

    return {
        "status": "ok",
        "products_with_trend": int(len(trend_df)),
        "rising_trends": rising,
        "falling_trends": falling,
        "avg_slope": round(float(trend_df["price_slope_per_tranche"].mean()), 4),
        "rows": trend_df.sort_values("price_slope_per_tranche", ascending=False)
        .head(100)
        .to_dict(orient="records"),
    }


def sequential_backtest_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"status": "no_data", "message": "No SRA rows available."}

    eval_rows: list[dict[str, Any]] = []

    for key, grp in frame.groupby("product_key"):
        ordered = grp.sort_values("tranche_no").reset_index(drop=True)
        if len(ordered) < 2:
            continue

        for i in range(len(ordered) - 1):
            current = ordered.iloc[i]
            nxt = ordered.iloc[i + 1]

            current_price = float(current["clearing_price"])
            next_price = float(nxt["clearing_price"])
            if current_price <= 0:
                continue

            f_pct = float(current["fill_rate_pct"])
            if f_pct >= 70:
                recommendation = "BUY"
            elif f_pct <= 30:
                recommendation = "AVOID"
            else:
                recommendation = "WATCH"

            forward_return_pct = ((next_price - current_price) / current_price) * 100.0

            if recommendation == "BUY":
                correct = forward_return_pct > 0
                signal_markout = forward_return_pct
            elif recommendation == "AVOID":
                correct = forward_return_pct < 0
                signal_markout = -forward_return_pct
            else:
                correct = abs(forward_return_pct) <= 2.0
                signal_markout = -abs(forward_return_pct)

            eval_rows.append(
                {
                    "product_key": key,
                    "quarter": current["quarter"],
                    "tranche_no": int(current["tranche_no"]),
                    "recommendation": recommendation,
                    "fill_rate_pct": round(f_pct, 2),
                    "current_price": round(current_price, 2),
                    "next_price": round(next_price, 2),
                    "forward_return_pct": round(forward_return_pct, 4),
                    "signal_markout_pct": round(signal_markout, 4),
                    "correct": bool(correct),
                }
            )

    if not eval_rows:
        return {"status": "ok", "pairs_evaluated": 0, "message": "No sequential tranche pairs found."}

    eval_df = pd.DataFrame(eval_rows)

    by_rec = (
        eval_df.groupby("recommendation", as_index=False)
        .agg(
            count=("correct", "size"),
            hit_rate=("correct", "mean"),
            avg_forward_return_pct=("forward_return_pct", "mean"),
            avg_signal_markout_pct=("signal_markout_pct", "mean"),
        )
        .sort_values("recommendation")
    )

    baseline_markout = float(-eval_df["forward_return_pct"].abs().mean())
    strategy_markout = float(eval_df["signal_markout_pct"].mean())

    return {
        "status": "ok",
        "pairs_evaluated": int(len(eval_df)),
        "overall_hit_rate": round(float(eval_df["correct"].mean()), 4),
        "strategy_avg_signal_markout_pct": round(strategy_markout, 4),
        "baseline_watch_all_markout_pct": round(baseline_markout, 4),
        "uplift_vs_baseline_pct": round(strategy_markout - baseline_markout, 4),
        "by_recommendation": by_rec.round(4).to_dict(orient="records"),
    }
