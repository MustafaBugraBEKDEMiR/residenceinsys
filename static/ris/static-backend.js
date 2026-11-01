/* In-browser backend for the static GitHub Pages demo.
 *
 * Mirrors the Django API (buildings/views.py): same filters, the same area
 * statistics and the same CSV export, computed from a pre-built JSON file
 * (scripts/build_site.py). Load this script before app.js. */
(() => {
  "use strict";

  const DATA_URL = window.RIS_DATA_URL || "data/ris.json";
  let cache = null;

  async function load() {
    if (cache) return cache;
    const raw = await (await fetch(DATA_URL)).json();
    const cols = raw.columns;
    const items = raw.rows.map((r) => {
      const o = {};
      cols.forEach((c, i) => { o[c] = r[i]; });
      return o;
    });
    cache = { meta: raw.meta, items };
    return cache;
  }

  const split = (v) => (v == null ? [] : String(v).split(",").map((s) => s.trim()).filter(Boolean));
  const num = (v) => (v === undefined || v === null || v === "" ? null : Number(v));

  function applyFilters(items, p = {}) {
    const areas = new Set(split(p.small_area));
    const risks = new Set(split(p.risk));
    const yMin = num(p.year_min), yMax = num(p.year_max), fMin = num(p.floors_min);
    const res = ["1", "true", "yes"].includes(String(p.residential ?? "").toLowerCase());
    const q = (p.q || "").trim().toLowerCase();
    return items.filter((b) => {
      if (areas.size && !areas.has(b.small_area)) return false;
      if (risks.size && !risks.has(b.risk_class)) return false;
      if (yMin !== null && !(b.construction_year !== null && b.construction_year >= yMin)) return false;
      if (yMax !== null && !(b.construction_year !== null && b.construction_year <= yMax)) return false;
      if (fMin !== null && !(b.floors_above_ground !== null && b.floors_above_ground >= fMin)) return false;
      if (res && !(b.dwellings > 0)) return false;
      if (q && !((b.street_address || "").toLowerCase().includes(q) || (b.building_name || "").toLowerCase().includes(q))) return false;
      return true;
    });
  }

  // --- geometry ------------------------------------------------------------
  const R = 6371008.8;
  const rad = (d) => (d * Math.PI) / 180;

  function haversine(lon1, lat1, lon2, lat2) {
    const dLat = rad(lat2 - lat1), dLon = rad(lon2 - lon1);
    const a = Math.sin(dLat / 2) ** 2 + Math.cos(rad(lat1)) * Math.cos(rad(lat2)) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.asin(Math.sqrt(a));
  }

  function inRing(x, y, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }

  function inPolygon(x, y, rings) {
    if (!inRing(x, y, rings[0])) return false;
    for (let k = 1; k < rings.length; k++) if (inRing(x, y, rings[k])) return false;
    return true;
  }

  function ringArea(ring) {
    // local equirectangular projection; accurate enough at city scale
    const lat0 = rad(ring.reduce((s, p) => s + p[1], 0) / ring.length);
    let a = 0;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const xi = R * rad(ring[i][0]) * Math.cos(lat0), yi = R * rad(ring[i][1]);
      const xj = R * rad(ring[j][0]) * Math.cos(lat0), yj = R * rad(ring[j][1]);
      a += xj * yi - xi * yj;
    }
    return Math.abs(a / 2);
  }

  function areaPredicate(g) {
    if (!g) return { test: () => true, area: null };
    if (g.type === "Feature") g = g.geometry;
    if (g.type === "Circle") {
      const [clon, clat] = g.center.map(Number), r = Number(g.radius);
      if (!(r > 0 && r <= 20000)) throw new Error("radius must be in (0, 20000] m");
      return { test: (b) => haversine(clon, clat, b.lon, b.lat) <= r, area: Math.PI * r * r };
    }
    const polys = g.type === "Polygon" ? [g.coordinates] : g.type === "MultiPolygon" ? g.coordinates : null;
    if (!polys) throw new Error("Only Polygon, MultiPolygon or Circle are supported");
    const area = polys.reduce((s, rings) => s + ringArea(rings[0]) - rings.slice(1).reduce((h, r) => h + ringArea(r), 0), 0);
    return { test: (b) => polys.some((rings) => inPolygon(b.lon, b.lat, rings)), area };
  }

  async function select(body) {
    const { items } = await load();
    const pred = areaPredicate(body.geometry);
    return { rows: applyFilters(items, body.filters || {}).filter(pred.test), area: pred.area };
  }

  const FEATURE_KEYS = ["id", "building_name", "street_address", "small_area", "construction_year",
    "refurbished_year", "floors_above_ground", "space_use", "accessibility", "dwellings",
    "dwelling_type", "est_residents", "risk_class", "property_id"];

  window.RIS_BACKEND = {
    async meta() { return (await load()).meta; },

    async buildings(params) {
      const { items } = await load();
      return {
        type: "FeatureCollection",
        features: applyFilters(items, params).map((b) => {
          const props = {};
          FEATURE_KEYS.forEach((k) => { props[k] = b[k]; });
          return { type: "Feature", id: b.id, geometry: { type: "Point", coordinates: [b.lon, b.lat] }, properties: props };
        }),
      };
    },

    async areaStats(body) {
      const { meta } = await load();
      const { rows, area } = await select(body);
      const sum = (arr, k) => arr.reduce((s, b) => s + (b[k] || 0), 0);
      const floors = rows.map((b) => b.floors_above_ground).filter((v) => v !== null);
      const years = rows.map((b) => b.construction_year).filter((v) => v !== null);
      const byArea = new Map();
      rows.forEach((b) => {
        const a = byArea.get(b.small_area) || { small_area: b.small_area, buildings: 0, est_residents: 0 };
        a.buildings += 1; a.est_residents += b.est_residents; byArea.set(b.small_area, a);
      });
      return {
        area_km2: area ? Math.round((area / 1e6) * 1e4) / 1e4 : null,
        buildings: rows.length,
        residential_buildings: rows.filter((b) => b.dwellings > 0).length,
        dwellings: sum(rows, "dwellings"),
        est_residents: Math.round(sum(rows, "est_residents")),
        floors_mean: floors.length ? Math.round((floors.reduce((s, v) => s + v, 0) / floors.length) * 10) / 10 : null,
        floors_max: floors.length ? Math.max(...floors) : null,
        oldest_construction_year: years.length ? Math.min(...years) : null,
        by_risk: meta.risk_classes.map((rc) => {
          const sub = rows.filter((b) => b.risk_class === rc.key);
          return { ...rc, buildings: sub.length, dwellings: sum(sub, "dwellings"), est_residents: Math.round(sum(sub, "est_residents")) };
        }),
        by_small_area: [...byArea.values()].sort((a, b) => b.est_residents - a.est_residents).slice(0, 10)
          .map((a) => ({ ...a, est_residents: Math.round(a.est_residents) })),
        priority_buildings: rows.filter((b) => b.dwellings > 0 && (b.risk_class === "high" || b.risk_class === "elevated"))
          .sort((a, b) => b.est_residents - a.est_residents || a.id - b.id).slice(0, 10),
        ids: rows.map((b) => b.id),
        persons_per_dwelling: meta.persons_per_dwelling,
      };
    },

    async exportCsv(body) {
      const { rows } = await select(body);
      const cols = ["property_id", "building_name", "street_address", "small_area", "construction_year",
        "refurbished_year", "floors_above_ground", "space_use", "dwellings", "dwelling_type",
        "est_residents", "risk_class", "latitude", "longitude"];
      const cell = (v) => {
        const s = v === null || v === undefined ? "" : String(v);
        return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
      };
      const lines = [cols.join(",")];
      [...rows].sort((a, b) => b.est_residents - a.est_residents || a.id - b.id).forEach((b) => {
        const o = { ...b, latitude: b.lat, longitude: b.lon };
        lines.push(cols.map((c) => cell(o[c])).join(","));
      });
      return new Blob([lines.join("\r\n") + "\r\n"], { type: "text/csv;charset=utf-8" });
    },
  };
})();
