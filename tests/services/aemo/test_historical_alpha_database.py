from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys

import pandas as pd


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.historical_alpha_database import HistoricalAlphaDatabaseBuilder  # noqa: E402
from transmission_rights.services.aemo.historical_market_state import (  # noqa: E402
    HistoricalMarketStateEngine,
    RuleSet,
)
from transmission_rights.services.aemo.historical_replay import HistoricalReplayEngine  # noqa: E402


def _write_minimal_inputs(tmp_path: Path) -> tuple[Path, Path]:
    payout = pd.DataFrame(
        [
            {
                "quarter": "C2025Q3",
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "total_surplus_aud": 1000.0,
                "total_units_sold": 100.0,
                "payout_per_unit": 10.0,
                "weighted_avg_clearing_price": 8.0,
                "alpha": 2.0,
                "alpha_pct": 25.0,
            }
        ]
    )
    payout_path = tmp_path / "payout.csv"
    payout.to_csv(payout_path, index=False)

    auctions = pd.DataFrame(
        [
            {
                "contract_id": "C2025Q3T01",
                "interconnector_id": "NSW1-QLD1",
                "from_region": "NSW1",
                "mmsdm_month": "2026-01",
                "quarter": "C2025Q3",
                "tranche": "T01",
                "version_no": 1,
                "units_offered": 100,
                "units_sold": 100,
                "clearing_price": 8.0,
                "reserve_price": 0.0,
            }
        ]
    )
    auctions_path = tmp_path / "auctions.csv"
    auctions.to_csv(auctions_path, index=False)
    return auctions_path, payout_path


def test_alpha_builder_requires_fidelity_gate(tmp_path: Path):
    auctions_path, payout_path = _write_minimal_inputs(tmp_path)

    market_state = HistoricalMarketStateEngine()
    replay = HistoricalReplayEngine(market_state_engine=market_state, payout_history_path=payout_path)
    builder = HistoricalAlphaDatabaseBuilder(
        market_state_engine=market_state,
        replay_engine=replay,
        auction_results_path=auctions_path,
        payout_history_path=payout_path,
    )

    try:
        builder.build(
            output_path=tmp_path / "alpha.csv",
            fidelity_as_of=datetime(2026, 7, 12),
            fidelity_target_pct=99.0,
        )
    except ValueError as exc:
        assert "Historical Fidelity gate failed" in str(exc)
    else:
        raise AssertionError("Expected fidelity gate failure when no RuleSet exists")


def test_alpha_builder_records_ruleset_id(tmp_path: Path):
    auctions_path, payout_path = _write_minimal_inputs(tmp_path)

    market_state = HistoricalMarketStateEngine()
    market_state.register_ruleset(
        RuleSet(
            rule_set_id="RS-2025Q3-v1",
            name="RuleSet 2025Q3 v1",
            effective_from=date(2025, 1, 1),
            published_at=datetime(2025, 1, 1, 0, 0, 0),
            known_changes=["Baseline quarterly rule set"],
            supporting_documents=["AEMO SRA Guide v1"],
        )
    )

    replay = HistoricalReplayEngine(market_state_engine=market_state, payout_history_path=payout_path)
    builder = HistoricalAlphaDatabaseBuilder(
        market_state_engine=market_state,
        replay_engine=replay,
        auction_results_path=auctions_path,
        payout_history_path=payout_path,
    )

    output = tmp_path / "alpha.csv"
    result = builder.build(
        output_path=output,
        fidelity_as_of=datetime(2026, 7, 12),
        fidelity_target_pct=99.0,
    )

    assert result.rows_written == 1
    frame = pd.read_csv(output)
    assert frame.loc[0, "ruleset_id"] == "RS-2025Q3-v1"
    assert float(frame.loc[0, "forecast_error_to_clearing"]) == 0.0
