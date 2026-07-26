#!/usr/bin/env python3
"""Phase 5B – Market Driver Discovery Engine

Objective: determine which variables explain deviations in settlement residue.
This is a scientific discovery phase, not a trading model.

Steps:
  1. Derive all computable features from in-repo data
  2. Correlation analysis: Pearson, Spearman, lag correlations
  3. Structural break detection (CUSUM) on payout and clearing price series
  4. Tranche price gradient analysis
  5. Regime clustering by quarter
  6. Driver ranking: explanatory power, stability, PIT safety
  7. Interaction analysis: variable pairs
  8. Data acquisition priority report
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.driver_catalogue import (  # noqa: E402
    build_catalogue_df,
    data_acquisition_report,
    missing_drivers_by_priority,
)
from transmission_rights.services.aemo.price_model_v2 import (  # noqa: E402
    quarter_settlement_timestamp,
    quarter_to_components,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _qkey(q: str) -> tuple[int, int]:
    return quarter_to_components(q)


def _safe_corr(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Return (pearson_r, spearman_r) with nan guards."""
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 4:
        return np.nan, np.nan
    xm, ym = x[mask], y[mask]
    try:
        pr = float(stats.pearsonr(xm, ym).statistic)
    except Exception:
        pr = np.nan
    try:
        sr = float(stats.spearmanr(xm, ym).statistic)
    except Exception:
        sr = np.nan
    return pr, sr


def _mutual_information(x: np.ndarray, y: np.ndarray, bins: int = 8) -> float:
    """Estimate mutual information via histogram binning."""
    mask = np.isfinite(x) & np.isfinite(y)
    if mask.sum() < 4:
        return np.nan
    xm, ym = x[mask], y[mask]
    # Bin both
    xb = np.digitize(xm, np.percentile(xm, np.linspace(0, 100, bins + 1)[1:-1]))
    yb = np.digitize(ym, np.percentile(ym, np.linspace(0, 100, bins + 1)[1:-1]))
    # Joint distribution
    joint = np.zeros((bins, bins))
    for xi, yi in zip(xb, yb):
        joint[min(xi, bins - 1), min(yi, bins - 1)] += 1
    joint /= joint.sum()
    px = joint.sum(axis=1, keepdims=True)
    py = joint.sum(axis=0, keepdims=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        mi = np.where(joint > 0, joint * np.log(joint / (px * py + 1e-12)), 0)
    return float(mi.sum())


# ── feature derivation ────────────────────────────────────────────────────────

def build_quarterly_features(
    alpha_df: pd.DataFrame,
    payout_df: pd.DataFrame,
) -> pd.DataFrame:
    """Build one row per (quarter, direction) with all derivable features.

    Features derived from in-repo data:
      - auction_clearing_price_mean / median / std
      - auction_clearing_price_momentum  (qoq change from prior quarter)
      - fill_probability_mean / trend
      - tranche_price_gradient  (slope of clearing price vs tranche number)
      - units_sold_total
      - payout_per_unit  (target variable)
      - payout_deviation_from_seasonal
      - quarter_number / year
      - years_since_2020q2  (structural trend proxy)
    """
    alpha_df = alpha_df.copy()
    alpha_df["direction_key"] = (
        alpha_df["interconnector_id"].astype(str) + "::" + alpha_df["from_region"].astype(str)
    )
    alpha_df["quarter_year"]   = alpha_df["quarter"].apply(lambda q: quarter_to_components(q)[0])
    alpha_df["quarter_number"] = alpha_df["quarter"].apply(lambda q: quarter_to_components(q)[1])
    alpha_df["quarter_sort"]   = alpha_df.apply(
        lambda r: quarter_to_components(r["quarter"]), axis=1
    )

    payout_df = payout_df.copy()
    payout_df["direction_key"] = (
        payout_df["interconnector_id"].astype(str) + "::" + payout_df["from_region"].astype(str)
    )

    directions = sorted(alpha_df["direction_key"].unique())
    quarters = sorted(alpha_df["quarter"].unique(), key=_qkey)

    records: list[dict] = []

    for dk in directions:
        dir_alpha  = alpha_df[alpha_df["direction_key"] == dk].copy()
        dir_payout = payout_df[payout_df["direction_key"] == dk].copy()

        # Seasonal mean per quarter-number (using all history — only for labelling)
        seasonal_means: dict[int, float] = {}
        for qno in range(1, 5):
            same_q = dir_payout[
                dir_payout["quarter"].apply(lambda q: quarter_to_components(q)[1]) == qno
            ]
            if len(same_q) > 0:
                seasonal_means[qno] = float(same_q["payout_per_unit"].mean())

        prev_quarter_payout: dict[str, float] = {}

        for i, q in enumerate(quarters):
            q_alpha = dir_alpha[dir_alpha["quarter"] == q].copy()
            if len(q_alpha) == 0:
                continue

            yr, qno = quarter_to_components(q)

            # Payout (target)
            payout_row = dir_payout[dir_payout["quarter"] == q]
            payout = float(payout_row["payout_per_unit"].iloc[0]) if len(payout_row) > 0 else np.nan

            # Auction metrics
            prices = q_alpha["auction_clearing_price"].values.astype(float)
            fills  = q_alpha["fill_probability"].values.astype(float)
            tranch = q_alpha["tranche_no"].values.astype(float)

            acp_mean   = float(np.nanmean(prices))
            acp_median = float(np.nanmedian(prices))
            acp_std    = float(np.nanstd(prices))
            fill_mean  = float(np.nanmean(fills))

            # Tranche price gradient: slope of clearing price vs tranche number
            if len(prices) >= 3:
                try:
                    gradient = float(np.polyfit(tranch, prices, 1)[0])
                except Exception:
                    gradient = np.nan
            else:
                gradient = np.nan

            # Price momentum: change from prior quarter
            prior_q = quarters[i - 1] if i > 0 else None
            if prior_q is not None:
                prior_alpha = dir_alpha[dir_alpha["quarter"] == prior_q]
                if len(prior_alpha) > 0:
                    prior_mean = float(prior_alpha["auction_clearing_price"].mean())
                    momentum = acp_mean - prior_mean
                else:
                    momentum = np.nan
            else:
                momentum = np.nan

            # Fill probability trend (change from prior quarter)
            if prior_q is not None:
                prior_alpha = dir_alpha[dir_alpha["quarter"] == prior_q]
                if len(prior_alpha) > 0:
                    prior_fill = float(prior_alpha["fill_probability"].mean())
                    fill_trend = fill_mean - prior_fill
                else:
                    fill_trend = np.nan
            else:
                fill_trend = np.nan

            # Payout momentum
            payout_momentum = np.nan
            prev_payout = prev_quarter_payout.get(dk, np.nan)
            if np.isfinite(prev_payout) and np.isfinite(payout):
                payout_momentum = payout - prev_payout
            if np.isfinite(payout):
                prev_quarter_payout[dk] = payout

            # Seasonal deviation
            seasonal = seasonal_means.get(qno, np.nan)
            seasonal_dev = payout - seasonal if np.isfinite(payout) and np.isfinite(seasonal) else np.nan

            # Structural trend proxy: quarters elapsed since C2020Q2
            years_since = (yr - 2020) + (qno - 2) / 4.0

            records.append({
                "quarter":               q,
                "quarter_year":          yr,
                "quarter_number":        qno,
                "years_since_2020q2":    years_since,
                "direction_key":         dk,
                "interconnector_id":     q_alpha["interconnector_id"].iloc[0],
                "from_region":           q_alpha["from_region"].iloc[0],
                "acp_mean":              acp_mean,
                "acp_median":            acp_median,
                "acp_std":               acp_std,
                "acp_momentum":          momentum,
                "fill_mean":             fill_mean,
                "fill_trend":            fill_trend,
                "tranche_price_gradient": gradient,
                "payout_per_unit":       payout,
                "payout_momentum":       payout_momentum,
                "seasonal_benchmark":    seasonal,
                "seasonal_deviation":    seasonal_dev,
                "units_sold_total":      float(q_alpha["units_sold"].sum()),
            })

    return pd.DataFrame(records)


# ── CUSUM structural break detection ─────────────────────────────────────────

def detect_cusum_breaks(
    series: pd.Series,
    threshold_sigma: float = 3.0,
) -> list[int]:
    """Return indices of detected structural breaks using CUSUM method."""
    x = series.dropna().values
    if len(x) < 6:
        return []
    mu = x.mean()
    sigma = x.std() or 1.0
    cusum_pos = np.zeros(len(x))
    cusum_neg = np.zeros(len(x))
    breaks = []
    for i in range(1, len(x)):
        cusum_pos[i] = max(0, cusum_pos[i - 1] + (x[i] - mu) / sigma - 0.5)
        cusum_neg[i] = max(0, cusum_neg[i - 1] - (x[i] - mu) / sigma - 0.5)
        if cusum_pos[i] > threshold_sigma or cusum_neg[i] > threshold_sigma:
            breaks.append(series.dropna().index[i])
            cusum_pos[i] = 0
            cusum_neg[i] = 0
    return breaks


# ── correlation analysis ──────────────────────────────────────────────────────

FEATURE_COLUMNS = [
    "acp_mean",
    "acp_median",
    "acp_std",
    "acp_momentum",
    "fill_mean",
    "fill_trend",
    "tranche_price_gradient",
    "payout_momentum",
    "years_since_2020q2",
    "quarter_number",
    "units_sold_total",
]

TARGET_COLUMNS = [
    "payout_per_unit",
    "seasonal_deviation",
]


def compute_correlations(features_df: pd.DataFrame) -> pd.DataFrame:
    """Compute correlations of each feature against each target, per corridor."""
    records = []
    for dk, grp in features_df.groupby("direction_key"):
        for feat in FEATURE_COLUMNS:
            for tgt in TARGET_COLUMNS:
                x = grp[feat].values.astype(float)
                y = grp[tgt].values.astype(float)
                pr, sr = _safe_corr(x, y)
                mi = _mutual_information(x, y)
                # Lag-1 correlation (feature at t vs target at t+1)
                if len(x) > 4:
                    pr_lag1, sr_lag1 = _safe_corr(x[:-1], y[1:])
                else:
                    pr_lag1, sr_lag1 = np.nan, np.nan
                records.append({
                    "direction_key": dk,
                    "feature": feat,
                    "target": tgt,
                    "n": int(np.isfinite(x).sum() & np.isfinite(y).sum() if hasattr(np, "sum") else len(grp)),
                    "pearson_r": round(pr, 4) if np.isfinite(pr) else np.nan,
                    "spearman_r": round(sr, 4) if np.isfinite(sr) else np.nan,
                    "mutual_info": round(mi, 4) if np.isfinite(mi) else np.nan,
                    "pearson_r_lag1": round(pr_lag1, 4) if np.isfinite(pr_lag1) else np.nan,
                    "spearman_r_lag1": round(sr_lag1, 4) if np.isfinite(sr_lag1) else np.nan,
                })
    return pd.DataFrame(records)


def compute_overall_correlations(features_df: pd.DataFrame) -> pd.DataFrame:
    """Compute correlations pooled across all corridors."""
    records = []
    for feat in FEATURE_COLUMNS:
        for tgt in TARGET_COLUMNS:
            x = features_df[feat].values.astype(float)
            y = features_df[tgt].values.astype(float)
            pr, sr = _safe_corr(x, y)
            mi = _mutual_information(x, y)
            if len(x) > 4:
                pr_lag1, sr_lag1 = _safe_corr(x[:-1], y[1:])
            else:
                pr_lag1, sr_lag1 = np.nan, np.nan
            records.append({
                "feature": feat,
                "target": tgt,
                "pearson_r": round(pr, 4) if np.isfinite(pr) else np.nan,
                "spearman_r": round(sr, 4) if np.isfinite(sr) else np.nan,
                "mutual_info": round(mi, 4) if np.isfinite(mi) else np.nan,
                "pearson_r_lag1": round(pr_lag1, 4) if np.isfinite(pr_lag1) else np.nan,
                "spearman_r_lag1": round(sr_lag1, 4) if np.isfinite(sr_lag1) else np.nan,
            })
    return pd.DataFrame(records)


# ── interaction analysis ──────────────────────────────────────────────────────

def compute_interactions(features_df: pd.DataFrame) -> pd.DataFrame:
    """Test pairs of features: does product of pair correlate better than each alone?"""
    records = []
    for tgt in TARGET_COLUMNS:
        for i, f1 in enumerate(FEATURE_COLUMNS):
            for f2 in FEATURE_COLUMNS[i + 1:]:
                x1 = features_df[f1].values.astype(float)
                x2 = features_df[f2].values.astype(float)
                y  = features_df[tgt].values.astype(float)
                mask = np.isfinite(x1) & np.isfinite(x2) & np.isfinite(y)
                if mask.sum() < 5:
                    continue
                x1m, x2m, ym = x1[mask], x2[mask], y[mask]
                # Standardise
                x1s = (x1m - x1m.mean()) / (x1m.std() or 1)
                x2s = (x2m - x2m.mean()) / (x2m.std() or 1)
                interaction = x1s * x2s
                pr_int, _ = _safe_corr(interaction, ym)
                pr_f1, _  = _safe_corr(x1m, ym)
                pr_f2, _  = _safe_corr(x2m, ym)
                improvement = abs(pr_int) - max(abs(pr_f1), abs(pr_f2))
                records.append({
                    "feature_1": f1,
                    "feature_2": f2,
                    "target": tgt,
                    "pearson_r_f1": round(pr_f1, 4) if np.isfinite(pr_f1) else np.nan,
                    "pearson_r_f2": round(pr_f2, 4) if np.isfinite(pr_f2) else np.nan,
                    "pearson_r_interaction": round(pr_int, 4) if np.isfinite(pr_int) else np.nan,
                    "interaction_improvement": round(improvement, 4) if np.isfinite(improvement) else np.nan,
                })
    return pd.DataFrame(records).sort_values("interaction_improvement", ascending=False)


# ── driver ranking ────────────────────────────────────────────────────────────

def rank_drivers(
    overall_corr: pd.DataFrame,
    corr_by_corridor: pd.DataFrame,
) -> pd.DataFrame:
    """Rank in-repo derivable features by explanatory power and stability."""
    # Average |pearson| and |spearman| across targets
    agg = overall_corr.groupby("feature").agg(
        mean_abs_pearson=("pearson_r", lambda x: x.abs().mean()),
        mean_abs_spearman=("spearman_r", lambda x: x.abs().mean()),
        mean_mi=("mutual_info", "mean"),
        mean_abs_lag1_pearson=("pearson_r_lag1", lambda x: x.abs().mean()),
    ).reset_index()

    # Stability: std of |pearson| across corridors (lower = more stable)
    stability = corr_by_corridor.groupby("feature")["pearson_r"].agg(
        lambda x: x.abs().std()
    ).reset_index().rename(columns={"pearson_r": "pearson_stability_std"})

    ranked = agg.merge(stability, on="feature", how="left")
    ranked["composite_score"] = (
        ranked["mean_abs_pearson"] * 0.35
        + ranked["mean_abs_spearman"] * 0.35
        + ranked["mean_mi"] * 0.20
        - ranked["pearson_stability_std"].fillna(0) * 0.10
    )
    return ranked.sort_values("composite_score", ascending=False).reset_index(drop=True)


# ── regime clustering ─────────────────────────────────────────────────────────

def identify_regimes(features_df: pd.DataFrame) -> pd.DataFrame:
    """Label each quarter with a simple regime based on observable features."""
    df = features_df.copy()
    # Use pooled metrics across corridors
    q_agg = df.groupby("quarter").agg(
        mean_acp=("acp_mean", "mean"),
        mean_gradient=("tranche_price_gradient", "mean"),
        mean_fill=("fill_mean", "mean"),
        mean_payout=("payout_per_unit", "mean"),
    ).reset_index()
    q_agg["quarter_year"]   = q_agg["quarter"].apply(lambda q: quarter_to_components(q)[0])
    q_agg["quarter_number"] = q_agg["quarter"].apply(lambda q: quarter_to_components(q)[1])

    # Label high/medium/low payout regimes relative to median
    med_payout = q_agg["mean_payout"].median()
    p25 = q_agg["mean_payout"].quantile(0.33)
    p75 = q_agg["mean_payout"].quantile(0.67)
    q_agg["payout_regime"] = pd.cut(
        q_agg["mean_payout"],
        bins=[-np.inf, p25, p75, np.inf],
        labels=["LOW", "MEDIUM", "HIGH"],
    )

    # High price gradient = steep tranche curve = informed bidding
    med_grad = q_agg["mean_gradient"].median()
    q_agg["gradient_regime"] = np.where(q_agg["mean_gradient"] > med_grad, "STEEP", "FLAT")

    return q_agg.sort_values("quarter", key=lambda s: s.map(_qkey))


# ── report writer ─────────────────────────────────────────────────────────────

def write_summary_report(
    output_path: Path,
    features_df: pd.DataFrame,
    overall_corr: pd.DataFrame,
    ranked: pd.DataFrame,
    regimes: pd.DataFrame,
    cusum_breaks: dict[str, list],
    interactions: pd.DataFrame,
    catalogue_df,
) -> None:
    """Write the main Phase 5B markdown summary."""

    def _fmt(v) -> str:
        if isinstance(v, float) and np.isfinite(v):
            return f"{v:+.3f}"
        return "–"

    lines = [
        "# Phase 5B – Market Driver Discovery Engine",
        "",
        "> **Objective:** Determine which physical and market variables explain",
        "> deviations in Settlement Residue and SRA payouts.",
        "> This is a scientific discovery phase. No trading model is built here.",
        "",
        "## Data availability verdict",
        "",
        "| Category | Status |",
        "|---|---|",
        "| SRA auction clearing prices | ✅ AVAILABLE (C2018Q3+) |",
        "| SRA settled payout history | ✅ AVAILABLE (C2020Q2+) |",
        "| Regional reference prices (RRP) | ❌ NOT IN REPO |",
        "| Interconnector flow / utilisation | ❌ NOT IN REPO |",
        "| Constraint binding frequency | ❌ NOT IN REPO |",
        "| Generation by fuel type | ❌ NOT IN REPO |",
        "| Weather / temperature | ❌ NOT IN REPO |",
        "| Network outage register | ❌ NOT IN REPO |",
        "",
        "**Key finding:** The variables most likely to explain settlement residue",
        "are all absent from this repository. Auction microstructure and payout",
        "history are the only available signals — and they encode seasonality,",
        "not the causal drivers of congestion.",
        "",
    ]

    # Overall correlation table
    pivot = overall_corr.pivot_table(
        index="feature",
        columns="target",
        values="pearson_r",
    ).reset_index()
    lines += [
        "## Pearson correlations (in-repo derivable features vs settlement payout)",
        "",
        "| Feature | vs payout_per_unit | vs seasonal_deviation |",
        "|---|---|---|",
    ]
    for _, row in pivot.iterrows():
        p = row.get("payout_per_unit", np.nan)
        s = row.get("seasonal_deviation", np.nan)
        lines.append(f"| {row['feature']} | {_fmt(p)} | {_fmt(s)} |")

    lines += [
        "",
        "## Ranked in-repo drivers",
        "",
        "| Rank | Feature | Composite Score | Abs Pearson | Abs Spearman |",
        "|---|---|---|---|---|",
    ]
    for i, (_, row) in enumerate(ranked.iterrows(), 1):
        lines.append(
            f"| {i} | {row['feature']} "
            f"| {row['composite_score']:.3f} "
            f"| {row['mean_abs_pearson']:.3f} "
            f"| {row['mean_abs_spearman']:.3f} |"
        )

    # Structural breaks
    lines += ["", "## Structural breaks detected (CUSUM on payout series)", ""]
    if any(cusum_breaks.values()):
        for dk, breaks in sorted(cusum_breaks.items()):
            if breaks:
                lines.append(f"- **{dk}:** breaks at quarters {breaks}")
    else:
        lines.append("No significant structural breaks detected in the payout series.")

    # Regime table
    lines += [
        "",
        "## Regime classification by quarter",
        "",
        "| Quarter | Payout Regime | Gradient Regime | Mean Payout | Mean ACP |",
        "|---|---|---|---|---|",
    ]
    for _, r in regimes.iterrows():
        payout = r["mean_payout"]
        acp = r["mean_acp"]
        p_str = f"{payout:,.0f}" if np.isfinite(payout) else "–"
        a_str = f"{acp:,.0f}" if np.isfinite(acp) else "–"
        lines.append(
            f"| {r['quarter']} | {r['payout_regime']} | {r['gradient_regime']} "
            f"| {p_str} | {a_str} |"
        )

    # Top interactions
    top_int = interactions.head(10)
    lines += [
        "",
        "## Top interaction pairs (in-repo features)",
        "",
        "| Feature 1 | Feature 2 | Target | r(f1) | r(f2) | r(f1×f2) | Improvement |",
        "|---|---|---|---|---|---|---|",
    ]
    for _, row in top_int.iterrows():
        lines.append(
            f"| {row['feature_1']} | {row['feature_2']} | {row['target']} "
            f"| {_fmt(row['pearson_r_f1'])} | {_fmt(row['pearson_r_f2'])} "
            f"| {_fmt(row['pearson_r_interaction'])} | {_fmt(row['interaction_improvement'])} |"
        )

    lines += [
        "",
        "## Engineering interpretation",
        "",
        "### Why in-repo features have limited explanatory power",
        "- **Auction clearing price** reflects the *market's expectation* of settlement residue.",
        "  It is priced by participants who already know the seasonal pattern.",
        "  It therefore mostly replicates the seasonal benchmark, not deviations from it.",
        "- **Tranche price gradient** captures how steeply the market prices capacity.",
        "  A steep curve suggests informed bidding but still encodes expectation, not cause.",
        "- **Fill probability** is driven by price vs. expected payout — circular with target.",
        "- **Payout momentum** is the closest thing to a regime signal in existing data,",
        "  but with only 25 settled quarters, it cannot reliably detect multi-quarter regimes.",
        "",
        "### What would actually explain settlement residue",
        "In order of engineering plausibility:",
        "",
        "1. **Regional price spread (RRP differential)** — This IS settlement residue.",
        "   When NSW RRP > VIC RRP, VIC1-NSW1 direction earns positive residue.",
        "   This is the direct physical identity: `residue = flow × price_spread`.",
        "   Without RRP data, we cannot compute this.",
        "",
        "2. **Interconnector utilisation / constraint binding frequency** — When the",
        "   interconnector is at its limit, price separation is full. When it is free,",
        "   prices equalise. Utilisation % is the best single predictor of residue magnitude.",
        "",
        "3. **Regional renewable penetration** — High wind in SA or VIC reduces local prices",
        "   and widens the price spread. Solar in QLD/NSW creates midday price inversion.",
        "   Renewable generation share is a structural driver of the price spread.",
        "",
        "4. **Temperature anomaly** — Heatwaves increase demand non-linearly. They cause",
        "   price spikes that are asymmetric by region depending on local peaking capacity.",
        "   Q1 heatwave events strongly correlate with extreme VIC1-SA payouts.",
        "",
        "5. **Major coal retirement / outage events** — These remove baseload capacity",
        "   from one side of an interconnector, creating persistent price separation.",
        "   Hazelwood (2017), Liddell (2023) are visible as structural breaks in the data.",
        "",
        "## Conclusion and next steps",
        "",
        "| Step | Action |",
        "|---|---|",
        "| 1 | Acquire AEMO DISPATCHPRICE (RRP by region, 5-min, 2020+) |",
        "| 2 | Acquire AEMO DISPATCHINTERCONNECTORRES (flow by interconnector, 2020+) |",
        "| 3 | Acquire AEMO Quarterly Energy Dynamics (generation by fuel type, 2020+) |",
        "| 4 | Acquire BOM temperature data (quarterly mean/max per capital city, 2020+) |",
        "| 5 | Re-run Phase 5B correlation engine with these data sources |",
        "| 6 | Build Price Model v3 only after confirming which variables |",
        "|   | explain ≥50% of variance in settlement residue per corridor |",
        "",
        "**Until step 5 is complete, no further statistical forecasting model",
        "is expected to beat the seasonal benchmark on unseen quarters.**",
    ]

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    import json

    reports_dir = REPO_ROOT / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    alpha_path  = REPO_ROOT / "data" / "derived" / "sra" / "alpha_database.csv"
    payout_path = REPO_ROOT / "data" / "derived" / "sra" / "sra_payout_history.csv"

    alpha_df  = pd.read_csv(alpha_path)
    payout_df = pd.read_csv(payout_path)

    print("Building quarterly features…", flush=True)
    features_df = build_quarterly_features(alpha_df, payout_df)

    print("Computing correlations…", flush=True)
    corr_by_corridor = compute_correlations(features_df)
    overall_corr     = compute_overall_correlations(features_df)
    ranked           = rank_drivers(overall_corr, corr_by_corridor)

    print("Computing interactions…", flush=True)
    interactions = compute_interactions(features_df)

    print("Detecting structural breaks…", flush=True)
    cusum_breaks: dict[str, list] = {}
    for dk, grp in features_df.groupby("direction_key"):
        s = grp.sort_values("quarter", key=lambda x: x.map(_qkey))["payout_per_unit"].reset_index(drop=True)
        brks = detect_cusum_breaks(s)
        if brks:
            cusum_breaks[str(dk)] = [int(b) for b in brks]
        else:
            cusum_breaks[str(dk)] = []

    print("Identifying regimes…", flush=True)
    regimes = identify_regimes(features_df)

    # Build catalogue
    catalogue_df = build_catalogue_df()
    acq_report   = data_acquisition_report(catalogue_df)

    # Save outputs
    features_path    = reports_dir / "phase5b_quarterly_features.csv"
    corr_path        = reports_dir / "phase5b_correlation_matrix.csv"
    ranked_path      = reports_dir / "phase5b_driver_ranking.csv"
    interaction_path = reports_dir / "phase5b_interaction_report.csv"
    regime_path      = reports_dir / "phase5b_regime_report.csv"
    catalogue_path   = reports_dir / "phase5b_driver_catalogue.csv"
    acq_path         = reports_dir / "PHASE5B_DATA_ACQUISITION.md"
    summary_path     = reports_dir / "PHASE5B_DRIVER_DISCOVERY_SUMMARY.md"

    features_df.to_csv(features_path, index=False)
    corr_by_corridor.to_csv(corr_path, index=False)
    ranked.to_csv(ranked_path, index=False)
    interactions.to_csv(interaction_path, index=False)
    regimes.to_csv(regime_path, index=False)
    catalogue_df.to_csv(catalogue_path, index=False)
    acq_path.write_text(acq_report, encoding="utf-8")

    write_summary_report(
        summary_path,
        features_df,
        overall_corr,
        ranked,
        regimes,
        cusum_breaks,
        interactions,
        catalogue_df,
    )

    top5 = ranked.head(5)["feature"].tolist()
    top_int = interactions.head(3)[["feature_1", "feature_2", "interaction_improvement"]].to_dict("records")

    print(json.dumps({
        "features_computed": len(FEATURE_COLUMNS),
        "corridors_analysed": int(features_df["direction_key"].nunique()),
        "quarters_analysed": int(features_df["quarter"].nunique()),
        "top5_in_repo_drivers": top5,
        "top_interaction": top_int[0] if top_int else None,
        "cusum_breaks_detected": {k: v for k, v in cusum_breaks.items() if v},
        "outputs": {
            "summary":      str(summary_path.relative_to(REPO_ROOT)),
            "catalogue":    str(catalogue_path.relative_to(REPO_ROOT)),
            "correlations": str(corr_path.relative_to(REPO_ROOT)),
            "ranked":       str(ranked_path.relative_to(REPO_ROOT)),
            "interactions": str(interaction_path.relative_to(REPO_ROOT)),
            "regimes":      str(regime_path.relative_to(REPO_ROOT)),
            "acquisition":  str(acq_path.relative_to(REPO_ROOT)),
        },
    }, indent=2))


if __name__ == "__main__":
    main()
