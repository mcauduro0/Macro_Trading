"""Feature engines for analytical agents.

Re-exports the feature engine classes used by inflation and monetary
policy agents.

InflationFeatureEngine is exported when available (built in plan 08-01).
MonetaryFeatureEngine is always available (built in plan 08-03, wave 1).
"""

from src.agents.features.monetary_features import MonetaryFeatureEngine

__all__ = ["MonetaryFeatureEngine"]

# InflationFeatureEngine is added in plan 08-01; import conditionally
# so plan 08-03 (wave 1) can run independently.
try:
    from src.agents.features.inflation_features import InflationFeatureEngine  # type: ignore[import]

    __all__ = ["MonetaryFeatureEngine", "InflationFeatureEngine"]
except ImportError:
    pass
