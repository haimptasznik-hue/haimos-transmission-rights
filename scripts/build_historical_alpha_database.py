#!/usr/bin/env python3

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.historical_alpha_database import (
    HistoricalAlphaDatabaseBuilder,
)
from transmission_rights.services.aemo.historical_market_state import (
    HistoricalMarketStateEngine,
    RuleSet,
)
from transmission_rights.services.aemo.historical_replay import HistoricalReplayEngine


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase C historical alpha database")
    parser.add_argument(
        "--auction-results",
        type=Path,
        default=Path("data/derived/sra/sra_auction_results.csv"),
        help="Combined historical auction results CSV",
    )
    parser.add_argument(
        "--payout-history",
        type=Path,
        default=Path("data/derived/sra/sra_payout_history.csv"),
        help="Historical payout history CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/derived/sra/alpha_database.csv"),
        help="Output alpha database CSV",
    )
    parser.add_argument(
        "--fidelity-as-of",
        type=str,
        default=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S%z"),
        help="As-of timestamp for historical fidelity gate (ISO8601)",
    )
    parser.add_argument(
        "--fidelity-target-pct",
        type=float,
        default=99.0,
        help="Minimum reconciliation percentage required before forecasting",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    fidelity_as_of = datetime.fromisoformat(args.fidelity_as_of)

    market_state = HistoricalMarketStateEngine()
    market_state.register_ruleset(
        RuleSet(
            rule_set_id="RS-BASELINE-v1",
            name="Baseline historical replay ruleset",
            effective_from=datetime(2020, 1, 1).date(),
            effective_to=None,
            published_at=datetime(2020, 1, 1, 0, 0, 0),
            unit_table_version="unit_table_v1",
            settlement_formula_version="settlement_formula_v1",
            fee_formula_version="fee_formula_v1",
            product_definitions_version="product_definitions_v1",
            known_changes=["Initial baseline ruleset"],
            supporting_documents=["AEMO SRA guide (baseline reference)"],
        )
    )

    replay = HistoricalReplayEngine(
        market_state_engine=market_state,
        payout_history_path=args.payout_history,
    )

    builder = HistoricalAlphaDatabaseBuilder(
        market_state_engine=market_state,
        replay_engine=replay,
        auction_results_path=args.auction_results,
        payout_history_path=args.payout_history,
    )

    result = builder.build(
        output_path=args.output,
        fidelity_as_of=fidelity_as_of,
        fidelity_target_pct=args.fidelity_target_pct,
    )

    print(f"rows_written={result.rows_written}")
    print(f"output={result.output_path}")
    print(f"fidelity_status={result.fidelity_report.get('status')}")


if __name__ == "__main__":
    main()
