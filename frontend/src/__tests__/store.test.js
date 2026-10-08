import allocation, {
  DEFAULT_WEIGHTS, runAlgorithm, runCompare, setWeight,
} from "../store/allocationSlice";
import ui, { selectOrder, selectTruck } from "../store/uiSlice";
import { loadScenario } from "../store/scenarioSlice";
import { diffAssignments, fmtTime } from "../utils/format";

const result = (pairs) => ({ assignments: pairs.map(([o, t]) => ({ order_id: o, truck_id: t, cost: 1 })) });

describe("allocation slice", () => {
  const init = allocation(undefined, { type: "@@init" });

  it("starts with default weights and no results", () => {
    expect(init.params.weights).toEqual(DEFAULT_WEIGHTS);
    expect(init.results).toEqual({ greedy: null, hungarian: null });
  });

  it("marks params dirty when a weight changes", () => {
    const s = allocation(init, setWeight({ key: "distance", value: 2 }));
    expect(s.params.weights.distance).toBe(2);
    expect(s.paramsDirty).toBe(true);
  });

  it("stores a single algorithm result and invalidates the comparison", () => {
    const withSummary = { ...init, summary: { x: 1 } };
    const s = allocation(withSummary, { type: runAlgorithm.fulfilled.type, payload: { metrics: {} }, meta: { arg: "greedy" } });
    expect(s.results.greedy).toEqual({ metrics: {} });
    expect(s.summary).toBeNull();
    expect(s.status.greedy).toBe("done");
  });

  it("stores both results from compare", () => {
    const payload = { results: { greedy: { a: 1 }, hungarian: { b: 2 } }, summary: { m: 1 }, wall_time_ms: 5 };
    const s = allocation(init, { type: runCompare.fulfilled.type, payload });
    expect(s.results.hungarian).toEqual({ b: 2 });
    expect(s.status.compare).toBe("done");
  });

  it("clears results when the scenario changes", () => {
    const loaded = { ...init, results: { greedy: { a: 1 }, hungarian: { b: 1 } }, summary: {} };
    const s = allocation(loaded, { type: loadScenario.fulfilled.type, payload: { id: "x" } });
    expect(s.results).toEqual({ greedy: null, hungarian: null });
    expect(s.summary).toBeNull();
  });
});

describe("ui slice", () => {
  it("toggles truck selection", () => {
    let s = ui(undefined, selectTruck("T1"));
    expect(s.selectedTruckId).toBe("T1");
    s = ui(s, selectTruck("T1"));
    expect(s.selectedTruckId).toBeNull();
  });
  it("selecting an order also focuses its truck", () => {
    const s = ui(undefined, selectOrder({ orderId: "O1", truckId: "T9" }));
    expect(s).toMatchObject({ selectedOrderId: "O1", selectedTruckId: "T9" });
  });
});

describe("utils", () => {
  it("formats minutes as HH:MM", () => {
    expect(fmtTime(0)).toBe("00:00");
    expect(fmtTime(605.4)).toBe("10:05");
  });
  it("finds assignment disagreements", () => {
    const d = diffAssignments(result([["O1", "A"], ["O2", "B"]]), result([["O1", "A"], ["O2", "C"], ["O3", "A"]]));
    expect(d.map((x) => [x.orderId, x.a, x.b])).toEqual([["O2", "B", "C"], ["O3", null, "A"]]);
  });
});

describe("scenario slice", () => {
  // eslint-disable-next-line global-require
  const scenario = require("../store/scenarioSlice");
  const reducer = scenario.default;

  it("clears current scenario when the last one is deleted", () => {
    const s0 = { ...scenario.initialState, current: { id: "a" } };
    const s1 = reducer(s0, { type: scenario.deleteScenario.fulfilled.type, payload: { id: "a", remaining: 0 } });
    expect(s1.current).toBeNull();
  });

  it("keeps current when other scenarios remain", () => {
    const s0 = { ...scenario.initialState, current: { id: "b" } };
    const s1 = reducer(s0, { type: scenario.deleteScenario.fulfilled.type, payload: { id: "a", remaining: 1 } });
    expect(s1.current).toEqual({ id: "b" });
  });

  it("a created scenario becomes current and results are cleared", () => {
    const sc = { id: "new", trucks: [], orders: [] };
    const s1 = reducer(scenario.initialState, { type: scenario.createScenario.fulfilled.type, payload: sc });
    expect(s1.current).toBe(sc);
    const a = allocation({ ...allocation(undefined, { type: "@@init" }), results: { greedy: {}, hungarian: {} } },
      { type: scenario.createScenario.fulfilled.type, payload: sc });
    expect(a.results).toEqual({ greedy: null, hungarian: null });
  });

  it("marks the list as loaded", () => {
    const s1 = reducer(scenario.initialState, { type: scenario.fetchScenarios.fulfilled.type, payload: [] });
    expect(s1.listLoaded).toBe(true);
  });
});

describe("time helpers", () => {
  // eslint-disable-next-line global-require
  const { toMin, toHHMM } = require("../utils/format");
  it("converts HH:MM to minutes and back", () => {
    expect(toMin("09:30")).toBe(570);
    expect(toMin("bad")).toBeNaN();
    expect(toHHMM(570)).toBe("09:30");
  });
});
