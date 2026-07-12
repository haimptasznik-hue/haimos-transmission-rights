from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

REPO_ROOT = Path(__file__).resolve().parents[3]
PAYOUT_HISTORY_PATH = REPO_ROOT / "data/derived/sra/sra_payout_history.csv"

from transmission_rights.services.aemo.historical_market_state import (  # noqa: E402
    HistoricalMarketStateEngine,
    MarketStateSelection,
    VersionedArtifact,
)
from transmission_rights.services.aemo.historical_replay import HistoricalReplayEngine  # noqa: E402


class CountingResolver:
    def __init__(self, delegate: HistoricalMarketStateEngine):
        self._delegate = delegate
        self.calls = 0

    def resolve(self, as_of: date | datetime) -> MarketStateSelection:
        self.calls += 1
        return self._delegate.resolve(as_of)


def test_closed_quarter_replay_returns_rows_and_state_versions():
    market_state = HistoricalMarketStateEngine()
    market_state.register(
        VersionedArtifact(
            kind="rule",
            version_id="rule_v1",
            effective_from=date(2025, 12, 1),
            published_at=datetime(2025, 11, 20, 9, 0, 0),
            payload={"name": "rule v1"},
        )
    )
    engine = HistoricalReplayEngine(
        market_state_engine=market_state,
        payout_history_path=PAYOUT_HISTORY_PATH,
    )

    bundle = engine.replay_quarter("C2025Q3", as_of=date(2026, 1, 15))

    assert len(bundle.rows) == 6
    assert bundle.market_state.version_registry == {"rule": "rule_v1"}
    assert bundle.rows[0].quarter == "C2025Q3"
    assert bundle.rows[0].market_state_versions == {"rule": "rule_v1"}


def test_open_quarter_is_not_replayed():
    engine = HistoricalReplayEngine(
        payout_history_path=PAYOUT_HISTORY_PATH,
    )

    bundle = engine.replay_quarter("C2026Q3", as_of=date(2026, 7, 12))

    assert bundle.rows == []


def test_replay_engine_asks_market_state_engine_for_rule_selection():
    market_state = HistoricalMarketStateEngine()
    market_state.register(
        VersionedArtifact(
            kind="rule",
            version_id="rule_v1",
            effective_from=date(2025, 12, 1),
            published_at=datetime(2025, 11, 20, 9, 0, 0),
            payload={"name": "rule v1"},
        )
    )
    resolver = CountingResolver(market_state)
    engine = HistoricalReplayEngine(
        market_state_engine=resolver,
        payout_history_path=PAYOUT_HISTORY_PATH,
    )

    result = engine.validate_point_in_time("C2025Q3", as_of=date(2026, 1, 15))

    assert resolver.calls == 1
    assert result["status"] == "ok"
    assert result["state_versions"] == {"rule": "rule_v1"}
