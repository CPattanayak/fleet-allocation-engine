import { configureStore } from "@reduxjs/toolkit";
import scenario from "./scenarioSlice";
import allocation from "./allocationSlice";
import ui from "./uiSlice";

export const makeStore = (preloadedState) =>
  configureStore({ reducer: { scenario, allocation, ui }, preloadedState });

export const store = makeStore();
