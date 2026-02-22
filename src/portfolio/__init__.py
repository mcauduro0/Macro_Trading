"""Portfolio construction and signal aggregation package.

Provides the signal-to-portfolio pipeline:
- SignalAggregator: Weighted vote consensus per asset class from agent signals.
- PortfolioConstructor: Risk parity + conviction overlay + regime scaling.
- CapitalAllocator: Constraint enforcement, drift-triggered rebalancing.
"""

from src.portfolio.portfolio_constructor import (
    PortfolioConstructor,
    PortfolioTarget,
    RegimeState,
)
from src.portfolio.signal_aggregator import (
    AggregatedSignal,
    SignalAggregator,
)

# CapitalAllocator and AllocationResult will be added in Task 2
# Deferred imports to avoid circular dependency before the file exists
try:
    from src.portfolio.capital_allocator import (
        AllocationConstraints,
        AllocationResult,
        CapitalAllocator,
    )
except ImportError:
    pass

__all__ = [
    "AggregatedSignal",
    "AllocationConstraints",
    "AllocationResult",
    "CapitalAllocator",
    "PortfolioConstructor",
    "PortfolioTarget",
    "RegimeState",
    "SignalAggregator",
]
