/**
 * Sidebar.jsx - Collapsible sidebar navigation for the Macro Trading Dashboard.
 *
 * Features:
 * - Mode switch: Dashboard (5 items) vs PMS (7 items)
 * - Collapse/expand toggle (icons only vs icons + labels)
 * - Active item highlighted (bg-blue-600)
 * - Alert badge count on Risk item
 * - PMS mode uses Bloomberg-dense dark styling
 */

const { useState } = React;
const { NavLink } = window.ReactRouterDOM;

// ---------------------------------------------------------------------------
// SVG icon components (inline, lightweight)
// ---------------------------------------------------------------------------
function IconChartBar() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("rect", { x: "3", y: "12", width: "4", height: "8", rx: "1" }),
    React.createElement("rect", { x: "10", y: "8", width: "4", height: "12", rx: "1" }),
    React.createElement("rect", { x: "17", y: "4", width: "4", height: "16", rx: "1" })
  );
}

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
    className: "w-5 h-5 flex-shrink-0"
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

function IconList() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
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
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("path", { d: "M21.21 15.89A10 10 0 118 2.83" }),
    React.createElement("path", { d: "M22 12A10 10 0 0012 2v10z" })
  );
}

function IconSettings() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("circle", { cx: "12", cy: "12", r: "3" }),
    React.createElement("path", {
      d: "M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-2 2 2 2 0 01-2-2v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 01-2-2 2 2 0 012-2h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 010-2.83 2 2 0 012.83 0l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 012-2 2 2 0 012 2v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 0 2 2 0 010 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 012 2 2 2 0 01-2 2h-.09a1.65 1.65 0 00-1.51 1z"
    })
  );
}

function IconBook() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("path", { d: "M4 19.5A2.5 2.5 0 016.5 17H20" }),
    React.createElement("path", { d: "M6.5 2H20v20H6.5A2.5 2.5 0 014 19.5v-15A2.5 2.5 0 016.5 2z" })
  );
}

function IconClipboardCheck() {
  return React.createElement("svg", {
    xmlns: "http://www.w3.org/2000/svg", viewBox: "0 0 24 24", fill: "none",
    stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round", strokeLinejoin: "round",
    className: "w-5 h-5 flex-shrink-0"
  },
    React.createElement("path", { d: "M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2" }),
    React.createElement("rect", { x: "8", y: "2", width: "8", height: "4", rx: "1" }),
    React.createElement("path", { d: "M9 14l2 2 4-4" })
  );
}

// ---------------------------------------------------------------------------
// Navigation items definitions
// ---------------------------------------------------------------------------
const NAV_ITEMS = [
  { to: "/strategies", label: "Strategies", Icon: IconChartBar },
  { to: "/signals",    label: "Signals",    Icon: IconActivity },
  { to: "/risk",       label: "Risk",       Icon: IconShield },
  { to: "/portfolio",  label: "Portfolio",   Icon: IconBriefcase },
  { to: "/agents",     label: "Agents",     Icon: IconCpu },
];

const PMS_NAV_ITEMS = [
  { to: "/pms/morning-pack", label: "Morning Pack",      Icon: IconSunrise },
  { to: "/pms/portfolio",    label: "Portfolio",          Icon: IconBriefcase },
  { to: "/pms/risk",         label: "Risk",              Icon: IconShield },
  { to: "/pms/blotter",      label: "Trade Blotter",     Icon: IconList },
  { to: "/pms/attribution",  label: "Attribution",       Icon: IconPieChart },
  { to: "/pms/journal",      label: "Decision Journal",  Icon: IconBook },
  { to: "/pms/agents",       label: "Agent Intel",       Icon: IconCpu },
  { to: "/pms/compliance",   label: "Compliance",        Icon: IconClipboardCheck },
];

// ---------------------------------------------------------------------------
// Sidebar component with Dashboard/PMS mode switch
// ---------------------------------------------------------------------------
function Sidebar({ alertCount = 0, pmsMode = false, onModeChange }) {
  const [collapsed, setCollapsed] = useState(false);

  const activeNavItems = pmsMode ? PMS_NAV_ITEMS : NAV_ITEMS;
  const sidebarBg = pmsMode ? { backgroundColor: '#0d1117' } : {};

  return (
    <div
      className={`text-white flex flex-col h-screen fixed left-0 top-0 z-40 border-r border-gray-800 transition-all duration-200 ${
        collapsed ? "w-16" : "w-56"
      } ${!pmsMode ? "bg-gray-900" : ""}`}
      style={sidebarBg}
    >
      {/* Logo / Brand area with mode switch */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-800">
        <span className="text-green-500 font-mono text-xl font-bold flex-shrink-0">MT</span>
        {!collapsed && onModeChange && (
          <div className="flex bg-gray-800 rounded-md p-0.5">
            <button
              onClick={() => onModeChange(false)}
              className={`px-2 py-1 text-xs rounded ${!pmsMode ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
            >
              Dashboard
            </button>
            <button
              onClick={() => onModeChange(true)}
              className={`px-2 py-1 text-xs rounded ${pmsMode ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-gray-200'}`}
            >
              PMS
            </button>
          </div>
        )}
        {collapsed && onModeChange && (
          <button
            onClick={() => onModeChange(!pmsMode)}
            className="text-xs px-1 py-0.5 rounded bg-gray-800 text-gray-400 hover:text-gray-200"
            title={pmsMode ? "Switch to Dashboard" : "Switch to PMS"}
          >
            {pmsMode ? "P" : "D"}
          </button>
        )}
      </div>

      {/* Navigation items */}
      <nav className="flex-1 py-3 space-y-1 overflow-y-auto">
        {activeNavItems.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-4 py-2.5 mx-2 rounded-lg transition-colors relative ${
                isActive
                  ? "bg-blue-600 text-white"
                  : "text-gray-400 hover:bg-gray-800 hover:text-gray-200"
              }`
            }
          >
            <Icon />
            {!collapsed && (
              <span className="text-sm truncate">{label}</span>
            )}
            {/* Badge count on Risk item (both modes) */}
            {(to === "/risk" || to === "/pms/risk") && alertCount > 0 && (
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

      {/* Collapse toggle button */}
      <div className="border-t border-gray-800 p-2">
        <button
          onClick={() => setCollapsed(!collapsed)}
          className="flex items-center justify-center w-full py-2 rounded-lg text-gray-400 hover:bg-gray-800 hover:text-gray-200 transition-colors"
          title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        >
          {collapsed ? <IconChevronRight /> : <IconChevronLeft />}
          {!collapsed && (
            <span className="ml-2 text-sm">Collapse</span>
          )}
        </button>
      </div>
    </div>
  );
}

// Expose on window for CDN/Babel compatibility
window.Sidebar = Sidebar;
