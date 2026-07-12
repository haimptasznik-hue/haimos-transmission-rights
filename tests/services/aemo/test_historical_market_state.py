from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
import sys


SRC_DIR = Path(__file__).resolve().parents[3] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from transmission_rights.services.aemo.historical_market_state import (
    HistoricalMarketStateEngine,
    VersionedArtifact,
)


def test_point_in_time_selection_uses_latest_published_version():
    engine = HistoricalMarketStateEngine()
    engine.register(
        VersionedArtifact(
            kind="rule",
            version_id="rule_v1",
            effective_from=date(2025, 12, 1),
            published_at=datetime(2025, 11, 20, 9, 0, 0),
            payload={"name": "rule v1"},
        )
    )
    engine.register(
        VersionedArtifact(
            kind="rule",
            version_id="rule_v2",
            effective_from=date(2026, 1, 1),
            published_at=datetime(2026, 1, 10, 9, 0, 0),
            payload={"name": "rule v2"},
        )
    )
    engine.register(
        VersionedArtifact(
            kind="unit_table",
            version_id="unit_v1",
            effective_from=date(2025, 12, 1),
            published_at=datetime(2025, 12, 15, 12, 0, 0),
            payload={"name": "units v1"},
        )
    )

    state = engine.resolve(date(2026, 1, 15))

    assert state.rule_version is not None
    assert state.rule_version.version_id == "rule_v2"
    assert state.unit_table is not None
    assert state.unit_table.version_id == "unit_v1"
    assert state.version_registry == {"rule": "rule_v2", "unit_table": "unit_v1"}


def test_future_versions_are_hidden_until_published():
    engine = HistoricalMarketStateEngine()
    engine.register(
        VersionedArtifact(
            kind="product",
            version_id="product_v1",
            effective_from=date(2026, 1, 1),
            published_at=datetime(2026, 1, 20, 8, 30, 0),
            payload={"name": "product v1"},
        )
    )

    state = engine.resolve(date(2026, 1, 15))

    assert state.product_definitions is None
    assert "product:missing" in state.selection_log
