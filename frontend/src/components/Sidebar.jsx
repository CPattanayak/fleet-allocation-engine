import logo from "../../public/favicon.svg";
import ParamsPanel from "./ParamsPanel";
import ScenarioPanel from "./ScenarioPanel";

export default function Sidebar({ health }) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <img src={logo} alt="" width={28} height={28} />
        <div>
          <div className="brand-name">Fleet Allocator</div>
          <div className="brand-sub">delivery resource engine</div>
        </div>
      </div>
      <ScenarioPanel />
      <ParamsPanel />
      <div className="health">
        {health ? (
          Object.entries(health.services).map(([k, v]) => (
            <span key={k} className={v === "ok" ? "ok" : "bad"}>● {k}</span>
          ))
        ) : <span className="bad">● gateway unreachable</span>}
      </div>
    </aside>
  );
}
