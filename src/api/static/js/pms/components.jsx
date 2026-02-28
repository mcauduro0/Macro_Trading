/**
 * components.jsx - Reusable PMS UI Component Library for the Macro Trading
 * Portfolio Management System.
 *
 * Bloomberg-dense dark theme components using PMS_THEME design tokens.
 * All components use inline styles referencing PMS_COLORS for consistent theming.
 *
 * Components:
 * 1. PMSCard       — Dark card with optional colored left border accent
 * 2. PMSTable      — Dense data table with alternating row colors
 * 3. PMSBadge      — Small badge/pill with semantic variants
 * 4. PMSGauge      — Horizontal bar gauge for utilization/limits
 * 5. PMSLayout     — CSS grid container for dashboard layouts
 * 6. PMSMetricCard — Tiny metric display for ticker strips
 * 7. PMSSkeleton   — Loading placeholder with pulse animation
 * 8. PMSAlertBanner— Sticky top banner for active alerts
 *
 * All exposed on window for CDN/Babel compatibility.
 */

const { PMS_COLORS, PMS_TYPOGRAPHY, PMS_SPACING } = window.PMS_THEME;

// ---------------------------------------------------------------------------
// 1. PMSCard — Dark card with optional colored left border accent
// ---------------------------------------------------------------------------
function PMSCard({ title, subtitle, children, accentColor, className }) {
  const cardStyle = {
    backgroundColor: PMS_COLORS.bg.secondary,
    border: `1px solid ${PMS_COLORS.border.default}`,
    borderLeft: accentColor ? `3px solid ${accentColor}` : `1px solid ${PMS_COLORS.border.default}`,
    borderRadius: '6px',
    padding: '8px 12px',
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
  };

  const titleStyle = {
    fontSize: PMS_TYPOGRAPHY.sizes.sm,
    fontWeight: PMS_TYPOGRAPHY.weights.semibold,
    color: PMS_COLORS.text.secondary,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    margin: 0,
    lineHeight: 1.4,
  };

  const subtitleStyle = {
    fontSize: PMS_TYPOGRAPHY.sizes.xs,
    color: PMS_COLORS.text.muted,
    margin: '2px 0 0 0',
  };

  return (
    <div style={cardStyle} className={className || ''}>
      {title && (
        <div style={{ marginBottom: children ? '6px' : 0 }}>
          <div style={titleStyle}>{title}</div>
          {subtitle && <div style={subtitleStyle}>{subtitle}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 2. PMSTable — Dense data table with alternating row backgrounds
// ---------------------------------------------------------------------------
function PMSTable({ columns, data, onRowClick, compact }) {
  const cellPadding = compact ? '3px 6px' : '5px 10px';

  const headerCellStyle = {
    padding: cellPadding,
    fontSize: PMS_TYPOGRAPHY.sizes.xs,
    fontWeight: PMS_TYPOGRAPHY.weights.semibold,
    color: PMS_COLORS.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    borderBottom: `1px solid ${PMS_COLORS.border.default}`,
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
    whiteSpace: 'nowrap',
  };

  const tableStyle = {
    width: '100%',
    borderCollapse: 'collapse',
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
    fontSize: PMS_TYPOGRAPHY.sizes.sm,
  };

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={tableStyle}>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                style={{ ...headerCellStyle, textAlign: col.align || 'left' }}
              >
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(data || []).map((row, rowIdx) => {
            const rowBg = rowIdx % 2 === 0
              ? PMS_COLORS.bg.secondary
              : PMS_COLORS.bg.tertiary;

            return (
              <tr
                key={rowIdx}
                style={{
                  backgroundColor: rowBg,
                  cursor: onRowClick ? 'pointer' : 'default',
                  transition: 'background-color 0.1s',
                }}
                onClick={() => onRowClick && onRowClick(row, rowIdx)}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = PMS_COLORS.bg.elevated;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = rowBg;
                }}
              >
                {columns.map((col) => {
                  const rawValue = row[col.key];
                  const displayValue = col.format
                    ? col.format(rawValue, row)
                    : (rawValue != null ? String(rawValue) : '--');

                  return (
                    <td
                      key={col.key}
                      style={{
                        padding: cellPadding,
                        color: PMS_COLORS.text.primary,
                        textAlign: col.align || 'left',
                        borderBottom: `1px solid ${PMS_COLORS.border.subtle}`,
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {displayValue}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      {(!data || data.length === 0) && (
        <div style={{
          textAlign: 'center',
          padding: '16px',
          color: PMS_COLORS.text.muted,
          fontSize: PMS_TYPOGRAPHY.sizes.sm,
          fontFamily: PMS_TYPOGRAPHY.fontFamily,
        }}>
          No data available
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. PMSBadge — Small badge/pill with semantic variants
// ---------------------------------------------------------------------------
function PMSBadge({ label, variant, size }) {
  const variantColors = {
    positive: { bg: PMS_COLORS.pnl.positive, text: PMS_COLORS.text.inverse },
    negative: { bg: PMS_COLORS.pnl.negative, text: '#ffffff' },
    warning:  { bg: PMS_COLORS.risk.warning, text: PMS_COLORS.text.inverse },
    neutral:  { bg: PMS_COLORS.bg.elevated, text: PMS_COLORS.text.secondary },
    info:     { bg: PMS_COLORS.border.accent, text: PMS_COLORS.text.inverse },
  };

  const colors = variantColors[variant] || variantColors.neutral;
  const isSmall = size === 'sm';

  const badgeStyle = {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.bg,
    color: colors.text,
    fontSize: isSmall ? PMS_TYPOGRAPHY.sizes.xs : PMS_TYPOGRAPHY.sizes.sm,
    fontWeight: PMS_TYPOGRAPHY.weights.semibold,
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
    padding: isSmall ? '1px 5px' : '2px 8px',
    borderRadius: '9999px',
    lineHeight: 1.4,
    whiteSpace: 'nowrap',
  };

  return <span style={badgeStyle}>{label}</span>;
}

// ---------------------------------------------------------------------------
// 4. PMSGauge — Simple horizontal bar gauge
// ---------------------------------------------------------------------------
function PMSGauge({ value, max, label, color, size }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const barHeight = size === 'sm' ? '4px' : '8px';
  const gaugeColor = color || PMS_COLORS.border.accent;

  const containerStyle = {
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
  };

  const trackStyle = {
    width: '100%',
    height: barHeight,
    backgroundColor: PMS_COLORS.bg.tertiary,
    borderRadius: '2px',
    overflow: 'hidden',
  };

  const fillStyle = {
    width: `${pct}%`,
    height: '100%',
    backgroundColor: gaugeColor,
    borderRadius: '2px',
    transition: 'width 0.3s ease',
  };

  const labelStyle = {
    fontSize: PMS_TYPOGRAPHY.sizes.xs,
    color: PMS_COLORS.text.muted,
    marginTop: '3px',
    display: 'flex',
    justifyContent: 'space-between',
  };

  return (
    <div style={containerStyle}>
      <div style={trackStyle}>
        <div style={fillStyle} />
      </div>
      {label && (
        <div style={labelStyle}>
          <span>{label}</span>
          <span style={{ color: PMS_COLORS.text.secondary }}>{pct.toFixed(0)}%</span>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 5. PMSLayout — CSS grid container for dashboard layouts
// ---------------------------------------------------------------------------
function PMSLayout({ children }) {
  const layoutStyle = {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: PMS_SPACING.md,
    padding: PMS_SPACING.sm,
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
  };

  return <div style={layoutStyle}>{children}</div>;
}

// ---------------------------------------------------------------------------
// 6. PMSMetricCard — Tiny metric display for ticker strips
// ---------------------------------------------------------------------------
function PMSMetricCard({ label, value, change, prefix, suffix }) {
  const { pnlColor } = window.PMS_THEME;

  const containerStyle = {
    display: 'inline-flex',
    flexDirection: 'column',
    alignItems: 'flex-start',
    padding: '4px 10px',
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
    minWidth: '80px',
  };

  const labelStyle = {
    fontSize: PMS_TYPOGRAPHY.sizes.xs,
    color: PMS_COLORS.text.muted,
    textTransform: 'uppercase',
    letterSpacing: '0.04em',
    lineHeight: 1.2,
  };

  const valueStyle = {
    fontSize: PMS_TYPOGRAPHY.sizes.lg,
    fontWeight: PMS_TYPOGRAPHY.weights.bold,
    color: PMS_COLORS.text.primary,
    lineHeight: 1.3,
  };

  const changeStyle = {
    fontSize: PMS_TYPOGRAPHY.sizes.xs,
    color: change != null ? pnlColor(change) : PMS_COLORS.text.muted,
    lineHeight: 1.2,
  };

  const arrow = change != null
    ? (change > 0 ? '\u25B2' : change < 0 ? '\u25BC' : '')
    : '';

  const changeText = change != null
    ? `${arrow} ${change > 0 ? '+' : ''}${(typeof change === 'number' ? change.toFixed(2) : change)}`
    : '';

  return (
    <div style={containerStyle}>
      <span style={labelStyle}>{label}</span>
      <span style={valueStyle}>
        {prefix || ''}{value != null ? value : '--'}{suffix || ''}
      </span>
      {change != null && <span style={changeStyle}>{changeText}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 7. PMSSkeleton — Loading placeholder with pulse animation
// ---------------------------------------------------------------------------
function PMSSkeleton({ width, height, className }) {
  const skeletonStyle = {
    width: width || '100%',
    height: height || '16px',
    backgroundColor: PMS_COLORS.bg.tertiary,
    borderRadius: '4px',
    animation: 'pulse 1.5s ease-in-out infinite',
  };

  return <div style={skeletonStyle} className={className || ''} />;
}

// ---------------------------------------------------------------------------
// 8. PMSAlertBanner — Sticky top banner for active alerts
// ---------------------------------------------------------------------------
function PMSAlertBanner({ alerts, onDismiss }) {
  if (!alerts || alerts.length === 0) return null;

  const { riskColor } = window.PMS_THEME;

  const bannerContainerStyle = {
    position: 'sticky',
    top: 0,
    zIndex: 30,
    display: 'flex',
    flexDirection: 'column',
    gap: '2px',
    fontFamily: PMS_TYPOGRAPHY.fontFamily,
  };

  return (
    <div style={bannerContainerStyle}>
      {alerts.map((alert, idx) => {
        const severity = alert.severity || alert.level || 'warning';
        const bgColor = riskColor(severity);

        const alertStyle = {
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '6px 12px',
          backgroundColor: bgColor,
          color: PMS_COLORS.text.inverse,
          fontSize: PMS_TYPOGRAPHY.sizes.sm,
          fontWeight: PMS_TYPOGRAPHY.weights.medium,
        };

        const dismissStyle = {
          background: 'none',
          border: 'none',
          color: PMS_COLORS.text.inverse,
          cursor: 'pointer',
          fontSize: PMS_TYPOGRAPHY.sizes.base,
          padding: '0 4px',
          lineHeight: 1,
          opacity: 0.8,
        };

        return (
          <div key={alert.id || idx} style={alertStyle}>
            <span>{alert.message || alert.text || String(alert)}</span>
            {onDismiss && (
              <button
                style={dismissStyle}
                onClick={() => onDismiss(alert.id || idx)}
                title="Dismiss"
                onMouseEnter={(e) => { e.currentTarget.style.opacity = 1; }}
                onMouseLeave={(e) => { e.currentTarget.style.opacity = 0.8; }}
              >
                x
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 9. PMSSampleDataBanner — Sticky banner when using fallback data
// ---------------------------------------------------------------------------
function PMSSampleDataBanner() {
  return (
    <div style={{
      backgroundColor: '#d29922',
      color: '#0d1117',
      padding: '4px 12px',
      fontSize: PMS_TYPOGRAPHY.sizes.xs,
      fontFamily: PMS_TYPOGRAPHY.fontFamily,
      fontWeight: PMS_TYPOGRAPHY.weights.semibold,
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      textAlign: 'center',
      position: 'sticky',
      top: 0,
      zIndex: 25,
    }}>
      SAMPLE DATA — API unavailable, displaying demonstration data
    </div>
  );
}

// ---------------------------------------------------------------------------
// 10. PMSEmptyState — Empty state placeholder when no data available
// ---------------------------------------------------------------------------
function PMSEmptyState({ message, subtitle }) {
  return (
    <div style={{
      padding: '40px 20px',
      textAlign: 'center',
      color: PMS_COLORS.text.muted,
      fontFamily: PMS_TYPOGRAPHY.fontFamily,
    }}>
      <div style={{
        fontSize: PMS_TYPOGRAPHY.sizes.lg,
        fontWeight: PMS_TYPOGRAPHY.weights.semibold,
        marginBottom: '8px',
      }}>
        {message || 'No data available'}
      </div>
      {subtitle && (
        <div style={{ fontSize: PMS_TYPOGRAPHY.sizes.sm }}>
          {subtitle}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Export all components on window for CDN/Babel compatibility
// ---------------------------------------------------------------------------
window.PMSCard = PMSCard;
window.PMSTable = PMSTable;
window.PMSBadge = PMSBadge;
window.PMSGauge = PMSGauge;
window.PMSLayout = PMSLayout;
window.PMSMetricCard = PMSMetricCard;
window.PMSSkeleton = PMSSkeleton;
window.PMSAlertBanner = PMSAlertBanner;
window.PMSSampleDataBanner = PMSSampleDataBanner;
window.PMSEmptyState = PMSEmptyState;
