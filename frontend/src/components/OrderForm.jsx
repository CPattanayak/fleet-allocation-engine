import { useEffect, useState } from "react";
import { CAPABILITIES, toHHMM, toMin } from "../utils/format";

const blank = () => ({
  id: "", customer: "", lat: "", lng: "", weight_kg: 25, priority: 2,
  window_start: "10:00", window_end: "13:00", service_minutes: 10, required_capabilities: [],
});

const fromOrder = (o) => ({
  id: o.id, customer: o.customer, lat: String(o.location.lat), lng: String(o.location.lng),
  weight_kg: o.weight_kg, priority: o.priority,
  window_start: toHHMM(o.window_start), window_end: toHHMM(o.window_end),
  service_minutes: o.service_minutes, required_capabilities: [...o.required_capabilities],
});

/** Form to add a new order or edit an existing one. Map clicks fill lat/lng via `picked`. */
export default function OrderForm({ editing, picked, busy, onSubmit, onCancel }) {
  const [f, setF] = useState(blank());
  const [error, setError] = useState(null);

  useEffect(() => { setF(editing ? fromOrder(editing) : blank()); setError(null); }, [editing]);
  useEffect(() => { if (picked) setF((x) => ({ ...x, lat: picked.lat.toFixed(5), lng: picked.lng.toFixed(5) })); }, [picked]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const toggleCap = (c) => setF({
    ...f,
    required_capabilities: f.required_capabilities.includes(c)
      ? f.required_capabilities.filter((x) => x !== c) : [...f.required_capabilities, c],
  });

  const submit = (e) => {
    e.preventDefault();
    const start = toMin(f.window_start);
    const end = toMin(f.window_end);
    if (f.lat === "" || f.lng === "") return setError("Pick the delivery spot on the map or type lat/lng.");
    if (!(end >= start)) return setError("Window 'to' must be after 'from'.");
    setError(null);
    const order = {
      id: f.id.trim(), customer: f.customer.trim(),
      location: { lat: Number(f.lat), lng: Number(f.lng) },
      weight_kg: Number(f.weight_kg), priority: Number(f.priority),
      window_start: start, window_end: end, service_minutes: Number(f.service_minutes),
      required_capabilities: f.required_capabilities,
    };
    onSubmit(order).then((ok) => { if (ok && !editing) setF({ ...blank(), window_start: f.window_start, window_end: f.window_end }); });
  };

  return (
    <form className="entity-form" onSubmit={submit}>
      <div className="form-title">{editing ? `Edit order ${editing.id}` : "Add an order"}</div>
      <div className="grid3">
        <label>ID<input value={f.id} onChange={set("id")} placeholder="auto" disabled={!!editing} /></label>
        <label className="span2">Customer<input value={f.customer} onChange={set("customer")} placeholder="e.g. Fresh Mart" /></label>
        <label>Lat<input value={f.lat} onChange={set("lat")} placeholder="click map" /></label>
        <label>Lng<input value={f.lng} onChange={set("lng")} placeholder="click map" /></label>
        <label>Weight kg<input type="number" min={0.1} step={0.1} value={f.weight_kg} onChange={set("weight_kg")} /></label>
        <label>From<input type="time" value={f.window_start} onChange={set("window_start")} /></label>
        <label>To<input type="time" value={f.window_end} onChange={set("window_end")} /></label>
        <label>Unload min<input type="number" min={0} value={f.service_minutes} onChange={set("service_minutes")} /></label>
        <label>Priority
          <select value={f.priority} onChange={set("priority")}>
            <option value={1}>Low</option><option value={2}>Normal</option><option value={3}>Urgent</option>
          </select>
        </label>
      </div>
      <div className="caps">
        <span className="muted small">Needs:</span>
        {CAPABILITIES.map((c) => (
          <label key={c} className="check inline"><input type="checkbox" checked={f.required_capabilities.includes(c)} onChange={() => toggleCap(c)} />{c}</label>
        ))}
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="row gap">
        <button className="btn primary" type="submit" disabled={busy}>{editing ? "Save order" : "Add order"}</button>
        {editing && <button className="btn ghost" type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
