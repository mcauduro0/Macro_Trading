/**
 * Sidebar.jsx - Collapsible sidebar navigation for the Macro Trading PMS.
 *
 * Features:
 * - PMS-only navigation (9 items including Signals)
 * - Collapse/expand toggle (icons only vs icons + labels)
 * - Active item highlighted with accent color
 * - Alert badge count on Risk item
 * - Bloomberg-dense dark styling (#0d1117)
 */

const { useState } = React;
const { NavLink } = window.ReactRouterDOM;

// ---------------------------------------------------------------------------
// SVG icon components (inline, lightweight)
// ---------------------------------------------------------------------------
function IconActivity() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("polyline", { points: "22 12 18 12 15 21 9 3 6 12 2 12" })
  );
}

function IconShield() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("path", { d: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" })
  );
}

function IconBriefcase() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("rect", { x: "2", y: "7", width: "20", height: "14", rx: "2" }),
    React.createElement("path", { d: "M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16" })
  );
}

function IconCpu() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
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

function IconChevronLeft() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5"
  },
    React.createElement("polyline", { points: "15 18 9 12 15 6" })
  );
}

function IconChevronRight() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5"
  },
    React.createElement("polyline", { points: "9 18 15 12 9 6" })
  );
}

// ---------------------------------------------------------------------------
// PMS-specific SVG icon components
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

// ---------------------------------------------------------------------------
// Navigation items — PMS only (9 items)
// ---------------------------------------------------------------------------
const PMS_NAV_ITEMS = [
  { to: "/pms/morning-pack", label: "Morning Pack",      Icon: IconSunrise },
  { to: "/pms/portfolio",    label: "Position Book",     Icon: IconBriefcase },
  { to: "/pms/blotter",      label: "Trade Blotter",     Icon: IconList },
  { to: "/pms/signals",      label: "Signals",           Icon: IconActivity },
  { to: "/pms/risk",         label: "Risk Monitor",      Icon: IconShield },
  { to: "/pms/attribution",  label: "Attribution",       Icon: IconPieChart },
  { to: "/pms/journal",      label: "Decision Journal",  Icon: IconBook },
  { to: "/pms/agents",       label: "Agent Intel",       Icon: IconCpu },
  { to: "/pms/compliance",   label: "Compliance",        Icon: IconClipboardCheck },
];

// ---------------------------------------------------------------------------
// Sidebar component — PMS-only, Bloomberg dark theme
// ---------------------------------------------------------------------------
function Sidebar({ alertCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false);
  const { PMS_COLORS: _C, PMS_TYPOGRAPHY: _T } = window.PMS_THEME;

  return (
    <div
      className={`text-white flex flex-col h-screen fixed left-0 top-0 z-40 border-r border-gray-800 transition-all duration-200 ${
        collapsed ? "w-16" : "w-56"
      }`}
      style={{ backgroundColor: '#0d1117' }}
    >
      {/* Logo / Brand area */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-green-500 font-mono text-xl font-bold flex-shrink-0">MT</span>
        {!collapsed && (
          <span className="text-gray-500 text-xs font-mono uppercase tracking-wider">PMS</span>
        )}
      </div>

      {/* Navigation items */}
      <nav className="flex-1 py-3 space-y-1 overflow-y-auto">
        {PMS_NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => getNavItemStyle(isActive)}
            title={collapsed ? label : undefined}
          >
            <Icon />
            {!collapsed && (
              <span className="text-sm truncate">{label}</span>
            )}
            {/* Badge count on Risk item */}
            {to === "/pms/risk" && alertCount > 0 && (
              <span
                className={`absolute flex items-center justify-center bg-red-500 text-white text-xs font-bold rounded-full ${
                  collapsed
                    ? "w-4 h-4 top-0 right-0 text-[10px]"
                    : "w-5 h-5 right-2"
                }`}
              >
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
