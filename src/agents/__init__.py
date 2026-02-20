"""Agent framework for the Macro Trading system.

Re-exports the core agent infrastructure:
- BaseAgent: Abstract base class with Template Method pattern
- AgentSignal: Typed signal output dataclass
- AgentReport: Complete agent run output
- PointInTimeDataLoader: PIT-correct data access layer
"""

from src.agents.base import AgentReport, AgentSignal, BaseAgent
from src.agents.data_loader import PointInTimeDataLoader

__all__ = [
    "BaseAgent",
    "AgentSignal",
    "AgentReport",
    "PointInTimeDataLoader",
]
