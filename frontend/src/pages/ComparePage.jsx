import { useEffect, useMemo } from "react";
import { useDispatch, useSelector } from "react-redux";
import { isRunnable, NeedsData } from "../components/EmptyState";
import FleetMap from "../components/FleetMap";
import { runCompare } from "../store/allocationSlice";
import { selectOrder } from "../store/uiSlice";
import { ALGO_META, diffAssignments, km, num, pct, truckColorMap } from "../utils/format";

const ROWS = [
  ["assigned_orders", "Orders served", (v) => v],
  ["fulfillment_rate", "Fulfillment rate", pct],
  ["priority_weighted_fulfillment", "Priority-weighted fulfillment", pct],
  ["urgent_fulfillment", "Urgent fulfillment", pct],
  ["total_distance_km", "Total distance", km],
  ["avg_distance_per_order_km", "Distance per order", km],
  ["total_wait_minutes", "Idle waiting (min)", (v) => num(v, 0)],
  ["avg_slack_minutes", "Avg slack to deadline (min)", (v) => num(v, 0)],
  ["avg_capacity_utilization", "Capacity utilisation", pct],
  ["load_balance_stddev", "Stops per truck σ", (v) => num(v, 2)],
  ["objective_cost", "Objective cost", (v) => num(v, 0)],
  ["runtime_ms", "Runtime (ms)", (v) => num(v, 1)],
];

function Bar({ value, max, color }) {
  const w = max > 0 ? Math.max(2, (value / max) * 100) : 0;
  return <div className="bar"><div style={{ width: `${w}%`, background: color }} /></div>;
}

export default function ComparePage() {
  const dispatch = useDispatch();
  const scenario = useSelector((s) => s.scenario.current);
  const { results, summary, status, wallTimeMs, paramsDirty, error } = useSelector((s) => s.allocation);
  const { greedy, hungarian } = results;
  const colors = useMemo(() => truckColorMap(scenario ? scenario.trucks : []), [scenario]);
  const diffs = useMemo(() => diffAssignments(greedy, hungarian), [greedy, hungarian]);

  const runnable = isRunnable(scenario);

  useEffect(() => {
    if (runnable && !summary && status.compare === "idle") dispatch(runCompare());
  }, [runnable, summary, status.compare, dispatch]);

  const wins = summary
    ? Object.values(summary).reduce((acc, r) => ({ ...acc, [r.winner]: (acc[r.winner] || 0) + 1 }), {})
    : {};

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Side by side</div>
          <h1>Greedy vs Hungarian</h1>
          <p className="muted">Same scenario, same constraints, same weights — only the assignment strategy differs.</p>
        </div>
        <div className="row gap">
          {paramsDirty && summary && <span className="hint">Parameters changed</span>}
          <button className="btn primary" disabled={!runnable || status.compare === "loading"} onClick={() => dispatch(runCompare())}>
            {status.compare === "loading" ? "Running both…" : "Run comparison"}
          </button>
        </div>
      </header>
      {error && status.compare === "error" && <div className="alert">{error}</div>}
      {!runnable && <NeedsData scenario={scenario} />}

      {summary && (
        <div className="scoreboard">
          <div className="score greedy"><span>{wins.greedy || 0}</span>metrics won by Greedy</div>
          <div className="score tie"><span>{wins.tie || 0}</span>ties</div>
          <div className="score hungarian"><span>{wins.hungarian || 0}</span>metrics won by Hungarian</div>
          <div className="score plain"><span>{diffs.length}</span>orders decided differently</div>
          <div className="score plain"><span>{num(wallTimeMs, 0)}</span>ms wall time (parallel)</div>
        </div>
      )}

      {runnable && <div className="compare-maps">
        {["greedy", "hungarian"].map((a) => (
          <div className="card" key={a}>
            <div className="card-title" style={{ borderColor: ALGO_META[a].accent }}>
              <b>{ALGO_META[a].label}</b>
              {results[a] && (
                <span className="muted">
                  {results[a].metrics.assigned_orders}/{results[a].metrics.total_orders} served ·{" "}
                  {km(results[a].metrics.total_distance_km)}
                </span>
              )}
            </div>
            <FleetMap scenario={scenario} result={results[a]} height={420} />
          </div>
        ))}
      </div>}

      {summary && greedy && hungarian && (
        <div className="split-even">
          <div className="card">
            <div className="card-title"><b>Metrics</b><span className="muted">winner highlighted</span></div>
            <table className="table compare-table">
              <thead><tr><th>Metric</th><th className="greedy-h">Greedy</th><th className="hungarian-h">Hungarian</th><th>Δ</th></tr></thead>
              <tbody>
                {ROWS.map(([key, label, fmt]) => {
                  const r = summary[key];
                  const g = greedy.metrics[key];
                  const h = hungarian.metrics[key];
                  const max = Math.max(Math.abs(g), Math.abs(h));
                  const delta = g === 0 ? null : ((h - g) / Math.abs(g)) * 100;
                  return (
                    <tr key={key}>
                      <td>{label} <small className="muted">{r && r.lower_is_better ? "↓" : "↑"}</small></td>
                      <td className={r && r.winner === "greedy" ? "win greedy" : ""}>
                        <span className="mono">{fmt(g)}</span><Bar value={Math.abs(g)} max={max} color="var(--greedy)" />
                      </td>
                      <td className={r && r.winner === "hungarian" ? "win hungarian" : ""}>
                        <span className="mono">{fmt(h)}</span><Bar value={Math.abs(h)} max={max} color="var(--hungarian)" />
                      </td>
                      <td className="mono small">{delta == null ? "–" : `${delta > 0 ? "+" : ""}${delta.toFixed(1)}%`}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="card">
            <div className="card-title"><b>Where they disagree</b><span className="muted">{diffs.length} orders</span></div>
            <div className="scroll">
              <table className="table">
                <thead><tr><th>Order</th><th>Greedy</th><th>Hungarian</th><th>Cost G → H</th></tr></thead>
                <tbody>
                  {diffs.map((d) => (
                    <tr key={d.orderId} onClick={() => dispatch(selectOrder({ orderId: d.orderId }))}>
                      <td className="mono">{d.orderId}</td>
                      <td>{d.a ? <><span className="swatch" style={{ background: colors[d.a] }} /> {d.a}</> : <span className="pill bad">unserved</span>}</td>
                      <td>{d.b ? <><span className="swatch" style={{ background: colors[d.b] }} /> {d.b}</> : <span className="pill bad">unserved</span>}</td>
                      <td className="mono small">{num(d.costA)} → {num(d.costB)}</td>
                    </tr>
                  ))}
                  {!diffs.length && <tr><td colSpan={4} className="muted">Both strategies produced identical assignments.</td></tr>}
                </tbody>
              </table>
            </div>
            <p className="muted small note">
              Note: per-order costs are marginal (they depend on what is already on the route), so a higher
              cost for one order can still mean a lower total.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
