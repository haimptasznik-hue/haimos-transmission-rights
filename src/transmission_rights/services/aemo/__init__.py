"""
AEMO Digital Twin Services

11 native modules for replicating and extending AEMO's SRA settlement and pricing calculations.

Modules:
- sra_product_registry: Directional interconnectors, categories, quarters, tranches, max units and proportions
- sra_market_calendar: Auction opening/closing dates, notices and product availability
- sra_irssr_calculator: Interval IRSR calculation using prices, adjusted flows and losses
- sra_distribution_engine: Allocation, unsold-unit treatment, negative-residue rules, minimum payment and fees
- sra_auction_parser: Bid/offer schemas, public results, clearing and cancellation prices
- sra_position_ledger: SRDAs, Units, acquisition cost, cancellations, assignments, accrued/settled value
- sra_historical_replay: Point-in-time reconstruction with settlement revisions
- sra_forecast_engine: Scenario and probabilistic future IRSR
- sra_mark_engine: Clean value, risk-adjusted value, bid/mid/offer and confidence
- sra_execution_adapter: AEMO file generation, validation, submission and acknowledgements
"""

from .sra_product_registry import SRAProductRegistry
from .sra_market_calendar import SRAMarketCalendar
from .sra_irssr_calculator import SRAIRSRCalculator
from .sra_distribution_engine import SRADistributionEngine
from .sra_auction_parser import SRAAuctionParser
from .sra_position_ledger import SRAPositionLedger
from .sra_historical_replay import SRAHistoricalReplay
from .sra_forecast_engine import SRAForecastEngine
from .sra_mark_engine import SRAMarkEngine
from .sra_execution_adapter import SRAExecutionAdapter

__all__ = [
    'SRAProductRegistry',
    'SRAMarketCalendar',
    'SRAIRSRCalculator',
    'SRADistributionEngine',
    'SRAAuctionParser',
    'SRAPositionLedger',
    'SRAHistoricalReplay',
    'SRAForecastEngine',
    'SRAMarkEngine',
    'SRAExecutionAdapter',
]
