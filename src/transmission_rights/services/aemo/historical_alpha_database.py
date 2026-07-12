"""Phase C alpha database builder.

For each historical auction this module runs the point-in-time chain:

Decision Date
-> Historical Market State
-> Historical Inputs
-> Forecast assumptions
-> Run Digital Twin
-> Fair value
-> Compare to auction clearing + final realised payout

The Historical Fidelity gate must pass before alpha records are built.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Dict, List, Optional, Protocol

import pandas as pd

from .historical_market_state import HistoricalMarketStateEngine, MarketStateSelection
from .historical_replay import HistoricalReplayEngine


class ForecastAssumptionsEngine(Protocol):
    def forecast_payout_per_unit(
        self,
        auction_row: pd.Series,
        known_auctions: pd.DataFrame,
        market_state: MarketStateSelection,
    ) -> float: ...


class ForecastDigitalTwin(Protocol):
    def fair_value(
        self,
        forecast_payout_per_unit: float,
        auction_row: pd.Series,
        market_state: MarketStateSelection,
    ) -> float: ...


class HistoricalClearingTrendAssumptions:
    """Simple no-lookahead assumptions based only on known historical clears."""

    def forecast_payout_per_unit(
        self,
        auction_row: pd.Series,
        known_auctions: pd.DataFrame,
        market_state: MarketStateSelection,
    ) -> float:
        _ = market_state
        same_quarter = known_auctions[
            (known_auctions["quarter"] == auction_row["quarter"])
            & (known_auctions["interconnector_id"] == auction_row["interconnector_id"])
            & (known_auctions["from_region"] == auction_row["from_region"])
            & (known_auctions["tranche_no"] < auction_row["tranche_no"])
        ]
        if not same_quarter.empty:
            return float(same_quarter["clearing_price"].median())

        same_category = known_auctions[
            (known_auctions["interconnector_id"] == auction_row["interconnector_id"])
            & (known_auctions["from_region"] == auction_row["from_region"])
        ]
        if not same_category.empty:
            return float(same_category["clearing_price"].median())

        return float(auction_row["clearing_price"])


class NeutralFairValueTwin:
    """Default fair-value twin that maps forecast payout directly to fair value."""

    def fair_value(
        self,
        forecast_payout_per_unit: float,
        auction_row: pd.Series,
        market_state: MarketStateSelection,
    ) -> float:
        _ = auction_row
        _ = market_state
        return float(forecast_payout_per_unit)


@dataclass(frozen=True)
class AlphaDatabaseBuildResult:
    rows_written: int
    output_path: Path
    fidelity_report: Dict[str, object]


class HistoricalAlphaDatabaseBuilder:
    def __init__(
        self,
        market_state_engine: HistoricalMarketStateEngine,
        replay_engine: HistoricalReplayEngine,
        auction_results_path: Path | str,
        payout_history_path: Path | str,
        assumptions_engine: Optional[ForecastAssumptionsEngine] = None,
        digital_twin: Optional[ForecastDigitalTwin] = None,
    ) -> None:
        self.market_state_engine = market_state_engine
        self.replay_engine = replay_engine
        self.auction_results_path = Path(auction_results_path)
        self.payout_history_path = Path(payout_history_path)
        self.assumptions_engine = assumptions_engine or HistoricalClearingTrendAssumptions()
        self.digital_twin = digital_twin or NeutralFairValueTwin()

    @staticmethod
    def _decision_point_from_month(value: str) -> datetime:
        return datetime.strptime(f"{value}-01", "%Y-%m-%d").replace(tzinfo=UTC)

    @staticmethod
    def _product_id(auction: pd.Series) -> str:
        return (
            f"{auction['quarter']}:{auction['interconnector_id']}:{auction['from_region']}:"
            f"{auction['tranche']}"
        )

    @staticmethod
    def _confidence_band(expected_alpha: float) -> str:
        if expected_alpha >= 2000:
            return "high"
        if expected_alpha >= 500:
            return "medium"
        if expected_alpha > 0:
            return "low"
        return "negative"

    def _load_auction_results(self) -> pd.DataFrame:
        frame = pd.read_csv(self.auction_results_path)
        frame = frame.copy()
        frame["tranche_no"] = frame["tranche"].astype(str).str.replace("T", "", regex=False).astype(int)
        frame["decision_point"] = frame["mmsdm_month"].astype(str).map(self._decision_point_from_month)
        return frame.sort_values(
            ["decision_point", "quarter", "tranche_no", "interconnector_id", "from_region"]
        ).reset_index(drop=True)

    def _load_realised_payout(self) -> pd.DataFrame:
        frame = pd.read_csv(self.payout_history_path)
        if "surplus_aud" in frame.columns and "total_surplus_aud" not in frame.columns:
            frame = frame.rename(columns={"surplus_aud": "total_surplus_aud"})
        return frame[["quarter", "interconnector_id", "from_region", "payout_per_unit"]].rename(
            columns={"payout_per_unit": "final_realised_payout_per_unit"}
        )

    def build(
        self,
        output_path: Path | str,
        fidelity_as_of: datetime,
        fidelity_target_pct: float = 99.0,
    ) -> AlphaDatabaseBuildResult:
        fidelity_report = self.replay_engine.historical_fidelity_report(
            as_of=fidelity_as_of,
            reconciliation_target_pct=fidelity_target_pct,
        )
        if fidelity_report.get("status") != "pass":
            raise ValueError(f"Historical Fidelity gate failed: {fidelity_report}")

        auctions = self._load_auction_results()
        realised = self._load_realised_payout()
        auctions = auctions.merge(
            realised,
            on=["quarter", "interconnector_id", "from_region"],
            how="left",
        )

        known_auctions = pd.DataFrame(columns=auctions.columns)
        rows: List[Dict[str, object]] = []
        for _, auction in auctions.iterrows():
            decision_point = auction["decision_point"]
            market_state = self.market_state_engine.resolve(decision_point)

            forecast_payout = self.assumptions_engine.forecast_payout_per_unit(
                auction_row=auction,
                known_auctions=known_auctions,
                market_state=market_state,
            )
            fair_value = self.digital_twin.fair_value(
                forecast_payout_per_unit=forecast_payout,
                auction_row=auction,
                market_state=market_state,
            )

            clearing_price = float(auction["clearing_price"])
            final_payout = (
                float(auction["final_realised_payout_per_unit"])
                if pd.notna(auction["final_realised_payout_per_unit"])
                else None
            )
            forecast_error_to_realised = (
                (fair_value - final_payout) if final_payout is not None else None
            )
            realised_alpha = (
                (final_payout - clearing_price) if final_payout is not None else None
            )

            rows.append(
                {
                    "decision_timestamp": decision_point.isoformat(),
                    "information_cutoff": decision_point.isoformat(),
                    "source_timestamp_max": decision_point.isoformat(),
                    "contract_id": auction["contract_id"],
                    "product_id": self._product_id(auction),
                    "quarter": auction["quarter"],
                    "tranche": auction["tranche"],
                    "tranche_no": int(auction["tranche_no"]),
                    "interconnector_id": auction["interconnector_id"],
                    "from_region": auction["from_region"],
                    "ruleset_id": market_state.ruleset.rule_set_id if market_state.ruleset else None,
                    "units_offered": int(auction["units_offered"]),
                    "units_sold": int(auction["units_sold"]),
                    "fill_probability": (
                        float(auction["units_sold"]) / float(auction["units_offered"])
                        if float(auction["units_offered"]) > 0
                        else 0.0
                    ),
                    "fair_value_forecast": fair_value,
                    "auction_clearing_price": clearing_price,
                    "final_realised_payout_per_unit": final_payout,
                    "expected_alpha": fair_value - clearing_price,
                    "confidence_band": self._confidence_band(fair_value - clearing_price),
                    "forecast_error_to_clearing": fair_value - clearing_price,
                    "forecast_error_to_realised": forecast_error_to_realised,
                    "realised_alpha": realised_alpha,
                    "source_lineage": json.dumps(
                        {
                            "auction_source": str(self.auction_results_path),
                            "payout_source": str(self.payout_history_path),
                            "auction_table": "MMSDM.RESIDUE_PUBLIC_DATA",
                            "settlement_source": "SETIRSURPLUS (closed quarters)",
                            "ruleset_id": (
                                market_state.ruleset.rule_set_id
                                if market_state.ruleset is not None
                                else None
                            ),
                        },
                        sort_keys=True,
                    ),
                }
            )

            known_auctions = pd.concat([known_auctions, pd.DataFrame([auction])], ignore_index=True)

        out = pd.DataFrame(rows)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output, index=False)
        return AlphaDatabaseBuildResult(
            rows_written=len(out),
            output_path=output,
            fidelity_report=fidelity_report,
        )
