"""
Fill-rate-based fair value model for SRA products.

Uses demand intensity (fill rate) as the primary driver of fair value.
Correlates 0.74 with historical clearing prices.
"""

import numpy as np
from dataclasses import dataclass


@dataclass
class FillRateFairValueResult:
    """Fair value estimate based on fill rate."""

    fair_value: float
    confidence: float  # 0-1, higher = more confident
    fill_rate_signal: float  # [-1, 1]
    volume_signal: float  # [-1, 1]
    model_notes: str


class FillRateFairValueEngine:
    """
    Fair value model driven by demand intensity (fill rate).

    Strategy:
    - Keep fair value anchored to the current market price scale
    - Tilt fair value up/down based on fill-rate demand signal
    - Apply a smaller liquidity adjustment based on offered volume
    """

    FILL_RATE_CORRELATION = 0.74

    def estimate_fair_value(
        self,
        market_price: float,
        fill_rate: float,
        units_offered: int,
        fill_rate_percentile: float,
        volume_percentile: float,
        interconnector_volatility: float = 0.28,  # avg from data
    ) -> FillRateFairValueResult:
        """Estimate fair value based on fill rate and market context.

        Args:
            market_price: Current clearing/market price.
            fill_rate: Units sold / units offered (can be > 1.0).
            units_offered: Total units in auction.
            fill_rate_percentile: 0-100, where 100 = highest demand across history.
            volume_percentile: 0-100, where 100 = highest volume.
            interconnector_volatility: Std dev of prices for this interconnector.

        Returns:
            FillRateFairValueResult with fair value and confidence.
        """

        # Signal 1: Fill rate percentile (primary driver)
        # -1 = very low demand, 0 = median, 1 = very high demand
        fill_rate_signal = (fill_rate_percentile - 50.0) / 50.0
        fill_rate_signal = np.clip(fill_rate_signal, -1.0, 1.0)

        # Signal 2: Volume percentile (liquidity adjustment)
        # -1 = illiquid, 0 = median, 1 = very liquid
        volume_signal = (volume_percentile - 50.0) / 50.0
        volume_signal = np.clip(volume_signal, -1.0, 1.0)

        demand_adjustment_pct = 0.20 * fill_rate_signal
        liquidity_adjustment_pct = 0.05 * volume_signal
        total_adjustment_pct = demand_adjustment_pct + liquidity_adjustment_pct

        fair_value = market_price * (1.0 + total_adjustment_pct)
        fair_value = float(np.clip(fair_value, market_price * 0.60, market_price * 1.60))

        # Confidence calculation
        # Higher when: signal is strong and data is liquid
        signal_strength = abs(fill_rate_signal)
        volume_confidence = max(0.5, 0.5 + 0.5 * volume_signal)
        market_price_quality = 1.0 if market_price > 0 else 0.0

        confidence = (
            (self.FILL_RATE_CORRELATION * signal_strength)
            + (0.15 * volume_confidence)
            + (0.10 * market_price_quality)
        )
        confidence = np.clip(confidence, 0.0, 1.0)

        notes = (
            f"fill_signal={fill_rate_signal:.2f}, "
            f"volume_signal={volume_signal:.2f}, "
            f"demand_adj_pct={demand_adjustment_pct:.3f}, "
            f"liquidity_adj_pct={liquidity_adjustment_pct:.3f}"
        )

        return FillRateFairValueResult(
            fair_value=round(fair_value, 2),
            confidence=round(confidence, 3),
            fill_rate_signal=round(fill_rate_signal, 2),
            volume_signal=round(volume_signal, 2),
            model_notes=notes,
        )

    def get_recommendation(
        self, fair_value: float, market_price: float, confidence: float
    ) -> tuple[str, str]:
        """Generate recommendation based on fair value vs market price.

        Args:
            fair_value: Estimated fair value.
            market_price: Current market price.
            confidence: Model confidence (0-1).

        Returns:
            (recommendation label, reason)
        """

        spread_pct = ((fair_value - market_price) / market_price * 100) if market_price > 0 else 0

        # Thresholds scale with confidence
        # Higher confidence → tighter thresholds
        buy_threshold = 12.0 * (1.0 - confidence * 0.5)  # 12% at low conf, 6% at high conf
        hold_threshold = 4.0 * (1.0 - confidence * 0.3)  # 4% at low conf, 2.8% at high conf
        avoid_threshold = -4.0 * (1.0 - confidence * 0.3)

        if spread_pct >= buy_threshold:
            return (
                "BUY",
                f"Strong undervalue ({spread_pct:.1f}% below fair value at {confidence:.0%} conf)",
            )
        elif spread_pct >= hold_threshold:
            return (
                "HOLD",
                f"Slight undervalue ({spread_pct:.1f}% below fair value)",
            )
        elif spread_pct <= avoid_threshold:
            return (
                "AVOID",
                f"Overvalued ({abs(spread_pct):.1f}% above fair value)",
            )
        else:
            return (
                "WATCH",
                f"Fair value close to market ({spread_pct:.1f}% spread)",
            )
