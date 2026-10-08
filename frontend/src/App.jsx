import { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api/client";
import { Welcome } from "./components/EmptyState";
import Sidebar from "./components/Sidebar";
import TopTabs from "./components/TopTabs";
import AlgorithmPage from "./pages/AlgorithmPage";
import ComparePage from "./pages/ComparePage";
import SetupPage from "./pages/SetupPage";
import { clearError, fetchCities, fetchScenarios, loadScenario } from "./store/scenarioSlice";

export default function App() {
  const dispatch = useDispatch();
  const { error, list, listLoaded, current } = useSelector((s) => s.scenario);
  const [health, setHealth] = useState(null);

  useEffect(() => {
    dispatch(fetchCities());
    dispatch(fetchScenarios()).unwrap().then((items) => {
      if (items.length) dispatch(loadScenario(items[0].id));
    }).catch(() => {});
    const ping = () => api.health().then(setHealth).catch(() => setHealth(null));
    ping();
    const id = setInterval(ping, 15000);
    return () => clearInterval(id);
  }, [dispatch]);

  const noScenarios = listLoaded && list.length === 0 && !current;

  return (
    <div className="app">
      <Sidebar health={health} />
      <main className="main">
        {error && (
          <div className="alert">
            {error} <button className="link" onClick={() => dispatch(clearError())}>dismiss</button>
          </div>
        )}
        {noScenarios ? (
          <Welcome />
        ) : (
          <>
            <TopTabs />
            {!current ? (
              <div className="loading">Loading scenario…</div>
            ) : (
              <Routes>
                <Route path="/" element={<Navigate to="/setup" replace />} />
                <Route path="/setup" element={<SetupPage />} />
                <Route path="/greedy" element={<AlgorithmPage algorithm="greedy" />} />
                <Route path="/hungarian" element={<AlgorithmPage algorithm="hungarian" />} />
                <Route path="/compare" element={<ComparePage />} />
                <Route path="*" element={<Navigate to="/setup" replace />} />
              </Routes>
            )}
          </>
        )}
      </main>
    </div>
  );
}
