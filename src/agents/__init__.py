"""Agent framework for the Macro Trading system.

Re-exports the core agent infrastructure:
- BaseAgent: Abstract base class with Template Method pattern
- AgentSignal: Typed signal output dataclass
- AgentReport: Complete agent run output
- PointInTimeDataLoader: PIT-correct data access layer
- AgentRegistry: Ordered execution and agent lookup
"""

from src.agents.base import AgentReport, AgentSignal, BaseAgent
from src.agents.data_loader import PointInTimeDataLoader
from src.agents.registry import AgentRegistry

__all__ = [
    "BaseAgent",
    "AgentSignal",
    "AgentReport",
    "PointInTimeDataLoader",
    "AgentRegistry",
]
