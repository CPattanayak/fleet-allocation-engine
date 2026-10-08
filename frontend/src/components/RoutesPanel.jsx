import { Fragment, useMemo, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { selectOrder, selectTruck } from "../store/uiSlice";
import { fmtTime, num, truckColorMap } from "../utils/format";

/** Per-truck route cards plus the explained assignment log and unassigned list. */
export default function RoutesPanel({ scenario, result }) {
  const dispatch = useDispatch();
  const { selectedTruckId, selectedOrderId } = useSelector((s) => s.ui);
  const [tab, setTab] = useState("routes");
  const colors = useMemo(() => truckColorMap(scenario.trucks), [scenario]);
  const byOrder = useMemo(() => Object.fromEntries(scenario.orders.map((o) => [o.id, o])), [scenario]);
  const trucks = Object.fromEntries(scenario.trucks.map((t) => [t.id, t]));

  const assignments = result.assignments.filter((a) => !selectedTruckId || a.truck_id === selectedTruckId);
  const routes = result.routes.filter((r) => !selectedTruckId || r.truck_id === selectedTruckId);

  return (
    <div className="panel">
      <div className="tabs">
        <button className={tab === "routes" ? "on" : ""} onClick={() => setTab("routes")}>Routes ({result.routes.length})</button>
        <button className={tab === "log" ? "on" : ""} onClick={() => setTab("log")}>Decisions ({result.assignments.length})</button>
        <button className={tab === "unassigned" ? "on" : ""} onClick={() => setTab("unassigned")}>
          Unassigned <span className={result.unassigned.length ? "pill bad" : "pill"}>{result.unassigned.length}</span>
        </button>
        {selectedTruckId && (
          <button className="filter-chip" onClick={() => dispatch(selectTruck(selectedTruckId))}>
            {selectedTruckId} ✕
          </button>
        )}
      </div>

      {tab === "routes" && (
        <div className="route-list">
          {routes.map((r) => {
            const t = trucks[r.truck_id];
            return (
              <div key={r.truck_id} className={`route-card ${selectedTruckId === r.truck_id ? "sel" : ""}`}
                onClick={() => dispatch(selectTruck(r.truck_id))}>
                <div className="route-head">
                  <span className="swatch" style={{ background: colors[r.truck_id] }} />
                  <b>{r.truck_id}</b> <span className="muted">{t && t.name}</span>
                  <span className="route-stat">{num(r.total_distance_km)} km · back {fmtTime(r.end_time)}</span>
                </div>
                <div className="loadbar"><div style={{ width: `${(r.load_kg / r.capacity_kg) * 100}%`, background: colors[r.truck_id] }} /></div>
                <div className="muted small">{num(r.load_kg, 0)} / {r.capacity_kg} kg · {r.stops.length}/{t ? t.max_stops : "?"} stops</div>
                <div className="stops">
                  <span className="stop depot">{t ? fmtTime(t.shift_start) : ""}</span>
                  {r.stops.map((s) => (
                    <Fragment key={s.order_id}>
                      <span className="arrow">→</span>
                      <span
                        className={`stop ${byOrder[s.order_id] && byOrder[s.order_id].priority === 3 ? "urgent" : ""} ${selectedOrderId === s.order_id ? "sel" : ""}`}
                        title={`arrive ${fmtTime(s.arrival)}, serve ${fmtTime(s.service_start)}`}
                        onClick={(e) => { e.stopPropagation(); dispatch(selectOrder({ orderId: s.order_id, truckId: r.truck_id })); }}
                      >
                        {s.order_id} <small>{fmtTime(s.service_start)}</small>
                      </span>
                    </Fragment>
                  ))}
                </div>
              </div>
            );
          })}
          {!routes.length && <p className="muted">No routes.</p>}
        </div>
      )}

      {tab === "log" && (
        <table className="table">
          <thead>
            <tr><th>Order</th><th>Truck</th><th>Rnd</th><th>ETA</th><th>Cost</th><th>Why</th></tr>
          </thead>
          <tbody>
            {assignments.map((a) => (
              <tr key={a.order_id} className={selectedOrderId === a.order_id ? "sel" : ""}
                onClick={() => dispatch(selectOrder({ orderId: a.order_id, truckId: a.truck_id }))}>
                <td className="mono">{a.order_id}</td>
                <td><span className="swatch" style={{ background: colors[a.truck_id] }} /> {a.truck_id}</td>
                <td className="mono">{a.round}</td>
                <td className="mono">{fmtTime(a.eta)}</td>
                <td className="mono">{num(a.cost)}</td>
                <td className="expl">{a.explanation}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {tab === "unassigned" && (
        <table className="table">
          <thead><tr><th>Order</th><th>Needs</th><th>Reason</th></tr></thead>
          <tbody>
            {result.unassigned.map((u) => {
              const o = byOrder[u.order_id];
              return (
                <tr key={u.order_id} className={selectedOrderId === u.order_id ? "sel" : ""}
                  onClick={() => dispatch(selectOrder({ orderId: u.order_id }))}>
                  <td className="mono">{u.order_id}</td>
                  <td className="small">{o ? `${o.weight_kg} kg ${o.required_capabilities.join(", ")}` : ""}</td>
                  <td className="expl">{u.reason}</td>
                </tr>
              );
            })}
            {!result.unassigned.length && <tr><td colSpan={3} className="muted">Every order was served.</td></tr>}
          </tbody>
        </table>
      )}
    </div>
  );
}
