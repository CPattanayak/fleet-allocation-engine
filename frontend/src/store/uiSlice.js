import { createSlice } from "@reduxjs/toolkit";
import { scenarioChanged } from "./scenarioSlice";

export const MAP_MODES = { VIEW: "view", ADD_ORDER: "addOrder", ADD_TRUCK: "addTruck" };

export const initialState = { selectedTruckId: null, selectedOrderId: null, mapMode: MAP_MODES.VIEW };

const slice = createSlice({
  name: "ui",
  initialState,
  reducers: {
    selectTruck: (s, { payload }) => {
      s.selectedTruckId = s.selectedTruckId === payload ? null : payload;
      s.selectedOrderId = null;
    },
    selectOrder: (s, { payload }) => {
      s.selectedOrderId = payload ? payload.orderId : null;
      s.selectedTruckId = payload ? payload.truckId || null : null;
    },
    clearSelection: (s) => { s.selectedTruckId = null; s.selectedOrderId = null; },
    setMapMode: (s, { payload }) => { s.mapMode = payload; },
  },
  extraReducers: (b) => {
    b.addMatcher(scenarioChanged, (s) => {
      s.selectedTruckId = null;
      s.selectedOrderId = null;
    });
  },
});

export const { selectTruck, selectOrder, clearSelection, setMapMode } = slice.actions;
export default slice.reducer;
