/**
 * AgentsPage.jsx - Agent cards layout with signal/confidence/drivers.
 *
 * Features:
 * - 5 agent cards in responsive grid
 * - Each card: name, signal direction badge, confidence bar, key drivers, risks
 * - Cross-Asset Agent: larger card spanning 2 columns, regime badge, LLM narrative
 * - Data from /api/v1/agents and individual /api/v1/agents/{id}/latest
 */

const { useState, useEffect, useMemo } = React;

// Agent icon mapping
const AGENT_ICONS = {
  inflation_agent: "\uD83D\uDCC8",
  monetary_agent: "\uD83C\uDFE6",
  fiscal_agent: "\uD83D\uDCCA",
  fx_agent: "\uD83D\uDCB1",
  cross_asset_agent: "\uD83C\uDF10",
};

// Regime color map
const REGIME_COLORS = {
  goldilocks: "bg-green-500/20 text-green-400",
  reflation: "bg-amber-500/20 text-amber-400",
  stagflation: "bg-red-500/20 text-red-400",
  deflation: "bg-blue-500/20 text-blue-400",
};

// Direction badge
function DirectionBadge({ direction, size }) {
  const d = (direction || "").toUpperCase();
  const cls = size === "lg"
    ? "inline-block px-3 py-1 rounded-lg text-sm font-bold"
    : "inline-block px-2 py-0.5 rounded text-xs font-semibold";

  if (d === "LONG" || d === "BULLISH") return <span className={cls + " bg-green-500/20 text-green-400"}>LONG</span>;
  if (d === "SHORT" || d === "BEARISH") return <span className={cls + " bg-red-500/20 text-red-400"}>SHORT</span>;
  return <span className={cls + " bg-gray-600/30 text-gray-400"}>NEUTRAL</span>;
}

// Confidence bar component
function ConfidenceBar({ confidence, direction }) {
  const pct = Math.max(0, Math.min(100, (confidence || 0) * 100));
  const d = (direction || "").toUpperCase();
  let barColor = "bg-gray-500";
  if (d === "LONG" || d === "BULLISH") barColor = "bg-green-500";
  if (d === "SHORT" || d === "BEARISH") barColor = "bg-red-500";

  return (
    <div className="w-full">
      <div className="flex justify-between text-xs text-gray-500 mb-1">
        <span>Confidence</span>
        <span className="font-mono">{pct.toFixed(0)}%</span>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-2">
        <div
          className={barColor + " rounded-full h-2 transition-all duration-300"}
          style={{ width: pct + "%" }}
        />
      </div>
    </div>
  );
}

// Single agent card component
function AgentCard({ agent, report, isCrossAsset }) {
  const agentId = agent.agent_id;
  const icon = AGENT_ICONS[agentId] || "\uD83E\uDD16";

  // Extract signal info from report
  const signals = report && report.signals ? report.signals : [];
  const primarySignal = signals.length > 0 ? signals[0] : null;
  const direction = primarySignal ? primarySignal.direction : "NEUTRAL";
  const confidence = primarySignal ? primarySignal.confidence || 0 : 0;

  // Extract narrative
  const narrative = report ? report.narrative : null;

  // Extract key drivers from signal metadata
  const drivers = [];
  const risks = [];
  if (primarySignal && primarySignal.metadata) {
    const meta = primarySignal.metadata;
    if (meta.drivers && Array.isArray(meta.drivers)) {
      drivers.push(...meta.drivers.slice(0, 5));
    }
    if (meta.risks && Array.isArray(meta.risks)) {
      risks.push(...meta.risks.slice(0, 3));
    }
    if (meta.key_factors && Array.isArray(meta.key_factors)) {
      drivers.push(...meta.key_factors.slice(0, 5));
    }
  }

  // If no drivers from metadata, extract from signal fields
  if (drivers.length === 0 && primarySignal) {
    if (primarySignal.value != null) drivers.push("Signal value: " + primarySignal.value.toFixed(3));
    if (primarySignal.horizon_days) drivers.push("Horizon: " + primarySignal.horizon_days + " days");
  }

  // Detect regime for Cross-Asset
  let regime = null;
  if (isCrossAsset) {
    if (primarySignal && primarySignal.metadata && primarySignal.metadata.regime) {
      regime = primarySignal.metadata.regime;
    } else if (narrative && typeof narrative === "string") {
      // Try to extract regime from narrative text
      const regimeMatch = narrative.toLowerCase();
      if (regimeMatch.includes("goldilocks")) regime = "goldilocks";
      else if (regimeMatch.includes("reflation")) regime = "reflation";
      else if (regimeMatch.includes("stagflation")) regime = "stagflation";
      else if (regimeMatch.includes("deflation")) regime = "deflation";
    }
  }

  const cardClass = isCrossAsset
    ? "bg-gray-800 rounded-lg p-6 col-span-1 lg:col-span-2 border border-gray-700"
    : "bg-gray-800 rounded-lg p-6 border border-gray-700";

  return (
    <div className={cardClass}>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <span className="text-2xl">{icon}</span>
          <h3 className="text-gray-200 font-semibold text-base">{agent.agent_name}</h3>
        </div>
        <DirectionBadge direction={direction} size="lg" />
      </div>

      {/* Confidence bar */}
      <div className="mb-4">
        <ConfidenceBar confidence={confidence} direction={direction} />
      </div>

      {/* Regime badge (Cross-Asset only) */}
      {isCrossAsset && regime && (
        <div className="mb-4">
          <span className="text-gray-500 text-xs uppercase mr-2">Regime:</span>
          <span className={
            "px-2 py-1 rounded text-xs font-semibold " +
            (REGIME_COLORS[regime.toLowerCase()] || "bg-gray-600/30 text-gray-400")
          }>
            {regime.charAt(0).toUpperCase() + regime.slice(1)}
          </span>
        </div>
      )}

      {/* Key drivers */}
      {drivers.length > 0 && (
        <div className="mb-3">
          <div className="text-gray-500 text-xs uppercase mb-1">Key Drivers</div>
          <ul className="space-y-1">
            {drivers.map((d, idx) => (
              <li key={idx} className="text-gray-300 text-sm flex items-start gap-2">
                <span className="text-gray-600 mt-0.5">{">"}</span>
                <span>{d}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Risks */}
      {risks.length > 0 && (
        <div className="mb-3">
          <div className="text-gray-500 text-xs uppercase mb-1">Risks</div>
          <ul className="space-y-1">
            {risks.map((r, idx) => (
              <li key={idx} className="text-red-300/70 text-sm flex items-start gap-2">
                <span className="text-red-500/50 mt-0.5">{"!"}</span>
                <span>{r}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* LLM Narrative (Cross-Asset only) */}
      {isCrossAsset && (
        <div className="mt-4 pt-4 border-t border-gray-700">
          <div className="text-gray-500 text-xs uppercase mb-2">Cross-Asset Narrative</div>
          {narrative ? (
            <blockquote className="text-gray-300 text-sm italic border-l-2 border-blue-500/40 pl-3 leading-relaxed">
              {narrative}
            </blockquote>
          ) : (
            <p className="text-gray-600 text-sm italic">
              Narrative unavailable -- using template fallback
            </p>
          )}
        </div>
      )}

      {/* Agent description */}
      <div className="mt-3 pt-3 border-t border-gray-700">
        <p className="text-gray-500 text-xs">{agent.description}</p>
      </div>

      {/* Signal count */}
      <div className="mt-2 flex justify-between text-xs text-gray-600">
        <span>Signals: {signals.length}</span>
        {report && report.as_of_date && (
          <span>As of: {report.as_of_date}</span>
        )}
      </div>
    </div>
  );
}

function AgentsPage() {
  const { data: agentsData, loading: agentsLoading, error: agentsError } = useFetch("/api/v1/agents", 30000);
  const [reports, setReports] = useState({});
  const [reportsLoading, setReportsLoading] = useState(true);

  const agents = agentsData && agentsData.data ? agentsData.data : [];

  // Fetch individual agent reports when agents list loads
  useEffect(() => {
    if (agents.length === 0) return;

    let cancelled = false;
    setReportsLoading(true);

    async function fetchReports() {
      const newReports = {};
      for (const agent of agents) {
        try {
          const res = await fetch("/api/v1/agents/" + agent.agent_id + "/latest");
          if (res.ok) {
            const json = await res.json();
            if (json.data) {
              newReports[agent.agent_id] = json.data;
            }
          }
        } catch (e) {
          // Skip failed agents
        }
      }
      if (!cancelled) {
        setReports(newReports);
        setReportsLoading(false);
      }
    }

    fetchReports();
    return () => { cancelled = true; };
  }, [agents.length]);

  // Separate cross-asset agent from others
  const { regularAgents, crossAssetAgent } = useMemo(() => {
    const regular = [];
    let cross = null;
    for (const agent of agents) {
      if (agent.agent_id === "cross_asset_agent") {
        cross = agent;
      } else {
        regular.push(agent);
      }
    }
    return { regularAgents: regular, crossAssetAgent: cross };
  }, [agents]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-100 mb-6">Analytical Agents</h1>

      {/* Error banner */}
      {agentsError && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 text-red-300 text-sm">
          Error loading agents: {agentsError}
        </div>
      )}

      {/* Loading skeleton */}
      {agentsLoading && agents.length === 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="skeleton bg-gray-800 h-48 rounded-lg"></div>
          ))}
        </div>
      )}

      {/* Agent cards grid */}
      {agents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {/* Regular agents */}
          {regularAgents.map((agent) => (
            <AgentCard
              key={agent.agent_id}
              agent={agent}
              report={reports[agent.agent_id]}
              isCrossAsset={false}
            />
          ))}

          {/* Cross-Asset Agent (larger card) */}
          {crossAssetAgent && (
            <AgentCard
              agent={crossAssetAgent}
              report={reports[crossAssetAgent.agent_id]}
              isCrossAsset={true}
            />
          )}
        </div>
      )}

      {/* Reports loading indicator */}
      {reportsLoading && agents.length > 0 && (
        <div className="mt-3 text-gray-500 text-xs text-center">
          Loading agent reports...
        </div>
      )}
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.AgentsPage = AgentsPage;
