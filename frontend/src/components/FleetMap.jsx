import { Fragment, useEffect, useMemo } from "react";
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip, useMap, useMapEvents } from "react-leaflet";
import { useDispatch, useSelector } from "react-redux";
import { selectOrder, selectTruck } from "../store/uiSlice";
import { fmtTime, fmtWindow, PRIORITY_LABEL, truckColorMap } from "../utils/format";

const UNASSIGNED = "#dc2626";
const PENDING = "#64748b";

function FitBounds({ scenario }) {
  const map = useMap();
  useEffect(() => {
    if (!scenario) return;
    const pts = [...scenario.trucks.map((t) => t.depot), ...scenario.orders.map((o) => o.location)];
    if (pts.length) map.fitBounds(pts.map((p) => [p.lat, p.lng]), { padding: [24, 24], maxZoom: 14 });
    else map.setView([scenario.city.center.lat, scenario.city.center.lng], 12); // empty scenario: show the city
  }, [scenario && scenario.id, map]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function ClickCapture({ onClick }) {
  useMapEvents({ click: (e) => onClick && onClick(e.latlng) });
  return null;
}

/**
 * Spatial view of a scenario, optionally overlaid with an allocation result.
 * Trucks = squares-ish thick-ringed circles at depots; orders = small dots coloured by
 * assigned truck; unassigned = red ring; routes = polylines (dashed leg = return to depot).
 */
export default function FleetMap({ scenario, result, height = 520, onMapClick, cursor, previewPoint }) {
  const dispatch = useDispatch();
  const { selectedTruckId, selectedOrderId } = useSelector((s) => s.ui);
  const colors = useMemo(() => truckColorMap(scenario ? scenario.trucks : []), [scenario]);

  const assignmentByOrder = useMemo(
    () => Object.fromEntries((result ? result.assignments : []).map((a) => [a.order_id, a])),
    [result],
  );
  const unassignedIds = useMemo(
    () => new Set((result ? result.unassigned : []).map((u) => u.order_id)),
    [result],
  );

  if (!scenario) return <div className="map-placeholder" style={{ height }}>No scenario loaded</div>;

  const center = [scenario.city.center.lat, scenario.city.center.lng];
  const trucksById = Object.fromEntries(scenario.trucks.map((t) => [t.id, t]));
  const dim = (truckId) => selectedTruckId && truckId !== selectedTruckId;

  return (
    <div className="map-wrap" style={{ height, cursor }}>
      <MapContainer center={center} zoom={12} style={{ height: "100%", width: "100%" }} preferCanvas>
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitBounds scenario={scenario} />
        {onMapClick && <ClickCapture onClick={onMapClick} />}

        {result && result.routes.map((r) => {
          const t = trucksById[r.truck_id];
          if (!t) return null;
          const path = [t.depot, ...r.stops.map((s) => s.location)].map((p) => [p.lat, p.lng]);
          const last = path[path.length - 1];
          const op = dim(r.truck_id) ? 0.12 : 0.85;
          return (
            <Fragment key={r.truck_id}>
              <Polyline positions={path} pathOptions={{ color: colors[r.truck_id], weight: selectedTruckId === r.truck_id ? 5 : 3, opacity: op }} />
              <Polyline positions={[last, [t.depot.lat, t.depot.lng]]} pathOptions={{ color: colors[r.truck_id], weight: 2, opacity: op * 0.6, dashArray: "4 6" }} />
            </Fragment>
          );
        })}

        {scenario.orders.map((o) => {
          const a = assignmentByOrder[o.id];
          const un = unassignedIds.has(o.id);
          const color = a ? colors[a.truck_id] : un ? UNASSIGNED : PENDING;
          const selected = selectedOrderId === o.id;
          const faded = a ? dim(a.truck_id) : !!selectedTruckId;
          return (
            <CircleMarker
              key={o.id}
              center={[o.location.lat, o.location.lng]}
              radius={selected ? 9 : o.priority === 3 ? 6.5 : 5}
              pathOptions={{
                color: un ? UNASSIGNED : "#0f172a",
                weight: un ? 2.5 : selected ? 2.5 : 1,
                fillColor: un ? "#fff" : color,
                fillOpacity: faded ? 0.15 : 0.95,
                opacity: faded ? 0.25 : 1,
              }}
              eventHandlers={{ click: () => dispatch(selectOrder({ orderId: o.id, truckId: a && a.truck_id })) }}
            >
              <Tooltip direction="top" offset={[0, -4]}>{o.id} · {o.weight_kg} kg · {fmtWindow(o)}</Tooltip>
              <Popup>
                <div className="popup">
                  <strong>{o.id}</strong> — {o.customer}
                  <div>{PRIORITY_LABEL[o.priority]} priority · {o.weight_kg} kg · window {fmtWindow(o)}</div>
                  {o.required_capabilities.length > 0 && <div>Needs: {o.required_capabilities.join(", ")}</div>}
                  {a && (
                    <div className="popup-expl">
                      <b style={{ color: colors[a.truck_id] }}>{a.truck_id}</b> · stop #{a.sequence} · ETA {fmtTime(a.eta)}
                      <p>{a.explanation}</p>
                    </div>
                  )}
                  {un && <p className="popup-expl bad">{result.unassigned.find((u) => u.order_id === o.id).reason}</p>}
                </div>
              </Popup>
            </CircleMarker>
          );
        })}

        {scenario.trucks.map((t) => (
          <CircleMarker
            key={t.id}
            center={[t.depot.lat, t.depot.lng]}
            radius={selectedTruckId === t.id ? 11 : 8}
            pathOptions={{
              color: t.available ? colors[t.id] : "#94a3b8",
              weight: 4,
              fillColor: "#0f172a",
              fillOpacity: dim(t.id) ? 0.2 : 0.9,
              opacity: dim(t.id) ? 0.3 : 1,
              dashArray: t.available ? null : "3 3",
            }}
            eventHandlers={{ click: () => dispatch(selectTruck(t.id)) }}
          >
            <Tooltip direction="top" offset={[0, -6]}>
              {t.name} ({t.id}) · {t.capacity_kg} kg{t.capabilities.length ? ` · ${t.capabilities.join(", ")}` : ""}
              {!t.available && " · OFF DUTY"}
            </Tooltip>
          </CircleMarker>
        ))}
        {previewPoint && (
          <CircleMarker center={[previewPoint.lat, previewPoint.lng]} radius={9}
            pathOptions={{ color: "#e0761b", weight: 3, dashArray: "4 3", fillColor: "#e0761b", fillOpacity: 0.25 }}>
            <Tooltip permanent direction="top" offset={[0, -8]}>picked spot</Tooltip>
          </CircleMarker>
        )}
      </MapContainer>
      <div className="map-legend">
        <span><i className="lg-truck" /> Truck (depot)</span>
        <span><i className="lg-order" /> Order</span>
        <span><i className="lg-unassigned" /> Unassigned</span>
        <span><i className="lg-return" /> Return leg</span>
      </div>
    </div>
  );
}
