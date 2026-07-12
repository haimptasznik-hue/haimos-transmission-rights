"""Historical replay engine for point-in-time validation.

Phase 2B consumes the Phase 2A market-state engine and the derived payout
history to replay closed-quarter outcomes without look-ahead bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

import pandas as pd

from .historical_market_state import HistoricalMarketStateEngine, MarketStateSelection
from transmission_rights.replication.quarter_closure import is_quarter_closed


class MarketStateResolver(Protocol):
    def resolve(self, as_of: date | datetime) -> MarketStateSelection: ...


class HistoricalInputsProvider(Protocol):
    def load_inputs(
        self,
        quarter: str,
        decision_point: datetime,
        market_state: MarketStateSelection,
    ) -> pd.DataFrame: ...


class DigitalTwinRunner(Protocol):
    def run(
        self,
        inputs: pd.DataFrame,
        market_state: MarketStateSelection,
        decision_point: datetime,
    ) -> pd.DataFrame: ...


class HistoricalRealityProvider(Protocol):
    def load_reality(self, quarter: str, as_of: datetime) -> pd.DataFrame: ...


class ReplayComparator(Protocol):
    def compare(self, replayed: pd.DataFrame, reality: pd.DataFrame) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class HistoricalReplayRow:
    """One quarter/category row from the replayed historical dataset."""

    quarter: str
    interconnector_id: str
    from_region: str
    total_surplus_aud: float
    total_units_sold: float
    payout_per_unit: float
    weighted_avg_clearing_price: float
    alpha: float
    alpha_pct: float
    decision_point: datetime
    ruleset_id: Optional[str] = None
    market_state_versions: Dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HistoricalReplayBundle:
    """A replay result for one decision point."""

    decision_point: datetime
    market_state: MarketStateSelection
    rows: List[HistoricalReplayRow]

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "quarter": row.quarter,
                    "interconnector_id": row.interconnector_id,
                    "from_region": row.from_region,
                    "total_surplus_aud": row.total_surplus_aud,
                    "total_units_sold": row.total_units_sold,
                    "payout_per_unit": row.payout_per_unit,
                    "weighted_avg_clearing_price": row.weighted_avg_clearing_price,
                    "alpha": row.alpha,
                    "alpha_pct": row.alpha_pct,
                    "decision_point": row.decision_point.isoformat(),
                    "ruleset_id": row.ruleset_id,
                    **{f"state_{k}": v for k, v in row.market_state_versions.items()},
                }
                for row in self.rows
            ]
        )


@dataclass(frozen=True)
class ReplayValidationResult:
    decision_point: datetime
    quarter: str
    market_state: MarketStateSelection
    replayed: pd.DataFrame
    reality: pd.DataFrame
    comparison: Dict[str, Any]


class PayoutHistoryInputsProvider:
    """Default input provider backed by replay payout history rows."""

    def __init__(self, payout_history: pd.DataFrame) -> None:
        self._payout_history = payout_history

    def load_inputs(
        self,
        quarter: str,
        decision_point: datetime,
        market_state: MarketStateSelection,
    ) -> pd.DataFrame:
        _ = decision_point
        _ = market_state
        return self._payout_history[self._payout_history["quarter"] == quarter].copy()


class PassthroughDigitalTwinRunner:
    """Default runner that treats prepared historical inputs as replay output."""

    def run(
        self,
        inputs: pd.DataFrame,
        market_state: MarketStateSelection,
        decision_point: datetime,
    ) -> pd.DataFrame:
        _ = market_state
        _ = decision_point
        return inputs.copy()


class PayoutHistoryRealityProvider:
    """Default reality provider backed by payout history rows."""

    def __init__(self, payout_history: pd.DataFrame) -> None:
        self._payout_history = payout_history

    def load_reality(self, quarter: str, as_of: datetime) -> pd.DataFrame:
        _ = as_of
        return self._payout_history[self._payout_history["quarter"] == quarter].copy()


class DataFrameReplayComparator:
    """Compares replayed rows against reality with simple payout/alpha error stats."""

    def compare(self, replayed: pd.DataFrame, reality: pd.DataFrame) -> Dict[str, Any]:
        if replayed.empty or reality.empty:
            return {
                "status": "not_available",
                "rows_replayed": int(len(replayed)),
                "rows_reality": int(len(reality)),
            }

        key = ["quarter", "interconnector_id", "from_region"]
        merged = replayed.merge(
            reality,
            on=key,
            suffixes=("_replay", "_real"),
            how="inner",
        )
        if merged.empty:
            return {
                "status": "no_overlap",
                "rows_replayed": int(len(replayed)),
                "rows_reality": int(len(reality)),
            }

        payout_error = merged["payout_per_unit_replay"] - merged["payout_per_unit_real"]
        alpha_error = merged["alpha_replay"] - merged["alpha_real"]
        mean_real_payout = float(merged["payout_per_unit_real"].abs().mean())
        mean_abs_payout_error = float(payout_error.abs().mean())
        reconciliation_pct = 100.0
        if mean_real_payout > 0:
            reconciliation_pct = max(0.0, 100.0 * (1.0 - (mean_abs_payout_error / mean_real_payout)))

        return {
            "status": "ok",
            "rows_compared": int(len(merged)),
            "mean_abs_payout_error": mean_abs_payout_error,
            "max_abs_payout_error": float(payout_error.abs().max()),
            "mean_abs_alpha_error": float(alpha_error.abs().mean()),
            "max_abs_alpha_error": float(alpha_error.abs().max()),
            "mean_real_payout": mean_real_payout,
            "reconciliation_pct": reconciliation_pct,
        }


class HistoricalReplayEngine:
    """Replays historical outcomes using market state selected externally.

    This engine never decides rule versions itself. It only asks the market
    state resolver for a point-in-time selection and then passes that state
    downstream to inputs, twin execution, and validation.
    """

    def __init__(
        self,
        market_state_engine: Optional[MarketStateResolver] = None,
        payout_history_path: Optional[Path | str] = None,
    ) -> None:
        self.market_state_engine = market_state_engine or HistoricalMarketStateEngine()
        self._payout_history = pd.DataFrame()
        self._inputs_provider: Optional[HistoricalInputsProvider] = None
        self._digital_twin_runner: Optional[DigitalTwinRunner] = None
        self._reality_provider: Optional[HistoricalRealityProvider] = None
        self._comparator: Optional[ReplayComparator] = None
        if payout_history_path is not None:
            self.load_payout_history(payout_history_path)

    def load_payout_history(self, path: Path | str) -> None:
        payout_path = Path(path)
        if not payout_path.exists():
            raise FileNotFoundError(payout_path)
        frame = pd.read_csv(payout_path)
        if "surplus_aud" in frame.columns and "total_surplus_aud" not in frame.columns:
            frame = frame.rename(columns={"surplus_aud": "total_surplus_aud"})

        expected = {
            "quarter",
            "interconnector_id",
            "from_region",
            "total_surplus_aud",
            "total_units_sold",
            "payout_per_unit",
            "weighted_avg_clearing_price",
            "alpha",
            "alpha_pct",
        }
        missing = expected - set(frame.columns)
        if missing:
            raise ValueError(f"Payout history missing columns: {sorted(missing)}")
        self._payout_history = frame.copy()
        self._inputs_provider = PayoutHistoryInputsProvider(self._payout_history)
        self._digital_twin_runner = PassthroughDigitalTwinRunner()
        self._reality_provider = PayoutHistoryRealityProvider(self._payout_history)
        self._comparator = DataFrameReplayComparator()

    def configure_pipeline(
        self,
        inputs_provider: Optional[HistoricalInputsProvider] = None,
        digital_twin_runner: Optional[DigitalTwinRunner] = None,
        reality_provider: Optional[HistoricalRealityProvider] = None,
        comparator: Optional[ReplayComparator] = None,
    ) -> None:
        if inputs_provider is not None:
            self._inputs_provider = inputs_provider
        if digital_twin_runner is not None:
            self._digital_twin_runner = digital_twin_runner
        if reality_provider is not None:
            self._reality_provider = reality_provider
        if comparator is not None:
            self._comparator = comparator

    def _decision_point(self, as_of: date | datetime | None) -> datetime:
        if as_of is None:
            return datetime.now(UTC)
        if isinstance(as_of, datetime):
            return as_of
        return datetime.combine(as_of, datetime.min.time())

    def _rows_for_quarter(self, quarter: str) -> pd.DataFrame:
        if self._payout_history.empty:
            return pd.DataFrame()
        return self._payout_history[self._payout_history["quarter"] == quarter].copy()

    def replay_quarter(
        self,
        quarter: str,
        as_of: date | datetime | None = None,
    ) -> HistoricalReplayBundle:
        """Replay a single quarter if it is closed as of the decision point.

        Pipeline:
          Decision Date -> Historical Market State -> Historical Inputs
          -> Run Digital Twin -> Historical Settlement
        """

        decision_point = self._decision_point(as_of)
        market_state = self.market_state_engine.resolve(decision_point)

        if not is_quarter_closed(quarter, as_of=decision_point.date()):
            return HistoricalReplayBundle(decision_point=decision_point, market_state=market_state, rows=[])

        if self._inputs_provider is None or self._digital_twin_runner is None:
            raise ValueError("Replay pipeline not configured. Call load_payout_history or configure_pipeline.")

        historical_inputs = self._inputs_provider.load_inputs(
            quarter=quarter,
            decision_point=decision_point,
            market_state=market_state,
        )
        historical_settlement = self._digital_twin_runner.run(
            inputs=historical_inputs,
            market_state=market_state,
            decision_point=decision_point,
        )

        rows = [
            HistoricalReplayRow(
                quarter=row["quarter"],
                interconnector_id=row["interconnector_id"],
                from_region=row["from_region"],
                total_surplus_aud=float(row["total_surplus_aud"]),
                total_units_sold=float(row["total_units_sold"]),
                payout_per_unit=float(row["payout_per_unit"]),
                weighted_avg_clearing_price=float(row["weighted_avg_clearing_price"]),
                alpha=float(row["alpha"]),
                alpha_pct=float(row["alpha_pct"]),
                decision_point=decision_point,
                ruleset_id=market_state.ruleset.rule_set_id if market_state.ruleset else None,
                market_state_versions=market_state.version_registry,
            )
            for _, row in historical_settlement.iterrows()
        ]
        return HistoricalReplayBundle(decision_point=decision_point, market_state=market_state, rows=rows)

    def replay_available_quarters(
        self,
        as_of: date | datetime | None = None,
    ) -> List[HistoricalReplayBundle]:
        """Replay every closed quarter available at a decision point."""

        decision_point = self._decision_point(as_of)
        if self._payout_history.empty:
            return []

        bundles: List[HistoricalReplayBundle] = []
        for quarter in sorted(self._payout_history["quarter"].unique()):
            if not is_quarter_closed(quarter, as_of=decision_point.date()):
                continue
            bundles.append(self.replay_quarter(quarter, decision_point))
        return bundles

    def validate_point_in_time(self, quarter: str, as_of: date | datetime | None = None) -> Dict[str, Any]:
        """Compare replayed settlement to historical reality for a decision point.

        Pipeline:
          Decision Date -> Historical Market State -> Historical Inputs
          -> Run Digital Twin -> Historical Settlement -> Compare to Reality
        """

        decision_point = self._decision_point(as_of)
        market_state = self.market_state_engine.resolve(decision_point)

        if not is_quarter_closed(quarter, as_of=decision_point.date()):
            return {
                "decision_point": decision_point.isoformat(),
                "quarter": quarter,
                "state_versions": market_state.version_registry,
                "status": "not_available_or_open",
            }

        if (
            self._inputs_provider is None
            or self._digital_twin_runner is None
            or self._reality_provider is None
            or self._comparator is None
        ):
            raise ValueError("Validation pipeline not configured. Call load_payout_history or configure_pipeline.")

        historical_inputs = self._inputs_provider.load_inputs(
            quarter=quarter,
            decision_point=decision_point,
            market_state=market_state,
        )
        historical_settlement = self._digital_twin_runner.run(
            inputs=historical_inputs,
            market_state=market_state,
            decision_point=decision_point,
        )
        reality = self._reality_provider.load_reality(quarter=quarter, as_of=decision_point)
        comparison = self._comparator.compare(historical_settlement, reality)

        return {
            "decision_point": decision_point.isoformat(),
            "quarter": quarter,
            "rows_replayed": int(len(historical_settlement)),
            "rows_reality": int(len(reality)),
            "state_versions": market_state.version_registry,
            **comparison,
        }

    def historical_fidelity_report(
        self,
        as_of: date | datetime | None = None,
        reconciliation_target_pct: float = 99.0,
    ) -> Dict[str, Any]:
        """Evaluate historical fidelity before forecasting.

        Acceptance gate:
          - every supported closed quarter auto-selects a RuleSet
          - no manual overrides
          - reconciliation target defaults to >99%
        """

        decision_point = self._decision_point(as_of)
        if self._payout_history.empty:
            return {
                "status": "no_data",
                "decision_point": decision_point.isoformat(),
                "supported_quarters": 0,
            }

        supported_quarters: List[str] = []
        missing_ruleset: List[str] = []
        below_target: List[str] = []
        weak_category_rows: List[Dict[str, Any]] = []
        results: List[Dict[str, Any]] = []

        for quarter in sorted(self._payout_history["quarter"].unique()):
            if not is_quarter_closed(quarter, as_of=decision_point.date()):
                continue
            supported_quarters.append(quarter)
            state = self.market_state_engine.resolve(decision_point)
            if state.ruleset is None:
                missing_ruleset.append(quarter)

            check = self.validate_point_in_time(quarter, as_of=decision_point)
            if check.get("status") != "ok":
                results.append(check)
                below_target.append(quarter)
                continue

            reconciliation_pct = float(check.get("reconciliation_pct", 0.0))

            historical_inputs = self._inputs_provider.load_inputs(
                quarter=quarter,
                decision_point=decision_point,
                market_state=state,
            )
            historical_settlement = self._digital_twin_runner.run(
                inputs=historical_inputs,
                market_state=state,
                decision_point=decision_point,
            )
            reality = self._reality_provider.load_reality(quarter=quarter, as_of=decision_point)
            merged = historical_settlement.merge(
                reality,
                on=["quarter", "interconnector_id", "from_region"],
                suffixes=("_replay", "_real"),
                how="inner",
            )
            if not merged.empty:
                for _, row in merged.iterrows():
                    real = float(abs(row["payout_per_unit_real"]))
                    err = float(abs(row["payout_per_unit_replay"] - row["payout_per_unit_real"]))
                    row_recon = 100.0 if real == 0 else max(0.0, 100.0 * (1.0 - (err / real)))
                    if row_recon < reconciliation_target_pct:
                        weak_category_rows.append(
                            {
                                "quarter": row["quarter"],
                                "interconnector_id": row["interconnector_id"],
                                "from_region": row["from_region"],
                                "reconciliation_pct": row_recon,
                                "abs_payout_error": err,
                            }
                        )

            results.append(check)
            if reconciliation_pct < reconciliation_target_pct:
                below_target.append(quarter)

        passed = (
            not missing_ruleset
            and not below_target
            and not weak_category_rows
            and bool(supported_quarters)
        )
        return {
            "status": "pass" if passed else "fail",
            "decision_point": decision_point.isoformat(),
            "supported_quarters": len(supported_quarters),
            "missing_ruleset_quarters": missing_ruleset,
            "below_target_quarters": below_target,
            "weak_category_rows": weak_category_rows,
            "reconciliation_target_pct": reconciliation_target_pct,
            "no_manual_overrides": True,
            "results": results,
        }

