import { createAsyncThunk, createSlice, isAnyOf } from "@reduxjs/toolkit";
import { api } from "../api/client";

export const fetchCities = createAsyncThunk("scenario/fetchCities", () => api.cities());
export const fetchScenarios = createAsyncThunk("scenario/fetchList", () => api.listScenarios());
export const loadScenario = createAsyncThunk("scenario/load", (id) => api.getScenario(id));

// Empty scenario, or one with trucks/orders from an imported JSON file.
export const createScenario = createAsyncThunk("scenario/create", async (body, { dispatch }) => {
  const sc = await api.createScenario(body);
  dispatch(fetchScenarios());
  return sc;
});

export const generateScenario = createAsyncThunk("scenario/generate", async (params, { dispatch }) => {
  const sc = await api.generateScenario(params);
  dispatch(fetchScenarios());
  return sc;
});

export const deleteScenario = createAsyncThunk("scenario/delete", async (id, { dispatch }) => {
  await api.deleteScenario(id);
  const list = await dispatch(fetchScenarios()).unwrap();
  if (list.length) await dispatch(loadScenario(list[0].id));
  return { id, remaining: list.length };
});

// Every change re-fetches the whole scenario so the store always matches the server.
const mutation = (type, fn) =>
  createAsyncThunk(`scenario/${type}`, async (arg, { getState }) => {
    const sid = getState().scenario.current.id;
    await fn(sid, arg);
    return api.getScenario(sid);
  });

export const addTruck = mutation("addTruck", (sid, truck) => api.addTruck(sid, truck));
export const updateTruck = mutation("updateTruck", (sid, truck) => api.updateTruck(sid, truck.id, truck));
export const toggleTruck = mutation("toggleTruck", (sid, t) =>
  api.patchTruck(sid, t.id, { available: !t.available }));
export const deleteTruck = mutation("deleteTruck", (sid, id) => api.deleteTruck(sid, id));
export const addOrder = mutation("addOrder", (sid, order) => api.addOrder(sid, order));
export const updateOrder = mutation("updateOrder", (sid, order) => api.updateOrder(sid, order.id, order));
export const addRandomOrders = mutation("addRandomOrders", (sid, n) => api.addRandomOrders(sid, n));
export const deleteOrder = mutation("deleteOrder", (sid, id) => api.deleteOrder(sid, id));

export const scenarioChanged = isAnyOf(
  loadScenario.fulfilled, createScenario.fulfilled, generateScenario.fulfilled,
  addTruck.fulfilled, updateTruck.fulfilled, toggleTruck.fulfilled, deleteTruck.fulfilled,
  addOrder.fulfilled, updateOrder.fulfilled, addRandomOrders.fulfilled, deleteOrder.fulfilled,
);
const mutationPending = isAnyOf(
  createScenario.pending, generateScenario.pending, addTruck.pending, updateTruck.pending,
  toggleTruck.pending, deleteTruck.pending, addOrder.pending, updateOrder.pending,
  addRandomOrders.pending, deleteOrder.pending, deleteScenario.pending,
);
const mutationRejected = isAnyOf(
  loadScenario.rejected, createScenario.rejected, generateScenario.rejected, addTruck.rejected,
  updateTruck.rejected, toggleTruck.rejected, deleteTruck.rejected, addOrder.rejected,
  updateOrder.rejected, addRandomOrders.rejected, deleteOrder.rejected, deleteScenario.rejected,
  fetchScenarios.rejected,
);

export const initialState = { list: [], listLoaded: false, current: null, cities: [], busy: false, error: null };

const slice = createSlice({
  name: "scenario",
  initialState,
  reducers: {
    clearError: (s) => { s.error = null; },
  },
  extraReducers: (b) => {
    b.addCase(fetchCities.fulfilled, (s, a) => { s.cities = a.payload; })
      .addCase(fetchScenarios.fulfilled, (s, a) => { s.list = a.payload; s.listLoaded = true; })
      .addCase(deleteScenario.fulfilled, (s, a) => {
        s.busy = false;
        if (a.payload.remaining === 0) s.current = null;   // deleted the last one
      })
      .addMatcher(mutationPending, (s) => { s.busy = true; s.error = null; })
      .addMatcher(scenarioChanged, (s, a) => { s.current = a.payload; s.busy = false; s.error = null; })
      .addMatcher(mutationRejected, (s, a) => { s.busy = false; s.error = a.error.message; });
  },
});

export const { clearError } = slice.actions;
export default slice.reducer;
