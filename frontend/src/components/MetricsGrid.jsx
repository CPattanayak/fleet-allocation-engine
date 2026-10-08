import { km, num, pct } from "../utils/format";

const TILES = [
  ["fulfillment_rate", "Fulfilled", pct, (m) => `${m.assigned_orders}/${m.total_orders} orders`],
  ["priority_weighted_fulfillment", "Priority-weighted", pct, (m) => `urgent ${pct(m.urgent_fulfillment)}`],
  ["total_distance_km", "Total distance", km, (m) => `${num(m.avg_distance_per_order_km)} km / order`],
  ["total_wait_minutes", "Idle waiting", (v) => `${num(v, 0)} min`, (m) => `avg slack ${num(m.avg_slack_minutes, 0)} min`],
  ["fleet_utilization", "Fleet used", pct, (m) => `${m.trucks_used} trucks · load ${pct(m.avg_capacity_utilization)}`],
  ["load_balance_stddev", "Stops σ", (v) => num(v, 2), () => "lower = more balanced"],
  ["objective_cost", "Objective", (v) => num(v, 0), () => "soft cost + unserved penalty"],
  ["runtime_ms", "Runtime", (v) => `${num(v, 1)} ms`, (m) => `${m.rounds} round(s)`],
];

export default function MetricsGrid({ metrics }) {
  if (!metrics) return null;
  return (
    <div className="metrics-grid">
      {TILES.map(([key, label, fmt, sub]) => (
        <div className="metric" key={key}>
          <div className="metric-label">{label}</div>
          <div className="metric-value">{fmt(metrics[key])}</div>
          <div className="metric-sub">{sub(metrics)}</div>
        </div>
      ))}
    </div>
  );
}
