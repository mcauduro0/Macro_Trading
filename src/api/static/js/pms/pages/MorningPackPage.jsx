/**
 * MorningPackPage.jsx - Morning Pack daily briefing page for the PMS.
 *
 * The first operational PMS screen giving the portfolio manager a complete
 * daily overview before markets open. Displays:
 * 1. Active alerts (sticky top banner)
 * 2. Market overview ticker strip (compact horizontal)
 * 3. Agent intelligence summaries (one card per agent)
 * 4. Actionable trade proposals with approve/reject flow
 *
 * Consumes 3 API endpoints:
 * - /api/v1/pms/morning-pack/latest  (main briefing data)
 * - /api/v1/pms/risk/live            (live risk alerts)
 * - /api/v1/pms/trades/proposals?status=pending (trade proposals)
 *
 * Falls back to sample data when API unavailable.
 * All components accessed via window globals (CDN/Babel pattern).
 */

const { useState, useEffect, useCallback } = React;

// ---------------------------------------------------------------------------
// Access PMS design system from window globals
// ---------------------------------------------------------------------------
const {
  PMS_COLORS: _COLORS,
  PMS_TYPOGRAPHY: _TYPO,
  PMS_SPACING: _SP,
  pnlColor: _pnlColor,
  riskColor: _riskColor,
  directionColor: _directionColor,
  convictionColor: _convictionColor,
  formatPnL: _formatPnL,
  formatNumber: _formatNumber,
} = window.PMS_THEME;

// ---------------------------------------------------------------------------
// Sample / Fallback Data
// ---------------------------------------------------------------------------
const SAMPLE_MARKET_DATA = [
  { ticker: 'DI1F26', value: 14.25, change: -0.15, unit: '%' },
  { ticker: 'DI1F27', value: 13.80, change: -0.08, unit: '%' },
  { ticker: 'IBOV', value: 128450, change: 1.2, unit: 'pts' },
  { ticker: 'USD/BRL', value: 4.92, change: -0.35, unit: '' },
  { ticker: 'VIX', value: 18.5, change: 2.1, unit: '' },
  { ticker: 'UST 10Y', value: 4.35, change: 0.03, unit: '%' },
  { ticker: 'CDS BR 5Y', value: 145, change: -3, unit: 'bps' },
  { ticker: 'IPCA 12M', value: 4.62, change: 0.0, unit: '%' },
  { ticker: 'Selic', value: 13.75, change: 0.0, unit: '%' },
  { ticker: 'S&P 500', value: 5320, change: 0.45, unit: 'pts' },
  { ticker: 'DXY', value: 103.8, change: -0.2, unit: '' },
  { ticker: 'Brent', value: 82.5, change: 1.3, unit: 'USD' },
];

const SAMPLE_AGENTS = [
  { id: 'inflation', name: 'Inflation Agent', signal: 'LONG', confidence: 0.72, key_metric: 'IPCA 12M: 4.62% (above target)', rationale: 'Inflation persistence above BCB target suggests further NTN-B protection needed' },
  { id: 'monetary', name: 'Monetary Policy Agent', signal: 'SHORT', confidence: 0.68, key_metric: 'Selic-Taylor gap: -75bps', rationale: 'Market pricing 50bps cut cycle but Taylor rule suggests only 25bps appropriate' },
  { id: 'fiscal', name: 'Fiscal Agent', signal: 'NEUTRAL', confidence: 0.55, key_metric: 'Debt/GDP: 74.2%', rationale: 'Fiscal trajectory stable but primary balance deteriorating at margins' },
  { id: 'fx', name: 'FX Equilibrium Agent', signal: 'LONG', confidence: 0.78, key_metric: 'BEER misalignment: -4.2%', rationale: 'BRL undervalued vs BEER model with positive carry differential supporting appreciation' },
  { id: 'cross_asset', name: 'Cross-Asset Agent', signal: 'NEUTRAL', confidence: 0.61, key_metric: 'Regime: Reflation (0.65)', rationale: 'Goldilocks-to-Reflation transition, moderate risk appetite, cross-asset correlations stable' },
];

const SAMPLE_PROPOSALS = [
  { id: 'tp-1', agent: 'inflation', instrument: 'NTN-B 2030', direction: 'LONG', suggested_size: 15000000, conviction: 0.82, expected_pnl: 45000, rationale: 'IPCA persistence above target, breakeven underpriced vs model', status: 'pending' },
  { id: 'tp-2', agent: 'fx', instrument: 'USD/BRL NDF 3M', direction: 'SHORT', suggested_size: 20000000, conviction: 0.75, expected_pnl: 62000, rationale: 'BRL undervalued per BEER, positive carry, flow momentum supportive', status: 'pending' },
  { id: 'tp-3', agent: 'monetary', instrument: 'DI1 Jan26', direction: 'LONG', suggested_size: 10000000, conviction: 0.68, expected_pnl: 28000, rationale: 'Market overpricing easing cycle, Taylor gap supports receiver position', status: 'pending' },
  { id: 'tp-4', agent: 'cross_asset', instrument: 'IBOV FUT', direction: 'LONG', suggested_size: 8000000, conviction: 0.58, expected_pnl: 18000, rationale: 'Reflation regime favors equities, risk appetite moderate-positive', status: 'pending' },
  { id: 'tp-5', agent: 'fiscal', instrument: 'CDS BR 5Y', direction: 'SHORT', suggested_size: 5000000, conviction: 0.52, expected_pnl: 12000, rationale: 'Fiscal metrics stable, spread compression expected on improved primary balance', status: 'pending' },
];

const SAMPLE_ALERTS = [
  { id: 'a1', severity: 'warning', message: 'VaR utilization at 82% of daily limit -- approaching threshold' },
  { id: 'a2', severity: 'breach', message: 'Sector concentration in Fixed Income exceeds 45% limit' },
];

// ---------------------------------------------------------------------------
// Formatting Helpers
// ---------------------------------------------------------------------------

/**
 * Format notional value for display.
 * e.g., 15000000 -> "BRL 15.0M", 500000 -> "BRL 500K"
 */
function formatNotional(value) {
  if (value == null || isNaN(value)) return '--';
  const abs = Math.abs(value);
  if (abs >= 1e9) return 'BRL ' + (value / 1e9).toFixed(1) + 'B';
  if (abs >= 1e6) return 'BRL ' + (value / 1e6).toFixed(1) + 'M';
  if (abs >= 1e3) return 'BRL ' + (value / 1e3).toFixed(0) + 'K';
  return 'BRL ' + value.toFixed(0);
}

/**
 * Format expected P&L with sign and color-friendly prefix.
 * e.g., 45000 -> "+R$ 45K", -12000 -> "-R$ 12K"
 */
function formatExpectedPnL(value) {
  if (value == null || isNaN(value)) return '--';
  const sign = value >= 0 ? '+' : '-';
  const abs = Math.abs(value);
  let formatted;
  if (abs >= 1e6) formatted = (abs / 1e6).toFixed(1) + 'M';
  else if (abs >= 1e3) formatted = (abs / 1e3).toFixed(0) + 'K';
  else formatted = abs.toFixed(0);
  return sign + 'R$ ' + formatted;
}

/**
 * Get badge variant for signal direction.
 */
function signalBadgeVariant(signal) {
  if (!signal) return 'neutral';
  const s = signal.toUpperCase();
  if (s === 'LONG' || s === 'BUY') return 'positive';
  if (s === 'SHORT' || s === 'SELL') return 'negative';
  return 'neutral';
}

// ---------------------------------------------------------------------------
// Section Components
// ---------------------------------------------------------------------------

/**
 * Section 1: Alert Banner (sticky top of page content)
 */
function AlertsSection({ riskData, briefingData }) {
  const [dismissed, setDismissed] = useState({});

  // Merge alerts from risk endpoint and briefing action_items
  let allAlerts = [];

  if (riskData && riskData.alerts && Array.isArray(riskData.alerts)) {
    allAlerts = [...riskData.alerts];
  }
  if (briefingData && briefingData.action_items && Array.isArray(briefingData.action_items)) {
    const actionAlerts = briefingData.action_items
      .filter(item => item.priority === 'high' || item.priority === 'urgent')
      .map((item, idx) => ({
        id: 'action-' + idx,
        severity: item.priority === 'urgent' ? 'breach' : 'warning',
        message: item.description || item.text || String(item),
      }));
    allAlerts = [...allAlerts, ...actionAlerts];
  }

  // Use sample alerts if no live data
  if (allAlerts.length === 0 && !riskData && !briefingData) {
    allAlerts = SAMPLE_ALERTS;
  }

  // Filter dismissed
  const visibleAlerts = allAlerts.filter(a => !dismissed[a.id]);

  const handleDismiss = (alertId) => {
    setDismissed(prev => ({ ...prev, [alertId]: true }));
  };

  return window.PMSAlertBanner({ alerts: visibleAlerts, onDismiss: handleDismiss });
}

/**
 * Section 2: Market Overview Ticker Strip (compact horizontal scrollable)
 */
function MarketOverviewStrip({ briefingData }) {
  const marketData = (briefingData && briefingData.market_snapshot && Array.isArray(briefingData.market_snapshot))
    ? briefingData.market_snapshot
    : SAMPLE_MARKET_DATA;

  const stripStyle = {
    display: 'flex',
    flexDirection: 'row',
    gap: '8px',
    overflowX: 'auto',
    padding: '4px 0',
    minHeight: '60px',
    alignItems: 'stretch',
  };

  const sectionHeaderStyle = {
    fontSize: _TYPO.sizes.xs,
    fontWeight: _TYPO.weights.semibold,
    color: _COLORS.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _TYPO.fontFamily,
    marginBottom: '4px',
  };

  return (
    <div style={{ marginBottom: _SP.md }}>
      <div style={sectionHeaderStyle}>Market Overview</div>
      <div style={stripStyle}>
        {marketData.map((item, idx) => (
          <window.PMSMetricCard
            key={item.ticker || idx}
            label={item.ticker}
            value={typeof item.value === 'number' ? _formatNumber(item.value, item.value >= 1000 ? 0 : 2) : item.value}
            change={item.change}
            suffix={item.unit ? (' ' + item.unit) : undefined}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Section 3: Agent Summaries (one card per analytical agent)
 */
function AgentSummariesSection({ briefingData }) {
  const agents = (briefingData && briefingData.agent_views && Array.isArray(briefingData.agent_views))
    ? briefingData.agent_views
    : SAMPLE_AGENTS;

  const gridStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
    gap: _SP.md,
    marginBottom: _SP.lg,
  };

  const sectionHeaderStyle = {
    fontSize: _TYPO.sizes.xs,
    fontWeight: _TYPO.weights.semibold,
    color: _COLORS.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _TYPO.fontFamily,
    marginBottom: '6px',
  };

  return (
    <div>
      <div style={sectionHeaderStyle}>Agent Intelligence</div>
      <div style={gridStyle}>
        {agents.map((agent) => {
          const agentId = agent.id || agent.agent_id || 'unknown';
          const accentColor = _COLORS.agent[agentId] || _COLORS.border.accent;
          const confColor = _convictionColor(agent.confidence);

          const headerStyle = {
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            marginBottom: '4px',
          };

          const nameStyle = {
            fontSize: _TYPO.sizes.sm,
            fontWeight: _TYPO.weights.semibold,
            color: _COLORS.text.primary,
            fontFamily: _TYPO.fontFamily,
          };

          const confidenceStyle = {
            fontSize: _TYPO.sizes.base,
            fontWeight: _TYPO.weights.bold,
            color: confColor,
            fontFamily: _TYPO.fontFamily,
            marginBottom: '2px',
          };

          const metricStyle = {
            fontSize: _TYPO.sizes.xs,
            color: _COLORS.text.secondary,
            fontFamily: _TYPO.fontFamily,
            marginBottom: '2px',
          };

          const rationaleStyle = {
            fontSize: _TYPO.sizes.xs,
            color: _COLORS.text.secondary,
            fontFamily: _TYPO.fontFamily,
            lineHeight: 1.4,
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
          };

          return (
            <window.PMSCard key={agentId} accentColor={accentColor}>
              <div style={headerStyle}>
                <span style={nameStyle}>{agent.name}</span>
                <window.PMSBadge
                  label={agent.signal}
                  variant={signalBadgeVariant(agent.signal)}
                  size="sm"
                />
              </div>
              <div style={confidenceStyle}>{agent.confidence != null ? agent.confidence.toFixed(2) : '--'}</div>
              <div style={metricStyle}>{agent.key_metric || '--'}</div>
              <div style={rationaleStyle}>{agent.rationale || '--'}</div>
            </window.PMSCard>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Section 4: Trade Proposals grouped by agent with approve/reject flow
 */
function TradeProposalsSection({ proposalsData, briefingData }) {
  const [proposalStatuses, setProposalStatuses] = useState({});
  const [errors, setErrors] = useState({});

  // Get proposals from API or fallback
  let proposals = [];
  if (proposalsData && Array.isArray(proposalsData) && proposalsData.length > 0) {
    proposals = proposalsData;
  } else if (briefingData && briefingData.trade_proposals && Array.isArray(briefingData.trade_proposals) && briefingData.trade_proposals.length > 0) {
    proposals = briefingData.trade_proposals;
  } else {
    proposals = SAMPLE_PROPOSALS;
  }

  // Group proposals by agent
  const grouped = {};
  proposals.forEach(p => {
    const agentKey = p.agent || p.agent_id || 'unknown';
    if (!grouped[agentKey]) grouped[agentKey] = [];
    grouped[agentKey].push(p);
  });

  // Agent name lookup
  const agentNames = {
    inflation: 'Inflation Agent',
    monetary: 'Monetary Policy Agent',
    fiscal: 'Fiscal Agent',
    fx: 'FX Equilibrium Agent',
    cross_asset: 'Cross-Asset Agent',
  };

  /**
   * Handle quick-approve action
   */
  const handleApprove = async (proposalId) => {
    try {
      setErrors(prev => ({ ...prev, [proposalId]: null }));
      const res = await fetch(`/api/v1/pms/trades/proposals/${proposalId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          execution_price: null,
          execution_notional: null,
          notes: 'Quick approved from Morning Pack',
        }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      setProposalStatuses(prev => ({ ...prev, [proposalId]: 'APPROVED' }));
    } catch (err) {
      // Gracefully handle - mark as approved in UI for sample data scenario
      if (proposals === SAMPLE_PROPOSALS) {
        setProposalStatuses(prev => ({ ...prev, [proposalId]: 'APPROVED' }));
      } else {
        setErrors(prev => ({ ...prev, [proposalId]: 'Approve failed: ' + err.message }));
      }
    }
  };

  /**
   * Handle reject action
   */
  const handleReject = async (proposalId) => {
    const reason = window.prompt('Rejection reason (optional):');
    if (reason === null) return; // User cancelled prompt

    try {
      setErrors(prev => ({ ...prev, [proposalId]: null }));
      const res = await fetch(`/api/v1/pms/trades/proposals/${proposalId}/reject`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes: reason || '' }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      setProposalStatuses(prev => ({ ...prev, [proposalId]: 'REJECTED' }));
    } catch (err) {
      if (proposals === SAMPLE_PROPOSALS) {
        setProposalStatuses(prev => ({ ...prev, [proposalId]: 'REJECTED' }));
      } else {
        setErrors(prev => ({ ...prev, [proposalId]: 'Reject failed: ' + err.message }));
      }
    }
  };

  /**
   * Handle detail view (placeholder for Phase 24 detail panel)
   */
  const handleDetails = (proposalId) => {
    console.log('Detail view requested for proposal:', proposalId);
  };

  const sectionHeaderStyle = {
    fontSize: _TYPO.sizes.xs,
    fontWeight: _TYPO.weights.semibold,
    color: _COLORS.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
    fontFamily: _TYPO.fontFamily,
    marginBottom: '6px',
  };

  const agentGroupHeaderStyle = (agentId) => ({
    fontSize: _TYPO.sizes.sm,
    fontWeight: _TYPO.weights.semibold,
    color: _COLORS.agent[agentId] || _COLORS.text.primary,
    fontFamily: _TYPO.fontFamily,
    padding: '6px 0 4px 0',
    borderBottom: `1px solid ${_COLORS.border.subtle}`,
    marginBottom: '4px',
  });

  // Proposal card styles (distinct from agent cards: no left accent, tertiary bg)
  const proposalCardStyle = (proposalId) => {
    const status = proposalStatuses[proposalId];
    let borderLeft = 'none';
    if (status === 'APPROVED') borderLeft = `3px solid ${_COLORS.pnl.positive}`;
    if (status === 'REJECTED') borderLeft = `3px solid ${_COLORS.pnl.negative}`;

    return {
      backgroundColor: _COLORS.bg.tertiary,
      border: `1px solid ${_COLORS.border.subtle}`,
      borderLeft,
      borderRadius: '4px',
      padding: '8px 12px',
      fontFamily: _TYPO.fontFamily,
      marginBottom: '4px',
      opacity: status ? 0.7 : 1.0,
    };
  };

  const buttonBase = {
    border: 'none',
    borderRadius: '4px',
    fontSize: _TYPO.sizes.xs,
    fontWeight: _TYPO.weights.semibold,
    fontFamily: _TYPO.fontFamily,
    cursor: 'pointer',
    padding: '3px 10px',
    lineHeight: 1.4,
  };

  const approveButtonStyle = {
    ...buttonBase,
    backgroundColor: _COLORS.pnl.positive,
    color: _COLORS.text.inverse,
  };

  const rejectButtonStyle = {
    ...buttonBase,
    backgroundColor: 'transparent',
    color: _COLORS.pnl.negative,
    border: `1px solid ${_COLORS.pnl.negative}`,
  };

  const detailButtonStyle = {
    ...buttonBase,
    backgroundColor: 'transparent',
    color: _COLORS.text.muted,
    border: `1px solid ${_COLORS.border.default}`,
  };

  return (
    <div>
      <div style={sectionHeaderStyle}>Trade Proposals</div>
      {Object.entries(grouped).map(([agentId, agentProposals]) => (
        <div key={agentId} style={{ marginBottom: _SP.md }}>
          <div style={agentGroupHeaderStyle(agentId)}>
            {agentNames[agentId] || agentId}
          </div>
          {agentProposals.map((proposal) => {
            const pid = proposal.id || proposal.proposal_id;
            const status = proposalStatuses[pid];
            const errMsg = errors[pid];
            const conviction = proposal.conviction != null ? proposal.conviction : 0;
            const isHighConf = conviction >= 0.70;

            return (
              <div key={pid} style={proposalCardStyle(pid)}>
                {/* Top row: instrument + direction badge + conviction */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '3px' }}>
                  <span style={{
                    fontSize: _TYPO.sizes.base,
                    fontWeight: _TYPO.weights.bold,
                    color: _COLORS.text.primary,
                  }}>
                    {proposal.instrument}
                  </span>
                  <window.PMSBadge
                    label={proposal.direction}
                    variant={signalBadgeVariant(proposal.direction)}
                    size="sm"
                  />
                  <span style={{
                    fontSize: _TYPO.sizes.sm,
                    fontWeight: _TYPO.weights.bold,
                    color: _convictionColor(conviction),
                    marginLeft: 'auto',
                  }}>
                    {conviction.toFixed(2)}
                  </span>
                  {status && (
                    <window.PMSBadge
                      label={status}
                      variant={status === 'APPROVED' ? 'positive' : 'negative'}
                      size="sm"
                    />
                  )}
                </div>

                {/* Middle row: size + expected P&L */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px', marginBottom: '3px' }}>
                  <span style={{
                    fontSize: _TYPO.sizes.sm,
                    color: _COLORS.text.secondary,
                  }}>
                    {formatNotional(proposal.suggested_size)}
                  </span>
                  <span style={{
                    fontSize: _TYPO.sizes.sm,
                    fontWeight: _TYPO.weights.semibold,
                    color: _pnlColor(proposal.expected_pnl),
                  }}>
                    {formatExpectedPnL(proposal.expected_pnl)}
                  </span>
                </div>

                {/* Bottom row: rationale */}
                <div style={{
                  fontSize: _TYPO.sizes.xs,
                  color: _COLORS.text.secondary,
                  marginBottom: '4px',
                  lineHeight: 1.3,
                }}>
                  {proposal.rationale || '--'}
                </div>

                {/* Action row */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '6px', alignItems: 'center' }}>
                  {errMsg && (
                    <span style={{ fontSize: _TYPO.sizes.xs, color: _COLORS.pnl.negative, marginRight: 'auto' }}>
                      {errMsg}
                    </span>
                  )}
                  {!status && isHighConf && (
                    <button
                      style={approveButtonStyle}
                      onClick={() => handleApprove(pid)}
                      title="Quick approve high-confidence proposal"
                    >
                      Quick Approve
                    </button>
                  )}
                  {!status && (
                    <button
                      style={detailButtonStyle}
                      onClick={() => handleDetails(pid)}
                      title="View proposal details"
                    >
                      Details
                    </button>
                  )}
                  {!status && (
                    <button
                      style={rejectButtonStyle}
                      onClick={() => handleReject(pid)}
                      title="Reject proposal"
                    >
                      Reject
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
      {Object.keys(grouped).length === 0 && (
        <div style={{
          textAlign: 'center',
          padding: '16px',
          color: _COLORS.text.muted,
          fontSize: _TYPO.sizes.sm,
          fontFamily: _TYPO.fontFamily,
        }}>
          No pending trade proposals
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading Skeletons
// ---------------------------------------------------------------------------
function MorningPackSkeleton() {
  return (
    <div style={{ fontFamily: _TYPO.fontFamily }}>
      {/* Ticker strip skeleton */}
      <div style={{ marginBottom: _SP.md }}>
        <window.PMSSkeleton width="120px" height="12px" />
        <div style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <window.PMSSkeleton key={i} width="100px" height="60px" />
          ))}
        </div>
      </div>
      {/* Agent cards skeleton */}
      <div style={{ marginBottom: _SP.md }}>
        <window.PMSSkeleton width="140px" height="12px" />
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: _SP.md,
          marginTop: '8px',
        }}>
          {Array.from({ length: 5 }).map((_, i) => (
            <window.PMSSkeleton key={i} width="100%" height="120px" />
          ))}
        </div>
      </div>
      {/* Proposals skeleton */}
      <div>
        <window.PMSSkeleton width="140px" height="12px" />
        {Array.from({ length: 3 }).map((_, i) => (
          <window.PMSSkeleton key={i} width="100%" height="80px" className="" />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main MorningPackPage Component
// ---------------------------------------------------------------------------
function MorningPackPage() {
  // Fetch main briefing data
  const briefing = window.useFetch('/api/v1/pms/morning-pack/latest', 60000);
  // Fetch live risk data (for alerts)
  const risk = window.useFetch('/api/v1/pms/risk/live', 60000);
  // Fetch pending trade proposals
  const proposals = window.useFetch('/api/v1/pms/trades/proposals?status=pending', 60000);

  const isLoading = briefing.loading && risk.loading && proposals.loading;

  const pageStyle = {
    fontFamily: _TYPO.fontFamily,
    color: _COLORS.text.primary,
    maxWidth: '1400px',
    margin: '0 auto',
  };

  const titleStyle = {
    fontSize: _TYPO.sizes['2xl'],
    fontWeight: _TYPO.weights.bold,
    color: _COLORS.text.primary,
    marginBottom: '2px',
  };

  const subtitleStyle = {
    fontSize: _TYPO.sizes.xs,
    color: _COLORS.text.muted,
    marginBottom: _SP.md,
  };

  // Show date from briefing or today
  const briefingDate = (briefing.data && briefing.data.briefing_date)
    ? briefing.data.briefing_date
    : new Date().toISOString().split('T')[0];

  const usingSample = !briefing.data && !briefing.loading;

  return (
    <div style={pageStyle}>
      {usingSample && <PMSSampleDataBanner />}
      {/* Section 1: Alerts Banner (sticky within content area) */}
      <AlertsSection riskData={risk.data} briefingData={briefing.data} />

      {/* Page header */}
      <div style={{ marginBottom: _SP.md }}>
        <div style={titleStyle}>Morning Pack</div>
        <div style={subtitleStyle}>{briefingDate} | Updated {new Date().toLocaleTimeString()}</div>
      </div>

      {isLoading ? (
        <MorningPackSkeleton />
      ) : (
        <React.Fragment>
          {/* Section 2: Market Overview Ticker Strip */}
          <MarketOverviewStrip briefingData={briefing.data} />

          {/* Section 3: Agent Summaries */}
          <AgentSummariesSection briefingData={briefing.data} />

          {/* Section 4: Trade Proposals */}
          <TradeProposalsSection
            proposalsData={proposals.data}
            briefingData={briefing.data}
          />
        </React.Fragment>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Expose on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.MorningPackPage = MorningPackPage;
