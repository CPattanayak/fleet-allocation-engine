import { NavLink } from "react-router-dom";
import { useSelector } from "react-redux";

/** Main navigation: Setup first, then one tab per algorithm, then the side-by-side view. */
export default function TopTabs() {
  const { results, status } = useSelector((s) => s.allocation);
  const scenario = useSelector((s) => s.scenario.current);
  const served = (algo) => {
    const r = results[algo];
    if (status[algo] === "loading") return "…";
    return r ? `${r.metrics.assigned_orders}/${r.metrics.total_orders}` : null;
  };

  const tabs = [
    { to: "/setup", label: "Setup", key: "setup",
      badge: scenario ? `${scenario.trucks.length} trucks · ${scenario.orders.length} orders` : null },
    { to: "/greedy", label: "Greedy", key: "greedy", badge: served("greedy") },
    { to: "/hungarian", label: "Hungarian", key: "hungarian", badge: served("hungarian") },
    { to: "/compare", label: "Compare", key: "compare", badge: null },
  ];

  return (
    <nav className="top-tabs">
      {tabs.map((t) => (
        <NavLink key={t.to} to={t.to} className={({ isActive }) => `top-tab ${t.key} ${isActive ? "active" : ""}`}>
          <i className="nav-dot" />
          {t.label}
          {t.badge && <span className="tab-badge">{t.badge}</span>}
        </NavLink>
      ))}
    </nav>
  );
}
