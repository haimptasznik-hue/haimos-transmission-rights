"""
transmission_rights/data/irsr_engine.py — Historical IRSR reconstruction
"""
from __future__ import annotations

from datetime import datetime
from typing import NamedTuple

import pandas as pd


class IRSRSnapshot(NamedTuple):
    timestamp: str  # ISO format, NEM time
    interconnector_id: str
    from_region: str
    to_region: str
    residue_from_region: float  # $AUD accumulated in the 5-min interval
    residue_to_region: float  # $AUD accumulated in the 5-min interval


class IRSRReconstructor:
    """
    Reconstructs IRSR per directional interconnector from raw NEMWeb dispatch data.
    
    AEMO publishes two residue values per interconnector per 5-min interval:
    - One for flow from the exporting region
    - One for flow to the importing region
    
    The settlement residue is the sum, distributed to SRA unit holders.
    """

    def __init__(self):
        self.cache = {}

    def process_dispatch_irsr_data(self, df: pd.DataFrame) -> list[IRSRSnapshot]:
        """
        Transform raw dispatch IRSR DataFrame into snapshots per interconnector pair.
        
        Input columns: timestamp, interconnector_id, from_region, residue_aud
        Output: List of IRSRSnapshot, one per directional pair per timestamp.
        """
        if df is None or df.empty:
            return []

        results = []
        
        # Group by timestamp and interconnector
        for (ts, ic_id), group in df.groupby(["timestamp", "interconnector_id"]):
            # Extract the two regional entries (one for each region's perspective)
            entries = group.to_dict("records")
            if len(entries) != 2:
                # Skip incomplete entries
                continue
            
            # Assume entries[0] is from_region view, entries[1] is to_region view
            entry_a = entries[0]
            entry_b = entries[1]
            
            from_region = entry_a["from_region"]
            to_region = entry_b["from_region"]
            residue_a = float(entry_a["residue_aud"])
            residue_b = float(entry_b["residue_aud"])
            
            results.append(IRSRSnapshot(
                timestamp=ts,
                interconnector_id=ic_id,
                from_region=from_region,
                to_region=to_region,
                residue_from_region=residue_a,
                residue_to_region=residue_b,
            ))
        
        return results

    def aggregate_by_quarter(self, snapshots: list[IRSRSnapshot], quarter: str) -> dict[str, float]:
        """
        Aggregate IRSR snapshots over a full quarter (calendar quarter).
        
        Returns: dict mapping interconnector_id → total distributable residue (AUD)
        """
        total_by_ic = {}
        for snap in snapshots:
            key = snap.interconnector_id
            # Sum both regional perspectives
            total = snap.residue_from_region + snap.residue_to_region
            total_by_ic[key] = total_by_ic.get(key, 0) + total
        return total_by_ic
