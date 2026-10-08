import { useEffect, useState } from "react";
import { CAPABILITIES, toHHMM, toMin } from "../utils/format";

const blank = () => ({
  id: "", name: "", lat: "", lng: "",
  capacity_kg: 500, max_stops: 8, shift_start: "08:00", shift_end: "20:00",
  speed_kmh: 30, cost_per_km: 1, capabilities: [], available: true,
});

const fromTruck = (t) => ({
  id: t.id, name: t.name, lat: String(t.depot.lat), lng: String(t.depot.lng),
  capacity_kg: t.capacity_kg, max_stops: t.max_stops,
  shift_start: toHHMM(t.shift_start), shift_end: toHHMM(t.shift_end),
  speed_kmh: t.speed_kmh, cost_per_km: t.cost_per_km, capabilities: [...t.capabilities], available: t.available,
});

/** Form to add a new truck or edit an existing one. Map clicks fill lat/lng via `picked`. */
export default function TruckForm({ editing, picked, busy, onSubmit, onCancel }) {
  const [f, setF] = useState(blank());
  const [error, setError] = useState(null);

  // switch between "add" and "edit"
  useEffect(() => { setF(editing ? fromTruck(editing) : blank()); setError(null); }, [editing]); // eslint-disable-line
  // a map click fills the location
  useEffect(() => { if (picked) setF((x) => ({ ...x, lat: picked.lat.toFixed(5), lng: picked.lng.toFixed(5) })); }, [picked]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const toggleCap = (c) => setF({ ...f, capabilities: f.capabilities.includes(c) ? f.capabilities.filter((x) => x !== c) : [...f.capabilities, c] });

  const submit = (e) => {
    e.preventDefault();
    const start = toMin(f.shift_start);
    const end = toMin(f.shift_end);
    if (f.lat === "" || f.lng === "") return setError("Pick the depot on the map or type lat/lng.");
    if (!(end > start)) return setError("Shift end must be after shift start.");
    setError(null);
    const truck = {
      id: f.id.trim(), name: f.name.trim(),
      depot: { lat: Number(f.lat), lng: Number(f.lng) },
      capacity_kg: Number(f.capacity_kg), max_stops: Number(f.max_stops),
      shift_start: start, shift_end: end,
      speed_kmh: Number(f.speed_kmh), cost_per_km: Number(f.cost_per_km),
      capabilities: f.capabilities, available: f.available,
    };
    onSubmit(truck).then((ok) => { if (ok && !editing) setF(blank()); });
  };

  return (
    <form className="entity-form" onSubmit={submit}>
      <div className="form-title">{editing ? `Edit truck ${editing.id}` : "Add a truck"}</div>
      <div className="grid3">
        <label>ID<input value={f.id} onChange={set("id")} placeholder="auto" disabled={!!editing} /></label>
        <label className="span2">Name<input value={f.name} onChange={set("name")} placeholder="e.g. Van 01" /></label>
        <label>Depot lat<input value={f.lat} onChange={set("lat")} placeholder="click map" /></label>
        <label>Depot lng<input value={f.lng} onChange={set("lng")} placeholder="click map" /></label>
        <label>Capacity kg<input type="number" min={1} value={f.capacity_kg} onChange={set("capacity_kg")} /></label>
        <label>Shift start<input type="time" value={f.shift_start} onChange={set("shift_start")} /></label>
        <label>Shift end<input type="time" value={f.shift_end} onChange={set("shift_end")} /></label>
        <label>Max stops<input type="number" min={1} value={f.max_stops} onChange={set("max_stops")} /></label>
        <label>Speed km/h<input type="number" min={1} value={f.speed_kmh} onChange={set("speed_kmh")} /></label>
        <label>Cost per km<input type="number" min={0} step={0.1} value={f.cost_per_km} onChange={set("cost_per_km")} /></label>
        <label className="check inline"><input type="checkbox" checked={f.available} onChange={set("available")} />On duty</label>
      </div>
      <div className="caps">
        {CAPABILITIES.map((c) => (
          <label key={c} className="check inline"><input type="checkbox" checked={f.capabilities.includes(c)} onChange={() => toggleCap(c)} />{c}</label>
        ))}
      </div>
      {error && <div className="form-error">{error}</div>}
      <div className="row gap">
        <button className="btn primary" type="submit" disabled={busy}>{editing ? "Save truck" : "Add truck"}</button>
        {editing && <button className="btn ghost" type="button" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}
