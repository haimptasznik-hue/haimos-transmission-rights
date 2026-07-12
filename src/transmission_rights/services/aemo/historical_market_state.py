"""Historical market state engine for point-in-time AEMO replication.

Phase 2A builds a versioned source of truth for what AEMO knew at any
decision point. The engine intentionally separates publication timestamps
from effective dates so historical replay can avoid look-ahead bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time
from typing import Any, Dict, Generic, Iterable, List, Optional, TypeVar


T = TypeVar("T")


def _to_datetime(value: date | datetime) -> datetime:
    if isinstance(value, datetime):
        point = value
    else:
        point = datetime.combine(value, time.max)

    if point.tzinfo is None:
        return point.replace(tzinfo=UTC)
    return point.astimezone(UTC)


@dataclass(frozen=True)
class VersionedArtifact(Generic[T]):
    """A versioned artifact with both publication and effective timestamps."""

    kind: str
    version_id: str
    effective_from: date
    published_at: datetime
    payload: T
    source: str = ""
    change_log: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuleSet:
    """First-class auditable RuleSet used by historical replay and validation."""

    rule_set_id: str
    name: str
    effective_from: date
    published_at: datetime
    effective_to: Optional[date] = None
    unit_table_version: str = ""
    settlement_formula_version: str = ""
    fee_formula_version: str = ""
    product_definitions_version: str = ""
    known_changes: List[str] = field(default_factory=list)
    supporting_documents: List[str] = field(default_factory=list)


class RuleSetRegistry:
    """Effective-dated registry for RuleSet objects."""

    def __init__(self) -> None:
        self._records: List[RuleSet] = []

    def register(self, ruleset: RuleSet) -> None:
        self._records.append(ruleset)
        self._records.sort(
            key=lambda item: (_to_datetime(item.published_at), item.effective_from, item.rule_set_id)
        )

    def all_versions(self) -> List[RuleSet]:
        return list(self._records)

    def resolve(self, as_of: date | datetime) -> Optional[RuleSet]:
        if not self._records:
            return None

        decision_point = _to_datetime(as_of)
        decision_date = decision_point.date()
        candidates = [record for record in self._records if _to_datetime(record.published_at) <= decision_point]
        if not candidates:
            return None

        active = [
            record
            for record in candidates
            if record.effective_from <= decision_date
            and (record.effective_to is None or decision_date <= record.effective_to)
        ]
        if active:
            return max(
                active,
                key=lambda item: (_to_datetime(item.published_at), item.effective_from, item.rule_set_id),
            )

        return max(
            candidates,
            key=lambda item: (_to_datetime(item.published_at), item.effective_from, item.rule_set_id),
        )


@dataclass(frozen=True)
class MarketStateSelection:
    """The selected point-in-time state for a decision date."""

    decision_point: datetime
    ruleset: Optional[RuleSet]
    rule_version: Optional[VersionedArtifact[Any]]
    product_definitions: Optional[VersionedArtifact[Any]]
    unit_table: Optional[VersionedArtifact[Any]]
    fee_model: Optional[VersionedArtifact[Any]]
    settlement_logic: Optional[VersionedArtifact[Any]]
    selection_log: List[str] = field(default_factory=list)

    @property
    def version_registry(self) -> Dict[str, str]:
        registry: Dict[str, str] = {}
        if self.ruleset is not None:
            registry["ruleset"] = self.ruleset.rule_set_id
        for artifact in (
            self.rule_version,
            self.product_definitions,
            self.unit_table,
            self.fee_model,
            self.settlement_logic,
        ):
            if artifact is not None:
                registry[artifact.kind] = artifact.version_id
        return registry


class EffectiveDatedRegistry(Generic[T]):
    """Stores effective-dated versions and resolves the latest known version."""

    def __init__(self, kind: str):
        self.kind = kind
        self._records: List[VersionedArtifact[T]] = []

    def register(self, artifact: VersionedArtifact[T]) -> None:
        if artifact.kind != self.kind:
            raise ValueError(f"Expected kind {self.kind!r}, got {artifact.kind!r}")
        self._records.append(artifact)
        self._records.sort(
            key=lambda item: (_to_datetime(item.published_at), item.effective_from, item.version_id)
        )

    def all_versions(self) -> List[VersionedArtifact[T]]:
        return list(self._records)

    def resolve(self, as_of: date | datetime) -> Optional[VersionedArtifact[T]]:
        if not self._records:
            return None

        decision_point = _to_datetime(as_of)
        candidates = [record for record in self._records if _to_datetime(record.published_at) <= decision_point]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda record: (_to_datetime(record.published_at), record.effective_from, record.version_id),
        )


class HistoricalMarketStateEngine:
    """Resolves the complete historical market state for a decision point."""

    def __init__(self) -> None:
        self.rule_sets = RuleSetRegistry()
        self.rule_versions: EffectiveDatedRegistry[Any] = EffectiveDatedRegistry("rule")
        self.product_definitions: EffectiveDatedRegistry[Any] = EffectiveDatedRegistry("product")
        self.unit_tables: EffectiveDatedRegistry[Any] = EffectiveDatedRegistry("unit_table")
        self.fee_models: EffectiveDatedRegistry[Any] = EffectiveDatedRegistry("fee_model")
        self.settlement_logic: EffectiveDatedRegistry[Any] = EffectiveDatedRegistry("settlement_logic")

    def register_ruleset(self, ruleset: RuleSet) -> None:
        self.rule_sets.register(ruleset)

    def register(self, artifact: VersionedArtifact[Any]) -> None:
        registry = self._registry_for_kind(artifact.kind)
        registry.register(artifact)

    def register_many(self, artifacts: Iterable[VersionedArtifact[Any]]) -> None:
        for artifact in artifacts:
            self.register(artifact)

    def _registry_for_kind(self, kind: str) -> EffectiveDatedRegistry[Any]:
        if kind == "rule":
            return self.rule_versions
        if kind == "product":
            return self.product_definitions
        if kind == "unit_table":
            return self.unit_tables
        if kind == "fee_model":
            return self.fee_models
        if kind == "settlement_logic":
            return self.settlement_logic
        raise ValueError(f"Unknown market-state kind: {kind}")

    def resolve(self, as_of: date | datetime) -> MarketStateSelection:
        decision_point = _to_datetime(as_of)
        selection_log: List[str] = []

        ruleset = self.rule_sets.resolve(decision_point)
        rule_version = self.rule_versions.resolve(decision_point)
        product_definitions = self.product_definitions.resolve(decision_point)
        unit_table = self.unit_tables.resolve(decision_point)
        fee_model = self.fee_models.resolve(decision_point)
        settlement_logic = self.settlement_logic.resolve(decision_point)

        if ruleset is None:
            selection_log.append("ruleset:missing")
        else:
            selection_log.append(f"ruleset:{ruleset.rule_set_id}@{ruleset.published_at.isoformat()}")

        for label, artifact in (
            ("rule", rule_version),
            ("product", product_definitions),
            ("unit_table", unit_table),
            ("fee_model", fee_model),
            ("settlement_logic", settlement_logic),
        ):
            if artifact is None:
                selection_log.append(f"{label}:missing")
            else:
                selection_log.append(
                    f"{label}:{artifact.version_id}@{artifact.published_at.isoformat()}"
                )

        return MarketStateSelection(
            decision_point=decision_point,
            ruleset=ruleset,
            rule_version=rule_version,
            product_definitions=product_definitions,
            unit_table=unit_table,
            fee_model=fee_model,
            settlement_logic=settlement_logic,
            selection_log=selection_log,
        )

    def version_registry(self) -> Dict[str, List[str]]:
        return {
            "ruleset": [item.rule_set_id for item in self.rule_sets.all_versions()],
            "rule": [item.version_id for item in self.rule_versions.all_versions()],
            "product": [item.version_id for item in self.product_definitions.all_versions()],
            "unit_table": [item.version_id for item in self.unit_tables.all_versions()],
            "fee_model": [item.version_id for item in self.fee_models.all_versions()],
            "settlement_logic": [item.version_id for item in self.settlement_logic.all_versions()],
        }
