// Thin fetch wrapper around the API gateway. In dev, webpack proxies /api;
// in Docker, nginx does. API_BASE can override for other setups.
const API_BASE = process.env.API_BASE || "/api";

async function request(method, path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data && data.detail;
    const msg = Array.isArray(detail)
      ? detail.map((d) => `${(d.loc || []).slice(1).join(".")}: ${d.msg}`).join("; ")
      : detail || `${res.status} ${res.statusText}`;
    throw new Error(msg);
  }
  return data;
}

export const api = {
  health: () => request("GET", "/health"),
  cities: () => request("GET", "/cities"),
  algorithms: () => request("GET", "/algorithms"),
  listScenarios: () => request("GET", "/scenarios"),
  getScenario: (id) => request("GET", `/scenarios/${id}`),
  createScenario: (body) => request("POST", "/scenarios", body),          // empty or imported
  generateScenario: (params) => request("POST", "/scenarios/generate", params),
  deleteScenario: (id) => request("DELETE", `/scenarios/${id}`),
  addTruck: (sid, truck) => request("POST", `/scenarios/${sid}/trucks`, truck),
  patchTruck: (sid, tid, patch) => request("PATCH", `/scenarios/${sid}/trucks/${tid}`, patch),
  updateTruck: (sid, tid, truck) => request("PUT", `/scenarios/${sid}/trucks/${tid}`, truck),
  deleteTruck: (sid, tid) => request("DELETE", `/scenarios/${sid}/trucks/${tid}`),
  addOrder: (sid, order) => request("POST", `/scenarios/${sid}/orders`, order),
  updateOrder: (sid, oid, order) => request("PUT", `/scenarios/${sid}/orders/${oid}`, order),
  addRandomOrders: (sid, count) => request("POST", `/scenarios/${sid}/orders/random?count=${count}`),
  deleteOrder: (sid, oid) => request("DELETE", `/scenarios/${sid}/orders/${oid}`),
  allocate: (body) => request("POST", "/allocate", body),
  compare: (body) => request("POST", "/compare", body),
};
