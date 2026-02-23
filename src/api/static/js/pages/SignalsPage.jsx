/**
 * SignalsPage.jsx - Signal heatmap and flip timeline.
 *
 * Features:
 * - Fetches signal data from /api/v1/signals/latest
 * - Heatmap: strategies (Y) x last 30 days (X) with color-coded direction/conviction
 * - Signal flip timeline: chronological list of recent signal changes
 * - Green shades for LONG (intensity = conviction), red for SHORT, gray for NEUTRAL
 */

const { useState, useMemo } = React;

// Color helpers for heatmap cells
function heatmapCellColor(direction, conviction) {
  if (!direction) return "rgba(107, 114, 128, 0.2)";
  const d = direction.toUpperCase();
  const c = Math.max(0.15, Math.min(1.0, conviction || 0.5));

  if (d === "LONG") {
    // Green scale: rgba(34, 197, 94, conviction)
    return "rgba(34, 197, 94, " + (c * 0.8 + 0.1).toFixed(2) + ")";
  }
  if (d === "SHORT") {
    // Red scale: rgba(239, 68, 68, conviction)
    return "rgba(239, 68, 68, " + (c * 0.8 + 0.1).toFixed(2) + ")";
  }
  return "rgba(107, 114, 128, 0.2)";
}

// Direction badge
function DirectionBadge({ direction }) {
  const d = (direction || "").toUpperCase();
  const base = "inline-block px-2 py-0.5 rounded text-xs font-semibold";
  if (d === "LONG") return <span className={base + " bg-green-500/20 text-green-400"}>LONG</span>;
  if (d === "SHORT") return <span className={base + " bg-red-500/20 text-red-400"}>SHORT</span>;
  return <span className={base + " bg-gray-600/30 text-gray-400"}>NEUTRAL</span>;
}

// Generate last N dates as strings
function getLastNDates(n) {
  const dates = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    dates.push(d.toISOString().slice(0, 10));
  }
  return dates;
}

// Extract signal flips from strategy signals
function extractFlips(strategySignals) {
  const flips = [];
  for (const [stratId, signals] of Object.entries(strategySignals)) {
    for (let i = 1; i < signals.length; i++) {
      const prev = signals[i - 1];
      const curr = signals[i];
      if (prev.direction !== curr.direction) {
        flips.push({
          date: curr.date,
          strategyId: stratId,
          oldDirection: prev.direction,
          newDirection: curr.direction,
          conviction: curr.conviction || 0.0,
        });
      }
    }
  }
  // Sort by date descending (most recent first)
  flips.sort((a, b) => (b.date > a.date ? 1 : b.date < a.date ? -1 : 0));
  return flips;
}

function SignalsPage() {
  const { data, loading, error } = useFetch("/api/v1/signals/latest", 30000);
  const [hoveredCell, setHoveredCell] = useState(null);

  const dates = useMemo(() => getLastNDates(30), []);

  // Parse signals into per-strategy map
  const { strategySignals, strategyIds } = useMemo(() => {
    const sigs = data && data.data && data.data.signals ? data.data.signals : [];
    const byStrategy = {};
    for (const sig of sigs) {
      const sid = sig.agent_id || sig.strategy_id || "unknown";
      if (!byStrategy[sid]) byStrategy[sid] = [];
      byStrategy[sid].push(sig);
    }
    return { strategySignals: byStrategy, strategyIds: Object.keys(byStrategy).sort() };
  }, [data]);

  // Build heatmap data: for each strategy x date, find direction/conviction
  const heatmapData = useMemo(() => {
    const map = {};
    for (const [sid, signals] of Object.entries(strategySignals)) {
      map[sid] = {};
      for (const sig of signals) {
        const d = sig.date || sig.as_of_date || "";
        if (d) {
          map[sid][d] = {
            direction: sig.direction,
            conviction: sig.confidence || sig.conviction || 0.5,
          };
        }
      }
    }
    return map;
  }, [strategySignals]);

  // Extract flips
  const flips = useMemo(() => extractFlips(strategySignals), [strategySignals]);

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-100 mb-6">Signals</h1>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/30 border border-red-700 rounded-lg p-3 mb-4 text-red-300 text-sm">
          Error loading signals: {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && strategyIds.length === 0 && (
        <div className="skeleton bg-gray-800 h-64 rounded-lg w-full mb-6"></div>
      )}

      {/* Signal Heatmap */}
      {strategyIds.length > 0 && (
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 mb-6 overflow-x-auto">
          <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Signal Heatmap (30 Days)</h2>
          <div style={{ display: "grid", gridTemplateColumns: "140px repeat(" + dates.length + ", 1fr)", gap: "1px", fontSize: "10px" }}>
            {/* Header row: dates */}
            <div className="text-gray-500 text-xs py-1 px-1 font-semibold">Strategy</div>
            {dates.map((d) => (
              <div key={d} className="text-gray-600 text-center py-1 px-0" style={{ writingMode: "vertical-rl", height: "50px", fontSize: "8px" }}>
                {d.slice(5)}
              </div>
            ))}

            {/* Strategy rows */}
            {strategyIds.map((sid) => (
              <React.Fragment key={sid}>
                <div className="text-gray-300 text-xs py-1 px-1 truncate font-mono" title={sid}>
                  {sid}
                </div>
                {dates.map((d) => {
                  const cell = heatmapData[sid] && heatmapData[sid][d];
                  const direction = cell ? cell.direction : null;
                  const conviction = cell ? cell.conviction : 0;
                  const isHovered = hoveredCell && hoveredCell.sid === sid && hoveredCell.date === d;
                  return (
                    <div
                      key={d}
                      className="rounded-sm cursor-pointer transition-transform"
                      style={{
                        backgroundColor: heatmapCellColor(direction, conviction),
                        minHeight: "18px",
                        border: isHovered ? "1px solid #3b82f6" : "1px solid transparent",
                        transform: isHovered ? "scale(1.3)" : "scale(1)",
                      }}
                      title={sid + " | " + d + " | " + (direction || "N/A") + " (" + (conviction * 100).toFixed(0) + "%)"}
                      onMouseEnter={() => setHoveredCell({ sid, date: d })}
                      onMouseLeave={() => setHoveredCell(null)}
                    />
                  );
                })}
              </React.Fragment>
            ))}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-4 mt-3 text-xs text-gray-500">
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: "rgba(34, 197, 94, 0.7)" }}></span>
              LONG
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: "rgba(239, 68, 68, 0.7)" }}></span>
              SHORT
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block w-3 h-3 rounded" style={{ backgroundColor: "rgba(107, 114, 128, 0.2)" }}></span>
              NEUTRAL
            </span>
            <span className="text-gray-600">| Intensity = conviction level</span>
          </div>
        </div>
      )}

      {/* Signal Flip Timeline */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Signal Flip Timeline</h2>
        {flips.length === 0 ? (
          <div className="text-gray-500 text-sm py-4 text-center">
            {loading ? "Loading..." : "No signal flips detected in the current period"}
          </div>
        ) : (
          <div className="space-y-2 max-h-64 overflow-y-auto">
            {flips.slice(0, 50).map((flip, idx) => (
              <div
                key={idx}
                className="flex items-center gap-3 px-3 py-2 bg-gray-800 rounded-lg text-sm"
              >
                <span className="text-gray-500 font-mono text-xs w-20 flex-shrink-0">{flip.date}</span>
                <span className="text-gray-300 font-mono w-32 truncate flex-shrink-0">{flip.strategyId}</span>
                <span className="flex items-center gap-1">
                  <DirectionBadge direction={flip.oldDirection} />
                  <span className="text-gray-500 mx-1">{"\u2192"}</span>
                  <DirectionBadge direction={flip.newDirection} />
                </span>
                <span className="text-gray-500 text-xs ml-auto">
                  {(flip.conviction * 100).toFixed(0)}% conviction
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Consensus summary */}
      {data && data.data && data.data.consensus && (
        <div className="mt-4 bg-gray-900 border border-gray-800 rounded-lg p-4">
          <h2 className="text-gray-300 text-sm font-semibold uppercase mb-3">Consensus</h2>
          <div className="flex gap-4">
            {Object.entries(data.data.consensus).map(([dir, info]) => (
              <div key={dir} className="bg-gray-800 rounded-lg p-3 text-center flex-1">
                <DirectionBadge direction={dir} />
                <div className="text-gray-300 text-lg font-semibold mt-1">
                  {(info.agreement_ratio * 100).toFixed(0)}%
                </div>
                <div className="text-gray-500 text-xs">
                  {info.count} signals | {(info.avg_confidence * 100).toFixed(0)}% avg conf
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.SignalsPage = SignalsPage;
