import { Link } from "react-router-dom";
import NewScenarioForm from "./NewScenarioForm";

/** Shown when there are no scenarios at all. */
export function Welcome() {
  return (
    <div className="welcome">
      <div className="card welcome-card">
        <div className="eyebrow">Get started</div>
        <h1>Create your first scenario</h1>
        <p className="muted">
          Start with an <b>empty</b> scenario and add your own trucks and orders, generate <b>random</b> test
          data, or <b>import</b> a JSON file you exported before.
        </p>
        <NewScenarioForm />
      </div>
    </div>
  );
}

/** Shown on the algorithm pages when the scenario can't be run yet. */
export function NeedsData({ scenario }) {
  const missing = [];
  if (!scenario.trucks.length) missing.push("at least one truck");
  if (!scenario.orders.length) missing.push("at least one order");
  return (
    <div className="card needs-data">
      <b>Nothing to allocate yet.</b>
      <p className="muted">This scenario needs {missing.join(" and ")}.</p>
      <Link className="btn primary" to="/setup">Go to Setup</Link>
    </div>
  );
}

export const isRunnable = (scenario) => !!scenario && scenario.trucks.length > 0 && scenario.orders.length > 0;
