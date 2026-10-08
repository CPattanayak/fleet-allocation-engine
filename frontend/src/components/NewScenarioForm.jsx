import { useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { useNavigate } from "react-router-dom";
import { createScenario, generateScenario } from "../store/scenarioSlice";

const MODES = [
  ["empty", "Empty"],
  ["random", "Random"],
  ["import", "Import JSON"],
];

/**
 * Three ways to start a scenario:
 *  - Empty:   just a name + city, then add trucks/orders yourself in Setup
 *  - Random:  generated test data (handy for big comparisons)
 *  - Import:  paste or upload a JSON file exported earlier
 */
export default function NewScenarioForm({ onDone, dark = false }) {
  const dispatch = useDispatch();
  const navigate = useNavigate();
  const { cities, busy } = useSelector((s) => s.scenario);
  const [mode, setMode] = useState("empty");
  const [name, setName] = useState("");
  const [city, setCity] = useState("bengaluru");
  const [gen, setGen] = useState({ num_trucks: 10, num_orders: 40, tightness: "normal", seed: "" });
  const [json, setJson] = useState("");
  const [localError, setLocalError] = useState(null);

  const finish = (promise, goTo) =>
    promise.unwrap().then(() => {
      setLocalError(null);
      if (onDone) onDone();
      navigate(goTo);
    }).catch(() => {});   // server error is shown in the top banner

  const submit = (e) => {
    e.preventDefault();
    if (mode === "empty") {
      finish(dispatch(createScenario({ name: name.trim() || "My scenario", city })), "/setup");
    } else if (mode === "random") {
      finish(dispatch(generateScenario({
        name: name.trim() || null, city,
        num_trucks: Number(gen.num_trucks), num_orders: Number(gen.num_orders),
        tightness: gen.tightness, seed: gen.seed === "" ? null : Number(gen.seed),
      })), "/greedy");
    } else {
      let data;
      try {
        data = JSON.parse(json);
      } catch {
        setLocalError("That isn't valid JSON.");
        return;
      }
      finish(dispatch(createScenario({
        name: name.trim() || data.name || "Imported scenario",
        city: data.city && data.city.id ? data.city.id : data.city || city,
        trucks: data.trucks || [],
        orders: data.orders || [],
      })), "/setup");
    }
  };

  const readFile = (e) => {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    file.text().then(setJson);
  };

  return (
    <form className={`new-form ${dark ? "dark" : ""}`} onSubmit={submit}>
      <div className="seg">
        {MODES.map(([key, label]) => (
          <button type="button" key={key} className={mode === key ? "on" : ""} onClick={() => setMode(key)}>{label}</button>
        ))}
      </div>

      <label>Name
        <input value={name} onChange={(e) => setName(e.target.value)}
          placeholder={mode === "import" ? "(from file)" : "e.g. Monday deliveries"} />
      </label>
      {mode !== "import" && (
        <label>City
          <select value={city} onChange={(e) => setCity(e.target.value)}>
            {cities.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
      )}

      {mode === "random" && (
        <div className="grid2">
          <label>Trucks<input type="number" min={1} max={200} value={gen.num_trucks} onChange={(e) => setGen({ ...gen, num_trucks: e.target.value })} /></label>
          <label>Orders<input type="number" min={1} max={1000} value={gen.num_orders} onChange={(e) => setGen({ ...gen, num_orders: e.target.value })} /></label>
          <label>Time windows
            <select value={gen.tightness} onChange={(e) => setGen({ ...gen, tightness: e.target.value })}>
              <option value="relaxed">Relaxed</option>
              <option value="normal">Normal</option>
              <option value="tight">Tight</option>
            </select>
          </label>
          <label>Seed<input type="number" placeholder="random" value={gen.seed} onChange={(e) => setGen({ ...gen, seed: e.target.value })} /></label>
        </div>
      )}

      {mode === "import" && (
        <>
          <label>JSON file<input type="file" accept=".json,application/json" onChange={readFile} /></label>
          <label>…or paste JSON
            <textarea rows={5} value={json} onChange={(e) => setJson(e.target.value)}
              placeholder='{"name": "...", "city": "bengaluru", "trucks": [...], "orders": [...]}' />
          </label>
        </>
      )}

      {localError && <div className="form-error">{localError}</div>}
      <button className="btn primary" type="submit" disabled={busy}>
        {mode === "empty" ? "Create empty scenario" : mode === "random" ? "Generate" : "Import"}
      </button>
    </form>
  );
}
