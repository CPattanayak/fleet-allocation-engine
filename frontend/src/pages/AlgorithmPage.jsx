import { useEffect } from "react";
import { useDispatch, useSelector } from "react-redux";
import { isRunnable, NeedsData } from "../components/EmptyState";
import FleetMap from "../components/FleetMap";
import MetricsGrid from "../components/MetricsGrid";
import RoutesPanel from "../components/RoutesPanel";
import { runAlgorithm } from "../store/allocationSlice";
import { ALGO_META } from "../utils/format";

const HOW = {
  greedy: [
    "Sort orders: urgent first, then earliest window close (EDF).",
    "For each order, evaluate every truck's current route end against hard constraints.",
    "Append it to the feasible truck with lowest marginal soft cost. Never revisit.",
  ],
  hungarian: [
    "Build a cost matrix: pending orders × trucks, plus 'leave unserved' dummy columns.",
    "SciPy finds the cheapest matching (≤ 1 new stop per truck), restricted to the look-ahead horizon if enabled.",
    "Commit the matches, advance truck clocks & positions, repeat until nothing changes.",
  ],
};

/** Dedicated view for a single strategy (segregated from the other). */
export default function AlgorithmPage({ algorithm }) {
  const dispatch = useDispatch();
  const scenario = useSelector((s) => s.scenario.current);
  const { results, status, paramsDirty, error } = useSelector((s) => s.allocation);
  const result = results[algorithm];
  const st = status[algorithm];
  const meta = ALGO_META[algorithm];

  const runnable = isRunnable(scenario);

  // run automatically the first time the tab is opened (or after the data changed)
  useEffect(() => {
    if (runnable && !result && st === "idle") dispatch(runAlgorithm(algorithm));
  }, [runnable, result, st, algorithm, dispatch]);

  return (
    <div className={`page algo-${algorithm}`}>
      <header className="page-head">
        <div>
          <div className="eyebrow" style={{ color: meta.accent }}>Strategy</div>
          <h1>{meta.label} allocation</h1>
          <p className="muted">{meta.tagline}</p>
        </div>
        <div className="row gap">
          {paramsDirty && result && <span className="hint">Parameters changed</span>}
          <button className="btn primary" style={{ background: meta.accent }} disabled={!runnable || st === "loading"}
            onClick={() => dispatch(runAlgorithm(algorithm))}>
            {st === "loading" ? "Running…" : result ? "Re-run" : "Run"}
          </button>
        </div>
      </header>

      {error && st === "error" && <div className="alert">{error}</div>}
      {!runnable && <NeedsData scenario={scenario} />}

      <ol className="how">
        {HOW[algorithm].map((s) => <li key={s}>{s}</li>)}
      </ol>

      <MetricsGrid metrics={result && result.metrics} />

      {runnable && <div className="split">
        <div className="card map-card">
          <FleetMap scenario={scenario} result={result} height={560} />
        </div>
        <div className="card side-card">
          {result ? <RoutesPanel scenario={scenario} result={result} /> : <div className="loading">Computing…</div>}
        </div>
      </div>}
    </div>
  );
}
