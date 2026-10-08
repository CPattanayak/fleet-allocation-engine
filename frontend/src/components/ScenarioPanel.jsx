import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { deleteScenario, loadScenario } from "../store/scenarioSlice";
import NewScenarioForm from "./NewScenarioForm";

export default function ScenarioPanel() {
  const dispatch = useDispatch();
  const { list, current, busy } = useSelector((s) => s.scenario);
  const [open, setOpen] = useState(false);

  return (
    <section className="side-section">
      <h3>Scenario</h3>
      {list.length > 0 ? (
        <select value={current ? current.id : ""} onChange={(e) => dispatch(loadScenario(e.target.value))} disabled={busy}>
          {list.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
      ) : (
        <p className="muted small">No scenarios yet.</p>
      )}
      {current && (
        <div className="side-meta">
          <span>{current.city.name}</span>
          <span>{current.trucks.length} trucks</span>
          <span>{current.orders.length} orders</span>
          {current.seed != null && <span>seed {current.seed}</span>}
        </div>
      )}
      <div className="row gap">
        <button className="btn ghost" onClick={() => setOpen(!open)}>{open ? "Cancel" : "+ New scenario"}</button>
        {current && (
          <button className="btn ghost danger" disabled={busy}
            onClick={() => { if (window.confirm(`Delete "${current.name}"?`)) dispatch(deleteScenario(current.id)); }}>
            Delete
          </button>
        )}
      </div>
      {open && <NewScenarioForm dark onDone={() => setOpen(false)} />}
    </section>
  );
}
