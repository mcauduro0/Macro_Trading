"""Agent registry and orchestration for the Macro Trading system.

Manages registration, lookup, and ordered execution of all analytical agents.
Execution order: inflation -> monetary -> fiscal -> fx -> cross_asset
"""

from datetime import date

import structlog

from src.agents.base import AgentReport, BaseAgent

logger = structlog.get_logger()


class AgentRegistry:
    """Registry of all active agents.

    Manages execution order and dependencies.  Agents listed in
    ``EXECUTION_ORDER`` are run first (in that sequence); any additional
    registered agents not in the list are appended alphabetically.

    Usage::

        AgentRegistry.register(InflationAgent())
        AgentRegistry.register(MonetaryPolicyAgent())
        reports = AgentRegistry.run_all(date.today())
    """

    _agents: dict[str, BaseAgent] = {}

    EXECUTION_ORDER: list[str] = [
        "inflation_agent",
        "monetary_agent",
        "fiscal_agent",
        "fx_agent",
        "cross_asset_agent",
    ]

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        """Register an agent instance.

        Args:
            agent: Agent to register.

        Raises:
            ValueError: If an agent with the same ``agent_id`` is already
                registered.
        """
        if agent.agent_id in cls._agents:
            raise ValueError(
                f"Agent '{agent.agent_id}' is already registered. "
                "Call unregister() first to replace it."
            )
        cls._agents[agent.agent_id] = agent
        logger.info(
            "agent_registered",
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
        )

    @classmethod
    def unregister(cls, agent_id: str) -> None:
        """Remove an agent from the registry.

        Args:
            agent_id: Identifier of the agent to remove.

        Raises:
            KeyError: If the agent_id is not registered.
        """
        if agent_id not in cls._agents:
            raise KeyError(
                f"Agent '{agent_id}' is not registered. "
                f"Registered agents: {sorted(cls._agents.keys())}"
            )
        del cls._agents[agent_id]
        logger.info("agent_unregistered", agent_id=agent_id)

    @classmethod
    def get(cls, agent_id: str) -> BaseAgent:
        """Retrieve a registered agent by id.

        Args:
            agent_id: Identifier of the agent.

        Returns:
            The registered BaseAgent instance.

        Raises:
            KeyError: If the agent_id is not registered.
        """
        if agent_id not in cls._agents:
            raise KeyError(
                f"Agent '{agent_id}' is not registered. "
                f"Registered agents: {sorted(cls._agents.keys())}"
            )
        return cls._agents[agent_id]

    @classmethod
    def list_registered(cls) -> list[str]:
        """Return sorted list of all registered agent IDs."""
        return sorted(cls._agents.keys())

    @classmethod
    def _ordered_agent_ids(cls) -> list[str]:
        """Return agent IDs in execution order.

        Agents in ``EXECUTION_ORDER`` come first (in that sequence),
        followed by any additional registered agents sorted alphabetically.
        """
        ordered: list[str] = []
        for aid in cls.EXECUTION_ORDER:
            if aid in cls._agents:
                ordered.append(aid)

        # Append any agents not in EXECUTION_ORDER
        extras = sorted(set(cls._agents.keys()) - set(ordered))
        ordered.extend(extras)
        return ordered

    @classmethod
    def run_all(cls, as_of_date: date) -> dict[str, AgentReport]:
        """Execute all registered agents in dependency order.

        Each agent is wrapped in try/except so that a failure in one agent
        does not abort the remaining agents.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            ``{agent_id: AgentReport}`` for agents that completed successfully.
        """
        reports: dict[str, AgentReport] = {}
        for agent_id in cls._ordered_agent_ids():
            agent = cls._agents[agent_id]
            try:
                logger.info("agent_run_starting", agent_id=agent_id)
                report = agent.run(as_of_date)
                reports[agent_id] = report
            except Exception:
                logger.exception(
                    "agent_run_failed",
                    agent_id=agent_id,
                    as_of_date=str(as_of_date),
                )
        return reports

    @classmethod
    def run_all_backtest(cls, as_of_date: date) -> dict[str, AgentReport]:
        """Execute all registered agents in dependency order (backtest mode).

        Same as ``run_all`` but calls ``backtest_run()`` which does NOT
        persist signals or reports to the database.

        Args:
            as_of_date: Point-in-time reference date.

        Returns:
            ``{agent_id: AgentReport}`` for agents that completed successfully.
        """
        reports: dict[str, AgentReport] = {}
        for agent_id in cls._ordered_agent_ids():
            agent = cls._agents[agent_id]
            try:
                logger.info("agent_backtest_starting", agent_id=agent_id)
                report = agent.backtest_run(as_of_date)
                reports[agent_id] = report
            except Exception:
                logger.exception(
                    "agent_backtest_failed",
                    agent_id=agent_id,
                    as_of_date=str(as_of_date),
                )
        return reports

    @classmethod
    def clear(cls) -> None:
        """Remove all registered agents.  Useful for testing."""
        cls._agents.clear()
        logger.info("agent_registry_cleared")
