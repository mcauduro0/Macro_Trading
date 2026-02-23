/**
 * Sidebar.jsx - Collapsible sidebar navigation for the Macro Trading Dashboard.
 *
 * Features:
 * - 5 navigation items: Strategies, Signals, Risk, Portfolio, Agents
 * - Collapse/expand toggle (icons only vs icons + labels)
 * - Active item highlighted (bg-blue-600)
 * - Alert badge count on Risk item
 */

const { useState } = React;
const { NavLink } = window.ReactRouterDOM;

// SVG icon components (inline, lightweight)
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

// Navigation items definition
const NAV_ITEMS = [
  { to: "/strategies", label: "Strategies", Icon: IconChartBar },
  { to: "/signals",    label: "Signals",    Icon: IconActivity },
  { to: "/risk",       label: "Risk",       Icon: IconShield },
  { to: "/portfolio",  label: "Portfolio",   Icon: IconBriefcase },
  { to: "/agents",     label: "Agents",     Icon: IconCpu },
];

function Sidebar({ alertCount = 0 }) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={`bg-gray-900 text-white flex flex-col h-screen fixed left-0 top-0 z-40 border-r border-gray-800 transition-all duration-200 ${
        collapsed ? "w-16" : "w-56"
      }`}
    >
      {/* Logo / Brand area */}
      <div className="flex items-center gap-2 px-4 py-4 border-b border-gray-800">
        <span className="text-green-500 font-mono text-xl font-bold flex-shrink-0">MT</span>
        {!collapsed && (
          <span className="text-gray-300 text-sm font-semibold truncate">
            Macro Trading
          </span>
        )}
      </div>

      {/* Navigation items */}
      <nav className="flex-1 py-3 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
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
            {/* Badge count on Risk item */}
            {to === "/risk" && alertCount > 0 && (
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
