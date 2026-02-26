"""SQLAlchemy 2.0 ORM models for the Macro Trading system.

Re-exports Base and all 20 model classes for convenient imports:
  - 3 metadata tables: Instrument, SeriesMetadata, DataSource
  - 7 hypertables: MarketData, MacroSeries, CurveData, FlowData,
    FiscalData, VolSurface, Signal
  - 5 v2/v3 tables: AgentReportRecord, BacktestResultRecord,
    StrategyStateRecord, NlpDocumentRecord, PortfolioStateRecord
  - 5 PMS v4 tables: PortfolioPosition, TradeProposal, DecisionJournal,
    DailyBriefing, PositionPnLHistory
"""

from .agent_reports import AgentReportRecord
from .backtest_results import BacktestResultRecord
from .base import Base
from .curves import CurveData
from .data_sources import DataSource
from .fiscal_data import FiscalData
from .flow_data import FlowData
from .instruments import Instrument
from .macro_series import MacroSeries
from .market_data import MarketData
from .nlp_documents import NlpDocumentRecord
from .pms_models import (
    DailyBriefing,
    DecisionJournal,
    PortfolioPosition,
    PositionPnLHistory,
    TradeProposal,
)
from .portfolio_state import PortfolioStateRecord
from .series_metadata import SeriesMetadata
from .signals import Signal
from .strategy_state import StrategyStateRecord
from .vol_surfaces import VolSurface

__all__ = [
    "Base",
    "Instrument",
    "SeriesMetadata",
    "DataSource",
    "MarketData",
    "MacroSeries",
    "CurveData",
    "FlowData",
    "FiscalData",
    "VolSurface",
    "Signal",
    "AgentReportRecord",
    "BacktestResultRecord",
    "StrategyStateRecord",
    "NlpDocumentRecord",
    "PortfolioStateRecord",
    "PortfolioPosition",
    "TradeProposal",
    "DecisionJournal",
    "DailyBriefing",
    "PositionPnLHistory",
]
