export const fmtTime = (minutes) => {
  if (minutes == null || Number.isNaN(minutes)) return "–";
  const m = Math.round(minutes);
  return `${String(Math.floor(m / 60)).padStart(2, "0")}:${String(m % 60).padStart(2, "0")}`;
};

export const fmtWindow = (o) => `${fmtTime(o.window_start)}–${fmtTime(o.window_end)}`;
export const pct = (x) => (x == null ? "–" : `${(x * 100).toFixed(1)}%`);
export const km = (x) => (x == null ? "–" : `${x.toFixed(1)} km`);
export const num = (x, d = 1) => (x == null ? "–" : Number(x).toFixed(d));

export const PRIORITY_LABEL = { 1: "Low", 2: "Normal", 3: "Urgent" };

// Distinct, colour-blind-friendlier palette for truck routes.
export const TRUCK_COLORS = [
  "#2563eb", "#db2777", "#16a34a", "#ea580c", "#7c3aed", "#0891b2",
  "#ca8a04", "#dc2626", "#4f46e5", "#059669", "#c026d3", "#65a30d",
  "#0284c7", "#e11d48", "#9333ea", "#d97706",
];

export const truckColorMap = (trucks = []) =>
  Object.fromEntries(trucks.map((t, i) => [t.id, TRUCK_COLORS[i % TRUCK_COLORS.length]]));

export const ALGO_META = {
  greedy: { label: "Greedy", accent: "var(--greedy)", tagline: "Sequential · urgent-first · earliest-deadline" },
  hungarian: { label: "Hungarian", accent: "var(--hungarian)", tagline: "Batched global matching · SciPy" },
};

/** Orders whose fate differs between two results (different truck, or served by only one). */
export const diffAssignments = (a, b) => {
  if (!a || !b) return [];
  const ma = Object.fromEntries(a.assignments.map((x) => [x.order_id, x]));
  const mb = Object.fromEntries(b.assignments.map((x) => [x.order_id, x]));
  const ids = new Set([...Object.keys(ma), ...Object.keys(mb)]);
  const out = [];
  for (const id of [...ids].sort()) {
    const x = ma[id];
    const y = mb[id];
    if (!x || !y || x.truck_id !== y.truck_id) {
      out.push({ orderId: id, a: x ? x.truck_id : null, b: y ? y.truck_id : null,
        costA: x ? x.cost : null, costB: y ? y.cost : null });
    }
  }
  return out;
};

/** "09:30" -> 570 (minutes since midnight). Returns NaN for bad input. */
export const toMin = (hhmm) => {
  const m = /^(\d{1,2}):(\d{2})$/.exec(String(hhmm || "").trim());
  if (!m) return NaN;
  return Number(m[1]) * 60 + Number(m[2]);
};

/** 570 -> "09:30", for <input type="time"> values. */
export const toHHMM = (minutes) => fmtTime(minutes);

export const CAPABILITIES = ["refrigerated", "hazmat", "liftgate", "fragile"];
