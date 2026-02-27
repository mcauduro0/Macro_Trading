/**
 * Sidebar.jsx - PMS sidebar navigation for ARC Macro.
 *
 * Features:
 * - PMS-only navigation (8 items) — Dashboard mode removed per review
 * - Collapse/expand toggle (icons only vs icons + labels)
 * - Active item highlighted with accent color
 * - Alert badge count on Risk item
 * - Bloomberg-dense dark styling using PMS design tokens
 */

const { useState } = React;
const { NavLink } = window.ReactRouterDOM;

// ---------------------------------------------------------------------------
// SVG icon components (inline, lightweight)
// ---------------------------------------------------------------------------
function IconSunrise() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("path", { d: "M17 18a5 5 0 00-10 0" }),
    React.createElement("line", { x1: "12", y1: "9", x2: "12", y2: "2" }),
    React.createElement("line", { x1: "4.22", y1: "10.22", x2: "5.64", y2: "11.64" }),
    React.createElement("line", { x1: "1", y1: "18", x2: "3", y2: "18" }),
    React.createElement("line", { x1: "21", y1: "18", x2: "23", y2: "18" }),
    React.createElement("line", { x1: "18.36", y1: "11.64", x2: "19.78", y2: "10.22" }),
    React.createElement("line", { x1: "23", y1: "22", x2: "1", y2: "22" }),
    React.createElement("polyline", { points: "8 6 12 2 16 6" })
  );
}

function IconBriefcase() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("rect", { x: "2", y: "7", width: "20", height: "14", rx: "2" }),
    React.createElement("path", { d: "M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16" })
  );
}

function IconShield() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("path", { d: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" })
  );
}

function IconList() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("line", { x1: "8", y1: "6", x2: "21", y2: "6" }),
    React.createElement("line", { x1: "8", y1: "12", x2: "21", y2: "12" }),
    React.createElement("line", { x1: "8", y1: "18", x2: "21", y2: "18" }),
    React.createElement("line", { x1: "3", y1: "6", x2: "3.01", y2: "6" }),
    React.createElement("line", { x1: "3", y1: "12", x2: "3.01", y2: "12" }),
    React.createElement("line", { x1: "3", y1: "18", x2: "3.01", y2: "18" })
  );
}

function IconPieChart() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("path", { d: "M21.21 15.89A10 10 0 118 2.83" }),
    React.createElement("path", { d: "M22 12A10 10 0 0012 2v10z" })
  );
}

function IconCpu() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("rect", { x: "4", y: "4", width: "16", height: "16", rx: "2" }),
    React.createElement("rect", { x: "9", y: "9", width: "6", height: "6" }),
    React.createElement("line", { x1: "9", y1: "1", x2: "9", y2: "4" }),
    React.createElement("line", { x1: "15", y1: "1", x2: "15", y2: "4" }),
    React.createElement("line", { x1: "9", y1: "20", x2: "9", y2: "23" }),
    React.createElement("line", { x1: "15", y1: "20", x2: "15", y2: "23" }),
    React.createElement("line", { x1: "20", y1: "9", x2: "23", y2: "9" }),
    React.createElement("line", { x1: "20", y1: "14", x2: "23", y2: "14" }),
    React.createElement("line", { x1: "1", y1: "9", x2: "4", y2: "9" }),
    React.createElement("line", { x1: "1", y1: "14", x2: "4", y2: "14" })
  );
}

function IconBook() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("path", { d: "M4 19.5A2.5 2.5 0 016.5 17H20" }),
    React.createElement("path", { d: "M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" })
  );
}

function IconClipboardCheck() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18, style: { flexShrink: 0 }
  },
    React.createElement("path", { d: "M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" }),
    React.createElement("rect", { x: "8", y: "2", width: "8", height: "4", rx: "1" }),
    React.createElement("path", { d: "M9 14l2 2 4-4" })
  );
}

function IconChevronLeft() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18
  },
    React.createElement("polyline", { points: "15 18 9 12 15 6" })
  );
}

function IconChevronRight() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    width: 18, height: 18
  },
    React.createElement("polyline", { points: "9 18 15 12 9 6" })
  );
}

// ---------------------------------------------------------------------------
// Navigation items — PMS only
// ---------------------------------------------------------------------------
const PMS_NAV_ITEMS = [
  { to: "/pms/morning-pack", label: "Morning Pack",      Icon: IconSunrise },
  { to: "/pms/portfolio",    label: "Position Book",     Icon: IconBriefcase },
  { to: "/pms/risk",         label: "Risk Monitor",      Icon: IconShield },
  { to: "/pms/blotter",      label: "Trade Blotter",     Icon: IconList },
  { to: "/pms/attribution",  label: "Attribution",       Icon: IconPieChart },
  { to: "/pms/journal",      label: "Decision Journal",  Icon: IconBook },
  { to: "/pms/agents",       label: "Agent Intel",       Icon: IconCpu },
  { to: "/pms/compliance",   label: "Compliance",        Icon: IconClipboardCheck },
];

// ---------------------------------------------------------------------------
// Sidebar component — PMS-only navigation
// ---------------------------------------------------------------------------
function Sidebar({ alertCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false);
  const { PMS_COLORS: _C, PMS_TYPOGRAPHY: _T } = window.PMS_THEME;

  const sidebarStyle = {
    display: 'flex',
    flexDirection: 'column',
    height: '100vh',
    position: 'fixed',
    left: 0,
    top: 0,
    zIndex: 40,
    width: collapsed ? '56px' : '224px',
    backgroundColor: _C.bg.secondary,
    borderRight: '1px solid ' + _C.border.default,
    transition: 'width 0.2s ease',
    fontFamily: _T.fontFamily,
    color: _C.text.primary,
  };

  const brandStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: collapsed ? 'center' : 'flex-start',
    padding: collapsed ? '12px 8px' : '12px 16px',
    borderBottom: '1px solid ' + _C.border.default,
    gap: '8px',
  };

  const brandTextStyle = {
    fontSize: _T.sizes.lg,
    fontWeight: _T.weights.bold,
    color: _C.pnl.positive,
    letterSpacing: '0.05em',
  };

  const navStyle = {
    flex: 1,
    padding: '8px 0',
    overflowY: 'auto',
  };

  const getNavItemStyle = (isActive) => ({
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
    padding: collapsed ? '8px 0' : '8px 12px',
    margin: '2px 6px',
    borderRadius: '6px',
    textDecoration: 'none',
    fontSize: _T.sizes.sm,
    fontWeight: isActive ? _T.weights.semibold : _T.weights.medium,
    color: isActive ? _C.text.primary : _C.text.secondary,
    backgroundColor: isActive ? _C.border.accent : 'transparent',
    cursor: 'pointer',
    transition: 'background-color 0.15s, color 0.15s',
    position: 'relative',
    justifyContent: collapsed ? 'center' : 'flex-start',
  });

  const collapseStyle = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '8px',
    borderTop: '1px solid ' + _C.border.default,
    cursor: 'pointer',
    color: _C.text.muted,
    background: 'none',
    border: 'none',
    width: '100%',
    fontFamily: _T.fontFamily,
    fontSize: _T.sizes.sm,
    gap: '6px',
  };

  const badgeStyle = {
    position: 'absolute',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#ef4444',
    color: '#fff',
    fontSize: '10px',
    fontWeight: _T.weights.bold,
    borderRadius: '9px',
    minWidth: collapsed ? '14px' : '18px',
    height: collapsed ? '14px' : '18px',
    padding: '0 4px',
    top: collapsed ? '-2px' : '50%',
    right: collapsed ? '-2px' : '6px',
    transform: collapsed ? 'none' : 'translateY(-50%)',
  };

  return (
    <div style={sidebarStyle}>
      {/* Brand */}
      <div style={brandStyle}>
        <span style={brandTextStyle}>ARC</span>
        {!collapsed && (
          <span style={{ fontSize: _T.sizes.xs, color: _C.text.muted, letterSpacing: '0.08em' }}>MACRO</span>
        )}
      </div>

      {/* Navigation */}
      <nav style={navStyle}>
        {PMS_NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => getNavItemStyle(isActive)}
            title={collapsed ? label : undefined}
          >
            <Icon />
            {!collapsed && <span>{label}</span>}
            {to === "/pms/risk" && alertCount > 0 && (
              <span style={badgeStyle}>
                {alertCount > 99 ? "99+" : alertCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      {/* Collapse toggle */}
      <button
        onClick={() => setCollapsed(!collapsed)}
        style={collapseStyle}
        title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
      >
        {collapsed ? <IconChevronRight /> : <IconChevronLeft />}
        {!collapsed && <span>Collapse</span>}
      </button>
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.Sidebar = Sidebar;
