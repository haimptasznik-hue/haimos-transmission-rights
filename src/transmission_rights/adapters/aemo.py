from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AEMODataDependencyPlan:
    current_sources: list[str]
    deferred_sources: list[str]


def planned_aemo_dependencies() -> AEMODataDependencyPlan:
    return AEMODataDependencyPlan(
        current_sources=[
            "AEMO controlled SRA product definitions and maximum-unit tables",
            "AEMO auction calendars and tranche schedules",
            "AEMO published auction results and clearing prices",
            "AEMO NEMWeb regional spot price data",
            "AEMO interconnector flow and loss-adjusted settlement inputs",
        ],
        deferred_sources=[
            "Participant File Server / Data Interchange submission integration",
            "Assignment workflow confirmations requiring current AEMO consent process",
            "Any non-public prudential or participant-specific settlement feeds",
        ],
    )
