import { createAsyncThunk, createSlice } from "@reduxjs/toolkit";
import { api } from "../api/client";
import { scenarioChanged } from "./scenarioSlice";

export const ALGORITHMS = ["greedy", "hungarian"];

export const DEFAULT_WEIGHTS = {
  distance: 1.0,
  waiting: 0.2,
  over_qualification: 3.0,
  load_balance: 0.5,
  lateness_risk: 0.05,
  unassigned_penalty: 500,
};

const requestBody = (state) => {
  const { params } = state.allocation;
  return {
    scenario_id: state.scenario.current.id,
    weights: params.weights,
    road_factor: params.roadFactor,
    single_stop: params.singleStop,
    hungarian_wait_horizon: params.horizonOn ? params.horizon : null,
  };
};

export const runAlgorithm = createAsyncThunk("allocation/run", async (algorithm, { getState }) => {
  const res = await api.allocate({ ...requestBody(getState()), algorithm });
  return res.result;
});

export const runCompare = createAsyncThunk("allocation/compare", (_, { getState }) =>
  api.compare(requestBody(getState())));

const emptyStatus = () => ({ greedy: "idle", hungarian: "idle", compare: "idle" });

export const initialState = {
  params: { weights: { ...DEFAULT_WEIGHTS }, roadFactor: 1.3, singleStop: false, horizonOn: true, horizon: 60 },
  paramsDirty: false,
  results: { greedy: null, hungarian: null },
  summary: null,
  wallTimeMs: null,
  status: emptyStatus(),
  error: null,
};

const clearResults = (s) => {
  s.results = { greedy: null, hungarian: null };
  s.summary = null;
  s.status = emptyStatus();
};

const slice = createSlice({
  name: "allocation",
  initialState,
  reducers: {
    setWeight: (s, { payload: { key, value } }) => {
      s.params.weights[key] = value;
      s.paramsDirty = true;
    },
    setRoadFactor: (s, { payload }) => { s.params.roadFactor = payload; s.paramsDirty = true; },
    setSingleStop: (s, { payload }) => { s.params.singleStop = payload; s.paramsDirty = true; },
    setHorizon: (s, { payload: { on, minutes } }) => {
      if (on !== undefined) s.params.horizonOn = on;
      if (minutes !== undefined) s.params.horizon = minutes;
      s.paramsDirty = true;
    },
    resetParams: (s) => {
      s.params = { ...initialState.params, weights: { ...DEFAULT_WEIGHTS } };
      s.paramsDirty = true;
    },
  },
  extraReducers: (b) => {
    b.addCase(runAlgorithm.pending, (s, a) => { s.status[a.meta.arg] = "loading"; s.error = null; })
      .addCase(runAlgorithm.fulfilled, (s, a) => {
        s.results[a.meta.arg] = a.payload;
        s.status[a.meta.arg] = "done";
        s.summary = null; // compare summary no longer matches
        s.status.compare = "idle";
        s.paramsDirty = false;
      })
      .addCase(runAlgorithm.rejected, (s, a) => { s.status[a.meta.arg] = "error"; s.error = a.error.message; })
      .addCase(runCompare.pending, (s) => {
        s.status.compare = s.status.greedy = s.status.hungarian = "loading";
        s.error = null;
      })
      .addCase(runCompare.fulfilled, (s, { payload }) => {
        s.results = payload.results;
        s.summary = payload.summary;
        s.wallTimeMs = payload.wall_time_ms;
        s.status = { greedy: "done", hungarian: "done", compare: "done" };
        s.paramsDirty = false;
      })
      .addCase(runCompare.rejected, (s, a) => {
        s.status = { greedy: "error", hungarian: "error", compare: "error" };
        s.error = a.error.message;
      })
      // Any change to the scenario invalidates previous results.
      .addMatcher(scenarioChanged, clearResults);
  },
});

export const { setWeight, setRoadFactor, setSingleStop, setHorizon, resetParams } = slice.actions;
export default slice.reducer;
