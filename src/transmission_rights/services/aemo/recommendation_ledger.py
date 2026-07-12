"""
Recommendation ledger and tracking for SRA products.

Persists every recommendation call with market state, fair value, and signal strength.
Enables forward-looking alpha validation and calibration analysis.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd


@dataclass
class RecommendationRecord:
    """A single recommendation event with full market context."""

    timestamp: str  # ISO format
    product_id: str  # interconnector e.g. "NSW1-QLD1"
    quarter: str  # e.g. "C2025Q3"
    tranche: int

    # Market state
    market_price_aud: float
    units_offered: int
    units_sold: int
    fill_rate: float  # units_sold / units_offered

    # Fair value model
    fair_value_aud: float
    fair_value_model: str  # e.g. "fill_rate_based_v1"
    fill_rate_percentile: float  # 0-100, where 100 = highest demand
    volume_percentile: float  # 0-100, where 100 = highest volume

    # Recommendation
    recommendation: str  # BUY, HOLD, AVOID, WATCH
    confidence: float  # 0-1 based on signal strength
    spread_aud: float  # fair_value - market_price
    spread_pct: float  # (fair_value - market_price) / market_price * 100

    # Model inputs
    fill_rate_signal: float  # [-1, 1] where 1 = high demand, -1 = low demand
    volume_signal: float  # [-1, 1] where 1 = high liquidity, -1 = low

    # Forward outcome (populated later)
    realized_price_24h: Optional[float] = None
    realized_price_7d: Optional[float] = None
    realized_price_quarter_end: Optional[float] = None
    markout_24h_pct: Optional[float] = None
    markout_7d_pct: Optional[float] = None
    recommendation_correct_24h: Optional[bool] = None
    recommendation_correct_7d: Optional[bool] = None

    def to_dict(self) -> dict:
        """Serialize to dictionary for JSON."""
        return asdict(self)


class RecommendationLedger:
    """Persistent ledger of all recommendations."""

    def __init__(self, ledger_dir: Path):
        """Initialize ledger manager.

        Args:
            ledger_dir: Directory to store ledger CSVs and indexes.
        """
        self.ledger_dir = Path(ledger_dir)
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.ledger_path = self.ledger_dir / "recommendation_ledger.csv"
        self.index_path = self.ledger_dir / "recommendation_index.json"

    def append_recommendation(self, record: RecommendationRecord) -> None:
        """Log a new recommendation to the ledger.

        Args:
            record: RecommendationRecord to log.
        """
        # Convert to DataFrame for easy append
        df = pd.DataFrame([record.to_dict()])

        if self.ledger_path.exists():
            existing = pd.read_csv(self.ledger_path)
            df = pd.concat([existing, df], ignore_index=True)

        df.to_csv(self.ledger_path, index=False)

    def load_ledger(self) -> pd.DataFrame:
        """Load all recommendations from ledger.

        Returns:
            DataFrame with all recommendation records.
        """
        if self.ledger_path.exists():
            return pd.read_csv(self.ledger_path)
        return pd.DataFrame()

    def get_recommendations_by_product(
        self, product_id: str, quarter: Optional[str] = None
    ) -> pd.DataFrame:
        """Retrieve recommendations for a specific product.

        Args:
            product_id: Product interconnector ID.
            quarter: Optional quarter filter.

        Returns:
            Filtered DataFrame.
        """
        df = self.load_ledger()
        df = df[df["product_id"] == product_id]
        if quarter:
            df = df[df["quarter"] == quarter]
        return df

    def compute_hit_rate(self) -> dict:
        """Compute recommendation accuracy metrics.

        Returns:
            Dictionary with hit rate, calibration, and performance by bucket.
        """
        df = self.load_ledger()
        if df.empty or "recommendation_correct_24h" not in df.columns:
            return {
                "status": "insufficient_data",
                "message": "No forward outcomes recorded yet",
            }

        # Overall hit rate
        valid_24h = df[df["recommendation_correct_24h"].notna()]
        hit_rate_24h = (
            valid_24h["recommendation_correct_24h"].mean()
            if len(valid_24h) > 0
            else 0
        )

        valid_7d = df[df["recommendation_correct_7d"].notna()]
        hit_rate_7d = (
            valid_7d["recommendation_correct_7d"].mean()
            if len(valid_7d) > 0
            else 0
        )

        # By recommendation bucket
        by_rec = {}
        for rec in ["BUY", "HOLD", "AVOID", "WATCH"]:
            subset = df[df["recommendation"] == rec]
            if len(subset) > 0:
                valid_subset = subset[subset["recommendation_correct_24h"].notna()]
                hit_rate = (
                    valid_subset["recommendation_correct_24h"].mean()
                    if len(valid_subset) > 0
                    else 0
                )
                by_rec[rec] = {
                    "count": len(subset),
                    "hit_rate_24h": round(hit_rate, 3),
                    "avg_confidence": round(subset["confidence"].mean(), 3),
                    "avg_spread_pct": round(subset["spread_pct"].mean(), 2),
                }

        # Calibration: group by confidence bins and check actual hit rate
        calibration = {}
        for conf_bin in [0.6, 0.7, 0.8, 0.9]:
            bin_start = conf_bin - 0.05
            bin_end = conf_bin + 0.05
            subset = df[(df["confidence"] >= bin_start) & (df["confidence"] < bin_end)]
            if len(subset) > 0:
                valid_subset = subset[subset["recommendation_correct_24h"].notna()]
                actual_hit = (
                    valid_subset["recommendation_correct_24h"].mean()
                    if len(valid_subset) > 0
                    else 0
                )
                calibration[f"{conf_bin:.0%}"] = {
                    "claimed_confidence": round(conf_bin, 2),
                    "actual_hit_rate": round(actual_hit, 3),
                    "count": len(subset),
                }

        return {
            "total_recommendations": len(df),
            "hit_rate_24h": round(hit_rate_24h, 3),
            "hit_rate_7d": round(hit_rate_7d, 3),
            "by_recommendation": by_rec,
            "calibration": calibration,
        }

    def compute_average_markout(self) -> dict:
        """Compute realized returns by recommendation bucket.

        Returns:
            Dictionary with average markout by bucket.
        """
        df = self.load_ledger()
        if df.empty or "markout_24h_pct" not in df.columns:
            return {"status": "insufficient_data"}

        result = {}
        for rec in ["BUY", "HOLD", "AVOID", "WATCH"]:
            subset = df[df["recommendation"] == rec]
            if len(subset) > 0:
                valid_24h = subset[subset["markout_24h_pct"].notna()]
                if len(valid_24h) > 0:
                    result[rec] = {
                        "count": len(subset),
                        "avg_markout_24h_pct": round(
                            valid_24h["markout_24h_pct"].mean(), 2
                        ),
                        "std_markout_24h_pct": round(
                            valid_24h["markout_24h_pct"].std(), 2
                        ),
                    }

        return result

    def compute_vs_baseline(self) -> dict:
        """Compare recommendation strategy against simple baselines.

        Baselines:
          - Naive: buy all high-fill products
          - Market: hold (no trade)
          - Simple threshold: buy if fill_rate > 80th percentile

        Returns:
            Dictionary with strategy performance vs baselines.
        """
        df = self.load_ledger()
        if df.empty or "markout_24h_pct" not in df.columns:
            return {"status": "insufficient_data"}

        # Strategy performance
        valid = df[df["markout_24h_pct"].notna()]
        strategy_pnl = valid["markout_24h_pct"].mean()
        strategy_hit_rate = (valid["recommendation_correct_24h"]).mean()

        # Baseline 1: buy all high-fill-rate products
        high_fill = df[df["fill_rate_percentile"] > 80]
        baseline_high_fill_pnl = (
            high_fill[high_fill["markout_24h_pct"].notna()]["markout_24h_pct"].mean()
            if len(high_fill) > 0
            else 0
        )

        # Baseline 2: market (no trade)
        baseline_market_pnl = 0

        return {
            "strategy_pnl_24h_pct": round(strategy_pnl, 2),
            "strategy_hit_rate": round(strategy_hit_rate, 3),
            "baseline_high_fill_pnl_24h_pct": round(baseline_high_fill_pnl, 2),
            "baseline_market_pnl_24h_pct": baseline_market_pnl,
            "strategy_vs_baseline_pnl": round(strategy_pnl - baseline_high_fill_pnl, 2),
        }
