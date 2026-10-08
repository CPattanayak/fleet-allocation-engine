import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import FleetMap from "../components/FleetMap";
import OrderForm from "../components/OrderForm";
import TruckForm from "../components/TruckForm";
import {
  addOrder, addRandomOrders, addTruck, deleteOrder, deleteTruck, toggleTruck, updateOrder, updateTruck,
} from "../store/scenarioSlice";
import { selectOrder, selectTruck } from "../store/uiSlice";
import { fmtTime, fmtWindow, PRIORITY_LABEL, truckColorMap } from "../utils/format";

/** Build the scenario by hand: add / edit / remove trucks and orders. */
export default function SetupPage() {
  const dispatch = useDispatch();
  const scenario = useSelector((s) => s.scenario.current);
  const busy = useSelector((s) => s.scenario.busy);
  const { selectedTruckId, selectedOrderId } = useSelector((s) => s.ui);
  const [tab, setTab] = useState("trucks");          // which list + form is showing
  const [editingTruck, setEditingTruck] = useState(null);
  const [editingOrder, setEditingOrder] = useState(null);
  const [picked, setPicked] = useState(null);          // last map click

  if (!scenario) return <div className="loading">Loading scenario…</div>;
  const colors = truckColorMap(scenario.trucks);

  // run a store action; return true if it worked (forms reset on success)
  const run = (action) => dispatch(action).unwrap().then(() => { setPicked(null); return true; }).catch(() => false);

  const saveTruck = (truck) => run(editingTruck ? updateTruck(truck) : addTruck(truck))
    .then((ok) => { if (ok) setEditingTruck(null); return ok; });
  const saveOrder = (order) => run(editingOrder ? updateOrder(order) : addOrder(order))
    .then((ok) => { if (ok) setEditingOrder(null); return ok; });

  const exportJson = () => {
    const data = { name: scenario.name, city: scenario.city.id, trucks: scenario.trucks, orders: scenario.orders };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `${scenario.name.replace(/[^\w-]+/g, "_")}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const showTab = (t) => { setTab(t); setPicked(null); };

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">Step 1</div>
          <h1>Set up {scenario.name}</h1>
          <p className="muted">Add trucks and orders, then open the Greedy or Hungarian tab. Click the map to pick a location.</p>
        </div>
        <div className="row gap">
          <button className="btn ghost" disabled={busy} onClick={() => dispatch(addRandomOrders(10))}>+10 random orders</button>
          <button className="btn ghost" onClick={exportJson}>Export JSON</button>
        </div>
      </header>

      <div className="split">
        <div className="card map-card">
          <FleetMap scenario={scenario} height={640} onMapClick={setPicked} cursor="crosshair" previewPoint={picked} />
        </div>

        <div className="card side-card tall">
          <div className="tabs">
            <button className={tab === "trucks" ? "on" : ""} onClick={() => showTab("trucks")}>Trucks ({scenario.trucks.length})</button>
            <button className={tab === "orders" ? "on" : ""} onClick={() => showTab("orders")}>Orders ({scenario.orders.length})</button>
          </div>

          {tab === "trucks" ? (
            <>
              <TruckForm editing={editingTruck} picked={picked} busy={busy}
                onSubmit={saveTruck} onCancel={() => setEditingTruck(null)} />
              <div className="scroll">
                <table className="table">
                  <thead><tr><th>Truck</th><th>Payload</th><th>Shift</th><th>Caps</th><th /></tr></thead>
                  <tbody>
                    {scenario.trucks.map((t) => (
                      <tr key={t.id} className={`${selectedTruckId === t.id ? "sel" : ""} ${t.available ? "" : "off"}`}
                        onClick={() => dispatch(selectTruck(t.id))}>
                        <td><span className="swatch" style={{ background: colors[t.id] }} /> <b>{t.id}</b><div className="muted small">{t.name}</div></td>
                        <td className="mono small">{t.capacity_kg} kg<br />≤{t.max_stops} stops</td>
                        <td className="mono small">{fmtTime(t.shift_start)}–{fmtTime(t.shift_end)}</td>
                        <td className="small">{t.capabilities.join(", ") || "–"}</td>
                        <td className="actions">
                          <button className="link" onClick={(e) => { e.stopPropagation(); setEditingTruck(t); }}>edit</button>
                          <button className="link" disabled={busy} onClick={(e) => { e.stopPropagation(); dispatch(toggleTruck(t)); }}>{t.available ? "off duty" : "on duty"}</button>
                          <button className="link danger" disabled={busy} onClick={(e) => { e.stopPropagation(); dispatch(deleteTruck(t.id)); }}>remove</button>
                        </td>
                      </tr>
                    ))}
                    {!scenario.trucks.length && <tr><td colSpan={5} className="muted">No trucks yet. Click the map, then "Add truck".</td></tr>}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <>
              <OrderForm editing={editingOrder} picked={picked} busy={busy}
                onSubmit={saveOrder} onCancel={() => setEditingOrder(null)} />
              <div className="scroll">
                <table className="table">
                  <thead><tr><th>Order</th><th>kg</th><th>Window</th><th>Prio</th><th>Needs</th><th /></tr></thead>
                  <tbody>
                    {scenario.orders.map((o) => (
                      <tr key={o.id} className={selectedOrderId === o.id ? "sel" : ""} onClick={() => dispatch(selectOrder({ orderId: o.id }))}>
                        <td><b className="mono">{o.id}</b><div className="muted small">{o.customer}</div></td>
                        <td className="mono small">{o.weight_kg}</td>
                        <td className="mono small">{fmtWindow(o)}</td>
                        <td><span className={`pill p${o.priority}`}>{PRIORITY_LABEL[o.priority]}</span></td>
                        <td className="small">{o.required_capabilities.join(", ") || "–"}</td>
                        <td className="actions">
                          <button className="link" onClick={(e) => { e.stopPropagation(); setEditingOrder(o); }}>edit</button>
                          <button className="link danger" disabled={busy} onClick={(e) => { e.stopPropagation(); dispatch(deleteOrder(o.id)); }}>remove</button>
                        </td>
                      </tr>
                    ))}
                    {!scenario.orders.length && <tr><td colSpan={6} className="muted">No orders yet. Click the map, then "Add order".</td></tr>}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
