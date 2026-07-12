"""
SRA Forecast Engine

Generates scenario-based forward IRSR forecasts with probabilistic distributions.
Integrates EYE price models, constraint models, outage calendars and weather data.
"""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional


class ScenarioTypeEnum(Enum):
    """Forecast scenario types."""
    LOW = "LOW"  # Low congestion, low IRSR
    BASE = "BASE"  # Central case
    HIGH = "HIGH"  # High congestion, high IRSR


@dataclass(frozen=True)
class IRSRScenario:
    """
    Probabilistic IRSR forecast for a category and quarter.
    """
    category_id: str  # e.g., "NSW1-VIC1"
    relevant_quarter: str  # e.g., "C2028Q1"
    scenario_type: ScenarioTypeEnum
    forecast_irsr_dollars: Decimal  # Expected IRSR for this scenario
    probability: Decimal  # 0-1, should sum to 1.0 across scenarios
    key_drivers: List[str] = None  # e.g., ["price_spread", "flow_volume", "outage_impact"]
    assumptions: str = ""


class SRAForecastEngine:
    """
    Forecasts forward IRSR using scenario analysis and probabilistic methods.
    
    Phase 3 deliverable:
    - Integrate existing EYE price models (regional prices, spreads)
    - Build directional flow scenarios (low/base/high congestion, outages, weather)
    - Output: 3-5 scenario distributions for quarterly IRSR
    - Generate probability distributions (P5, P25, P50, mean, P75, P95)
    
    Blueprint Section 10, 12 (forward simulation and scenarios)
    """

    def __init__(self):
        """Initialize empty forecast engine."""
        self.scenarios: List[IRSRScenario] = []

    def add_scenario(self, scenario: IRSRScenario) -> None:
        """Register a forecast scenario."""
        self.scenarios.append(scenario)

    def get_scenarios_for_product(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> List[IRSRScenario]:
        """
        Get all forecast scenarios for a product.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            List of IRSRScenario objects
        """
        return [s for s in self.scenarios
                if s.category_id == category_id and s.relevant_quarter == relevant_quarter]

    def probability_weighted_irsr(
        self,
        category_id: str,
        relevant_quarter: str,
    ) -> Optional[Decimal]:
        """
        Calculate probability-weighted expected IRSR.
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            
        Returns:
            Probability-weighted IRSR, or None if no scenarios
        """
        scenarios = self.get_scenarios_for_product(category_id, relevant_quarter)
        if not scenarios:
            return None

        # Verify probabilities sum to ~1.0
        total_prob = sum(s.probability for s in scenarios)
        if abs(total_prob - Decimal("1.0")) > Decimal("0.01"):
            return None  # Invalid scenario set

        return sum(s.forecast_irsr_dollars * s.probability for s in scenarios)

    def percentile_irsr(
        self,
        category_id: str,
        relevant_quarter: str,
        percentile: int,  # 5, 25, 50, 75, 95
    ) -> Optional[Decimal]:
        """
        Calculate IRSR at a specific percentile (simplified: assumes discrete scenarios).
        
        Args:
            category_id: e.g., "NSW1-VIC1"
            relevant_quarter: e.g., "C2028Q1"
            percentile: 5, 25, 50, 75, or 95
            
        Returns:
            IRSR value at percentile, or None
        """
        scenarios = self.get_scenarios_for_product(category_id, relevant_quarter)
        if not scenarios:
            return None

        # Sort by forecast IRSR
        sorted_scenarios = sorted(scenarios, key=lambda s: s.forecast_irsr_dollars)

        # Simple discrete percentile: return scenario closest to percentile
        if len(sorted_scenarios) == 1:
            return sorted_scenarios[0].forecast_irsr_dollars

        # For 3-point scenarios (low, base, high): map percentiles to scenarios
        if len(sorted_scenarios) == 3:
            if percentile <= 25:
                return sorted_scenarios[0].forecast_irsr_dollars  # LOW
            elif percentile <= 75:
                return sorted_scenarios[1].forecast_irsr_dollars  # BASE
            else:
                return sorted_scenarios[2].forecast_irsr_dollars  # HIGH

        # For continuous Monte Carlo: would need cumulative probability weighting
        # Simplified here: return value at rank proportional to percentile
        rank = max(0, min(len(sorted_scenarios) - 1,
                          int((percentile / 100) * len(sorted_scenarios))))
        return sorted_scenarios[rank].forecast_irsr_dollars
