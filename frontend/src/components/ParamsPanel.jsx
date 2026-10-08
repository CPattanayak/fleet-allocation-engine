import { useDispatch, useSelector } from "react-redux";
import { resetParams, setHorizon, setRoadFactor, setSingleStop, setWeight } from "../store/allocationSlice";

const SLIDERS = [
  ["distance", "Distance", 0, 3, 0.1, "per km driven"],
  ["waiting", "Idle waiting", 0, 1, 0.05, "per minute before window"],
  ["over_qualification", "Save special trucks", 0, 15, 0.5, "per unused capability"],
  ["load_balance", "Load balance", 0, 5, 0.1, "per stop already on route"],
  ["lateness_risk", "Lateness risk", 0, 1, 0.01, "per min of slack < 30"],
  ["unassigned_penalty", "Unserved penalty", 50, 2000, 50, "× priority"],
];

/** Soft-constraint weights shared by both algorithms. */
export default function ParamsPanel() {
  const dispatch = useDispatch();
  const { params } = useSelector((s) => s.allocation);
  return (
    <section className="side-section">
      <div className="row between">
        <h3>Soft constraints</h3>
        <button className="link" onClick={() => dispatch(resetParams())}>reset</button>
      </div>
      {SLIDERS.map(([key, label, min, max, step, hint]) => (
        <label key={key} className="slider">
          <span className="row between"><span>{label}</span><span className="mono">{params.weights[key]}</span></span>
          <input type="range" min={min} max={max} step={step} value={params.weights[key]}
            onChange={(e) => dispatch(setWeight({ key, value: Number(e.target.value) }))} />
          <small className="muted">{hint}</small>
        </label>
      ))}
      <label className="slider">
        <span className="row between"><span>Road factor</span><span className="mono">{params.roadFactor}</span></span>
        <input type="range" min={1} max={2} step={0.05} value={params.roadFactor}
          onChange={(e) => dispatch(setRoadFactor(Number(e.target.value)))} />
        <small className="muted">road km ÷ straight-line km</small>
      </label>
      <label className="check">
        <input type="checkbox" checked={params.horizonOn} onChange={(e) => dispatch(setHorizon({ on: e.target.checked }))} />
        <span>Hungarian look-ahead <small className="muted">(per round, match only orders a truck can start within the horizon)</small></span>
      </label>
      {params.horizonOn && (
        <label className="slider">
          <span className="row between"><span>Look-ahead horizon</span><span className="mono">{params.horizon} min</span></span>
          <input type="range" min={0} max={480} step={15} value={params.horizon}
            onChange={(e) => dispatch(setHorizon({ minutes: Number(e.target.value) }))} />
          <small className="muted">max idle wait allowed in a matching round</small>
        </label>
      )}
      <label className="check">
        <input type="checkbox" checked={params.singleStop} onChange={(e) => dispatch(setSingleStop(e.target.checked))} />
        <span>One order per truck <small className="muted">(pure matching — Hungarian is provably optimal)</small></span>
      </label>
    </section>
  );
}
